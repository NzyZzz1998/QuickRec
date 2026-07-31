from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from exporting.models import ExportMaterialProbe, ExportPlanRequest
from exporting.plan_builder import ExportPlanBuilder
from services.project_library import ProjectLibraryService
from services.timeline_commands import TimelineCommandService
from services.timeline_frame_time import frame_to_microseconds
from services.timeline_query import build_playback_plan
from utils.project_store import (
    ProjectMaterialRef,
    ProjectWriteResult,
    load_project,
)


def _workspace(
    tmp_path: Path,
    *,
    duration_sec: float = 4.0,
) -> tuple[ProjectLibraryService, Path, Path]:
    media = tmp_path / "素材 目录" / "中文 视频.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"controlled-media")
    service = ProjectLibraryService(
        tmp_path / "projects.json",
        default_root=tmp_path / "projects",
    )
    created = service.create_project(
        name="D7 集成项目",
        project_id="project-d7",
        editing_fps=60,
    )
    assert created.ok and created.path is not None
    assert service.add_material(
        "project-d7",
        ProjectMaterialRef(
            material_id="material-1",
            last_known_path=str(media),
            file_name=media.name,
            added_at="2026-07-30T14:00:00+08:00",
            metadata_snapshot={
                "duration_sec": duration_sec,
                "width": 1280,
                "height": 720,
                "fps": 60.0,
                "has_audio": True,
                "audio_source": "both",
            },
        ),
    ).ok
    loaded = service.get_project("project-d7")
    assert loaded.ok and loaded.project is not None
    project = loaded.project
    project.extensions["future.project"] = {
        "schema_version": 7,
        "payload": {"keep": True},
    }
    assert service.commit_project_candidate("project-d7", project).ok
    return service, created.path, media


def _probe(_path: Path) -> ExportMaterialProbe:
    return ExportMaterialProbe(
        container="mov,mp4,m4a,3gp,3g2,mj2",
        video_codec="h264",
        width=1280,
        height=720,
        fps=60.0,
        duration_us=4_000_000,
        audio_codec="aac",
        audio_sample_rate=48_000,
        audio_channels=2,
        audio_duration_us=4_000_000,
    )


def _export_plan(project_path: Path, output_dir: Path):
    builder = ExportPlanBuilder(
        media_probe=_probe,
        ffmpeg_resolver=lambda: __file__,
        ffprobe_resolver=lambda: __file__,
        free_space_provider=lambda _path: 10 * 1024**3,
        clock=lambda: "2026-07-30T14:00:00+08:00",
        id_factory=lambda: "plan-d7",
    )
    result = builder.build(
        ExportPlanRequest(
            project_path=str(project_path),
            width=1280,
            height=720,
            fps=60,
            output_directory=str(output_dir),
            filename="D7-export.mp4",
        )
    )
    assert result.ok and result.plan is not None
    return result.plan


def test_new_commands_persist_backup_restart_and_unknown_extensions(
    tmp_path: Path,
) -> None:
    service, project_path, _media = _workspace(tmp_path)
    session = TimelineCommandService(service, "project-d7")
    first = session.add_material("material-1", has_audio=True)
    assert first.ok
    assert session.unlink_clip(first.affected_clip_ids[0]).ok
    candidate = session.preview_material_drop(
        "material-1",
        has_video=True,
        has_audio=True,
        raw_start_us=0,
        hovered_track_id=first.affected_track_ids[0],
        playhead_us=0,
        pixels_per_second=100,
        transaction_id="d7-auto-track",
    )
    assert candidate.valid
    assert candidate.auto_track_kinds == ("video", "audio")
    assert session.commit_material_drop(candidate).ok

    restarted = TimelineCommandService(service, "project-d7")
    loaded = load_project(project_path)
    backup = project_path.with_name(f"{project_path.name}.bak")

    assert restarted.editing_fps == 60
    assert {
        clip.link_group_id
        for clip in restarted.timeline.clips
        if clip.clip_id in first.affected_clip_ids
    } == {None}
    assert [
        (track.kind, track.order)
        for track in restarted.timeline.tracks
    ] == [
        (track.kind, track.order)
        for track in candidate.timeline.tracks
    ]
    assert loaded.ok and loaded.project is not None
    assert loaded.project.extensions["future.project"] == {
        "schema_version": 7,
        "payload": {"keep": True},
    }
    assert backup.is_file()
    assert load_project(backup).ok


def test_normal_and_ripple_delete_have_distinct_saved_export_duration(
    tmp_path: Path,
) -> None:
    service, project_path, _media = _workspace(tmp_path)
    session = TimelineCommandService(service, "project-d7")
    first = session.add_material("material-1", has_audio=True)
    second = session.add_material("material-1", has_audio=True)
    assert first.ok and second.ok

    ordinary = session.delete_clip(first.affected_clip_ids[0], confirmed=True)
    ordinary_plan = _export_plan(project_path, tmp_path / "ordinary")

    assert ordinary.ok
    assert ordinary_plan.timeline.duration_us == 8_000_000
    assert {
        clip.timeline_start_us
        for clip in ordinary_plan.timeline.clips
    } == {4_000_000}

    assert session.undo().ok
    ripple_candidate = session.preview_ripple_delete(
        first.affected_clip_ids[0]
    )
    ripple = session.commit_edit_candidate(ripple_candidate)
    ripple_plan = _export_plan(project_path, tmp_path / "ripple")

    assert ripple.ok
    assert ripple_plan.timeline.duration_us == 4_000_000
    assert {
        clip.timeline_start_us
        for clip in ripple_plan.timeline.clips
    } == {0}


def test_failed_unlink_keeps_last_saved_project_for_export(
    tmp_path: Path,
) -> None:
    service, project_path, _media = _workspace(tmp_path)
    session = TimelineCommandService(service, "project-d7")
    added = session.add_material("material-1", has_audio=True)
    assert added.ok
    before = session.timeline
    before_undo = session.undo_depth

    with patch(
        "services.project_library.save_project",
        return_value=ProjectWriteResult(
            False,
            project_path,
            stage="write",
            error="injected D7 save failure",
        ),
    ):
        failed = session.unlink_clip(added.affected_clip_ids[0])

    plan = _export_plan(project_path, tmp_path / "last-saved")

    assert not failed.ok
    assert session.timeline == before
    assert session.undo_depth == before_undo
    assert session.has_pending_save
    assert {clip.link_group_id for clip in plan.timeline.clips} == {
        next(iter({clip.link_group_id for clip in before.clips}))
    }
    assert None not in {clip.link_group_id for clip in plan.timeline.clips}
    assert session.discard_pending_save().ok


def test_unlinked_playback_and_frame_jump_keep_independent_track_semantics(
    tmp_path: Path,
) -> None:
    service, _project_path, _media = _workspace(tmp_path)
    session = TimelineCommandService(service, "project-d7")
    first = session.add_material("material-1", has_audio=True)
    assert first.ok
    assert session.unlink_clip(first.affected_clip_ids[0]).ok
    candidate = session.preview_material_drop(
        "material-1",
        has_video=True,
        has_audio=True,
        raw_start_us=0,
        hovered_track_id=first.affected_track_ids[0],
        playhead_us=0,
        pixels_per_second=100,
        transaction_id="d7-overlap",
    )
    assert candidate.valid
    assert session.commit_material_drop(candidate).ok
    position_us = frame_to_microseconds(30, session.editing_fps)

    plan = build_playback_plan(
        session.project,
        session.timeline,
        position_us,
    )

    assert position_us == 500_000
    assert plan.position_us == position_us
    assert plan.video is not None
    assert plan.video.track.order == 0
    assert plan.video.source_position_us == position_us
    assert len(plan.audio) == 2
    assert {
        clip.clip.link_group_id
        for clip in plan.audio
    } == {None, next(
        clip.link_group_id
        for clip in session.timeline.clips
        if clip.link_group_id is not None
    )}
