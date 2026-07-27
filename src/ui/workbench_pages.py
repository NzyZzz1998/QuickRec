"""QuickRec Full 工作台录制页与诊断页。"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import ConfigManager
from ui.design_system import (
    COLORS,
    quickrec_icon,
    refresh_style,
    set_button_icon,
)

QUALITY_LABELS = {
    "native": "原生画质",
    "high": "高 · 1080p",
    "medium": "中 · 720p",
    "low": "低 · 480p",
}
AUDIO_LABELS = {
    "none": "无声",
    "system": "系统声音",
    "microphone": "麦克风",
    "both": "系统声音 + 麦克风",
}
MODE_LABELS = {
    "fullscreen": "全屏",
    "region": "区域",
    "area": "区域",
    "window": "窗口",
}


class RecordingModeCard(QFrame):
    """录制模式说明卡和明确命令按钮。"""

    def __init__(
        self,
        title: str,
        description: str,
        metadata: str,
        action_text: str,
        icon_name: str,
        callback,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "modeCard")
        self.setMinimumHeight(156)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        heading = QHBoxLayout()
        icon = QLabel()
        icon.setProperty("role", "iconBadge")
        icon.setPixmap(quickrec_icon(icon_name, COLORS["blue"], 22).pixmap(22, 22))
        icon.setFixedSize(38, 38)
        icon.setAlignment(Qt.AlignCenter)
        heading.addWidget(icon)
        title_label = QLabel(title)
        title_label.setProperty("role", "sectionTitle")
        heading.addWidget(title_label, 1)
        layout.addLayout(heading)

        description_label = QLabel(description)
        description_label.setProperty("role", "secondary")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        layout.addStretch()

        metadata_label = QLabel(metadata)
        metadata_label.setProperty("role", "secondary")
        layout.addWidget(metadata_label)

        self.action_button = QPushButton(action_text)
        self.action_button.setToolTip(f"{description}。点击后进入对应的录制流程。")
        self.action_button.setAccessibleName(action_text)
        self.action_button.setAccessibleDescription(description)
        set_button_icon(
            self.action_button,
            icon_name,
            color=COLORS["secondary"],
        )
        self.action_button.clicked.connect(callback)
        layout.addWidget(self.action_button)


class RecordingPage(QWidget):
    """工作台录制入口、只读状态和工作台来源结果区。"""

    start_fullscreen_requested = pyqtSignal()
    start_region_requested = pyqtSignal()
    start_window_requested = pyqtSignal()
    open_settings_requested = pyqtSignal()
    open_material_requested = pyqtSignal()
    open_file_requested = pyqtSignal(str)
    open_folder_requested = pyqtSignal(str)
    retry_material_requested = pyqtSignal(str)

    def __init__(self, config: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._output_path = ""
        self._init_ui()
        self.refresh_summary()
        self.set_recording_state("idle")

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        title = QLabel("录制")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        subtitle = QLabel("选择录制范围，当前设置将在开始前统一校验。")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(subtitle)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(12)
        self._card_fullscreen = RecordingModeCard(
            "全屏录制",
            "捕获当前单显示器完整画面",
            "使用当前画质与帧率",
            "开始全屏录制",
            "monitor",
            self.start_fullscreen_requested.emit,
        )
        self._card_region = RecordingModeCard(
            "区域录制",
            "框选屏幕中的固定区域",
            "最小选区 100 × 100",
            "选择区域",
            "region",
            self.start_region_requested.emit,
        )
        self._card_window = RecordingModeCard(
            "窗口录制",
            "选择一个可见桌面窗口",
            "移动时保持既有冻结策略",
            "选择窗口",
            "window",
            self.start_window_requested.emit,
        )
        self._btn_fullscreen = self._card_fullscreen.action_button
        self._btn_region = self._card_region.action_button
        self._btn_window = self._card_window.action_button
        for card in (self._card_fullscreen, self._card_region, self._card_window):
            mode_layout.addWidget(card, 1)
        root.addLayout(mode_layout)

        summary = QFrame()
        summary.setObjectName("recordingSummary")
        summary.setProperty("role", "panel")
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setHorizontalSpacing(16)
        summary_layout.setVerticalSpacing(8)
        self._quality_value = QLabel()
        self._fps_value = QLabel()
        self._audio_value = QLabel()
        self._path_value = QLabel()
        self._path_value.setWordWrap(False)
        for row, (label, value) in enumerate(
            (
                ("画质", self._quality_value),
                ("帧率", self._fps_value),
                ("音频", self._audio_value),
                ("保存位置", self._path_value),
            )
        ):
            summary_layout.addWidget(QLabel(label), row, 0)
            summary_layout.addWidget(value, row, 1)
        self._btn_open_settings = QPushButton("前往设置")
        self._btn_open_settings.clicked.connect(self.open_settings_requested.emit)
        self._btn_open_settings.setToolTip("打开工作台设置页修改录制参数")
        self._btn_open_settings.setAccessibleName("打开录制设置")
        set_button_icon(self._btn_open_settings, "settings")
        summary_layout.addWidget(self._btn_open_settings, 0, 2, 4, 1)
        root.addWidget(summary)

        state = QFrame()
        state.setObjectName("recordingState")
        state.setProperty("role", "panel")
        state_layout = QVBoxLayout(state)
        state_layout.setContentsMargins(18, 14, 18, 14)
        self._state_title = QLabel()
        self._state_detail = QLabel()
        state_layout.addWidget(self._state_title)
        state_layout.addWidget(self._state_detail)
        root.addWidget(state)

        self._result_panel = QFrame()
        self._result_panel.setObjectName("recordingResult")
        self._result_panel.setProperty("role", "panel")
        result_layout = QVBoxLayout(self._result_panel)
        result_layout.setContentsMargins(18, 14, 18, 14)
        self._result_title = QLabel("录制已保存")
        self._result_path = QLabel()
        self._result_path.setWordWrap(True)
        self._result_status = QLabel()
        self._result_performance = QLabel()
        self._result_performance.setWordWrap(True)
        result_layout.addWidget(self._result_title)
        result_layout.addWidget(self._result_path)
        result_layout.addWidget(self._result_status)
        result_layout.addWidget(self._result_performance)
        result_actions = QHBoxLayout()
        self._btn_open_file = QPushButton("打开视频")
        set_button_icon(self._btn_open_file, "play")
        self._btn_open_file.setToolTip("使用系统默认播放器打开本次录制")
        self._btn_open_file.clicked.connect(
            lambda: self.open_file_requested.emit(self._output_path)
        )
        self._btn_open_folder = QPushButton("打开目录")
        set_button_icon(self._btn_open_folder, "folder")
        self._btn_open_folder.setToolTip("在资源管理器中定位本次录制")
        self._btn_open_folder.clicked.connect(
            lambda: self.open_folder_requested.emit(self._output_path)
        )
        self._btn_open_material = QPushButton("查看素材")
        set_button_icon(self._btn_open_material, "library")
        self._btn_open_material.setToolTip("切换到素材库页查看本次录制")
        self._btn_open_material.clicked.connect(self.open_material_requested.emit)
        self._btn_retry_material = QPushButton("重试入库")
        set_button_icon(self._btn_retry_material, "refresh")
        self._btn_retry_material.setToolTip("重新尝试把已保存视频写入素材索引")
        self._btn_retry_material.clicked.connect(
            lambda: self.retry_material_requested.emit(self._output_path)
        )
        for button in (
            self._btn_open_file,
            self._btn_open_folder,
            self._btn_open_material,
            self._btn_retry_material,
        ):
            result_actions.addWidget(button)
        result_actions.addStretch()
        result_layout.addLayout(result_actions)
        self._result_panel.hide()
        root.addWidget(self._result_panel)
        root.addStretch()

    def refresh_summary(self) -> None:
        quality = str(self._config.get("quality", "high"))
        fps = int(self._config.get("fps", 30))
        audio = str(self._config.get("audio_source", "none"))
        save_path = str(self._config.get("save_path", ""))
        self._quality_value.setText(QUALITY_LABELS.get(quality, quality))
        self._fps_value.setText(f"{fps} FPS")
        self._audio_value.setText(AUDIO_LABELS.get(audio, audio))
        self._path_value.setText(self._compact_path(save_path))
        self._path_value.setToolTip(save_path)

    @staticmethod
    def _compact_path(path: str, *, limit: int = 58) -> str:
        if len(path) <= limit:
            return path
        candidate = Path(path)
        anchor = candidate.anchor
        parts = [part for part in candidate.parts if part != anchor]
        if len(parts) >= 2:
            compact = str(Path(anchor, parts[0], "...", parts[-1]))
            if len(compact) <= limit:
                return compact
        return f"...{path[-(limit - 3):]}"

    def set_recording_state(self, state: str, *, mode: str = "") -> None:
        active = state in {"countdown", "recording", "paused", "saving"}
        for button in (self._btn_fullscreen, self._btn_region, self._btn_window):
            button.setEnabled(not active)
        if state == "idle":
            self._state_title.setText("准备录制")
            self._state_detail.setText("录制控制将在独立浮动工具栏中显示。")
        elif state == "countdown":
            self._state_title.setText("录制即将开始")
            self._state_detail.setText("可在倒计时浮层中取消。")
        elif state == "selecting":
            self._state_title.setText("正在选择录制范围")
            self._state_detail.setText("取消选择后将返回工作台。")
        elif state == "starting":
            self._state_title.setText("正在启动录制")
            self._state_detail.setText("正在校验捕获与编码环境。")
        elif state == "recording":
            self._state_title.setText(f"{MODE_LABELS.get(mode, mode or '屏幕')}录制中")
            self._state_detail.setText("工作台仅展示状态；暂停、停止和取消请使用浮动工具栏。")
        elif state == "paused":
            self._state_title.setText("录制已暂停")
            self._state_detail.setText("请使用浮动工具栏继续或停止。")
        elif state == "saving":
            self._state_title.setText("正在保存")
            self._state_detail.setText("视频编码完成前请勿退出 QuickRec。")
        else:
            self._state_title.setText("录制状态不可用")
            self._state_detail.setText(state)
        state_panel = self._state_title.parentWidget()
        if state_panel is not None:
            state_panel.setProperty("state", state)
            refresh_style(state_panel)

    def show_result(
        self,
        output_path: str,
        size_text: str,
        *,
        index_ok: bool,
        performance_text: str = "",
        performance_stable: bool = True,
    ) -> None:
        self._output_path = output_path
        self._result_title.setText("录制已保存")
        self._result_path.setText(f"{output_path} · {size_text}")
        self._result_status.setText(
            "已加入素材库" if index_ok else "素材入库失败，视频文件仍已保存"
        )
        self._result_performance.setText(performance_text)
        self._result_performance.setVisible(bool(performance_text))
        result_state = "saved" if index_ok and performance_stable else "warning"
        self._result_panel.setProperty("state", result_state)
        refresh_style(self._result_panel)
        self._btn_open_file.show()
        self._btn_open_folder.show()
        self._btn_open_material.setVisible(index_ok)
        self._btn_retry_material.setVisible(not index_ok)
        self._result_panel.show()

    def clear_result(self) -> None:
        self._output_path = ""
        self._result_panel.hide()

    def show_failure(self, message: str) -> None:
        self._output_path = ""
        self._result_title.setText("录制未保存")
        self._result_path.setText(message)
        self._result_status.setText("请检查诊断信息后重试。")
        self._result_performance.clear()
        self._result_performance.hide()
        self._btn_open_file.hide()
        self._btn_open_folder.hide()
        self._btn_open_material.hide()
        self._btn_retry_material.hide()
        self._result_panel.setProperty("state", "error")
        refresh_style(self._result_panel)
        self._result_panel.show()


class DiagnosticPage(QWidget):
    """独立诊断目录草稿、操作入口和显式保存页面。"""

    config_saved = pyqtSignal()
    dirty_changed = pyqtSignal(bool)
    copy_diagnostic_requested = pyqtSignal(str)
    open_diagnostic_dir_requested = pyqtSignal(str)
    export_diagnostic_requested = pyqtSignal(str)

    def __init__(self, config: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._loading = False
        self._dirty = False
        self._init_ui()
        self.load_config()

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)
        title = QLabel("诊断")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        subtitle = QLabel("诊断信息仅保存在本地，用于排查录制和保存异常。")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(subtitle)

        capability_title = QLabel("120 FPS 能力")
        capability_title.setProperty("role", "sectionTitle")
        root.addWidget(capability_title)
        self._capture_capability_status = QLabel("尚未读取能力检测状态")
        self._capture_capability_status.setWordWrap(True)
        root.addWidget(self._capture_capability_status)

        section_title = QLabel("诊断文件")
        section_title.setProperty("role", "sectionTitle")
        root.addWidget(section_title)

        path_row = QHBoxLayout()
        self._edit_diagnostic_dir = QLineEdit()
        self._edit_diagnostic_dir.setAccessibleName("诊断目录")
        self._edit_diagnostic_dir.textChanged.connect(self._mark_dirty)
        path_row.addWidget(self._edit_diagnostic_dir, 1)
        browse = QPushButton("选择目录")
        browse.clicked.connect(self._browse_directory)
        browse.setToolTip("选择本地诊断文件保存目录")
        browse.setAccessibleName("选择诊断目录")
        set_button_icon(browse, "folder")
        path_row.addWidget(browse)
        root.addLayout(path_row)

        actions = QHBoxLayout()
        self._btn_copy = QPushButton("复制诊断信息")
        self._btn_open = QPushButton("打开日志目录")
        self._btn_export = QPushButton("导出诊断文件")
        set_button_icon(self._btn_copy, "copy")
        set_button_icon(self._btn_open, "folder")
        set_button_icon(self._btn_export, "file")
        self._btn_copy.setToolTip("将当前诊断摘要复制到剪贴板")
        self._btn_open.setToolTip("在资源管理器中打开诊断目录")
        self._btn_export.setToolTip("生成可供排查使用的本地诊断文本文件")
        self._btn_copy.clicked.connect(
            lambda: self.copy_diagnostic_requested.emit(self.current_directory)
        )
        self._btn_open.clicked.connect(
            lambda: self.open_diagnostic_dir_requested.emit(self.current_directory)
        )
        self._btn_export.clicked.connect(
            lambda: self.export_diagnostic_requested.emit(self.current_directory)
        )
        for button in (self._btn_copy, self._btn_open, self._btn_export):
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)
        root.addStretch()

        save_row = QHBoxLayout()
        save_row.addStretch()
        self._btn_discard = QPushButton("放弃更改")
        self._btn_discard.setToolTip("恢复到上次已保存的诊断目录")
        self._btn_discard.clicked.connect(self.discard_changes)
        self._btn_save = QPushButton("保存更改")
        self._btn_save.setProperty("role", "primary")
        self._btn_save.setToolTip("保存当前诊断目录设置")
        set_button_icon(self._btn_save, "save", color="#FFFFFF")
        self._btn_save.clicked.connect(self._save_clicked)
        save_row.addWidget(self._btn_discard)
        save_row.addWidget(self._btn_save)
        root.addLayout(save_row)
        self._sync_buttons()

    def _save_clicked(self) -> None:
        self.save_changes()

    @property
    def current_directory(self) -> str:
        return self._edit_diagnostic_dir.text().strip()

    def load_config(self) -> None:
        self._loading = True
        self._edit_diagnostic_dir.setText(self._config.get_diagnostic_dir())
        self._loading = False
        self._set_dirty(False)
        self._status_label.setText("")

    def _mark_dirty(self, _text: str = "") -> None:
        if not self._loading:
            self._set_dirty(
                self.current_directory != str(self._config.get_diagnostic_dir())
            )

    def _set_dirty(self, dirty: bool) -> None:
        changed = dirty != self._dirty
        self._dirty = dirty
        self._sync_buttons()
        if changed:
            self.dirty_changed.emit(dirty)

    def _sync_buttons(self) -> None:
        if hasattr(self, "_btn_save"):
            self._btn_save.setEnabled(self._dirty)
            self._btn_discard.setEnabled(self._dirty)

    def save_changes(self) -> bool:
        if not self._dirty:
            return True
        candidate = self._config.snapshot()
        directory = self.current_directory
        default_directory = str(
            Path(str(candidate.get("save_path", ""))) / "QuickRecDiagnostics"
        )
        if directory == default_directory:
            candidate["diagnostic_dir"] = ""
            candidate["diagnostic_dir_customized"] = False
        elif directory:
            candidate["diagnostic_dir"] = directory
            candidate["diagnostic_dir_customized"] = True
        result = self._config.save_candidate(candidate)
        if not result.ok:
            self._status_label.setText(
                f"保存失败：{result.stage}。当前输入已保留，可修复后重试。"
            )
            return False
        self._set_dirty(False)
        self._status_label.setText("诊断目录已保存")
        self.config_saved.emit()
        return True

    def discard_changes(self) -> None:
        self.load_config()

    def confirm_navigation(self) -> bool:
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("诊断目录尚未保存")
        box.setText("保存诊断目录更改后再继续吗？")
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

    def set_diagnostic_status(self, text: str) -> None:
        self._status_label.setText(text)

    def set_capture_capability_status(self, text: str) -> None:
        self._capture_capability_status.setText(text)

    def _browse_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择诊断目录",
            self.current_directory,
        )
        if selected:
            self._edit_diagnostic_dir.setText(selected)
