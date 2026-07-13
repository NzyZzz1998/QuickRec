import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.recording_library_store import (
    MaterialItem,
    load_library,
    normalize_windows_path,
    resolve_library_file,
    save_library,
)


class TestRecordingLibraryStore(unittest.TestCase):
    def test_resolve_library_file_uses_appdata_quickrec_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = resolve_library_file(Path(temp_dir))

        self.assertEqual(path, Path(temp_dir) / "QuickRec" / "recordings.json")

    def test_save_and_load_preserve_extensions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "recordings.json"
            video = Path(temp_dir) / "QuickRec_20260710_150000.mp4"
            video.write_bytes(b"video")
            item = self._item(video, "2026-07-10T15:00:00+08:00", "item-1")
            item.extensions["future"] = {"value": 1}

            written = save_library(path, [item], extensions={"root_future": True})
            loaded = load_library(path)

        self.assertTrue(written.ok)
        self.assertTrue(loaded.ok)
        self.assertEqual(loaded.extensions, {"root_future": True})
        self.assertEqual(loaded.items[0].extensions, {"future": {"value": 1}})
        self.assertEqual(loaded.items[0].id, "item-1")

    def test_save_keeps_newest_200_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "recordings.json"
            items = [
                self._item(
                    Path(temp_dir) / f"QuickRec_{index:03d}.mp4",
                    f"2026-07-10T{index // 60:02d}:{index % 60:02d}:00+08:00",
                    f"item-{index:03d}",
                )
                for index in range(201)
            ]

            result = save_library(path, items)

        self.assertTrue(result.ok)
        self.assertEqual(len(result.items), 200)
        self.assertEqual(result.items[0].id, "item-200")
        self.assertEqual(result.items[-1].id, "item-001")

    def test_second_save_keeps_previous_valid_document_as_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "recordings.json"
            first = self._item(Path(temp_dir) / "QuickRec_first.mp4", "2026-07-10T14:00:00+08:00", "first")
            second = self._item(Path(temp_dir) / "QuickRec_second.mp4", "2026-07-10T15:00:00+08:00", "second")

            self.assertTrue(save_library(path, [first]).ok)
            self.assertTrue(save_library(path, [second]).ok)
            backup = load_library(path.with_name("recordings.json.bak"))

        self.assertTrue(backup.ok)
        self.assertEqual([item.id for item in backup.items], ["first"])

    def test_atomic_write_failure_keeps_previous_index_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "recordings.json"
            first = self._item(Path(temp_dir) / "QuickRec_first.mp4", "2026-07-10T14:00:00+08:00", "first")
            second = self._item(Path(temp_dir) / "QuickRec_second.mp4", "2026-07-10T15:00:00+08:00", "second")
            self.assertTrue(save_library(path, [first]).ok)
            before = path.read_bytes()

            with patch(
                "utils.recording_library_store._atomic_write_json",
                side_effect=OSError("write denied"),
            ):
                result = save_library(path, [second])

            self.assertFalse(result.ok)
            self.assertEqual(path.read_bytes(), before)

    def test_corrupt_index_without_valid_backup_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "recordings.json"
            path.write_text("{broken", encoding="utf-8")

            result = load_library(path)

            self.assertFalse(result.ok)
            self.assertEqual(path.read_text(encoding="utf-8"), "{broken")
            self.assertEqual(len(list(path.parent.glob("recordings.corrupt-*.json"))), 1)

    def test_load_archives_corrupt_document_and_recovers_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "recordings.json"
            first = self._item(Path(temp_dir) / "QuickRec_first.mp4", "2026-07-10T14:00:00+08:00", "first")
            second = self._item(Path(temp_dir) / "QuickRec_second.mp4", "2026-07-10T15:00:00+08:00", "second")
            self.assertTrue(save_library(path, [first]).ok)
            self.assertTrue(save_library(path, [second]).ok)
            path.write_text("{broken", encoding="utf-8")

            recovered = load_library(path)
            corrupt_files = list(path.parent.glob("recordings.corrupt-*.json"))

        self.assertTrue(recovered.ok)
        self.assertTrue(recovered.recovered)
        self.assertEqual([item.id for item in recovered.items], ["first"])
        self.assertEqual(len(corrupt_files), 1)

    def test_corrupt_archive_retention_is_limited_to_five(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "recordings.json"
            first = self._item(Path(temp_dir) / "QuickRec_first.mp4", "2026-07-10T14:00:00+08:00", "first")
            second = self._item(Path(temp_dir) / "QuickRec_second.mp4", "2026-07-10T15:00:00+08:00", "second")
            self.assertTrue(save_library(path, [first]).ok)
            self.assertTrue(save_library(path, [second]).ok)

            for _ in range(6):
                path.write_text("{broken", encoding="utf-8")
                self.assertTrue(load_library(path).ok)

            corrupt_files = list(path.parent.glob("recordings.corrupt-*.json"))

        self.assertEqual(len(corrupt_files), 5)

    def test_load_skips_invalid_items_and_reports_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "recordings.json"
            path.write_text(
                '{"schema_version":2,"items":[{"id":"valid","file_path":"missing.mp4",'
                '"created_at":"2026-07-10T15:00:00+08:00"},"bad",42]}',
                encoding="utf-8",
            )

            result = load_library(path)

        self.assertTrue(result.ok)
        self.assertEqual([item.id for item in result.items], ["valid"])
        self.assertEqual(result.skipped_items, 2)

    def test_load_skips_object_missing_required_identity_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "recordings.json"
            path.write_text(
                '{"schema_version":2,"items":['
                '{"id":"valid","file_path":"missing.mp4","created_at":"2026-07-10T15:00:00+08:00"},'
                '{"id":"bad","created_at":"2026-07-10T14:00:00+08:00"}]}',
                encoding="utf-8",
            )

            result = load_library(path)

        self.assertTrue(result.ok)
        self.assertEqual([item.id for item in result.items], ["valid"])
        self.assertEqual(result.skipped_items, 1)

    def test_load_rejects_unsupported_schema_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "recordings.json"
            path.write_text('{"schema_version":99,"items":[]}', encoding="utf-8")

            result = load_library(path)

        self.assertFalse(result.ok)
        self.assertIn("schema", result.error.lower())

    def test_normalize_windows_path_treats_case_and_separators_as_equal(self):
        first = normalize_windows_path(r"E:\QRtest\A\..\QuickRec_demo.mp4")
        second = normalize_windows_path("e:/qrtest/QuickRec_demo.mp4")

        self.assertEqual(first, second)

    @staticmethod
    def _item(path: Path, created_at: str, item_id: str) -> MaterialItem:
        return MaterialItem(
            id=item_id,
            file_path=str(path),
            file_name=path.name,
            directory=str(path.parent),
            mode="fullscreen",
            audio_source="none",
            created_at=created_at,
        )


if __name__ == "__main__":
    unittest.main()
