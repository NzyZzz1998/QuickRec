import tempfile
import unittest
from pathlib import Path

from services.project_query import ProjectQueryCriteria, ProjectQueryEngine
from utils.project_store import (
    ProjectFile,
    ProjectIndexEntry,
    ProjectMaterialRef,
    save_project,
)


class TestProjectQueryEngine(unittest.TestCase):
    def test_filters_active_and_archived_projects(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            active = self._entry(temp_dir, "active", archived_at=None)
            archived = self._entry(
                temp_dir,
                "archived",
                archived_at="2026-07-26T12:00:00+08:00",
            )
            engine = ProjectQueryEngine()

            active_result = engine.query(
                [active, archived],
                ProjectQueryCriteria(scope="active"),
            )
            archived_result = engine.query(
                [active, archived],
                ProjectQueryCriteria(scope="archived"),
            )

        self.assertEqual([item.entry.project_id for item in active_result.items], ["active"])
        self.assertEqual([item.entry.project_id for item in archived_result.items], ["archived"])

    def test_keyword_matches_project_name_case_insensitively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tutorial = self._entry(temp_dir, "tutorial", name="QuickRec 教程")
            demo = self._entry(temp_dir, "demo", name="发布演示")
            engine = ProjectQueryEngine()

            result = engine.query(
                [tutorial, demo],
                ProjectQueryCriteria(keyword="quickrec", scope="all"),
            )

        self.assertEqual([item.entry.project_id for item in result.items], ["tutorial"])

    def test_keyword_also_matches_material_file_name_inside_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wanted = self._entry(
                temp_dir,
                "wanted",
                material_name="客户演示 成片.mp4",
            )
            other = self._entry(
                temp_dir,
                "other",
                material_name="普通录制.mp4",
            )

            result = ProjectQueryEngine().query(
                [wanted, other],
                ProjectQueryCriteria(keyword="客户演示", scope="all"),
            )

        self.assertEqual(
            [item.entry.project_id for item in result.items],
            ["wanted"],
        )

    def test_sort_uses_last_opened_then_updated_time_descending(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            old = self._entry(
                temp_dir,
                "old",
                updated_at="2026-07-26T09:00:00+08:00",
                last_opened_at="2026-07-26T11:00:00+08:00",
            )
            new = self._entry(
                temp_dir,
                "new",
                updated_at="2026-07-26T12:00:00+08:00",
                last_opened_at=None,
            )
            engine = ProjectQueryEngine()

            result = engine.query([old, new], ProjectQueryCriteria(scope="all"))

        self.assertEqual([item.entry.project_id for item in result.items], ["new", "old"])

    def test_recent_projects_are_limited_to_eight(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            entries = [
                self._entry(
                    temp_dir,
                    f"project-{index}",
                    updated_at=f"2026-07-26T{index:02d}:00:00+08:00",
                )
                for index in range(10)
            ]
            engine = ProjectQueryEngine()

            recent = engine.recent(entries)

        self.assertEqual(len(recent), 8)
        self.assertEqual(recent[0].entry.project_id, "project-9")
        self.assertEqual(recent[-1].entry.project_id, "project-2")

    def test_query_reports_missing_corrupt_and_available_health(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            available = self._entry(temp_dir, "available")
            missing = self._entry(temp_dir, "missing", create_file=False)
            corrupt = self._entry(temp_dir, "corrupt", valid_file=False)
            engine = ProjectQueryEngine()

            result = engine.query(
                [available, missing, corrupt],
                ProjectQueryCriteria(scope="all"),
            )
            health = {item.entry.project_id: item.health for item in result.items}

        self.assertEqual(health["available"], "available")
        self.assertEqual(health["missing"], "missing")
        self.assertEqual(health["corrupt"], "corrupt")

    def test_query_reports_material_count_for_valid_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            entry = self._entry(temp_dir, "project-1")
            engine = ProjectQueryEngine()

            result = engine.query([entry], ProjectQueryCriteria(scope="all"))

        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.items[0].material_count, 0)

    @staticmethod
    def _entry(
        temp_dir: str,
        project_id: str,
        *,
        name: str | None = None,
        updated_at: str = "2026-07-26T10:00:00+08:00",
        last_opened_at: str | None = None,
        archived_at: str | None = None,
        create_file: bool = True,
        valid_file: bool = True,
        material_name: str | None = None,
    ) -> ProjectIndexEntry:
        path = Path(temp_dir) / project_id / "project.qrproj"
        if create_file:
            if valid_file:
                project = ProjectFile(
                    project_id=project_id,
                    name=name or project_id,
                    description="",
                    created_at="2026-07-26T09:00:00+08:00",
                    updated_at=updated_at,
                    archived_at=archived_at,
                )
                if material_name:
                    project.materials.append(
                        ProjectMaterialRef(
                            material_id=f"material-{project_id}",
                            last_known_path=str(Path(temp_dir) / material_name),
                            file_name=material_name,
                            added_at=updated_at,
                        )
                    )
                save_project(
                    path,
                    project,
                )
            else:
                path.parent.mkdir(parents=True)
                path.write_text("{broken", encoding="utf-8")
        return ProjectIndexEntry(
            project_id=project_id,
            file_path=str(path),
            name=name or project_id,
            created_at="2026-07-26T09:00:00+08:00",
            updated_at=updated_at,
            last_opened_at=last_opened_at,
            archived_at=archived_at,
            file_modified_ns=path.stat().st_mtime_ns if path.exists() else 0,
        )


if __name__ == "__main__":
    unittest.main()
