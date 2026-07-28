from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from services.project_library import ProjectLibraryService
from services.timeline_commands import TimelineCommandService
from utils.project_store import ProjectMaterialRef, load_project, save_project
from utils.timeline_model import (
    MAX_TRACKS_PER_KIND,
    TIMELINE_EXTENSION_KEY,
    load_project_timeline,
)


class TimelineFixture:
    def __init__(self, root: Path) -> None:
        self.index_path = root / "projects.json"
        self.project_service = ProjectLibraryService(self.index_path)
        created = self.project_service.create_project(
            name="时间线项目",
            root_path=root / "projects",
            project_id="project-1",
            now="2026-07-28T10:00:00+08:00",
        )
        if not created.ok:
            raise AssertionError(created.error)
        self.project_path = created.path
        added = self.project_service.add_material(
            "project-1",
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=r"E:\QRtest\中文 空格\demo.mp4",
                file_name="demo.mp4",
                added_at="2026-07-28T10:01:00+08:00",
                metadata_snapshot={
                    "duration_sec": 1.0,
                    "audio_source": "both",
                },
            ),
            now="2026-07-28T10:01:00+08:00",
        )
        if not added.ok:
            raise AssertionError(added.error)
        self.session = TimelineCommandService(
            self.project_service,
            "project-1",
        )
        if not self.session.ready:
            raise AssertionError(self.session.error)


@pytest.fixture
def timeline_fixture(tmp_path: Path) -> TimelineFixture:
    return TimelineFixture(tmp_path)


def test_add_material_creates_linked_video_and_audio_and_persists(
    timeline_fixture: TimelineFixture,
) -> None:
    result = timeline_fixture.session.add_material(
        "material-1",
        has_audio=True,
        now="2026-07-28T10:02:00+08:00",
    )
    loaded = load_project(timeline_fixture.project_path)
    assert loaded.ok and loaded.project is not None
    persisted = load_project_timeline(loaded.project)

    assert result.ok and result.changed and result.saved
    assert len(result.affected_clip_ids) == 2
    assert persisted.ok and persisted.timeline is not None
    assert persisted.timeline == timeline_fixture.session.timeline
    video, audio = persisted.timeline.clips
    assert video.clip_id != audio.clip_id
    assert video.link_group_id == audio.link_group_id
    assert video.timeline_start_us == audio.timeline_start_us == 0
    assert video.timeline_duration_us == audio.timeline_duration_us == 1_000_000


def test_timeline_load_and_save_logs_are_classified_without_media_path(
    timeline_fixture: TimelineFixture,
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="QuickRec")
    timeline_fixture.session.reload()

    result = timeline_fixture.session.add_material(
        "material-1",
        has_audio=False,
    )

    assert result.ok
    assert "timeline loaded" in caplog.text
    assert "timeline command saved" in caplog.text
    assert "add_material" in caplog.text
    assert r"E:\QRtest\中文 空格" not in caplog.text


def test_same_material_can_be_added_as_independent_instances(
    timeline_fixture: TimelineFixture,
) -> None:
    first = timeline_fixture.session.add_material("material-1", has_audio=False)
    second = timeline_fixture.session.add_material("material-1", has_audio=False)

    assert first.ok and second.ok
    assert len(timeline_fixture.session.timeline.clips) == 2
    first_clip, second_clip = timeline_fixture.session.timeline.clips
    assert first_clip.clip_id != second_clip.clip_id
    assert (first_clip.timeline_start_us, second_clip.timeline_start_us) == (
        0,
        1_000_000,
    )


def test_delete_linked_clip_requires_confirmation_then_removes_group(
    timeline_fixture: TimelineFixture,
) -> None:
    added = timeline_fixture.session.add_material("material-1", has_audio=True)
    clip_id = added.affected_clip_ids[0]
    before = copy.deepcopy(timeline_fixture.session.timeline)

    pending = timeline_fixture.session.delete_clip(clip_id)

    assert not pending.ok
    assert pending.requires_confirmation
    assert timeline_fixture.session.timeline == before

    deleted = timeline_fixture.session.delete_clip(clip_id, confirmed=True)

    assert deleted.ok
    assert len(deleted.affected_clip_ids) == 2
    assert timeline_fixture.session.timeline.clips == []


def test_remove_referenced_project_material_is_atomic_and_undoable(
    timeline_fixture: TimelineFixture,
) -> None:
    added = timeline_fixture.session.add_material("material-1", has_audio=True)
    assert added.ok
    before = copy.deepcopy(timeline_fixture.session.project)

    pending = timeline_fixture.session.remove_project_material("material-1")

    assert not pending.ok
    assert pending.requires_confirmation
    assert set(pending.affected_clip_ids) == set(added.affected_clip_ids)
    assert timeline_fixture.session.project == before

    removed = timeline_fixture.session.remove_project_material(
        "material-1",
        confirmed=True,
    )

    assert removed.ok
    assert timeline_fixture.session.project.materials == []
    assert timeline_fixture.session.timeline.clips == []
    persisted = load_project(timeline_fixture.project_path)
    assert persisted.ok and persisted.project is not None
    assert persisted.project.materials == []
    assert load_project_timeline(persisted.project).timeline.clips == []

    undone = timeline_fixture.session.undo()

    assert undone.ok
    assert [item.material_id for item in timeline_fixture.session.project.materials] == [
        "material-1"
    ]
    assert {
        item.clip_id for item in timeline_fixture.session.timeline.clips
    } == set(added.affected_clip_ids)

    redone = timeline_fixture.session.redo()

    assert redone.ok
    assert timeline_fixture.session.project.materials == []
    assert timeline_fixture.session.timeline.clips == []


def test_remove_project_material_save_failure_keeps_reference_and_clips(
    timeline_fixture: TimelineFixture,
) -> None:
    added = timeline_fixture.session.add_material("material-1", has_audio=True)
    assert added.ok
    before_project = copy.deepcopy(timeline_fixture.session.project)
    before_timeline = copy.deepcopy(timeline_fixture.session.timeline)
    before_file = timeline_fixture.project_path.read_bytes()

    with patch(
        "services.project_library.save_project",
        side_effect=OSError("project write denied"),
    ):
        result = timeline_fixture.session.remove_project_material(
            "material-1",
            confirmed=True,
        )

    assert not result.ok
    assert timeline_fixture.session.project == before_project
    assert timeline_fixture.session.timeline == before_timeline
    assert timeline_fixture.project_path.read_bytes() == before_file


def test_horizontal_move_keeps_linked_start_and_vertical_move_only_changes_selected_track(
    timeline_fixture: TimelineFixture,
) -> None:
    added = timeline_fixture.session.add_material("material-1", has_audio=True)
    video_clip_id, _audio_clip_id = added.affected_clip_ids
    new_track = timeline_fixture.session.add_track("video")
    assert new_track.ok
    target_track_id = new_track.affected_track_ids[0]

    moved = timeline_fixture.session.move_clip(
        video_clip_id,
        timeline_start_us=2_000_000,
        target_track_id=target_track_id,
    )

    assert moved.ok
    clips = timeline_fixture.session.timeline.clips
    video = next(item for item in clips if item.clip_id == video_clip_id)
    audio = next(item for item in clips if item.clip_id != video_clip_id)
    assert video.track_id == target_track_id
    assert video.timeline_start_us == audio.timeline_start_us == 2_000_000


def test_invalid_move_has_zero_effect_on_memory_file_and_history(
    timeline_fixture: TimelineFixture,
) -> None:
    first = timeline_fixture.session.add_material("material-1", has_audio=False)
    second = timeline_fixture.session.add_material("material-1", has_audio=False)
    before_timeline = copy.deepcopy(timeline_fixture.session.timeline)
    before_file = timeline_fixture.project_path.read_bytes()
    before_undo = timeline_fixture.session.undo_depth

    result = timeline_fixture.session.move_clip(
        second.affected_clip_ids[0],
        timeline_start_us=500_000,
    )

    assert not result.ok
    assert result.stage == "validate"
    assert timeline_fixture.session.timeline == before_timeline
    assert timeline_fixture.project_path.read_bytes() == before_file
    assert timeline_fixture.session.undo_depth == before_undo
    assert first.ok


def test_track_management_enforces_limits_names_order_and_minimum(
    timeline_fixture: TimelineFixture,
) -> None:
    session = timeline_fixture.session
    created_ids: list[str] = []
    for _ in range(MAX_TRACKS_PER_KIND - 1):
        result = session.add_track("video")
        assert result.ok
        created_ids.extend(result.affected_track_ids)
    assert not session.add_track("video").ok

    renamed = session.rename_track(created_ids[0], "")
    assert renamed.ok
    renamed_track = next(
        track for track in session.timeline.tracks if track.track_id == created_ids[0]
    )
    assert renamed_track.name.startswith("视频 ")

    reordered = session.reorder_track(created_ids[-1], 0)
    assert reordered.ok
    video_orders = sorted(
        track.order for track in session.timeline.tracks if track.kind == "video"
    )
    assert video_orders == list(range(MAX_TRACKS_PER_KIND))

    for track_id in created_ids:
        assert session.delete_track(track_id, confirmed=True).ok
    remaining_video = next(
        track for track in session.timeline.tracks if track.kind == "video"
    )
    minimum = session.delete_track(remaining_video.track_id, confirmed=True)
    assert not minimum.ok
    assert minimum.stage == "validate"


def test_delete_track_previews_and_removes_external_link_members(
    timeline_fixture: TimelineFixture,
) -> None:
    added = timeline_fixture.session.add_material("material-1", has_audio=True)
    video_clip = next(
        clip
        for clip in timeline_fixture.session.timeline.clips
        if clip.clip_id == added.affected_clip_ids[0]
    )
    extra_video_track = timeline_fixture.session.add_track("video")
    assert extra_video_track.ok

    pending = timeline_fixture.session.delete_track(video_clip.track_id)

    assert not pending.ok
    assert pending.requires_confirmation
    assert set(pending.affected_clip_ids) == set(added.affected_clip_ids)

    deleted = timeline_fixture.session.delete_track(
        video_clip.track_id,
        confirmed=True,
    )

    assert deleted.ok
    assert timeline_fixture.session.timeline.clips == []


def test_undo_redo_persist_and_new_command_clears_redo(
    timeline_fixture: TimelineFixture,
) -> None:
    session = timeline_fixture.session
    added = session.add_material("material-1", has_audio=False)
    assert added.ok and session.undo_depth == 1

    undone = session.undo()
    assert undone.ok
    assert session.timeline.clips == []
    assert session.redo_depth == 1
    persisted = load_project(timeline_fixture.project_path)
    assert persisted.ok and persisted.project is not None
    assert load_project_timeline(persisted.project).timeline.clips == []

    redone = session.redo()
    assert redone.ok
    assert len(session.timeline.clips) == 1

    assert session.undo().ok
    assert session.add_track("video").ok
    assert session.redo_depth == 0


def test_history_is_limited_to_fifty_commands(
    timeline_fixture: TimelineFixture,
) -> None:
    session = timeline_fixture.session
    for index in range(55):
        result = session.rename_track(
            session.timeline.tracks[0].track_id,
            f"视频轨 {index}",
        )
        assert result.ok

    assert session.undo_depth == 50
    for _ in range(50):
        assert session.undo().ok
    assert not session.undo().ok


def test_project_save_failure_rolls_back_memory_and_history(
    timeline_fixture: TimelineFixture,
) -> None:
    before = copy.deepcopy(timeline_fixture.session.timeline)
    before_file = timeline_fixture.project_path.read_bytes()

    with patch(
        "services.project_library.save_project",
        side_effect=OSError("project write denied"),
    ):
        result = timeline_fixture.session.add_track("video")

    assert not result.ok
    assert result.stage == "project"
    assert timeline_fixture.session.timeline == before
    assert timeline_fixture.project_path.read_bytes() == before_file
    assert timeline_fixture.session.undo_depth == 0


def test_index_failure_restores_exact_project_and_allows_later_retry(
    timeline_fixture: TimelineFixture,
) -> None:
    before = timeline_fixture.project_path.read_bytes()

    with patch(
        "services.project_library.save_project_index",
        side_effect=OSError("index write denied"),
    ):
        failed = timeline_fixture.session.add_track("video")

    assert not failed.ok
    assert failed.stage == "index"
    assert failed.rolled_back
    assert timeline_fixture.project_path.read_bytes() == before
    assert timeline_fixture.session.undo_depth == 0

    retried = timeline_fixture.session.retry_pending_save()
    assert retried.ok


def test_failed_save_keeps_exact_candidate_for_retry(
    timeline_fixture: TimelineFixture,
) -> None:
    before = timeline_fixture.session.timeline

    with patch(
        "services.project_library.save_project_index",
        side_effect=OSError("index write denied"),
    ):
        failed = timeline_fixture.session.add_track("video")

    assert not failed.ok
    assert timeline_fixture.session.has_pending_save
    assert timeline_fixture.session.pending_save_stage == "index"
    assert timeline_fixture.session.timeline == before

    blocked = timeline_fixture.session.add_track("audio")
    assert not blocked.ok
    assert blocked.stage == "pending_save"

    retried = timeline_fixture.session.retry_pending_save()

    assert retried.ok
    assert retried.command == "add_track"
    assert not timeline_fixture.session.has_pending_save
    assert len(timeline_fixture.session.timeline.tracks) == len(before.tracks) + 1
    assert timeline_fixture.session.undo_depth == 1


def test_discard_pending_save_preserves_last_persisted_timeline(
    timeline_fixture: TimelineFixture,
) -> None:
    before = timeline_fixture.session.timeline
    before_file = timeline_fixture.project_path.read_bytes()

    with patch(
        "services.project_library.save_project",
        side_effect=OSError("project write denied"),
    ):
        failed = timeline_fixture.session.add_track("video")

    assert not failed.ok
    discarded = timeline_fixture.session.discard_pending_save()

    assert discarded.ok
    assert not timeline_fixture.session.has_pending_save
    assert timeline_fixture.session.timeline == before
    assert timeline_fixture.project_path.read_bytes() == before_file
    assert timeline_fixture.session.undo_depth == 0


def test_external_conflict_can_save_unregistered_recovery_copy(
    timeline_fixture: TimelineFixture,
) -> None:
    changed = timeline_fixture.project_service.rename_project(
        "project-1",
        "外部新名称",
        now="2026-07-28T11:00:00+08:00",
    )
    assert changed.ok

    failed = timeline_fixture.session.add_track("video")

    assert not failed.ok
    assert failed.stage == "external_conflict"
    assert timeline_fixture.session.has_pending_save

    recovered = timeline_fixture.session.save_pending_recovery_copy(
        timestamp="20260728_111500",
    )

    assert recovered.ok
    recovery_path = Path(recovered.recovery_path)
    assert recovery_path.is_file()
    assert "timeline-recovery-20260728_111500" in recovery_path.name
    recovery_project = load_project(recovery_path)
    assert recovery_project.ok and recovery_project.project is not None
    recovery_timeline = load_project_timeline(recovery_project.project)
    assert recovery_timeline.ok and recovery_timeline.timeline is not None
    assert len(recovery_timeline.timeline.tracks) == 3

    current = load_project(timeline_fixture.project_path)
    assert current.ok and current.project is not None
    assert current.project.name == "外部新名称"
    assert not timeline_fixture.session.has_pending_save
    assert timeline_fixture.session.project.name == "外部新名称"


def test_external_project_change_blocks_stale_session(
    timeline_fixture: TimelineFixture,
) -> None:
    changed = timeline_fixture.project_service.rename_project(
        "project-1",
        "外部新名称",
        now="2026-07-28T11:00:00+08:00",
    )
    assert changed.ok

    result = timeline_fixture.session.add_track("video")

    assert not result.ok
    assert result.stage == "external_conflict"


def test_reload_external_project_refreshes_index_before_next_timeline_edit(
    timeline_fixture: TimelineFixture,
) -> None:
    entry_before = timeline_fixture.project_service.get_entry("project-1")
    loaded = load_project(timeline_fixture.project_path)
    assert entry_before is not None
    assert loaded.ok and loaded.project is not None

    external = copy.deepcopy(loaded.project)
    external.name = "外部修改名称"
    external.updated_at = "2026-07-28T11:00:00+08:00"
    assert save_project(timeline_fixture.project_path, external).ok
    assert (
        timeline_fixture.project_path.stat().st_mtime_ns
        != entry_before.file_modified_ns
    )

    conflict = timeline_fixture.session.add_track("video")
    reloaded = timeline_fixture.session.reload_external_project()
    edited = timeline_fixture.session.add_track("video")

    assert not conflict.ok
    assert conflict.stage == "external_conflict"
    assert reloaded.ok
    assert edited.ok
    assert timeline_fixture.session.project.name == "外部修改名称"


def test_refresh_project_snapshot_keeps_timeline_history_and_new_material(
    timeline_fixture: TimelineFixture,
) -> None:
    session = timeline_fixture.session
    added_clip = session.add_material("material-1", has_audio=False)
    assert added_clip.ok
    before_timeline = session.timeline
    assert session.undo_depth == 1

    added_reference = timeline_fixture.project_service.add_material(
        "project-1",
        ProjectMaterialRef(
            material_id="material-2",
            last_known_path=r"E:\QRtest\中文 空格\second.mp4",
            file_name="second.mp4",
            added_at="2026-07-28T11:05:00+08:00",
            metadata_snapshot={
                "duration_sec": 2.0,
                "audio_source": "none",
            },
        ),
        now="2026-07-28T11:05:00+08:00",
    )
    assert added_reference.ok

    refreshed = session.refresh_project_snapshot()

    assert refreshed.ok
    assert session.timeline == before_timeline
    assert session.undo_depth == 1
    assert [item.material_id for item in session.project.materials] == [
        "material-1",
        "material-2",
    ]

    undone = session.undo()
    assert undone.ok
    persisted_after_undo = load_project(timeline_fixture.project_path)
    assert persisted_after_undo.ok
    assert persisted_after_undo.project is not None
    assert [
        item.material_id for item in persisted_after_undo.project.materials
    ] == ["material-1", "material-2"]
    assert load_project_timeline(
        persisted_after_undo.project
    ).timeline.clips == []

    redone = session.redo()
    assert redone.ok
    persisted_after_redo = load_project(timeline_fixture.project_path)
    assert persisted_after_redo.ok
    assert persisted_after_redo.project is not None
    assert [
        item.material_id for item in persisted_after_redo.project.materials
    ] == ["material-1", "material-2"]
    assert len(load_project_timeline(persisted_after_redo.project).timeline.clips) == 1


def test_archived_project_rejects_timeline_command(tmp_path: Path) -> None:
    fixture = TimelineFixture(tmp_path)
    assert fixture.project_service.archive_project("project-1").ok
    session = TimelineCommandService(fixture.project_service, "project-1")

    result = session.add_track("video")

    assert not result.ok
    assert result.stage == "read_only"


def test_corrupt_timeline_can_recover_from_valid_project_backup(
    tmp_path: Path,
) -> None:
    fixture = TimelineFixture(tmp_path)
    assert fixture.session.add_material("material-1", has_audio=False).ok
    backup = fixture.project_path.with_name(
        f"{fixture.project_path.name}.bak"
    )
    backup.write_bytes(fixture.project_path.read_bytes())
    _write_corrupt_timeline(fixture.project_path)
    session = TimelineCommandService(
        fixture.project_service,
        "project-1",
    )

    assert session.status == "corrupt"
    assert session.timeline_backup_available
    result = session.recover_timeline_from_backup()

    assert result.ok
    assert session.ready
    assert session.status == "ready"
    assert len(session.timeline.clips) == 1


def test_corrupt_timeline_without_backup_is_preserved_before_empty_rebuild(
    tmp_path: Path,
) -> None:
    fixture = TimelineFixture(tmp_path)
    assert fixture.session.add_material("material-1", has_audio=False).ok
    _write_corrupt_timeline(fixture.project_path)
    fixture.project_path.with_name(
        f"{fixture.project_path.name}.bak"
    ).unlink(missing_ok=True)
    session = TimelineCommandService(
        fixture.project_service,
        "project-1",
    )

    result = session.rebuild_empty_timeline()

    assert result.ok
    assert session.ready
    assert session.timeline.clips == []
    assert len(session.project.materials) == 1
    preserved = list(
        fixture.project_path.parent.glob(
            "project.timeline-corrupt-*.qrproj"
        )
    )
    assert len(preserved) == 1
    raw = json.loads(preserved[0].read_text(encoding="utf-8"))
    assert raw["extensions"][TIMELINE_EXTENSION_KEY]["tracks"] == []


def test_timeline_save_only_changes_timeline_extension(
    timeline_fixture: TimelineFixture,
) -> None:
    before = load_project(timeline_fixture.project_path)
    assert before.ok and before.project is not None
    before_project = before.project

    result = timeline_fixture.session.add_track("video")
    after = load_project(timeline_fixture.project_path)
    assert after.ok and after.project is not None

    assert result.ok
    assert after.project.project_id == before_project.project_id
    assert after.project.name == before_project.name
    assert after.project.materials == before_project.materials
    assert TIMELINE_EXTENSION_KEY in after.project.extensions


def _write_corrupt_timeline(path: Path) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["extensions"][TIMELINE_EXTENSION_KEY] = {
        "schema_version": 1,
        "timeline_id": "timeline-corrupt",
        "tracks": [],
        "clips": [],
    }
    path.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
