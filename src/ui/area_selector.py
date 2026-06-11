"""
区域选择模块

全屏遮罩 + 矩形区域选择。
"""

from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import QWidget, QApplication


class AreaSelector(QWidget):
    """区域选择器"""

    region_selected = pyqtSignal(int, int, int, int)  # (x, y, width, height)
    cancelled = pyqtSignal()

    MIN_SIZE = 100  # 最小选区尺寸

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_point = QPoint()
        self._end_point = QPoint()
        self._is_drawing = False
        self._selected_rect = QRect()

        self._init_ui()

    def _init_ui(self):
        """初始化界面"""
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setStyleSheet("background: transparent;")

    def show_fullscreen(self):
        """全屏显示选择器"""
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        self.show()
        self.activateWindow()
        self.setFocus()

    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 全屏半透明遮罩
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))

        if self._is_drawing:
            # 绘制选中区域（清除遮罩，显示原始画面）
            selection = self._get_selection_rect()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selection, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # 绘制边框
            pen = QPen(QColor(0, 150, 255), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(selection)

            # 绘制尺寸标签
            size_text = f"{selection.width()} x {selection.height()}"
            font = QFont("Consolas", 12)
            font.setBold(True)
            painter.setFont(font)

            label_rect = painter.fontMetrics().boundingRect(size_text)
            label_x = selection.center().x() - label_rect.width() // 2
            label_y = selection.top() - label_rect.height() - 8

            if label_y < 0:
                label_y = selection.bottom() + 8

            painter.fillRect(
                label_x - 4, label_y - 2,
                label_rect.width() + 8, label_rect.height() + 4,
                QColor(0, 0, 0, 180)
            )
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(label_x, label_y + label_rect.height() - 4, size_text)

    def mousePressEvent(self, event):
        """鼠标按下：记录起点"""
        if event.button() == Qt.LeftButton:
            self._start_point = event.pos()
            self._end_point = event.pos()
            self._is_drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        """鼠标移动：更新终点，重绘"""
        if self._is_drawing:
            self._end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        """鼠标松开：发送选区信号"""
        if event.button() == Qt.LeftButton and self._is_drawing:
            self._is_drawing = False
            selection = self._get_selection_rect()

            if selection.width() >= self.MIN_SIZE and selection.height() >= self.MIN_SIZE:
                self._selected_rect = selection
                self.region_selected.emit(
                    selection.x(), selection.y(),
                    selection.width(), selection.height()
                )
            else:
                # 选区太小，视为取消
                self.cancelled.emit()

            self.close()

    def keyPressEvent(self, event):
        """ESC 键取消选择"""
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()

    def _get_selection_rect(self) -> QRect:
        """获取规范化选区矩形"""
        return QRect(
            min(self._start_point.x(), self._end_point.x()),
            min(self._start_point.y(), self._end_point.y()),
            abs(self._end_point.x() - self._start_point.x()),
            abs(self._end_point.y() - self._start_point.y()),
        )