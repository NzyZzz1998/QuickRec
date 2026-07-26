"""
录制工具栏模块

录制中的悬浮控制窗口，显示录制状态和提供控制按钮。

v1.1 新增：编码完成后结果条模式，支持打开文件夹和自动关闭。
v1.2 新增：录制倒计时模式，在计时器位置显示 3→2→1。
"""

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ui.design_system import (
    FLOATING_STYLESHEET,
    refresh_style,
    set_button_icon,
)


class RecordingToolbar(QWidget):
    """录制工具栏

    三种模式共享同一布局：
    - 录制模式：指示灯 + 计时器 + 暂停/停止/取消
    - 倒计时模式：指示灯 + 倒计时数字 + 暂停/停止/取消
    - 结果条模式：状态标识 + 文件信息 + 已保存/打开/关闭

    倒计时和录制模式布局完全一致，仅计时器文本内容不同。
    ESC 取消由 pynput 全局监听处理，不依赖窗口键盘焦点。
    """

    paused = pyqtSignal()
    resumed = pyqtSignal()
    stopped = pyqtSignal()
    cancelled = pyqtSignal()

    open_folder_requested = pyqtSignal()
    open_file_requested = pyqtSignal()
    material_library_requested = pyqtSignal()
    retry_material_requested = pyqtSignal(str)

    countdown_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = True
        self._paused = False
        self._elapsed_seconds = 0

        self._result_mode = False
        self._output_path = ""
        self._index_failed = False
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._on_auto_close)

        self._countdown_mode = False
        self._countdown_value = 0
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._countdown_tick)

        self._init_ui()
        self._init_timer()
        self._resize_animation = QPropertyAnimation(self, b"geometry", self)
        self._resize_animation.setDuration(180)
        self._resize_animation.setEasingCurve(QEasingCurve.OutCubic)

    def _init_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setObjectName("recordingToolbar")
        self.setFixedHeight(48)
        self.setStyleSheet(FLOATING_STYLESHEET)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 指示灯
        self._indicator = QLabel("")
        self._indicator.setObjectName("recordingIndicator")
        self._indicator.setProperty("state", "recording")
        self._indicator.setFixedSize(10, 10)
        self._indicator.setAccessibleName("录制状态")
        layout.addWidget(self._indicator)

        # 计时器 / 倒计时数字（共用位置）
        self._label_timer = QLabel("00:00")
        self._label_timer.setFont(QFont("Consolas", 11))
        self._label_timer.setMinimumWidth(52)
        self._label_timer.setAccessibleName("录制计时")
        layout.addWidget(self._label_timer)
        layout.addStretch(1)

        # 录制模式按钮
        self._btn_pause = QPushButton("暂停")
        self._configure_action(self._btn_pause, "pause", "暂停当前录制")
        self._btn_pause.clicked.connect(self._on_pause)
        layout.addWidget(self._btn_pause)

        self._btn_stop = QPushButton("停止")
        self._configure_action(self._btn_stop, "stop", "停止并保存当前录制")
        self._btn_stop.clicked.connect(self._on_stop)
        layout.addWidget(self._btn_stop)

        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setProperty("role", "danger")
        self._configure_action(self._btn_cancel, "close", "取消录制并丢弃本次输出")
        self._btn_cancel.clicked.connect(self._on_cancel)
        layout.addWidget(self._btn_cancel)

        # 结果条按钮（初始隐藏）
        self._btn_saved = QPushButton("已保存")
        self._configure_action(self._btn_saved, "check", "打开本次录制视频")
        self._btn_saved.clicked.connect(self._on_open_file)
        self._btn_saved.hide()
        layout.addWidget(self._btn_saved)

        self._btn_open = QPushButton("打开目录")
        self._configure_action(self._btn_open, "folder", "在资源管理器中定位视频")
        self._btn_open.clicked.connect(self._on_open_folder)
        self._btn_open.hide()
        layout.addWidget(self._btn_open)

        self._btn_material = QPushButton("素材库")
        self._configure_action(self._btn_material, "library", "在工作台素材库中查看录制")
        self._btn_material.clicked.connect(self._on_material_library)
        self._btn_material.hide()
        layout.addWidget(self._btn_material)

        self._btn_close_result = QPushButton("关闭")
        self._configure_action(self._btn_close_result, "close", "关闭录制结果条")
        self._btn_close_result.clicked.connect(self._on_close_result)
        self._btn_close_result.hide()
        layout.addWidget(self._btn_close_result)

        self._drag_pos = None

    @staticmethod
    def _configure_action(button: QPushButton, icon_name: str, tooltip: str) -> None:
        button.setMinimumWidth(72)
        button.setToolTip(tooltip)
        button.setAccessibleName(button.text())
        set_button_icon(button, icon_name, color="#DCE3ED", size=16)

    def _set_indicator_state(self, state: str) -> None:
        self._indicator.setProperty("state", state)
        refresh_style(self._indicator)

    def _transition_to_content_width(self) -> None:
        layout = self.layout()
        if layout is not None:
            layout.activate()
        target_width = max(250, self.sizeHint().width())
        target_height = self.height()
        current = self.geometry()
        if not self.isVisible() or current.width() <= 0:
            self.resize(target_width, target_height)
            return
        center_x = current.center().x()
        target = QRect(
            center_x - target_width // 2,
            current.y(),
            target_width,
            target_height,
        )
        self._resize_animation.stop()
        self._resize_animation.setStartValue(current)
        self._resize_animation.setEndValue(target)
        self._resize_animation.start()

    def _init_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_timer)

    def center_on_screen(self):
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.adjustSize()
            self.move(geo.center().x() - self.width() // 2, geo.top() + 10)

    # --- 录制模式 ---

    def start_recording_timer(self):
        self._elapsed_seconds = 0
        self._recording = True
        self._paused = False
        self._result_mode = False
        self._show_recording_buttons()
        self._timer.start(1000)
        self._set_indicator_state("recording")
        self._transition_to_content_width()
        QTimer.singleShot(0, self.center_on_screen)

    def stop_recording_timer(self):
        self._timer.stop()

    def set_paused(self, paused: bool):
        self._paused = paused
        if paused:
            self._btn_pause.setText("继续")
            set_button_icon(self._btn_pause, "play", color="#DCE3ED", size=16)
            self._btn_pause.setAccessibleName("继续录制")
            self._set_indicator_state("paused")
        else:
            self._btn_pause.setText("暂停")
            set_button_icon(self._btn_pause, "pause", color="#DCE3ED", size=16)
            self._btn_pause.setAccessibleName("暂停录制")
            self._set_indicator_state("recording")
        self._transition_to_content_width()

    # --- 倒计时模式 ---

    def start_countdown(self, seconds: int = 3):
        self._countdown_mode = True
        self._countdown_value = seconds
        self._recording = False
        self._result_mode = False
        self._show_countdown_ui()
        self._countdown_timer.start()
        self._transition_to_content_width()
        QTimer.singleShot(0, self.center_on_screen)

    def cancel_countdown(self):
        self._countdown_timer.stop()
        self._countdown_mode = False
        self._countdown_value = 0
        self.close()

    def is_countdown_mode(self) -> bool:
        return self._countdown_mode

    def _countdown_tick(self):
        self._countdown_value -= 1
        if self._countdown_value <= 0:
            self._countdown_timer.stop()
            self._countdown_mode = False
            self._show_recording_ui()
            self.countdown_finished.emit()
        else:
            self._label_timer.setText(str(self._countdown_value))

    def _show_countdown_ui(self):
        """倒计时：同一位置显示数字，布局不变"""
        self._label_timer.setText(str(self._countdown_value))
        self._label_timer.setFont(QFont("Arial", 16, QFont.Bold))
        self._set_indicator_state("paused")
        self._show_recording_buttons()

    def _show_recording_ui(self):
        """从倒计时恢复为录制显示"""
        self._label_timer.setText("00:00")
        self._label_timer.setFont(QFont("Consolas", 11))
        self._set_indicator_state("recording")
        self._transition_to_content_width()

    # --- 结果条模式 ---

    def show_saving(self):
        self._recording = False
        self._timer.stop()
        self._label_timer.setText("保存中...")
        self._label_timer.setFont(QFont("Consolas", 11))
        self._set_indicator_state("saving")
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_cancel.setEnabled(False)
        self._transition_to_content_width()

    def show_result(self, output_path: str, file_size: str, *, index_ok: bool = True):
        self._result_mode = True
        self._output_path = output_path
        self._index_failed = not index_ok
        self._recording = False
        self._timer.stop()

        self._label_timer.setText(f"{file_size}")
        self._label_timer.setFont(QFont("Consolas", 11))

        self._set_indicator_state("saved")
        self._auto_close_timer.stop()
        self._btn_material.setText("素材库" if index_ok else "重试入库")
        set_button_icon(
            self._btn_material,
            "library" if index_ok else "refresh",
            color="#DCE3ED",
            size=16,
        )
        self._show_result_buttons()
        self._btn_pause.setEnabled(True)
        self._btn_stop.setEnabled(True)
        self._btn_cancel.setEnabled(True)
        self._transition_to_content_width()
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
        self._btn_material.hide()
        self._btn_close_result.hide()

    def _show_result_buttons(self):
        self._btn_pause.hide()
        self._btn_stop.hide()
        self._btn_cancel.hide()
        self._btn_saved.show()
        self._btn_open.show()
        self._btn_material.show()
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

    def _on_material_library(self):
        if self._index_failed and self._output_path:
            self.retry_material_requested.emit(self._output_path)
        else:
            self.material_library_requested.emit()
        self._restart_auto_close()

    def mark_material_index_saved(self) -> None:
        self._index_failed = False
        self._btn_material.setText("素材库")
        set_button_icon(self._btn_material, "library", color="#DCE3ED", size=16)

    def _restart_auto_close(self):
        if self._result_mode:
            self._auto_close_timer.start(5000)

    def _on_close_result(self):
        self._auto_close_timer.stop()
        self.close()

    def _on_auto_close(self):
        self.close()

    # --- 键盘事件（辅助，主要靠 pynput 全局 ESC） ---

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._countdown_mode:
            self.cancel_countdown()
            return
        super().keyPressEvent(event)

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
