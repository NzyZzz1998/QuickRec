from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from services.project_library import ProjectLibraryService  # noqa: E402
from ui.project_page import ProjectPage  # noqa: E402
from utils.project_store import (  # noqa: E402
    ProjectFile,
    ProjectIndexEntry,
    ProjectMaterialRef,
    save_project,
    save_project_index,
)

APP = QApplication.instance() or QApplication([])


def _project(
    project_id: str,
    *,
    materials: list[ProjectMaterialRef] | None = None,
) -> ProjectFile:
    return ProjectFile(
        project_id=project_id,
        name=f"项目 {project_id}",
        description="性能夹具",
        created_at="2026-07-26T10:00:00+08:00",
        updated_at="2026-07-26T10:00:00+08:00",
        materials=materials or [],
    )


def test_first_project_page_display_with_100_projects_completes_under_one_second():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        entries: list[ProjectIndexEntry] = []
        for index in range(100):
            project = _project(f"project-{index:03d}")
            path = base / "projects" / project.project_id / "project.qrproj"
            assert save_project(path, project).ok
            entries.append(ProjectIndexEntry.from_project(project, path))
        index_path = base / "projects.json"
        assert save_project_index(index_path, entries).ok
        service = ProjectLibraryService(index_path)

        started = time.perf_counter()
        page = ProjectPage(service)
        elapsed = time.perf_counter() - started

        assert page._project_list.count() == 8
        assert elapsed < 1.0


def test_open_project_with_200_material_references_completes_under_one_second():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        refs = [
            ProjectMaterialRef(
                material_id=f"material-{index:03d}",
                last_known_path=str(base / "videos" / f"素材 {index:03d}.mp4"),
                file_name=f"素材 {index:03d}.mp4",
                added_at="2026-07-26T10:10:00+08:00",
            )
            for index in range(200)
        ]
        project = _project("project-200", materials=refs)
        project_path = base / "projects" / "project-200" / "project.qrproj"
        assert save_project(project_path, project).ok
        index_path = base / "projects.json"
        assert save_project_index(
            index_path,
            [ProjectIndexEntry.from_project(project, project_path)],
        ).ok

        started = time.perf_counter()
        page = ProjectPage(ProjectLibraryService(index_path))
        page._select_project("project-200")
        elapsed = time.perf_counter() - started

        assert page._material_table.rowCount() == 200
        assert elapsed < 1.0


def test_ordinary_project_rename_returns_feedback_under_500_ms():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        assert service.create_project(name="待重命名", project_id="project-1").ok

        started = time.perf_counter()
        result = service.rename_project("project-1", "已重命名")
        elapsed = time.perf_counter() - started

        assert result.ok
        assert elapsed < 0.5
