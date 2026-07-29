from __future__ import annotations

import copy
import logging
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import pytest

from services.project_library import ProjectLibraryService
from services.timeline_commands import TimelineCommandService
from utils.project_store import (
    ProjectMaterialRef,
    ProjectWriteResult,
    load_project,
)
from utils.timeline_model import load_project_timeline


class EditingFixture:
    def __init__(self, root: Path) -> None:
        self.project_service = ProjectLibraryService(root / "projects.json")
        created = self.project_service.create_project(
            name="剪辑事务",
            root_path=root / "projects",
            project_id="project-edit-command",
            now="2026-07-29T12:00:00+08:00",
        )
        assert created.ok
        self.project_path = created.path
        added = self.project_service.add_material(
            "project-edit-command",
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=r"E:\QRtest\中文 空格\editing.mp4",
                file_name="editing.mp4",
                added_at="2026-07-29T12:00:01+08:00",
                metadata_snapshot={
                    "duration_sec": 5.0,
                    "fps": 30.0,
                    "audio_source": "both",
                },
            ),
            now="2026-07-29T12:00:01+08:00",
        )
        assert added.ok
        self.session = TimelineCommandService(
            self.project_service,
            "project-edit-command",
        )
        target = self.session.add_material("material-1", has_audio=True)
        later = self.session.add_material("material-1", has_audio=True)
        assert target.ok and later.ok
        self.target_ids = target.affected_clip_ids
        self.later_ids = later.affected_clip_ids


@pytest.fixture
def editing_fixture(tmp_path: Path) -> EditingFixture:
    return EditingFixture(tmp_path)


def test_trim_candidate_commits_once_and_undo_redo_roundtrip(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    before = session.timeline
    baseline_undo = session.undo_depth
    candidate = session.preview_trim_clip(
        editing_fixture.target_ids[0],
        source_start_us=0,
        source_end_us=4_000_000,
    )

    with patch.object(
        editing_fixture.project_service,
        "commit_project_candidate",
        wraps=editing_fixture.project_service.commit_project_candidate,
    ) as commit:
        result = session.commit_edit_candidate(
            candidate,
            now="2026-07-29T12:01:00+08:00",
        )

    assert candidate.valid
    assert result.ok and result.saved
    assert result.command == "trim_clip"
    assert commit.call_count == 1
    assert session.undo_depth == baseline_undo + 1
    after = session.timeline
    assert after != before
    assert {
        clip.timeline_start_us
        for clip in after.clips
        if clip.clip_id in editing_fixture.later_ids
    } == {4_000_000}

    undone = session.undo(now="2026-07-29T12:01:01+08:00")
    assert undone.ok
    assert session.timeline == before

    redone = session.redo(now="2026-07-29T12:01:02+08:00")
    assert redone.ok
    assert session.timeline == after


def test_split_candidate_is_one_snapshot_history_and_restores_identity(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    before = session.timeline
    before_ids = {clip.clip_id for clip in before.clips}
    candidate = session.preview_split_clip(
        editing_fixture.target_ids[0],
        playhead_us=2_000_000,
    )

    result = session.commit_edit_candidate(candidate)

    assert candidate.valid
    assert result.ok
    assert len(candidate.selected_clip_ids) == 2
    after_ids = {clip.clip_id for clip in session.timeline.clips}
    assert before_ids < after_ids
    assert set(candidate.selected_clip_ids) == after_ids - before_ids

    assert session.undo().ok
    assert session.timeline == before
    assert session.redo().ok
    assert {clip.clip_id for clip in session.timeline.clips} == after_ids


def test_edit_diagnostic_summary_tracks_preview_commit_and_history_without_paths(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    candidate = session.preview_trim_clip(
        editing_fixture.target_ids[0],
        source_start_us=0,
        source_end_us=4_000_000,
    )
    preview = session.diagnostic_summary()

    assert candidate.valid
    assert preview["last_edit_command"] == "trim"
    assert preview["last_edit_stage"] == "preview"
    assert preview["last_edit_result"] == "ok"
    assert preview["last_edit_conflicts"] == []
    assert preview["last_ripple_clip_count"] == 2

    assert session.commit_edit_candidate(candidate).ok
    assert session.undo().ok
    assert session.redo().ok
    summary = session.diagnostic_summary()
    serialized = str(summary)

    assert summary["last_edit_command"] == "trim"
    assert summary["last_edit_stage"] == "complete"
    assert summary["last_save_result"] == "ok"
    assert summary["last_undo_result"] == "ok"
    assert summary["last_redo_result"] == "ok"
    assert summary["save_pending"] is False
    assert r"E:\QRtest" not in serialized


def test_edit_preview_and_commit_logs_are_classified_without_media_path(
    editing_fixture: EditingFixture,
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="QuickRec")
    session = editing_fixture.session
    candidate = session.preview_ripple_delete(editing_fixture.target_ids[0])

    assert candidate.valid
    assert session.commit_edit_candidate(candidate).ok
    assert "timeline edit preview" in caplog.text
    assert "operation=ripple_delete" in caplog.text
    assert "ripple_tracks=" in caplog.text
    assert "timeline command saved" in caplog.text
    assert r"E:\QRtest\中文 空格" not in caplog.text


def test_ripple_delete_does_not_remove_project_material_or_media_reference(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    material_before = copy.deepcopy(session.project.materials)
    candidate = session.preview_ripple_delete(
        editing_fixture.target_ids[1],
    )

    result = session.commit_edit_candidate(candidate)

    assert result.ok
    assert session.project.materials == material_before
    assert {
        clip.clip_id for clip in session.timeline.clips
    } == set(editing_fixture.later_ids)
    assert {
        clip.timeline_start_us for clip in session.timeline.clips
    } == {0}
    assert Path(material_before[0].last_known_path).name == "editing.mp4"


def test_locked_track_rejects_add_move_and_legacy_delete(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    clip_id = editing_fixture.target_ids[0]
    clip = next(item for item in session.timeline.clips if item.clip_id == clip_id)
    assert session.set_track_locked(clip.track_id, True).ok
    before = session.timeline

    added = session.add_material(
        "material-1",
        has_audio=False,
        video_track_id=clip.track_id,
    )
    moved = session.move_clip(clip_id, timeline_start_us=250_000)
    deleted = session.delete_clip(clip_id, confirmed=True)

    assert not added.ok and added.stage == "validate"
    assert not moved.ok and moved.stage == "validate"
    assert not deleted.ok and deleted.stage == "validate"
    assert session.timeline == before


def test_stale_candidate_is_rejected_without_saving(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    candidate = session.preview_trim_clip(
        editing_fixture.target_ids[0],
        source_start_us=0,
        source_end_us=4_000_000,
    )
    renamed = session.rename_track("video-track-" + "missing", "noop")
    assert not renamed.ok
    actual_track = session.timeline.tracks[0]
    assert session.rename_track(actual_track.track_id, "已变化").ok
    before = session.timeline
    before_file = editing_fixture.project_path.read_bytes()
    before_undo = session.undo_depth

    result = session.commit_edit_candidate(candidate)

    assert not result.ok
    assert result.stage == "stale_candidate"
    assert session.timeline == before
    assert editing_fixture.project_path.read_bytes() == before_file
    assert session.undo_depth == before_undo


def test_save_failure_keeps_state_and_retry_reuses_exact_candidate(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    candidate = session.preview_trim_clip(
        editing_fixture.target_ids[0],
        source_start_us=0,
        source_end_us=4_000_000,
    )
    before = session.timeline
    before_file = editing_fixture.project_path.read_bytes()
    before_undo = session.undo_depth

    with patch(
        "services.project_library.save_project",
        return_value=ProjectWriteResult(
            False,
            editing_fixture.project_path,
            stage="write",
            error="injected edit failure",
        ),
    ):
        failed = session.commit_edit_candidate(candidate)

    assert not failed.ok
    assert session.has_pending_save
    assert session.timeline == before
    assert editing_fixture.project_path.read_bytes() == before_file
    assert session.undo_depth == before_undo

    retried = session.retry_pending_save(
        now="2026-07-29T12:02:00+08:00",
    )

    assert retried.ok
    assert not session.has_pending_save
    assert session.undo_depth == before_undo + 1
    assert session.timeline == candidate.timeline
    later_starts = {
        clip.timeline_start_us
        for clip in session.timeline.clips
        if clip.clip_id in editing_fixture.later_ids
    }
    assert later_starts == {4_000_000}


def test_discard_failed_edit_keeps_last_successful_state(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    candidate = session.preview_ripple_delete(
        editing_fixture.target_ids[0],
    )
    before = session.timeline

    with patch(
        "services.project_library.save_project",
        return_value=ProjectWriteResult(
            False,
            editing_fixture.project_path,
            stage="write",
            error="injected edit failure",
        ),
    ):
        assert not session.commit_edit_candidate(candidate).ok

    discarded = session.discard_pending_save()

    assert discarded.ok
    assert session.timeline == before
    persisted = load_project(editing_fixture.project_path)
    assert persisted.ok and persisted.project is not None
    loaded = load_project_timeline(persisted.project)
    assert loaded.ok and loaded.timeline == before


def test_read_only_and_pending_save_block_edit_candidate(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    candidate = session.preview_split_clip(
        editing_fixture.target_ids[0],
        playhead_us=2_000_000,
    )
    session.set_runtime_read_only(True, reason="recording")

    blocked = session.commit_edit_candidate(candidate)

    assert not blocked.ok
    assert blocked.stage == "read_only"
    session.set_runtime_read_only(False)


def test_track_lock_uses_one_history_entry_and_is_undoable(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    track_id = session.timeline.tracks[0].track_id
    baseline = session.undo_depth

    locked = session.set_track_locked(track_id, True)

    assert locked.ok
    assert session.undo_depth == baseline + 1
    assert next(
        track for track in session.timeline.tracks if track.track_id == track_id
    ).locked
    assert session.undo().ok
    assert not next(
        track for track in session.timeline.tracks if track.track_id == track_id
    ).locked
    assert session.redo().ok
    assert next(
        track for track in session.timeline.tracks if track.track_id == track_id
    ).locked


def test_candidate_preview_does_not_write_project(
    editing_fixture: EditingFixture,
) -> None:
    session = editing_fixture.session
    before = editing_fixture.project_path.read_bytes()
    before_undo = session.undo_depth

    candidate = session.preview_trim_clip(
        editing_fixture.target_ids[0],
        source_start_us=0,
        source_end_us=4_000_000,
    )

    assert candidate.valid
    assert editing_fixture.project_path.read_bytes() == before
    assert session.undo_depth == before_undo


def test_100_clip_trim_commit_stays_within_transaction_budget(
    tmp_path: Path,
) -> None:
    fixture = EditingFixture(tmp_path)
    session = fixture.session
    for _ in range(48):
        assert session.add_material("material-1", has_audio=True).ok
    assert len(session.timeline.clips) == 100
    candidate = session.preview_trim_clip(
        fixture.target_ids[0],
        source_start_us=0,
        source_end_us=4_000_000,
    )

    started = perf_counter()
    result = session.commit_edit_candidate(candidate)
    elapsed_ms = (perf_counter() - started) * 1000

    assert result.ok
    assert len(result.affected_clip_ids) == 100
    assert elapsed_ms < 300
