"""
区域选择模块

全屏遮罩 + 矩形区域选择。
v1.1: 修复 Win11 点击穿透、新增确认对话框、最小尺寸提示、白色虚线边框。
"""

from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QApplication, QDesktopWidget,
    QPushButton, QLabel, QHBoxLayout, QVBoxLayout
)


class AreaSelector(QWidget):
    """区域选择器

    v1.1 修复：
    - 移除 Qt.Tool（Win11 点击穿透根因）
    - 添加 Qt.StrongFocus 确保焦点
    - show_fullscreen() 中 raise_() → activateWindow() → setFocus()

    v1.1 新增：
    - 确认对话框：拖拽完成后在选区中心显示"开始录制"/"取消"
    - 最小尺寸提示：选区 < 100x100 显示红色提示
    - 白色虚线边框（原蓝色实线）
    """

    region_selected = pyqtSignal(int, int, int, int)  # (x, y, width, height)
    cancelled = pyqtSignal()

    MIN_SIZE = 100  # 最小选区边长

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_point = QPoint()
        self._end_point = QPoint()
        self._is_drawing = False
        self._selected_rect = QRect()

        # 确认对话框相关
        self._confirm_widget = None
        self._tip_label = None

        self._init_ui()

    def _init_ui(self):
        """初始化界面"""
        # 移除 Qt.Tool（Win11 点击穿透根因），仅保留必要标志
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setStyleSheet("background: transparent;")
        # 强焦点策略，确保 Win11 下可接收键盘输入
        self.setFocusPolicy(Qt.StrongFocus)

    def show_fullscreen(self):
        """全屏显示选择器"""
        desktop = QApplication.desktop()
        if desktop:
            geo = desktop.geometry()
            self.setGeometry(geo)
        self.show()
        self.raise_()          # 提升到最顶层
        self.activateWindow()  # 激活窗口
        self.setFocus()        # 强制获取焦点

    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 全屏半透明遮罩
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))

        if self._is_drawing:
            selection = self._get_selection_rect()
            # 清除选中区域的遮罩，显示原始画面
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selection, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # 白色虚线边框
            pen = QPen(QColor(255, 255, 255), 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(selection)

            # 尺寸标签
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
        """鼠标按下：右键取消，左键记录起点"""
        # 清除之前的确认对话框
        self._clear_confirm()

        if event.button() == Qt.RightButton:
            self.cancelled.emit()
            self.close()
            return
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
        """鼠标松开：判断选区大小，显示确认对话框或提示"""
        if event.button() == Qt.LeftButton and self._is_drawing:
            self._is_drawing = False
            selection = self._get_selection_rect()

            if selection.width() >= self.MIN_SIZE and selection.height() >= self.MIN_SIZE:
                self._selected_rect = selection
                self.update()
                self._show_confirm_dialog(selection)
            else:
                # 选区太小，显示红色提示
                self._show_min_size_tip(event.pos())
                QTimer.singleShot(1000, self._cancel_and_close)

    def keyPressEvent(self, event):
        """ESC 键取消选择"""
        if event.key() == Qt.Key_Escape:
            self._cancel_and_close()

    def _get_selection_rect(self) -> QRect:
        """获取规范化选区矩形"""
        return QRect(
            min(self._start_point.x(), self._end_point.x()),
            min(self._start_point.y(), self._end_point.y()),
            abs(self._end_point.x() - self._start_point.x()),
            abs(self._end_point.y() - self._start_point.y()),
        )

    def _show_confirm_dialog(self, rect: QRect):
        """在选区中心显示确认对话框"""
        self._clear_confirm()

        widget = QWidget(self)
        widget.setStyleSheet("""
            QWidget {
                background-color: rgba(26, 26, 46, 230);
                border-radius: 8px;
            }
            QPushButton {
                background-color: transparent;
                color: #bdc3c7;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 30);
                color: #ffffff;
            }
            QPushButton#btn_start {
                color: #2ecc71;
                border-color: #2ecc71;
            }
            QPushButton#btn_start:hover {
                background-color: rgba(46, 204, 113, 30);
            }
        """)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        btn_start = QPushButton("▶ 开始录制")
        btn_start.setObjectName("btn_start")
        btn_start.clicked.connect(self._on_start_recording)

        btn_cancel = QPushButton("✕ 取消")
        btn_cancel.clicked.connect(self._on_cancel)

        layout.addWidget(btn_start)
        layout.addWidget(btn_cancel)

        widget.adjustSize()
        # 居中放置在选区中心
        x = rect.center().x() - widget.width() // 2
        y = rect.center().y() - widget.height() // 2
        widget.move(x, y)
        widget.show()

        self._confirm_widget = widget

    def _show_min_size_tip(self, pos: QPoint):
        """显示选区太小的红色提示"""
        self._clear_confirm()

        label = QLabel("选区太小 (最小 100×100)", self)
        label.setStyleSheet("""
            QLabel {
                color: #e74c3c;
                background-color: rgba(0, 0, 0, 200);
                border: 1px solid #e74c3c;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }
        """)
        label.adjustSize()
        label.move(pos.x() - label.width() // 2, pos.y() - label.height() // 2)
        label.show()

        self._tip_label = label
        # 1秒后自动关闭
        QTimer.singleShot(1000, label.close)

    def _clear_confirm(self):
        """清除确认对话框"""
        if self._confirm_widget:
            self._confirm_widget.close()
            self._confirm_widget = None

    def _on_start_recording(self):
        """确认开始录制"""
        rect = self._selected_rect
        self._clear_confirm()
        self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
        self.close()

    def _on_cancel(self):
        """取消选择"""
        self._clear_confirm()
        self.cancelled.emit()
        self.close()

    def _cancel_and_close(self):
        """取消并关闭"""
        self._clear_confirm()
        self.cancelled.emit()
        self.close()