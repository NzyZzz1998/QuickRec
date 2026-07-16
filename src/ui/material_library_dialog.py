"""QuickRec Full 素材库窗口。"""

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.pending_recordings import PendingRecordingService
from services.recording_library import DirectoryScanResult, MigrationResult, RecordingLibraryService
from utils.pending_recording_store import PendingRecordingItem
from utils.recording_library_store import STATUS_AVAILABLE, STATUS_METADATA_INCOMPLETE, MaterialItem

MODE_LABELS = {
    "fullscreen": "全屏录制",
    "area": "区域录制",
    "region": "区域录制",
    "window": "窗口录制",
    "unknown": "未知模式",
}
AUDIO_LABELS = {
    "none": "无声",
    "system": "系统声音",
    "microphone": "麦克风",
    "mic": "麦克风",
    "both": "系统声音 + 麦克风",
    "unknown": "未知",
}


class _LibraryTask(QThread):
    result_ready = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation: Callable[[Callable[[], bool]], Any], parent=None):
        super().__init__(parent)
        self._operation = operation

    def run(self) -> None:
        try:
            self.result_ready.emit(self._operation(self.isInterruptionRequested))
        except Exception as exc:
            self.failed.emit(str(exc))


class MaterialLibraryDialog(QDialog):
    PAGE_SIZE = 50

    def __init__(
        self,
        service: RecordingLibraryService,
        parent=None,
        *,
        pending_service: PendingRecordingService | None = None,
        ingestion_coordinator: Any = None,
        current_save_dir: str | Path | None = None,
    ):
        super().__init__(parent)
        self._service = service
        self._pending_service = pending_service
        self._ingestion_coordinator = ingestion_coordinator
        self._current_save_dir = Path(current_save_dir) if current_save_dir else None
        self._items: list[MaterialItem] = []
        self._pending_items: list[PendingRecordingItem] = []
        self._rows: list[tuple[str, MaterialItem | PendingRecordingItem]] = []
        self._visible_count = self.PAGE_SIZE
        self._task: _LibraryTask | None = None
        self._task_result_handler: Callable[[Any], None] | None = None
        self._close_when_task_done = False
        self.setWindowTitle("素材库")
        self.resize(980, 560)
        self._init_ui()
        self.reload()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        toolbar.addWidget(self._status_label, 1)
        self._btn_import = QPushButton("导入旧目录")
        self._btn_import.clicked.connect(self._on_import)
        toolbar.addWidget(self._btn_import)
        self._btn_rebuild = QPushButton("重建目录")
        self._btn_rebuild.clicked.connect(self._on_rebuild)
        toolbar.addWidget(self._btn_rebuild)
        root.addLayout(toolbar)

        self._splitter = QSplitter(Qt.Horizontal)
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["文件", "时间", "时长", "分辨率", "大小", "状态"])
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        vertical_header = self._table.verticalHeader()
        horizontal_header = self._table.horizontalHeader()
        assert vertical_header is not None
        assert horizontal_header is not None
        vertical_header.setVisible(False)
        horizontal_header.setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._update_detail)
        self._splitter.addWidget(self._table)
        self._splitter.addWidget(self._create_detail_panel())
        self._splitter.setSizes([580, 400])
        root.addWidget(self._splitter, 1)

        footer = QHBoxLayout()
        self._btn_load_more = QPushButton("加载更多 50 条")
        self._btn_load_more.clicked.connect(self._load_more)
        footer.addWidget(self._btn_load_more)
        footer.addStretch()
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self._close_dialog)
        footer.addWidget(close_button)
        root.addLayout(footer)

    def _create_detail_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self._detail_name = QLabel("未选择素材")
        self._detail_name.setWordWrap(True)
        self._detail_name.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self._detail_name)

        form = QFormLayout()
        self._detail_time = QLabel("-")
        self._detail_duration = QLabel("-")
        self._detail_video = QLabel("-")
        self._detail_mode = QLabel("-")
        self._detail_audio = QLabel("-")
        self._detail_size = QLabel("-")
        self._detail_path = QLabel("-")
        self._detail_path.setWordWrap(True)
        self._detail_diagnostic = QLabel("-")
        self._detail_diagnostic.setWordWrap(True)
        self._detail_source = QLabel("-")
        self._detail_failure = QLabel("-")
        self._detail_failure.setWordWrap(True)
        for label, widget in (
            ("录制时间", self._detail_time),
            ("时长", self._detail_duration),
            ("画面", self._detail_video),
            ("模式", self._detail_mode),
            ("音频", self._detail_audio),
            ("大小", self._detail_size),
            ("路径", self._detail_path),
            ("诊断目录", self._detail_diagnostic),
            ("来源", self._detail_source),
            ("失败原因", self._detail_failure),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self._btn_open = QPushButton("打开")
        self._btn_open.clicked.connect(self._on_open)
        actions.addWidget(self._btn_open)
        self._btn_open_dir = QPushButton("打开目录")
        self._btn_open_dir.clicked.connect(self._on_open_dir)
        actions.addWidget(self._btn_open_dir)
        self._btn_copy = QPushButton("复制路径")
        self._btn_copy.clicked.connect(self._on_copy)
        actions.addWidget(self._btn_copy)
        layout.addLayout(actions)

        manage = QHBoxLayout()
        self._btn_relink = QPushButton("重新定位")
        self._btn_relink.clicked.connect(self._on_relink)
        manage.addWidget(self._btn_relink)
        self._btn_retry_pending = QPushButton("重试入库")
        self._btn_retry_pending.clicked.connect(self._on_retry_pending)
        manage.addWidget(self._btn_retry_pending)
        self._btn_remove_pending = QPushButton("移除待处理记录")
        self._btn_remove_pending.clicked.connect(self._on_remove_pending)
        manage.addWidget(self._btn_remove_pending)
        self._btn_remove = QPushButton("从素材库移除")
        self._btn_remove.clicked.connect(self._on_remove)
        manage.addWidget(self._btn_remove)
        self._btn_delete = QPushButton("删除视频文件")
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_delete.setStyleSheet("color: #c42b1c;")
        manage.addWidget(self._btn_delete)
        layout.addLayout(manage)
        layout.addStretch()
        self._set_actions_enabled(False)
        return panel

    def reload(self) -> None:
        selected = self._selected_entry()
        selected_key = self._entry_key(selected) if selected else None
        loaded = self._service.load()
        if not loaded.ok:
            self._items = []
            self._status_label.setText(f"素材索引加载失败：{loaded.error}")
        else:
            self._items = loaded.items
            if not self._items:
                self._status_label.setText("暂无素材")
            else:
                self._status_label.setText(
                    f"显示 {min(self._visible_count, len(self._items))} / {len(self._items)} 条素材"
                )
                if loaded.recovered:
                    self._status_label.setText("素材索引已从最近有效备份恢复")
        if self._pending_service is not None:
            pending = self._pending_service.load(self._current_save_dir)
            self._pending_items = pending.items
            if not pending.ok:
                self._status_label.setText(f"待入库记录加载失败：{pending.error}")
        else:
            self._pending_items = []
        if loaded.ok and (self._pending_items or self._items):
            self._set_count_status()
        self._render_items()
        if selected_key:
            for row, entry in enumerate(self._rows):
                if self._entry_key(entry) == selected_key:
                    self._table.selectRow(row)
                    break

    def show_migration_result(self, result: MigrationResult) -> None:
        if result.ok:
            self.reload()
            self._status_label.setText(
                f"首次迁移完成：新增 {result.added_count} 条，重复 {result.duplicate_count} 条，"
                f"跳过 {result.skipped_count} 条"
            )
        else:
            self._status_label.setText(
                f"首次迁移失败：{result.error}。可使用“导入旧目录”重试，或稍后处理。"
            )

    def show_legacy_source_prompt(self, source: str | Path) -> None:
        self._status_label.setText(
            f"检测到旧录制历史：{source}。可点击“导入旧目录”预览并导入，或关闭窗口稍后处理。"
        )

    def _render_items(self) -> None:
        visible_items = self._items[: self._visible_count]
        self._rows = [("pending", item) for item in self._pending_items]
        self._rows.extend(("material", item) for item in visible_items)
        self._table.setRowCount(len(self._rows))
        for row, (kind, item) in enumerate(self._rows):
            if kind == "pending":
                assert isinstance(item, PendingRecordingItem)
                values = [
                    item.file_name,
                    item.created_at,
                    self._format_duration(item.duration_seconds),
                    self._format_dimensions(item.width, item.height),
                    self._format_size(item.file_size_bytes),
                    self._format_pending_status(item.status),
                ]
                item_id = item.pending_id
            else:
                assert isinstance(item, MaterialItem)
                values = [
                    item.file_name,
                    item.created_at,
                    self._format_duration(item.duration_sec),
                    self._format_resolution(item),
                    self._format_size(item.file_size_bytes),
                    self._format_status(item.status),
                ]
                item_id = item.id
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.UserRole, item_id)
                self._table.setItem(row, column, cell)
        self._table.resizeColumnsToContents()
        self._btn_load_more.setVisible(len(self._items) > self._visible_count)
        self._update_detail()

    def _load_more(self) -> None:
        self._visible_count = min(len(self._items), self._visible_count + self.PAGE_SIZE)
        self._set_count_status()
        self._render_items()

    def _selected_item(self) -> MaterialItem | None:
        entry = self._selected_entry()
        if entry is None or entry[0] != "material":
            return None
        item = entry[1]
        return item if isinstance(item, MaterialItem) else None

    def _selected_entry(self) -> tuple[str, MaterialItem | PendingRecordingItem] | None:
        selection_model = self._table.selectionModel()
        if selection_model is None:
            return None
        rows = selection_model.selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        return self._rows[row] if 0 <= row < len(self._rows) else None

    @staticmethod
    def _entry_key(entry: tuple[str, MaterialItem | PendingRecordingItem]) -> tuple[str, str]:
        kind, item = entry
        return (kind, item.pending_id if isinstance(item, PendingRecordingItem) else item.id)

    def _set_count_status(self) -> None:
        if not self._pending_items and not self._items:
            self._status_label.setText("暂无素材")
            return
        if self._pending_service is None:
            self._status_label.setText(
                f"显示 {min(self._visible_count, len(self._items))} / {len(self._items)} 条素材"
            )
            return
        self._status_label.setText(
            f"待入库 {len(self._pending_items)} 条 · "
            f"素材 {len(self._items)} 条（显示 {min(self._visible_count, len(self._items))} 条）"
        )

    def _update_detail(self) -> None:
        entry = self._selected_entry()
        self._set_actions_enabled(entry is not None)
        if entry is None:
            self._detail_name.setText("未选择素材")
            for label in (
                self._detail_time,
                self._detail_duration,
                self._detail_video,
                self._detail_mode,
                self._detail_audio,
                self._detail_size,
                self._detail_path,
                self._detail_diagnostic,
                self._detail_source,
                self._detail_failure,
            ):
                label.setText("-")
            self._set_pending_actions_visible(False)
            return
        kind, item = entry
        is_pending = kind == "pending"
        self._set_pending_actions_visible(is_pending)
        self._detail_name.setText(item.file_name)
        self._detail_time.setText(item.created_at or "-")
        if isinstance(item, PendingRecordingItem):
            self._detail_duration.setText(self._format_duration(item.duration_seconds))
            self._detail_video.setText(
                f"{self._format_dimensions(item.width, item.height)} · {self._format_fps(item.fps)}"
            )
            self._detail_mode.setText(
                MODE_LABELS.get(item.capture_mode, item.capture_mode or "未知模式")
            )
            self._detail_source.setText(item.source or "录制失败降级")
            attempt_detail = f"已尝试 {item.attempt_count} 次"
            if item.last_attempt_at:
                attempt_detail += f" · 最近 {item.last_attempt_at}"
            self._detail_failure.setText(
                f"{item.last_error_summary or '-'}\n{attempt_detail}"
            )
            self._btn_retry_pending.setEnabled(item.status != "missing")
            self._btn_relink.setEnabled(item.status == "missing")
        else:
            self._detail_duration.setText(self._format_duration(item.duration_sec))
            self._detail_video.setText(
                f"{self._format_resolution(item)} · {self._format_fps(item.fps)}"
            )
            self._detail_mode.setText(MODE_LABELS.get(item.mode, item.mode or "未知模式"))
            self._detail_source.setText(item.source_type)
            self._detail_failure.setText("-")
            self._btn_delete.setEnabled(item.status != "missing")
            self._btn_relink.setEnabled(item.status in {"missing", STATUS_METADATA_INCOMPLETE})
        self._detail_audio.setText(AUDIO_LABELS.get(item.audio_source, item.audio_source or "未知"))
        self._detail_size.setText(self._format_size(item.file_size_bytes))
        self._detail_path.setText(item.file_path)
        diagnostic_dir = (
            item.diagnostics_dir if isinstance(item, PendingRecordingItem) else item.diagnostic_dir
        )
        self._detail_diagnostic.setText(diagnostic_dir or "-")
        self._btn_open.setEnabled(item.status != "missing")

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self._btn_open,
            self._btn_open_dir,
            self._btn_copy,
            self._btn_relink,
            self._btn_retry_pending,
            self._btn_remove_pending,
            self._btn_remove,
            self._btn_delete,
        ):
            button.setEnabled(enabled)

    def _set_pending_actions_visible(self, pending: bool) -> None:
        self._btn_retry_pending.setVisible(pending)
        self._btn_remove_pending.setVisible(pending)
        self._btn_remove.setVisible(not pending)
        self._btn_delete.setVisible(not pending)

    def _on_open(self) -> None:
        item = self._selected_value()
        if item:
            try:
                os.startfile(item.file_path)
            except OSError as exc:
                self._status_label.setText(f"无法打开素材：{exc}")

    def _on_open_dir(self) -> None:
        item = self._selected_value()
        if item:
            try:
                directory = item.directory if isinstance(item, MaterialItem) else str(Path(item.file_path).parent)
                os.startfile(directory)
            except OSError as exc:
                self._status_label.setText(f"无法打开目录：{exc}")

    def _on_copy(self) -> None:
        item = self._selected_value()
        if item:
            clipboard = QApplication.clipboard()
            if clipboard is None:
                self._status_label.setText("剪贴板当前不可用")
                return
            clipboard.setText(item.file_path)
            self._status_label.setText("素材路径已复制")

    def _on_relink(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        _, item = entry
        directory = item.directory if isinstance(item, MaterialItem) else str(Path(item.file_path).parent)
        selected, _ = QFileDialog.getOpenFileName(self, "重新定位素材", directory, "MP4 视频 (*.mp4)")
        if not selected:
            return
        if isinstance(item, PendingRecordingItem) and self._pending_service is not None:
            result = self._pending_service.relink(
                item.pending_id,
                selected,
                current_save_dir=self._current_save_dir,
            )
        elif isinstance(item, MaterialItem):
            result = self._service.relink(item.id, selected)
        else:
            return
        self._status_label.setText("素材已重新定位" if result.ok else f"重新定位失败：{result.error}")
        if result.ok:
            self.reload()

    def _on_retry_pending(self) -> None:
        entry = self._selected_entry()
        if entry is None or not isinstance(entry[1], PendingRecordingItem):
            return
        if self._ingestion_coordinator is None:
            self._status_label.setText("当前无法重试入库，请重启 QuickRec 后再试")
            return
        entry[1].status = "retrying"
        self._render_items()
        QApplication.processEvents()
        result = self._ingestion_coordinator.retry(
            entry[1].pending_id,
            current_save_dir=self._current_save_dir,
        )
        self.reload()
        if result.formal_indexed:
            self._status_label.setText("素材已加入素材库")
        else:
            self._status_label.setText(f"重试入库失败：{result.error or '未知错误'}")

    def _on_remove_pending(self) -> None:
        entry = self._selected_entry()
        if (
            entry is None
            or not isinstance(entry[1], PendingRecordingItem)
            or self._pending_service is None
        ):
            return
        answer = QMessageBox.question(
            self,
            "移除待处理记录",
            "只移除这条待处理记录？\n视频文件不会被删除。",
        )
        if answer != QMessageBox.Yes:
            return
        result = self._pending_service.remove(
            entry[1].pending_id,
            current_save_dir=self._current_save_dir,
        )
        if result.ok:
            self.reload()
            self._status_label.setText("待处理记录已移除，视频文件已保留")
        else:
            self._status_label.setText(f"移除待处理记录失败：{result.error}")

    def _selected_value(self) -> MaterialItem | PendingRecordingItem | None:
        entry = self._selected_entry()
        return entry[1] if entry else None

    def _on_remove(self) -> None:
        item = self._selected_item()
        if not item:
            return
        answer = QMessageBox.question(
            self,
            "从素材库移除",
            "从素材库移除这条记录？\n视频文件不会被删除。",
        )
        if answer != QMessageBox.Yes:
            return
        result = self._service.remove(item.id)
        self._status_label.setText("素材已从索引移除" if result.ok else f"移除失败：{result.error}")
        if result.ok:
            self.reload()

    def _on_delete(self) -> None:
        item = self._selected_item()
        if not item:
            return
        answer = QMessageBox.question(
            self,
            "删除视频文件",
            "将此视频移入 Windows 回收站？\n不会删除诊断日志或其他文件。",
        )
        if answer != QMessageBox.Yes:
            return
        result = self._service.recycle(item.id)
        self._status_label.setText("视频已移入回收站" if result.ok else f"删除失败：{result.error}")
        if result.ok:
            self.reload()

    def _on_import(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择旧 QuickRec 保存目录")
        if not directory:
            return
        self._discover_pending_directory(directory)
        source = Path(directory) / "QuickRecMetadata" / "recordings.json"
        if not source.is_file():
            self._status_label.setText("所选目录没有旧索引，可使用“重建目录”")
            return
        self._start_task(
            lambda _cancel: self._service.preview_v1_history(source, imported_at=_now_iso()),
            self._finish_import_preview,
            "正在读取旧索引…",
        )

    def _finish_import_preview(self, result: MigrationResult) -> None:
        if result.ok:
            answer = QMessageBox.question(
                self,
                "确认导入旧索引",
                f"新增 {result.added_count} 条，重复 {result.duplicate_count} 条，"
                f"跳过 {result.skipped_count} 条，淘汰最旧 {result.pruned_count} 条。\n"
                "确认后一次性写入素材库。",
            )
            if answer != QMessageBox.Yes:
                self._status_label.setText("旧索引导入已取消，中央索引未改变")
                return
            written = self._service.commit_migration(result)
            if written.ok:
                self.reload()
                self._status_label.setText(
                    f"导入完成：新增 {result.added_count} 条，重复 {result.duplicate_count} 条，"
                    f"跳过 {result.skipped_count} 条"
                )
            else:
                self._status_label.setText(f"导入失败：{written.error}")
        else:
            self._status_label.setText(f"导入失败：{result.error}")

    def _on_rebuild(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择 QuickRec 视频目录")
        if not directory:
            return
        self._discover_pending_directory(directory)
        self._start_task(
            lambda cancel: self._service.preview_directory(directory, cancel_requested=cancel),
            self._finish_rebuild_preview,
            "正在扫描目录，可关闭窗口取消…",
        )

    def _discover_pending_directory(self, directory: str | Path) -> None:
        if self._pending_service is None:
            return
        result = self._pending_service.discover_directory(directory)
        if not result.ok:
            self._status_label.setText(f"待入库标记发现失败：{result.error}")

    def _finish_rebuild_preview(self, preview: DirectoryScanResult) -> None:
        if preview.cancelled:
            self._status_label.setText("目录扫描已取消，中央索引未改变")
            return
        if not preview.ok:
            self._status_label.setText(f"目录扫描失败：{preview.error}")
            return
        accepted_paths: set[str] = set()
        for candidate in self._service.find_relink_candidates(preview.items):
            answer = QMessageBox.question(
                self,
                "发现重新定位候选",
                f"原路径：{candidate.old_path}\n候选路径：{candidate.candidate_path}\n"
                "是否将缺失素材重新定位到该文件？",
            )
            if answer == QMessageBox.Yes:
                relinked = self._service.relink(candidate.item_id, candidate.candidate_path)
                if relinked.ok:
                    accepted_paths.add(candidate.candidate_path)
        remaining_items = [item for item in preview.items if item.file_path not in accepted_paths]
        preview = DirectoryScanResult(
            preview.ok,
            preview.directory,
            remaining_items,
            scanned_count=preview.scanned_count,
            duplicate_count=preview.duplicate_count,
            skipped_count=preview.skipped_count,
            failed_count=preview.failed_count,
        )
        if not preview.items:
            self.reload()
            self._status_label.setText("目录扫描完成，没有需要新增的素材")
            return
        answer = QMessageBox.question(
            self,
            "确认目录重建",
            f"扫描 {preview.scanned_count} 条，成功 {len(preview.items)} 条，"
            f"已存在 {preview.duplicate_count} 条，跳过 {preview.skipped_count} 条，"
            f"失败 {preview.failed_count} 条。\n确认后写入素材库。",
        )
        if answer != QMessageBox.Yes:
            self._status_label.setText("目录重建已取消，中央索引未改变")
            return
        result = self._service.commit_scan(preview, imported_at=_now_iso())
        self._status_label.setText("目录重建完成" if result.ok else f"目录重建失败：{result.error}")
        if result.ok:
            self.reload()

    def _start_task(
        self,
        operation: Callable[[Callable[[], bool]], Any],
        result_handler: Callable[[Any], None],
        status_text: str,
    ) -> None:
        if self._task is not None:
            self._status_label.setText("已有素材任务正在进行")
            return
        self._status_label.setText(status_text)
        self._set_task_buttons_enabled(False)
        self._task_result_handler = result_handler
        self._task = _LibraryTask(operation, self)
        self._task.result_ready.connect(self._on_task_result)
        self._task.failed.connect(self._on_task_failed)
        self._task.finished.connect(self._on_task_finished)
        self._task.start()

    def _on_task_result(self, result: Any) -> None:
        if self._task_result_handler is not None:
            self._task_result_handler(result)

    def _on_task_failed(self, error: str) -> None:
        self._status_label.setText(f"素材任务失败：{error}")

    def _on_task_finished(self) -> None:
        if self._task is not None:
            self._task.deleteLater()
        self._task = None
        self._task_result_handler = None
        self._set_task_buttons_enabled(True)
        if self._close_when_task_done:
            self._close_when_task_done = False
            self.close()

    def _set_task_buttons_enabled(self, enabled: bool) -> None:
        self._btn_import.setEnabled(enabled)
        self._btn_rebuild.setEnabled(enabled)

    def _close_dialog(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:
        if self._task is not None and self._task.isRunning():
            answer = QMessageBox.question(
                self,
                "取消素材任务",
                "素材扫描仍在进行，是否取消任务并关闭窗口？",
            )
            if answer == QMessageBox.Yes:
                self._close_when_task_done = True
                self._task.requestInterruption()
                self._status_label.setText("正在取消素材任务…")
            event.ignore()
            return
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_splitter"):
            self._splitter.setOrientation(Qt.Vertical if self.width() < 760 else Qt.Horizontal)

    @staticmethod
    def _format_duration(value: float | None) -> str:
        if value is None:
            return "-"
        total = max(0, int(round(value)))
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _format_resolution(item: MaterialItem) -> str:
        return MaterialLibraryDialog._format_dimensions(item.width, item.height)

    @staticmethod
    def _format_dimensions(width: int | None, height: int | None) -> str:
        return f"{width} × {height}" if width and height else "-"

    @staticmethod
    def _format_fps(value: float | None) -> str:
        return f"{value:g} FPS" if value is not None else "-"

    @staticmethod
    def _format_size(value: int | None) -> str:
        if value is None:
            return "-"
        if value < 1024 * 1024:
            return f"{value / 1024:.1f} KB"
        return f"{value / (1024 * 1024):.1f} MB"

    @staticmethod
    def _format_status(status: str) -> str:
        if status == STATUS_AVAILABLE:
            return "可用"
        if status == STATUS_METADATA_INCOMPLETE:
            return "元数据不完整"
        return "文件已移动或删除"

    @staticmethod
    def _format_pending_status(status: str) -> str:
        if status == "retrying":
            return "正在重试"
        if status == "missing":
            return "文件已移动或删除"
        if status == "retry_failed":
            return "入库失败"
        return "待入库"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
