from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from services.project_library import ProjectLibraryService
from services.timeline_commands import TimelineCommandService
from utils.project_store import ProjectMaterialRef, ProjectWriteResult


@pytest.fixture
def delete_session(
    tmp_path: Path,
) -> tuple[TimelineCommandService, tuple[str, ...], tuple[str, ...], Path]:
    source = tmp_path / "中文 空格" / "source.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"video")
    service = ProjectLibraryService(
        tmp_path / "projects.json",
        default_root=tmp_path / "projects",
    )
    created = service.create_project(
        name="删除测试",
        project_id="project-delete",
    )
    assert created.ok
    assert service.add_material(
        "project-delete",
        ProjectMaterialRef(
            material_id="material-1",
            last_known_path=str(source),
            file_name=source.name,
            added_at="2026-07-30T12:00:00+08:00",
            metadata_snapshot={
                "duration_sec": 5.0,
                "fps": 30.0,
                "audio_source": "both",
            },
        ),
    ).ok
    session = TimelineCommandService(service, "project-delete")
    first = session.add_material("material-1", has_audio=True)
    second = session.add_material("material-1", has_audio=True)
    assert first.ok and second.ok
    assert created.path is not None
    return (
        session,
        first.affected_clip_ids,
        second.affected_clip_ids,
        created.path,
    )


def test_normal_delete_of_unlinked_clip_preserves_gap_and_other_side(
    delete_session,
) -> None:
    session, first_ids, second_ids, _project_path = delete_session
    assert session.unlink_clip(first_ids[0]).ok
    before_starts = {
        clip.clip_id: clip.timeline_start_us
        for clip in session.timeline.clips
        if clip.clip_id != first_ids[1]
    }

    candidate = session.preview_delete_clip(first_ids[1])
    deleted = session.commit_edit_candidate(candidate)

    assert candidate.valid
    assert candidate.operation == "delete"
    assert candidate.impact.ripple_clip_ids == ()
    assert deleted.ok
    remaining = {
        clip.clip_id: clip.timeline_start_us
        for clip in session.timeline.clips
    }
    assert first_ids[1] not in remaining
    assert first_ids[0] in remaining
    assert all(clip_id in remaining for clip_id in second_ids)
    assert remaining == before_starts


def test_normal_delete_of_linked_group_requires_confirmation_and_keeps_gap(
    delete_session,
) -> None:
    session, first_ids, second_ids, _project_path = delete_session
    before_starts = {
        clip.clip_id: clip.timeline_start_us
        for clip in session.timeline.clips
        if clip.clip_id in second_ids
    }

    pending = session.delete_clip(first_ids[0])
    deleted = session.delete_clip(first_ids[0], confirmed=True)

    assert not pending.ok
    assert pending.requires_confirmation
    assert set(pending.affected_clip_ids) == set(first_ids)
    assert deleted.ok
    remaining = {
        clip.clip_id: clip.timeline_start_us
        for clip in session.timeline.clips
    }
    assert set(remaining) == set(second_ids)
    assert remaining == before_starts


def test_ripple_delete_remains_a_distinct_command_that_moves_later_clips(
    delete_session,
) -> None:
    session, first_ids, second_ids, _project_path = delete_session

    candidate = session.preview_ripple_delete(first_ids[0])
    deleted = session.commit_edit_candidate(candidate)

    assert candidate.operation == "ripple_delete"
    assert deleted.ok
    assert deleted.command == "ripple_delete_clip"
    assert {
        clip.timeline_start_us
        for clip in session.timeline.clips
        if clip.clip_id in second_ids
    } == {0}


def test_normal_delete_save_failure_has_zero_memory_and_history_side_effects(
    delete_session,
) -> None:
    session, first_ids, _second_ids, project_path = delete_session
    assert session.unlink_clip(first_ids[0]).ok
    before = session.timeline
    before_file = project_path.read_bytes()
    before_undo = session.undo_depth

    with patch(
        "services.project_library.save_project",
        return_value=ProjectWriteResult(
            False,
            project_path,
            stage="write",
            error="injected delete failure",
        ),
    ):
        failed = session.delete_clip(first_ids[0])

    assert not failed.ok
    assert session.has_pending_save
    assert session.timeline == before
    assert session.undo_depth == before_undo
    assert project_path.read_bytes() == before_file
    assert session.discard_pending_save().ok
    assert session.timeline == before
