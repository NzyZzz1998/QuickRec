"""
设置对话框模块

提供用户修改配置的界面。

v1.1 新增：音频源选择下拉框、区域录制快捷键。
v1.2 新增：开机自启复选框、录制倒计时复选框+秒数、鼠标点击高亮复选框、
         窗口录制快捷键、画质动态显示分辨率。
"""

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QFileDialog,
    QCheckBox
)

from config import ConfigManager
from utils.autostart import is_autostart_enabled, enable_autostart, disable_autostart

# 音频源选项：显示文本 → 配置值
_AUDIO_OPTIONS = ConfigManager.AUDIO_OPTIONS


class _ShortcutRecorder(QLabel):
    """可点击录制快捷键的标签控件"""

    shortcut_changed = pyqtSignal(str)

    def __init__(self, initial_text: str, parent=None):
        super().__init__(initial_text, parent)
        self._recording = False
        self._keys = set()
        self._original = initial_text
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("点击此处，然后按下新快捷键组合")
        self.setStyleSheet("QLabel { padding: 4px 8px; border: 1px solid #ccc; border-radius: 3px; background: #fff; }")

    def mousePressEvent(self, event):
        if not self._recording:
            self._start_recording()

    def _start_recording(self):
        self._recording = True
        self._keys.clear()
        self.setText("按下快捷键...")
        self.setStyleSheet("QLabel { padding: 4px 8px; border: 2px solid #4a9eff; border-radius: 3px; background: #e8f4ff; }")
        self.setFocus()
        self.grabKeyboard()

    def keyPressEvent(self, event):
        if not self._recording:
            return super().keyPressEvent(event)

        key = event.key()
        modifiers = event.modifiers()

        # Escape 取消录制
        if key == Qt.Key_Escape:
            self._stop_recording(self._original)
            return

        # 单独的修饰键不算有效快捷键
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            # 更新显示当前修饰键
            parts = []
            if modifiers & Qt.ControlModifier:
                parts.append("Ctrl")
            if modifiers & Qt.ShiftModifier:
                parts.append("Shift")
            if modifiers & Qt.AltModifier:
                parts.append("Alt")
            self.setText("+".join(parts) + "+?")
            return

        # 有效快捷键：修饰键 + 普通键
        parts = []
        if modifiers & Qt.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.AltModifier:
            parts.append("Alt")

        if key == Qt.Key_Space:
            parts.append("Space")
        elif key == Qt.Key_Return:
            parts.append("Enter")
        elif key == Qt.Key_Tab:
            parts.append("Tab")
        elif key == Qt.Key_Backspace:
            # Backspace 清除快捷键 → 恢复默认
            self._stop_recording(self._original)
            return
        else:
            ch = chr(key)
            if ch.isalpha() or ch.isdigit():
                parts.append(ch.upper())
            else:
                # 其他键不处理
                return

        shortcut = "+".join(parts)
        self._stop_recording(shortcut)
        self.shortcut_changed.emit(shortcut)

    def focusOutEvent(self, event):
        if self._recording:
            self._stop_recording(self._original)
        super().focusOutEvent(event)

    def _stop_recording(self, text: str):
        self._recording = False
        self.releaseKeyboard()
        self.setText(text)
        self.setStyleSheet("QLabel { padding: 4px 8px; border: 1px solid #ccc; border-radius: 3px; background: #fff; }")

    def get_shortcut(self) -> str:
        """获取当前快捷键文本"""
        return self.text()


class SettingsDialog(QDialog):
    """设置对话框"""

    config_saved = pyqtSignal()

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config
        self._init_ui()
        self._load_config()

    def _init_ui(self):
        """初始化界面"""
        self.setWindowTitle("QuickRec Lite 设置")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        # 表单布局
        form = QFormLayout()

        # 保存路径
        path_layout = QHBoxLayout()
        self._edit_save_path = QLineEdit()
        self._edit_save_path.setReadOnly(True)
        path_layout.addWidget(self._edit_save_path)
        self._btn_browse = QPushButton("浏览...")
        self._btn_browse.setFixedWidth(70)
        self._btn_browse.clicked.connect(self._browse_save_path)
        path_layout.addWidget(self._btn_browse)
        form.addRow("保存路径:", path_layout)

        # 音频源选择
        self._combo_audio_source = QComboBox()
        for display_text, value in _AUDIO_OPTIONS:
            self._combo_audio_source.addItem(display_text, value)
        form.addRow("音频源:", self._combo_audio_source)

        # Lite v0: only keep autostart from the advanced option group.
        options_layout = QHBoxLayout()
        options_layout.setSpacing(12)
        self._cb_auto_start = QCheckBox("开机自启")

        options_layout.addWidget(self._cb_auto_start)
        options_layout.addStretch()
        form.addRow("选项:", options_layout)

        # 快捷键（可点击录制）
        self._shortcut_start = _ShortcutRecorder("Ctrl+Shift+R")
        self._shortcut_start.shortcut_changed.connect(
            lambda s: self._shortcut_start.setText(s)
        )
        form.addRow("开始快捷键:", self._shortcut_start)

        self._shortcut_stop = _ShortcutRecorder("Ctrl+Shift+S")
        self._shortcut_stop.shortcut_changed.connect(
            lambda s: self._shortcut_stop.setText(s)
        )
        form.addRow("停止快捷键:", self._shortcut_stop)

        self._shortcut_pause = _ShortcutRecorder("Ctrl+Shift+P")
        self._shortcut_pause.shortcut_changed.connect(
            lambda s: self._shortcut_pause.setText(s)
        )
        form.addRow("暂停快捷键:", self._shortcut_pause)

        layout.addLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_save = QPushButton("保存")
        self._btn_save.setFixedSize(80, 32)
        self._btn_save.clicked.connect(self._save_config)
        btn_layout.addWidget(self._btn_save)

        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setFixedSize(80, 32)
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        layout.addLayout(btn_layout)

    def _load_config(self):
        """从 ConfigManager 加载当前值到控件"""
        self._edit_save_path.setText(self._config.get("save_path"))

        self._shortcut_start.setText(
            str(self._config.get("shortcut_start", "Ctrl+Shift+R"))
        )
        self._shortcut_stop.setText(
            str(self._config.get("shortcut_stop", "Ctrl+Shift+S"))
        )
        self._shortcut_pause.setText(
            str(self._config.get("shortcut_pause", "Ctrl+Shift+P"))
        )
        # 音频源加载
        audio_source = self._config.get("audio_source", "none")
        for i, (display_text, value) in enumerate(_AUDIO_OPTIONS):
            if value == audio_source:
                self._combo_audio_source.setCurrentIndex(i)
                break

        # v1.2 新增配置加载
        # 开机自启：检查 config 配置 + 注册表实际状态
        auto_start_config = self._config.get("auto_start", False)
        auto_start_actual = is_autostart_enabled()
        self._cb_auto_start.setChecked(auto_start_config and auto_start_actual)

    def _save_config(self):
        """从控件读取值，写入 ConfigManager"""
        self._config.set("save_path", self._edit_save_path.text())
        self._config.set("quality", "native")
        self._config.set("fps", 60)
        self._config.set("shortcut_start", self._shortcut_start.text())
        self._config.set("shortcut_stop", self._shortcut_stop.text())
        self._config.set("shortcut_pause", self._shortcut_pause.text())
        self._config.set("audio_source", self._combo_audio_source.currentData())
        self._config.set("show_countdown", False)
        self._config.set("countdown_seconds", 3)
        self._config.set("mouse_highlight", False)

        # 开机自启：同时操作注册表
        auto_start = self._cb_auto_start.isChecked()
        self._config.set("auto_start", auto_start)
        if auto_start:
            enable_autostart()
        else:
            disable_autostart()

        self._config.save()
        self.config_saved.emit()
        self.accept()

    def _browse_save_path(self):
        """打开文件夹选择对话框"""
        path = QFileDialog.getExistingDirectory(
            self, "选择保存路径",
            self._edit_save_path.text()
        )
        if path:
            self._edit_save_path.setText(path)
