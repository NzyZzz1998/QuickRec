"""
录制工具栏模块

录制中的悬浮控制窗口，显示录制状态和提供控制按钮。
"""

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QCursor
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QFrame
)


class RecordingToolbar(QWidget):
    """录制工具栏"""

    paused = pyqtSignal()
    resumed = pyqtSignal()
    stopped = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = True
        self._paused = False
        self._elapsed_seconds = 0

        self._init_ui()
        self._init_timer()

    def _init_ui(self):
        """初始化界面"""
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedHeight(40)
        self._setup_styles()

        # 主布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        # 录制指示灯
        self._indicator = QLabel("●")
        self._indicator.setFixedWidth(16)
        self._indicator.setStyleSheet("color: #e74c3c; font-size: 16px;")
        layout.addWidget(self._indicator)

        # 计时器
        self._label_timer = QLabel("00:00")
        self._label_timer.setFont(QFont("Consolas", 11))
        self._label_timer.setStyleSheet("color: #ecf0f1;")
        self._label_timer.setFixedWidth(50)
        layout.addWidget(self._label_timer)

        # 暂停按钮
        self._btn_pause = QPushButton("⏸ 暂停")
        self._btn_pause.setFixedSize(70, 28)
        self._btn_pause.clicked.connect(self._on_pause)
        layout.addWidget(self._btn_pause)

        # 停止按钮
        self._btn_stop = QPushButton("⏹ 停止")
        self._btn_stop.setFixedSize(70, 28)
        self._btn_stop.clicked.connect(self._on_stop)
        layout.addWidget(self._btn_stop)

        # 取消按钮
        self._btn_cancel = QPushButton("✕ 取消")
        self._btn_cancel.setFixedSize(70, 28)
        self._btn_cancel.clicked.connect(self._on_cancel)
        layout.addWidget(self._btn_cancel)

        # 拖拽支持
        self._drag_pos = None

    def _setup_styles(self):
        """设置样式"""
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(26, 26, 46, 230);
                border-radius: 8px;
            }
            QPushButton {
                background-color: transparent;
                color: #bdc3c7;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 30);
                color: #ffffff;
            }
        """)

    def _init_timer(self):
        """初始化计时器"""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_timer)

    def start_countdown(self, seconds: int = 0):
        """开始录制计时"""
        self._elapsed_seconds = 0
        self._recording = True
        self._paused = False
        self._timer.start(1000)
        # 将工具栏定位到屏幕顶部居中
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            self.move(
                screen_geo.center().x() - self.width() // 2,
                screen_geo.top() + 10
            )

    def stop_countdown(self):
        """停止录制计时"""
        self._timer.stop()
        self._elapsed_seconds = 0
        self._label_timer.setText("00:00")

    def set_paused(self, paused: bool):
        """设置暂停状态"""
        self._paused = paused
        if paused:
            self._btn_pause.setText("▶ 继续")
            self._indicator.setStyleSheet("color: #f39c12; font-size: 16px;")
        else:
            self._btn_pause.setText("⏸ 暂停")
            self._indicator.setStyleSheet("color: #e74c3c; font-size: 16px;")

    def show_saving(self):
        """显示保存中状态，禁用所有按钮"""
        self._recording = False
        self._timer.stop()
        self._label_timer.setText("保存中...")
        self._indicator.setStyleSheet("color: #3498db; font-size: 16px;")
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_cancel.setEnabled(False)

    def _update_timer(self):
        """更新计时器显示"""
        if not self._paused:
            self._elapsed_seconds += 1
        minutes = self._elapsed_seconds // 60
        seconds = self._elapsed_seconds % 60
        self._label_timer.setText(f"{minutes:02d}:{seconds:02d}")

    def _on_pause(self):
        """暂停/继续按钮点击"""
        if self._paused:
            self.resumed.emit()
        else:
            self.paused.emit()

    def _on_stop(self):
        """停止按钮点击"""
        self.stopped.emit()

    def _on_cancel(self):
        """取消按钮点击"""
        self.cancelled.emit()

    # 拖拽支持
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None