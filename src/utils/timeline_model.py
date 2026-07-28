"""QuickRec Full 时间线纯数据模型、schema 与兼容边界。"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal

from utils.project_store import ProjectFile

TIMELINE_EXTENSION_KEY = "quickrec.timeline"
TIMELINE_SCHEMA_VERSION = 1
TIMELINE_TIME_UNIT = "microseconds"
MAX_TRACKS_PER_KIND = 8

TrackKind = Literal["video", "audio"]
_TRACK_KINDS: tuple[TrackKind, TrackKind] = ("video", "audio")
_TIMELINE_NAMESPACE = uuid.UUID("14e4e357-41f6-4c1d-9bde-3cb67c8e13ad")


class TimelineValidationError(ValueError):
    """时间线 schema 或结构校验失败。"""


class UnsupportedTimelineSchemaError(TimelineValidationError):
    """时间线扩展使用当前程序不支持的新版本。"""


@dataclass
class TimelineTrack:
    track_id: str
    kind: TrackKind | str
    name: str
    order: int
    extensions: dict[str, Any] = field(default_factory=dict)
    unknown_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineTrack:
        known = {"track_id", "kind", "name", "order", "extensions"}
        return cls(
            track_id=_required_text(data, "track_id"),
            kind=_required_text(data, "kind"),
            name=_required_text(data, "name"),
            order=_required_int(data, "order"),
            extensions=_object(data.get("extensions"), "track.extensions"),
            unknown_fields=_unknown_fields(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = copy.deepcopy(self.unknown_fields)
        payload.update(
            {
                "track_id": self.track_id,
                "kind": self.kind,
                "name": self.name,
                "order": self.order,
                "extensions": copy.deepcopy(self.extensions),
            }
        )
        return payload


@dataclass
class TimelineClip:
    clip_id: str
    material_id: str
    track_id: str
    timeline_start_us: int
    timeline_duration_us: int
    source_start_us: int
    source_duration_us: int
    link_group_id: str | None = None
    extensions: dict[str, Any] = field(default_factory=dict)
    unknown_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineClip:
        known = {
            "clip_id",
            "material_id",
            "track_id",
            "timeline_start_us",
            "timeline_duration_us",
            "source_start_us",
            "source_duration_us",
            "link_group_id",
            "extensions",
        }
        return cls(
            clip_id=_required_text(data, "clip_id"),
            material_id=_required_text(data, "material_id"),
            track_id=_required_text(data, "track_id"),
            timeline_start_us=_required_int(data, "timeline_start_us"),
            timeline_duration_us=_required_int(data, "timeline_duration_us"),
            source_start_us=_required_int(data, "source_start_us"),
            source_duration_us=_required_int(data, "source_duration_us"),
            link_group_id=_optional_text(data.get("link_group_id")),
            extensions=_object(data.get("extensions"), "clip.extensions"),
            unknown_fields=_unknown_fields(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = copy.deepcopy(self.unknown_fields)
        payload.update(
            {
                "clip_id": self.clip_id,
                "material_id": self.material_id,
                "track_id": self.track_id,
                "timeline_start_us": self.timeline_start_us,
                "timeline_duration_us": self.timeline_duration_us,
                "source_start_us": self.source_start_us,
                "source_duration_us": self.source_duration_us,
                "link_group_id": self.link_group_id,
                "extensions": copy.deepcopy(self.extensions),
            }
        )
        return payload

    @property
    def timeline_end_us(self) -> int:
        return self.timeline_start_us + self.timeline_duration_us


@dataclass
class Timeline:
    timeline_id: str
    tracks: list[TimelineTrack]
    clips: list[TimelineClip] = field(default_factory=list)
    schema_version: int = TIMELINE_SCHEMA_VERSION
    time_unit: str = TIMELINE_TIME_UNIT
    extensions: dict[str, Any] = field(default_factory=dict)
    unknown_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Timeline:
        schema_version = _required_int(data, "schema_version")
        if schema_version != TIMELINE_SCHEMA_VERSION:
            raise UnsupportedTimelineSchemaError(
                f"unsupported timeline schema: {schema_version}"
            )
        raw_tracks = _array(data.get("tracks"), "tracks")
        raw_clips = _array(data.get("clips"), "clips")
        known = {
            "schema_version",
            "time_unit",
            "timeline_id",
            "tracks",
            "clips",
            "extensions",
        }
        return cls(
            timeline_id=_required_text(data, "timeline_id"),
            tracks=[
                TimelineTrack.from_dict(_entry_object(item, "track"))
                for item in raw_tracks
            ],
            clips=[
                TimelineClip.from_dict(_entry_object(item, "clip"))
                for item in raw_clips
            ],
            schema_version=schema_version,
            time_unit=_required_text(data, "time_unit"),
            extensions=_object(data.get("extensions"), "timeline.extensions"),
            unknown_fields=_unknown_fields(data, known),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = copy.deepcopy(self.unknown_fields)
        payload.update(
            {
                "schema_version": self.schema_version,
                "time_unit": self.time_unit,
                "timeline_id": self.timeline_id,
                "tracks": [track.to_dict() for track in self.tracks],
                "clips": [clip.to_dict() for clip in self.clips],
                "extensions": copy.deepcopy(self.extensions),
            }
        )
        return payload


@dataclass(frozen=True)
class TimelineLoadResult:
    ok: bool
    status: str
    timeline: Timeline | None = None
    persisted: bool = False
    read_only: bool = False
    error: str = ""
    raw_extension: dict[str, Any] | None = None


def create_empty_timeline(project_id: str) -> Timeline:
    """为旧项目建立确定性内存时间线，查看本身不会触发写盘。"""
    cleaned_project_id = str(project_id or "").strip()
    if not cleaned_project_id:
        raise TimelineValidationError("project_id is required")
    timeline_id = _deterministic_id("timeline", cleaned_project_id)
    return Timeline(
        timeline_id=timeline_id,
        tracks=[
            TimelineTrack(
                _deterministic_id("video-track", cleaned_project_id),
                "video",
                "视频 1",
                0,
            ),
            TimelineTrack(
                _deterministic_id("audio-track", cleaned_project_id),
                "audio",
                "音频 1",
                0,
            ),
        ],
    )


def new_timeline_id() -> str:
    return _random_id("timeline")


def new_track_id() -> str:
    return _random_id("track")


def new_clip_id() -> str:
    return _random_id("clip")


def new_link_group_id() -> str:
    return _random_id("link")


def load_project_timeline(project: ProjectFile) -> TimelineLoadResult:
    """只解析时间线扩展；错误不会让项目或素材本身失效。"""
    if TIMELINE_EXTENSION_KEY not in project.extensions:
        return TimelineLoadResult(
            True,
            "empty",
            create_empty_timeline(project.project_id),
            persisted=False,
        )

    raw_value = project.extensions[TIMELINE_EXTENSION_KEY]
    if not isinstance(raw_value, dict):
        return TimelineLoadResult(
            False,
            "corrupt",
            persisted=True,
            read_only=True,
            error="timeline extension must be an object",
        )
    raw = copy.deepcopy(raw_value)
    schema_version = raw.get("schema_version")
    if (
        isinstance(schema_version, int)
        and not isinstance(schema_version, bool)
        and schema_version != TIMELINE_SCHEMA_VERSION
    ):
        return TimelineLoadResult(
            False,
            "unsupported",
            persisted=True,
            read_only=True,
            error=f"unsupported timeline schema: {schema_version}",
            raw_extension=raw,
        )

    try:
        timeline = Timeline.from_dict(raw)
        validate_timeline(timeline, project)
    except UnsupportedTimelineSchemaError as exc:
        return TimelineLoadResult(
            False,
            "unsupported",
            persisted=True,
            read_only=True,
            error=str(exc),
            raw_extension=raw,
        )
    except Exception as exc:
        return TimelineLoadResult(
            False,
            "corrupt",
            persisted=True,
            read_only=True,
            error=str(exc),
            raw_extension=raw,
        )
    return TimelineLoadResult(
        True,
        "ready",
        timeline,
        persisted=True,
        raw_extension=raw,
    )


def serialize_timeline(timeline: Timeline, project: ProjectFile) -> dict[str, Any]:
    validate_timeline(timeline, project)
    return timeline.to_dict()


def with_project_timeline(project: ProjectFile, timeline: Timeline) -> ProjectFile:
    """返回带有已校验时间线的候选项目，不修改调用方对象。"""
    candidate = copy.deepcopy(project)
    candidate.extensions[TIMELINE_EXTENSION_KEY] = serialize_timeline(
        timeline,
        project,
    )
    return candidate


def validate_timeline(timeline: Timeline, project: ProjectFile) -> None:
    if not str(timeline.timeline_id or "").strip():
        raise TimelineValidationError("timeline_id is required")
    if timeline.schema_version != TIMELINE_SCHEMA_VERSION:
        raise UnsupportedTimelineSchemaError(
            f"unsupported timeline schema: {timeline.schema_version}"
        )
    if timeline.time_unit != TIMELINE_TIME_UNIT:
        raise TimelineValidationError(
            f"time_unit must be {TIMELINE_TIME_UNIT}"
        )

    tracks_by_id = _validate_tracks(timeline.tracks)
    material_durations = _material_durations(project)
    _validate_clips(timeline.clips, tracks_by_id, material_durations)


def seconds_to_microseconds(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("seconds must be a finite non-negative number")
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("seconds must be a finite non-negative number") from exc
    if not decimal_value.is_finite() or decimal_value < 0:
        raise ValueError("seconds must be a finite non-negative number")
    return int(
        (decimal_value * Decimal(1_000_000)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def microseconds_to_display(value: int) -> str:
    microseconds = _strict_int(value, "microseconds")
    if microseconds < 0:
        raise ValueError("microseconds must be non-negative")
    total_ms = (microseconds + 500) // 1000
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def _validate_tracks(
    tracks: list[TimelineTrack],
) -> dict[str, TimelineTrack]:
    tracks_by_id: dict[str, TimelineTrack] = {}
    by_kind: dict[str, list[TimelineTrack]] = {kind: [] for kind in _TRACK_KINDS}
    for track in tracks:
        track_id = str(track.track_id or "").strip()
        if not track_id:
            raise TimelineValidationError("track_id is required")
        if track_id in tracks_by_id:
            raise TimelineValidationError(f"duplicate track_id: {track_id}")
        if track.kind not in _TRACK_KINDS:
            raise TimelineValidationError(f"unsupported track kind: {track.kind}")
        if not str(track.name or "").strip():
            raise TimelineValidationError(f"track name is required: {track_id}")
        order = _strict_int(track.order, "track order")
        if order < 0:
            raise TimelineValidationError("track order must be non-negative")
        tracks_by_id[track_id] = track
        by_kind[track.kind].append(track)

    for kind in _TRACK_KINDS:
        kind_tracks = by_kind[kind]
        if len(kind_tracks) < 1:
            raise TimelineValidationError(
                f"{kind} tracks must contain at least one track"
            )
        if len(kind_tracks) > MAX_TRACKS_PER_KIND:
            raise TimelineValidationError(
                f"{kind} tracks may contain at most {MAX_TRACKS_PER_KIND} tracks"
            )
        orders = sorted(_strict_int(track.order, "track order") for track in kind_tracks)
        if orders != list(range(len(kind_tracks))):
            raise TimelineValidationError(
                f"{kind} track order must be continuous from zero"
            )
    return tracks_by_id


def _validate_clips(
    clips: list[TimelineClip],
    tracks_by_id: dict[str, TimelineTrack],
    material_durations: dict[str, int],
) -> None:
    clips_by_id: dict[str, TimelineClip] = {}
    clips_by_track: dict[str, list[TimelineClip]] = {}
    link_groups: dict[str, list[TimelineClip]] = {}
    for clip in clips:
        clip_id = str(clip.clip_id or "").strip()
        if not clip_id:
            raise TimelineValidationError("clip_id is required")
        if clip_id in clips_by_id:
            raise TimelineValidationError(f"duplicate clip_id: {clip_id}")
        clips_by_id[clip_id] = clip

        if clip.track_id not in tracks_by_id:
            raise TimelineValidationError(
                f"clip references missing track_id: {clip.track_id}"
            )
        if clip.material_id not in material_durations:
            raise TimelineValidationError(
                f"clip references missing material_id: {clip.material_id}"
            )
        timeline_start = _strict_int(
            clip.timeline_start_us,
            "timeline_start_us",
        )
        timeline_duration = _strict_int(
            clip.timeline_duration_us,
            "timeline_duration_us",
        )
        source_start = _strict_int(clip.source_start_us, "source_start_us")
        source_duration = _strict_int(
            clip.source_duration_us,
            "source_duration_us",
        )
        if timeline_start < 0:
            raise TimelineValidationError(
                "timeline_start_us must be non-negative"
            )
        if timeline_duration <= 0:
            raise TimelineValidationError(
                "timeline_duration_us must be greater than zero"
            )
        if source_start != 0:
            raise TimelineValidationError(
                "source_start_us must be zero in timeline schema v1"
            )
        if source_duration <= 0:
            raise TimelineValidationError(
                "source_duration_us must be greater than zero"
            )
        if timeline_duration != source_duration:
            raise TimelineValidationError(
                "timeline duration must match source duration in schema v1"
            )
        material_duration = material_durations[clip.material_id]
        if source_start + source_duration != material_duration:
            raise TimelineValidationError(
                "source duration must match the full material duration"
            )

        clips_by_track.setdefault(clip.track_id, []).append(clip)
        if clip.link_group_id:
            link_groups.setdefault(clip.link_group_id, []).append(clip)

    for track_id, track_clips in clips_by_track.items():
        ordered = sorted(
            track_clips,
            key=lambda item: (item.timeline_start_us, item.clip_id),
        )
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.timeline_start_us < previous.timeline_end_us:
                raise TimelineValidationError(
                    f"clips overlap on track {track_id}: "
                    f"{previous.clip_id}, {current.clip_id}"
                )

    for link_group_id, members in link_groups.items():
        kinds = [tracks_by_id[item.track_id].kind for item in members]
        if len(members) != 2 or kinds.count("video") != 1 or kinds.count("audio") != 1:
            raise TimelineValidationError(
                f"link group {link_group_id} must contain one video "
                "and one audio clip"
            )
        first, second = members
        if first.material_id != second.material_id:
            raise TimelineValidationError(
                f"link group {link_group_id} must reference one material"
            )
        if first.timeline_start_us != second.timeline_start_us:
            raise TimelineValidationError(
                f"link group {link_group_id} members must have the same timeline start"
            )
        if (
            first.timeline_duration_us != second.timeline_duration_us
            or first.source_start_us != second.source_start_us
            or first.source_duration_us != second.source_duration_us
        ):
            raise TimelineValidationError(
                f"link group {link_group_id} members must have matching durations"
            )


def _material_durations(project: ProjectFile) -> dict[str, int]:
    durations: dict[str, int] = {}
    for material in project.materials:
        if material.material_id in durations:
            raise TimelineValidationError(
                f"duplicate project material_id: {material.material_id}"
            )
        raw_duration = material.metadata_snapshot.get("duration_sec")
        try:
            duration = seconds_to_microseconds(raw_duration)
        except ValueError as exc:
            raise TimelineValidationError(
                f"material duration is unavailable: {material.material_id}"
            ) from exc
        if duration <= 0:
            raise TimelineValidationError(
                f"material duration must be positive: {material.material_id}"
            )
        durations[material.material_id] = duration
    return durations


def _deterministic_id(label: str, project_id: str) -> str:
    value = uuid.uuid5(_TIMELINE_NAMESPACE, f"{project_id}:{label}")
    return f"{label}-{value.hex}"


def _random_id(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex}"


def _required_text(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise TimelineValidationError(f"{key} is required")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_int(data: dict[str, Any], key: str) -> int:
    if key not in data:
        raise TimelineValidationError(f"{key} is required")
    return _strict_int(data[key], key)


def _strict_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TimelineValidationError(f"{label} must be an integer")
    return value


def _object(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TimelineValidationError(f"{label} must be an object")
    return copy.deepcopy(value)


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TimelineValidationError(f"{label} must be an array")
    return list(value)


def _entry_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TimelineValidationError(f"{label} entry must be an object")
    return value


def _unknown_fields(
    data: dict[str, Any],
    known_fields: set[str],
) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in data.items()
        if key not in known_fields
    }
