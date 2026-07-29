from __future__ import annotations

import copy
from dataclasses import dataclass, replace

from utils.project_store import ProjectFile
from utils.timeline_model import (
    TIMELINE_EXTENSION_KEY,
    Timeline,
    TimelineClip,
    TimelineTrack,
    validate_timeline,
    with_project_timeline,
)

DELTA_HISTORY_COMMANDS = frozenset(
    {
        "move_clip",
        "rename_track",
        "reorder_track",
        "set_track_locked",
        "trim_clip",
    }
)


@dataclass(frozen=True)
class TrackChange:
    track_id: str
    before: TimelineTrack
    after: TimelineTrack


@dataclass(frozen=True)
class ClipChange:
    clip_id: str
    before: TimelineClip
    after: TimelineClip


@dataclass(frozen=True)
class SnapshotTimelineHistoryEntry:
    command: str
    before: Timeline
    after: Timeline
    before_project: ProjectFile
    after_project: ProjectFile

    def undo(
        self,
        _current_project: ProjectFile,
        _current_timeline: Timeline,
    ) -> tuple[ProjectFile, Timeline]:
        return (
            copy.deepcopy(self.before_project),
            copy.deepcopy(self.before),
        )

    def redo(
        self,
        _current_project: ProjectFile,
        _current_timeline: Timeline,
    ) -> tuple[ProjectFile, Timeline]:
        return (
            copy.deepcopy(self.after_project),
            copy.deepcopy(self.after),
        )

    def rebase_project(
        self,
        fresh_project: ProjectFile,
    ) -> SnapshotTimelineHistoryEntry:
        return replace(
            self,
            before_project=with_project_timeline(
                fresh_project,
                self.before,
            ),
            after_project=with_project_timeline(
                fresh_project,
                self.after,
            ),
        )


@dataclass(frozen=True)
class DeltaTimelineHistoryEntry:
    command: str
    track_changes: tuple[TrackChange, ...] = ()
    clip_changes: tuple[ClipChange, ...] = ()

    @property
    def stored_entity_count(self) -> int:
        return len(self.track_changes) + len(self.clip_changes)

    def undo(
        self,
        current_project: ProjectFile,
        current_timeline: Timeline,
    ) -> tuple[ProjectFile, Timeline]:
        return self._apply(
            current_project,
            current_timeline,
            use_after=False,
        )

    def redo(
        self,
        current_project: ProjectFile,
        current_timeline: Timeline,
    ) -> tuple[ProjectFile, Timeline]:
        return self._apply(
            current_project,
            current_timeline,
            use_after=True,
        )

    def rebase_project(
        self,
        _fresh_project: ProjectFile,
    ) -> DeltaTimelineHistoryEntry:
        return self

    def _apply(
        self,
        current_project: ProjectFile,
        current_timeline: Timeline,
        *,
        use_after: bool,
    ) -> tuple[ProjectFile, Timeline]:
        candidate = copy.deepcopy(current_timeline)
        tracks_by_id = {
            track.track_id: index
            for index, track in enumerate(candidate.tracks)
        }
        clips_by_id = {
            clip.clip_id: index
            for index, clip in enumerate(candidate.clips)
        }
        for track_change in self.track_changes:
            index = tracks_by_id.get(track_change.track_id)
            if index is None:
                raise RuntimeError(
                    "timeline history track is missing: "
                    f"{track_change.track_id}"
                )
            candidate.tracks[index] = copy.deepcopy(
                track_change.after if use_after else track_change.before
            )
        for clip_change in self.clip_changes:
            index = clips_by_id.get(clip_change.clip_id)
            if index is None:
                raise RuntimeError(
                    "timeline history clip is missing: "
                    f"{clip_change.clip_id}"
                )
            candidate.clips[index] = copy.deepcopy(
                clip_change.after if use_after else clip_change.before
            )
        validate_timeline(candidate, current_project)
        return (
            with_project_timeline(current_project, candidate),
            candidate,
        )


type TimelineHistoryEntry = (
    SnapshotTimelineHistoryEntry | DeltaTimelineHistoryEntry
)


def build_timeline_history_entry(
    command: str,
    before: Timeline,
    after: Timeline,
    before_project: ProjectFile,
    after_project: ProjectFile,
) -> TimelineHistoryEntry:
    if (
        command in DELTA_HISTORY_COMMANDS
        and _timeline_headers_match(before, after)
        and _project_context_matches(before_project, after_project)
    ):
        delta = _build_delta(command, before, after)
        if delta is not None:
            return delta
    return SnapshotTimelineHistoryEntry(
        command,
        copy.deepcopy(before),
        copy.deepcopy(after),
        copy.deepcopy(before_project),
        copy.deepcopy(after_project),
    )


def _build_delta(
    command: str,
    before: Timeline,
    after: Timeline,
) -> DeltaTimelineHistoryEntry | None:
    before_tracks = {item.track_id: item for item in before.tracks}
    after_tracks = {item.track_id: item for item in after.tracks}
    before_clips = {item.clip_id: item for item in before.clips}
    after_clips = {item.clip_id: item for item in after.clips}
    if (
        before_tracks.keys() != after_tracks.keys()
        or before_clips.keys() != after_clips.keys()
    ):
        return None

    track_changes = tuple(
        TrackChange(
            track_id,
            copy.deepcopy(before_tracks[track_id]),
            copy.deepcopy(after_tracks[track_id]),
        )
        for track_id in before_tracks
        if before_tracks[track_id] != after_tracks[track_id]
    )
    clip_changes = tuple(
        ClipChange(
            clip_id,
            copy.deepcopy(before_clips[clip_id]),
            copy.deepcopy(after_clips[clip_id]),
        )
        for clip_id in before_clips
        if before_clips[clip_id] != after_clips[clip_id]
    )
    if not track_changes and not clip_changes:
        return None
    return DeltaTimelineHistoryEntry(
        command,
        track_changes,
        clip_changes,
    )


def _timeline_headers_match(before: Timeline, after: Timeline) -> bool:
    before_header = copy.deepcopy(before)
    after_header = copy.deepcopy(after)
    before_header.tracks = []
    before_header.clips = []
    after_header.tracks = []
    after_header.clips = []
    return before_header == after_header


def _project_context_matches(
    before: ProjectFile,
    after: ProjectFile,
) -> bool:
    before_context = copy.deepcopy(before)
    after_context = copy.deepcopy(after)
    before_context.updated_at = ""
    after_context.updated_at = ""
    before_context.extensions.pop(TIMELINE_EXTENSION_KEY, None)
    after_context.extensions.pop(TIMELINE_EXTENSION_KEY, None)
    return before_context == after_context
