"""
窗口边框高亮模块

在录制目标窗口四周绘制绿色虚线边框。
仅作为屏幕叠加层，不渲染到视频帧。
"""

import ctypes
import ctypes.wintypes
import logging

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtWidgets import QWidget

logger = logging.getLogger(__name__)

BORDER_WIDTH = 3
BORDER_COLOR = QColor(0, 200, 0, 200)  # 绿色半透明
TRACK_INTERVAL_MS = 100  # 位置跟踪间隔（毫秒）


class WindowHighlighter(QWidget):
    """录制窗口边框高亮指示器

    在目标窗口四周绘制绿色虚线边框。
    仅作为屏幕叠加层，不渲染到视频帧。
    """

    def __init__(self, hwnd: int, parent=None):
        super().__init__(parent)
        self._hwnd = hwnd
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_position)

        # 无边框、置顶、工具窗口、透明背景、不拦截鼠标
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

    def show_highlight(self):
        """显示高亮边框并启动位置跟踪"""
        self._update_position()
        self.show()
        self._timer.start(TRACK_INTERVAL_MS)
        logger.debug(f"WindowHighlighter 已显示 (hwnd={self._hwnd})")

    def hide_highlight(self):
        """隐藏高亮边框并停止位置跟踪"""
        self._timer.stop()
        self.hide()
        logger.debug(f"WindowHighlighter 已隐藏 (hwnd={self._hwnd})")

    def _update_position(self):
        """根据目标窗口位置更新自身位置"""
        user32 = ctypes.windll.user32

        # 检查窗口是否仍然有效
        if not user32.IsWindow(self._hwnd):
            logger.info(f"目标窗口已关闭 (hwnd={self._hwnd})")
            self.hide_highlight()
            return

        # 检查窗口是否可见
        if not user32.IsWindowVisible(self._hwnd):
            self.hide()
            return

        # 获取窗口位置
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(self._hwnd, ctypes.byref(rect))

        width = rect.right - rect.left
        height = rect.bottom - rect.top

        # 窗口最小化时隐藏
        if width < 10 or height < 10:
            self.hide()
            return

        self.setGeometry(
            rect.left - BORDER_WIDTH,
            rect.top - BORDER_WIDTH,
            width + BORDER_WIDTH * 2,
            height + BORDER_WIDTH * 2,
        )
        self.show()

    def paintEvent(self, event):
        """绘制绿色虚线边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(BORDER_COLOR, BORDER_WIDTH, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # 在 widget 边缘绘制边框
        painter.drawRect(
            self.rect().adjusted(
                BORDER_WIDTH // 2,
                BORDER_WIDTH // 2,
                -(BORDER_WIDTH // 2),
                -(BORDER_WIDTH // 2),
            )
        )
        painter.end()

    def closeEvent(self, event):
        """关闭时停止定时器"""
        self._timer.stop()
        super().closeEvent(event)