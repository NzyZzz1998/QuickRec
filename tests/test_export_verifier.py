from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from exporting.models import (
    ExportClip,
    ExportFailureKind,
    ExportMaterialProbe,
    ExportMaterialSnapshot,
    ExportOutputSpec,
    ExportPlan,
    ExportProjectSnapshot,
    ExportTimelineSnapshot,
    ExportTrack,
    RenderPolicy,
)
from exporting.verifier import ExportVerifier


def _plan(tmp_path: Path, *, with_audio: bool = True) -> ExportPlan:
    media = tmp_path / "中文 素材.mp4"
    media.write_bytes(b"controlled-source")
    stat = media.stat()
    material = ExportMaterialSnapshot(
        material_id="material-1",
        path=str(media),
        normalized_path=str(media).casefold(),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        container="mov,mp4,m4a,3gp,3g2,mj2",
        video_codec="h264",
        width=1920,
        height=1080,
        fps=60.0,
        duration_us=2_000_000,
        audio_codec="aac" if with_audio else None,
        audio_sample_rate=48_000 if with_audio else None,
        audio_channels=2 if with_audio else None,
        audio_duration_us=2_000_000 if with_audio else None,
    )
    tracks = [ExportTrack("video-1", "video", 0)]
    clips = [
        ExportClip(
            "video-clip",
            "material-1",
            "video-1",
            None,
            0,
            2_000_000,
            0,
            2_000_000,
        )
    ]
    if with_audio:
        tracks.append(ExportTrack("audio-1", "audio", 0))
        clips.append(
            ExportClip(
                "audio-clip",
                "material-1",
                "audio-1",
                None,
                0,
                2_000_000,
                0,
                2_000_000,
            )
        )
    return ExportPlan.create(
        plan_id="plan-verify",
        created_at="2026-07-29T12:00:00+00:00",
        project=ExportProjectSnapshot(
            "project-1",
            "验证项目",
            str(tmp_path / "project.qrproj"),
            1,
            2,
        ),
        timeline=ExportTimelineSnapshot(
            "timeline-1",
            2_000_000,
            tuple(tracks),
            tuple(clips),
        ),
        materials=(material,),
        render_policy=RenderPolicy(),
        output=ExportOutputSpec(
            1920,
            1080,
            60,
            str(tmp_path / "output"),
            "result.mp4",
        ),
    )


def _payload(*, with_audio: bool = True) -> dict[str, Any]:
    streams: list[dict[str, Any]] = [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "pix_fmt": "yuv420p",
            "width": 1920,
            "height": 1080,
            "avg_frame_rate": "60/1",
            "duration": "2.000000",
        }
    ]
    if with_audio:
        streams.append(
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
                "duration": "2.000000",
            }
        )
    return {
        "streams": streams,
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": "2.000000",
        },
    }


class StubRunner:
    def __init__(
        self,
        payload: dict[str, Any] | str,
        *,
        returncode: int = 0,
        stderr: str = "",
        timeout: bool = False,
    ) -> None:
        self.payload = payload
        self.returncode = returncode
        self.stderr = stderr
        self.timeout = timeout
        self.arguments: list[str] = []

    def __call__(self, arguments: list[str], **_kwargs: object):
        self.arguments = list(arguments)
        if self.timeout:
            raise subprocess.TimeoutExpired(arguments, 60)
        stdout = (
            self.payload
            if isinstance(self.payload, str)
            else json.dumps(self.payload)
        )
        return subprocess.CompletedProcess(
            arguments,
            self.returncode,
            stdout=stdout,
            stderr=self.stderr,
        )


def _probe_from_plan(plan: ExportPlan) -> ExportMaterialProbe:
    material = plan.materials[0]
    return ExportMaterialProbe(
        container=material.container,
        video_codec=material.video_codec,
        width=material.width,
        height=material.height,
        fps=material.fps,
        duration_us=material.duration_us,
        audio_codec=material.audio_codec,
        audio_sample_rate=material.audio_sample_rate,
        audio_channels=material.audio_channels,
        audio_duration_us=material.audio_duration_us,
    )


@pytest.mark.parametrize("with_audio", [False, True])
def test_verifier_accepts_exact_output_contract(
    tmp_path: Path,
    with_audio: bool,
) -> None:
    plan = _plan(tmp_path, with_audio=with_audio)
    output = tmp_path / "result.mp4"
    output.write_bytes(b"valid-output")
    runner = StubRunner(_payload(with_audio=with_audio))
    verifier = ExportVerifier(
        ffprobe_resolver=lambda: "ffprobe.exe",
        runner=runner,
    )

    result = verifier.verify_output(plan, output)

    assert result.ok
    assert result.failure_kind is None
    assert result.summary is not None
    assert result.summary.width == 1920
    assert result.summary.height == 1080
    assert result.summary.fps == 60.0
    assert result.summary.has_audio is with_audio
    assert runner.arguments[-1] == str(output)
    assert runner.arguments.count(str(output)) == 1


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (("format", "format_name", "matroska"), "container"),
        (("video", "codec_name", "hevc"), "video codec"),
        (("video", "pix_fmt", "yuv444p"), "pixel format"),
        (("video", "width", 1280), "canvas"),
        (("video", "avg_frame_rate", "30/1"), "fps"),
        (("format", "duration", "2.200000"), "duration"),
        (("audio", "codec_name", "mp3"), "audio codec"),
        (("audio", "sample_rate", "44100"), "sample rate"),
        (("audio", "channels", 1), "channels"),
    ],
)
def test_verifier_rejects_output_contract_mismatch(
    tmp_path: Path,
    mutation: tuple[str, str, object],
    expected_error: str,
) -> None:
    plan = _plan(tmp_path)
    output = tmp_path / "result.mp4"
    output.write_bytes(b"invalid-output")
    payload = copy.deepcopy(_payload())
    section, key, value = mutation
    if section == "format":
        payload["format"][key] = value
    else:
        stream = next(
            item
            for item in payload["streams"]
            if item["codec_type"] == section
        )
        stream[key] = value
    verifier = ExportVerifier(
        ffprobe_resolver=lambda: "ffprobe.exe",
        runner=StubRunner(payload),
    )

    result = verifier.verify_output(plan, output)

    assert not result.ok
    assert result.failure_kind == ExportFailureKind.VERIFICATION_FAILED
    assert expected_error in result.message.casefold()


def test_verifier_rejects_audio_for_silent_plan(tmp_path: Path) -> None:
    plan = _plan(tmp_path, with_audio=False)
    output = tmp_path / "result.mp4"
    output.write_bytes(b"unexpected-audio")
    verifier = ExportVerifier(
        ffprobe_resolver=lambda: "ffprobe.exe",
        runner=StubRunner(_payload(with_audio=True)),
    )

    result = verifier.verify_output(plan, output)

    assert not result.ok
    assert "unexpected audio" in result.message.casefold()


@pytest.mark.parametrize(
    ("runner", "kind"),
    [
        (
            StubRunner({}, returncode=1, stderr="decode failed"),
            ExportFailureKind.TOOL_FAILED,
        ),
        (
            StubRunner({}, timeout=True),
            ExportFailureKind.TOOL_TIMEOUT,
        ),
        (
            StubRunner("{broken-json"),
            ExportFailureKind.VERIFICATION_FAILED,
        ),
    ],
)
def test_verifier_reports_ffprobe_failures(
    tmp_path: Path,
    runner: StubRunner,
    kind: ExportFailureKind,
) -> None:
    plan = _plan(tmp_path)
    output = tmp_path / "result.mp4"
    output.write_bytes(b"output")

    result = ExportVerifier(
        ffprobe_resolver=lambda: "ffprobe.exe",
        runner=runner,
    ).verify_output(plan, output)

    assert not result.ok
    assert result.failure_kind == kind


def test_material_fingerprint_check_detects_file_and_probe_changes(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    probe = _probe_from_plan(plan)
    verifier = ExportVerifier(
        ffprobe_resolver=lambda: "ffprobe.exe",
        media_probe=lambda _path, _ffprobe: probe,
    )

    assert verifier.verify_materials(plan).ok

    Path(plan.materials[0].path).write_bytes(b"changed")
    changed_file = verifier.verify_materials(plan)
    assert not changed_file.ok
    assert changed_file.failure_kind == ExportFailureKind.MATERIAL_CHANGED

    original = plan.materials[0]
    Path(original.path).write_bytes(b"controlled-source")
    stat = Path(original.path).stat()
    restored = ExportMaterialSnapshot(
        material_id=original.material_id,
        path=original.path,
        normalized_path=original.normalized_path,
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        container=original.container,
        video_codec=original.video_codec,
        width=original.width,
        height=original.height,
        fps=original.fps,
        duration_us=original.duration_us,
        audio_codec=original.audio_codec,
        audio_sample_rate=original.audio_sample_rate,
        audio_channels=original.audio_channels,
        audio_duration_us=original.audio_duration_us,
    )
    refreshed_plan = ExportPlan.create(
        plan_id=plan.plan_id,
        created_at=plan.created_at,
        project=plan.project,
        timeline=plan.timeline,
        materials=(restored,),
        render_policy=plan.render_policy,
        output=plan.output,
    )
    mismatched_probe = ExportMaterialProbe(
        **{
            **_probe_from_plan(refreshed_plan).__dict__,
            "fps": 30.0,
        }
    )
    probe_changed = ExportVerifier(
        ffprobe_resolver=lambda: "ffprobe.exe",
        media_probe=lambda _path, _ffprobe: mismatched_probe,
    ).verify_materials(refreshed_plan)

    assert not probe_changed.ok
    assert probe_changed.failure_kind == ExportFailureKind.MATERIAL_CHANGED
