"""
鼠标点击高亮模块

在屏幕叠加层显示鼠标左键点击的扩散圆圈动画。
仅作为屏幕叠加层可见，不渲染到视频帧。
使用 pynput 鼠标监听器捕获点击，通过信号桥转发到 Qt 主线程。
"""

import logging

from PyQt5.QtCore import QPropertyAnimation, QObject, QRectF, Qt, pyqtProperty, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtWidgets import QWidget
from pynput import mouse

logger = logging.getLogger(__name__)

CLICK_CIRCLE_RADIUS_MAX = 30
CLICK_CIRCLE_DURATION = 300
CLICK_CIRCLE_COLOR = QColor(231, 76, 60, 180)
CLICK_CIRCLE_BORDER_WIDTH = 3


class _ClickBridge(QObject):
    """pynput 鼠标线程 → Qt 主线程信号桥"""

    click_occurred = pyqtSignal(int, int)


class ClickCircle(QWidget):
    """单击扩散圆圈动画

    在屏幕 (x, y) 位置显示一个从小到大扩散的圆圈，
    持续约 300ms 后消失。不拦截鼠标事件。
    """

    def __init__(self, x: int, y: int, parent=None):
        super().__init__(parent)
        self._radius = 0
        self._opacity = 1.0

        size = CLICK_CIRCLE_RADIUS_MAX * 2 + CLICK_CIRCLE_BORDER_WIDTH * 2 + 4
        self.setFixedSize(size, size)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.move(x - size // 2, y - size // 2)

    def showEvent(self, event):
        """窗口显示时启动动画"""
        super().showEvent(event)
        self._start_animation()

    def _start_animation(self):
        """启动扩散动画：半径 0→30px + 透明度 1→0"""
        self._anim_radius = QPropertyAnimation(self, b"radius")
        self._anim_radius.setDuration(CLICK_CIRCLE_DURATION)
        self._anim_radius.setStartValue(0)
        self._anim_radius.setEndValue(CLICK_CIRCLE_RADIUS_MAX)

        self._anim_opacity = QPropertyAnimation(self, b"opacity")
        self._anim_opacity.setDuration(CLICK_CIRCLE_DURATION)
        self._anim_opacity.setStartValue(1.0)
        self._anim_opacity.setEndValue(0.0)

        self._anim_radius.finished.connect(self.close)
        self._anim_radius.finished.connect(self.deleteLater)

        self._anim_radius.start()
        self._anim_opacity.start()

    # --- QPropertyAnimation 属性 ---

    def get_radius(self):
        return self._radius

    def set_radius(self, value):
        self._radius = value
        self.update()

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, value):
        self._opacity = value
        self.update()

    radius = pyqtProperty(int, get_radius, set_radius)
    opacity = pyqtProperty(float, get_opacity, set_opacity)

    # --- 绘制 ---

    def paintEvent(self, event):
        if self._radius <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(CLICK_CIRCLE_COLOR)
        color.setAlpha(int(CLICK_CIRCLE_COLOR.alpha() * self._opacity))

        pen = QPen(color, CLICK_CIRCLE_BORDER_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        center_x = self.width() / 2
        center_y = self.height() / 2
        painter.drawEllipse(
            QRectF(
                center_x - self._radius,
                center_y - self._radius,
                self._radius * 2,
                self._radius * 2,
            )
        )
        painter.end()


class ClickHighlighter:
    """鼠标点击高亮管理器

    当配置开启且录制中时，监听鼠标左键点击并在点击位置显示扩散圆圈动画。
    仅作为屏幕叠加层，不影响录制的视频帧。
    """

    def __init__(self):
        self._listener = None
        self._bridge = _ClickBridge()
        self._bridge.click_occurred.connect(self._show_click_effect)

    def start(self):
        """启动鼠标监听"""
        if self._listener is not None:
            return
        self._listener = mouse.Listener(on_click=self._on_click)
        self._listener.start()
        logger.debug("ClickHighlighter 已启动")

    def stop(self):
        """停止鼠标监听"""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        logger.debug("ClickHighlighter 已停止")

    def is_running(self) -> bool:
        """是否正在监听"""
        return self._listener is not None and self._listener.is_alive()

    def _on_click(self, x, y, button, pressed):
        """pynput 鼠标点击回调（在 pynput 线程中执行）"""
        if button == mouse.Button.left and pressed:
            self._bridge.click_occurred.emit(x, y)

    def _show_click_effect(self, x: int, y: int):
        """在屏幕位置创建扩散圆圈（Qt 主线程）"""
        ClickCircle(x, y).show()