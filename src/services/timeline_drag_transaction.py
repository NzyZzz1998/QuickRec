"""Pure timeline material-drop planning and auto-track transactions."""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from services.timeline_edit_service import timeline_edit_fingerprint
from services.timeline_snap import TimelineSnapResult, snap_timeline_time
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import (
    MAX_TRACKS_PER_KIND,
    Timeline,
    TimelineClip,
    TimelineTrack,
    new_clip_id,
    new_link_group_id,
    new_track_id,
    seconds_to_microseconds,
    validate_timeline,
)


@dataclass(frozen=True)
class TimelineDragCandidate:
    transaction_id: str
    material_id: str
    valid: bool
    source_fingerprint: str
    timeline: Timeline | None
    raw_start_us: int
    start_us: int
    duration_us: int = 0
    has_video: bool = False
    has_audio: bool = False
    hovered_track_id: str = ""
    video_track_id: str | None = None
    audio_track_id: str | None = None
    snap_source: str = "none"
    snap_reference_id: str = ""
    auto_track_kinds: tuple[str, ...] = ()
    created_track_ids: tuple[str, ...] = ()
    created_clip_ids: tuple[str, ...] = ()
    conflict_code: str = ""
    conflict_reason: str = ""

    @classmethod
    def invalid(
        cls,
        *,
        transaction_id: str,
        material_id: str,
        raw_start_us: int,
        start_us: int,
        conflict_code: str,
        conflict_reason: str,
        source_fingerprint: str = "",
        duration_us: int = 0,
        has_video: bool = False,
        has_audio: bool = False,
        hovered_track_id: str = "",
        snap: TimelineSnapResult | None = None,
    ) -> TimelineDragCandidate:
        return cls(
            transaction_id=transaction_id,
            material_id=material_id,
            valid=False,
            source_fingerprint=source_fingerprint,
            timeline=None,
            raw_start_us=raw_start_us,
            start_us=start_us,
            duration_us=duration_us,
            has_video=has_video,
            has_audio=has_audio,
            hovered_track_id=hovered_track_id,
            snap_source=(snap.source.value if snap is not None else "none"),
            snap_reference_id=(
                snap.reference_id if snap is not None else ""
            ),
            conflict_code=conflict_code,
            conflict_reason=conflict_reason,
        )


class TimelineDragTransactionService:
    """Build a complete drop candidate without mutating project state."""

    def __init__(
        self,
        *,
        track_id_factory: Callable[[], str] = new_track_id,
        clip_id_factory: Callable[[], str] = new_clip_id,
        link_group_id_factory: Callable[[], str] = new_link_group_id,
    ) -> None:
        self._track_id_factory = track_id_factory
        self._clip_id_factory = clip_id_factory
        self._link_group_id_factory = link_group_id_factory

    def preview(
        self,
        timeline: Timeline,
        project: ProjectFile,
        *,
        material_id: str,
        has_video: bool,
        has_audio: bool,
        raw_start_us: int,
        hovered_track_id: str | None,
        playhead_us: int,
        editing_fps: int,
        pixels_per_second: float,
        snap_enabled: bool,
        transaction_id: str,
    ) -> TimelineDragCandidate:
        raw_start = max(0, int(raw_start_us))
        hovered_id = str(hovered_track_id or "")
        fingerprint = timeline_edit_fingerprint(timeline, project)
        try:
            validate_timeline(timeline, project)
            material = _find_material(project, material_id)
            duration_us = seconds_to_microseconds(
                material.metadata_snapshot.get("duration_sec")
            )
            if duration_us <= 0:
                raise ValueError("material duration must be positive")
            if not Path(material.last_known_path).is_file():
                raise ValueError("material file is missing")
            if not has_video and not has_audio:
                raise ValueError("material has no supported media stream")
        except Exception as exc:
            return TimelineDragCandidate.invalid(
                transaction_id=transaction_id,
                material_id=material_id,
                raw_start_us=raw_start,
                start_us=raw_start,
                conflict_code="invalid_material",
                conflict_reason=str(exc),
                source_fingerprint=fingerprint,
                has_video=has_video,
                has_audio=has_audio,
                hovered_track_id=hovered_id,
            )

        snap = snap_timeline_time(
            raw_start,
            editing_fps=editing_fps,
            pixels_per_second=pixels_per_second,
            playhead_us=playhead_us,
            clips=timeline.clips,
            enabled=snap_enabled,
        )
        start_us = snap.time_us
        tracks_by_id = {track.track_id: track for track in timeline.tracks}
        hovered = tracks_by_id.get(hovered_id) if hovered_id else None
        if hovered_id and hovered is None:
            return self._invalid(
                transaction_id,
                material_id,
                fingerprint,
                raw_start,
                start_us,
                duration_us,
                has_video,
                has_audio,
                hovered_id,
                snap,
                "missing_track",
                "drop target track no longer exists",
            )
        if hovered is not None and hovered.locked:
            return self._invalid(
                transaction_id,
                material_id,
                fingerprint,
                raw_start,
                start_us,
                duration_us,
                has_video,
                has_audio,
                hovered_id,
                snap,
                "locked_track",
                "drop target track is locked",
            )
        allowed_kinds = {
            kind
            for kind, present in (
                ("video", has_video),
                ("audio", has_audio),
            )
            if present
        }
        if hovered is not None and hovered.kind not in allowed_kinds:
            return self._invalid(
                transaction_id,
                material_id,
                fingerprint,
                raw_start,
                start_us,
                duration_us,
                has_video,
                has_audio,
                hovered_id,
                snap,
                "incompatible_track",
                "material stream type is incompatible with the target track",
            )

        candidate = copy.deepcopy(timeline)
        auto_kinds: list[str] = []
        created_track_ids: list[str] = []
        selected: dict[str, TimelineTrack] = {}
        for kind, present in (
            ("video", has_video),
            ("audio", has_audio),
        ):
            if not present:
                continue
            preferred = (
                hovered.track_id
                if hovered is not None and hovered.kind == kind
                else None
            )
            target = _select_free_track(
                candidate,
                kind,
                start_us,
                duration_us,
                preferred_track_id=preferred,
            )
            if target is None:
                kind_tracks = [
                    track
                    for track in candidate.tracks
                    if track.kind == kind
                ]
                if len(kind_tracks) >= MAX_TRACKS_PER_KIND:
                    return self._invalid(
                        transaction_id,
                        material_id,
                        fingerprint,
                        raw_start,
                        start_us,
                        duration_us,
                        has_video,
                        has_audio,
                        hovered_id,
                        snap,
                        "track_limit",
                        f"{kind} tracks have reached the limit",
                    )
                target = self._append_auto_track(candidate, kind)
                auto_kinds.append(kind)
                created_track_ids.append(target.track_id)
            selected[kind] = target

        created_clip_ids: list[str] = []
        link_group_id = (
            self._link_group_id_factory()
            if has_video and has_audio
            else None
        )
        for kind in ("video", "audio"):
            target = selected.get(kind)
            if target is None:
                continue
            clip_id = self._clip_id_factory()
            created_clip_ids.append(clip_id)
            candidate.clips.append(
                TimelineClip(
                    clip_id=clip_id,
                    material_id=material_id,
                    track_id=target.track_id,
                    timeline_start_us=start_us,
                    timeline_duration_us=duration_us,
                    source_start_us=0,
                    source_duration_us=duration_us,
                    link_group_id=link_group_id,
                )
            )
        try:
            validate_timeline(candidate, project)
        except Exception as exc:
            return self._invalid(
                transaction_id,
                material_id,
                fingerprint,
                raw_start,
                start_us,
                duration_us,
                has_video,
                has_audio,
                hovered_id,
                snap,
                "candidate_invalid",
                str(exc),
            )
        return TimelineDragCandidate(
            transaction_id=transaction_id,
            material_id=material_id,
            valid=True,
            source_fingerprint=fingerprint,
            timeline=candidate,
            raw_start_us=raw_start,
            start_us=start_us,
            duration_us=duration_us,
            has_video=has_video,
            has_audio=has_audio,
            hovered_track_id=hovered_id,
            video_track_id=(
                selected["video"].track_id if "video" in selected else None
            ),
            audio_track_id=(
                selected["audio"].track_id if "audio" in selected else None
            ),
            snap_source=snap.source.value,
            snap_reference_id=snap.reference_id,
            auto_track_kinds=tuple(auto_kinds),
            created_track_ids=tuple(created_track_ids),
            created_clip_ids=tuple(created_clip_ids),
        )

    def _append_auto_track(
        self,
        timeline: Timeline,
        kind: str,
    ) -> TimelineTrack:
        tracks = [track for track in timeline.tracks if track.kind == kind]
        track = TimelineTrack(
            track_id=self._track_id_factory(),
            kind=kind,
            name=_unused_track_name(kind, tracks),
            order=0 if kind == "video" else len(tracks),
        )
        if kind == "video":
            for existing in tracks:
                existing.order += 1
            insertion = next(
                (
                    index
                    for index, existing in enumerate(timeline.tracks)
                    if existing.kind == "video"
                ),
                0,
            )
            timeline.tracks.insert(insertion, track)
        else:
            timeline.tracks.append(track)
        return track

    @staticmethod
    def _invalid(
        transaction_id: str,
        material_id: str,
        source_fingerprint: str,
        raw_start_us: int,
        start_us: int,
        duration_us: int,
        has_video: bool,
        has_audio: bool,
        hovered_track_id: str,
        snap: TimelineSnapResult,
        conflict_code: str,
        conflict_reason: str,
    ) -> TimelineDragCandidate:
        return TimelineDragCandidate.invalid(
            transaction_id=transaction_id,
            material_id=material_id,
            raw_start_us=raw_start_us,
            start_us=start_us,
            conflict_code=conflict_code,
            conflict_reason=conflict_reason,
            source_fingerprint=source_fingerprint,
            duration_us=duration_us,
            has_video=has_video,
            has_audio=has_audio,
            hovered_track_id=hovered_track_id,
            snap=snap,
        )


def _find_material(project: ProjectFile, material_id: str) -> ProjectMaterialRef:
    material = next(
        (
            item
            for item in project.materials
            if item.material_id == material_id
        ),
        None,
    )
    if material is None:
        raise ValueError(f"material is not part of the project: {material_id}")
    return material


def _select_free_track(
    timeline: Timeline,
    kind: str,
    start_us: int,
    duration_us: int,
    *,
    preferred_track_id: str | None,
) -> TimelineTrack | None:
    tracks = sorted(
        (
            track
            for track in timeline.tracks
            if track.kind == kind and not track.locked
        ),
        key=lambda track: (track.order, track.track_id),
    )
    preferred = next(
        (
            track
            for track in tracks
            if track.track_id == preferred_track_id
        ),
        None,
    )
    if preferred is not None and _track_is_free(
        timeline,
        preferred.track_id,
        start_us,
        duration_us,
    ):
        return preferred
    if preferred is not None:
        tracks.sort(
            key=lambda track: (
                abs(track.order - preferred.order),
                track.order,
                track.track_id,
            )
        )
    return next(
        (
            track
            for track in tracks
            if _track_is_free(
                timeline,
                track.track_id,
                start_us,
                duration_us,
            )
        ),
        None,
    )


def _track_is_free(
    timeline: Timeline,
    track_id: str,
    start_us: int,
    duration_us: int,
) -> bool:
    end_us = start_us + duration_us
    return all(
        clip.track_id != track_id
        or clip.timeline_end_us <= start_us
        or clip.timeline_start_us >= end_us
        for clip in timeline.clips
    )


def _unused_track_name(
    kind: str,
    tracks: list[TimelineTrack],
) -> str:
    label = "视频" if kind == "video" else "音频"
    names = {track.name for track in tracks}
    index = 1
    while f"{label} {index}" in names:
        index += 1
    return f"{label} {index}"
