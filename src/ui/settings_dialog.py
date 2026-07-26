"""
设置对话框模块

提供用户修改配置的界面。

v1.1 新增：音频源选择下拉框、区域录制快捷键。
v1.2 新增：开机自启复选框、录制倒计时复选框+秒数、鼠标点击高亮复选框、
         窗口录制快捷键、画质动态显示分辨率。
"""

import logging
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config import ConfigManager
from services.capture_capability import display_supports_120
from services.capture_capability_runtime import CaptureCapabilityRuntime
from ui.capture_self_test_dialog import CaptureSelfTestDialog
from ui.design_system import set_button_icon
from utils.autostart import disable_autostart, enable_autostart, is_autostart_enabled

# 音频源选项：显示文本 → 配置值
_AUDIO_OPTIONS = ConfigManager.AUDIO_OPTIONS
logger = logging.getLogger(__name__)


class _ShortcutRecorder(QLabel):
    """可点击录制快捷键的标签控件"""

    shortcut_changed = pyqtSignal(str)

    def __init__(self, initial_text: str, parent=None):
        super().__init__(initial_text, parent)
        self._recording = False
        self._keys: set[int] = set()
        self._original = initial_text
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("点击此处，然后按下新快捷键组合")
        self.setStyleSheet(
            "QLabel { padding: 6px 9px; border: 1px solid #C2CAD7; "
            "border-radius: 4px; color: #172033; background: #FFFFFF; }"
        )

    def mousePressEvent(self, event):
        if not self._recording:
            self._start_recording()

    def _start_recording(self):
        self._recording = True
        self._keys.clear()
        self.setText("按下快捷键...")
        self.setStyleSheet(
            "QLabel { padding: 5px 8px; border: 2px solid #2563EB; "
            "border-radius: 4px; color: #172033; background: #E8F0FF; }"
        )
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
        self.setStyleSheet(
            "QLabel { padding: 6px 9px; border: 1px solid #C2CAD7; "
            "border-radius: 4px; color: #172033; background: #FFFFFF; }"
        )

    def get_shortcut(self) -> str:
        """获取当前快捷键文本"""
        return self.text()


class SettingsDialog(QDialog):
    """设置对话框"""

    config_saved = pyqtSignal()
    dirty_changed = pyqtSignal(bool)
    copy_diagnostic_requested = pyqtSignal(str)
    open_diagnostic_dir_requested = pyqtSignal(str)
    export_diagnostic_requested = pyqtSignal(str)
    open_capture_diagnostics_requested = pyqtSignal()

    def __init__(
        self,
        config: ConfigManager,
        parent=None,
        *,
        embedded: bool = False,
        capture_capability: CaptureCapabilityRuntime | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._embedded = embedded
        self._capture_capability = capture_capability
        self._last_non_120_fps = "30"
        self._loading = False
        self._dirty = False
        if embedded:
            self.setWindowFlags(Qt.Widget)
        self._init_ui()
        self._connect_dirty_signals()
        self._load_config()
        if embedded:
            self._diagnostic_group.hide()

    def _init_ui(self):
        """初始化界面"""
        self.setWindowTitle("QuickRec 设置")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        if self._embedded:
            layout.setContentsMargins(32, 28, 32, 16)
            layout.setSpacing(14)
            title = QLabel("设置")
            title.setObjectName("pageTitle")
            layout.addWidget(title)
            subtitle = QLabel("显式保存录制参数、行为和快捷键。")
            subtitle.setObjectName("pageSubtitle")
            layout.addWidget(subtitle)

        # 表单布局
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        if self._embedded:
            section = QLabel("录制参数")
            section.setProperty("role", "sectionTitle")
            form.addRow(section)

        # 保存路径
        path_layout = QHBoxLayout()
        self._edit_save_path = QLineEdit()
        self._edit_save_path.setReadOnly(True)
        self._edit_save_path.setAccessibleName("录制保存路径")
        path_layout.addWidget(self._edit_save_path)
        self._btn_browse = QPushButton("浏览...")
        self._btn_browse.setFixedWidth(70)
        self._btn_browse.clicked.connect(self._browse_save_path)
        self._btn_browse.setToolTip("选择新录制文件的默认保存目录")
        self._btn_browse.setAccessibleName("浏览录制保存目录")
        set_button_icon(self._btn_browse, "folder")
        path_layout.addWidget(self._btn_browse)
        form.addRow("保存路径:", path_layout)

        # 画质选择（动态显示分辨率）
        self._combo_quality = QComboBox()
        self._combo_quality.setAccessibleName("录制画质")
        self._refresh_quality_combo()
        form.addRow("画质:", self._combo_quality)

        # 帧率选择
        self._combo_fps = QComboBox()
        self._combo_fps.setAccessibleName("录制帧率")
        self._combo_fps.addItems(["30", "60", "120"])
        self._combo_fps.setCurrentText("30")
        form.addRow("帧率:", self._combo_fps)
        self._label_fps_capability = QLabel("")
        self._label_fps_capability.setWordWrap(True)
        form.addRow("", self._label_fps_capability)
        self._configure_120_option()
        self._combo_fps.currentTextChanged.connect(self._on_fps_changed)

        # 音频源选择
        self._combo_audio_source = QComboBox()
        self._combo_audio_source.setAccessibleName("录制音频来源")
        for display_text, value in _AUDIO_OPTIONS:
            self._combo_audio_source.addItem(display_text, value)
        form.addRow("音频源:", self._combo_audio_source)

        # v1.2 新增：开机自启、录制倒计时、鼠标点击高亮
        if self._embedded:
            section = QLabel("录制行为")
            section.setProperty("role", "sectionTitle")
            form.addRow(section)
        options_layout = QHBoxLayout()
        options_layout.setSpacing(12)
        self._cb_auto_start = QCheckBox("开机自启")
        self._cb_countdown = QCheckBox("录制倒计时")
        self._combo_countdown_seconds = QComboBox()
        self._combo_countdown_seconds.addItems([f"{i} 秒" for i in range(1, 11)])
        self._combo_countdown_seconds.setCurrentIndex(2)  # 默认 3 秒
        self._combo_countdown_seconds.setEnabled(False)
        self._cb_countdown.toggled.connect(
            lambda checked: self._combo_countdown_seconds.setEnabled(checked)
        )
        self._cb_mouse_highlight = QCheckBox("鼠标点击高亮")

        options_layout.addWidget(self._cb_auto_start)
        options_layout.addWidget(self._cb_countdown)
        options_layout.addWidget(self._combo_countdown_seconds)
        options_layout.addStretch()
        options_layout.addWidget(self._cb_mouse_highlight)
        form.addRow("选项:", options_layout)

        # 快捷键（可点击录制）
        if self._embedded:
            section = QLabel("快捷键")
            section.setProperty("role", "sectionTitle")
            form.addRow(section)
        self._shortcut_start = _ShortcutRecorder("Ctrl+Shift+R")
        self._shortcut_start.setAccessibleName("开始录制快捷键")
        self._shortcut_start.shortcut_changed.connect(
            lambda s: self._shortcut_start.setText(s)
        )
        form.addRow("开始快捷键:", self._shortcut_start)

        self._shortcut_stop = _ShortcutRecorder("Ctrl+Shift+S")
        self._shortcut_stop.setAccessibleName("停止录制快捷键")
        self._shortcut_stop.shortcut_changed.connect(
            lambda s: self._shortcut_stop.setText(s)
        )
        form.addRow("停止快捷键:", self._shortcut_stop)

        self._shortcut_pause = _ShortcutRecorder("Ctrl+Shift+P")
        self._shortcut_pause.setAccessibleName("暂停或继续录制快捷键")
        self._shortcut_pause.shortcut_changed.connect(
            lambda s: self._shortcut_pause.setText(s)
        )
        form.addRow("暂停快捷键:", self._shortcut_pause)

        # 区域录制快捷键
        self._shortcut_area = _ShortcutRecorder("Ctrl+Shift+A")
        self._shortcut_area.setAccessibleName("区域录制快捷键")
        self._shortcut_area.shortcut_changed.connect(
            lambda s: self._shortcut_area.setText(s)
        )
        form.addRow("区域录制:", self._shortcut_area)

        self._shortcut_window = _ShortcutRecorder("Ctrl+Shift+W")
        self._shortcut_window.setAccessibleName("窗口录制快捷键")
        self._shortcut_window.shortcut_changed.connect(
            lambda s: self._shortcut_window.setText(s)
        )
        form.addRow("窗口录制:", self._shortcut_window)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addLayout(form)

        self._diagnostic_group = QGroupBox("诊断")
        diagnostic_layout = QVBoxLayout(self._diagnostic_group)
        diagnostic_path_layout = QHBoxLayout()
        self._edit_diagnostic_dir = QLineEdit()
        diagnostic_path_layout.addWidget(self._edit_diagnostic_dir)
        self._btn_browse_diagnostic = QPushButton("浏览...")
        self._btn_browse_diagnostic.setFixedWidth(70)
        self._btn_browse_diagnostic.clicked.connect(self._browse_diagnostic_dir)
        diagnostic_path_layout.addWidget(self._btn_browse_diagnostic)
        diagnostic_layout.addLayout(diagnostic_path_layout)

        diagnostic_btn_layout = QHBoxLayout()
        self._btn_copy_diagnostic = QPushButton("复制诊断信息")
        self._btn_copy_diagnostic.clicked.connect(self._emit_copy_diagnostic)
        diagnostic_btn_layout.addWidget(self._btn_copy_diagnostic)
        self._btn_open_diagnostic_dir = QPushButton("打开日志目录")
        self._btn_open_diagnostic_dir.clicked.connect(self._emit_open_diagnostic_dir)
        diagnostic_btn_layout.addWidget(self._btn_open_diagnostic_dir)
        self._btn_export_diagnostic = QPushButton("导出诊断文件")
        self._btn_export_diagnostic.clicked.connect(self._emit_export_diagnostic)
        diagnostic_btn_layout.addWidget(self._btn_export_diagnostic)
        diagnostic_layout.addLayout(diagnostic_btn_layout)

        self._label_diagnostic_status = QLabel("")
        diagnostic_layout.addWidget(self._label_diagnostic_status)
        content_layout.addWidget(self._diagnostic_group)
        content_layout.addStretch()

        if self._embedded:
            self._scroll_area = QScrollArea()
            self._scroll_area.setObjectName("settingsScrollArea")
            self._scroll_area.setWidgetResizable(True)
            self._scroll_area.setFrameShape(QScrollArea.NoFrame)
            self._scroll_area.setWidget(content)
            layout.addWidget(self._scroll_area, 1)
        else:
            self._scroll_area = None
            layout.addWidget(content)

        # 按钮
        btn_layout = QHBoxLayout()
        self._label_save_status = QLabel("")
        self._label_save_status.setWordWrap(True)
        btn_layout.addWidget(self._label_save_status, 1)
        btn_layout.addStretch()

        self._btn_save = QPushButton("保存更改" if self._embedded else "保存")
        self._btn_save.setMinimumWidth(92 if self._embedded else 80)
        self._btn_save.setProperty("role", "primary")
        self._btn_save.setToolTip("将当前草稿保存为正式配置")
        set_button_icon(self._btn_save, "save", color="#FFFFFF")
        self._btn_save.clicked.connect(self._save_config)

        self._btn_cancel = QPushButton("放弃更改" if self._embedded else "取消")
        self._btn_cancel.setMinimumWidth(92 if self._embedded else 80)
        self._btn_cancel.setToolTip(
            "恢复到上次已保存的设置" if self._embedded else "关闭且不保存"
        )
        if self._embedded:
            self._btn_cancel.clicked.connect(self.discard_changes)
        else:
            self._btn_cancel.clicked.connect(self.reject)
        if self._embedded:
            btn_layout.addWidget(self._btn_cancel)
            btn_layout.addWidget(self._btn_save)
        else:
            btn_layout.addWidget(self._btn_save)
            btn_layout.addWidget(self._btn_cancel)

        layout.addLayout(btn_layout)
        self._sync_dirty_buttons()

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def _connect_dirty_signals(self) -> None:
        self._edit_save_path.textChanged.connect(self._mark_dirty)
        for combo in (
            self._combo_quality,
            self._combo_fps,
            self._combo_audio_source,
            self._combo_countdown_seconds,
        ):
            combo.currentIndexChanged.connect(self._mark_dirty)
        for checkbox in (
            self._cb_auto_start,
            self._cb_countdown,
            self._cb_mouse_highlight,
        ):
            checkbox.toggled.connect(self._mark_dirty)
        for shortcut in (
            self._shortcut_start,
            self._shortcut_stop,
            self._shortcut_pause,
            self._shortcut_area,
            self._shortcut_window,
        ):
            shortcut.shortcut_changed.connect(self._mark_dirty)

    def _configure_120_option(self) -> None:
        index = self._combo_fps.findText("120")
        item = self._combo_fps.model().item(index)
        if self._capture_capability is None:
            item.setEnabled(False)
            self._label_fps_capability.setText("120 FPS 能力检测服务不可用")
            return
        inspection = self._capture_capability.inspect()
        supported, reason = display_supports_120(inspection.display)
        item.setEnabled(supported)
        if not supported:
            self._label_fps_capability.setText(reason)
        elif inspection.readiness.ready:
            self._label_fps_capability.setText("当前环境已通过 120 FPS 能力检测")
        else:
            self._label_fps_capability.setText("首次选择 120 FPS 时需要完成约 5 秒检测")

    def _on_fps_changed(self, value: str) -> None:
        if self._loading:
            return
        if value != "120":
            self._last_non_120_fps = value
            return
        if self._capture_capability is None:
            self._combo_fps.setCurrentText(self._last_non_120_fps)
            return
        inspection = self._capture_capability.inspect()
        supported, reason = display_supports_120(inspection.display)
        if not supported:
            self._label_fps_capability.setText(reason)
            self._combo_fps.setCurrentText(self._last_non_120_fps)
            return
        if inspection.readiness.ready:
            self._label_fps_capability.setText("当前环境已通过 120 FPS 能力检测")
            return
        result = CaptureSelfTestDialog.execute(
            self._capture_capability,
            self,
            open_diagnostics=self.open_capture_diagnostics_requested.emit,
        )
        if result is None:
            self._combo_fps.setCurrentText(self._last_non_120_fps)
            self._label_fps_capability.setText("未启用 120 FPS，原帧率保持不变")
            return
        self._label_fps_capability.setText(
            f"检测通过：平均 {result.average_fps:.1f} FPS；保存后生效"
        )

    def _refresh_quality_combo(self):
        """动态更新画质下拉框，原生画质显示实际分辨率"""
        native_w, native_h = ConfigManager.get_native_resolution()
        quality_items = [
            (f"原生 ({native_w}×{native_h})", "native"),
            ("高 (1080p)", "high"),
            ("中 (720p)", "medium"),
            ("低 (480p)", "low"),
        ]
        self._combo_quality.clear()
        for label, value in quality_items:
            self._combo_quality.addItem(label, value)

    def _load_config(self):
        """从 ConfigManager 加载当前值到控件"""
        self._loading = True
        self._edit_save_path.setText(self._config.get("save_path"))

        # 画质：根据配置值选择对应选项
        quality = self._config.get("quality", "native")
        for i in range(self._combo_quality.count()):
            if self._combo_quality.itemData(i) == quality:
                self._combo_quality.setCurrentIndex(i)
                break

        self._combo_fps.setCurrentText(
            str(self._config.get("fps", 30))
        )
        self._shortcut_start.setText(
            str(self._config.get("shortcut_start", "Ctrl+Shift+R"))
        )
        self._shortcut_stop.setText(
            str(self._config.get("shortcut_stop", "Ctrl+Shift+S"))
        )
        self._shortcut_pause.setText(
            str(self._config.get("shortcut_pause", "Ctrl+Shift+P"))
        )
        self._shortcut_area.setText(
            str(self._config.get("shortcut_area", "Ctrl+Shift+A"))
        )
        self._shortcut_window.setText(
            str(self._config.get("shortcut_window", "Ctrl+Shift+W"))
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

        # 录制倒计时
        show_countdown = self._config.get("show_countdown", False)
        self._cb_countdown.setChecked(show_countdown)
        self._combo_countdown_seconds.setCurrentIndex(
            self._config.get("countdown_seconds", 3) - 1
        )
        self._combo_countdown_seconds.setEnabled(show_countdown)

        # 鼠标点击高亮
        self._cb_mouse_highlight.setChecked(
            self._config.get("mouse_highlight", False)
        )
        if hasattr(self._config, "get_diagnostic_dir"):
            self._edit_diagnostic_dir.setText(self._config.get_diagnostic_dir())
        else:
            self._edit_diagnostic_dir.setText(str(self._config.get("diagnostic_dir", "")))
        self._loading = False
        self._set_dirty(False)
        self._label_save_status.setText("")

    def _save_config(self) -> bool:
        """原子保存候选配置，失败时保留当前窗口与正式配置。"""
        candidate = self._build_candidate()
        auto_start_before = is_autostart_enabled()
        auto_start_after = bool(candidate["auto_start"])
        autostart_changed = auto_start_before != auto_start_after

        if autostart_changed:
            autostart_ok = (
                enable_autostart() if auto_start_after else disable_autostart()
            )
            if not autostart_ok:
                self._show_save_error("无法更新开机自启设置，请检查系统权限后重试。")
                return False

        result = self._config.save_candidate(candidate)
        if not result.ok:
            rollback_ok = True
            if autostart_changed:
                rollback_ok = (
                    enable_autostart() if auto_start_before else disable_autostart()
                )
            rollback_note = "" if rollback_ok else "\n开机自启状态自动恢复失败，请手动检查。"
            logger.error(
                "配置保存失败: stage=%s error=%s rollback_ok=%s",
                result.stage,
                result.message,
                rollback_ok,
            )
            self._show_save_error(
                f"配置未保存，原设置保持不变。\n失败阶段：{result.stage}{rollback_note}"
            )
            return False

        self._set_dirty(False)
        self._label_save_status.setText("设置已保存")
        self.config_saved.emit()
        if not self._embedded:
            self.accept()
        return True

    def save_changes(self) -> bool:
        if not self._dirty:
            return True
        return self._save_config()

    def discard_changes(self) -> None:
        self._load_config()

    def confirm_navigation(self) -> bool:
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("设置尚未保存")
        box.setText("保存设置更改后再继续吗？")
        box.setStandardButtons(
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        )
        for standard_button, label in (
            (QMessageBox.Save, "保存"),
            (QMessageBox.Discard, "放弃"),
            (QMessageBox.Cancel, "取消"),
        ):
            button = box.button(standard_button)
            if button is not None:
                button.setText(label)
        box.setDefaultButton(QMessageBox.Save)
        choice = box.exec_()
        if choice == QMessageBox.Save:
            return self.save_changes()
        if choice == QMessageBox.Discard:
            self.discard_changes()
            return True
        return False

    def _mark_dirty(self, *_args) -> None:
        if self._loading:
            return
        self._set_dirty(self._build_candidate() != self._config.snapshot())

    def _set_dirty(self, dirty: bool) -> None:
        changed = dirty != self._dirty
        self._dirty = dirty
        self._sync_dirty_buttons()
        if changed:
            self.dirty_changed.emit(dirty)

    def _sync_dirty_buttons(self) -> None:
        if not hasattr(self, "_btn_save"):
            return
        if self._embedded:
            self._btn_save.setEnabled(self._dirty)
            self._btn_cancel.setEnabled(self._dirty)

    def _build_candidate(self) -> dict[str, object]:
        """从当前控件构建不影响正式配置的候选值。"""
        candidate = self._config.snapshot()
        previous_diagnostic_dir = self._config.get_diagnostic_dir()
        save_path = self._edit_save_path.text()

        candidate.update({
            "save_path": save_path,
            "quality": self._combo_quality.currentData(),
            "fps": int(self._combo_fps.currentText()),
            "shortcut_start": self._shortcut_start.text(),
            "shortcut_stop": self._shortcut_stop.text(),
            "shortcut_pause": self._shortcut_pause.text(),
            "shortcut_area": self._shortcut_area.text(),
            "shortcut_window": self._shortcut_window.text(),
            "audio_source": self._combo_audio_source.currentData(),
            "show_countdown": self._cb_countdown.isChecked(),
            "countdown_seconds": self._combo_countdown_seconds.currentIndex() + 1,
            "mouse_highlight": self._cb_mouse_highlight.isChecked(),
            "auto_start": self._cb_auto_start.isChecked(),
        })

        if not self._embedded:
            diagnostic_dir = self._edit_diagnostic_dir.text().strip()
            default_diagnostic_dir = str(Path(save_path) / "QuickRecDiagnostics")
            diagnostic_was_customized = bool(
                self._config.get("diagnostic_dir_customized", False)
            )
            if (
                not diagnostic_was_customized
                and diagnostic_dir
                in {previous_diagnostic_dir, default_diagnostic_dir}
            ):
                candidate["diagnostic_dir"] = ""
                candidate["diagnostic_dir_customized"] = False
            elif diagnostic_dir:
                candidate["diagnostic_dir"] = diagnostic_dir
                candidate["diagnostic_dir_customized"] = True

        return candidate

    def _show_save_error(self, message: str) -> None:
        """显示保存失败反馈并保持当前输入可继续重试。"""
        self._label_save_status.setText(f"保存失败：{message}")
        if not self._embedded:
            QMessageBox.critical(self, "保存失败", message)

    def _browse_save_path(self):
        """打开文件夹选择对话框"""
        path = QFileDialog.getExistingDirectory(
            self, "选择保存路径",
            self._edit_save_path.text()
        )
        if path:
            self._edit_save_path.setText(path)

    def _browse_diagnostic_dir(self):
        """打开诊断目录选择对话框"""
        path = QFileDialog.getExistingDirectory(
            self, "选择诊断目录",
            self._edit_diagnostic_dir.text()
        )
        if path:
            self._edit_diagnostic_dir.setText(path)

    def _current_diagnostic_dir(self) -> str:
        return self._edit_diagnostic_dir.text().strip()

    def _emit_copy_diagnostic(self):
        self.copy_diagnostic_requested.emit(self._current_diagnostic_dir())

    def _emit_open_diagnostic_dir(self):
        self.open_diagnostic_dir_requested.emit(self._current_diagnostic_dir())

    def _emit_export_diagnostic(self):
        self.export_diagnostic_requested.emit(self._current_diagnostic_dir())

    def set_diagnostic_status(self, text: str):
        self._label_diagnostic_status.setText(text)

    def set_recording_active(self, active: bool) -> None:
        """录制中禁止修改会影响当前捕获与编码的设置。"""
        for control in (
            self._edit_save_path,
            self._btn_browse,
            self._combo_quality,
            self._combo_fps,
            self._combo_audio_source,
            self._cb_countdown,
            self._combo_countdown_seconds,
            self._cb_mouse_highlight,
            self._shortcut_start,
            self._shortcut_stop,
            self._shortcut_pause,
            self._shortcut_area,
            self._shortcut_window,
        ):
            control.setEnabled(not active)
        self._combo_countdown_seconds.setEnabled(
            not active and self._cb_countdown.isChecked()
        )
