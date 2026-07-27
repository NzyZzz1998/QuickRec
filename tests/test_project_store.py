import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.project_store import (
    PROJECT_FILE_NAME,
    ProjectFile,
    ProjectIndexEntry,
    ProjectMaterialRef,
    discover_project_files,
    load_project,
    load_project_index,
    rebuild_project_index,
    recover_project_from_backup,
    resolve_default_project_root,
    resolve_project_file,
    resolve_project_index,
    save_project,
    save_project_index,
)

FIXTURES = Path(__file__).parent / "fixtures" / "v1_9"


class TestProjectStore(unittest.TestCase):
    def test_resolves_default_project_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "用户 家目录"
            appdata = Path(temp_dir) / "Roaming"

            root = resolve_default_project_root(home)
            index = resolve_project_index(appdata)
            project = resolve_project_file(root, "project-1")

        self.assertEqual(root, home / "Videos" / "QuickRec" / "Projects")
        self.assertEqual(index, appdata / "QuickRec" / "projects.json")
        self.assertEqual(project, root / "project-1" / PROJECT_FILE_NAME)

    def test_project_roundtrip_preserves_material_snapshot_and_extensions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "中文 空格" / PROJECT_FILE_NAME
            project = self._project()
            project.extensions["future"] = {"enabled": True}
            project.materials[0].extensions["material_future"] = 1

            written = save_project(path, project)
            loaded = load_project(path)

        self.assertTrue(written.ok)
        self.assertTrue(loaded.ok)
        self.assertEqual(loaded.project, project)
        self.assertEqual(loaded.project.materials[0].metadata_snapshot["fps"], 60)

    def test_index_roundtrip_preserves_entries_and_extensions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "projects.json"
            entry = self._entry(Path(temp_dir) / "项目 A" / PROJECT_FILE_NAME)

            written = save_project_index(path, [entry], extensions={"future": 1})
            loaded = load_project_index(path)

        self.assertTrue(written.ok)
        self.assertTrue(loaded.ok)
        self.assertEqual(loaded.entries, [entry])
        self.assertEqual(loaded.extensions, {"future": 1})

    def test_loads_checked_in_normal_fixture(self):
        result = load_project(FIXTURES / "project_v1_normal.json")

        self.assertTrue(result.ok)
        self.assertEqual(result.project.project_id, "project-normal")
        self.assertEqual(result.project.materials[0].material_id, "material-1")

    def test_rejects_project_missing_required_identity(self):
        result = load_project(FIXTURES / "project_v1_missing_id.json")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "corrupt")
        self.assertIn("project_id", result.error)

    def test_rejects_unsupported_project_schema(self):
        result = load_project(FIXTURES / "project_v99_unsupported.json")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "unsupported")
        self.assertIn("schema", result.error.lower())

    def test_missing_project_has_distinct_status(self):
        result = load_project(FIXTURES / "not-found.qrproj")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "missing")

    def test_atomic_project_write_failure_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / PROJECT_FILE_NAME
            first = self._project(name="first")
            second = self._project(name="second")
            self.assertTrue(save_project(path, first).ok)
            before = path.read_bytes()

            with patch(
                "utils.project_store._atomic_write_json",
                side_effect=OSError("replace denied"),
            ):
                result = save_project(path, second)

            self.assertFalse(result.ok)
            self.assertEqual(result.stage, "write")
            self.assertEqual(path.read_bytes(), before)

    def test_second_project_save_keeps_previous_valid_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / PROJECT_FILE_NAME
            self.assertTrue(save_project(path, self._project(name="first")).ok)
            self.assertTrue(save_project(path, self._project(name="second")).ok)

            backup = load_project(path.with_name(f"{PROJECT_FILE_NAME}.bak"))

        self.assertTrue(backup.ok)
        self.assertEqual(backup.project.name, "first")

    def test_corrupt_project_is_not_silently_replaced_by_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / PROJECT_FILE_NAME
            path.write_text("{broken", encoding="utf-8")
            path.with_name(f"{PROJECT_FILE_NAME}.bak").write_text(
                (FIXTURES / "project_v1_normal.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            loaded = load_project(path)

            self.assertFalse(loaded.ok)
            self.assertEqual(loaded.status, "corrupt")
            self.assertTrue(loaded.backup_available)
            self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_explicit_backup_recovery_archives_corrupt_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / PROJECT_FILE_NAME
            path.write_text("{broken", encoding="utf-8")
            path.with_name(f"{PROJECT_FILE_NAME}.bak").write_text(
                (FIXTURES / "project_v1_normal.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            recovered = recover_project_from_backup(path)
            loaded = load_project(path)
            archives = list(path.parent.glob("project.corrupt-*.qrproj"))

        self.assertTrue(recovered.ok)
        self.assertTrue(loaded.ok)
        self.assertEqual(loaded.project.project_id, "project-normal")
        self.assertEqual(len(archives), 1)

    def test_invalid_backup_does_not_modify_corrupt_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / PROJECT_FILE_NAME
            path.write_text("{main-broken", encoding="utf-8")
            path.with_name(f"{PROJECT_FILE_NAME}.bak").write_text(
                "{backup-broken",
                encoding="utf-8",
            )
            before = path.read_bytes()

            result = recover_project_from_backup(path)

            self.assertFalse(result.ok)
            self.assertEqual(path.read_bytes(), before)

    def test_corrupt_index_recovers_previous_valid_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "projects.json"
            first = self._entry(Path(temp_dir) / "first" / PROJECT_FILE_NAME, "first")
            second = self._entry(Path(temp_dir) / "second" / PROJECT_FILE_NAME, "second")
            self.assertTrue(save_project_index(path, [first]).ok)
            self.assertTrue(save_project_index(path, [second]).ok)
            path.write_text("{broken", encoding="utf-8")

            recovered = load_project_index(path)

        self.assertTrue(recovered.ok)
        self.assertTrue(recovered.recovered)
        self.assertEqual([entry.project_id for entry in recovered.entries], ["first"])

    def test_corrupt_index_without_backup_is_preserved_and_archived(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "projects.json"
            path.write_text("{broken", encoding="utf-8")

            loaded = load_project_index(path)
            archives = list(path.parent.glob("projects.corrupt-*.json"))

            self.assertFalse(loaded.ok)
            self.assertEqual(path.read_text(encoding="utf-8"), "{broken")
            self.assertEqual(len(archives), 1)

    def test_index_rejects_duplicate_project_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "projects.json"
            first = self._entry(Path(temp_dir) / "first" / PROJECT_FILE_NAME)
            duplicate = self._entry(Path(temp_dir) / "second" / PROJECT_FILE_NAME)

            result = save_project_index(path, [first, duplicate])

        self.assertFalse(result.ok)
        self.assertIn("duplicate project_id", result.error)

    def test_discovery_skips_corrupt_and_deduplicates_project_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid = root / "A" / PROJECT_FILE_NAME
            duplicate = root / "B" / PROJECT_FILE_NAME
            corrupt = root / "C" / PROJECT_FILE_NAME
            self.assertTrue(save_project(valid, self._project()).ok)
            self.assertTrue(save_project(duplicate, self._project()).ok)
            corrupt.parent.mkdir(parents=True)
            corrupt.write_text("{broken", encoding="utf-8")

            result = discover_project_files([root])

        self.assertEqual(result.scanned_count, 3)
        self.assertEqual(len(result.projects), 1)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.failed_count, 1)

    def test_rebuild_index_creates_entries_from_known_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "项目 根目录"
            project_path = root / "project-normal" / PROJECT_FILE_NAME
            self.assertTrue(save_project(project_path, self._project()).ok)

            rebuilt = rebuild_project_index([root])

        self.assertTrue(rebuilt.ok)
        self.assertEqual(len(rebuilt.entries), 1)
        self.assertEqual(rebuilt.entries[0].file_path, str(project_path))
        self.assertEqual(rebuilt.entries[0].project_id, "project-1")

    def test_read_only_or_occupied_write_returns_failure_stage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / PROJECT_FILE_NAME
            with patch(
                "utils.project_store._atomic_write_json",
                side_effect=PermissionError("file is occupied"),
            ):
                result = save_project(path, self._project())

        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "write")
        self.assertIn("occupied", result.error)

    @staticmethod
    def _project(*, name: str = "示例项目") -> ProjectFile:
        return ProjectFile(
            project_id="project-1",
            name=name,
            description="项目说明",
            created_at="2026-07-26T10:00:00+08:00",
            updated_at="2026-07-26T10:00:00+08:00",
            materials=[
                ProjectMaterialRef(
                    material_id="material-1",
                    last_known_path=r"E:\QRtest\中文 空格\demo.mp4",
                    file_name="demo.mp4",
                    added_at="2026-07-26T10:05:00+08:00",
                    metadata_snapshot={
                        "duration_sec": 3.5,
                        "width": 1920,
                        "height": 1080,
                        "fps": 60,
                    },
                )
            ],
        )

    @staticmethod
    def _entry(path: Path, project_id: str = "project-1") -> ProjectIndexEntry:
        return ProjectIndexEntry(
            project_id=project_id,
            file_path=str(path),
            name=f"项目 {project_id}",
            created_at="2026-07-26T10:00:00+08:00",
            updated_at="2026-07-26T10:00:00+08:00",
            last_opened_at=None,
            archived_at=None,
            file_modified_ns=0,
        )


if __name__ == "__main__":
    unittest.main()
