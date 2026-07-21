import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QMessageBox

from services.material_query import MaterialQueryEngine
from services.material_query_session import MaterialQuerySession
from services.pending_recordings import PendingRecordingService
from services.recording_library import DirectoryScanResult, RecordingLibraryService
from ui.material_library_dialog import MaterialLibraryDialog
from utils.media_metadata import MediaMetadataResult
from utils.pending_recording_store import PendingRecordingItem
from utils.recording_library_store import STATUS_METADATA_INCOMPLETE, MaterialItem

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestMaterialLibraryDialog(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.service = RecordingLibraryService(self.base_path / "QuickRec" / "recordings.json")
        self.pending_service = PendingRecordingService(self.base_path / "QuickRec" / "pending-recordings.json")

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

    def test_keyword_search_matches_file_name_or_path_after_debounce(self):
        name_match = self._item(1)
        name_match.file_name = "Target Demo.mp4"
        path_match = self._item(2)
        path_match.file_path = str(self.base_path / "目标目录" / "plain.mp4")
        miss = self._item(3)
        self.assertTrue(self.service.replace([name_match, path_match, miss]).ok)
        dialog = MaterialLibraryDialog(self.service)

        dialog._search_input.setText("target")
        QTest.qWait(180)
        QApplication.processEvents()

        self.assertEqual(dialog._table.rowCount(), 1)
        self.assertIn("匹配 1 / 共 3 条", dialog._query_count_label.text())

        dialog._search_input.setText("目标目录")
        QTest.qWait(180)
        QApplication.processEvents()
        self.assertEqual(dialog._table.rowCount(), 1)
        self.assertEqual(dialog._table.item(0, 0).text(), path_match.file_name)

    def test_filter_categories_combine_with_and_and_sorting_updates_rows(self):
        wanted = self._item(1)
        wanted.mode = "window"
        wanted.audio_source = "both"
        wanted.duration_sec = 10
        other = self._item(2)
        other.mode = "region"
        other.audio_source = "none"
        other.duration_sec = 20
        self.assertTrue(self.service.replace([wanted, other]).ok)
        dialog = MaterialLibraryDialog(self.service)

        dialog._mode_combo.setCurrentIndex(dialog._mode_combo.findData("window"))
        dialog._audio_combo.setCurrentIndex(dialog._audio_combo.findData("both"))
        QApplication.processEvents()

        self.assertEqual(dialog._table.rowCount(), 1)
        self.assertEqual(dialog._table.item(0, 0).text(), wanted.file_name)

        dialog._btn_reset_query.click()
        dialog._sort_combo.setCurrentIndex(dialog._sort_combo.findData("duration_desc"))
        QApplication.processEvents()
        self.assertEqual(dialog._table.item(0, 0).text(), other.file_name)

    def test_no_match_state_can_reset_to_full_library(self):
        self.assertTrue(self.service.replace([self._item(1)]).ok)
        dialog = MaterialLibraryDialog(self.service)

        dialog._search_input.setText("does-not-exist")
        QTest.qWait(180)
        QApplication.processEvents()

        self.assertEqual(dialog._table.rowCount(), 0)
        self.assertIn("没有符合当前条件", dialog._status_label.text())

        dialog._btn_reset_query.click()
        QApplication.processEvents()
        self.assertEqual(dialog._table.rowCount(), 1)
        self.assertEqual(dialog._search_input.text(), "")

    def test_query_failure_keeps_last_rows_and_shows_non_blocking_feedback(self):
        self.assertTrue(self.service.replace([self._item(1)]).ok)
        engine = MaterialQueryEngine()
        session = MaterialQuerySession(engine=engine)
        dialog = MaterialLibraryDialog(self.service, query_session=session)
        self.assertEqual(dialog._table.rowCount(), 1)

        with patch.object(engine, "execute", side_effect=RuntimeError("private path")):
            dialog._status_combo.setCurrentIndex(dialog._status_combo.findData("available"))
            QApplication.processEvents()

        self.assertEqual(dialog._table.rowCount(), 1)
        self.assertIn("已保留上一次有效结果", dialog._status_label.text())

    def test_query_runs_before_formal_pagination(self):
        items = [self._item(index) for index in range(120)]
        for index, item in enumerate(items):
            item.file_name = f"match-{index:03d}.mp4" if index < 60 else f"other-{index:03d}.mp4"
        self.assertTrue(self.service.replace(items).ok)
        dialog = MaterialLibraryDialog(self.service)

        dialog._search_input.setText("match-")
        QTest.qWait(180)
        QApplication.processEvents()

        self.assertEqual(dialog._table.rowCount(), 50)
        self.assertIn("显示 50 / 60", dialog._status_label.text())
        dialog._btn_load_more.click()
        self.assertEqual(dialog._table.rowCount(), 60)
        self.assertTrue(dialog._btn_load_more.isHidden())

    def test_close_keeps_conditions_but_resets_page_and_selection(self):
        items = [self._item(index) for index in range(80)]
        self.assertTrue(self.service.replace(items).ok)
        dialog = MaterialLibraryDialog(self.service)
        dialog._search_input.setText("QuickRec")
        QTest.qWait(180)
        dialog._btn_load_more.click()
        dialog._table.selectRow(0)
        self.assertEqual(dialog._table.rowCount(), 80)

        dialog.close()
        dialog.reload()

        self.assertEqual(dialog._search_input.text(), "QuickRec")
        self.assertEqual(dialog._table.rowCount(), 50)
        self.assertEqual(dialog._table.currentRow(), -1)

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

    def test_pending_items_are_shown_before_formal_items_with_independent_counts(self):
        video = self.base_path / "QuickRec_pending.mp4"
        video.write_bytes(b"video")
        self.assertTrue(self.pending_service.persist(self._pending_item(video)).ok)
        formal_item = self._item(1)
        Path(formal_item.file_path).write_bytes(b"video")
        self.assertTrue(self.service.replace([formal_item]).ok)

        dialog = MaterialLibraryDialog(
            self.service,
            pending_service=self.pending_service,
            current_save_dir=self.base_path,
        )

        self.assertEqual(dialog._table.rowCount(), 2)
        self.assertEqual(dialog._table.item(0, 5).text(), "待入库")
        self.assertEqual(dialog._table.item(1, 5).text(), "可用")
        self.assertIn("待入库 1 条", dialog._status_label.text())
        self.assertIn("素材 1 条", dialog._status_label.text())

    def test_pending_only_state_is_not_reported_as_empty_library(self):
        video = self.base_path / "QuickRec_pending.mp4"
        video.write_bytes(b"video")
        self.assertTrue(self.pending_service.persist(self._pending_item(video)).ok)

        dialog = MaterialLibraryDialog(
            self.service,
            pending_service=self.pending_service,
            current_save_dir=self.base_path,
        )

        self.assertEqual(dialog._table.rowCount(), 1)
        self.assertNotEqual(dialog._status_label.text(), "暂无素材")

    def test_selecting_pending_item_shows_retry_and_pending_remove_actions(self):
        video = self.base_path / "QuickRec_pending.mp4"
        video.write_bytes(b"video")
        self.assertTrue(self.pending_service.persist(self._pending_item(video)).ok)
        dialog = MaterialLibraryDialog(
            self.service,
            pending_service=self.pending_service,
            current_save_dir=self.base_path,
        )

        dialog._table.selectRow(0)

        self.assertFalse(dialog._btn_retry_pending.isHidden())
        self.assertFalse(dialog._btn_remove_pending.isHidden())
        self.assertTrue(dialog._btn_remove.isHidden())
        self.assertTrue(dialog._btn_delete.isHidden())
        self.assertIn("中央索引写入失败", dialog._detail_failure.text())

    def test_pending_retry_refreshes_item_into_formal_material(self):
        video = self.base_path / "QuickRec_pending.mp4"
        video.write_bytes(b"video")
        item = self._pending_item(video)
        self.assertTrue(self.pending_service.persist(item).ok)
        coordinator = SimpleNamespace()

        def retry(pending_id, *, current_save_dir=None):
            self.assertEqual(pending_id, item.pending_id)
            self.assertEqual(Path(current_save_dir), self.base_path)
            self.assertTrue(self.service.add_recording(
                video,
                metadata={"mode": "fullscreen", "audio_source": "none"},
                diagnostic_dir=None,
                item_id=item.material_id,
            ).ok)
            self.assertTrue(self.pending_service.remove(item.pending_id, current_save_dir=self.base_path).ok)
            return SimpleNamespace(formal_indexed=True, error="")

        coordinator.retry = retry
        dialog = MaterialLibraryDialog(
            self.service,
            pending_service=self.pending_service,
            ingestion_coordinator=coordinator,
            current_save_dir=self.base_path,
        )
        dialog._table.selectRow(0)

        dialog._btn_retry_pending.click()

        self.assertEqual(dialog._table.rowCount(), 1)
        self.assertEqual(dialog._table.item(0, 5).text(), "可用")
        self.assertIn("素材已加入素材库", dialog._status_label.text())

    def test_remove_pending_confirmation_keeps_video_file(self):
        video = self.base_path / "QuickRec_pending.mp4"
        video.write_bytes(b"video")
        item = self._pending_item(video)
        self.assertTrue(self.pending_service.persist(item).ok)
        dialog = MaterialLibraryDialog(
            self.service,
            pending_service=self.pending_service,
            current_save_dir=self.base_path,
        )
        dialog._table.selectRow(0)

        with patch("ui.material_library_dialog.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog._btn_remove_pending.click()

        self.assertTrue(video.exists())
        self.assertEqual(self.pending_service.load(self.base_path).items, [])
        self.assertEqual(dialog._table.rowCount(), 0)

    def _pending_item(self, path: Path) -> PendingRecordingItem:
        return PendingRecordingItem(
            pending_id="pending-1",
            material_id="material-1",
            file_path=str(path),
            file_name=path.name,
            created_at="2026-07-15T10:00:00+08:00",
            queued_at="2026-07-15T10:01:00+08:00",
            updated_at="2026-07-15T10:01:00+08:00",
            status="pending",
            attempt_count=1,
            capture_mode="fullscreen",
            audio_source="none",
            last_error_summary="中央索引写入失败",
            duration_seconds=2.0,
            width=1920,
            height=1080,
            fps=60,
            file_size_bytes=path.stat().st_size,
        )

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
