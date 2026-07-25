"""
窗口选择器模块（v1.3 重写）

从零重写，修复 v1.2 已知 Bug：
  - ctypes.wintypes 未显式导入 → EnumWindows 回调 0xC0000409 崩溃
  - UWP 窗口被误过滤（ApplicationFrameWindow 从黑名单移除）
  - 系统控件出现在列表中（扩充黑名单）
"""

import ctypes
import ctypes.wintypes

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ui.design_system import SELECTOR_STYLESHEET, set_button_icon

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
        self._accepted = False
        self._cancel_notified = False
        self.setWindowTitle("选择录制窗口")
        self.setObjectName("windowSelector")
        self.setMinimumSize(480, 340)
        self.resize(560, 420)
        self.setStyleSheet(SELECTOR_STYLESHEET)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("选择录制窗口")
        title.setObjectName("selectorTitle")
        layout.addWidget(title)
        subtitle = QLabel("选择一个可见桌面窗口；最小化窗口将在确认后恢复。")
        subtitle.setObjectName("selectorSubtitle")
        layout.addWidget(subtitle)

        self._list = QListWidget()
        self._list.setAccessibleName("可录制窗口列表")
        self._list.itemDoubleClicked.connect(self._select)
        self._list.currentItemChanged.connect(
            lambda current, _previous: self._btn_select.setEnabled(current is not None)
        )
        layout.addWidget(self._list)

        self._summary = QLabel("正在读取窗口列表…")
        self._summary.setObjectName("selectorSubtitle")
        layout.addWidget(self._summary)

        btn_row = QHBoxLayout()
        self._btn_refresh = QPushButton("刷新列表")
        self._btn_refresh.clicked.connect(self._refresh)
        self._btn_refresh.setToolTip("重新读取当前可录制的桌面窗口")
        set_button_icon(self._btn_refresh, "refresh")
        self._btn_select = QPushButton("选择窗口")
        self._btn_select.setProperty("role", "primary")
        self._btn_select.setEnabled(False)
        self._btn_select.setToolTip("确认所选窗口并进入倒计时或开始录制")
        set_button_icon(self._btn_select, "window", color="#FFFFFF")
        self._btn_select.clicked.connect(self._select)
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setToolTip("关闭窗口选择器并返回上一个入口")
        self._btn_cancel.clicked.connect(self._cancel)
        btn_row.addWidget(self._btn_refresh)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_select)
        btn_row.addWidget(self._btn_cancel)
        layout.addLayout(btn_row)

    def _refresh(self):
        self._list.clear()
        self._windows = _enum_visible_windows()
        for hwnd, title, is_min in self._windows:
            label = f"{title}（最小化）" if is_min else title
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, (hwnd, title, is_min))
            item.setSizeHint(QSize(0, 46))
            self._list.addItem(item)
        self._summary.setText(
            f"找到 {len(self._windows)} 个可录制窗口"
            if self._windows
            else "未找到可录制窗口，可刷新后重试"
        )
        self._btn_select.setEnabled(self._list.currentItem() is not None)

    def _select(self):
        item = self._list.currentItem()
        if item is None:
            return
        hwnd, title, is_min = item.data(Qt.UserRole)
        # 仅恢复最小化窗口到可见，置前台交由 main._on_window_selected 统一处理
        if is_min:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        self._accepted = True
        self.window_selected.emit(hwnd, title)
        self.accept()

    def _cancel(self):
        self._notify_cancelled()
        self.reject()

    def closeEvent(self, event):
        if not self._accepted:
            self._notify_cancelled()
        super().closeEvent(event)

    def _notify_cancelled(self) -> None:
        if not self._cancel_notified:
            self._cancel_notified = True
            self.cancelled.emit()
