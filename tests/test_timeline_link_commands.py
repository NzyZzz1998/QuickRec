from __future__ import annotations

import copy
from pathlib import Path
from unittest.mock import patch

from services.project_library import ProjectLibraryService
from services.timeline_commands import TimelineCommandService
from services.timeline_edit_service import TimelineEditService
from utils.project_store import (
    ProjectFile,
    ProjectMaterialRef,
    ProjectWriteResult,
)
from utils.timeline_model import Timeline, TimelineClip, TimelineTrack


def _project(source: Path) -> ProjectFile:
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    return ProjectFile(
        project_id="project-1",
        name="关联测试",
        description="",
        created_at="2026-07-30T12:00:00+08:00",
        updated_at="2026-07-30T12:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=str(source),
                file_name=source.name,
                added_at="2026-07-30T12:00:00+08:00",
                metadata_snapshot={
                    "duration_sec": 10.0,
                    "fps": 30.0,
                    "audio_source": "both",
                },
            )
        ],
    )


def _tracks() -> list[TimelineTrack]:
    return [
        TimelineTrack("video-1", "video", "视频 1", 0),
        TimelineTrack("video-2", "video", "视频 2", 1),
        TimelineTrack("video-3", "video", "视频 3", 2),
        TimelineTrack("audio-1", "audio", "音频 1", 0),
        TimelineTrack("audio-2", "audio", "音频 2", 1),
        TimelineTrack("audio-3", "audio", "音频 3", 2),
        TimelineTrack("audio-4", "audio", "音频 4", 3),
        TimelineTrack("audio-5", "audio", "音频 5", 4),
        TimelineTrack("audio-6", "audio", "音频 6", 5),
        TimelineTrack("audio-7", "audio", "音频 7", 6),
    ]


def _clip(
    clip_id: str,
    track_id: str,
    *,
    link_group_id: str | None = None,
    start_us: int = 1_000_000,
    duration_us: int = 3_000_000,
    source_start_us: int = 2_000_000,
    material_id: str = "material-1",
) -> TimelineClip:
    return TimelineClip(
        clip_id=clip_id,
        material_id=material_id,
        track_id=track_id,
        timeline_start_us=start_us,
        timeline_duration_us=duration_us,
        source_start_us=source_start_us,
        source_duration_us=duration_us,
        link_group_id=link_group_id,
        extensions={"future": {"keep": True}},
        unknown_fields={"future_clip": "keep"},
    )


def _command_session(
    tmp_path: Path,
) -> tuple[TimelineCommandService, tuple[str, ...], Path]:
    source = tmp_path / "source.mp4"
    project = _project(source)
    project_service = ProjectLibraryService(
        tmp_path / "projects.json",
        default_root=tmp_path / "projects",
    )
    created = project_service.create_project(
        name=project.name,
        project_id=project.project_id,
    )
    assert created.ok and created.path is not None
    assert project_service.add_material(
        project.project_id,
        project.materials[0],
    ).ok
    session = TimelineCommandService(project_service, project.project_id)
    added = session.add_material("material-1", has_audio=True)
    assert added.ok
    return session, added.affected_clip_ids, created.path


def _linked_timeline() -> Timeline:
    return Timeline(
        "timeline-1",
        _tracks(),
        [
            _clip("video-clip", "video-1", link_group_id="link-original"),
            _clip("audio-clip", "audio-1", link_group_id="link-original"),
        ],
    )


def test_unlink_candidate_only_clears_both_link_group_ids(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "中文 空格" / "source.mp4")
    timeline = _linked_timeline()
    before = {
        clip.clip_id: clip.to_dict()
        for clip in timeline.clips
    }

    candidate = TimelineEditService().unlink(
        timeline,
        project,
        "video-clip",
    )

    assert candidate.valid
    assert candidate.timeline is not None
    assert candidate.selected_clip_ids == ("video-clip",)
    assert set(candidate.impact.target_clip_ids) == {
        "video-clip",
        "audio-clip",
    }
    for clip in candidate.timeline.clips:
        expected = copy.deepcopy(before[clip.clip_id])
        expected["link_group_id"] = None
        assert clip.to_dict() == expected


def test_unlink_rejects_locked_member_without_side_effects(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "source.mp4")
    timeline = _linked_timeline()
    next(
        track
        for track in timeline.tracks
        if track.track_id == "audio-1"
    ).locked = True
    before = copy.deepcopy(timeline)

    candidate = TimelineEditService().unlink(
        timeline,
        project,
        "video-clip",
    )

    assert not candidate.valid
    assert candidate.timeline is None
    assert {item.code for item in candidate.conflicts} == {
        "locked_target_track"
    }
    assert timeline == before


def test_unlink_rejects_malformed_link_group_without_side_effects(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "source.mp4")
    timeline = _linked_timeline()
    timeline.clips.append(
        _clip(
            "extra-audio",
            "audio-2",
            link_group_id="link-original",
        )
    )
    before = copy.deepcopy(timeline)

    candidate = TimelineEditService().unlink(
        timeline,
        project,
        "video-clip",
    )

    assert not candidate.valid
    assert candidate.timeline is None
    assert {item.code for item in candidate.conflicts} == {
        "invalid_timeline"
    }
    assert timeline == before


def test_relink_options_are_strict_and_stably_sorted(tmp_path: Path) -> None:
    project = _project(tmp_path / "中文 空格" / "source.mp4")
    timeline = Timeline(
        "timeline-1",
        _tracks(),
        [
            _clip("video-clip", "video-1"),
            _clip("audio-near", "audio-1"),
            _clip("audio-far", "audio-2"),
                _clip(
                    "audio-wrong-start",
                    "audio-3",
                    start_us=2_000_000,
                ),
        ],
    )

    options = TimelineEditService().relink_options(
        timeline,
        project,
        "video-clip",
    )

    assert [item.clip_id for item in options] == [
        "audio-near",
        "audio-far",
    ]
    assert [item.track_name for item in options] == [
        "音频 1",
        "音频 2",
    ]
    assert all(item.file_exists for item in options)


def test_relink_options_filter_every_incompatible_candidate(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.mp4"
    project = _project(source)
    other_source = tmp_path / "other.mp4"
    other_source.write_bytes(b"other")
    project.materials.append(
        ProjectMaterialRef(
            material_id="material-2",
            last_known_path=str(other_source),
            file_name=other_source.name,
            added_at="2026-07-30T12:00:00+08:00",
            metadata_snapshot={
                "duration_sec": 10.0,
                "fps": 30.0,
                "audio_source": "both",
            },
        )
    )
    timeline = Timeline(
        "timeline-1",
        _tracks(),
        [
            _clip("selected-video", "video-1"),
            _clip("same-kind", "video-2"),
            _clip(
                "linked-video",
                "video-3",
                link_group_id="existing-link",
            ),
            _clip(
                "other-material",
                "audio-1",
                material_id="material-2",
            ),
            _clip("wrong-start", "audio-2", start_us=2_000_000),
            _clip("wrong-duration", "audio-3", duration_us=2_000_000),
            _clip(
                "wrong-source",
                "audio-4",
                source_start_us=3_000_000,
            ),
            _clip("valid-option", "audio-6"),
            _clip(
                "already-linked",
                "audio-7",
                link_group_id="existing-link",
            ),
        ],
    )

    options = TimelineEditService().relink_options(
        timeline,
        project,
        "selected-video",
    )

    assert [item.clip_id for item in options] == ["valid-option"]


def test_relink_candidate_revalidates_and_assigns_a_new_group(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "source.mp4")
    timeline = Timeline(
        "timeline-1",
        _tracks(),
        [
            _clip("video-clip", "video-1"),
            _clip("audio-clip", "audio-1"),
        ],
    )
    before = {
        clip.clip_id: clip.to_dict()
        for clip in timeline.clips
    }
    service = TimelineEditService(
        link_group_id_factory=lambda: "link-new",
    )

    candidate = service.relink(
        timeline,
        project,
        "video-clip",
        "audio-clip",
    )

    assert candidate.valid
    assert candidate.timeline is not None
    for clip in candidate.timeline.clips:
        expected = copy.deepcopy(before[clip.clip_id])
        expected["link_group_id"] = "link-new"
        assert clip.to_dict() == expected

    timeline.clips[1].source_start_us += 1
    rejected = service.relink(
        timeline,
        project,
        "video-clip",
        "audio-clip",
    )
    assert not rejected.valid
    assert rejected.timeline is None
    assert timeline.clips[0].link_group_id is None
    assert timeline.clips[1].link_group_id is None


def test_relink_preview_is_non_mutating_and_stale_commit_is_rejected(
    tmp_path: Path,
) -> None:
    session, clip_ids, project_path = _command_session(tmp_path)
    assert session.unlink_clip(clip_ids[0]).ok
    before = session.timeline
    before_file = project_path.read_bytes()
    before_undo = session.undo_depth

    candidate = session.preview_relink_clip(clip_ids[0], clip_ids[1])

    assert candidate.valid
    assert session.timeline == before
    assert project_path.read_bytes() == before_file
    assert session.undo_depth == before_undo

    track_id = session.timeline.tracks[0].track_id
    assert session.rename_track(track_id, "changed").ok
    changed = session.timeline
    changed_undo = session.undo_depth
    rejected = session.commit_edit_candidate(candidate)

    assert not rejected.ok
    assert rejected.stage == "stale_candidate"
    assert session.timeline == changed
    assert session.undo_depth == changed_undo


def test_unlink_command_is_one_atomic_history_entry_and_round_trips(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.mp4"
    project = _project(source)
    project_service = ProjectLibraryService(
        tmp_path / "projects.json",
        default_root=tmp_path / "projects",
    )
    created = project_service.create_project(
        name=project.name,
        project_id=project.project_id,
    )
    assert created.ok
    assert project_service.add_material(
        project.project_id,
        project.materials[0],
    ).ok
    session = TimelineCommandService(project_service, project.project_id)
    added = session.add_material("material-1", has_audio=True)
    assert added.ok
    before = session.timeline
    original_group = {
        clip.link_group_id
        for clip in before.clips
    }
    baseline_undo = session.undo_depth

    result = session.unlink_clip(added.affected_clip_ids[0])

    assert result.ok
    assert result.command == "unlink_clips"
    assert session.undo_depth == baseline_undo + 1
    assert {clip.link_group_id for clip in session.timeline.clips} == {None}
    assert session.undo().ok
    assert {
        clip.link_group_id for clip in session.timeline.clips
    } == original_group
    assert session.redo().ok
    assert {clip.link_group_id for clip in session.timeline.clips} == {None}


def test_relink_command_uses_current_candidate_and_new_identity(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.mp4"
    project = _project(source)
    project_service = ProjectLibraryService(
        tmp_path / "projects.json",
        default_root=tmp_path / "projects",
    )
    assert project_service.create_project(
        name=project.name,
        project_id=project.project_id,
    ).ok
    assert project_service.add_material(
        project.project_id,
        project.materials[0],
    ).ok
    session = TimelineCommandService(project_service, project.project_id)
    added = session.add_material("material-1", has_audio=True)
    assert added.ok
    old_group = next(
        clip.link_group_id
        for clip in session.timeline.clips
    )
    assert session.unlink_clip(added.affected_clip_ids[0]).ok

    options = session.relink_candidates(added.affected_clip_ids[0])
    assert [item.clip_id for item in options] == [
        added.affected_clip_ids[1]
    ]
    result = session.relink_clip(
        added.affected_clip_ids[0],
        added.affected_clip_ids[1],
    )

    assert result.ok
    groups = {
        clip.link_group_id
        for clip in session.timeline.clips
    }
    assert len(groups) == 1
    assert None not in groups
    assert old_group not in groups


def test_missing_media_allows_unlink_but_blocks_relink_options(
    tmp_path: Path,
) -> None:
    source = tmp_path / "missing.mp4"
    project = _project(source)
    timeline = _linked_timeline()
    source.unlink()
    service = TimelineEditService()

    unlinked = service.unlink(timeline, project, "video-clip")

    assert unlinked.valid
    assert unlinked.timeline is not None
    assert service.relink_options(
        unlinked.timeline,
        project,
        "video-clip",
    ) == ()


def test_unlink_save_failure_keeps_original_link_and_history(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.mp4"
    project = _project(source)
    project_service = ProjectLibraryService(
        tmp_path / "projects.json",
        default_root=tmp_path / "projects",
    )
    created = project_service.create_project(
        name=project.name,
        project_id=project.project_id,
    )
    assert created.ok and created.path is not None
    assert project_service.add_material(
        project.project_id,
        project.materials[0],
    ).ok
    session = TimelineCommandService(project_service, project.project_id)
    added = session.add_material("material-1", has_audio=True)
    assert added.ok
    before = session.timeline
    before_undo = session.undo_depth

    with patch(
        "services.project_library.save_project",
        return_value=ProjectWriteResult(
            False,
            created.path,
            stage="write",
            error="injected unlink failure",
        ),
    ):
        failed = session.unlink_clip(added.affected_clip_ids[0])

    assert not failed.ok
    assert session.timeline == before
    assert session.undo_depth == before_undo
    assert session.has_pending_save
    assert session.discard_pending_save().ok
    assert session.timeline == before


def test_relink_save_failure_keeps_unlinked_state_and_history(
    tmp_path: Path,
) -> None:
    session, clip_ids, project_path = _command_session(tmp_path)
    assert session.unlink_clip(clip_ids[0]).ok
    before = session.timeline
    before_file = project_path.read_bytes()
    before_undo = session.undo_depth

    with patch(
        "services.project_library.save_project",
        return_value=ProjectWriteResult(
            False,
            project_path,
            stage="write",
            error="injected relink failure",
        ),
    ):
        failed = session.relink_clip(clip_ids[0], clip_ids[1])

    assert not failed.ok
    assert session.timeline == before
    assert session.undo_depth == before_undo
    assert project_path.read_bytes() == before_file
    assert session.has_pending_save
    assert session.discard_pending_save().ok
    assert session.timeline == before


def test_unlinked_move_changes_only_selected_clip(tmp_path: Path) -> None:
    session, clip_ids, _project_path = _command_session(tmp_path)
    assert session.unlink_clip(clip_ids[0]).ok
    other_before = next(
        clip
        for clip in session.timeline.clips
        if clip.clip_id == clip_ids[1]
    )

    moved = session.move_clip(
        clip_ids[0],
        timeline_start_us=1_000_000,
    )

    assert moved.ok
    clips = {clip.clip_id: clip for clip in session.timeline.clips}
    assert clips[clip_ids[0]].timeline_start_us == 1_000_000
    assert clips[clip_ids[1]] == other_before


def test_unlinked_trim_changes_only_selected_clip(tmp_path: Path) -> None:
    session, clip_ids, _project_path = _command_session(tmp_path)
    initial = session.preview_trim_clip(
        clip_ids[0],
        source_start_us=0,
        source_end_us=8_000_000,
    )
    assert session.commit_edit_candidate(initial).ok
    assert session.unlink_clip(clip_ids[0]).ok
    other_before = next(
        clip
        for clip in session.timeline.clips
        if clip.clip_id == clip_ids[1]
    )

    shifted = session.preview_trim_clip(
        clip_ids[0],
        source_start_us=1_000_000,
        source_end_us=9_000_000,
    )
    result = session.commit_edit_candidate(shifted)

    assert shifted.valid
    assert result.ok
    clips = {clip.clip_id: clip for clip in session.timeline.clips}
    assert clips[clip_ids[0]].source_start_us == 1_000_000
    assert clips[clip_ids[1]] == other_before


def test_unlinked_split_changes_only_selected_clip(tmp_path: Path) -> None:
    session, clip_ids, _project_path = _command_session(tmp_path)
    assert session.unlink_clip(clip_ids[0]).ok
    other_before = next(
        clip
        for clip in session.timeline.clips
        if clip.clip_id == clip_ids[1]
    )

    candidate = session.preview_split_clip(
        clip_ids[0],
        playhead_us=5_000_000,
    )
    result = session.commit_edit_candidate(candidate)

    assert candidate.valid
    assert result.ok
    clips = session.timeline.clips
    assert sum(clip.track_id == other_before.track_id for clip in clips) == 1
    assert next(
        clip for clip in clips if clip.clip_id == clip_ids[1]
    ) == other_before
    assert sum(
        clip.material_id == "material-1"
        and clip.track_id != other_before.track_id
        for clip in clips
    ) == 2


def test_unlinked_ripple_delete_preflight_targets_only_selected_side(
    tmp_path: Path,
) -> None:
    session, clip_ids, _project_path = _command_session(tmp_path)
    assert session.unlink_clip(clip_ids[0]).ok

    candidate = session.preview_ripple_delete(clip_ids[0])

    assert not candidate.valid
    assert candidate.impact.target_clip_ids == (clip_ids[0],)
    assert clip_ids[1] not in candidate.impact.target_clip_ids
    assert any(
        conflict.code == "crosses_delete_range"
        and clip_ids[1] in conflict.clip_ids
        for conflict in candidate.conflicts
    )


def test_fifty_unlink_relink_and_history_cycles_preserve_clip_identity(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.mp4"
    project = _project(source)
    project_service = ProjectLibraryService(
        tmp_path / "projects.json",
        default_root=tmp_path / "projects",
    )
    assert project_service.create_project(
        name=project.name,
        project_id=project.project_id,
    ).ok
    assert project_service.add_material(
        project.project_id,
        project.materials[0],
    ).ok
    session = TimelineCommandService(project_service, project.project_id)
    added = session.add_material("material-1", has_audio=True)
    assert added.ok
    immutable_fields = {
        clip.clip_id: (
            clip.material_id,
            clip.track_id,
            clip.timeline_start_us,
            clip.timeline_duration_us,
            clip.source_start_us,
            clip.source_duration_us,
            copy.deepcopy(clip.extensions),
            copy.deepcopy(clip.unknown_fields),
        )
        for clip in session.timeline.clips
    }

    for _ in range(50):
        assert session.unlink_clip(added.affected_clip_ids[0]).ok
        assert session.undo().ok
        assert session.redo().ok
        assert session.relink_clip(
            added.affected_clip_ids[0],
            added.affected_clip_ids[1],
        ).ok

    current = session.timeline
    assert all(clip.link_group_id for clip in current.clips)
    assert len({clip.link_group_id for clip in current.clips}) == 1
    assert {
        clip.clip_id: (
            clip.material_id,
            clip.track_id,
            clip.timeline_start_us,
            clip.timeline_duration_us,
            clip.source_start_us,
            clip.source_duration_us,
            clip.extensions,
            clip.unknown_fields,
        )
        for clip in current.clips
    } == immutable_fields
