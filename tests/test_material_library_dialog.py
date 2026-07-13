import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QMessageBox

from services.recording_library import DirectoryScanResult, RecordingLibraryService
from ui.material_library_dialog import MaterialLibraryDialog
from utils.media_metadata import MediaMetadataResult
from utils.recording_library_store import STATUS_METADATA_INCOMPLETE, MaterialItem

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestMaterialLibraryDialog(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.service = RecordingLibraryService(self.base_path / "QuickRec" / "recordings.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_empty_state(self):
        dialog = MaterialLibraryDialog(self.service)

        self.assertEqual(dialog.windowTitle(), "素材库")
        self.assertEqual(dialog._table.rowCount(), 0)
        self.assertEqual(dialog._status_label.text(), "暂无素材")

    def test_initial_page_shows_50_and_load_more_adds_50(self):
        self.assertTrue(self.service.replace([self._item(index) for index in range(120)]).ok)
        dialog = MaterialLibraryDialog(self.service)

        self.assertEqual(dialog._table.rowCount(), 50)
        self.assertIn("显示 50 / 120", dialog._status_label.text())

        dialog._btn_load_more.click()

        self.assertEqual(dialog._table.rowCount(), 100)
        self.assertIn("显示 100 / 120", dialog._status_label.text())

    def test_load_more_reaches_200_and_hides_button(self):
        self.assertTrue(self.service.replace([self._item(index) for index in range(200)]).ok)
        dialog = MaterialLibraryDialog(self.service)

        for _ in range(3):
            dialog._btn_load_more.click()

        self.assertEqual(dialog._table.rowCount(), 200)
        self.assertTrue(dialog._btn_load_more.isHidden())

    def test_selection_updates_detail_panel(self):
        self.assertTrue(self.service.replace([self._item(1)]).ok)
        dialog = MaterialLibraryDialog(self.service)

        dialog._table.selectRow(0)

        self.assertEqual(dialog._detail_name.text(), "QuickRec_001.mp4")
        self.assertIn("1920 × 1080", dialog._detail_video.text())
        self.assertEqual(dialog._detail_mode.text(), "全屏录制")

    def test_reload_keeps_current_selection_when_new_record_arrives(self):
        older = self._item(1)
        self.assertTrue(self.service.replace([older]).ok)
        dialog = MaterialLibraryDialog(self.service)
        dialog._table.selectRow(0)
        newer = self._item(2)

        self.assertTrue(self.service.add(newer).ok)
        dialog.reload()

        self.assertEqual(dialog._selected_item().id, older.id)

    def test_status_copy_and_remove_actions_keep_video_file(self):
        video = self.base_path / "QuickRec_available.mp4"
        video.write_bytes(b"video")
        item = self._item(1)
        item.file_path = str(video)
        item.file_name = video.name
        item.directory = str(video.parent)
        item.status = STATUS_METADATA_INCOMPLETE
        self.assertTrue(self.service.replace([item]).ok)
        dialog = MaterialLibraryDialog(self.service)
        dialog._table.selectRow(0)

        self.assertEqual(dialog._table.item(0, 5).text(), "元数据不完整")
        dialog._btn_copy.click()
        self.assertEqual(QApplication.clipboard().text(), str(video))
        with patch("ui.material_library_dialog.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog._btn_remove.click()

        self.assertTrue(video.exists())
        self.assertEqual(self.service.load().items, [])
        self.assertEqual(dialog._detail_name.text(), "未选择素材")
        self.assertEqual(dialog._detail_time.text(), "-")
        self.assertEqual(dialog._detail_video.text(), "-")
        self.assertEqual(dialog._detail_path.text(), "-")

    def test_delete_confirmation_cancel_does_not_call_recycle(self):
        video = self.base_path / "QuickRec_delete.mp4"
        video.write_bytes(b"video")
        item = self._item(1)
        item.file_path = str(video)
        item.file_name = video.name
        item.directory = str(video.parent)
        self.assertTrue(self.service.replace([item]).ok)
        dialog = MaterialLibraryDialog(self.service)
        dialog._table.selectRow(0)

        with patch.object(self.service, "recycle") as recycle, \
                patch("ui.material_library_dialog.QMessageBox.question", return_value=QMessageBox.No):
            dialog._btn_delete.click()

        recycle.assert_not_called()
        self.assertTrue(video.exists())

    def test_narrow_window_switches_to_vertical_layout(self):
        dialog = MaterialLibraryDialog(self.service)

        dialog.show()
        dialog.resize(700, 600)
        QApplication.processEvents()

        self.assertEqual(dialog._splitter.orientation(), Qt.Vertical)

    def test_directory_rebuild_scan_runs_off_qt_main_thread(self):
        video_dir = self.base_path / "videos"
        video_dir.mkdir()
        (video_dir / "QuickRec_20260710_160000.mp4").write_bytes(b"video")
        dialog = MaterialLibraryDialog(self.service)
        main_thread = threading.get_ident()
        worker_threads = []
        original_preview = self.service.preview_directory

        def preview(directory, *, cancel_requested=None):
            worker_threads.append(threading.get_ident())
            return original_preview(directory, cancel_requested=cancel_requested)

        with patch.object(self.service, "preview_directory", side_effect=preview), \
                patch(
                    "services.recording_library.probe_media",
                    return_value=MediaMetadataResult(True, duration_sec=1, width=320, height=240, fps=30),
                ), \
                patch("ui.material_library_dialog.QFileDialog.getExistingDirectory", return_value=str(video_dir)), \
                patch("ui.material_library_dialog.QMessageBox.question", return_value=QMessageBox.No):
            dialog._on_rebuild()
            for _ in range(100):
                QApplication.processEvents()
                if getattr(dialog, "_task", None) is None:
                    break
                QTest.qWait(10)

        self.assertEqual(len(worker_threads), 1)
        self.assertNotEqual(worker_threads[0], main_thread)
        self.assertIn("取消", dialog._status_label.text())

    def test_close_requests_background_task_cancellation(self):
        dialog = MaterialLibraryDialog(self.service)
        started = threading.Event()
        cancelled = threading.Event()

        def operation(cancel_requested):
            started.set()
            while not cancel_requested():
                time.sleep(0.01)
            cancelled.set()
            return DirectoryScanResult(True, self.base_path, cancelled=True)

        dialog._start_task(operation, lambda _result: None, "扫描中")
        self.assertTrue(started.wait(1))
        event = QCloseEvent()

        with patch("ui.material_library_dialog.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog.closeEvent(event)

        self.assertFalse(event.isAccepted())
        for _ in range(100):
            QApplication.processEvents()
            if dialog._task is None:
                break
            QTest.qWait(10)
        self.assertTrue(cancelled.is_set())
        self.assertIsNone(dialog._task)

    def _item(self, index: int) -> MaterialItem:
        path = self.base_path / f"QuickRec_{index:03d}.mp4"
        return MaterialItem(
            id=f"item-{index:03d}",
            file_path=str(path),
            file_name=path.name,
            directory=str(path.parent),
            mode="fullscreen",
            audio_source="both",
            created_at=f"2026-07-10T{index // 60:02d}:{index % 60:02d}:00+08:00",
            duration_sec=12.5,
            width=1920,
            height=1080,
            fps=60.0,
            file_size_bytes=1024 * 1024,
        )


if __name__ == "__main__":
    unittest.main()
