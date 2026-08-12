"""
录制工具栏模块

录制中的悬浮控制窗口，显示录制状态和提供控制按钮。

v1.1 新增：编码完成后结果条模式，支持打开文件夹和自动关闭。
"""

import os
import subprocess

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton
)


class RecordingToolbar(QWidget):
    """录制工具栏

    两种模式共享同一布局：
    - 录制模式：指示灯 + 计时器 + 暂停/停止/取消
    - 结果条模式：✓ + 文件信息 + 已保存/打开/关闭
    """

    paused = pyqtSignal()
    resumed = pyqtSignal()
    stopped = pyqtSignal()
    cancelled = pyqtSignal()

    open_folder_requested = pyqtSignal()
    open_file_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = True
        self._paused = False
        self._elapsed_seconds = 0

        self._result_mode = False
        self._output_path = ""
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._on_auto_close)

        self._init_ui()
        self._init_timer()

    def _init_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedHeight(40)
        self._setup_styles()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        # 指示灯
        self._indicator = QLabel("●")
        self._indicator.setFixedWidth(16)
        self._indicator.setStyleSheet("color: #e74c3c; font-size: 16px;")
        layout.addWidget(self._indicator)

        # 录制计时器
        self._label_timer = QLabel("00:00")
        self._label_timer.setFont(QFont("Consolas", 11))
        self._label_timer.setStyleSheet("color: #ecf0f1;")
        layout.addWidget(self._label_timer)

        # 录制模式按钮
        self._btn_pause = QPushButton("⏸ 暂停")
        self._btn_pause.setFixedSize(70, 28)
        self._btn_pause.clicked.connect(self._on_pause)
        layout.addWidget(self._btn_pause)

        self._btn_stop = QPushButton("⏹ 停止")
        self._btn_stop.setFixedSize(70, 28)
        self._btn_stop.clicked.connect(self._on_stop)
        layout.addWidget(self._btn_stop)

        self._btn_cancel = QPushButton("✕ 取消")
        self._btn_cancel.setFixedSize(70, 28)
        self._btn_cancel.clicked.connect(self._on_cancel)
        layout.addWidget(self._btn_cancel)

        # 结果条按钮（初始隐藏）
        self._btn_saved = QPushButton("✓ 已保存")
        self._btn_saved.setFixedSize(70, 28)
        self._btn_saved.clicked.connect(self._on_open_file)
        self._btn_saved.hide()
        layout.addWidget(self._btn_saved)

        self._btn_open = QPushButton("📂 打开")
        self._btn_open.setFixedSize(70, 28)
        self._btn_open.clicked.connect(self._on_open_folder)
        self._btn_open.hide()
        layout.addWidget(self._btn_open)

        self._btn_close_result = QPushButton("✕ 关闭")
        self._btn_close_result.setFixedSize(70, 28)
        self._btn_close_result.clicked.connect(self._on_close_result)
        self._btn_close_result.hide()
        layout.addWidget(self._btn_close_result)

        self._drag_pos = None

    def _setup_styles(self):
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
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_timer)

    def center_on_screen(self):
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move(geo.center().x() - self.width() // 2, geo.top() + 10)

    # --- 录制模式 ---

    def start_recording_timer(self):
        self._elapsed_seconds = 0
        self._recording = True
        self._paused = False
        self._result_mode = False
        self._show_recording_buttons()
        self._timer.start(1000)
        QTimer.singleShot(0, self.center_on_screen)

    def stop_recording_timer(self):
        self._timer.stop()

    def set_paused(self, paused: bool):
        self._paused = paused
        if paused:
            self._btn_pause.setText("▶ 继续")
            self._indicator.setStyleSheet("color: #f39c12; font-size: 16px;")
        else:
            self._btn_pause.setText("⏸ 暂停")
            self._indicator.setStyleSheet("color: #e74c3c; font-size: 16px;")

    # --- 结果条模式 ---

    def show_saving(self):
        self._recording = False
        self._timer.stop()
        self._label_timer.setText("保存中...")
        self._label_timer.setFont(QFont("Consolas", 11))
        self._label_timer.setStyleSheet("color: #ecf0f1;")
        self._indicator.setStyleSheet("color: #3498db; font-size: 16px;")
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_cancel.setEnabled(False)

    def show_result(self, output_path: str, file_size: str):
        self._result_mode = True
        self._output_path = output_path
        self._recording = False
        self._timer.stop()

        self._label_timer.setText(f"{file_size}")
        self._label_timer.setFont(QFont("Consolas", 11))
        self._label_timer.setStyleSheet("color: #ecf0f1;")

        self._indicator.setText("✓")
        self._indicator.setStyleSheet("color: #2ecc71; font-size: 16px;")
        self._auto_close_timer.stop()
        self._show_result_buttons()
        self._btn_pause.setEnabled(True)
        self._btn_stop.setEnabled(True)
        self._btn_cancel.setEnabled(True)
        self._auto_close_timer.start(5000)

    # --- 内部 ---

    def _show_recording_buttons(self):
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
        self._btn_pause.hide()
        self._btn_stop.hide()
        self._btn_cancel.hide()
        self._btn_saved.show()
        self._btn_open.show()
        self._btn_close_result.show()

    def _update_timer(self):
        if not self._paused:
            self._elapsed_seconds += 1
        minutes = self._elapsed_seconds // 60
        seconds = self._elapsed_seconds % 60
        self._label_timer.setText(f"{minutes:02d}:{seconds:02d}")

    def _on_pause(self):
        if self._paused:
            self.resumed.emit()
        else:
            self.paused.emit()

    def _on_stop(self):
        self.stopped.emit()

    def _on_cancel(self):
        self.cancelled.emit()

    def _on_open_file(self):
        if self._output_path:
            self.open_file_requested.emit()
        self._restart_auto_close()

    def _on_open_folder(self):
        if self._output_path:
            self.open_folder_requested.emit()
        self._restart_auto_close()

    def _restart_auto_close(self):
        if self._result_mode:
            self._auto_close_timer.start(5000)

    def _on_close_result(self):
        self._auto_close_timer.stop()
        self.close()

    def _on_auto_close(self):
        self.close()

    # --- 拖拽 ---

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self._restart_auto_close()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
