"""
窗口边框高亮模块（v1.3 重写）

从零重写，修复 v1.2 已知 Bug：
  - Qt.WA_TransparentForMouseInput 属性名错误（应为 WA_TransparentForMouseEvents）
  - ctypes.wintypes 未显式导入 → _update_position 崩溃
  - 窗口关闭后 hwnd 失效无保护
"""

import ctypes
import ctypes.wintypes

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget


class WindowHighlighter(QWidget):
    """录制窗口绿色虚线边框高亮（仅屏幕叠加层）"""

    def __init__(self, hwnd: int, parent=None):
        super().__init__(parent)
        self._hwnd = hwnd

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._update_position)

        self._update_position()

    def show_highlight(self):
        self.show()
        self._timer.start()

    def hide_highlight(self):
        self._timer.stop()
        self.hide()

    @property
    def hwnd(self) -> int:
        return self._hwnd

    def _update_position(self):
        # 使用客户区坐标（GetClientRect + ClientToScreen），与 recorder_manager 保持一致
        user32 = ctypes.windll.user32
        if not user32.IsWindow(self._hwnd) or user32.IsIconic(self._hwnd):
            self.hide_highlight()
            return
        client_rect = ctypes.wintypes.RECT()
        user32.GetClientRect(self._hwnd, ctypes.byref(client_rect))
        w = client_rect.right
        h = client_rect.bottom
        if w < 10 or h < 10:
            return
        pt = ctypes.wintypes.POINT()
        user32.ClientToScreen(self._hwnd, ctypes.byref(pt))
        self.setGeometry(pt.x, pt.y, w, h)

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(QColor("#00e676"), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
        painter.end()

    def __del__(self):
        try:
            self.hide_highlight()
        except Exception:
            pass
