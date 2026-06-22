"""
窗口选择器模块（v1.3 重写）

从零重写，修复 v1.2 已知 Bug：
  - ctypes.wintypes 未显式导入 → EnumWindows 回调 0xC0000409 崩溃
  - UWP 窗口被误过滤（ApplicationFrameWindow 从黑名单移除）
  - 系统控件出现在列表中（扩充黑名单）
"""

import ctypes
import ctypes.wintypes

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton,
)

_SYSTEM_CLASSES = {
    "Shell_TrayWnd", "Progman", "WorkerW", "DV2ControlHost",
    "MsgrIMEWindowClass", "SysShadow", "tooltips_class32",
    "Button", "ComboBox", "Edit", "Static", "ScrollBar",
    "IME", "MSCTFIME UI",
}


def _enum_visible_windows():
    """枚举可见窗口，返回 [(hwnd, title, is_minimized)]"""
    user32 = ctypes.windll.user32
    results = []

    def callback(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            ex_style = user32.GetWindowLongW(hwnd, -20)
            if ex_style & 0x00000080:  # WS_EX_TOOLWINDOW
                return True
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buf, 256)
            if buf.value in _SYSTEM_CLASSES:
                return True
            title_buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buf, length + 1)
            results.append((hwnd, title_buf.value, bool(user32.IsIconic(hwnd))))
        except Exception:
            pass
        return True

    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)(callback)
    user32.EnumWindows(proc, 0)
    return results


class WindowSelector(QDialog):
    """窗口选择对话框"""

    window_selected = pyqtSignal(int, str)  # (hwnd, title)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._windows = []
        self.setWindowTitle("选择录制窗口")
        self.setMinimumSize(400, 300)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._select)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self._refresh)
        self._btn_select = QPushButton("选择")
        self._btn_select.clicked.connect(self._select)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self._cancel)
        btn_row.addWidget(btn_refresh)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_select)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _refresh(self):
        self._list.clear()
        self._windows = _enum_visible_windows()
        for hwnd, title, is_min in self._windows:
            label = f"{title}（最小化）" if is_min else title
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, (hwnd, title, is_min))
            self._list.addItem(item)

    def _select(self):
        item = self._list.currentItem()
        if item is None:
            return
        hwnd, title, is_min = item.data(Qt.UserRole)
        # 仅恢复最小化窗口到可见，置前台交由 main._on_window_selected 统一处理
        if is_min:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        self.window_selected.emit(hwnd, title)
        self.accept()

    def _cancel(self):
        self.cancelled.emit()
        self.reject()

    def closeEvent(self, event):
        self.cancelled.emit()
        super().closeEvent(event)
