from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli.commands import (
    CliCommandContext,
    run_doctor,
    run_editing_smoke,
    run_probe,
    run_project_validate,
    run_record,
    run_timeline_validate,
)
from cli.contracts import CliExitCode, CliFailure
from cli.isolation import CliIsolation
from utils.project_store import ProjectFile, ProjectMaterialRef, save_project
from utils.timeline_model import create_empty_timeline, with_project_timeline


def _project(path: Path, *, with_timeline: bool = True) -> Path:
    project = ProjectFile(
        project_id="project-cli",
        name="CLI 验证项目",
        description="",
        created_at="2026-07-29T00:00:00+08:00",
        updated_at="2026-07-29T00:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=str(path.parent / "素材 1.mp4"),
                file_name="素材 1.mp4",
                added_at="2026-07-29T00:00:00+08:00",
                metadata_snapshot={
                    "duration_sec": 3.0,
                    "width": 1280,
                    "height": 720,
                    "fps": 30.0,
                    "has_audio": True,
                },
            )
        ],
    )
    if with_timeline:
        project = with_project_timeline(
            project,
            create_empty_timeline(project.project_id),
        )
    written = save_project(path, project)
    assert written.ok
    return path


def test_doctor_reports_dependencies_without_importing_gui(tmp_path: Path) -> None:
    context = CliCommandContext(timeout=30.0)

    outcome = run_doctor(context)

    assert outcome.result["python"]["compatible"] is True
    assert outcome.result["ffmpeg"]["available"] is True
    assert outcome.result["ffprobe"]["available"] is True
    assert outcome.result["gui_initialized"] is False


def test_project_validate_is_read_only(tmp_path: Path) -> None:
    project_path = _project(tmp_path / "项目 空格" / "project.qrproj")
    before = project_path.read_bytes()

    outcome = run_project_validate(
        CliCommandContext(timeout=30.0),
        project_path,
    )

    assert outcome.result["status"] == "available"
    assert outcome.result["project_id"] == "project-cli"
    assert outcome.result["material_count"] == 1
    assert project_path.read_bytes() == before


def test_project_validate_classifies_corrupt_project(tmp_path: Path) -> None:
    project_path = tmp_path / "broken.qrproj"
    project_path.write_text("{", encoding="utf-8")

    with pytest.raises(CliFailure) as raised:
        run_project_validate(CliCommandContext(timeout=30.0), project_path)

    assert raised.value.exit_code == CliExitCode.VALIDATION_FAILED
    assert raised.value.category == "invalid_project"
    assert raised.value.context["status"] == "corrupt"


def test_timeline_validate_reports_schema_and_counts(tmp_path: Path) -> None:
    project_path = _project(tmp_path / "project.qrproj")

    outcome = run_timeline_validate(
        CliCommandContext(timeout=30.0),
        project_path,
    )

    assert outcome.result["status"] == "ready"
    assert outcome.result["timeline_schema"] == 2
    assert outcome.result["track_count"] == 2
    assert outcome.result["clip_count"] == 0
    assert outcome.result["read_only"] is False


def test_probe_reports_media_metadata_hash_and_no_absolute_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video = tmp_path / "中文 空格.mp4"
    video.write_bytes(b"controlled-media")

    class Metadata:
        ok = True
        duration_sec = 2.0
        width = 640
        height = 360
        fps = 30.0
        error = ""

    monkeypatch.setattr("cli.commands.probe_media", lambda *_args, **_kwargs: Metadata())

    outcome = run_probe(CliCommandContext(timeout=30.0), video)

    serialized = json.dumps(outcome.result, ensure_ascii=False)
    assert outcome.result["file_name"] == "中文 空格.mp4"
    assert outcome.result["size_bytes"] == len(b"controlled-media")
    assert len(outcome.result["sha256"]) == 64
    assert str(tmp_path) not in serialized


def test_probe_rejects_unparseable_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video = tmp_path / "broken.mp4"
    video.write_bytes(b"broken")

    class Metadata:
        ok = False
        duration_sec = None
        width = None
        height = None
        fps = None
        error = "invalid media"

    monkeypatch.setattr("cli.commands.probe_media", lambda *_args, **_kwargs: Metadata())

    with pytest.raises(CliFailure) as raised:
        run_probe(CliCommandContext(timeout=30.0), video)

    assert raised.value.exit_code == CliExitCode.VALIDATION_FAILED
    assert raised.value.category == "invalid_media"


def test_record_uses_isolated_config_and_reports_probe_and_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolation = CliIsolation.prepare(
        tmp_path / "workspace",
        tmp_path / "evidence",
    )
    created: list[object] = []

    class Preflight:
        requested_source = "microphone"
        final_source = "microphone"
        degraded = False
        reason = ""
        system_available = False
        microphone_available = True

    class Recorder:
        def __init__(self, config, on_saved):
            self.config = config
            self.on_saved = on_saved
            self.cancelled = False
            created.append(self)

        def start_fullscreen(self):
            return True

        def get_audio_preflight(self):
            return Preflight()

        def stop(self, cancel=False):
            self.cancelled = cancel
            if not cancel:
                output = Path(self.config.get("save_path")) / "recorded.mp4"
                output.write_bytes(b"recorded-media")
                self.on_saved(str(output))
            return ""

        def wait_until_idle(self, timeout=60.0):
            return True

        def get_last_recording_metadata(self):
            return {
                "duration_sec": 0.01,
                "width": 1920,
                "height": 1080,
                "fps": 60.0,
                "mode": "fullscreen",
                "audio_source": "microphone",
            }

        def get_diagnostic_context(self):
            return {"recorder": {"last_failure_reason": ""}}

    class Metadata:
        ok = True
        duration_sec = 0.01
        width = 1920
        height = 1080
        fps = 60.0
        error = ""

    monkeypatch.setattr("cli.commands.probe_media", lambda *_args, **_kwargs: Metadata())
    context = CliCommandContext(
        timeout=5.0,
        recorder_factory=lambda config, on_saved: Recorder(config, on_saved),
    )

    outcome = run_record(
        context,
        isolation,
        mode="fullscreen",
        duration=0.01,
        fps=60,
        audio="mic",
    )

    recorder = created[0]
    assert recorder.config.get("save_path") == str(isolation.output_dir)
    assert recorder.config.get("audio_source") == "microphone"
    assert recorder.config.get("fps") == 60
    assert outcome.result["actual_audio"] == "microphone"
    assert outcome.result["fps"] == 60.0
    assert len(outcome.result["sha256"]) == 64
    assert outcome.result["output"] == "output/recorded.mp4"
    assert outcome.evidence == ["record.json"]
    assert (isolation.evidence_dir / "record.json").is_file()


def test_record_rejects_audio_degradation_instead_of_claiming_success(
    tmp_path: Path,
) -> None:
    isolation = CliIsolation.prepare(
        tmp_path / "workspace",
        tmp_path / "evidence",
    )

    class Preflight:
        requested_source = "system"
        final_source = "none"
        degraded = True
        reason = "loopback unavailable"
        system_available = False
        microphone_available = False

    class Recorder:
        def __init__(self, _config, _on_saved):
            self.cancelled = False

        def start_fullscreen(self):
            return True

        def get_audio_preflight(self):
            return Preflight()

        def stop(self, cancel=False):
            self.cancelled = cancel
            return ""

        def wait_until_idle(self, timeout=60.0):
            return True

    recorder = Recorder(None, None)
    context = CliCommandContext(
        timeout=5.0,
        recorder_factory=lambda _config, _on_saved: recorder,
    )

    with pytest.raises(CliFailure) as raised:
        run_record(
            context,
            isolation,
            mode="fullscreen",
            duration=0.01,
            fps=30,
            audio="system",
        )

    assert raised.value.exit_code == CliExitCode.VALIDATION_FAILED
    assert raised.value.category == "audio_unavailable"
    assert recorder.cancelled is True


def test_record_timeout_cancels_recorder_and_cleans_up(tmp_path: Path) -> None:
    isolation = CliIsolation.prepare(
        tmp_path / "workspace",
        tmp_path / "evidence",
    )

    class Preflight:
        requested_source = "none"
        final_source = "none"
        degraded = False
        reason = ""

    class Recorder:
        def __init__(self):
            self.cancelled = False

        def start_fullscreen(self):
            return True

        def get_audio_preflight(self):
            return Preflight()

        def stop(self, cancel=False):
            self.cancelled = self.cancelled or cancel
            return ""

        def wait_until_idle(self, timeout=60.0):
            return True

    recorder = Recorder()
    context = CliCommandContext(
        timeout=0.01,
        recorder_factory=lambda _config, _on_saved: recorder,
    )

    with pytest.raises(CliFailure) as raised:
        run_record(
            context,
            isolation,
            mode="fullscreen",
            duration=1.0,
            fps=30,
            audio="none",
        )

    assert raised.value.exit_code == CliExitCode.TIMEOUT
    assert raised.value.category == "recording_timeout"
    assert recorder.cancelled is True


def test_record_120_uses_existing_capability_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolation = CliIsolation.prepare(
        tmp_path / "workspace",
        tmp_path / "evidence",
    )
    inspected: list[bool] = []

    class Display:
        monitor_count = 1
        refresh_hz = 120

    class Readiness:
        ready = True

    class Inspection:
        display = Display()
        readiness = Readiness()

    class CapabilityRuntime:
        def inspect(self):
            inspected.append(True)
            return Inspection()

    class Preflight:
        requested_source = "none"
        final_source = "none"
        degraded = False
        reason = ""

    class Recorder:
        def __init__(self, config, on_saved):
            self.config = config
            self.on_saved = on_saved

        def start_fullscreen(self):
            return True

        def get_audio_preflight(self):
            return Preflight()

        def stop(self, cancel=False):
            if not cancel:
                output = Path(self.config.get("save_path")) / "120.mp4"
                output.write_bytes(b"120-media")
                self.on_saved(str(output))
            return ""

        def wait_until_idle(self, timeout=60.0):
            return True

        def get_last_recording_metadata(self):
            return {
                "duration_sec": 0.01,
                "width": 1920,
                "height": 1080,
                "fps": 120.0,
                "mode": "fullscreen",
                "audio_source": "none",
            }

    class Metadata:
        ok = True
        duration_sec = 0.01
        width = 1920
        height = 1080
        fps = 120.0
        error = ""

    monkeypatch.setattr("cli.commands.probe_media", lambda *_args, **_kwargs: Metadata())
    context = CliCommandContext(
        timeout=5.0,
        recorder_factory=lambda config, on_saved: Recorder(config, on_saved),
        capability_runtime_factory=lambda _isolation: CapabilityRuntime(),
    )

    outcome = run_record(
        context,
        isolation,
        mode="fullscreen",
        duration=0.01,
        fps=120,
        audio="none",
    )

    assert inspected == [True]
    assert outcome.result["requested_fps"] == 120


def test_editing_smoke_copies_input_and_exercises_v2_edit_boundaries(
    tmp_path: Path,
) -> None:
    source = _project(
        tmp_path / "input" / "project.qrproj",
        with_timeline=False,
    )
    before = source.read_bytes()
    isolation = CliIsolation.prepare(
        tmp_path / "workspace",
        tmp_path / "evidence",
    )

    outcome = run_editing_smoke(
        CliCommandContext(timeout=30.0),
        isolation,
        project_path=source,
    )

    assert source.read_bytes() == before
    assert outcome.result["input_unchanged"] is True
    assert outcome.result["timeline_schema"] == 2
    assert outcome.result["trim_valid"] is True
    assert outcome.result["split_valid"] is True
    assert outcome.result["playback_plan_valid"] is True
    assert outcome.result["reload_valid"] is True
    assert outcome.evidence == ["editing-smoke.json", "editing-smoke-project.qrproj"]
    assert (isolation.evidence_dir / "editing-smoke.json").is_file()
    assert (isolation.evidence_dir / "editing-smoke-project.qrproj").is_file()
