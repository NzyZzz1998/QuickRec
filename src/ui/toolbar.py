"""
录制工具栏模块

录制中的悬浮控制窗口，显示录制状态和提供控制按钮。

v1.1 新增：编码完成后结果条模式，支持打开文件夹和自动关闭。
"""

import os
import subprocess

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QCursor
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QFrame
)


class RecordingToolbar(QWidget):
    """录制工具栏

    v1.1 新增：
    - show_result() 结果条模式（✓ 时长 | 已保存 | 📂 打开 | ✕ 关闭）
    - open_folder_requested / open_file_requested 信号
    - 5 秒自动关闭定时器
    """

    paused = pyqtSignal()
    resumed = pyqtSignal()
    stopped = pyqtSignal()
    cancelled = pyqtSignal()

    # v1.1 新增信号
    open_folder_requested = pyqtSignal()
    open_file_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = True
        self._paused = False
        self._elapsed_seconds = 0

        # v1.1 新增状态
        self._result_mode = False
        self._output_path = ""
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._on_auto_close)

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
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 5, 10, 5)
        self._layout.setSpacing(8)

        # 录制指示灯
        self._indicator = QLabel("●")
        self._indicator.setFixedWidth(16)
        self._indicator.setStyleSheet("color: #e74c3c; font-size: 16px;")
        self._layout.addWidget(self._indicator)

        # 计时器
        self._label_timer = QLabel("00:00")
        self._label_timer.setFont(QFont("Consolas", 11))
        self._label_timer.setStyleSheet("color: #ecf0f1;")
        self._label_timer.setFixedWidth(50)
        self._layout.addWidget(self._label_timer)

        # 录制模式的按钮
        self._btn_pause = QPushButton("⏸ 暂停")
        self._btn_pause.setFixedSize(70, 28)
        self._btn_pause.clicked.connect(self._on_pause)
        self._layout.addWidget(self._btn_pause)

        self._btn_stop = QPushButton("⏹ 停止")
        self._btn_stop.setFixedSize(70, 28)
        self._btn_stop.clicked.connect(self._on_stop)
        self._layout.addWidget(self._btn_stop)

        self._btn_cancel = QPushButton("✕ 取消")
        self._btn_cancel.setFixedSize(70, 28)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._layout.addWidget(self._btn_cancel)

        # 结果条模式的按钮（初始隐藏）
        self._btn_saved = QPushButton("✓ 已保存")
        self._btn_saved.setFixedSize(70, 28)
        self._btn_saved.clicked.connect(self._on_open_file)
        self._btn_saved.hide()
        self._layout.addWidget(self._btn_saved)

        self._btn_open = QPushButton("📂 打开")
        self._btn_open.setFixedSize(70, 28)
        self._btn_open.clicked.connect(self._on_open_folder)
        self._btn_open.hide()
        self._layout.addWidget(self._btn_open)

        self._btn_close_result = QPushButton("✕ 关闭")
        self._btn_close_result.setFixedSize(70, 28)
        self._btn_close_result.clicked.connect(self._on_close_result)
        self._btn_close_result.hide()
        self._layout.addWidget(self._btn_close_result)

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

    def center_on_screen(self):
        """将工具栏移动到屏幕顶部居中位置"""
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            self.move(
                screen_geo.center().x() - self.width() // 2,
                screen_geo.top() + 10
            )

    def start_countdown(self, seconds: int = 0):
        """开始录制计时"""
        self._elapsed_seconds = 0
        self._recording = True
        self._paused = False
        self._result_mode = False
        self._show_recording_buttons()
        self._timer.start(1000)
        QTimer.singleShot(0, self.center_on_screen)

    def stop_countdown(self):
        """停止录制计时"""
        self._timer.stop()

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

    def show_result(self, output_path: str, file_size: str):
        """编码完成后切换到结果条模式

        Args:
            output_path: 输出文件路径
            file_size: 文件大小字符串（如 "25.3MB"）
        """
        self._result_mode = True
        self._output_path = output_path
        self._recording = False
        self._timer.stop()

        # 绿色指示灯
        self._indicator.setText("✓")
        self._indicator.setStyleSheet("color: #2ecc71; font-size: 16px;")

        # 停止自动关闭定时器（如果正在计时）
        self._auto_close_timer.stop()

        # 切换到结果条按钮
        self._show_result_buttons()

        # 禁用录制按钮后重新启用结果条按钮
        self._btn_pause.setEnabled(True)
        self._btn_stop.setEnabled(True)
        self._btn_cancel.setEnabled(True)

        # 5秒后自动关闭
        self._auto_close_timer.start(5000)

    # --- 内部方法 ---

    def _show_recording_buttons(self):
        """显示录制模式的按钮"""
        self._btn_pause.show()
        self._btn_stop.show()
        self._btn_cancel.show()
        self._btn_pause.setEnabled(True)
        self._btn_stop.setEnabled(True)
        self._btn_cancel.setEnabled(True)

        self._btn_saved.hide()
        self._btn_open.hide()
        self._btn_close_result.hide()

    def _show_result_buttons(self):
        """显示结果条模式的按钮"""
        self._btn_pause.hide()
        self._btn_stop.hide()
        self._btn_cancel.hide()

        self._btn_saved.show()
        self._btn_open.show()
        self._btn_close_result.show()

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

    def _on_open_file(self):
        """结果条：打开视频文件"""
        self._auto_close_timer.stop()
        if self._output_path:
            self.open_file_requested.emit()

    def _on_open_folder(self):
        """结果条：打开文件夹并选中文件"""
        self._auto_close_timer.stop()
        if self._output_path:
            self.open_folder_requested.emit()

    def _on_close_result(self):
        """结果条：关闭"""
        self._auto_close_timer.stop()
        self.cancelled.emit()

    def _on_auto_close(self):
        """5秒后自动关闭"""
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