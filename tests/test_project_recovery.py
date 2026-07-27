from __future__ import annotations

import tempfile
from pathlib import Path

from services.project_library import ProjectLibraryService
from utils.project_store import ProjectFile, load_project, save_project


def _project(project_id: str, name: str = "项目") -> ProjectFile:
    return ProjectFile(
        project_id=project_id,
        name=name,
        description="",
        created_at="2026-07-26T10:00:00+08:00",
        updated_at="2026-07-26T10:00:00+08:00",
    )


def test_relink_missing_project_rejects_wrong_project_id_without_changing_index():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="原项目", project_id="expected")
        assert created.ok
        original_path = service.list_entries()[0].file_path
        created.path.unlink()
        candidate = base / "moved" / "project.qrproj"
        assert save_project(candidate, _project("other")).ok

        result = service.relink_project("expected", candidate)

        assert not result.ok
        assert result.stage == "project_id_mismatch"
        assert service.list_entries()[0].file_path == original_path


def test_relink_missing_project_accepts_matching_project_and_updates_index():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="原项目", project_id="expected")
        assert created.ok
        created.path.unlink()
        candidate = base / "移动 后" / "project.qrproj"
        assert save_project(candidate, _project("expected", "移动后的项目")).ok

        result = service.relink_project("expected", candidate)

        assert result.ok
        assert service.list_entries()[0].file_path == str(candidate)
        assert service.get_project("expected").project.name == "移动后的项目"


def test_recover_corrupt_project_from_valid_backup_updates_index():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="初始", project_id="project-1")
        assert created.ok
        assert service.rename_project("project-1", "备份版本").ok
        created.path.write_text("{broken", encoding="utf-8")

        result = service.recover_project("project-1")
        loaded = service.get_project("project-1")

        assert result.ok
        assert loaded.ok
        assert loaded.project.project_id == "project-1"
        assert result.project is not None
        assert result.project.name == "初始"
        assert result.path.with_name("project.qrproj.bak").is_file()


def test_corrupt_project_without_backup_can_be_removed_from_index_only():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="损坏", project_id="project-1")
        assert created.ok
        created.path.with_name("project.qrproj.bak").unlink(missing_ok=True)
        created.path.write_text("{broken", encoding="utf-8")

        result = service.remove_project_entry("project-1")

        assert result.ok
        assert created.path.read_text(encoding="utf-8") == "{broken"
        assert service.list_entries() == []


def test_reload_external_project_refreshes_fingerprint_before_next_write():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="原名称", project_id="project-1")
        assert created.ok
        external = load_project(created.path).project
        external.name = "外部名称"
        external.updated_at = "2026-07-26T12:00:00+08:00"
        assert save_project(created.path, external).ok

        conflict = service.rename_project("project-1", "不应覆盖")
        refreshed = service.reload_project("project-1")
        renamed = service.rename_project("project-1", "重新编辑")

        assert not conflict.ok
        assert conflict.stage == "external_conflict"
        assert refreshed.ok
        assert refreshed.project.name == "外部名称"
        assert renamed.ok
