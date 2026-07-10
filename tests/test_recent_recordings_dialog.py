import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication

from config import ConfigManager
from ui.recent_recordings_dialog import RecentRecordingsDialog
from utils.recording_history import RecordingHistoryItem, save_history

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestRecentRecordingsDialog(unittest.TestCase):
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

    def test_empty_state(self):
        dialog = RecentRecordingsDialog(self.config)

        self.assertEqual(dialog._table.rowCount(), 0)
        self.assertEqual(dialog._status_label.text(), "暂无录制记录")

    def test_available_record_is_rendered(self):
        video = self._write_video("one.mp4")
        save_history(self.config, [self._item("one", video)])

        dialog = RecentRecordingsDialog(self.config)

        self.assertEqual(dialog._table.rowCount(), 1)
        self.assertEqual(dialog._table.item(0, 0).text(), "one.mp4")
        self.assertEqual(dialog._table.item(0, 4).text(), "可用")

    def test_missing_record_is_rendered(self):
        save_history(self.config, [self._item("missing", self.save_path / "missing.mp4")])

        dialog = RecentRecordingsDialog(self.config)

        self.assertEqual(dialog._table.item(0, 4).text(), "文件已移动或删除")

    def test_copy_path_copies_selected_record(self):
        video = self._write_video("copy.mp4")
        save_history(self.config, [self._item("copy", video)])
        dialog = RecentRecordingsDialog(self.config)
        dialog._table.selectRow(0)

        dialog._btn_copy_path.click()

        self.assertEqual(QApplication.clipboard().text(), str(video))
        self.assertEqual(dialog._status_label.text(), "录制路径已复制")

    def test_remove_deletes_selected_record(self):
        video = self._write_video("remove.mp4")
        save_history(self.config, [self._item("remove", video)])
        dialog = RecentRecordingsDialog(self.config)
        dialog._table.selectRow(0)

        dialog._btn_remove.click()

        self.assertEqual(dialog._table.rowCount(), 0)
        self.assertEqual(dialog._status_label.text(), "记录已从列表移除")

    def _write_video(self, name: str) -> Path:
        self.save_path.mkdir(parents=True, exist_ok=True)
        path = self.save_path / name
        path.write_bytes(b"video")
        return path

    def _item(self, item_id: str, path: Path) -> RecordingHistoryItem:
        return RecordingHistoryItem(
            id=item_id,
            file_path=str(path),
            file_name=path.name,
            directory=str(path.parent),
            mode="fullscreen",
            audio_source="none",
            created_at="2026-07-10T15:30:00+08:00",
            file_size_bytes=path.stat().st_size if path.exists() else None,
        )


if __name__ == "__main__":
    unittest.main()
