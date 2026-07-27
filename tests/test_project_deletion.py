from __future__ import annotations

import tempfile
from pathlib import Path

from services.project_deletion import ProjectDeletionCoordinator
from services.project_library import ProjectLibraryService, ProjectOperationResult
from services.recording_library import RecordingLibraryService
from utils.project_store import ProjectMaterialRef
from utils.recording_library_store import LibraryWriteResult, MaterialItem
from utils.recycle_bin import RecycleResult


def _material(base: Path, material_id: str) -> MaterialItem:
    path = base / "视频" / f"{material_id}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"video")
    return MaterialItem(
        id=material_id,
        file_path=str(path),
        file_name=path.name,
        directory=str(path.parent),
        mode="fullscreen",
        audio_source="none",
        created_at="2026-07-26T10:00:00+08:00",
    )


def _ref(material: MaterialItem) -> ProjectMaterialRef:
    return ProjectMaterialRef(
        material_id=material.id,
        last_known_path=material.file_path,
        file_name=material.file_name,
        added_at="2026-07-26T10:10:00+08:00",
    )


def _services(base: Path):
    projects = ProjectLibraryService(
        base / "projects.json",
        default_root=base / "projects",
    )
    materials = RecordingLibraryService(base / "recordings.json")
    created = projects.create_project(name="待删除", project_id="project-1")
    assert created.ok
    return projects, materials, created.path


def test_delete_plan_defaults_to_no_selected_videos():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects, materials, _project_path = _services(base)
        material = _material(base, "exclusive")
        assert materials.add(material).ok
        assert projects.add_material("project-1", _ref(material)).ok
        coordinator = ProjectDeletionCoordinator(projects, materials)

        plan = coordinator.build_plan("project-1")

        assert plan.ok
        assert len(plan.materials) == 1
        assert plan.materials[0].state == "exclusive"
        assert plan.materials[0].selectable
        assert plan.selected_ids == ()


def test_shared_and_uncertain_materials_cannot_be_selected_for_delete():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects, materials, _project_path = _services(base)
        material = _material(base, "shared")
        assert materials.add(material).ok
        assert projects.add_material("project-1", _ref(material)).ok
        assert projects.create_project(name="共享项目", project_id="project-2").ok
        assert projects.add_material("project-2", _ref(material)).ok
        coordinator = ProjectDeletionCoordinator(projects, materials)

        plan = coordinator.build_plan("project-1")
        result = coordinator.execute(plan, selected_material_ids=["shared"])

        assert plan.materials[0].state == "shared"
        assert not plan.materials[0].selectable
        assert not result.ok
        assert result.stage == "validate_selection"
        assert projects.get_project("project-1").ok


def test_delete_project_without_selected_videos_preserves_video_and_global_index():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects, materials, project_path = _services(base)
        material = _material(base, "keep")
        assert materials.add(material).ok
        assert projects.add_material("project-1", _ref(material)).ok
        recycled_projects: list[Path] = []
        coordinator = ProjectDeletionCoordinator(
            projects,
            materials,
            recycle_project=lambda path: (
                recycled_projects.append(path),
                RecycleResult(True, path),
            )[1],
        )

        result = coordinator.execute(
            coordinator.build_plan("project-1"),
            selected_material_ids=[],
        )

        assert result.ok
        assert recycled_projects == [project_path]
        assert Path(material.file_path).is_file()
        assert materials.find_existing(item_id=material.id) is not None
        assert projects.list_entries() == []


def test_exclusive_selected_video_is_recycled_before_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects, materials, project_path = _services(base)
        material = _material(base, "delete")
        assert materials.add(material).ok
        assert projects.add_material("project-1", _ref(material)).ok
        calls: list[tuple[str, str]] = []

        def recycle_material(material_id: str) -> LibraryWriteResult:
            calls.append(("material", material_id))
            return LibraryWriteResult(True, materials.library_path)

        def recycle_project(path: Path) -> RecycleResult:
            calls.append(("project", str(path)))
            return RecycleResult(True, path)

        coordinator = ProjectDeletionCoordinator(
            projects,
            materials,
            recycle_material=recycle_material,
            recycle_project=recycle_project,
        )
        result = coordinator.execute(
            coordinator.build_plan("project-1"),
            selected_material_ids=["delete"],
        )

        assert result.ok
        assert calls == [
            ("material", "delete"),
            ("project", str(project_path)),
        ]
        assert projects.list_entries() == []


def test_partial_video_recycle_failure_keeps_project_and_skips_project_recycle():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects, materials, _project_path = _services(base)
        for material_id in ("one", "two"):
            material = _material(base, material_id)
            assert materials.add(material).ok
            assert projects.add_material("project-1", _ref(material)).ok
        project_calls: list[Path] = []

        def recycle_material(material_id: str) -> LibraryWriteResult:
            return LibraryWriteResult(
                material_id == "one",
                materials.library_path,
                error="" if material_id == "one" else "recycle denied",
            )

        coordinator = ProjectDeletionCoordinator(
            projects,
            materials,
            recycle_material=recycle_material,
            recycle_project=lambda path: (
                project_calls.append(path),
                RecycleResult(True, path),
            )[1],
        )
        result = coordinator.execute(
            coordinator.build_plan("project-1"),
            selected_material_ids=["one", "two"],
        )

        assert not result.ok
        assert result.stage == "material_recycle"
        assert project_calls == []
        assert projects.get_project("project-1").ok


def test_project_recycle_success_but_index_failure_reports_partial_result():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        projects, materials, project_path = _services(base)
        coordinator = ProjectDeletionCoordinator(
            projects,
            materials,
            recycle_project=lambda path: RecycleResult(True, path),
        )
        projects.remove_project_entry = lambda project_id: ProjectOperationResult(
            False,
            "index",
            projects.index_path,
            error="index denied",
        )

        result = coordinator.execute(
            coordinator.build_plan("project-1"),
            selected_material_ids=[],
        )

        assert not result.ok
        assert result.stage == "index"
        assert result.project_recycled
        assert not result.index_removed
        assert result.project_path == project_path
