from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from services.project_editing_profile import EDITING_EXTENSION_KEY
from services.project_library import (
    ProjectLibraryService,
    ProjectOperationResult,
)
from services.timeline_commands import TimelineCommandService
from utils.project_store import ProjectMaterialRef, load_project


def _service(tmp_path: Path) -> ProjectLibraryService:
    return ProjectLibraryService(
        tmp_path / "projects.json",
        default_root=tmp_path / "projects",
    )


def _add_material(
    service: ProjectLibraryService,
    *,
    fps: float = 59.94,
) -> None:
    result = service.add_material(
        "project-1",
        ProjectMaterialRef(
            "material-1",
            str(Path(r"E:\素材") / "项目 视频.mp4"),
            "项目 视频.mp4",
            "2026-07-30T10:00:00+08:00",
            {
                "duration_sec": 2.0,
                "fps": fps,
                "audio_source": "none",
            },
        ),
    )
    assert result.ok


def _legacy_project_with_clip(
    tmp_path: Path,
) -> tuple[ProjectLibraryService, Path]:
    service = _service(tmp_path)
    created = service.create_project(
        name="旧项目",
        project_id="project-1",
        editing_fps=30,
    )
    assert created.ok
    _add_material(service)
    initial = TimelineCommandService(service, "project-1")
    assert initial.add_material("material-1", has_audio=False).ok
    project_result = service.get_project("project-1")
    assert project_result.ok and project_result.project is not None
    legacy = project_result.project
    legacy.extensions.pop(EDITING_EXTENSION_KEY)
    assert service.commit_project_candidate("project-1", legacy).ok
    return service, created.path


def test_opening_legacy_project_infers_fps_without_writing_disk(
    tmp_path: Path,
) -> None:
    service, project_path = _legacy_project_with_clip(tmp_path)
    before = project_path.read_bytes()

    session = TimelineCommandService(service, "project-1")

    assert session.editing_fps == 60
    assert session.editing_fps_locked
    assert not session.editing_profile_persisted
    assert project_path.read_bytes() == before


def test_first_successful_legacy_edit_persists_inferred_profile_atomically(
    tmp_path: Path,
) -> None:
    service, project_path = _legacy_project_with_clip(tmp_path)
    session = TimelineCommandService(service, "project-1")
    track = session.timeline.tracks[0]

    result = session.rename_track(track.track_id, "画面主轨")
    persisted = load_project(project_path)

    assert result.ok and result.saved
    assert persisted.ok and persisted.project is not None
    assert persisted.project.extensions[EDITING_EXTENSION_KEY] == {
        "schema_version": 1,
        "editing_fps": 60,
        "fps_locked": True,
    }
    assert session.editing_profile_persisted


def test_unknown_editing_profile_schema_makes_timeline_read_only(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    assert service.create_project(
        name="未来项目",
        project_id="project-1",
    ).ok
    loaded = service.get_project("project-1")
    assert loaded.ok and loaded.project is not None
    project = loaded.project
    project.extensions[EDITING_EXTENSION_KEY] = {
        "schema_version": 99,
        "editing_fps": 60,
        "future": "keep",
    }
    assert service.commit_project_candidate("project-1", project).ok

    session = TimelineCommandService(service, "project-1")
    result = session.add_track("video")

    assert session.ready
    assert session.read_only
    assert session.editing_profile_status == "unsupported"
    assert not result.ok
    assert result.stage == "read_only"


def test_empty_timeline_can_change_fps_then_content_locks_it_permanently(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    assert service.create_project(
        name="新项目",
        project_id="project-1",
    ).ok
    _add_material(service, fps=120)
    session = TimelineCommandService(service, "project-1")

    changed = session.set_editing_fps(60)
    added = session.add_material("material-1", has_audio=False)
    clip_id = added.affected_clip_ids[0]
    blocked = session.set_editing_fps(120)
    deleted = session.delete_clip(clip_id)
    session.reload()

    assert changed.ok and changed.saved
    assert added.ok
    assert not blocked.ok and blocked.stage == "locked"
    assert deleted.ok
    assert session.timeline.clips == []
    assert session.editing_fps == 60
    assert session.editing_fps_locked


def test_editing_fps_save_failure_keeps_original_memory_value(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(
        name="保存失败项目",
        project_id="project-1",
    )
    assert created.ok
    session = TimelineCommandService(service, "project-1")
    failure = ProjectOperationResult(
        False,
        "project",
        created.path,
        error="write denied",
    )

    with patch.object(
        service,
        "commit_project_candidate",
        return_value=failure,
    ):
        result = session.set_editing_fps(60)

    assert not result.ok
    assert session.editing_fps == 30
    assert session.has_pending_save
