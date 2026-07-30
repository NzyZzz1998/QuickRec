"""从已保存项目构造不可变导出计划并执行创建前预检。"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from exporting.models import (
    ExportClip,
    ExportMaterialProbe,
    ExportMaterialSnapshot,
    ExportOutputSpec,
    ExportPlan,
    ExportPlanBuildResult,
    ExportPlanIssue,
    ExportPlanRequest,
    ExportProjectSnapshot,
    ExportTimelineSnapshot,
    ExportTrack,
    ExportValidationError,
    OverwriteMode,
    RenderPolicy,
    TargetFingerprint,
)
from utils.media_metadata import resolve_ffmpeg_path, resolve_ffprobe_path
from utils.project_store import PROJECT_SCHEMA_VERSION, load_project
from utils.recording_library_store import normalize_windows_path
from utils.timeline_model import (
    TIMELINE_SCHEMA_VERSION,
    load_project_timeline,
)

MediaProbe = Callable[[Path], ExportMaterialProbe]
PathResolver = Callable[[], str]
FreeSpaceProvider = Callable[[Path], int]
Clock = Callable[[], str]
IdFactory = Callable[[], str]
SizeEstimator = Callable[[int, int, int, int], int]

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_FILENAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class ExportPlanBuilder:
    def __init__(
        self,
        *,
        media_probe: MediaProbe | None = None,
        ffmpeg_resolver: PathResolver = resolve_ffmpeg_path,
        ffprobe_resolver: PathResolver = resolve_ffprobe_path,
        free_space_provider: FreeSpaceProvider | None = None,
        clock: Clock | None = None,
        id_factory: IdFactory | None = None,
        size_estimator: SizeEstimator | None = None,
    ) -> None:
        self._ffmpeg_resolver = ffmpeg_resolver
        self._ffprobe_resolver = ffprobe_resolver
        self._media_probe = media_probe or self._probe_material
        self._free_space_provider = free_space_provider or (
            lambda path: shutil.disk_usage(path).free
        )
        self._clock = clock or (
            lambda: datetime.now(UTC).isoformat(timespec="seconds")
        )
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._size_estimator = size_estimator or _estimate_output_size

    def build(self, request: ExportPlanRequest) -> ExportPlanBuildResult:
        errors: list[ExportPlanIssue] = []
        warnings: list[ExportPlanIssue] = []
        suggested_filename: str | None = None

        if not request.project_saved:
            errors.append(_issue("PROJECT_NOT_SAVED", "项目尚未成功保存"))
        if request.save_pending:
            errors.append(
                _issue("PROJECT_SAVE_PENDING", "项目存在待处理的保存")
            )
        if request.external_conflict:
            errors.append(
                _issue(
                    "PROJECT_EXTERNAL_CONFLICT",
                    "项目文件存在外部修改冲突",
                )
            )
        if request.incomplete_job_count >= 20:
            errors.append(
                _issue(
                    "QUEUE_LIMIT_REACHED",
                    "未完成导出任务已达到 20 条",
                    count=request.incomplete_job_count,
                )
            )

        ffmpeg = self._ffmpeg_resolver()
        ffprobe = self._ffprobe_resolver()
        if not ffmpeg or not Path(ffmpeg).is_file():
            errors.append(_issue("FFMPEG_UNAVAILABLE", "FFmpeg 不可用"))
        if not ffprobe or not Path(ffprobe).is_file():
            errors.append(_issue("FFPROBE_UNAVAILABLE", "FFprobe 不可用"))

        project_path = Path(request.project_path).expanduser().resolve()
        loaded = load_project(project_path)
        if not loaded.ok or loaded.project is None:
            errors.append(
                _issue(
                    f"PROJECT_{loaded.status.upper()}",
                    loaded.error or "项目文件不可用",
                )
            )
            return _failed(errors, warnings)
        project = loaded.project

        timeline_result = load_project_timeline(project)
        if not timeline_result.ok or timeline_result.timeline is None:
            errors.append(
                _issue(
                    f"TIMELINE_{timeline_result.status.upper()}",
                    timeline_result.error or "时间线不可用",
                )
            )
            return _failed(errors, warnings)
        timeline = timeline_result.timeline
        if timeline.schema_version != TIMELINE_SCHEMA_VERSION:
            errors.append(
                _issue(
                    "TIMELINE_SCHEMA_UNSUPPORTED",
                    "导出需要 timeline schema v2",
                    schema_version=timeline.schema_version,
                )
            )
        if not timeline.clips:
            errors.append(_issue("TIMELINE_EMPTY", "空时间线不能导出"))

        output_directory = Path(request.output_directory).expanduser().resolve()
        try:
            _ensure_writable_directory(output_directory)
        except OSError as exc:
            errors.append(
                _issue(
                    "OUTPUT_DIRECTORY_UNWRITABLE",
                    "输出目录不可写",
                    error_type=type(exc).__name__,
                )
            )

        filename = _sanitize_filename(request.filename, project.name, self._clock())
        target = output_directory / filename
        reserved_targets = {
            normalize_windows_path(Path(path).expanduser().resolve())
            for path in request.reserved_target_paths
        }
        target_reserved = normalize_windows_path(target) in reserved_targets
        target_fingerprint: TargetFingerprint | None = None
        if target.exists() or target_reserved:
            suggested_filename = _safe_suffix(
                output_directory,
                filename,
                reserved_targets=reserved_targets,
            )
            if request.overwrite_mode == OverwriteMode.REPLACE:
                if target_reserved:
                    errors.append(
                        _issue(
                            "OUTPUT_TARGET_RESERVED",
                            "目标已被另一个未完成导出任务占用",
                        )
                    )
                elif not target.is_file():
                    errors.append(
                        _issue("OUTPUT_TARGET_INVALID", "覆盖目标不是普通文件")
                    )
                else:
                    target_fingerprint = _target_fingerprint(target)
            elif request.accept_safe_suffix:
                filename = suggested_filename
                target = output_directory / filename
            else:
                errors.append(
                    _issue(
                        "OUTPUT_CONFLICT",
                        "目标文件已存在，需要接受安全文件名或显式覆盖",
                    )
                )
        elif request.overwrite_mode == OverwriteMode.REPLACE:
            errors.append(
                _issue(
                    "OVERWRITE_TARGET_MISSING",
                    "显式覆盖要求目标文件已经存在",
                )
            )

        if errors:
            return _failed(errors, warnings, suggested_filename)

        try:
            output = ExportOutputSpec(
                width=request.width,
                height=request.height,
                fps=request.fps,
                directory=str(output_directory),
                filename=filename,
                overwrite_mode=request.overwrite_mode,
                target_fingerprint=target_fingerprint,
            )
        except ExportValidationError as exc:
            errors.append(_issue("OUTPUT_INVALID", str(exc)))
            return _failed(errors, warnings, suggested_filename)

        tracks = tuple(
            ExportTrack(track.track_id, track.kind, track.order)
            for track in sorted(
                timeline.tracks,
                key=lambda item: (
                    0 if item.kind == "video" else 1,
                    item.order,
                    item.track_id,
                ),
            )
        )
        track_rank = {
            track.track_id: index for index, track in enumerate(tracks)
        }
        clips = tuple(
            ExportClip(
                clip_id=clip.clip_id,
                material_id=clip.material_id,
                track_id=clip.track_id,
                link_group_id=clip.link_group_id,
                timeline_start_us=clip.timeline_start_us,
                timeline_duration_us=clip.timeline_duration_us,
                source_start_us=clip.source_start_us,
                source_duration_us=clip.source_duration_us,
            )
            for clip in sorted(
                timeline.clips,
                key=lambda item: (
                    item.timeline_start_us,
                    track_rank.get(item.track_id, len(track_rank)),
                    item.clip_id,
                ),
            )
        )
        duration_us = max((clip.timeline_end_us for clip in clips), default=0)

        project_materials = {
            material.material_id: material for material in project.materials
        }
        track_kind_by_id = {track.track_id: track.kind for track in tracks}
        material_streams = {
            material_id: {
                track_kind_by_id[clip.track_id]
                for clip in clips
                if clip.material_id == material_id
            }
            for material_id in {clip.material_id for clip in clips}
        }
        material_snapshots: list[ExportMaterialSnapshot] = []
        for material_id in sorted({clip.material_id for clip in clips}):
            material = project_materials.get(material_id)
            if material is None:
                errors.append(
                    _issue(
                        "MATERIAL_REFERENCE_MISSING",
                        "时间线引用的项目素材不存在",
                        material_id=material_id,
                    )
                )
                continue
            path = Path(material.last_known_path).expanduser()
            if not path.is_absolute():
                path = (project_path.parent / path).resolve()
            else:
                path = path.resolve()
            if not path.is_file():
                errors.append(
                    _issue(
                        "MATERIAL_MISSING",
                        "素材文件已移动或删除",
                        material_id=material_id,
                    )
                )
                continue
            try:
                stat = path.stat()
                probe = self._media_probe(path)
            except (OSError, ValueError, RuntimeError) as exc:
                errors.append(
                    _issue(
                        "MATERIAL_UNREADABLE",
                        "素材不可读取或不可解析",
                        material_id=material_id,
                        error_type=type(exc).__name__,
                    )
                )
                continue
            if not probe.ok:
                errors.append(
                    _issue(
                        "MATERIAL_UNREADABLE",
                        probe.error or "素材不可解析",
                        material_id=material_id,
                    )
                )
                continue
            used_streams = material_streams[material_id]
            if (
                "video" in used_streams
                and (probe.video_codec or "").casefold() != "h264"
            ):
                errors.append(
                    _issue(
                        "MATERIAL_CODEC_UNSUPPORTED",
                        "视频轨仅支持 H.264 素材",
                        material_id=material_id,
                        stream="video",
                        codec=probe.video_codec or "missing",
                    )
                )
            if (
                "audio" in used_streams
                and (probe.audio_codec or "").casefold() != "aac"
            ):
                errors.append(
                    _issue(
                        "MATERIAL_CODEC_UNSUPPORTED",
                        "音频轨仅支持 AAC 素材",
                        material_id=material_id,
                        stream="audio",
                        codec=probe.audio_codec or "missing",
                    )
                )
            if errors:
                continue
            try:
                snapshot = ExportMaterialSnapshot(
                    material_id=material_id,
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
            except ExportValidationError as exc:
                errors.append(
                    _issue(
                        "MATERIAL_UNREADABLE",
                        str(exc),
                        material_id=material_id,
                    )
                )
                continue
            material_snapshots.append(snapshot)

        if errors:
            return _failed(errors, warnings, suggested_filename)

        estimated_size = self._size_estimator(
            duration_us,
            output.width,
            output.height,
            output.fps,
        )
        output = ExportOutputSpec(
            width=output.width,
            height=output.height,
            fps=output.fps,
            directory=output.directory,
            filename=output.filename,
            overwrite_mode=output.overwrite_mode,
            estimated_size_bytes=estimated_size,
            target_fingerprint=output.target_fingerprint,
        )
        free_bytes = self._free_space_provider(output_directory)
        if free_bytes < 200 * 1024**2:
            warnings.append(
                _issue(
                    "DISK_SPACE_CRITICAL",
                    "可用空间低于 200 MB，导出很可能失败",
                    free_bytes=free_bytes,
                    estimated_size_bytes=estimated_size,
                )
            )
        elif free_bytes < estimated_size:
            warnings.append(
                _issue(
                    "DISK_SPACE_CRITICAL",
                    "可用空间低于保守估算值",
                    free_bytes=free_bytes,
                    estimated_size_bytes=estimated_size,
                )
            )
        elif free_bytes < int(estimated_size * 1.5):
            warnings.append(
                _issue(
                    "DISK_SPACE_WARNING",
                    "可用空间低于保守估算值的 1.5 倍",
                    free_bytes=free_bytes,
                    estimated_size_bytes=estimated_size,
                )
            )

        plan = ExportPlan.create(
            plan_id=self._id_factory(),
            created_at=self._clock(),
            project=ExportProjectSnapshot(
                project_id=project.project_id,
                project_name=project.name,
                project_path=str(project_path),
                project_schema_version=PROJECT_SCHEMA_VERSION,
                timeline_schema_version=timeline.schema_version,
            ),
            timeline=ExportTimelineSnapshot(
                timeline_id=timeline.timeline_id,
                duration_us=duration_us,
                tracks=tracks,
                clips=clips,
            ),
            materials=tuple(material_snapshots),
            render_policy=RenderPolicy(),
            output=output,
        )
        return ExportPlanBuildResult(
            True,
            plan=plan,
            warnings=tuple(warnings),
            suggested_filename=suggested_filename,
        )

    def _probe_material(self, path: Path) -> ExportMaterialProbe:
        ffprobe = self._ffprobe_resolver()
        if not ffprobe:
            return ExportMaterialProbe(
                container="",
                video_codec=None,
                width=None,
                height=None,
                fps=None,
                duration_us=0,
                audio_codec=None,
                audio_sample_rate=None,
                audio_channels=None,
                audio_duration_us=None,
                ok=False,
                error="ffprobe executable not found",
            )
        return probe_export_material(path, ffprobe)


def probe_export_material(path: Path, executable: str) -> ExportMaterialProbe:
    command = [
        executable,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _failed_probe(type(exc).__name__)
    if completed.returncode != 0:
        return _failed_probe("ffprobe returned nonzero")
    try:
        payload = json.loads(completed.stdout)
        streams = [
            stream
            for stream in payload.get("streams", [])
            if isinstance(stream, dict)
        ]
        video = next(
            (stream for stream in streams if stream.get("codec_type") == "video"),
            None,
        )
        audio = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"),
            None,
        )
        format_data = payload.get("format")
        if not isinstance(format_data, dict):
            raise ValueError("ffprobe format is missing")
        duration_us = _seconds_to_us(format_data.get("duration"))
        if duration_us <= 0 or (video is None and audio is None):
            raise ValueError("required media streams are missing")
        return ExportMaterialProbe(
            container=str(format_data.get("format_name") or ""),
            video_codec=_stream_text(video, "codec_name"),
            width=_stream_int(video, "width"),
            height=_stream_int(video, "height"),
            fps=_frame_rate(video),
            duration_us=duration_us,
            audio_codec=_stream_text(audio, "codec_name"),
            audio_sample_rate=_stream_int(audio, "sample_rate"),
            audio_channels=_stream_int(audio, "channels"),
            audio_duration_us=(
                _seconds_to_us(audio.get("duration"))
                if audio is not None and audio.get("duration") is not None
                else (duration_us if audio is not None else None)
            ),
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return _failed_probe(f"invalid ffprobe output: {exc}")


def _failed_probe(error: str) -> ExportMaterialProbe:
    return ExportMaterialProbe(
        container="",
        video_codec=None,
        width=None,
        height=None,
        fps=None,
        duration_us=0,
        audio_codec=None,
        audio_sample_rate=None,
        audio_channels=None,
        audio_duration_us=None,
        ok=False,
        error=error,
    )


def _ensure_writable_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise NotADirectoryError(str(path))
    probe = path / f".quickrec-export-write-{uuid.uuid4().hex}.tmp"
    try:
        with probe.open("xb") as handle:
            handle.write(b"ok")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        probe.unlink(missing_ok=True)


def _sanitize_filename(filename: str, project_name: str, timestamp: str) -> str:
    fallback_stamp = re.sub(r"\D", "", timestamp)[:14] or "export"
    raw = str(filename or "").strip()
    if not raw:
        raw = f"{project_name}_{fallback_stamp}.mp4"
    suffix = ".mp4"
    if raw.lower().endswith(suffix):
        stem = raw[: -len(suffix)]
    else:
        stem = raw
    stem = _INVALID_FILENAME_CHARS.sub("_", stem).strip(" .")
    if not stem or stem.casefold() in _RESERVED_FILENAMES:
        stem = f"QuickRec_Export_{fallback_stamp}"
    return f"{stem}.mp4"


def _safe_suffix(
    directory: Path,
    filename: str,
    *,
    reserved_targets: set[str] | None = None,
) -> str:
    stem = Path(filename).stem
    suffix = Path(filename).suffix or ".mp4"
    reserved = reserved_targets or set()
    index = 1
    while True:
        candidate = f"{stem} ({index}){suffix}"
        candidate_path = directory / candidate
        if (
            not candidate_path.exists()
            and normalize_windows_path(candidate_path) not in reserved
        ):
            return candidate
        index += 1


def _target_fingerprint(path: Path) -> TargetFingerprint:
    stat = path.stat()
    return TargetFingerprint(
        normalized_path=normalize_windows_path(path),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
    )


def _estimate_output_size(
    duration_us: int,
    width: int,
    height: int,
    fps: int,
) -> int:
    duration_seconds = max(0.0, duration_us / 1_000_000)
    pixel_factor = (width * height) / (1920 * 1080)
    fps_factor = fps / 60
    video_bitrate = 12_000_000 * pixel_factor * fps_factor
    audio_bitrate = 192_000
    return max(
        1,
        int(((video_bitrate + audio_bitrate) / 8) * duration_seconds * 1.25),
    )


def _issue(
    code: str,
    message: str,
    **context: str | int | float | bool,
) -> ExportPlanIssue:
    return ExportPlanIssue(code, message, context)


def _failed(
    errors: list[ExportPlanIssue],
    warnings: list[ExportPlanIssue],
    suggested_filename: str | None = None,
) -> ExportPlanBuildResult:
    return ExportPlanBuildResult(
        False,
        errors=tuple(errors),
        warnings=tuple(warnings),
        suggested_filename=suggested_filename,
    )


def _stream_text(stream: dict[str, Any] | None, key: str) -> str | None:
    if stream is None:
        return None
    value = str(stream.get(key) or "").strip()
    return value or None


def _stream_int(stream: dict[str, Any] | None, key: str) -> int | None:
    if stream is None or stream.get(key) is None:
        return None
    return int(stream[key])


def _frame_rate(stream: dict[str, Any] | None) -> float | None:
    if stream is None:
        return None
    value = str(
        stream.get("avg_frame_rate")
        or stream.get("r_frame_rate")
        or ""
    )
    if not value:
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        denominator_value = float(denominator)
        return float(numerator) / denominator_value if denominator_value else None
    return float(value)


def _seconds_to_us(value: Any) -> int:
    return int(round(float(value) * 1_000_000))
