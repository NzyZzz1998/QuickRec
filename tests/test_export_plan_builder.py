from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from exporting import plan_builder as plan_builder_module
from exporting.models import (
    ExportMaterialProbe,
    ExportPlanRequest,
    OverwriteMode,
)
from exporting.plan_builder import ExportPlanBuilder
from utils.project_store import ProjectFile, ProjectMaterialRef, load_project, save_project
from utils.timeline_model import (
    TIMELINE_SCHEMA_V1,
    Timeline,
    TimelineClip,
    TimelineTrack,
    load_project_timeline,
    with_project_timeline,
)


def _project_file(
    tmp_path: Path,
    *,
    media_name: str = "中文 素材.mp4",
    include_clip: bool = True,
    timeline_schema_version: int = 2,
) -> tuple[Path, Path]:
    media = tmp_path / media_name
    media.write_bytes(b"controlled-media")
    project = ProjectFile(
        project_id="project-1",
        name="演示:项目",
        description="",
        created_at="2026-07-29T10:00:00+00:00",
        updated_at="2026-07-29T10:00:00+00:00",
        materials=[
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=str(media),
                file_name=media.name,
                added_at="2026-07-29T10:00:00+00:00",
                metadata_snapshot={
                    "duration_sec": 2.0,
                    "width": 1920,
                    "height": 1080,
                    "fps": 60.0,
                },
            )
        ],
    )
    timeline = Timeline(
        timeline_id="timeline-1",
        schema_version=timeline_schema_version,
        tracks=[
            TimelineTrack("video-1", "video", "视频 1", 0),
            TimelineTrack("audio-1", "audio", "音频 1", 0),
        ],
        clips=(
            [
                TimelineClip(
                    clip_id="video-clip",
                    material_id="material-1",
                    track_id="video-1",
                    timeline_start_us=0,
                    timeline_duration_us=2_000_000,
                    source_start_us=0,
                    source_duration_us=2_000_000,
                    link_group_id="link-1",
                ),
                TimelineClip(
                    clip_id="audio-clip",
                    material_id="material-1",
                    track_id="audio-1",
                    timeline_start_us=0,
                    timeline_duration_us=2_000_000,
                    source_start_us=0,
                    source_duration_us=2_000_000,
                    link_group_id="link-1",
                ),
            ]
            if include_clip
            else []
        ),
    )
    project = with_project_timeline(project, timeline)
    project_path = tmp_path / "project.qrproj"
    assert save_project(project_path, project).ok
    return project_path, media


def _probe(path: Path) -> ExportMaterialProbe:
    return ExportMaterialProbe(
        container="mov,mp4,m4a,3gp,3g2,mj2",
        video_codec="h264",
        width=1920,
        height=1080,
        fps=60.0,
        duration_us=2_000_000,
        audio_codec="aac",
        audio_sample_rate=48_000,
        audio_channels=2,
        audio_duration_us=2_000_000,
    )


def _builder() -> ExportPlanBuilder:
    return ExportPlanBuilder(
        media_probe=_probe,
        ffmpeg_resolver=lambda: __file__,
        ffprobe_resolver=lambda: __file__,
        free_space_provider=lambda _path: 10 * 1024**3,
        clock=lambda: "2026-07-29T12:00:00+00:00",
        id_factory=lambda: "plan-1",
    )


def _request(project_path: Path, output_dir: Path) -> ExportPlanRequest:
    return ExportPlanRequest(
        project_path=str(project_path),
        width=1920,
        height=1080,
        fps=60,
        output_directory=str(output_dir),
        filename="演示:项目.mp4",
    )


def test_builder_freezes_saved_timeline_material_and_safe_filename(tmp_path: Path) -> None:
    project_path, media = _project_file(tmp_path)
    result = _builder().build(_request(project_path, tmp_path / "Exports"))

    assert result.ok
    assert result.plan is not None
    assert result.plan.plan_id == "plan-1"
    assert result.plan.project.project_id == "project-1"
    assert result.plan.timeline.duration_us == 2_000_000
    assert len(result.plan.timeline.tracks) == 2
    assert len(result.plan.timeline.clips) == 2
    assert result.plan.materials[0].path == str(media.resolve())
    assert result.plan.materials[0].size_bytes == media.stat().st_size
    assert result.plan.output.filename == "演示_项目.mp4"
    assert Path(result.plan.output.directory).is_dir()


def test_builder_plan_is_unchanged_after_project_and_media_mutate(tmp_path: Path) -> None:
    project_path, media = _project_file(tmp_path)
    builder = _builder()
    first = builder.build(_request(project_path, tmp_path / "Exports"))
    assert first.plan is not None

    media.write_bytes(b"changed-media")
    project_path.write_text("{}", encoding="utf-8")

    assert first.plan.materials[0].size_bytes == len(b"controlled-media")
    assert first.plan.timeline.clips[0].clip_id == "video-clip"


def test_builder_rejects_empty_timeline(tmp_path: Path) -> None:
    project_path, _ = _project_file(tmp_path, include_clip=False)

    result = _builder().build(_request(project_path, tmp_path / "Exports"))

    assert not result.ok
    assert result.plan is None
    assert result.errors[0].code == "TIMELINE_EMPTY"


def test_builder_rejects_timeline_schema_v1(tmp_path: Path) -> None:
    project_path, _ = _project_file(
        tmp_path,
        timeline_schema_version=TIMELINE_SCHEMA_V1,
    )

    result = _builder().build(_request(project_path, tmp_path / "Exports"))

    assert not result.ok
    assert {error.code for error in result.errors} == {
        "TIMELINE_SCHEMA_UNSUPPORTED"
    }


def test_builder_rejects_missing_or_unreadable_media(tmp_path: Path) -> None:
    project_path, media = _project_file(tmp_path)
    media.unlink()

    result = _builder().build(_request(project_path, tmp_path / "Exports"))

    assert not result.ok
    assert {error.code for error in result.errors} == {"MATERIAL_MISSING"}


@pytest.mark.parametrize(
    ("video_codec", "audio_codec", "expected_context"),
    [
        ("hevc", "aac", "video"),
        ("h264", "mp3", "audio"),
    ],
)
def test_builder_rejects_unsupported_referenced_stream_codec(
    tmp_path: Path,
    video_codec: str,
    audio_codec: str,
    expected_context: str,
) -> None:
    project_path, _ = _project_file(tmp_path)

    def unsupported_probe(_path: Path) -> ExportMaterialProbe:
        return ExportMaterialProbe(
            container="mov,mp4,m4a,3gp,3g2,mj2",
            video_codec=video_codec,
            width=1920,
            height=1080,
            fps=60.0,
            duration_us=2_000_000,
            audio_codec=audio_codec,
            audio_sample_rate=48_000,
            audio_channels=2,
            audio_duration_us=2_000_000,
        )

    builder = ExportPlanBuilder(
        media_probe=unsupported_probe,
        ffmpeg_resolver=lambda: __file__,
        ffprobe_resolver=lambda: __file__,
        free_space_provider=lambda _path: 10 * 1024**3,
    )

    result = builder.build(_request(project_path, tmp_path / "Exports"))

    assert not result.ok
    assert result.errors[0].code == "MATERIAL_CODEC_UNSUPPORTED"
    assert result.errors[0].context["stream"] == expected_context


def test_builder_rejects_pending_save_external_conflict_and_job_limit(tmp_path: Path) -> None:
    project_path, _ = _project_file(tmp_path)
    request = replace(
        _request(project_path, tmp_path / "Exports"),
        save_pending=True,
        external_conflict=True,
        incomplete_job_count=20,
    )

    result = _builder().build(request)

    assert not result.ok
    assert {error.code for error in result.errors} == {
        "PROJECT_SAVE_PENDING",
        "PROJECT_EXTERNAL_CONFLICT",
        "QUEUE_LIMIT_REACHED",
    }


def test_builder_rejects_missing_media_tools(tmp_path: Path) -> None:
    project_path, _ = _project_file(tmp_path)
    builder = ExportPlanBuilder(
        media_probe=_probe,
        ffmpeg_resolver=lambda: "",
        ffprobe_resolver=lambda: "",
        free_space_provider=lambda _path: 10 * 1024**3,
    )

    result = builder.build(_request(project_path, tmp_path / "Exports"))

    assert not result.ok
    assert {error.code for error in result.errors} == {
        "FFMPEG_UNAVAILABLE",
        "FFPROBE_UNAVAILABLE",
    }


def test_builder_rejects_output_path_that_is_not_a_directory(tmp_path: Path) -> None:
    project_path, _ = _project_file(tmp_path)
    output_path = tmp_path / "not-a-directory"
    output_path.write_text("occupied", encoding="utf-8")

    result = _builder().build(_request(project_path, output_path))

    assert not result.ok
    assert {error.code for error in result.errors} == {
        "OUTPUT_DIRECTORY_UNWRITABLE"
    }


def test_existing_target_requires_safe_suffix_or_explicit_overwrite(tmp_path: Path) -> None:
    project_path, _ = _project_file(tmp_path)
    output_dir = tmp_path / "Exports"
    output_dir.mkdir()
    target = output_dir / "output.mp4"
    target.write_bytes(b"existing")
    request = replace(
        _request(project_path, output_dir),
        filename="output.mp4",
        accept_safe_suffix=False,
    )

    blocked = _builder().build(request)

    assert not blocked.ok
    assert blocked.errors[0].code == "OUTPUT_CONFLICT"
    assert blocked.suggested_filename == "output (1).mp4"

    safe = _builder().build(replace(request, accept_safe_suffix=True))
    assert safe.ok
    assert safe.plan is not None
    assert safe.plan.output.filename == "output (1).mp4"

    overwrite = _builder().build(
        replace(request, overwrite_mode=OverwriteMode.REPLACE)
    )
    assert overwrite.ok
    assert overwrite.plan is not None
    assert overwrite.plan.output.target_fingerprint is not None
    assert overwrite.plan.output.target_fingerprint.size_bytes == len(b"existing")


def test_reserved_queue_targets_are_included_in_safe_suffix_selection(
    tmp_path: Path,
) -> None:
    project_path, _ = _project_file(tmp_path)
    output_dir = tmp_path / "Exports"
    output_dir.mkdir()
    request = replace(
        _request(project_path, output_dir),
        filename="output.mp4",
        reserved_target_paths=(
            str(output_dir / "output.mp4"),
            str(output_dir / "output (1).mp4"),
        ),
    )

    result = _builder().build(request)

    assert result.ok
    assert result.plan is not None
    assert result.plan.output.filename == "output (2).mp4"


def test_explicit_overwrite_rejects_missing_target(tmp_path: Path) -> None:
    project_path, _ = _project_file(tmp_path)
    request = replace(
        _request(project_path, tmp_path / "Exports"),
        overwrite_mode=OverwriteMode.REPLACE,
    )

    result = _builder().build(request)

    assert not result.ok
    assert {error.code for error in result.errors} == {
        "OVERWRITE_TARGET_MISSING"
    }


@pytest.mark.parametrize(
    ("free_bytes", "expected_code"),
    [
        (50 * 1024**3, None),
        (500 * 1024**2, "DISK_SPACE_WARNING"),
        (100 * 1024**2, "DISK_SPACE_CRITICAL"),
    ],
)
def test_disk_space_is_warning_only(
    tmp_path: Path,
    free_bytes: int,
    expected_code: str | None,
) -> None:
    project_path, _ = _project_file(tmp_path)
    builder = ExportPlanBuilder(
        media_probe=_probe,
        ffmpeg_resolver=lambda: __file__,
        ffprobe_resolver=lambda: __file__,
        free_space_provider=lambda _path: free_bytes,
        clock=lambda: "2026-07-29T12:00:00+00:00",
        id_factory=lambda: "plan-1",
        size_estimator=lambda _duration, _width, _height, _fps: 400 * 1024**2,
    )

    result = builder.build(_request(project_path, tmp_path / "Exports"))

    assert result.ok
    codes = {warning.code for warning in result.warnings}
    if expected_code is None:
        assert not codes
    else:
        assert expected_code in codes


def test_invalid_custom_canvas_is_reported_as_preflight_error(tmp_path: Path) -> None:
    project_path, _ = _project_file(tmp_path)
    request = replace(_request(project_path, tmp_path / "Exports"), width=1919)

    result = _builder().build(request)

    assert not result.ok
    assert result.errors[0].code == "OUTPUT_INVALID"


def test_builder_reports_unsaved_and_corrupt_project(tmp_path: Path) -> None:
    missing_project = tmp_path / "missing.qrproj"
    request = replace(
        _request(missing_project, tmp_path / "Exports"),
        project_saved=False,
    )

    result = _builder().build(request)

    assert not result.ok
    assert {issue.code for issue in result.errors} == {
        "PROJECT_NOT_SAVED",
        "PROJECT_MISSING",
    }


def test_builder_rejects_corrupt_timeline_payload(tmp_path: Path) -> None:
    project = ProjectFile(
        project_id="corrupt-timeline",
        name="损坏时间线",
        description="",
        created_at="2026-07-29T10:00:00+00:00",
        updated_at="2026-07-29T10:00:00+00:00",
        extensions={"quickrec.timeline": "not-an-object"},
    )
    project_path = tmp_path / "corrupt.qrproj"
    assert save_project(project_path, project).ok

    result = _builder().build(_request(project_path, tmp_path / "Exports"))

    assert not result.ok
    assert result.errors[0].code.startswith("TIMELINE_")


def test_builder_rejects_directory_as_explicit_overwrite_target(
    tmp_path: Path,
) -> None:
    project_path, _ = _project_file(tmp_path)
    output_dir = tmp_path / "Exports"
    target = output_dir / "output.mp4"
    target.mkdir(parents=True)

    result = _builder().build(
        replace(
            _request(project_path, output_dir),
            filename=target.name,
            overwrite_mode=OverwriteMode.REPLACE,
        )
    )

    assert not result.ok
    assert result.errors[0].code == "OUTPUT_TARGET_INVALID"


def test_builder_rejects_timeline_material_reference_missing_from_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_path, _ = _project_file(tmp_path)
    loaded = load_project(project_path)
    assert loaded.project is not None
    timeline_result = load_project_timeline(loaded.project)
    assert timeline_result.ok
    payload = json.loads(project_path.read_text(encoding="utf-8"))
    payload["materials"] = []
    project_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        plan_builder_module,
        "load_project_timeline",
        lambda _project: timeline_result,
    )

    result = _builder().build(_request(project_path, tmp_path / "Exports"))

    assert not result.ok
    assert result.errors[0].code == "MATERIAL_REFERENCE_MISSING"


def test_builder_resolves_relative_material_path(tmp_path: Path) -> None:
    project_path, media = _project_file(tmp_path, media_name="relative.mp4")
    payload = json.loads(project_path.read_text(encoding="utf-8"))
    payload["materials"][0]["last_known_path"] = media.name
    project_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    result = _builder().build(_request(project_path, tmp_path / "Exports"))

    assert result.ok
    assert result.plan is not None
    assert result.plan.materials[0].path == str(media.resolve())


@pytest.mark.parametrize("error_type", [OSError, ValueError, RuntimeError])
def test_builder_maps_probe_exception_to_unreadable_material(
    tmp_path: Path,
    error_type: type[Exception],
) -> None:
    project_path, _ = _project_file(tmp_path)

    def failing_probe(_path: Path) -> ExportMaterialProbe:
        raise error_type("controlled")

    builder = ExportPlanBuilder(
        media_probe=failing_probe,
        ffmpeg_resolver=lambda: __file__,
        ffprobe_resolver=lambda: __file__,
        free_space_provider=lambda _path: 10 * 1024**3,
    )

    result = builder.build(_request(project_path, tmp_path / "Exports"))

    assert not result.ok
    assert result.errors[0].code == "MATERIAL_UNREADABLE"
    assert result.errors[0].context["error_type"] == error_type.__name__


def test_builder_rejects_failed_or_invalid_probe_result(tmp_path: Path) -> None:
    project_path, _ = _project_file(tmp_path)
    failed = replace(_probe(tmp_path), ok=False, error="decode failed")
    invalid = replace(_probe(tmp_path), duration_us=0)

    for probe in (failed, invalid):
        builder = ExportPlanBuilder(
            media_probe=lambda _path, value=probe: value,
            ffmpeg_resolver=lambda: __file__,
            ffprobe_resolver=lambda: __file__,
            free_space_provider=lambda _path: 10 * 1024**3,
        )
        result = builder.build(_request(project_path, tmp_path / "Exports"))
        assert not result.ok
        assert result.errors[0].code == "MATERIAL_UNREADABLE"


def test_builder_reports_estimate_shortfall_above_absolute_disk_floor(
    tmp_path: Path,
) -> None:
    project_path, _ = _project_file(tmp_path)
    builder = ExportPlanBuilder(
        media_probe=_probe,
        ffmpeg_resolver=lambda: __file__,
        ffprobe_resolver=lambda: __file__,
        free_space_provider=lambda _path: 300 * 1024**2,
        size_estimator=lambda *_args: 400 * 1024**2,
    )

    result = builder.build(_request(project_path, tmp_path / "Exports"))

    assert result.ok
    assert result.warnings[0].code == "DISK_SPACE_CRITICAL"


def test_default_probe_reports_missing_ffprobe() -> None:
    builder = ExportPlanBuilder(ffprobe_resolver=lambda: "")

    result = builder._probe_material(Path("missing.mp4"))

    assert not result.ok
    assert result.error == "ffprobe executable not found"


def test_probe_export_material_parses_video_audio_and_fallback_duration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 640,
                "height": 360,
                "avg_frame_rate": "30000/1001",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
            },
        ],
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": "2.5",
        },
    }
    monkeypatch.setattr(
        plan_builder_module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["ffprobe"],
            0,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )

    result = plan_builder_module.probe_export_material(
        tmp_path / "中文 空格.mp4",
        "ffprobe",
    )

    assert result.ok
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"
    assert result.audio_duration_us == 2_500_000
    assert result.fps == pytest.approx(29.97002997)


@pytest.mark.parametrize(
    ("completed", "expected_error"),
    [
        (
            subprocess.CompletedProcess(
                ["ffprobe"],
                1,
                stdout="",
                stderr="bad media",
            ),
            "ffprobe returned nonzero",
        ),
        (
            subprocess.CompletedProcess(
                ["ffprobe"],
                0,
                stdout="{invalid",
                stderr="",
            ),
            "invalid ffprobe output",
        ),
        (
            subprocess.CompletedProcess(
                ["ffprobe"],
                0,
                stdout=json.dumps({"streams": [], "format": {}}),
                stderr="",
            ),
            "invalid ffprobe output",
        ),
    ],
)
def test_probe_export_material_maps_tool_and_payload_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    completed: subprocess.CompletedProcess[str],
    expected_error: str,
) -> None:
    monkeypatch.setattr(
        plan_builder_module.subprocess,
        "run",
        lambda *_args, **_kwargs: completed,
    )

    result = plan_builder_module.probe_export_material(
        tmp_path / "sample.mp4",
        "ffprobe",
    )

    assert not result.ok
    assert expected_error in result.error


def test_probe_export_material_maps_launch_and_timeout_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for failure in (
        OSError("launch failed"),
        subprocess.TimeoutExpired(["ffprobe"], 30),
    ):
        def raise_failure(*_args, current=failure, **_kwargs):
            raise current

        monkeypatch.setattr(
            plan_builder_module.subprocess,
            "run",
            raise_failure,
        )
        result = plan_builder_module.probe_export_material(
            tmp_path / "sample.mp4",
            "ffprobe",
        )
        assert not result.ok


def test_plan_builder_filename_suffix_and_numeric_helpers(tmp_path: Path) -> None:
    assert (
        plan_builder_module._sanitize_filename(
            "CON",
            "CON",
            "2026-07-29T12:34:56",
        )
        == "QuickRec_Export_20260729123456.mp4"
    )
    assert (
        plan_builder_module._sanitize_filename(
            "",
            "CON",
            "2026-07-29T12:34:56",
        )
        == "CON_20260729123456.mp4"
    )
    assert (
        plan_builder_module._sanitize_filename(
            "custom.name",
            "ignored",
            "invalid",
        )
        == "custom.name.mp4"
    )
    (tmp_path / "output (1).mp4").write_bytes(b"occupied")
    assert (
        plan_builder_module._safe_suffix(tmp_path, "output.mp4")
        == "output (2).mp4"
    )
    assert plan_builder_module._stream_text(None, "codec_name") is None
    assert plan_builder_module._stream_text({}, "codec_name") is None
    assert plan_builder_module._stream_int(None, "width") is None
    assert plan_builder_module._stream_int({}, "width") is None
    assert plan_builder_module._frame_rate(None) is None
    assert plan_builder_module._frame_rate({}) is None
    assert plan_builder_module._frame_rate({"r_frame_rate": "30/0"}) is None
    assert plan_builder_module._frame_rate({"r_frame_rate": "60"}) == 60.0
    assert plan_builder_module._seconds_to_us("1.25") == 1_250_000
    assert plan_builder_module._estimate_output_size(0, 1920, 1080, 60) == 1
