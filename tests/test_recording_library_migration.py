import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.recording_library import RecordingLibraryService
from utils.media_metadata import MediaMetadataResult

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "v1_6"


class TestRecordingLibraryMigration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.service = RecordingLibraryService(self.base_path / "appdata" / "QuickRec" / "recordings.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_migrate_preserves_ids_and_does_not_modify_source(self):
        source = self._copy_fixture("schema_v1_normal.json")
        before = self._sha256(source)

        result = self.service.migrate_v1_history(source, imported_at="2026-07-10T16:00:00+08:00")

        self.assertTrue(result.ok)
        self.assertEqual(result.added_count, 2)
        self.assertEqual(result.duplicate_count, 0)
        self.assertEqual([item.id for item in result.items], ["fixture-fullscreen-001", "fixture-window-002"])
        self.assertEqual(self._sha256(source), before)
        self.assertTrue(all(item.source_type == "migration" for item in result.items))
        self.assertTrue(all(item.source_history_path == str(source) for item in result.items))

    def test_migrate_same_source_is_idempotent(self):
        source = self._copy_fixture("schema_v1_normal.json")

        first = self.service.migrate_v1_history(source, imported_at="2026-07-10T16:00:00+08:00")
        second = self.service.migrate_v1_history(source, imported_at="2026-07-10T16:05:00+08:00")

        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertEqual(second.added_count, 0)
        self.assertEqual(second.duplicate_count, 2)
        self.assertEqual(len(self.service.load().items), 2)
        self.assertTrue(self.service.has_processed_source(source))

    def test_preview_migration_does_not_create_or_change_central_index(self):
        source = self._copy_fixture("schema_v1_normal.json")

        preview = self.service.preview_v1_history(
            source,
            imported_at="2026-07-10T16:00:00+08:00",
        )

        self.assertTrue(preview.ok)
        self.assertEqual(preview.added_count, 2)
        self.assertFalse(self.service.library_path.exists())

        committed = self.service.commit_migration(preview)

        self.assertTrue(committed.ok)
        self.assertEqual(len(committed.items), 2)

    def test_mark_source_status_supports_prompt_once_without_touching_legacy_file(self):
        source = self._copy_fixture("schema_v1_normal.json")
        before = self._sha256(source)

        written = self.service.mark_source_status(
            source,
            status="prompted",
            changed_at="2026-07-10T16:00:00+08:00",
        )

        self.assertTrue(written.ok)
        self.assertTrue(self.service.has_source_status(source))
        self.assertFalse(self.service.has_processed_source(source))
        self.assertEqual(self._sha256(source), before)

    def test_migrate_reports_invalid_items_without_dropping_valid_record(self):
        source = self._copy_fixture("schema_v1_partial_invalid.json")

        result = self.service.migrate_v1_history(source, imported_at="2026-07-10T16:00:00+08:00")

        self.assertTrue(result.ok)
        self.assertEqual(result.added_count, 1)
        self.assertEqual(result.skipped_count, 2)
        self.assertEqual([item.id for item in result.items], ["fixture-valid-001"])

    def test_migrate_keeps_newest_200_and_reports_pruned_count(self):
        source = self.base_path / "large-v1.json"
        source.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "items": [
                        {
                            "id": f"legacy-{index:03d}",
                            "file_path": str(self.base_path / f"QuickRec_{index:03d}.mp4"),
                            "created_at": f"2026-07-10T{index // 60:02d}:{index % 60:02d}:00+08:00",
                        }
                        for index in range(201)
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self.service.migrate_v1_history(
            source,
            imported_at="2026-07-10T16:00:00+08:00",
        )

        self.assertTrue(result.ok)
        self.assertEqual(len(result.items), 200)
        self.assertEqual(result.pruned_count, 1)
        self.assertEqual(result.items[0].id, "legacy-200")
        self.assertEqual(result.items[-1].id, "legacy-001")

    @patch("services.recording_library.probe_media")
    def test_manual_import_skips_existing_unparseable_and_non_mp4_files(self, probe):
        good = self.base_path / "有效 视频.mp4"
        broken = self.base_path / "损坏视频.mp4"
        not_video = self.base_path / "说明.txt"
        good.write_bytes(b"video")
        broken.write_bytes(b"broken")
        not_video.write_text("text", encoding="utf-8")
        source = self.base_path / "recordings.json"
        source.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "items": [
                        {"id": "good", "file_path": str(good), "created_at": "2026-07-10T15:00:00+08:00"},
                        {"id": "bad", "file_path": str(broken), "created_at": "2026-07-10T14:00:00+08:00"},
                        {"id": "text", "file_path": str(not_video), "created_at": "2026-07-10T13:00:00+08:00"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        probe.side_effect = [
            MediaMetadataResult(True, duration_sec=1, width=320, height=240, fps=30),
            MediaMetadataResult(False, error="invalid media"),
        ]

        result = self.service.preview_v1_history(source, imported_at="2026-07-10T16:00:00+08:00")

        self.assertTrue(result.ok)
        self.assertEqual([item.id for item in result.items], ["good"])
        self.assertEqual(result.skipped_count, 2)

    def _copy_fixture(self, name: str) -> Path:
        target = self.base_path / name
        target.write_bytes((FIXTURE_DIR / name).read_bytes())
        return target

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
