from __future__ import annotations

import hashlib
import importlib
import json
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any

from cli.contracts import (
    CliCommandOutcome,
    CliExitCode,
    CliFailure,
)
from cli.isolation import CliIsolation
from services.project_editing_profile import (
    EDITING_EXTENSION_KEY,
    resolve_project_editing_profile,
)
from services.timeline_edit_service import TimelineEditService
from services.timeline_query import build_playback_plan
from utils.media_metadata import (
    probe_media,
    resolve_ffmpeg_path,
    resolve_ffprobe_path,
)
from utils.project_store import (
    ProjectFile,
    ProjectMaterialRef,
    load_project,
    save_project,
)
from utils.timeline_model import (
    Timeline,
    TimelineClip,
    create_empty_timeline,
    load_project_timeline,
    validate_timeline,
    with_project_timeline,
)

RecorderFactory = Callable[[Any, Callable[[str], None]], Any]
CapabilityRuntimeFactory = Callable[[CliIsolation], Any]


@dataclass(frozen=True)
class CliCommandContext:
    timeout: float
    recorder_factory: RecorderFactory | None = None
    capability_runtime_factory: CapabilityRuntimeFactory | None = None

    def require_positive_timeout(self) -> None:
        if self.timeout <= 0:
            raise CliFailure(
                CliExitCode.USAGE_ERROR,
                "invalid_timeout",
                "timeout 必须大于 0",
            )


def run_doctor(context: CliCommandContext) -> CliCommandOutcome:
    started = time.monotonic()
    context.require_positive_timeout()
    ffmpeg = resolve_ffmpeg_path()
    ffprobe = resolve_ffprobe_path()
    result: dict[str, Any] = {
        "python": {
            "version": platform.python_version(),
            "compatible": sys.version_info >= (3, 12),
        },
        "platform": {
            "system": platform.system(),
            "windows": platform.system() == "Windows",
        },
        "ffmpeg": _dependency_status(ffmpeg, context.timeout),
        "ffprobe": _dependency_status(ffprobe, context.timeout),
        "pyav": _python_dependency_status("av"),
        "gui_initialized": _is_gui_initialized(),
    }
    _raise_if_timed_out(started, context.timeout)
    missing = [
        name
        for name in ("ffmpeg", "ffprobe", "pyav")
        if not bool(result[name]["available"])
    ]
    if missing:
        raise CliFailure(
            CliExitCode.DEPENDENCY_MISSING,
            "dependency_missing",
            "缺少 QuickRec 必需媒体依赖",
            context={"dependencies": missing},
        )
    if not result["python"]["compatible"]:
        raise CliFailure(
            CliExitCode.VALIDATION_FAILED,
            "python_version_unsupported",
            "QuickRecCLI 需要 Python 3.12 或更高版本",
        )
    return CliCommandOutcome(result=result)


def _is_gui_initialized() -> bool:
    qt_widgets = sys.modules.get("PyQt6.QtWidgets")
    application_type = getattr(qt_widgets, "QApplication", None)
    if application_type is None:
        return False
    return application_type.instance() is not None


def run_probe(
    context: CliCommandContext,
    video_path: str | Path,
) -> CliCommandOutcome:
    started = time.monotonic()
    context.require_positive_timeout()
    path = Path(video_path)
    if not path.is_file():
        raise CliFailure(
            CliExitCode.VALIDATION_FAILED,
            "media_missing",
            "媒体文件不存在或不是普通文件",
            context={"file_name": path.name},
        )
    metadata = probe_media(path, timeout=context.timeout)
    _raise_if_timed_out(started, context.timeout)
    if not metadata.ok:
        raise CliFailure(
            CliExitCode.VALIDATION_FAILED,
            "invalid_media",
            "媒体文件无法解析",
            context={
                "file_name": path.name,
                "detail": _safe_error(metadata.error),
            },
        )
    return CliCommandOutcome(
        result={
            "file_name": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "duration_sec": metadata.duration_sec,
            "width": metadata.width,
            "height": metadata.height,
            "fps": metadata.fps,
        }
    )


def run_project_validate(
    context: CliCommandContext,
    project_path: str | Path,
) -> CliCommandOutcome:
    started = time.monotonic()
    context.require_positive_timeout()
    loaded = load_project(project_path)
    _raise_if_timed_out(started, context.timeout)
    if not loaded.ok or loaded.project is None:
        raise CliFailure(
            CliExitCode.VALIDATION_FAILED,
            "invalid_project",
            "项目文件校验失败",
            context={
                "status": loaded.status,
                "detail": _safe_error(loaded.error),
            },
        )
    project = loaded.project
    timeline_result = load_project_timeline(project)
    editing_timeline = (
        timeline_result.timeline
        if timeline_result.timeline is not None
        else create_empty_timeline(project.project_id)
    )
    editing = _editing_validation_result(project, editing_timeline)
    return CliCommandOutcome(
        result={
            "status": loaded.status,
            "project_id": project.project_id,
            "name": project.name,
            "archived": bool(project.archived_at),
            "material_count": len(project.materials),
            "timeline_present": "quickrec.timeline" in project.extensions,
            **editing,
        }
    )


def run_timeline_validate(
    context: CliCommandContext,
    project_path: str | Path,
) -> CliCommandOutcome:
    started = time.monotonic()
    context.require_positive_timeout()
    loaded = load_project(project_path)
    if not loaded.ok or loaded.project is None:
        raise CliFailure(
            CliExitCode.VALIDATION_FAILED,
            "invalid_project",
            "项目文件校验失败",
            context={
                "status": loaded.status,
                "detail": _safe_error(loaded.error),
            },
        )
    timeline_result = load_project_timeline(loaded.project)
    _raise_if_timed_out(started, context.timeout)
    if not timeline_result.ok or timeline_result.timeline is None:
        raise CliFailure(
            CliExitCode.VALIDATION_FAILED,
            "invalid_timeline",
            "时间线校验失败",
            context={
                "status": timeline_result.status,
                "read_only": timeline_result.read_only,
                "detail": _safe_error(timeline_result.error),
            },
        )
    timeline = timeline_result.timeline
    editing = _editing_validation_result(loaded.project, timeline)
    linked_clips = [
        clip for clip in timeline.clips if clip.link_group_id is not None
    ]
    return CliCommandOutcome(
        result={
            "status": timeline_result.status,
            "timeline_schema": timeline.schema_version,
            "time_unit": timeline.time_unit,
            "track_count": len(timeline.tracks),
            "clip_count": len(timeline.clips),
            "linked_clip_count": len(linked_clips),
            "unlinked_clip_count": len(timeline.clips) - len(linked_clips),
            "link_group_count": len(
                {
                    clip.link_group_id
                    for clip in linked_clips
                    if clip.link_group_id is not None
                }
            ),
            "read_only": (
                timeline_result.read_only
                or bool(editing["editing_read_only"])
            ),
            "persisted": timeline_result.persisted,
            **editing,
        }
    )


def run_record(
    context: CliCommandContext,
    isolation: CliIsolation,
    *,
    mode: str,
    duration: float,
    fps: int,
    audio: str,
) -> CliCommandOutcome:
    context.require_positive_timeout()
    if mode != "fullscreen":
        raise CliFailure(
            CliExitCode.USAGE_ERROR,
            "unsupported_record_mode",
            "CLI 录制仅支持 fullscreen",
        )
    if duration <= 0:
        raise CliFailure(
            CliExitCode.USAGE_ERROR,
            "invalid_duration",
            "duration 必须大于 0",
        )
    if fps not in (30, 60, 120):
        raise CliFailure(
            CliExitCode.USAGE_ERROR,
            "invalid_fps",
            "fps 仅支持 30、60 或 120",
        )
    audio_map = {
        "none": "none",
        "system": "system",
        "mic": "microphone",
        "both": "both",
    }
    if audio not in audio_map:
        raise CliFailure(
            CliExitCode.USAGE_ERROR,
            "invalid_audio",
            "audio 仅支持 none、system、mic 或 both",
        )

    snapshot = isolation.activate()
    recorder: Any | None = None
    saved_paths: list[str] = []
    started = time.monotonic()
    try:
        if fps == 120:
            _ensure_120_capability(context, isolation)
        from config import ConfigManager

        config = ConfigManager()
        config.set("save_path", str(isolation.output_dir))
        config.set("quality", "high")
        config.set("fps", fps)
        config.set("audio_source", audio_map[audio])
        factory = context.recorder_factory or _default_recorder_factory
        recorder = factory(config, saved_paths.append)
        if not recorder.start_fullscreen():
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "recording_start_failed",
                "全屏录制未能启动",
                context=_safe_recorder_error(recorder),
            )

        preflight = recorder.get_audio_preflight()
        expected_audio = audio_map[audio]
        if expected_audio != "none" and (
            bool(getattr(preflight, "degraded", False))
            or str(getattr(preflight, "final_source", "")) != expected_audio
        ):
            recorder.stop(cancel=True)
            recorder.wait_until_idle(timeout=min(context.timeout, 30.0))
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "audio_unavailable",
                "请求的音频设备不可用，录制已取消",
                context={
                    "requested": expected_audio,
                    "actual": str(getattr(preflight, "final_source", "")),
                    "reason": _safe_error(str(getattr(preflight, "reason", ""))),
                },
            )

        deadline = started + context.timeout
        record_until = time.monotonic() + duration
        while time.monotonic() < record_until:
            if time.monotonic() >= deadline:
                recorder.stop(cancel=True)
                recorder.wait_until_idle(timeout=10.0)
                raise CliFailure(
                    CliExitCode.TIMEOUT,
                    "recording_timeout",
                    "录制命令执行超时",
                )
            time.sleep(min(0.05, max(record_until - time.monotonic(), 0.001)))

        recorder.stop()
        remaining = max(deadline - time.monotonic(), 0.0)
        if remaining <= 0 or not recorder.wait_until_idle(timeout=remaining):
            recorder.stop(cancel=True)
            raise CliFailure(
                CliExitCode.TIMEOUT,
                "recording_finalize_timeout",
                "录制停止或保存超时",
            )
        output_path = Path(saved_paths[-1]) if saved_paths else Path()
        if not output_path.is_file():
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "recording_output_missing",
                "录制完成但未生成可用视频",
                context=_safe_recorder_error(recorder),
            )
        output_relative = _relative_to_workspace(output_path, isolation)
        remaining = max(deadline - time.monotonic(), 0.001)
        metadata = probe_media(output_path, timeout=remaining)
        if not metadata.ok:
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "recording_output_invalid",
                "录制视频无法通过 FFprobe 校验",
                context={"detail": _safe_error(metadata.error)},
            )
        recording_metadata = dict(recorder.get_last_recording_metadata())
        result = {
            "output": output_relative,
            "size_bytes": output_path.stat().st_size,
            "sha256": _sha256(output_path),
            "duration_sec": metadata.duration_sec,
            "width": metadata.width,
            "height": metadata.height,
            "fps": metadata.fps,
            "requested_fps": fps,
            "requested_audio": audio,
            "actual_audio": recording_metadata.get("audio_source", "none"),
            "recording": _sanitize_mapping(recording_metadata),
        }
        evidence_path = isolation.evidence_dir / "record.json"
        _write_json(evidence_path, result)
        return CliCommandOutcome(
            result=result,
            evidence=[isolation.evidence_reference(evidence_path)],
        )
    finally:
        if recorder is not None:
            try:
                state = recorder.get_state() if hasattr(recorder, "get_state") else None
                if state is not None and getattr(state, "value", "idle") != "idle":
                    recorder.stop(cancel=True)
                    recorder.wait_until_idle(timeout=10.0)
            except Exception:
                pass
        isolation.restore(snapshot)


def run_editing_smoke(
    context: CliCommandContext,
    isolation: CliIsolation,
    *,
    project_path: str | Path | None = None,
) -> CliCommandOutcome:
    context.require_positive_timeout()
    snapshot = isolation.activate()
    started = time.monotonic()
    try:
        smoke_root = isolation.workspace / "editing-smoke"
        smoke_root.mkdir(parents=True, exist_ok=True)
        source_path = (
            Path(project_path).resolve()
            if project_path is not None
            else smoke_root / "generated-input.qrproj"
        )
        if project_path is None:
            _write_smoke_project(source_path)
        if not source_path.is_file():
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "input_project_missing",
                "editing smoke 输入项目不存在",
            )
        input_hash = _sha256(source_path)
        copied_path = smoke_root / "project-copy.qrproj"
        shutil.copy2(source_path, copied_path)

        copied = load_project(copied_path)
        if not copied.ok or copied.project is None:
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "invalid_project",
                "editing smoke 输入项目不可用",
                context={"status": copied.status},
            )
        project = _ensure_smoke_timeline(copied_path, copied.project)
        timeline_result = load_project_timeline(project)
        if not timeline_result.ok or timeline_result.timeline is None:
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "invalid_timeline",
                "editing smoke 时间线不可用",
            )
        timeline = timeline_result.timeline
        selected = next(
            (
                clip
                for clip in timeline.clips
                if next(
                    track
                    for track in timeline.tracks
                    if track.track_id == clip.track_id
                ).kind
                == "video"
            ),
            None,
        )
        if selected is None:
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "smoke_fixture_invalid",
                "editing smoke 缺少视频片段",
            )

        service = TimelineEditService()
        before_timeline = deepcopy(timeline)
        trim = service.trim(
            timeline,
            project,
            selected.clip_id,
            source_start_us=1_000_000,
            source_end_us=5_000_000,
        )
        if not trim.valid or trim.timeline is None:
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "trim_smoke_failed",
                "editing smoke 裁剪候选失败",
                context={"conflicts": [item.code for item in trim.conflicts]},
            )
        rollback_valid = timeline.to_dict() == before_timeline.to_dict()
        trimmed_selected = next(
            clip for clip in trim.timeline.clips if clip.clip_id == selected.clip_id
        )
        split_at = trimmed_selected.timeline_start_us + 2_000_000
        split = service.split(
            trim.timeline,
            project,
            selected.clip_id,
            playhead_us=split_at,
        )
        if not split.valid or split.timeline is None:
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "split_smoke_failed",
                "editing smoke 分割候选失败",
                context={"conflicts": [item.code for item in split.conflicts]},
            )
        validate_timeline(split.timeline, project)
        playback = build_playback_plan(project, split.timeline, split_at - 100_000)
        playback_valid = (
            playback.video is not None
            and playback.video.source_position_us >= 1_000_000
        )
        candidate_project = with_project_timeline(project, split.timeline)
        saved = save_project(copied_path, candidate_project)
        if not saved.ok:
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "smoke_save_failed",
                "editing smoke 项目副本保存失败",
                context={"stage": saved.stage},
            )
        reloaded = load_project(copied_path)
        reloaded_timeline = (
            load_project_timeline(reloaded.project)
            if reloaded.ok and reloaded.project is not None
            else None
        )
        reload_valid = bool(
            reloaded_timeline
            and reloaded_timeline.ok
            and reloaded_timeline.timeline is not None
            and reloaded_timeline.timeline.schema_version == 2
        )
        _raise_if_timed_out(started, context.timeout)
        result = {
            "input_unchanged": _sha256(source_path) == input_hash,
            "timeline_schema": split.timeline.schema_version,
            "trim_valid": trim.valid,
            "split_valid": split.valid,
            "rollback_valid": rollback_valid,
            "playback_plan_valid": playback_valid,
            "reload_valid": reload_valid,
            "clip_count": len(split.timeline.clips),
            "track_count": len(split.timeline.tracks),
        }
        evidence_report = isolation.evidence_dir / "editing-smoke.json"
        evidence_project = isolation.evidence_dir / "editing-smoke-project.qrproj"
        _write_json(evidence_report, result)
        shutil.copy2(copied_path, evidence_project)
        return CliCommandOutcome(
            result=result,
            evidence=[
                isolation.evidence_reference(evidence_report),
                isolation.evidence_reference(evidence_project),
            ],
        )
    finally:
        isolation.restore(snapshot)


def _default_recorder_factory(
    config: Any,
    on_saved: Callable[[str], None],
) -> Any:
    from recorder.recorder_manager import RecorderManager

    return RecorderManager(config, on_saved=on_saved)


def _ensure_120_capability(
    context: CliCommandContext,
    isolation: CliIsolation,
) -> None:
    if context.capability_runtime_factory is not None:
        runtime = context.capability_runtime_factory(isolation)
    else:
        from services.capture_capability_runtime import CaptureCapabilityRuntime

        runtime = CaptureCapabilityRuntime(
            save_path=lambda: str(isolation.output_dir),
            ffmpeg_path=resolve_ffmpeg_path(),
            store_path=isolation.appdata_dir
            / "QuickRec"
            / "capture-capabilities.json",
        )
    inspection = runtime.inspect()
    if (
        inspection.display.monitor_count != 1
        or inspection.display.refresh_hz < 119
    ):
        raise CliFailure(
            CliExitCode.VALIDATION_FAILED,
            "capture_120_environment_unsupported",
            "当前显示环境不满足 120 FPS 门禁",
            context={
                "monitor_count": inspection.display.monitor_count,
                "refresh_hz": inspection.display.refresh_hz,
            },
        )
    if inspection.readiness.ready:
        return
    result = runtime.run(Event())
    if not result.passed:
        raise CliFailure(
            CliExitCode.VALIDATION_FAILED,
            "capture_120_gate_failed",
            "120 FPS 能力检测未通过",
            context={
                "stage": result.failure_stage,
                "reason": _safe_error(result.failure_reason),
                "average_fps": result.average_fps,
                "minimum_one_second_fps": result.minimum_one_second_fps,
            },
        )


def _write_smoke_project(path: Path) -> None:
    project = ProjectFile(
        project_id="quickrec-cli-smoke",
        name="QuickRecCLI editing smoke",
        description="",
        created_at="2026-07-29T00:00:00+08:00",
        updated_at="2026-07-29T00:00:00+08:00",
    )
    written = save_project(path, project)
    if not written.ok:
        raise CliFailure(
            CliExitCode.ISOLATION_ERROR,
            "smoke_input_prepare_failed",
            "无法创建 editing smoke 输入项目",
            context={"stage": written.stage},
        )


def _editing_validation_result(
    project: ProjectFile,
    timeline: Timeline,
) -> dict[str, object]:
    raw = project.extensions.get(EDITING_EXTENSION_KEY)
    raw_schema = raw.get("schema_version") if isinstance(raw, dict) else None
    schema = (
        raw_schema
        if isinstance(raw_schema, int) and not isinstance(raw_schema, bool)
        else None
    )
    resolved = resolve_project_editing_profile(project, timeline)
    return {
        "editing_present": raw is not None,
        "editing_schema": schema,
        "editing_status": resolved.status,
        "editing_fps": resolved.profile.editing_fps,
        "editing_fps_locked": resolved.profile.fps_locked,
        "editing_read_only": resolved.read_only,
        "editing_error": _safe_error(resolved.error),
    }


def _ensure_smoke_timeline(path: Path, project: ProjectFile) -> ProjectFile:
    timeline_result = load_project_timeline(project)
    if (
        project.materials
        and timeline_result.ok
        and timeline_result.timeline is not None
        and timeline_result.timeline.clips
    ):
        return project

    candidate = deepcopy(project)
    material_id = "quickrec-cli-smoke-material"
    candidate.materials = [
        ProjectMaterialRef(
            material_id=material_id,
            last_known_path=str(path.parent / "controlled-source.mp4"),
            file_name="controlled-source.mp4",
            added_at="2026-07-29T00:00:00+08:00",
            metadata_snapshot={
                "duration_sec": 6.0,
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "has_audio": True,
            },
        )
    ]
    timeline = create_empty_timeline(candidate.project_id)
    timeline.schema_version = 1
    video_track = next(track for track in timeline.tracks if track.kind == "video")
    audio_track = next(track for track in timeline.tracks if track.kind == "audio")
    timeline.clips = [
        TimelineClip(
            clip_id="quickrec-cli-video",
            material_id=material_id,
            track_id=video_track.track_id,
            timeline_start_us=0,
            timeline_duration_us=6_000_000,
            source_start_us=0,
            source_duration_us=6_000_000,
            link_group_id="quickrec-cli-link",
        ),
        TimelineClip(
            clip_id="quickrec-cli-audio",
            material_id=material_id,
            track_id=audio_track.track_id,
            timeline_start_us=0,
            timeline_duration_us=6_000_000,
            source_start_us=0,
            source_duration_us=6_000_000,
            link_group_id="quickrec-cli-link",
        ),
    ]
    validate_timeline(timeline, candidate)
    candidate = with_project_timeline(candidate, timeline)
    saved = save_project(path, candidate)
    if not saved.ok or saved.project is None:
        raise CliFailure(
            CliExitCode.ISOLATION_ERROR,
            "smoke_fixture_save_failed",
            "无法保存 editing smoke 项目副本",
            context={"stage": saved.stage},
        )
    return saved.project


def _safe_recorder_error(recorder: Any) -> dict[str, object]:
    try:
        context = recorder.get_diagnostic_context()
        failure = context.get("recorder", {}).get("last_failure_reason", "")
        return {"reason": _safe_error(str(failure))}
    except Exception:
        return {}


def _relative_to_workspace(path: Path, isolation: CliIsolation) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(isolation.workspace).as_posix()
    except ValueError as exc:
        raise CliFailure(
            CliExitCode.ISOLATION_ERROR,
            "output_outside_workspace",
            "录制输出越过了隔离工作区",
        ) from exc


def _sanitize_mapping(mapping: dict[str, Any]) -> dict[str, object]:
    allowed = {
        "duration_sec",
        "width",
        "height",
        "fps",
        "mode",
        "audio_source",
        "target_fps",
        "stable_120",
        "average_fps",
        "minimum_one_second_fps",
        "maximum_backlog_ms",
        "submitted_frames",
    }
    return {
        key: value
        for key, value in mapping.items()
        if key in allowed and isinstance(value, (str, int, float, bool, type(None)))
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise CliFailure(
            CliExitCode.ISOLATION_ERROR,
            "evidence_write_failed",
            "无法写入 CLI 证据文件",
            context={"error_type": type(exc).__name__},
        ) from exc


def _dependency_status(path: str, timeout: float) -> dict[str, object]:
    if not path or not Path(path).is_file():
        return {"available": False, "version": ""}
    try:
        completed = subprocess.run(
            [path, "-version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(timeout, 10.0),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise CliFailure(
            CliExitCode.TIMEOUT,
            "dependency_timeout",
            "媒体依赖检查超时",
            context={"dependency": Path(path).stem},
        ) from exc
    except OSError:
        return {"available": False, "version": ""}
    version = completed.stdout.splitlines()[0].strip() if completed.stdout else ""
    return {
        "available": completed.returncode == 0,
        "version": version,
    }


def _python_dependency_status(module_name: str) -> dict[str, object]:
    try:
        module = importlib.import_module(module_name)
    except (ImportError, OSError):
        return {"available": False, "version": ""}
    return {
        "available": True,
        "version": str(getattr(module, "__version__", "")),
    }


def _raise_if_timed_out(started: float, timeout: float) -> None:
    if time.monotonic() - started > timeout:
        raise CliFailure(
            CliExitCode.TIMEOUT,
            "command_timeout",
            "命令执行超时",
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _safe_error(value: str, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text[:limit]
