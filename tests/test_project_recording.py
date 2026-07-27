from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from services.project_library import ProjectLibraryService
from services.project_recording import (
    ProjectRecordingContext,
    ProjectRecordingCoordinator,
)
from services.recording_library import RecordingLibraryService


def _services(base: Path):
    projects = ProjectLibraryService(
        base / "projects.json",
        default_root=base / "projects",
    )
    library = RecordingLibraryService(base / "recordings.json")
    assert projects.create_project(name="录制项目", project_id="project-1").ok
    return projects, library


def _add_material(
    base: Path,
    library: RecordingLibraryService,
    material_id: str = "material-1",
) -> Path:
    video = base / "视频.mp4"
    video.write_bytes(b"video")
    assert library.add_recording(
        video,
        item_id=material_id,
        metadata={
            "mode": "fullscreen",
            "audio_source": "both",
            "duration_sec": 3.0,
            "width": 1920,
            "height": 1080,
            "fps": 120,
        },
        diagnostic_dir=None,
    ).ok
    return video


def test_project_recording_context_accepts_three_existing_modes():
    assert [
        ProjectRecordingContext("project-1", mode).mode
        for mode in ("fullscreen", "region", "window")
    ] == ["fullscreen", "region", "window"]


def test_link_material_adds_global_material_snapshot_to_active_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects, library = _services(base)
        _add_material(base, library)
        coordinator = ProjectRecordingCoordinator(projects, library)

        result = coordinator.link_material(
            "project-1",
            "material-1",
            now="2026-07-26T12:00:00+08:00",
        )
        loaded = projects.get_project("project-1").project

        assert result.ok
        assert loaded.materials[0].material_id == "material-1"
        assert loaded.materials[0].metadata_snapshot["fps"] == 120


def test_link_material_is_idempotent():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects, library = _services(base)
        _add_material(base, library)
        coordinator = ProjectRecordingCoordinator(projects, library)

        first = coordinator.link_material("project-1", "material-1")
        second = coordinator.link_material("project-1", "material-1")

        assert first.ok and second.ok
        assert second.duplicate
        assert len(projects.get_project("project-1").project.materials) == 1


def test_link_material_rejects_archived_or_missing_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects, library = _services(base)
        _add_material(base, library)
        coordinator = ProjectRecordingCoordinator(projects, library)

        assert projects.archive_project("project-1").ok
        archived = coordinator.link_material("project-1", "material-1")
        entry_path = Path(projects.list_entries()[0].file_path)
        entry_path.unlink()
        missing = coordinator.link_material("project-1", "material-1")

        assert not archived.ok
        assert archived.stage == "project_read_only"
        assert not missing.ok
        assert missing.stage == "project_missing"


def test_link_material_reports_material_missing_and_project_write_failure():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects, library = _services(base)
        coordinator = ProjectRecordingCoordinator(projects, library)

        missing = coordinator.link_material("project-1", "missing")
        _add_material(base, library)
        with patch.object(projects, "add_material") as add:
            add.return_value.ok = False
            add.return_value.stage = "project"
            add.return_value.error = "write denied"
            failed = coordinator.link_material("project-1", "material-1")

        assert not missing.ok
        assert missing.stage == "material_missing"
        assert not failed.ok
        assert failed.stage == "project"
