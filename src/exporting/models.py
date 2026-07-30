"""不可变导出计划、预检输入和稳定序列化合同。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, cast

PLAN_SCHEMA_VERSION = 1
SUPPORTED_FPS = frozenset({30, 60, 120})
MAX_CANVAS_WIDTH = 3840
MAX_CANVAS_HEIGHT = 2160
MAX_120_FPS_WIDTH = 1920
MAX_120_FPS_HEIGHT = 1080

TrackKind = Literal["video", "audio"]


class ExportValidationError(ValueError):
    """导出计划或请求不满足当前 schema 合同。"""


class OverwriteMode(StrEnum):
    DENY = "deny"
    REPLACE = "replace"


class ExportFailureKind(StrEnum):
    TOOL_MISSING = "tool_missing"
    TOOL_START_FAILED = "tool_start_failed"
    TOOL_FAILED = "tool_failed"
    TOOL_TIMEOUT = "tool_timeout"
    STALLED = "stalled"
    CANCELLED = "cancelled"
    MATERIAL_CHANGED = "material_changed"
    VERIFICATION_FAILED = "verification_failed"
    TARGET_CONFLICT = "target_conflict"
    TARGET_CHANGED = "target_changed"
    COMMIT_FAILED = "commit_failed"
    RECOVERY_AMBIGUOUS = "recovery_ambiguous"
    DISK_ERROR = "disk_error"
    INTERNAL_ERROR = "internal_error"


class ExportStage(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    RUNNING = "running"
    CANCELLING = "cancelling"
    VERIFYING = "verifying"
    COMMITTING = "committing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class TargetFingerprint:
    normalized_path: str
    size_bytes: int
    mtime_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalized_path": self.normalized_path,
            "size_bytes": self.size_bytes,
            "mtime_ns": self.mtime_ns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TargetFingerprint:
        return cls(
            normalized_path=_required_text(data, "normalized_path"),
            size_bytes=_required_int(data, "size_bytes"),
            mtime_ns=_required_int(data, "mtime_ns"),
        )


@dataclass(frozen=True)
class ExportOutputSpec:
    width: int
    height: int
    fps: int
    directory: str
    filename: str
    overwrite_mode: OverwriteMode = OverwriteMode.DENY
    container: str = "mp4"
    video_profile: str = "h264-crf20-veryfast-yuv420p"
    audio_profile: str = "aac-48k-stereo-192k"
    estimated_size_bytes: int = 0
    target_fingerprint: TargetFingerprint | None = None

    def __post_init__(self) -> None:
        _validate_output_dimensions(self.width, self.height, self.fps)
        if not str(self.directory).strip():
            raise ExportValidationError("output directory is required")
        filename = str(self.filename).strip()
        if not filename:
            raise ExportValidationError("output filename is required")
        if Path(filename).name != filename:
            raise ExportValidationError("output filename must not contain a directory")
        if not filename.lower().endswith(".mp4"):
            raise ExportValidationError("output filename must use .mp4")
        if self.container != "mp4":
            raise ExportValidationError("output container must be mp4")
        if self.estimated_size_bytes < 0:
            raise ExportValidationError("estimated size must be non-negative")
        if (
            self.overwrite_mode == OverwriteMode.REPLACE
            and self.target_fingerprint is None
        ):
            raise ExportValidationError(
                "explicit overwrite requires a target fingerprint"
            )

    @property
    def target_path(self) -> Path:
        return Path(self.directory) / self.filename

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "container": self.container,
            "video_profile": self.video_profile,
            "audio_profile": self.audio_profile,
            "directory": self.directory,
            "filename": self.filename,
            "overwrite_mode": self.overwrite_mode.value,
            "estimated_size_bytes": self.estimated_size_bytes,
            "target_fingerprint": (
                self.target_fingerprint.to_dict()
                if self.target_fingerprint is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportOutputSpec:
        raw_fingerprint = data.get("target_fingerprint")
        fingerprint = (
            TargetFingerprint.from_dict(_object(raw_fingerprint, "target_fingerprint"))
            if raw_fingerprint is not None
            else None
        )
        try:
            overwrite_mode = OverwriteMode(
                str(data.get("overwrite_mode") or OverwriteMode.DENY.value)
            )
        except ValueError as exc:
            raise ExportValidationError("unsupported overwrite mode") from exc
        return cls(
            width=_required_int(data, "width"),
            height=_required_int(data, "height"),
            fps=_required_int(data, "fps"),
            directory=_required_text(data, "directory"),
            filename=_required_text(data, "filename"),
            overwrite_mode=overwrite_mode,
            container=str(data.get("container") or "mp4"),
            video_profile=str(
                data.get("video_profile") or "h264-crf20-veryfast-yuv420p"
            ),
            audio_profile=str(
                data.get("audio_profile") or "aac-48k-stereo-192k"
            ),
            estimated_size_bytes=_optional_int(
                data.get("estimated_size_bytes"),
                default=0,
            ),
            target_fingerprint=fingerprint,
        )


@dataclass(frozen=True)
class ExportProjectSnapshot:
    project_id: str
    project_name: str
    project_path: str
    project_schema_version: int
    timeline_schema_version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "project_path": self.project_path,
            "project_schema_version": self.project_schema_version,
            "timeline_schema_version": self.timeline_schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportProjectSnapshot:
        return cls(
            project_id=_required_text(data, "project_id"),
            project_name=_required_text(data, "project_name"),
            project_path=_required_text(data, "project_path"),
            project_schema_version=_required_int(data, "project_schema_version"),
            timeline_schema_version=_required_int(
                data,
                "timeline_schema_version",
            ),
        )


@dataclass(frozen=True)
class ExportTrack:
    track_id: str
    kind: TrackKind
    order: int

    def __post_init__(self) -> None:
        if self.kind not in ("video", "audio"):
            raise ExportValidationError(f"unsupported export track kind: {self.kind}")
        if self.order < 0:
            raise ExportValidationError("export track order must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "kind": self.kind,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportTrack:
        kind = _required_text(data, "kind")
        if kind not in ("video", "audio"):
            raise ExportValidationError(f"unsupported export track kind: {kind}")
        return cls(
            track_id=_required_text(data, "track_id"),
            kind=cast(TrackKind, kind),
            order=_required_int(data, "order"),
        )


@dataclass(frozen=True)
class ExportClip:
    clip_id: str
    material_id: str
    track_id: str
    link_group_id: str | None
    timeline_start_us: int
    timeline_duration_us: int
    source_start_us: int
    source_duration_us: int

    def __post_init__(self) -> None:
        if self.timeline_start_us < 0 or self.source_start_us < 0:
            raise ExportValidationError("clip start positions must be non-negative")
        if self.timeline_duration_us <= 0 or self.source_duration_us <= 0:
            raise ExportValidationError("clip durations must be positive")
        if self.timeline_duration_us != self.source_duration_us:
            raise ExportValidationError(
                "timeline and source duration must match for v1.9.4 export"
            )

    @property
    def timeline_end_us(self) -> int:
        return self.timeline_start_us + self.timeline_duration_us

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "material_id": self.material_id,
            "track_id": self.track_id,
            "link_group_id": self.link_group_id,
            "timeline_start_us": self.timeline_start_us,
            "timeline_duration_us": self.timeline_duration_us,
            "source_start_us": self.source_start_us,
            "source_duration_us": self.source_duration_us,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportClip:
        return cls(
            clip_id=_required_text(data, "clip_id"),
            material_id=_required_text(data, "material_id"),
            track_id=_required_text(data, "track_id"),
            link_group_id=_optional_text(data.get("link_group_id")),
            timeline_start_us=_required_int(data, "timeline_start_us"),
            timeline_duration_us=_required_int(data, "timeline_duration_us"),
            source_start_us=_required_int(data, "source_start_us"),
            source_duration_us=_required_int(data, "source_duration_us"),
        )


@dataclass(frozen=True)
class ExportTimelineSnapshot:
    timeline_id: str
    duration_us: int
    tracks: tuple[ExportTrack, ...]
    clips: tuple[ExportClip, ...]

    def __post_init__(self) -> None:
        if self.duration_us <= 0:
            raise ExportValidationError("export timeline must not be empty")
        track_ids = {track.track_id for track in self.tracks}
        if len(track_ids) != len(self.tracks):
            raise ExportValidationError("duplicate export track id")
        clip_ids = {clip.clip_id for clip in self.clips}
        if len(clip_ids) != len(self.clips):
            raise ExportValidationError("duplicate export clip id")
        if not self.clips:
            raise ExportValidationError("export timeline must contain clips")
        if any(clip.track_id not in track_ids for clip in self.clips):
            raise ExportValidationError("export clip references a missing track")
        actual_duration = max(clip.timeline_end_us for clip in self.clips)
        if actual_duration != self.duration_us:
            raise ExportValidationError("export timeline duration is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline_id": self.timeline_id,
            "duration_us": self.duration_us,
            "tracks": [track.to_dict() for track in self.tracks],
            "clips": [clip.to_dict() for clip in self.clips],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportTimelineSnapshot:
        return cls(
            timeline_id=_required_text(data, "timeline_id"),
            duration_us=_required_int(data, "duration_us"),
            tracks=tuple(
                ExportTrack.from_dict(_object(item, "track"))
                for item in _array(data.get("tracks"), "tracks")
            ),
            clips=tuple(
                ExportClip.from_dict(_object(item, "clip"))
                for item in _array(data.get("clips"), "clips")
            ),
        )


@dataclass(frozen=True)
class ExportMaterialProbe:
    container: str
    video_codec: str | None
    width: int | None
    height: int | None
    fps: float | None
    duration_us: int
    audio_codec: str | None
    audio_sample_rate: int | None
    audio_channels: int | None
    audio_duration_us: int | None
    ok: bool = True
    error: str = ""


@dataclass(frozen=True)
class ExportMaterialSnapshot:
    material_id: str
    path: str
    normalized_path: str
    size_bytes: int
    mtime_ns: int
    container: str
    video_codec: str | None
    width: int | None
    height: int | None
    fps: float | None
    duration_us: int
    audio_codec: str | None
    audio_sample_rate: int | None
    audio_channels: int | None
    audio_duration_us: int | None
    exists: bool = True

    def __post_init__(self) -> None:
        if not self.exists:
            raise ExportValidationError("export material must exist")
        if self.size_bytes < 0 or self.mtime_ns < 0:
            raise ExportValidationError("invalid material file identity")
        if self.duration_us <= 0:
            raise ExportValidationError("material duration must be positive")
        if self.video_codec is None and self.audio_codec is None:
            raise ExportValidationError("material must contain video or audio")

    @property
    def fingerprint(self) -> str:
        payload = {
            "normalized_path": self.normalized_path,
            "size_bytes": self.size_bytes,
            "mtime_ns": self.mtime_ns,
            "container": self.container,
            "video_codec": self.video_codec,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "duration_us": self.duration_us,
            "audio_codec": self.audio_codec,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_channels": self.audio_channels,
            "audio_duration_us": self.audio_duration_us,
        }
        return _sha256(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "path": self.path,
            "normalized_path": self.normalized_path,
            "size_bytes": self.size_bytes,
            "mtime_ns": self.mtime_ns,
            "container": self.container,
            "video_codec": self.video_codec,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "duration_us": self.duration_us,
            "audio_codec": self.audio_codec,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_channels": self.audio_channels,
            "audio_duration_us": self.audio_duration_us,
            "exists": self.exists,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportMaterialSnapshot:
        snapshot = cls(
            material_id=_required_text(data, "material_id"),
            path=_required_text(data, "path"),
            normalized_path=_required_text(data, "normalized_path"),
            size_bytes=_required_int(data, "size_bytes"),
            mtime_ns=_required_int(data, "mtime_ns"),
            container=_required_text(data, "container"),
            video_codec=_optional_text(data.get("video_codec")),
            width=_nullable_int(data.get("width")),
            height=_nullable_int(data.get("height")),
            fps=_nullable_float(data.get("fps")),
            duration_us=_required_int(data, "duration_us"),
            audio_codec=_optional_text(data.get("audio_codec")),
            audio_sample_rate=_nullable_int(data.get("audio_sample_rate")),
            audio_channels=_nullable_int(data.get("audio_channels")),
            audio_duration_us=_nullable_int(data.get("audio_duration_us")),
            exists=bool(data.get("exists", True)),
        )
        expected = str(data.get("fingerprint") or snapshot.fingerprint)
        if expected != snapshot.fingerprint:
            raise ExportValidationError("material fingerprint mismatch")
        return snapshot


@dataclass(frozen=True)
class RenderPolicy:
    video_rule: str = "highest_track_full_frame"
    audio_rule: str = "equal_active_gain_with_limiter"
    blank_rule: str = "black"

    def to_dict(self) -> dict[str, str]:
        return {
            "video_rule": self.video_rule,
            "audio_rule": self.audio_rule,
            "blank_rule": self.blank_rule,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RenderPolicy:
        policy = cls(
            video_rule=_required_text(data, "video_rule"),
            audio_rule=_required_text(data, "audio_rule"),
            blank_rule=_required_text(data, "blank_rule"),
        )
        if policy != cls():
            raise ExportValidationError("unsupported export render policy")
        return policy


@dataclass(frozen=True)
class ExportPlan:
    plan_schema_version: int
    plan_id: str
    plan_hash: str
    created_at: str
    project: ExportProjectSnapshot
    timeline: ExportTimelineSnapshot
    materials: tuple[ExportMaterialSnapshot, ...]
    render_policy: RenderPolicy
    output: ExportOutputSpec

    def __post_init__(self) -> None:
        if self.plan_schema_version != PLAN_SCHEMA_VERSION:
            raise ExportValidationError(
                f"unsupported export plan schema: {self.plan_schema_version}"
            )
        if not self.plan_id.strip() or not self.created_at.strip():
            raise ExportValidationError("plan identity is required")
        referenced = {clip.material_id for clip in self.timeline.clips}
        available = {material.material_id for material in self.materials}
        if referenced != available:
            raise ExportValidationError(
                "export plan materials must exactly match referenced materials"
            )
        if len(available) != len(self.materials):
            raise ExportValidationError("duplicate export material id")
        if self.plan_hash != self.compute_hash():
            raise ExportValidationError("export plan hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        plan_id: str,
        created_at: str,
        project: ExportProjectSnapshot,
        timeline: ExportTimelineSnapshot,
        materials: tuple[ExportMaterialSnapshot, ...],
        render_policy: RenderPolicy,
        output: ExportOutputSpec,
    ) -> ExportPlan:
        payload = _render_payload(
            project=project,
            timeline=timeline,
            materials=materials,
            render_policy=render_policy,
            output=output,
        )
        return cls(
            plan_schema_version=PLAN_SCHEMA_VERSION,
            plan_id=plan_id,
            plan_hash=_sha256(payload),
            created_at=created_at,
            project=project,
            timeline=timeline,
            materials=materials,
            render_policy=render_policy,
            output=output,
        )

    def compute_hash(self) -> str:
        return _sha256(
            _render_payload(
                project=self.project,
                timeline=self.timeline,
                materials=self.materials,
                render_policy=self.render_policy,
                output=self.output,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_schema_version": self.plan_schema_version,
            "plan_id": self.plan_id,
            "plan_hash": self.plan_hash,
            "created_at": self.created_at,
            "project": self.project.to_dict(),
            "timeline": self.timeline.to_dict(),
            "materials": [material.to_dict() for material in self.materials],
            "render_policy": self.render_policy.to_dict(),
            "output": self.output.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportPlan:
        version = _required_int(data, "plan_schema_version")
        if version != PLAN_SCHEMA_VERSION:
            raise ExportValidationError(
                f"unsupported export plan schema: {version}"
            )
        return cls(
            plan_schema_version=version,
            plan_id=_required_text(data, "plan_id"),
            plan_hash=_required_text(data, "plan_hash"),
            created_at=_required_text(data, "created_at"),
            project=ExportProjectSnapshot.from_dict(
                _object(data.get("project"), "project")
            ),
            timeline=ExportTimelineSnapshot.from_dict(
                _object(data.get("timeline"), "timeline")
            ),
            materials=tuple(
                ExportMaterialSnapshot.from_dict(_object(item, "material"))
                for item in _array(data.get("materials"), "materials")
            ),
            render_policy=RenderPolicy.from_dict(
                _object(data.get("render_policy"), "render_policy")
            ),
            output=ExportOutputSpec.from_dict(
                _object(data.get("output"), "output")
            ),
        )


@dataclass(frozen=True)
class ExportPlanRequest:
    project_path: str
    width: int
    height: int
    fps: int
    output_directory: str
    filename: str
    overwrite_mode: OverwriteMode = OverwriteMode.DENY
    accept_safe_suffix: bool = True
    project_saved: bool = True
    save_pending: bool = False
    external_conflict: bool = False
    incomplete_job_count: int = 0
    reserved_target_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExportPlanIssue:
    code: str
    message: str
    context: dict[str, str | int | float | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class ExportPlanBuildResult:
    ok: bool
    plan: ExportPlan | None = None
    errors: tuple[ExportPlanIssue, ...] = ()
    warnings: tuple[ExportPlanIssue, ...] = ()
    suggested_filename: str | None = None


def _validate_output_dimensions(width: int, height: int, fps: int) -> None:
    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or width <= 0
        or height <= 0
        or width % 2
        or height % 2
    ):
        raise ExportValidationError("output dimensions must be positive even integers")
    if width > MAX_CANVAS_WIDTH or height > MAX_CANVAS_HEIGHT:
        raise ExportValidationError("output canvas must not exceed 3840x2160")
    if fps not in SUPPORTED_FPS:
        raise ExportValidationError("output fps must be 30, 60, or 120")
    if fps == 120 and (
        width > MAX_120_FPS_WIDTH or height > MAX_120_FPS_HEIGHT
    ):
        raise ExportValidationError(
            "120 fps output canvas must not exceed 1920x1080"
        )


def _render_payload(
    *,
    project: ExportProjectSnapshot,
    timeline: ExportTimelineSnapshot,
    materials: tuple[ExportMaterialSnapshot, ...],
    render_policy: RenderPolicy,
    output: ExportOutputSpec,
) -> dict[str, Any]:
    return {
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "project": project.to_dict(),
        "timeline": timeline.to_dict(),
        "materials": [material.to_dict() for material in materials],
        "render_policy": render_policy.to_dict(),
        "output": output.to_dict(),
    }


def _sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _required_text(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ExportValidationError(f"{key} is required")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExportValidationError(f"{key} must be an integer")
    return value


def _optional_int(value: Any, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExportValidationError("value must be an integer")
    return value


def _nullable_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExportValidationError("value must be an integer")
    return value


def _nullable_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExportValidationError("value must be numeric")
    return float(value)


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExportValidationError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ExportValidationError(f"{label} must be an array")
    return value
