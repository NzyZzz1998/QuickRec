import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ConfigManager
from utils.recording_history import (
    DEFAULT_MAX_ITEMS,
    HISTORY_FILE_NAME,
    METADATA_DIR_NAME,
    STATUS_AVAILABLE,
    STATUS_MISSING,
    RecordingHistoryItem,
    add_history_item,
    build_history_item,
    load_history,
    remove_history_item,
    resolve_history_file,
    save_history,
)


class TestRecordingHistory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.save_path = self.base_path / "videos"
        self.config = ConfigManager.__new__(ConfigManager)
        self.config.config_path = self.base_path / "config.json"
        self.config._config = ConfigManager.defaults.copy()
        self.config.set("save_path", str(self.save_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resolve_history_file_uses_save_path_metadata_dir(self):
        path = resolve_history_file(self.config)

        self.assertEqual(path, self.save_path / METADATA_DIR_NAME / HISTORY_FILE_NAME)

    def test_load_history_returns_empty_when_file_missing(self):
        result = load_history(self.config)

        self.assertTrue(result.ok)
        self.assertEqual(result.items, [])

    def test_add_history_item_writes_record(self):
        video = self._write_video("one.mp4")
        item = build_history_item(
            video,
            mode="fullscreen",
            audio_source="both",
            diagnostic_dir=self.base_path / "diagnostics",
            duration_sec=3.2,
            created_at=datetime(2026, 7, 10, 15, 30, tzinfo=UTC),
        )

        result = add_history_item(self.config, item)
        loaded = load_history(self.config)

        self.assertTrue(result.ok)
        self.assertEqual(len(loaded.items), 1)
        saved = loaded.items[0]
        self.assertEqual(saved.file_name, "one.mp4")
        self.assertEqual(saved.mode, "fullscreen")
        self.assertEqual(saved.audio_source, "both")
        self.assertEqual(saved.status, STATUS_AVAILABLE)
        self.assertEqual(saved.file_size_bytes, video.stat().st_size)
        self.assertEqual(saved.diagnostic_dir, str(self.base_path / "diagnostics"))

    def test_save_history_prunes_to_max_items(self):
        items = [
            self._item(f"item-{index}", created_at=f"2026-07-10T15:{index:02d}:00+08:00")
            for index in range(DEFAULT_MAX_ITEMS + 5)
        ]

        result = save_history(self.config, items)
        loaded = load_history(self.config)

        self.assertTrue(result.ok)
        self.assertEqual(len(loaded.items), DEFAULT_MAX_ITEMS)
        self.assertEqual(loaded.items[0].id, "item-54")
        self.assertEqual(loaded.items[-1].id, "item-5")

    def test_load_history_marks_missing_file(self):
        missing_path = self.save_path / "missing.mp4"
        item = self._item("missing", file_path=missing_path)
        save_history(self.config, [item])

        loaded = load_history(self.config)

        self.assertEqual(loaded.items[0].status, STATUS_MISSING)

    def test_remove_history_item_removes_from_json(self):
        kept = self._item("kept")
        removed = self._item("removed")
        save_history(self.config, [kept, removed])

        result = remove_history_item(self.config, "removed")
        loaded = load_history(self.config)

        self.assertTrue(result.ok)
        self.assertEqual([item.id for item in loaded.items], ["kept"])

    def test_load_history_reports_corrupt_json_without_raising(self):
        path = resolve_history_file(self.config)
        path.parent.mkdir(parents=True)
        path.write_text("{broken", encoding="utf-8")

        result = load_history(self.config)

        self.assertFalse(result.ok)
        self.assertEqual(result.items, [])
        self.assertTrue(result.error)

    def test_save_history_reports_write_failure_without_raising(self):
        item = self._item("one")

        with patch("utils.recording_history._atomic_write_json", side_effect=OSError("no write")):
            result = save_history(self.config, [item])

        self.assertFalse(result.ok)
        self.assertIn("no write", result.error)

    def _write_video(self, name: str) -> Path:
        self.save_path.mkdir(parents=True, exist_ok=True)
        path = self.save_path / name
        path.write_bytes(b"video")
        return path

    def _item(
        self,
        item_id: str,
        file_path: Path | None = None,
        created_at: str = "2026-07-10T15:30:00+08:00",
    ) -> RecordingHistoryItem:
        path = file_path or self._write_video(f"{item_id}.mp4")
        return RecordingHistoryItem(
            id=item_id,
            file_path=str(path),
            file_name=path.name,
            directory=str(path.parent),
            mode="fullscreen",
            audio_source="none",
            created_at=created_at,
            file_size_bytes=path.stat().st_size if path.exists() else None,
            status=STATUS_AVAILABLE if path.exists() else STATUS_MISSING,
        )


if __name__ == "__main__":
    unittest.main()
