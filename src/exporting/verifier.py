"""FFprobe 输出合同与源素材指纹复核。"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from exporting.models import (
    ExportFailureKind,
    ExportMaterialProbe,
    ExportMaterialSnapshot,
    ExportPlan,
)
from exporting.plan_builder import probe_export_material
from utils.media_metadata import resolve_ffprobe_path
from utils.recording_library_store import normalize_windows_path

Runner = Callable[..., subprocess.CompletedProcess[str]]
MediaProbe = Callable[[Path, str], ExportMaterialProbe]


@dataclass(frozen=True)
class OutputVerificationSummary:
    container: str
    video_codec: str
    pixel_format: str
    width: int
    height: int
    fps: float
    duration_us: int
    has_audio: bool
    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    audio_channels: int | None = None


@dataclass(frozen=True)
class ExportVerificationResult:
    ok: bool
    failure_kind: ExportFailureKind | None = None
    message: str = ""
    summary: OutputVerificationSummary | None = None
    material_id: str | None = None


class ExportVerifier:
    def __init__(
        self,
        *,
        ffprobe_resolver: Callable[[], str] = resolve_ffprobe_path,
        runner: Runner = subprocess.run,
        media_probe: MediaProbe = probe_export_material,
        timeout_seconds: float = 60,
    ) -> None:
        self._ffprobe_resolver = ffprobe_resolver
        self._runner = runner
        self._media_probe = media_probe
        self._timeout_seconds = timeout_seconds

    def verify_materials(self, plan: ExportPlan) -> ExportVerificationResult:
        executable = self._ffprobe_resolver()
        if not executable:
            return _failed(
                ExportFailureKind.TOOL_MISSING,
                "FFprobe executable is missing",
            )
        for expected in plan.materials:
            path = Path(expected.path)
            try:
                if not path.is_file():
                    return _failed(
                        ExportFailureKind.MATERIAL_CHANGED,
                        "material file is missing",
                        material_id=expected.material_id,
                    )
                stat = path.stat()
            except OSError as exc:
                return _failed(
                    ExportFailureKind.MATERIAL_CHANGED,
                    f"material stat failed: {type(exc).__name__}",
                    material_id=expected.material_id,
                )
            if (
                stat.st_size != expected.size_bytes
                or stat.st_mtime_ns != expected.mtime_ns
            ):
                return _failed(
                    ExportFailureKind.MATERIAL_CHANGED,
                    "material file identity changed",
                    material_id=expected.material_id,
                )
            probe = self._media_probe(path, executable)
            if not probe.ok:
                return _failed(
                    ExportFailureKind.MATERIAL_CHANGED,
                    "material media probe changed or failed",
                    material_id=expected.material_id,
                )
            current = ExportMaterialSnapshot(
                material_id=expected.material_id,
                path=str(path),
                normalized_path=normalize_windows_path(path),
                size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                container=probe.container,
                video_codec=probe.video_codec,
                width=probe.width,
                height=probe.height,
                fps=probe.fps,
                duration_us=probe.duration_us,
                audio_codec=probe.audio_codec,
                audio_sample_rate=probe.audio_sample_rate,
                audio_channels=probe.audio_channels,
                audio_duration_us=probe.audio_duration_us,
            )
            if current.fingerprint != expected.fingerprint:
                return _failed(
                    ExportFailureKind.MATERIAL_CHANGED,
                    "material media fingerprint changed",
                    material_id=expected.material_id,
                )
        return ExportVerificationResult(True)

    def verify_output(
        self,
        plan: ExportPlan,
        output_path: Path,
    ) -> ExportVerificationResult:
        try:
            if not output_path.is_file() or output_path.stat().st_size <= 0:
                return _failed(
                    ExportFailureKind.VERIFICATION_FAILED,
                    "output file is missing or empty",
                )
        except OSError as exc:
            return _failed(
                ExportFailureKind.VERIFICATION_FAILED,
                f"output file stat failed: {type(exc).__name__}",
            )
        executable = self._ffprobe_resolver()
        if not executable:
            return _failed(
                ExportFailureKind.TOOL_MISSING,
                "FFprobe executable is missing",
            )
        arguments = [
            executable,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(output_path),
        ]
        try:
            completed = self._runner(
                arguments,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=self._timeout_seconds,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            return _failed(
                ExportFailureKind.TOOL_TIMEOUT,
                "FFprobe verification timed out",
            )
        except OSError as exc:
            return _failed(
                ExportFailureKind.TOOL_START_FAILED,
                f"FFprobe start failed: {type(exc).__name__}",
            )
        if completed.returncode != 0:
            return _failed(
                ExportFailureKind.TOOL_FAILED,
                "FFprobe returned nonzero",
            )
        try:
            payload = json.loads(completed.stdout)
            summary = _parse_output_summary(payload, plan)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return _failed(
                ExportFailureKind.VERIFICATION_FAILED,
                str(exc),
            )
        return ExportVerificationResult(True, summary=summary)


def _parse_output_summary(
    payload: dict[str, Any],
    plan: ExportPlan,
) -> OutputVerificationSummary:
    format_data = payload.get("format")
    streams = payload.get("streams")
    if not isinstance(format_data, dict) or not isinstance(streams, list):
        raise ValueError("invalid FFprobe response")
    typed_streams = [item for item in streams if isinstance(item, dict)]
    video_streams = [
        item for item in typed_streams if item.get("codec_type") == "video"
    ]
    audio_streams = [
        item for item in typed_streams if item.get("codec_type") == "audio"
    ]
    if "mp4" not in str(format_data.get("format_name") or "").casefold():
        raise ValueError("container mismatch")
    if len(video_streams) != 1:
        raise ValueError("video stream count mismatch")
    video = video_streams[0]
    if str(video.get("codec_name") or "").casefold() != "h264":
        raise ValueError("video codec mismatch")
    if str(video.get("pix_fmt") or "").casefold() != "yuv420p":
        raise ValueError("pixel format mismatch")
    width = _integer(video.get("width"), "video width")
    height = _integer(video.get("height"), "video height")
    if (width, height) != (plan.output.width, plan.output.height):
        raise ValueError("canvas mismatch")
    fps = _frame_rate(
        video.get("avg_frame_rate") or video.get("r_frame_rate")
    )
    if abs(fps - plan.output.fps) > 0.01:
        raise ValueError("fps mismatch")
    duration_us = round(
        _number(format_data.get("duration"), "duration") * 1_000_000
    )
    duration_tolerance_us = max(round(1_000_000 / plan.output.fps), 40_000)
    if abs(duration_us - plan.timeline.duration_us) > duration_tolerance_us:
        raise ValueError("duration mismatch")
    expects_audio = _plan_has_audio(plan)
    if expects_audio and len(audio_streams) != 1:
        raise ValueError("audio stream count mismatch")
    if not expects_audio and audio_streams:
        raise ValueError("unexpected audio stream")
    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    audio_channels: int | None = None
    if expects_audio:
        audio = audio_streams[0]
        audio_codec = str(audio.get("codec_name") or "").casefold()
        if audio_codec != "aac":
            raise ValueError("audio codec mismatch")
        audio_sample_rate = _integer(
            audio.get("sample_rate"),
            "audio sample rate",
        )
        if audio_sample_rate != 48_000:
            raise ValueError("audio sample rate mismatch")
        audio_channels = _integer(audio.get("channels"), "audio channels")
        if audio_channels != 2:
            raise ValueError("audio channels mismatch")
    return OutputVerificationSummary(
        container=str(format_data.get("format_name") or ""),
        video_codec="h264",
        pixel_format="yuv420p",
        width=width,
        height=height,
        fps=fps,
        duration_us=duration_us,
        has_audio=expects_audio,
        audio_codec=audio_codec,
        audio_sample_rate=audio_sample_rate,
        audio_channels=audio_channels,
    )


def _plan_has_audio(plan: ExportPlan) -> bool:
    track_kind = {
        track.track_id: track.kind for track in plan.timeline.tracks
    }
    return any(
        track_kind[clip.track_id] == "audio"
        for clip in plan.timeline.clips
    )


def _frame_rate(value: Any) -> float:
    text = str(value or "")
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        denominator_value = float(denominator)
        if denominator_value == 0:
            raise ValueError("fps denominator is zero")
        return float(numerator) / denominator_value
    return _number(text, "fps")


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} is invalid")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is invalid") from exc


def _number(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is invalid") from exc


def _failed(
    kind: ExportFailureKind,
    message: str,
    *,
    material_id: str | None = None,
) -> ExportVerificationResult:
    return ExportVerificationResult(
        False,
        failure_kind=kind,
        message=message,
        material_id=material_id,
    )
