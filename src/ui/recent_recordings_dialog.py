from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from utils.recording_history import (
    STATUS_AVAILABLE,
    RecordingHistoryItem,
    load_history,
    open_recording_directory,
    open_recording_file,
    remove_history_item,
)


class RecentRecordingsDialog(QDialog):
    """最近录制轻量窗口。"""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._items: list[RecordingHistoryItem] = []
        self.setWindowTitle("最近录制")
        self.resize(760, 420)
        self._init_ui()
        self.reload()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["文件", "模式", "时间", "大小", "状态"])
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._update_actions)
        layout.addWidget(self._table)

        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self._btn_open_file = QPushButton("打开")
        self._btn_open_file.clicked.connect(self._on_open_file)
        action_layout.addWidget(self._btn_open_file)

        self._btn_open_dir = QPushButton("打开目录")
        self._btn_open_dir.clicked.connect(self._on_open_dir)
        action_layout.addWidget(self._btn_open_dir)

        self._btn_copy_path = QPushButton("复制路径")
        self._btn_copy_path.clicked.connect(self._on_copy_path)
        action_layout.addWidget(self._btn_copy_path)

        self._btn_remove = QPushButton("从列表移除")
        self._btn_remove.clicked.connect(self._on_remove)
        action_layout.addWidget(self._btn_remove)

        self._btn_close = QPushButton("关闭")
        self._btn_close.clicked.connect(self.close)
        action_layout.addWidget(self._btn_close)
        layout.addLayout(action_layout)
        self._update_actions()

    def reload(self) -> None:
        result = load_history(self._config)
        self._items = result.items if result.ok else []
        self._render_items()
        if not result.ok:
            self._status_label.setText("最近录制加载失败")
        elif not self._items:
            self._status_label.setText("暂无录制记录")
        else:
            self._status_label.setText(f"共 {len(self._items)} 条最近录制")
        self._update_actions()

    def _render_items(self) -> None:
        self._table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            values = [
                item.file_name,
                item.mode,
                item.created_at,
                self._format_size(item.file_size_bytes),
                "可用" if item.status == STATUS_AVAILABLE else "文件已移动或删除",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.UserRole, item.id)
                self._table.setItem(row, column, cell)
        self._table.resizeColumnsToContents()

    def _selected_item(self) -> RecordingHistoryItem | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]

    def _update_actions(self) -> None:
        item = self._selected_item()
        has_item = item is not None
        file_exists = has_item and item.status == STATUS_AVAILABLE
        self._btn_open_file.setEnabled(bool(file_exists))
        self._btn_open_dir.setEnabled(has_item)
        self._btn_copy_path.setEnabled(has_item)
        self._btn_remove.setEnabled(has_item)

    def _on_open_file(self) -> None:
        item = self._selected_item()
        if not item:
            return
        if open_recording_file(item.file_path):
            self._status_label.setText("录制文件已打开")
        else:
            self._status_label.setText("无法打开录制文件")

    def _on_open_dir(self) -> None:
        item = self._selected_item()
        if not item:
            return
        if open_recording_directory(item.file_path):
            self._status_label.setText("录制目录已打开")
        else:
            self._status_label.setText("无法打开录制目录")

    def _on_copy_path(self) -> None:
        item = self._selected_item()
        if not item:
            return
        QApplication.clipboard().setText(item.file_path)
        self._status_label.setText("录制路径已复制")

    def _on_remove(self) -> None:
        item = self._selected_item()
        if not item:
            return
        result = remove_history_item(self._config, item.id)
        if result.ok:
            self.reload()
            self._status_label.setText("记录已从列表移除")
        else:
            self._status_label.setText("移除失败")

    @staticmethod
    def _format_size(size: int | None) -> str:
        if size is None:
            return "-"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        return f"{size / (1024 * 1024):.1f}MB"


def reveal_recording_directory(file_path: str | Path) -> bool:
    return open_recording_directory(file_path)
