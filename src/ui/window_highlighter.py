from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget

from utils.window_geometry import get_window_client_rect

_FOLLOW_INTERVAL_MS = 33


class WindowHighlighter(QWidget):
    """Recording-window overlay border."""

    def __init__(self, hwnd: int, parent=None):
        super().__init__(parent)
        self._hwnd = hwnd

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._timer = QTimer(self)
        self._timer.setInterval(_FOLLOW_INTERVAL_MS)
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
        rect = get_window_client_rect(self._hwnd)
        if rect is None:
            self.hide_highlight()
            return
        if self.geometry() != rect:
            self.setGeometry(rect)

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
