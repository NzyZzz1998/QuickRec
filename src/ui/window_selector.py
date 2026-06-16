"""
窗口选择器模块

枚举当前可见窗口列表，让用户选择一个窗口作为录制目标。
使用 Win32 API（ctypes）枚举窗口，PyQt5 QDialog 显示列表。
"""

import ctypes
import ctypes.wintypes
import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel
)

logger = logging.getLogger(__name__)

# Win32 API 常量
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_VISIBLE = 0x10000000
WS_MINIMIZE = 0x20000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOINHERITLAYOUT = 0x00100000

# 系统窗口类名黑名单（不显示在选择列表中）
_SYSTEM_WINDOW_CLASSES = {
    # 桌面和任务栏
    "Progman",           # 桌面
    "Shell_TrayWnd",     # 任务栏
    "WorkerW",           # 桌面辅助
    "Desktop Window X",  # 桌面
    # 输入法
    "IME",
    "MSCTFIME UI",
    "IMEUIWindow",
    # 提示和菜单
    "tooltips_class32",
    "MenuDeskBar",
    "ToolbarWindow32",
    # 系统控件
    "Button",            # 系统按钮
    "ComboBox",
    "ComboBoxEx32",
    "Edit",
    "ListBox",
    "Static",
    "SysHeader32",
    "SysListView32",
    "SysTreeView32",
    "msctls_statusbar32",
    "msctls_updown32",
    "msctls_progress32",
    "msctls_hotkey32",
    "msctls_trackbar32",
    "msctls_tab32",
    # 系统通知和浮动窗口
    "NotifyIconOverflowWindow",  # 通知溢出窗口
    "TaskManagerWindow",         # 任务管理器（隐藏窗口）
    "SearchUI",                  # 搜索界面后台
    "Shell_InputSwitch",         # 输入法切换
    # DWM 和渲染
    "DwmWindowCompositionWindow",  # DWM 合成
    "MultitaskViewFrame",         # 多任务视图
    "Xaml_WindowedPopupClass",    # XAML 弹出
}


class WindowSelector(QDialog):
    """窗口选择对话框

    显示当前可见窗口列表，用户选择一个窗口后，
    通过 window_selected 信号返回窗口句柄（HWND）和标题。
    """

    window_selected = pyqtSignal(int, str)  # (hwnd, title)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._windows = []  # [(hwnd, title, rect), ...]
        self._init_ui()
        self.refresh_windows()

    def _init_ui(self):
        """初始化界面"""
        self.setWindowTitle("选择录制窗口")
        self.setMinimumSize(420, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)

        # 提示标签
        hint = QLabel("选择要录制的窗口：")
        hint.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(hint)

        # 窗口列表
        self._list_widget = QListWidget()
        self._list_widget.setFont(QFont("Microsoft YaHei", 10))
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list_widget)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_refresh = QPushButton("刷新")
        self._btn_refresh.setFixedSize(80, 32)
        self._btn_refresh.clicked.connect(self.refresh_windows)
        btn_layout.addWidget(self._btn_refresh)

        self._btn_select = QPushButton("选择")
        self._btn_select.setFixedSize(80, 32)
        self._btn_select.clicked.connect(self._on_select_clicked)
        btn_layout.addWidget(self._btn_select)

        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setFixedSize(80, 32)
        self._btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self._btn_cancel)

        layout.addLayout(btn_layout)

        # 暗色主题
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b3d;
                color: #ecf0f1;
            }
            QListWidget {
                background-color: #1a1a2e;
                color: #ecf0f1;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background-color: #4a9eff;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #3a3a5e;
            }
            QPushButton {
                background-color: #3a3a5e;
                color: #ecf0f1;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a4a7e;
            }
            QLabel {
                color: #ecf0f1;
            }
        """)

    def refresh_windows(self):
        """重新枚举并刷新窗口列表"""
        self._windows = self._enum_visible_windows()
        self._list_widget.clear()

        for hwnd, title, rect, is_minimized in self._windows:
            suffix = "  (最小化)" if is_minimized else f"  ({rect.width()}×{rect.height()})"
            item = QListWidgetItem(f"{title}{suffix}")
            item.setData(Qt.UserRole, hwnd)
            self._list_widget.addItem(item)

        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def _on_item_double_clicked(self, item):
        """双击选择窗口"""
        self._select_window(item)

    def _on_select_clicked(self):
        """点击"选择"按钮"""
        current_item = self._list_widget.currentItem()
        if current_item:
            self._select_window(current_item)

    def _on_cancel_clicked(self):
        """点击"取消"按钮"""
        self.cancelled.emit()
        self.reject()

    def _select_window(self, item):
        """选中窗口并发射信号"""
        hwnd = item.data(Qt.UserRole)
        # 根据hwnd找title
        title = ""
        for entry in self._windows:
            if entry[0] == hwnd:
                title = entry[1]
                break
        self.window_selected.emit(hwnd, title)
        self.accept()

    @staticmethod
    def _enum_visible_windows():
        """枚举所有可见窗口

        Returns:
            [(hwnd, title, QRect), ...] 列表
        """
        user32 = ctypes.windll.user32
        windows = []

        # 回调函数类型
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def _enum_callback(hwnd, _lparam):
            # 只保留可见窗口
            if not user32.IsWindowVisible(hwnd):
                return True

            # 获取窗口标题
            title_length = user32.GetWindowTextLengthW(hwnd)
            if title_length == 0:
                return True
            title = ctypes.create_unicode_buffer(title_length + 1)
            user32.GetWindowTextW(hwnd, title, title_length + 1)
            title_str = title.value.strip()
            if not title_str:
                return True

            # 获取类名并过滤系统窗口
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            if class_name.value in _SYSTEM_WINDOW_CLASSES:
                return True

            # 获取扩展样式，过滤工具窗口
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if (ex_style & WS_EX_TOOLWINDOW) and not (ex_style & WS_EX_APPWINDOW):
                return True

            # 检查是否最小化（不过滤，用于标注）
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            is_minimized = bool(style & WS_MINIMIZE)

            # 获取窗口位置
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            width = rect.right - rect.left
            height = rect.bottom - rect.top

            # 过滤过小的窗口（最小化窗口宽高可能为0，不在此过滤）
            if not is_minimized and (width < 50 or height < 50):
                return True

            from PyQt5.QtCore import QRect
            windows.append((hwnd, title_str, QRect(rect.left, rect.top, max(width, 100), max(height, 100)), is_minimized))
            return True

        user32.EnumWindows(WNDENUMPROC(_enum_callback), 0)
        return windows