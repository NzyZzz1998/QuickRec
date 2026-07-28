import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.project_library import ProjectLibraryService
from utils.project_store import (
    PROJECT_FILE_NAME,
    ProjectFile,
    ProjectMaterialRef,
    load_project,
    load_project_index,
    save_project,
)


class TestProjectLibraryService(unittest.TestCase):
    def test_create_project_writes_file_and_central_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "项目 根目录"
            index_path = Path(temp_dir) / "AppData" / "QuickRec" / "projects.json"
            service = ProjectLibraryService(index_path)

            result = service.create_project(
                name=" 教程项目 ",
                description="说明",
                root_path=root,
                project_id="project-1",
                now="2026-07-26T10:00:00+08:00",
            )
            loaded = load_project(root / "project-1" / PROJECT_FILE_NAME)
            index = load_project_index(index_path)

        self.assertTrue(result.ok)
        self.assertTrue(result.project_written)
        self.assertTrue(result.index_written)
        self.assertEqual(loaded.project.name, "教程项目")
        self.assertEqual(index.entries[0].project_id, "project-1")

    def test_create_project_supports_custom_root_without_mutating_service_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            default_root = Path(temp_dir) / "default"
            custom_root = Path(temp_dir) / "custom"
            service = ProjectLibraryService(
                Path(temp_dir) / "projects.json",
                default_root=default_root,
            )

            result = service.create_project(
                name="自定义位置",
                root_path=custom_root,
                project_id="custom-project",
                now="2026-07-26T10:00:00+08:00",
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.path.parent, custom_root / "custom-project")
        self.assertEqual(service.default_root, default_root)

    def test_create_project_reports_partial_success_when_index_write_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            service = ProjectLibraryService(Path(temp_dir) / "projects.json")

            with patch(
                "services.project_library.save_project_index",
                side_effect=OSError("index denied"),
            ):
                result = service.create_project(
                    name="部分成功",
                    root_path=root,
                    project_id="project-partial",
                    now="2026-07-26T10:00:00+08:00",
                )

            project_path = root / "project-partial" / PROJECT_FILE_NAME

            self.assertFalse(result.ok)
            self.assertTrue(result.project_written)
            self.assertFalse(result.index_written)
            self.assertEqual(result.stage, "index")
            self.assertTrue(project_path.is_file())

    def test_register_same_id_new_path_requires_explicit_update(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ProjectLibraryService(Path(temp_dir) / "projects.json")
            first = Path(temp_dir) / "first" / PROJECT_FILE_NAME
            second = Path(temp_dir) / "second" / PROJECT_FILE_NAME
            self.assertTrue(save_project(first, self._project()).ok)
            self.assertTrue(save_project(second, self._project()).ok)
            self.assertTrue(service.register_project(first).ok)

            conflict = service.register_project(second)
            updated = service.register_project(second, update_existing_path=True)
            entries = service.list_entries()

        self.assertFalse(conflict.ok)
        self.assertEqual(conflict.stage, "path_conflict")
        self.assertEqual(conflict.conflict_path, first)
        self.assertTrue(updated.ok)
        self.assertEqual(entries[0].file_path, str(second))

    def test_rename_preserves_project_id_and_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, project_path = self._created_service(temp_dir)

            result = service.rename_project(
                "project-1",
                " 新名称 ",
                now="2026-07-26T11:00:00+08:00",
            )
            loaded = load_project(project_path)

        self.assertTrue(result.ok)
        self.assertEqual(result.path, project_path)
        self.assertEqual(loaded.project.project_id, "project-1")
        self.assertEqual(loaded.project.name, "新名称")

    def test_update_details_changes_name_and_description_together(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, project_path = self._created_service(temp_dir)

            result = service.update_project_details(
                "project-1",
                name=" 更新后的项目 ",
                description="新的项目说明",
                now="2026-07-26T11:00:00+08:00",
            )
            loaded = load_project(project_path)

        self.assertTrue(result.ok)
        self.assertEqual(loaded.project.name, "更新后的项目")
        self.assertEqual(loaded.project.description, "新的项目说明")
        self.assertEqual(loaded.project.project_id, "project-1")

    def test_archive_and_restore_update_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, project_path = self._created_service(temp_dir)

            archived = service.archive_project(
                "project-1",
                now="2026-07-26T11:00:00+08:00",
            )
            archived_file = load_project(project_path)
            restored = service.restore_project(
                "project-1",
                now="2026-07-26T12:00:00+08:00",
            )
            restored_file = load_project(project_path)

        self.assertTrue(archived.ok)
        self.assertEqual(archived_file.project.archived_at, "2026-07-26T11:00:00+08:00")
        self.assertTrue(restored.ok)
        self.assertIsNone(restored_file.project.archived_at)

    def test_failed_project_save_keeps_original_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, project_path = self._created_service(temp_dir)
            before = project_path.read_bytes()

            with patch(
                "services.project_library.save_project",
                side_effect=OSError("write denied"),
            ):
                result = service.archive_project(
                    "project-1",
                    now="2026-07-26T11:00:00+08:00",
                )

            after = project_path.read_bytes()

        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "project")
        self.assertEqual(before, after)

    def test_index_failure_rolls_back_project_candidate_exactly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, project_path = self._created_service(temp_dir)
            before = project_path.read_bytes()
            loaded = service.get_project("project-1")
            self.assertTrue(loaded.ok)
            candidate = loaded.project
            candidate.name = "不能留下"

            with patch(
                "services.project_library.save_project_index",
                side_effect=OSError("index denied"),
            ):
                result = service.commit_project_candidate(
                    "project-1",
                    candidate,
                )

            after = project_path.read_bytes()

        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "index")
        self.assertTrue(result.rolled_back)
        self.assertEqual(after, before)

    def test_external_modification_blocks_silent_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, project_path = self._created_service(temp_dir)
            payload = project_path.read_text(encoding="utf-8")
            project_path.write_text(payload + "\n", encoding="utf-8")

            result = service.rename_project(
                "project-1",
                "不应覆盖",
                now="2026-07-26T11:00:00+08:00",
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "external_conflict")

    def test_add_material_is_idempotent_per_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, project_path = self._created_service(temp_dir)
            ref = self._ref("material-1")

            first = service.add_material("project-1", ref)
            second = service.add_material("project-1", ref)
            loaded = load_project(project_path)

        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertTrue(second.duplicate)
        self.assertEqual(len(loaded.project.materials), 1)

    def test_same_material_can_belong_to_multiple_projects(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            index = Path(temp_dir) / "projects.json"
            service = ProjectLibraryService(index)
            for project_id in ("project-1", "project-2"):
                self.assertTrue(
                    service.create_project(
                        name=project_id,
                        root_path=Path(temp_dir) / "root",
                        project_id=project_id,
                        now="2026-07-26T10:00:00+08:00",
                    ).ok
                )

            ref = self._ref("material-shared")
            first = service.add_material("project-1", ref)
            second = service.add_material("project-2", ref)
            states = service.classify_material_references(["material-shared"])

        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertEqual(states.states["material-shared"], "shared")

    def test_remove_material_only_changes_target_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            index = Path(temp_dir) / "projects.json"
            service = ProjectLibraryService(index)
            for project_id in ("project-1", "project-2"):
                self.assertTrue(
                    service.create_project(
                        name=project_id,
                        root_path=Path(temp_dir) / "root",
                        project_id=project_id,
                        now="2026-07-26T10:00:00+08:00",
                    ).ok
                )
                self.assertTrue(service.add_material(project_id, self._ref("material-1")).ok)

            removed = service.remove_material("project-1", "material-1")
            first = service.get_project("project-1")
            second = service.get_project("project-2")

        self.assertTrue(removed.ok)
        self.assertEqual(first.project.materials, [])
        self.assertEqual([item.material_id for item in second.project.materials], ["material-1"])

    def test_archived_project_rejects_content_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, _project_path = self._created_service(temp_dir)
            self.assertTrue(service.archive_project("project-1").ok)

            renamed = service.rename_project("project-1", "不能改")
            added = service.add_material("project-1", self._ref("material-1"))

        self.assertFalse(renamed.ok)
        self.assertEqual(renamed.stage, "read_only")
        self.assertFalse(added.ok)
        self.assertEqual(added.stage, "read_only")

    def test_unreadable_project_makes_single_reference_uncertain(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, _project_path = self._created_service(temp_dir)
            self.assertTrue(service.add_material("project-1", self._ref("material-1")).ok)
            missing = service.create_project(
                name="稍后缺失",
                root_path=Path(temp_dir) / "root",
                project_id="project-missing",
            )
            self.assertTrue(missing.ok)
            missing.path.unlink()

            states = service.classify_material_references(["material-1"])

        self.assertEqual(states.states["material-1"], "uncertain")
        self.assertEqual(states.unreadable_project_ids, ("project-missing",))

    def test_single_reference_is_exclusive_when_all_projects_readable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, _project_path = self._created_service(temp_dir)
            self.assertTrue(service.add_material("project-1", self._ref("material-1")).ok)

            states = service.classify_material_references(["material-1", "unknown"])

        self.assertEqual(states.states["material-1"], "exclusive")
        self.assertEqual(states.states["unknown"], "uncertain")

    @classmethod
    def _created_service(cls, temp_dir: str):
        service = ProjectLibraryService(Path(temp_dir) / "projects.json")
        created = service.create_project(
            name="示例项目",
            root_path=Path(temp_dir) / "root",
            project_id="project-1",
            now="2026-07-26T10:00:00+08:00",
        )
        if not created.ok:
            raise AssertionError(created.error)
        return service, created.path

    @staticmethod
    def _project() -> ProjectFile:
        return ProjectFile(
            project_id="project-1",
            name="项目",
            description="",
            created_at="2026-07-26T10:00:00+08:00",
            updated_at="2026-07-26T10:00:00+08:00",
        )

    @staticmethod
    def _ref(material_id: str) -> ProjectMaterialRef:
        return ProjectMaterialRef(
            material_id=material_id,
            last_known_path=rf"E:\QRtest\{material_id}.mp4",
            file_name=f"{material_id}.mp4",
            added_at="2026-07-26T10:30:00+08:00",
            metadata_snapshot={"fps": 60},
        )


if __name__ == "__main__":
    unittest.main()
