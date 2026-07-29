from __future__ import annotations

import copy
import pickle

import pytest

from services.timeline_history import (
    DeltaTimelineHistoryEntry,
    SnapshotTimelineHistoryEntry,
    build_timeline_history_entry,
)
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import (
    Timeline,
    TimelineClip,
    TimelineTrack,
    with_project_timeline,
)


def _project() -> ProjectFile:
    return ProjectFile(
        project_id="project-1",
        name="Project",
        description="",
        created_at="2026-07-28T10:00:00+08:00",
        updated_at="2026-07-28T10:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path="video.mp4",
                file_name="video.mp4",
                added_at="2026-07-28T10:00:00+08:00",
                metadata_snapshot={"duration_sec": 1.0},
            )
        ],
    )


def _timeline(*, clip_count: int = 1) -> Timeline:
    clips = [
        TimelineClip(
            clip_id=f"clip-{index}",
            material_id="material-1",
            track_id="video-1",
            timeline_start_us=index * 1_000_000,
            timeline_duration_us=1_000_000,
            source_start_us=0,
            source_duration_us=1_000_000,
        )
        for index in range(clip_count)
    ]
    return Timeline(
        timeline_id="timeline-1",
        tracks=[
            TimelineTrack("video-1", "video", "Video 1", 0),
            TimelineTrack("video-2", "video", "Video 2", 1),
            TimelineTrack("audio-1", "audio", "Audio 1", 0),
        ],
        clips=clips,
    )


def test_rename_track_uses_delta_history_and_roundtrips() -> None:
    project = _project()
    before = _timeline()
    after = copy.deepcopy(before)
    after.tracks[0].name = "Primary video"
    entry = build_timeline_history_entry(
        "rename_track",
        before,
        after,
        with_project_timeline(project, before),
        with_project_timeline(project, after),
    )

    assert isinstance(entry, DeltaTimelineHistoryEntry)
    assert entry.stored_entity_count == 1

    undone_project, undone = entry.undo(
        with_project_timeline(project, after),
        after,
    )
    redone_project, redone = entry.redo(undone_project, undone)

    assert undone == before
    assert redone == after
    assert redone_project.name == project.name


def test_delta_history_preserves_new_non_timeline_project_fields() -> None:
    project = _project()
    before = _timeline()
    after = copy.deepcopy(before)
    after.clips[0].timeline_start_us = 5_000_000
    entry = build_timeline_history_entry(
        "move_clip",
        before,
        after,
        with_project_timeline(project, before),
        with_project_timeline(project, after),
    )
    fresh_project = with_project_timeline(project, after)
    fresh_project.description = "Changed outside timeline history"

    undone_project, undone = entry.undo(fresh_project, after)

    assert undone == before
    assert undone_project.description == "Changed outside timeline history"


def test_complex_command_keeps_snapshot_adapter() -> None:
    project = _project()
    before = _timeline()
    after = copy.deepcopy(before)
    after.tracks.pop(1)

    entry = build_timeline_history_entry(
        "delete_track",
        before,
        after,
        with_project_timeline(project, before),
        with_project_timeline(project, after),
    )

    assert isinstance(entry, SnapshotTimelineHistoryEntry)


def test_delta_history_rejects_missing_changed_entity_without_mutating_input() -> None:
    project = _project()
    before = _timeline()
    after = copy.deepcopy(before)
    after.tracks[0].name = "Primary video"
    entry = build_timeline_history_entry(
        "rename_track",
        before,
        after,
        with_project_timeline(project, before),
        with_project_timeline(project, after),
    )
    incompatible = copy.deepcopy(after)
    incompatible.tracks = [
        track
        for track in incompatible.tracks
        if track.track_id != "video-1"
    ]
    untouched = copy.deepcopy(incompatible)

    with pytest.raises(RuntimeError, match="video-1"):
        entry.undo(
            with_project_timeline(project, after),
            incompatible,
        )

    assert incompatible == untouched


def test_delta_history_is_materially_smaller_for_large_timeline_move() -> None:
    project = _project()
    before = _timeline(clip_count=100)
    after = copy.deepcopy(before)
    after.clips[50].track_id = "video-2"
    before_project = with_project_timeline(project, before)
    after_project = with_project_timeline(project, after)

    delta = build_timeline_history_entry(
        "move_clip",
        before,
        after,
        before_project,
        after_project,
    )
    snapshot = SnapshotTimelineHistoryEntry(
        "move_clip",
        before,
        after,
        before_project,
        after_project,
    )

    assert isinstance(delta, DeltaTimelineHistoryEntry)
    assert len(pickle.dumps(delta)) < len(pickle.dumps(snapshot)) / 10


@pytest.mark.parametrize("command", ["trim_clip", "set_track_locked"])
def test_v193_entity_updates_use_delta_history(command: str) -> None:
    project = _project()
    before = _timeline()
    after = copy.deepcopy(before)
    if command == "trim_clip":
        after.clips[0].source_duration_us = 900_000
        after.clips[0].timeline_duration_us = 900_000
    else:
        after.tracks[0].locked = True
    entry = build_timeline_history_entry(
        command,
        before,
        after,
        with_project_timeline(project, before),
        with_project_timeline(project, after),
    )

    assert isinstance(entry, DeltaTimelineHistoryEntry)
    assert entry.stored_entity_count == 1


@pytest.mark.parametrize("command", ["split_clip", "ripple_delete_clip"])
def test_v193_structural_edits_keep_snapshot_history(command: str) -> None:
    project = _project()
    before = _timeline()
    after = copy.deepcopy(before)
    if command == "split_clip":
        after.clips[0].timeline_duration_us = 500_000
        after.clips[0].source_duration_us = 500_000
        after.clips.append(
            TimelineClip(
                clip_id="clip-right",
                material_id="material-1",
                track_id="video-1",
                timeline_start_us=500_000,
                timeline_duration_us=500_000,
                source_start_us=500_000,
                source_duration_us=500_000,
            )
        )
    else:
        after.clips.clear()
    entry = build_timeline_history_entry(
        command,
        before,
        after,
        with_project_timeline(project, before),
        with_project_timeline(project, after),
    )

    assert isinstance(entry, SnapshotTimelineHistoryEntry)
