"""QuickRec v1.9.3 时间线剪辑候选与全局波纹规则。"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import (
    Timeline,
    TimelineClip,
    TimelineTrack,
    new_clip_id,
    new_link_group_id,
    seconds_to_microseconds,
    upgrade_timeline_for_v2_edit,
    validate_timeline,
)

_VIDEO_FALLBACK_MINIMUM_US = 100_000
_AUDIO_MINIMUM_US = 20_000


@dataclass(frozen=True)
class TimelineEditConflict:
    code: str
    message: str
    track_ids: tuple[str, ...] = ()
    clip_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimelineEditImpact:
    operation: str
    delta_us: int = 0
    range_start_us: int | None = None
    range_end_us: int | None = None
    insert_at_us: int | None = None
    timeline_duration_before_us: int = 0
    timeline_duration_after_us: int = 0
    target_clip_ids: tuple[str, ...] = ()
    ripple_clip_ids: tuple[str, ...] = ()
    affected_track_ids: tuple[str, ...] = ()
    affected_clip_ids: tuple[str, ...] = ()
    affected_link_group_ids: tuple[str, ...] = ()
    associated_clip_count: int = 0


@dataclass(frozen=True)
class TimelineEditCandidate:
    operation: str
    valid: bool
    source_fingerprint: str
    timeline: Timeline | None
    impact: TimelineEditImpact
    conflicts: tuple[TimelineEditConflict, ...] = ()
    selected_clip_ids: tuple[str, ...] = ()
    normalized_source_start_us: int | None = None
    normalized_source_end_us: int | None = None
    normalized_playhead_us: int | None = None


@dataclass(frozen=True)
class _TargetContext:
    timeline: Timeline
    selected: TimelineClip
    targets: tuple[TimelineClip, ...]
    material: ProjectMaterialRef
    tracks: dict[str, TimelineTrack]
    fps: Decimal | None
    minimum_duration_us: int
    source_fingerprint: str


class TimelineEditService:
    """在正式状态之外计算可验证的剪辑候选。"""

    def __init__(
        self,
        *,
        clip_id_factory: Callable[[], str] = new_clip_id,
        link_group_id_factory: Callable[[], str] = new_link_group_id,
    ) -> None:
        self._clip_id_factory = clip_id_factory
        self._link_group_id_factory = link_group_id_factory

    def trim(
        self,
        timeline: Timeline,
        project: ProjectFile,
        clip_id: str,
        *,
        source_start_us: int,
        source_end_us: int,
    ) -> TimelineEditCandidate:
        operation = "trim"
        prepared = self._prepare(operation, timeline, project, clip_id)
        if isinstance(prepared, TimelineEditCandidate):
            return prepared
        context = prepared

        try:
            requested_start = _integer_microseconds(
                source_start_us,
                "source_start_us",
            )
            requested_end = _integer_microseconds(
                source_end_us,
                "source_end_us",
            )
        except ValueError as exc:
            return self._invalid(context, operation, "invalid_source_range", str(exc))

        material_duration = _material_duration_us(context.material)
        normalized_start = _normalize_media_boundary(
            requested_start,
            fps=context.fps,
            material_duration_us=material_duration,
        )
        normalized_end = _normalize_media_boundary(
            requested_end,
            fps=context.fps,
            material_duration_us=material_duration,
        )
        if (
            normalized_start < 0
            or normalized_end > material_duration
            or normalized_end <= normalized_start
        ):
            return self._invalid(
                context,
                operation,
                "invalid_source_range",
                "source range must stay within the material and have positive duration",
                normalized_source_start_us=normalized_start,
                normalized_source_end_us=normalized_end,
            )

        new_duration = normalized_end - normalized_start
        if new_duration < context.minimum_duration_us:
            return self._invalid(
                context,
                operation,
                "minimum_duration",
                f"clip duration must be at least {context.minimum_duration_us} us",
                normalized_source_start_us=normalized_start,
                normalized_source_end_us=normalized_end,
            )

        old_duration = context.selected.timeline_duration_us
        current_source_end = (
            context.selected.source_start_us
            + context.selected.source_duration_us
        )
        if (
            normalized_start == context.selected.source_start_us
            and normalized_end == current_source_end
        ):
            return self._invalid(
                context,
                operation,
                "no_change",
                "trim range does not change the selected clip",
                normalized_source_start_us=normalized_start,
                normalized_source_end_us=normalized_end,
            )

        delta_us = new_duration - old_duration
        target_ids = _clip_ids(context.targets)
        if delta_us < 0:
            range_start_us = context.selected.timeline_start_us + new_duration
            range_end_us = context.selected.timeline_end_us
            insert_at_us = None
            ripple_ids, conflicts = _analyze_delete_ripple(
                context.timeline,
                context.tracks,
                target_ids,
                range_start_us,
                range_end_us,
            )
        elif delta_us > 0:
            range_start_us = None
            range_end_us = None
            insert_at_us = context.selected.timeline_end_us
            ripple_ids, conflicts = _analyze_insert_ripple(
                context.timeline,
                context.tracks,
                target_ids,
                insert_at_us,
            )
        else:
            range_start_us = None
            range_end_us = None
            insert_at_us = None
            ripple_ids = ()
            conflicts = ()

        conflicts = (
            *_locked_target_conflicts(context.targets, context.tracks),
            *conflicts,
        )
        impact = _impact(
            operation,
            context.timeline,
            target_ids=target_ids,
            ripple_ids=ripple_ids,
            delta_us=delta_us,
            range_start_us=range_start_us,
            range_end_us=range_end_us,
            insert_at_us=insert_at_us,
            associated_clip_count=len(target_ids),
        )
        if conflicts:
            return TimelineEditCandidate(
                operation,
                False,
                context.source_fingerprint,
                None,
                impact,
                _unique_conflicts(conflicts),
                normalized_source_start_us=normalized_start,
                normalized_source_end_us=normalized_end,
            )

        candidate = copy.deepcopy(context.timeline)
        candidate_targets = {
            clip.clip_id: clip
            for clip in candidate.clips
            if clip.clip_id in target_ids
        }
        for clip in candidate_targets.values():
            clip.source_start_us = normalized_start
            clip.source_duration_us = new_duration
            clip.timeline_duration_us = new_duration
        if delta_us:
            for clip in candidate.clips:
                if clip.clip_id in ripple_ids:
                    clip.timeline_start_us += delta_us

        return self._validated(
            context,
            operation,
            project,
            candidate,
            impact=_impact(
                operation,
                context.timeline,
                candidate=candidate,
                target_ids=target_ids,
                ripple_ids=ripple_ids,
                delta_us=delta_us,
                range_start_us=range_start_us,
                range_end_us=range_end_us,
                insert_at_us=insert_at_us,
                associated_clip_count=len(target_ids),
            ),
            selected_clip_ids=target_ids,
            normalized_source_start_us=normalized_start,
            normalized_source_end_us=normalized_end,
        )

    def split(
        self,
        timeline: Timeline,
        project: ProjectFile,
        clip_id: str,
        *,
        playhead_us: int,
    ) -> TimelineEditCandidate:
        operation = "split"
        prepared = self._prepare(operation, timeline, project, clip_id)
        if isinstance(prepared, TimelineEditCandidate):
            return prepared
        context = prepared
        target_ids = _clip_ids(context.targets)
        locked = _locked_target_conflicts(context.targets, context.tracks)
        if locked:
            return TimelineEditCandidate(
                operation,
                False,
                context.source_fingerprint,
                None,
                _impact(
                    operation,
                    context.timeline,
                    target_ids=target_ids,
                    associated_clip_count=len(target_ids),
                ),
                locked,
            )

        try:
            requested_playhead = _integer_microseconds(playhead_us, "playhead_us")
        except ValueError as exc:
            return self._invalid(context, operation, "invalid_playhead", str(exc))
        source_at_playhead = (
            context.selected.source_start_us
            + requested_playhead
            - context.selected.timeline_start_us
        )
        material_duration = _material_duration_us(context.material)
        normalized_source = _normalize_media_boundary(
            source_at_playhead,
            fps=context.fps,
            material_duration_us=material_duration,
        )
        left_duration = normalized_source - context.selected.source_start_us
        right_duration = context.selected.source_duration_us - left_duration
        normalized_playhead = context.selected.timeline_start_us + left_duration
        if (
            left_duration < context.minimum_duration_us
            or right_duration < context.minimum_duration_us
        ):
            return self._invalid(
                context,
                operation,
                "minimum_duration",
                "split must leave a legal duration on both sides",
                normalized_playhead_us=normalized_playhead,
            )

        right_link_group_id = (
            self._link_group_id_factory()
            if context.selected.link_group_id is not None
            else None
        )
        right_ids: list[str] = []
        right_by_left_id: dict[str, TimelineClip] = {}
        for target in context.targets:
            right_id = self._clip_id_factory()
            right_ids.append(right_id)
            right_by_left_id[target.clip_id] = TimelineClip(
                clip_id=right_id,
                material_id=target.material_id,
                track_id=target.track_id,
                timeline_start_us=normalized_playhead,
                timeline_duration_us=right_duration,
                source_start_us=normalized_source,
                source_duration_us=right_duration,
                link_group_id=right_link_group_id,
                extensions=copy.deepcopy(target.extensions),
                unknown_fields=copy.deepcopy(target.unknown_fields),
            )

        candidate = copy.deepcopy(context.timeline)
        rebuilt: list[TimelineClip] = []
        for clip in candidate.clips:
            if clip.clip_id not in target_ids:
                rebuilt.append(clip)
                continue
            clip.timeline_duration_us = left_duration
            clip.source_duration_us = left_duration
            rebuilt.append(clip)
            rebuilt.append(copy.deepcopy(right_by_left_id[clip.clip_id]))
        candidate.clips = rebuilt

        affected_ids = (*target_ids, *right_ids)
        return self._validated(
            context,
            operation,
            project,
            candidate,
            impact=_impact(
                operation,
                context.timeline,
                candidate=candidate,
                target_ids=affected_ids,
                associated_clip_count=len(target_ids),
            ),
            selected_clip_ids=tuple(right_ids),
            normalized_playhead_us=normalized_playhead,
        )

    def ripple_delete(
        self,
        timeline: Timeline,
        project: ProjectFile,
        clip_id: str,
    ) -> TimelineEditCandidate:
        operation = "ripple_delete"
        prepared = self._prepare(operation, timeline, project, clip_id)
        if isinstance(prepared, TimelineEditCandidate):
            return prepared
        context = prepared
        target_ids = _clip_ids(context.targets)
        range_start_us = context.selected.timeline_start_us
        range_end_us = context.selected.timeline_end_us
        ripple_ids, conflicts = _analyze_delete_ripple(
            context.timeline,
            context.tracks,
            target_ids,
            range_start_us,
            range_end_us,
        )
        conflicts = (
            *_locked_target_conflicts(context.targets, context.tracks),
            *conflicts,
        )
        delta_us = range_start_us - range_end_us
        impact = _impact(
            operation,
            context.timeline,
            target_ids=target_ids,
            ripple_ids=ripple_ids,
            delta_us=delta_us,
            range_start_us=range_start_us,
            range_end_us=range_end_us,
            associated_clip_count=len(target_ids),
        )
        if conflicts:
            return TimelineEditCandidate(
                operation,
                False,
                context.source_fingerprint,
                None,
                impact,
                _unique_conflicts(conflicts),
            )

        candidate = copy.deepcopy(context.timeline)
        candidate.clips = [
            clip
            for clip in candidate.clips
            if clip.clip_id not in target_ids
        ]
        for clip in candidate.clips:
            if clip.clip_id in ripple_ids:
                clip.timeline_start_us += delta_us
        return self._validated(
            context,
            operation,
            project,
            candidate,
            impact=_impact(
                operation,
                context.timeline,
                candidate=candidate,
                target_ids=target_ids,
                ripple_ids=ripple_ids,
                delta_us=delta_us,
                range_start_us=range_start_us,
                range_end_us=range_end_us,
                associated_clip_count=len(target_ids),
            ),
        )

    def _prepare(
        self,
        operation: str,
        timeline: Timeline,
        project: ProjectFile,
        clip_id: str,
    ) -> _TargetContext | TimelineEditCandidate:
        fingerprint = timeline_edit_fingerprint(timeline, project)
        try:
            validate_timeline(timeline, project)
            candidate = upgrade_timeline_for_v2_edit(timeline, project)
            selected = _find_clip(candidate, clip_id)
            targets = _resolve_targets(candidate, selected)
            tracks = {track.track_id: track for track in candidate.tracks}
            material = _find_material(project, selected.material_id)
            fps = _target_fps(targets, tracks, material)
            minimum_duration_us = _minimum_duration_us(
                targets,
                tracks,
                fps,
            )
        except Exception as exc:
            return TimelineEditCandidate(
                operation,
                False,
                fingerprint,
                None,
                _impact(operation, timeline),
                (
                    TimelineEditConflict(
                        "invalid_timeline",
                        str(exc),
                    ),
                ),
            )
        return _TargetContext(
            candidate,
            selected,
            targets,
            material,
            tracks,
            fps,
            minimum_duration_us,
            fingerprint,
        )

    def _invalid(
        self,
        context: _TargetContext,
        operation: str,
        code: str,
        message: str,
        *,
        normalized_source_start_us: int | None = None,
        normalized_source_end_us: int | None = None,
        normalized_playhead_us: int | None = None,
    ) -> TimelineEditCandidate:
        target_ids = _clip_ids(context.targets)
        return TimelineEditCandidate(
            operation,
            False,
            context.source_fingerprint,
            None,
            _impact(
                operation,
                context.timeline,
                target_ids=target_ids,
                associated_clip_count=len(target_ids),
            ),
            (TimelineEditConflict(code, message, clip_ids=target_ids),),
            normalized_source_start_us=normalized_source_start_us,
            normalized_source_end_us=normalized_source_end_us,
            normalized_playhead_us=normalized_playhead_us,
        )

    def _validated(
        self,
        context: _TargetContext,
        operation: str,
        project: ProjectFile,
        candidate: Timeline,
        *,
        impact: TimelineEditImpact,
        selected_clip_ids: tuple[str, ...] = (),
        normalized_source_start_us: int | None = None,
        normalized_source_end_us: int | None = None,
        normalized_playhead_us: int | None = None,
    ) -> TimelineEditCandidate:
        overlaps = _same_track_overlap_conflicts(candidate)
        if overlaps:
            return TimelineEditCandidate(
                operation,
                False,
                context.source_fingerprint,
                None,
                impact,
                overlaps,
                normalized_source_start_us=normalized_source_start_us,
                normalized_source_end_us=normalized_source_end_us,
                normalized_playhead_us=normalized_playhead_us,
            )
        try:
            validate_timeline(candidate, project)
        except Exception as exc:
            return TimelineEditCandidate(
                operation,
                False,
                context.source_fingerprint,
                None,
                impact,
                (
                    TimelineEditConflict(
                        "candidate_invalid",
                        str(exc),
                    ),
                ),
                normalized_source_start_us=normalized_source_start_us,
                normalized_source_end_us=normalized_source_end_us,
                normalized_playhead_us=normalized_playhead_us,
            )
        return TimelineEditCandidate(
            operation,
            True,
            context.source_fingerprint,
            candidate,
            impact,
            selected_clip_ids=selected_clip_ids,
            normalized_source_start_us=normalized_source_start_us,
            normalized_source_end_us=normalized_source_end_us,
            normalized_playhead_us=normalized_playhead_us,
        )


def timeline_edit_fingerprint(
    timeline: Timeline,
    project: ProjectFile,
) -> str:
    """为候选提交生成不包含媒体路径的稳定来源指纹。"""
    materials = sorted(
        (
            {
                "material_id": material.material_id,
                "duration_sec": material.metadata_snapshot.get("duration_sec"),
                "fps": material.metadata_snapshot.get("fps"),
            }
            for material in project.materials
        ),
        key=lambda item: item["material_id"],
    )
    payload = {
        "timeline": timeline.to_dict(),
        "materials": materials,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _analyze_delete_ripple(
    timeline: Timeline,
    tracks: dict[str, TimelineTrack],
    target_ids: tuple[str, ...],
    range_start_us: int,
    range_end_us: int,
) -> tuple[tuple[str, ...], tuple[TimelineEditConflict, ...]]:
    ripple_ids: list[str] = []
    conflicts: list[TimelineEditConflict] = []
    target_set = set(target_ids)
    for clip in timeline.clips:
        if clip.clip_id in target_set:
            continue
        if clip.timeline_start_us >= range_end_us:
            ripple_ids.append(clip.clip_id)
            track = tracks[clip.track_id]
            if track.locked:
                conflicts.append(
                    TimelineEditConflict(
                        "locked_ripple_track",
                        f"locked track would move: {track.name}",
                        (track.track_id,),
                        (clip.clip_id,),
                    )
                )
            continue
        if (
            clip.timeline_start_us < range_end_us
            and clip.timeline_end_us > range_start_us
        ):
            track = tracks[clip.track_id]
            conflicts.append(
                TimelineEditConflict(
                    "crosses_delete_range",
                    f"clip crosses the ripple delete range: {clip.clip_id}",
                    (track.track_id,),
                    (clip.clip_id,),
                )
            )
    return tuple(ripple_ids), _unique_conflicts(conflicts)


def _analyze_insert_ripple(
    timeline: Timeline,
    tracks: dict[str, TimelineTrack],
    target_ids: tuple[str, ...],
    insert_at_us: int,
) -> tuple[tuple[str, ...], tuple[TimelineEditConflict, ...]]:
    ripple_ids: list[str] = []
    conflicts: list[TimelineEditConflict] = []
    target_set = set(target_ids)
    for clip in timeline.clips:
        if clip.clip_id in target_set:
            continue
        if clip.timeline_start_us >= insert_at_us:
            ripple_ids.append(clip.clip_id)
            track = tracks[clip.track_id]
            if track.locked:
                conflicts.append(
                    TimelineEditConflict(
                        "locked_ripple_track",
                        f"locked track would move: {track.name}",
                        (track.track_id,),
                        (clip.clip_id,),
                    )
                )
            continue
        if clip.timeline_start_us < insert_at_us < clip.timeline_end_us:
            track = tracks[clip.track_id]
            conflicts.append(
                TimelineEditConflict(
                    "crosses_insert_point",
                    f"clip crosses the ripple insert point: {clip.clip_id}",
                    (track.track_id,),
                    (clip.clip_id,),
                )
            )
    return tuple(ripple_ids), _unique_conflicts(conflicts)


def _locked_target_conflicts(
    targets: tuple[TimelineClip, ...],
    tracks: dict[str, TimelineTrack],
) -> tuple[TimelineEditConflict, ...]:
    conflicts = []
    for clip in targets:
        track = tracks[clip.track_id]
        if track.locked:
            conflicts.append(
                TimelineEditConflict(
                    "locked_target_track",
                    f"selected clip is on a locked track: {track.name}",
                    (track.track_id,),
                    (clip.clip_id,),
                )
            )
    return _unique_conflicts(conflicts)


def _same_track_overlap_conflicts(
    timeline: Timeline,
) -> tuple[TimelineEditConflict, ...]:
    conflicts: list[TimelineEditConflict] = []
    by_track: dict[str, list[TimelineClip]] = {}
    for clip in timeline.clips:
        by_track.setdefault(clip.track_id, []).append(clip)
    for track_id, clips in by_track.items():
        ordered = sorted(
            clips,
            key=lambda item: (item.timeline_start_us, item.clip_id),
        )
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.timeline_start_us < previous.timeline_end_us:
                conflicts.append(
                    TimelineEditConflict(
                        "same_track_overlap",
                        f"clips overlap on track {track_id}",
                        (track_id,),
                        (previous.clip_id, current.clip_id),
                    )
                )
    return _unique_conflicts(conflicts)


def _impact(
    operation: str,
    before: Timeline,
    *,
    candidate: Timeline | None = None,
    target_ids: tuple[str, ...] = (),
    ripple_ids: tuple[str, ...] = (),
    delta_us: int = 0,
    range_start_us: int | None = None,
    range_end_us: int | None = None,
    insert_at_us: int | None = None,
    associated_clip_count: int = 0,
) -> TimelineEditImpact:
    affected_ids = _ordered_unique((*target_ids, *ripple_ids))
    clips_by_id = {clip.clip_id: clip for clip in before.clips}
    if candidate is not None:
        for clip in candidate.clips:
            clips_by_id.setdefault(clip.clip_id, clip)
    affected_clips = [
        clips_by_id[clip_id]
        for clip_id in affected_ids
        if clip_id in clips_by_id
    ]
    affected_track_ids = _ordered_unique(
        clip.track_id for clip in affected_clips
    )
    affected_link_group_ids = _ordered_unique(
        clip.link_group_id
        for clip in affected_clips
        if clip.link_group_id is not None
    )
    before_duration = _timeline_duration(before)
    predicted_after = max(0, before_duration + delta_us)
    return TimelineEditImpact(
        operation=operation,
        delta_us=delta_us,
        range_start_us=range_start_us,
        range_end_us=range_end_us,
        insert_at_us=insert_at_us,
        timeline_duration_before_us=before_duration,
        timeline_duration_after_us=(
            _timeline_duration(candidate)
            if candidate is not None
            else predicted_after
        ),
        target_clip_ids=target_ids,
        ripple_clip_ids=ripple_ids,
        affected_track_ids=affected_track_ids,
        affected_clip_ids=affected_ids,
        affected_link_group_ids=affected_link_group_ids,
        associated_clip_count=associated_clip_count,
    )


def _resolve_targets(
    timeline: Timeline,
    selected: TimelineClip,
) -> tuple[TimelineClip, ...]:
    if selected.link_group_id is None:
        return (selected,)
    targets = tuple(
        clip
        for clip in timeline.clips
        if clip.link_group_id == selected.link_group_id
    )
    if len(targets) != 2:
        raise ValueError(
            f"link group is not editable: {selected.link_group_id}"
        )
    return targets


def _target_fps(
    targets: tuple[TimelineClip, ...],
    tracks: dict[str, TimelineTrack],
    material: ProjectMaterialRef,
) -> Decimal | None:
    if not any(tracks[clip.track_id].kind == "video" for clip in targets):
        return None
    raw = material.metadata_snapshot.get("fps")
    if isinstance(raw, bool):
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not value.is_finite() or value <= 0 or value > 1000:
        return None
    return value


def _minimum_duration_us(
    targets: tuple[TimelineClip, ...],
    tracks: dict[str, TimelineTrack],
    fps: Decimal | None,
) -> int:
    if any(tracks[clip.track_id].kind == "video" for clip in targets):
        if fps is None:
            return _VIDEO_FALLBACK_MINIMUM_US
        return max(
            1,
            int(
                (Decimal(1_000_000) / fps).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
            ),
        )
    return _AUDIO_MINIMUM_US


def _normalize_media_boundary(
    value_us: int,
    *,
    fps: Decimal | None,
    material_duration_us: int,
) -> int:
    if fps is None or value_us in (0, material_duration_us):
        return value_us
    frame_index = (
        Decimal(value_us) * fps / Decimal(1_000_000)
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    normalized = int(
        (frame_index * Decimal(1_000_000) / fps).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )
    return max(0, min(normalized, material_duration_us))


def _material_duration_us(material: ProjectMaterialRef) -> int:
    duration = seconds_to_microseconds(
        material.metadata_snapshot.get("duration_sec")
    )
    if duration <= 0:
        raise ValueError(
            f"material duration is unavailable: {material.material_id}"
        )
    return duration


def _find_clip(timeline: Timeline, clip_id: str) -> TimelineClip:
    cleaned = str(clip_id or "").strip()
    for clip in timeline.clips:
        if clip.clip_id == cleaned:
            return clip
    raise ValueError(f"clip does not exist: {cleaned}")


def _find_material(
    project: ProjectFile,
    material_id: str,
) -> ProjectMaterialRef:
    for material in project.materials:
        if material.material_id == material_id:
            return material
    raise ValueError(f"material does not exist: {material_id}")


def _integer_microseconds(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _clip_ids(clips: tuple[TimelineClip, ...]) -> tuple[str, ...]:
    return tuple(clip.clip_id for clip in clips)


def _timeline_duration(timeline: Timeline) -> int:
    return max((clip.timeline_end_us for clip in timeline.clips), default=0)


def _ordered_unique(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values))


def _unique_conflicts(
    conflicts,
) -> tuple[TimelineEditConflict, ...]:
    unique: dict[
        tuple[str, tuple[str, ...], tuple[str, ...]],
        TimelineEditConflict,
    ] = {}
    for conflict in conflicts:
        key = (
            conflict.code,
            conflict.track_ids,
            conflict.clip_ids,
        )
        unique.setdefault(key, conflict)
    return tuple(unique.values())
