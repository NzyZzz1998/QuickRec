"""QuickRec Full 独立剪辑工作台窗口与单实例协调器。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PyQt5.QtCore import QEvent, QMimeData, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QDrag, QIcon, QImage, QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QSplitter,
    QSplitterHandle,
    QVBoxLayout,
    QWidget,
)

from services.playback_runtime import (
    PlaybackRuntime,
    PlaybackSnapshot,
    PlaybackState,
)
from services.project_materials import (
    ProjectMaterialDescriptor,
    resolve_project_media_sources,
)
from services.pyav_playback_backend import PyAVPlaybackBackend
from services.timeline_edit_service import TimelineEditCandidate
from services.timeline_health import (
    TimelineClipHealth,
    assess_timeline_clip_health,
    summarize_timeline_health,
)
from services.timeline_query import timeline_duration_us
from services.timeline_session import TimelineSession, TimelineSessionRegistry
from ui.clip_inspector_widget import ClipInspectorWidget
from ui.design_system import COLORS, WORKBENCH_STYLESHEET, quickrec_icon, set_button_icon
from ui.timeline_canvas import TimelineCanvas
from ui.timeline_edit_dialogs import TimelineImpactDialog
from utils.timeline_model import (
    MAX_TRACKS_PER_KIND,
    Timeline,
    TimelineClip,
    TimelineTrack,
)
from utils.timeline_view import DEFAULT_TIMELINE_PIXELS_PER_SECOND

_MATERIAL_ID_ROLE = Qt.UserRole
_MATERIAL_HAS_AUDIO_ROLE = Qt.UserRole + 1
_MATERIAL_PATH_ROLE = Qt.UserRole + 2
_MATERIAL_AVAILABLE_ROLE = Qt.UserRole + 3


class _TimelineMaterialList(QListWidget):
    """只导出 QuickRec 时间线素材 MIME，不接受外部写入。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setDefaultDropAction(Qt.CopyAction)

    def startDrag(self, _supported_actions) -> None:
        item = self.currentItem()
        if item is None or not bool(item.data(_MATERIAL_AVAILABLE_ROLE)):
            return
        payload = {
            "material_id": str(item.data(_MATERIAL_ID_ROLE)),
            "has_audio": bool(item.data(_MATERIAL_HAS_AUDIO_ROLE)),
        }
        mime = QMimeData()
        mime.setData(
            TimelineCanvas.MATERIAL_MIME_TYPE,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        icon = item.icon()
        if not icon.isNull():
            drag.setPixmap(icon.pixmap(self.iconSize()))
        drag.exec_(Qt.CopyAction)


class _TimelineSplitterHandle(QSplitterHandle):
    def keyPressEvent(self, event) -> None:
        splitter = self.splitter()
        if not isinstance(splitter, _TimelineSplitter):
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key_Home:
            splitter.move_to_boundary(primary_minimum=True)
        elif key == Qt.Key_End:
            splitter.move_to_boundary(primary_minimum=False)
        elif key in {Qt.Key_Up, Qt.Key_Left}:
            splitter.nudge(-12)
        elif key in {Qt.Key_Down, Qt.Key_Right}:
            splitter.nudge(12)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        splitter = self.splitter()
        if isinstance(splitter, _TimelineSplitter):
            splitter.restore_default()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _TimelineSplitter(QSplitter):
    ratio_changed = pyqtSignal(float)

    def __init__(
        self,
        orientation: Qt.Orientation,
        *,
        default_ratio: float = 0.68,
        parent=None,
    ) -> None:
        super().__init__(orientation, parent)
        self.default_ratio = min(0.8, max(0.2, float(default_ratio)))
        self.splitterMoved.connect(self._emit_ratio)

    def createHandle(self) -> QSplitterHandle:
        handle = _TimelineSplitterHandle(self.orientation(), self)
        handle.setFocusPolicy(Qt.StrongFocus)
        handle.setToolTip(
            "拖动调整预览与时间线高度；方向键微调，Home/End 到边界，双击恢复"
        )
        return handle

    def restore_default(self) -> None:
        total = self._available_total()
        primary = round(total * self.default_ratio)
        secondary = total - primary
        primary, secondary = self._safe_sizes(primary, secondary)
        self.setSizes([primary, secondary])
        self._emit_ratio()

    def nudge(self, delta: int) -> None:
        sizes = self.sizes()
        if len(sizes) < 2:
            return
        primary, secondary = self._safe_sizes(
            sizes[0] + int(delta),
            sizes[1] - int(delta),
        )
        self.setSizes([primary, secondary])
        self._emit_ratio()

    def move_to_boundary(self, *, primary_minimum: bool) -> None:
        total = self._available_total()
        minimum_primary = max(
            160,
            _required_splitter_widget(self, 0).minimumSizeHint().height(),
        )
        minimum_secondary = max(
            200,
            _required_splitter_widget(self, 1).minimumSizeHint().height(),
        )
        if primary_minimum:
            primary = min(minimum_primary, max(0, total - minimum_secondary))
        else:
            primary = max(minimum_primary, total - minimum_secondary)
        secondary = total - primary
        primary, secondary = self._safe_sizes(primary, secondary)
        self.setSizes([primary, secondary])
        self._emit_ratio()

    def _available_total(self) -> int:
        sizes = self.sizes()
        total = sum(sizes)
        return total if total > 0 else max(400, self.height() - self.handleWidth())

    def _safe_sizes(self, primary: int, secondary: int) -> tuple[int, int]:
        total = max(1, int(primary) + int(secondary))
        minimum_primary = min(266, max(160, total - 200))
        minimum_secondary = min(200, max(120, total - minimum_primary))
        primary = min(
            max(minimum_primary, int(primary)),
            max(minimum_primary, total - minimum_secondary),
        )
        return primary, max(minimum_secondary, total - primary)

    def _emit_ratio(self, *_args) -> None:
        sizes = self.sizes()
        total = sum(sizes)
        if total > 0:
            self.ratio_changed.emit(sizes[0] / total)


class TimelineEditorWindow(QMainWindow):
    """与主工作台并存的独立顶级剪辑窗口。"""

    return_to_project_requested = pyqtSignal(str)
    open_material_workspace_requested = pyqtSignal(str)
    open_diagnostics_requested = pyqtSignal(str)
    export_requested = pyqtSignal(str)
    start_recording_requested = pyqtSignal(str, str)
    hidden_requested = pyqtSignal()

    def __init__(
        self,
        parent=None,
        *,
        material_provider: (
            Callable[[Any], list[ProjectMaterialDescriptor]] | None
        ) = None,
        playback_runtime_factory: (
            Callable[[Any, Any], PlaybackRuntime] | None
        ) = None,
        audio_decision_provider: Callable[[], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("quickrecTimelineEditor")
        self.setWindowTitle("QuickRec 剪辑工作台")
        self.setWindowIcon(quickrec_icon("record", COLORS["blue"], 24))
        self.setMinimumSize(960, 640)
        self.resize(1280, 800)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._material_provider = material_provider
        self._playback_runtime_factory = (
            playback_runtime_factory or _create_playback_runtime
        )
        self._audio_decision_provider = audio_decision_provider
        self._session: TimelineSession | Any | None = None
        self._playback_runtime: PlaybackRuntime | None = None
        self._current_materials: list[Any] = []
        self._clip_health: dict[str, TimelineClipHealth] = {}
        self._preview_image: QImage | None = None
        self._inspector_candidate: TimelineEditCandidate | None = None
        self._shutting_down = False
        self._pending_success_text = "时间线已保存"
        self._init_ui()
        self._write_control_tooltips = {
            button: button.toolTip()
            for button in (
                self._btn_add_selected,
                self._btn_undo,
                self._btn_redo,
                self._btn_split_clip,
                self._btn_delete_clip,
                self._btn_add_video_track,
                self._btn_add_audio_track,
                self._btn_rename_track,
                self._btn_move_track_up,
                self._btn_move_track_down,
                self._btn_delete_track,
            )
        }
        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(16)
        self._playback_timer.timeout.connect(self._on_playback_tick)
        self._shortcut_split = QShortcut(QKeySequence("Ctrl+B"), self)
        self._shortcut_split.setContext(Qt.WindowShortcut)
        self._shortcut_split.activated.connect(self._on_split_clip)
        self._shortcut_delete_clip = QShortcut(
            QKeySequence(Qt.Key_Delete),
            self,
        )
        self._shortcut_delete_clip.setContext(Qt.WindowShortcut)
        self._shortcut_delete_clip.activated.connect(self._on_delete_shortcut)
        self.setStyleSheet(WORKBENCH_STYLESHEET + _EDITOR_STYLESHEET)

    @property
    def session(self) -> TimelineSession | Any | None:
        return self._session

    @property
    def project_id(self) -> str | None:
        return (
            str(self._session.project_id)
            if self._session is not None
            else None
        )

    def _init_ui(self) -> None:
        root_widget = QWidget()
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        command_bar = QFrame()
        command_bar.setObjectName("timelineCommandBar")
        command_layout = QHBoxLayout(command_bar)
        command_layout.setContentsMargins(14, 10, 14, 10)
        command_layout.setSpacing(8)

        self._btn_return = QPushButton("返回项目")
        self._btn_return.setToolTip("激活主工作台并返回当前项目；剪辑状态会在本进程中保留")
        set_button_icon(self._btn_return, "folder")
        self._btn_return.clicked.connect(self._emit_return_to_project)
        command_layout.addWidget(self._btn_return)

        title_block = QVBoxLayout()
        title_block.setSpacing(1)
        self._project_name = QLabel("未打开项目")
        self._project_name.setObjectName("timelineProjectName")
        title_block.addWidget(self._project_name)
        self._save_status = QLabel("等待项目")
        self._save_status.setObjectName("pageSubtitle")
        title_block.addWidget(self._save_status)
        command_layout.addLayout(title_block, 1)

        self._btn_restore_timeline = QPushButton("从备份恢复")
        self._btn_restore_timeline.setToolTip(
            "使用项目 .bak 恢复时间线；恢复前会保留当前损坏文件"
        )
        self._btn_restore_timeline.clicked.connect(
            self._on_restore_timeline
        )
        self._btn_restore_timeline.hide()
        command_layout.addWidget(self._btn_restore_timeline)

        self._btn_rebuild_timeline = QPushButton("重建空时间线")
        self._btn_rebuild_timeline.setToolTip(
            "先保留损坏项目副本，再移除损坏编排并创建空时间线"
        )
        self._btn_rebuild_timeline.clicked.connect(
            self._on_rebuild_timeline
        )
        self._btn_rebuild_timeline.hide()
        command_layout.addWidget(self._btn_rebuild_timeline)

        self._recording_status = QLabel("")
        self._recording_status.setObjectName("timelineRecordingStatus")
        self._recording_status.hide()
        command_layout.addWidget(self._recording_status)

        self._btn_materials = QPushButton("素材工作台")
        self._btn_materials.setToolTip("激活主工作台素材库；当前剪辑窗口和项目上下文保持")
        set_button_icon(self._btn_materials, "library")
        self._btn_materials.clicked.connect(self._emit_open_materials)
        command_layout.addWidget(self._btn_materials)

        self._btn_export = QPushButton("导出项目")
        self._btn_export.setToolTip(
            "从当前已保存项目创建不可变导出计划；加入队列后可继续编辑"
        )
        set_button_icon(self._btn_export, "file")
        self._btn_export.clicked.connect(self._emit_export)
        self._btn_export.setEnabled(False)
        command_layout.addWidget(self._btn_export)

        self._btn_record = QPushButton("开始录制")
        self._btn_record.setProperty("role", "primary")
        self._btn_record.setToolTip("复用 QuickRec 既有录制页选择全屏、区域或窗口模式")
        set_button_icon(
            self._btn_record,
            "record",
            color="#FFFFFF",
        )
        record_menu = QMenu(self._btn_record)
        for label, mode in (
            ("全屏录制", "fullscreen"),
            ("区域录制", "region"),
            ("窗口录制", "window"),
        ):
            action = record_menu.addAction(label)
            assert action is not None
            action.triggered.connect(
                lambda _checked=False, target=mode: self._emit_start_recording(
                    target
                )
            )
        self._btn_record.setMenu(record_menu)
        command_layout.addWidget(self._btn_record)

        self._btn_close = QPushButton()
        self._btn_close.setAccessibleName("关闭剪辑工作台")
        self._btn_close.setToolTip("关闭剪辑工作台；QuickRec 和主工作台继续运行")
        self._btn_close.setFixedSize(36, 36)
        set_button_icon(self._btn_close, "close")
        self._btn_close.clicked.connect(self._request_close)
        command_layout.addWidget(self._btn_close)
        root.addWidget(command_bar)

        self._save_error_bar = QFrame()
        self._save_error_bar.setObjectName("timelineSaveErrorBar")
        error_layout = QHBoxLayout(self._save_error_bar)
        error_layout.setContentsMargins(14, 8, 14, 8)
        error_layout.setSpacing(8)
        self._save_error_message = QLabel("")
        self._save_error_message.setObjectName("timelineSaveErrorMessage")
        self._save_error_message.setWordWrap(True)
        error_layout.addWidget(self._save_error_message, 1)

        self._btn_retry_save = QPushButton("重试保存")
        self._btn_retry_save.setToolTip("重新提交刚才失败的同一项修改，不重复执行其他命令")
        self._btn_retry_save.clicked.connect(self._retry_pending_save)
        error_layout.addWidget(self._btn_retry_save)

        self._btn_error_diagnostics = QPushButton("查看诊断")
        self._btn_error_diagnostics.setToolTip(
            "打开主工作台诊断页；当前失败候选和项目文件保持不变"
        )
        self._btn_error_diagnostics.clicked.connect(
            self._emit_open_diagnostics
        )
        error_layout.addWidget(self._btn_error_diagnostics)

        self._btn_discard_change = QPushButton("放弃本次修改")
        self._btn_discard_change.setToolTip(
            "丢弃尚未写入磁盘的本次候选，恢复到最近一次成功保存的状态"
        )
        self._btn_discard_change.clicked.connect(
            self._discard_pending_save
        )
        error_layout.addWidget(self._btn_discard_change)

        self._btn_reload_external = QPushButton("重新加载")
        self._btn_reload_external.setToolTip(
            "放弃本次候选并读取外部修改后的项目；不会覆盖外部版本"
        )
        self._btn_reload_external.clicked.connect(
            self._reload_external_project
        )
        error_layout.addWidget(self._btn_reload_external)

        self._btn_save_recovery_copy = QPushButton("保存恢复副本")
        self._btn_save_recovery_copy.setToolTip(
            "把本次候选另存为项目旁的恢复文件，不登记为新项目且不覆盖原文件"
        )
        self._btn_save_recovery_copy.clicked.connect(
            self._save_external_recovery_copy
        )
        error_layout.addWidget(self._btn_save_recovery_copy)

        self._btn_cancel_conflict = QPushButton("取消")
        self._btn_cancel_conflict.setToolTip(
            "暂不处理冲突；保留候选和错误条，不覆盖任何项目文件"
        )
        self._btn_cancel_conflict.clicked.connect(
            self._cancel_external_conflict
        )
        error_layout.addWidget(self._btn_cancel_conflict)
        self._save_error_bar.hide()
        root.addWidget(self._save_error_bar)

        self._main_splitter = _TimelineSplitter(
            Qt.Vertical,
            default_ratio=0.68,
        )
        self._main_splitter.setObjectName("timelineMainSplitter")
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.ratio_changed.connect(self._store_splitter_ratio)

        self._workspace_splitter = QSplitter(Qt.Horizontal)
        self._workspace_splitter.setObjectName("timelineWorkspaceSplitter")
        self._workspace_splitter.setChildrenCollapsible(False)
        self._workspace_splitter.addWidget(self._build_material_rail())
        self._workspace_splitter.addWidget(self._build_preview_panel())
        self._workspace_splitter.setSizes([300, 980])
        self._main_splitter.addWidget(self._workspace_splitter)
        self._main_splitter.addWidget(self._build_timeline_panel())
        self._main_splitter.setSizes([510, 240])
        root.addWidget(self._main_splitter, 1)
        self.setCentralWidget(root_widget)

    def _build_material_rail(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("timelineMaterialRail")
        panel.setMinimumWidth(240)
        panel.setMaximumWidth(380)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        label = QLabel("项目素材")
        label.setProperty("role", "sectionTitle")
        header.addWidget(label, 1)
        self._btn_collapse_materials = QPushButton("收起")
        self._btn_collapse_materials.setToolTip("收起项目素材区，为预览画面释放更多宽度")
        self._btn_collapse_materials.clicked.connect(self._toggle_materials)
        header.addWidget(self._btn_collapse_materials)
        layout.addLayout(header)
        self._material_search = QLineEdit()
        self._material_search.setPlaceholderText("搜索名称或路径")
        self._material_search.setClearButtonEnabled(True)
        self._material_search.textChanged.connect(self._filter_materials)
        layout.addWidget(self._material_search)
        self._material_list = _TimelineMaterialList()
        self._material_list.setAccessibleName("项目素材列表")
        self._material_list.setIconSize(QSize(96, 54))
        self._material_list.setSpacing(4)
        self._material_list.currentItemChanged.connect(
            self._on_material_selection_changed
        )
        self._material_list.itemDoubleClicked.connect(
            lambda _item: self._on_add_selected_material()
        )
        layout.addWidget(self._material_list, 1)
        self._material_hint = QLabel("选择素材后可加入兼容轨道")
        self._material_hint.setObjectName("pageSubtitle")
        layout.addWidget(self._material_hint)
        self._btn_add_selected = QPushButton("加入时间线")
        self._btn_add_selected.setEnabled(False)
        self._btn_add_selected.setToolTip(
            "把当前素材追加到第一组兼容轨道；有音频时同时创建关联音频片段"
        )
        self._btn_add_selected.clicked.connect(self._on_add_selected_material)
        set_button_icon(self._btn_add_selected, "library")
        layout.addWidget(self._btn_add_selected)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("timelinePreviewPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        header = QHBoxLayout()
        label = QLabel("时间线预览")
        label.setProperty("role", "sectionTitle")
        header.addWidget(label, 1)
        self._btn_maximize_preview = QPushButton("放大预览")
        self._btn_maximize_preview.setToolTip("隐藏时间线并放大预览；再次点击恢复原分栏")
        self._btn_maximize_preview.clicked.connect(self._toggle_preview_maximized)
        header.addWidget(self._btn_maximize_preview)
        layout.addLayout(header)
        self._preview_surface = QLabel("播放后端将在 D6 接入")
        self._preview_surface.setObjectName("timelinePreviewSurface")
        self._preview_surface.setAlignment(Qt.AlignCenter)
        self._preview_surface.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        layout.addWidget(self._preview_surface, 1)
        controls = QHBoxLayout()
        self._btn_play = QPushButton("播放")
        self._btn_play.setEnabled(False)
        self._btn_play.setToolTip("从当前播放头播放；播放中点击将暂停")
        self._btn_play.clicked.connect(self._toggle_playback)
        set_button_icon(self._btn_play, "play")
        self._btn_play.setProperty("playbackIcon", "play")
        controls.addWidget(self._btn_play)
        self._time_label = QLabel("00:00.000 / 00:00.000")
        controls.addWidget(self._time_label)
        controls.addStretch(1)
        self._btn_retry_playback = QPushButton("重试播放")
        self._btn_retry_playback.setToolTip(
            "释放当前播放资源并从播放头重新准备；仅在整体播放失败时显示"
        )
        self._btn_retry_playback.clicked.connect(self._retry_playback)
        self._btn_retry_playback.hide()
        controls.addWidget(self._btn_retry_playback)
        self._btn_open_diagnostics = QPushButton("查看诊断")
        self._btn_open_diagnostics.setToolTip(
            "打开主工作台诊断页；剪辑窗口和当前项目上下文保持"
        )
        self._btn_open_diagnostics.clicked.connect(
            self._emit_open_diagnostics
        )
        controls.addWidget(self._btn_open_diagnostics)
        self._preview_status = QLabel("未播放")
        controls.addWidget(self._preview_status)
        layout.addLayout(controls)
        return panel

    def _build_timeline_panel(self) -> QWidget:
        panel = QFrame()
        self._timeline_panel = panel
        panel.setObjectName("timelinePanel")
        panel.setMinimumHeight(200)
        panel.installEventFilter(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 10)
        toolbar = QHBoxLayout()
        self._btn_undo = QPushButton("撤销")
        self._btn_undo.setEnabled(False)
        self._btn_undo.setToolTip("撤销最近一次成功保存的时间线编辑")
        self._btn_undo.clicked.connect(self._on_undo)
        toolbar.addWidget(self._btn_undo)
        self._btn_redo = QPushButton("重做")
        self._btn_redo.setEnabled(False)
        self._btn_redo.setToolTip("重新执行最近一次被撤销的时间线编辑")
        self._btn_redo.clicked.connect(self._on_redo)
        toolbar.addWidget(self._btn_redo)
        self._btn_split_clip = QPushButton("分割")
        self._btn_split_clip.setToolTip(
            "在播放头处分割当前片段或关联音视频组（Ctrl+B）"
        )
        self._btn_split_clip.clicked.connect(self._on_split_clip)
        toolbar.addWidget(self._btn_split_clip)
        self._btn_delete_clip = QPushButton("删除片段")
        self._btn_delete_clip.setToolTip(
            "预览影响后，从时间线删除当前片段并执行全局波纹（Delete）"
        )
        self._btn_delete_clip.clicked.connect(self._on_delete_clip)
        toolbar.addWidget(self._btn_delete_clip)
        self._ripple_mode_label = QLabel("全局波纹")
        self._ripple_mode_label.setObjectName("timelineRippleMode")
        self._ripple_mode_label.setToolTip(
            "固定开启：裁剪或删除会移动全部未锁定轨道上的后续片段"
        )
        toolbar.addWidget(self._ripple_mode_label)
        self._btn_add_video_track = QPushButton("视频轨")
        self._btn_add_video_track.setToolTip("新增一条视频轨，视频轨最多 8 条")
        self._btn_add_video_track.clicked.connect(
            lambda: self._on_add_track("video")
        )
        toolbar.addWidget(self._btn_add_video_track)
        self._btn_add_audio_track = QPushButton("音频轨")
        self._btn_add_audio_track.setToolTip("新增一条音频轨，音频轨最多 8 条")
        self._btn_add_audio_track.clicked.connect(
            lambda: self._on_add_track("audio")
        )
        toolbar.addWidget(self._btn_add_audio_track)
        self._btn_rename_track = QPushButton("重命名轨道")
        self._btn_rename_track.setToolTip("修改当前选中轨道名称并原子保存")
        self._btn_rename_track.clicked.connect(self._on_rename_track)
        toolbar.addWidget(self._btn_rename_track)
        self._btn_move_track_up = QPushButton("上移")
        self._btn_move_track_up.setToolTip("在同类型轨道中把当前轨道上移一层")
        self._btn_move_track_up.clicked.connect(
            lambda: self._on_reorder_track(-1)
        )
        toolbar.addWidget(self._btn_move_track_up)
        self._btn_move_track_down = QPushButton("下移")
        self._btn_move_track_down.setToolTip("在同类型轨道中把当前轨道下移一层")
        self._btn_move_track_down.clicked.connect(
            lambda: self._on_reorder_track(1)
        )
        toolbar.addWidget(self._btn_move_track_down)
        self._btn_delete_track = QPushButton("删除轨道")
        self._btn_delete_track.setToolTip(
            "删除空轨道；有片段时必须确认，关联片段会一并处理"
        )
        self._btn_delete_track.clicked.connect(self._on_delete_track)
        toolbar.addWidget(self._btn_delete_track)
        toolbar.addStretch(1)
        self._btn_focus_timeline = QPushButton("专注时间线")
        self._btn_focus_timeline.setToolTip("隐藏素材区和预览，让轨道使用全部可用空间")
        self._btn_focus_timeline.clicked.connect(self._toggle_timeline_focus)
        toolbar.addWidget(self._btn_focus_timeline)
        self._zoom_label = QLabel("100%")
        toolbar.addWidget(self._zoom_label)
        self._btn_zoom_out = QPushButton("-")
        self._btn_zoom_out.setAccessibleName("缩小时间线")
        self._btn_zoom_out.setToolTip("以当前画布中心缩小时间线")
        self._btn_zoom_out.clicked.connect(lambda: self._change_zoom(1 / 1.25))
        toolbar.addWidget(self._btn_zoom_out)
        self._btn_zoom_in = QPushButton("+")
        self._btn_zoom_in.setAccessibleName("放大时间线")
        self._btn_zoom_in.setToolTip("以当前画布中心放大时间线")
        self._btn_zoom_in.clicked.connect(lambda: self._change_zoom(1.25))
        toolbar.addWidget(self._btn_zoom_in)
        self._btn_fit_timeline = QPushButton("适配")
        self._btn_fit_timeline.setToolTip("缩放到完整时间线适合当前可见宽度")
        self._btn_fit_timeline.clicked.connect(self._fit_timeline)
        toolbar.addWidget(self._btn_fit_timeline)
        layout.addLayout(toolbar)
        selection_row = QHBoxLayout()
        self._selection_summary = QLabel("未选择片段")
        self._selection_summary.setObjectName("pageSubtitle")
        selection_row.addWidget(self._selection_summary, 1)
        self._btn_clip_inspector = QPushButton("片段属性")
        self._btn_clip_inspector.setToolTip(
            "打开精确裁剪检查器，查看源范围、关联状态和波纹影响"
        )
        self._btn_clip_inspector.clicked.connect(
            self._open_clip_inspector
        )
        selection_row.addWidget(self._btn_clip_inspector)
        layout.addLayout(selection_row)
        self._timeline_scroll = QScrollArea()
        self._timeline_scroll.setObjectName("timelineScrollArea")
        self._timeline_scroll.setWidgetResizable(False)
        self._timeline_scroll.setFrameShape(QFrame.NoFrame)
        self._timeline_canvas = TimelineCanvas()
        self._timeline_canvas.clip_selected.connect(self._on_clip_selected)
        self._timeline_canvas.track_selected.connect(self._on_track_selected)
        self._timeline_canvas.playhead_requested.connect(
            self._on_playhead_requested
        )
        self._timeline_canvas.clip_move_requested.connect(
            self._on_clip_move_requested
        )
        self._timeline_canvas.clip_trim_preview_requested.connect(
            self._on_clip_trim_preview_requested
        )
        self._timeline_canvas.clip_trim_commit_requested.connect(
            self._on_clip_trim_commit_requested
        )
        self._timeline_canvas.clip_context_requested.connect(
            self._on_clip_context_requested
        )
        self._timeline_canvas.track_lock_requested.connect(
            self._on_track_lock_requested
        )
        self._timeline_canvas.material_drop_requested.connect(
            self._on_material_drop_requested
        )
        self._timeline_canvas.invalid_drop.connect(self._show_timeline_error)
        self._timeline_canvas.zoom_changed.connect(self._on_canvas_zoom_changed)
        self._timeline_scroll.setWidget(self._timeline_canvas)
        horizontal = self._timeline_scroll.horizontalScrollBar()
        vertical = self._timeline_scroll.verticalScrollBar()
        assert horizontal is not None
        assert vertical is not None
        horizontal.valueChanged.connect(self._on_horizontal_scroll_changed)
        vertical.valueChanged.connect(self._on_vertical_scroll_changed)
        layout.addWidget(self._timeline_scroll, 1)

        self._clip_inspector = ClipInspectorWidget(panel)
        self._clip_inspector.preview_requested.connect(
            self._on_inspector_preview_requested
        )
        self._clip_inspector.apply_requested.connect(
            self._on_inspector_apply_requested
        )
        self._clip_inspector.cancel_requested.connect(
            self._cancel_edit_preview
        )
        self._clip_inspector.hide()
        return panel

    def set_session(self, session: TimelineSession | Any) -> None:
        self._release_playback()
        self._hide_save_error()
        self._cancel_edit_preview()
        self._clip_inspector.hide()
        self._current_materials = []
        self._session = session
        self._apply_recording_status(
            bool(getattr(session, "recording_active", False))
        )
        self._set_timeline_recovery_actions(session)
        if not bool(getattr(session, "ready", False)):
            self._clip_health = {}
            self._timeline_canvas.set_timeline(Timeline("unavailable", []))
            self._timeline_canvas.set_clip_statuses({})
            status = str(getattr(session, "status", "") or "unavailable")
            try:
                project = session.project
            except (RuntimeError, AttributeError):
                project = None
            self._project_name.setText(
                str(project.name) if project is not None else "项目不可用"
            )
            if project is not None:
                self._populate_materials(self._material_items(project))
            else:
                self._populate_materials([])
            status_text = {
                "corrupt": (
                    "时间线数据损坏，项目素材仍可查看；"
                    "请选择从备份恢复或保留损坏副本后重建"
                ),
                "unsupported": (
                    "时间线版本高于当前程序，已启用只读保护"
                ),
                "missing": "项目文件缺失，无法加载时间线",
            }.get(
                status,
                str(getattr(session, "error", "") or "无法读取时间线"),
            )
            self._save_status.setText(status_text)
            self._preview_surface.setText("时间线不可播放")
            self._btn_play.setEnabled(False)
            self._set_editor_enabled(False)
            return
        project = session.project
        self._project_name.setText(str(project.name))
        status = str(getattr(session, "status", "ready"))
        read_only = bool(getattr(session, "read_only", False))
        self._save_status.setText(self._session_save_status_text(session))
        self._current_materials = self._material_items(project)
        self._populate_materials(self._current_materials)
        self._timeline_canvas.set_timeline(session.timeline)
        self._refresh_clip_health()
        self._set_editor_enabled(
            status in {"ready", "available", "empty"} and not read_only
        )
        self._apply_session_layout()
        self._create_lazy_playback_runtime()
        commands = getattr(session, "commands", None)
        if bool(getattr(commands, "has_pending_save", False)):
            stage = str(getattr(commands, "pending_save_stage", "") or "project")
            self._show_save_failure(
                stage,
                "上一次修改尚未保存，请先处理后再继续编辑",
            )

    def _set_timeline_recovery_actions(self, session: Any) -> None:
        corrupt = str(getattr(session, "status", "")) == "corrupt"
        writable = not bool(getattr(session, "recording_active", False))
        commands = getattr(session, "commands", None)
        backup_available = bool(
            getattr(
                commands,
                "timeline_backup_available",
                getattr(session, "timeline_backup_available", False),
            )
        )
        self._btn_restore_timeline.setVisible(
            corrupt and backup_available
        )
        self._btn_restore_timeline.setEnabled(
            corrupt and backup_available and writable
        )
        self._btn_rebuild_timeline.setVisible(corrupt)
        self._btn_rebuild_timeline.setEnabled(corrupt and writable)

    def _on_restore_timeline(self) -> None:
        session = self._session
        recover = getattr(session, "recover_timeline_from_backup", None)
        if not callable(recover):
            self._show_timeline_error("当前会话无法执行备份恢复")
            return
        answer = QMessageBox.question(
            self,
            "从备份恢复时间线",
            "将使用项目 .bak 恢复整个项目文件。当前损坏文件会先保留，"
            "但备份之后的项目改动可能回退。继续吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        result = recover()
        if not result.ok:
            self._show_timeline_error(
                f"{result.stage}：{result.error or '备份恢复失败'}"
            )
            return
        self.set_session(session)
        self._save_status.setText("时间线已从项目备份恢复")

    def _on_rebuild_timeline(self) -> None:
        session = self._session
        rebuild = getattr(session, "rebuild_empty_timeline", None)
        if not callable(rebuild):
            self._show_timeline_error("当前会话无法重建时间线")
            return
        answer = QMessageBox.question(
            self,
            "重建空时间线",
            "该操作会丢失当前时间线编排，但不会删除项目素材或视频。"
            "系统会先保留损坏项目副本。继续吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        result = rebuild()
        if not result.ok:
            self._show_timeline_error(
                f"{result.stage}：{result.error or '时间线重建失败'}"
            )
            return
        self.set_session(session)
        self._save_status.setText("损坏数据已保留，空时间线已创建")

    def _material_items(self, project: Any) -> list[Any]:
        if self._material_provider is None:
            return list(project.materials or [])
        try:
            return list(self._material_provider(project))
        except Exception as exc:
            self._save_status.setText(f"素材信息加载失败：{exc}")
            return list(project.materials or [])

    def _populate_materials(self, materials: list[Any]) -> None:
        self._material_list.clear()
        for material in materials:
            if isinstance(material, ProjectMaterialDescriptor):
                material_id = material.material_id
                file_name = material.file_name
                file_path = material.file_path
                duration = material.duration_sec
                audio = material.audio_source
                exists = material.file_exists
                available = (
                    material.business_status == "available" and exists
                )
                status = {
                    "available": "可用",
                    "missing": "文件缺失",
                    "unindexed": "待关联素材库",
                }.get(
                    material.business_status,
                    material.business_status,
                )
                dimensions = (
                    f"{material.width}×{material.height}"
                    if material.width and material.height
                    else "分辨率未知"
                )
                fps = (
                    f"{material.fps:g} FPS"
                    if material.fps is not None
                    else "FPS 未知"
                )
                preview_path = material.preview_path
            else:
                snapshot = material.metadata_snapshot
                material_id = str(material.material_id)
                file_name = str(material.file_name)
                file_path = str(material.last_known_path)
                duration = snapshot.get("duration_sec", 0)
                audio = snapshot.get("audio_source", "none")
                exists = Path(file_path).is_file()
                available = exists
                status = "可用" if exists else "文件缺失"
                width = snapshot.get("width")
                height = snapshot.get("height")
                dimensions = (
                    f"{width}×{height}"
                    if width and height
                    else "分辨率未知"
                )
                raw_fps = snapshot.get("fps")
                fps = (
                    f"{float(raw_fps):g} FPS"
                    if raw_fps is not None
                    else "FPS 未知"
                )
                preview_path = None
            item = QListWidgetItem(
                f"{file_name}\n"
                f"{float(duration or 0):.1f} 秒 · {dimensions} · "
                f"{fps} · {audio} · {status}"
            )
            if preview_path is not None and Path(preview_path).is_file():
                item.setIcon(QIcon(str(preview_path)))
            item.setData(_MATERIAL_ID_ROLE, material_id)
            item.setData(
                _MATERIAL_HAS_AUDIO_ROLE,
                str(audio or "none").lower()
                not in {"", "none", "off", "silent", "无声"},
            )
            item.setData(_MATERIAL_PATH_ROLE, file_path)
            item.setData(_MATERIAL_AVAILABLE_ROLE, available)
            item.setToolTip(file_path)
            item.setSizeHint(QSize(0, 70))
            self._material_list.addItem(item)
        if self._material_list.count() > 0:
            self._material_list.setCurrentRow(0)
        self._sync_command_controls()

    def _set_editor_enabled(self, writable: bool) -> None:
        self._writable = bool(writable)
        self._timeline_canvas.set_editing_enabled(writable)
        read_only_hint = (
            "当前时间线只读；请结束录制、处理保存失败，或恢复可写项目后再操作"
        )
        self._timeline_canvas.setToolTip("" if writable else read_only_hint)
        for button, tooltip in self._write_control_tooltips.items():
            button.setToolTip(tooltip if writable else read_only_hint)
        self._material_list.setDragEnabled(writable)
        self._btn_undo.setEnabled(
            writable
            and bool(getattr(getattr(self._session, "commands", None), "undo_depth", 0))
        )
        self._btn_redo.setEnabled(
            writable
            and bool(getattr(getattr(self._session, "commands", None), "redo_depth", 0))
        )
        self._update_export_action()
        self._sync_command_controls()

    def _update_export_action(self) -> None:
        session = self._session
        commands = getattr(session, "commands", None)
        enabled = bool(
            session is not None
            and getattr(session, "project_id", None)
            and bool(getattr(session, "ready", False))
            and str(getattr(session, "status", ""))
            in {"ready", "available", "empty"}
            and not bool(getattr(commands, "has_pending_save", False))
            and str(getattr(commands, "pending_save_stage", ""))
            != "external_conflict"
        )
        self._btn_export.setEnabled(enabled)

    def _sync_command_controls(self) -> None:
        writable = bool(getattr(self, "_writable", False))
        session = self._session
        timeline = (
            session.timeline
            if session is not None and bool(getattr(session, "ready", False))
            else None
        )
        selected_track = self._selected_track() if timeline is not None else None
        selected_clip_id = self._timeline_canvas.selected_clip_id()
        selected_clip = self._clip_by_id(selected_clip_id)
        selected_clip_track = (
            self._track_by_id(selected_clip.track_id)
            if selected_clip is not None
            else None
        )
        selected_health = (
            self._clip_health.get(selected_clip.clip_id)
            if selected_clip is not None
            else None
        )
        selected_clip_base_editable = bool(
            writable
            and selected_clip is not None
            and selected_clip_track is not None
            and not selected_clip_track.locked
        )
        selected_clip_range_editable = bool(
            selected_clip_base_editable
            and (
                selected_health is None
                or selected_health.range_editable
            )
        )
        selected_clip_delete_editable = bool(
            selected_clip_base_editable
            and (
                selected_health is None
                or selected_health.delete_editable
            )
        )
        selected_clip_viewable = bool(
            timeline is not None and selected_clip is not None
        )
        current_material = self._material_list.currentItem()
        material_available = bool(
            current_material is not None
            and current_material.data(_MATERIAL_AVAILABLE_ROLE)
        )
        self._btn_add_selected.setEnabled(
            writable
            and material_available
            and (selected_track is None or not selected_track.locked)
        )
        self._btn_add_video_track.setEnabled(
            writable
            and timeline is not None
            and sum(track.kind == "video" for track in timeline.tracks)
            < MAX_TRACKS_PER_KIND
        )
        self._btn_add_audio_track.setEnabled(
            writable
            and timeline is not None
            and sum(track.kind == "audio" for track in timeline.tracks)
            < MAX_TRACKS_PER_KIND
        )
        has_track = writable and selected_track is not None
        self._btn_rename_track.setEnabled(has_track)
        peers = (
            sorted(
                (
                    track
                    for track in timeline.tracks
                    if selected_track is not None
                    and track.kind == selected_track.kind
                ),
                key=lambda track: track.order,
            )
            if timeline is not None
            else []
        )
        self._btn_move_track_up.setEnabled(
            has_track and selected_track is not None and selected_track.order > 0
        )
        self._btn_move_track_down.setEnabled(
            has_track
            and selected_track is not None
            and selected_track.order < len(peers) - 1
        )
        self._btn_delete_track.setEnabled(has_track and len(peers) > 1)
        self._btn_delete_clip.setEnabled(selected_clip_delete_editable)
        self._btn_clip_inspector.setEnabled(selected_clip_viewable)
        block_reason = self._clip_edit_block_reason(
            selected_clip,
            selected_clip_track,
            selected_health,
            writable=writable,
        )
        self._btn_delete_clip.setToolTip(
            "预览影响后，从时间线删除当前片段并执行全局波纹（Delete）"
            if selected_clip_delete_editable
            else block_reason
        )
        self._btn_clip_inspector.setToolTip(
            "打开片段属性；当前状态仅允许查看，不能裁剪"
            if selected_clip_viewable and not selected_clip_range_editable
            else "打开精确裁剪检查器，查看源范围、关联状态和波纹影响"
        )
        split_enabled = False
        split_reason = block_reason
        commands = getattr(session, "commands", None)
        if selected_clip_range_editable and commands is not None:
            assert selected_clip is not None
            playhead_us = int(
                getattr(
                    getattr(session, "view_state", None),
                    "playhead_us",
                    0,
                )
            )
            preview_split = getattr(commands, "preview_split_clip", None)
            if callable(preview_split):
                candidate = preview_split(
                    selected_clip.clip_id,
                    playhead_us=playhead_us,
                )
                split_enabled = bool(candidate.valid)
                if candidate.conflicts:
                    split_reason = "；".join(
                        item.message for item in candidate.conflicts
                    )
                elif split_enabled:
                    split_reason = "在播放头处分割当前片段或关联组（Ctrl+B）"
        self._btn_split_clip.setEnabled(split_enabled)
        self._btn_split_clip.setToolTip(split_reason)
        if hasattr(self, "_clip_inspector"):
            self._clip_inspector.set_editable(selected_clip_range_editable)

    def _clip_edit_block_reason(
        self,
        clip: TimelineClip | None,
        track: TimelineTrack | None,
        health: TimelineClipHealth | None,
        *,
        writable: bool,
    ) -> str:
        if clip is None:
            return "请先选择一个片段"
        if not writable:
            session = self._session
            if bool(getattr(session, "recording_active", False)):
                return "正在录制，时间线暂时只读"
            commands = getattr(session, "commands", None)
            if bool(getattr(commands, "has_pending_save", False)):
                return "存在待处理保存，解决后才能继续编辑"
            project = getattr(session, "project", None)
            if project is not None and getattr(project, "archived_at", None):
                return "项目已归档，当前为只读查看"
            return "当前项目为只读状态"
        if track is not None and track.locked:
            return "当前轨道已锁定"
        if health is not None and health.status == "missing":
            return "素材文件缺失；可查看属性或确认后波纹删除"
        if health is not None and health.status == "link_error":
            return "关联异常；整组只读，请查看诊断或从备份恢复"
        return "请先选择一个可编辑片段"

    def _refresh_clip_health(self) -> None:
        session = self._session
        if session is None or not bool(getattr(session, "ready", False)):
            self._clip_health = {}
            self._timeline_canvas.set_clip_statuses({})
            return
        self._clip_health = assess_timeline_clip_health(
            session.timeline,
            session.project,
            self._current_materials,
        )
        self._timeline_canvas.set_clip_statuses(
            {
                clip_id: item.status
                for clip_id, item in self._clip_health.items()
            }
        )

    def _apply_session_layout(self) -> None:
        state = getattr(self._session, "view_state", None)
        if state is None:
            return
        self._zoom_label.setText(_format_zoom(float(state.zoom)))
        self._time_label.setText(
            f"{_format_us(int(state.playhead_us))} / 00:00.000"
        )
        self._timeline_canvas.set_playhead(int(state.playhead_us))
        self._timeline_canvas.set_zoom(float(state.zoom))
        self._timeline_canvas.select_track(state.selected_track_id)
        self._timeline_canvas.select_clip(state.selected_clip_id)
        total = max(400, sum(self._main_splitter.sizes()) or 750)
        primary = round(total * float(state.splitter_ratio))
        self._main_splitter.setSizes([primary, total - primary])
        _required_splitter_widget(self._workspace_splitter, 0).setVisible(
            not bool(state.materials_collapsed)
        )
        self._btn_collapse_materials.setText(
            "展开" if state.materials_collapsed else "收起"
        )
        _required_splitter_widget(self._main_splitter, 0).setVisible(
            not bool(state.timeline_focused)
        )
        _required_splitter_widget(self._main_splitter, 1).setVisible(
            not bool(state.preview_maximized)
        )
        self._btn_focus_timeline.setText(
            "显示预览" if state.timeline_focused else "专注时间线"
        )
        self._btn_maximize_preview.setText(
            "恢复分栏" if state.preview_maximized else "放大预览"
        )
        self._btn_focus_timeline.setEnabled(
            not bool(state.preview_maximized)
        )
        self._btn_maximize_preview.setEnabled(
            not bool(state.timeline_focused)
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._restore_session_splitter)
        QTimer.singleShot(0, self._position_clip_inspector)

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is getattr(self, "_timeline_panel", None)
            and event.type() == QEvent.Resize
        ):
            QTimer.singleShot(0, self._position_clip_inspector)
        return super().eventFilter(watched, event)

    def _position_clip_inspector(self) -> None:
        inspector = getattr(self, "_clip_inspector", None)
        panel = getattr(self, "_timeline_panel", None)
        if inspector is None or panel is None:
            return
        width = min(360, max(300, panel.width() // 3))
        top = 8
        bottom = 8
        inspector.setGeometry(
            max(0, panel.width() - width - 8),
            top,
            width,
            max(0, panel.height() - top - bottom),
        )
        if inspector.isVisible():
            inspector.raise_()

    def _restore_session_splitter(self) -> None:
        state = getattr(self._session, "view_state", None)
        if state is not None:
            self._main_splitter.default_ratio = float(state.splitter_ratio)
        self._main_splitter.restore_default()

    def _on_material_selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        self._sync_command_controls()
        if current is None:
            self._material_hint.setText("选择素材后可加入兼容轨道")
        else:
            self._material_hint.setText(
                f"已选择：{current.text().splitlines()[0]}"
            )

    def _on_add_selected_material(self) -> None:
        item = self._material_list.currentItem()
        commands = getattr(self._session, "commands", None)
        if item is None or commands is None:
            return
        selected_track_id = self._timeline_canvas.selected_track_id()
        selected_track = self._track_by_id(selected_track_id)
        video_track_id = (
            selected_track_id
            if selected_track is not None and selected_track.kind == "video"
            else None
        )
        audio_track_id = (
            selected_track_id
            if selected_track is not None and selected_track.kind == "audio"
            else None
        )
        result = commands.add_material(
            str(item.data(_MATERIAL_ID_ROLE)),
            has_audio=bool(item.data(_MATERIAL_HAS_AUDIO_ROLE)),
            video_track_id=video_track_id,
            audio_track_id=audio_track_id,
        )
        self._apply_command_result(result, success_text="素材已加入并自动保存")

    def _on_material_drop_requested(
        self,
        material_id: str,
        has_audio: bool,
        start_us: int,
        track_id: str,
    ) -> None:
        commands = getattr(self._session, "commands", None)
        track = self._track_by_id(track_id)
        if commands is None or track is None:
            self._show_timeline_error("素材拖入目标已经失效")
            return
        result = commands.add_material(
            material_id,
            has_audio=has_audio,
            timeline_start_us=start_us,
            video_track_id=track_id if track.kind == "video" else None,
            audio_track_id=track_id if track.kind == "audio" else None,
        )
        self._apply_command_result(
            result,
            success_text="素材已拖入时间线并自动保存",
        )

    def _on_undo(self) -> None:
        commands = getattr(self._session, "commands", None)
        if commands is not None:
            self._apply_command_result(
                commands.undo(),
                success_text="已撤销并自动保存",
            )

    def _on_redo(self) -> None:
        commands = getattr(self._session, "commands", None)
        if commands is not None:
            self._apply_command_result(
                commands.redo(),
                success_text="已重做并自动保存",
            )

    def _on_add_track(self, kind: str) -> None:
        commands = getattr(self._session, "commands", None)
        if commands is None:
            return
        result = commands.add_track(kind)
        self._apply_command_result(
            result,
            success_text=(
                "视频轨已新增并自动保存"
                if kind == "video"
                else "音频轨已新增并自动保存"
            ),
        )

    def _on_rename_track(self) -> None:
        track = self._selected_track()
        commands = getattr(self._session, "commands", None)
        if track is None or commands is None:
            self._show_timeline_error("请先选择一条轨道")
            return
        name, accepted = QInputDialog.getText(
            self,
            "重命名轨道",
            "轨道名称",
            text=track.name,
        )
        if not accepted:
            return
        self._apply_command_result(
            commands.rename_track(track.track_id, name),
            success_text="轨道已重命名并自动保存",
        )

    def _on_reorder_track(self, delta: int) -> None:
        track = self._selected_track()
        commands = getattr(self._session, "commands", None)
        session = self._session
        if track is None or commands is None or session is None:
            self._show_timeline_error("请先选择一条轨道")
            return
        peers = sorted(
            (
                item
                for item in session.timeline.tracks
                if item.kind == track.kind
            ),
            key=lambda item: item.order,
        )
        target = min(
            len(peers) - 1,
            max(0, track.order + int(delta)),
        )
        if target == track.order:
            self._show_timeline_error("轨道已经位于该方向的边界")
            return
        self._apply_command_result(
            commands.reorder_track(track.track_id, target),
            success_text="轨道顺序已更新并自动保存",
        )

    def _on_delete_track(self) -> None:
        track = self._selected_track()
        commands = getattr(self._session, "commands", None)
        if track is None or commands is None:
            self._show_timeline_error("请先选择一条轨道")
            return
        result = commands.delete_track(track.track_id)
        if result.requires_confirmation:
            if QMessageBox.question(
                self,
                "删除轨道",
                "该轨道包含片段，删除后关联片段也会一并移除。继续吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            ) != QMessageBox.Yes:
                return
            result = commands.delete_track(track.track_id, confirmed=True)
        self._apply_command_result(
            result,
            success_text="轨道已删除并自动保存",
        )

    def _on_delete_clip(self) -> None:
        clip_id = self._timeline_canvas.selected_clip_id()
        commands = getattr(self._session, "commands", None)
        if clip_id is None or commands is None:
            self._show_timeline_error("请先选择一个片段")
            return
        health = self._clip_health.get(clip_id)
        if health is not None and not health.delete_editable:
            self._show_timeline_error(health.reason or "当前片段不可删除")
            return
        self._pause_for_edit()
        candidate = commands.preview_ripple_delete(clip_id)
        self._confirm_and_commit_edit(
            candidate,
            title="删除片段并执行全局波纹",
            confirm_text="从时间线删除并波纹",
            success_text="片段已删除，全局波纹已应用并自动保存",
        )

    def _on_delete_shortcut(self) -> None:
        if isinstance(QApplication.focusWidget(), QLineEdit):
            return
        self._on_delete_clip()

    def _on_split_clip(self) -> None:
        clip_id = self._timeline_canvas.selected_clip_id()
        commands = getattr(self._session, "commands", None)
        if clip_id is None or commands is None or self._session is None:
            self._show_timeline_error("请先选择一个片段")
            return
        health = self._clip_health.get(clip_id)
        if health is not None and not health.range_editable:
            self._show_timeline_error(health.reason or "当前片段不可分割")
            return
        self._pause_for_edit()
        playhead_us = int(self._session.view_state.playhead_us)
        candidate = commands.preview_split_clip(
            clip_id,
            playhead_us=playhead_us,
        )
        if not candidate.valid:
            self._show_edit_candidate_error(candidate)
            return
        self._commit_edit_candidate(
            candidate,
            success_text="片段已在播放头处分割并自动保存",
        )

    def _on_clip_trim_preview_requested(
        self,
        clip_id: str,
        source_start_us: int,
        source_end_us: int,
    ) -> None:
        commands = getattr(self._session, "commands", None)
        if commands is None:
            self._timeline_canvas.set_trim_candidate(None)
            return
        health = self._clip_health.get(clip_id)
        if health is not None and not health.range_editable:
            self._timeline_canvas.set_trim_candidate(None)
            self._show_timeline_error(health.reason or "当前片段不可裁剪")
            return
        self._pause_for_edit()
        candidate = commands.preview_trim_clip(
            clip_id,
            source_start_us=source_start_us,
            source_end_us=source_end_us,
        )
        self._inspector_candidate = candidate
        self._timeline_canvas.set_trim_candidate(candidate)
        if self._clip_inspector.isVisible():
            self._clip_inspector.set_candidate(candidate)
        if candidate.valid:
            self._save_status.setText(
                "正在预览裁剪候选 · 正式时间线尚未改变"
            )
        else:
            self._show_edit_candidate_error(candidate)

    def _on_clip_trim_commit_requested(
        self,
        candidate: TimelineEditCandidate,
    ) -> None:
        self._confirm_and_commit_edit(
            candidate,
            title="确认裁剪与全局波纹",
            confirm_text="确认并应用",
            success_text="裁剪与全局波纹已应用并自动保存",
        )

    def _on_inspector_preview_requested(
        self,
        source_start_us: int,
        source_end_us: int,
    ) -> None:
        clip_id = self._timeline_canvas.selected_clip_id()
        commands = getattr(self._session, "commands", None)
        if clip_id is None or commands is None:
            return
        self._pause_for_edit()
        candidate = commands.preview_trim_clip(
            clip_id,
            source_start_us=source_start_us,
            source_end_us=source_end_us,
        )
        self._inspector_candidate = candidate
        self._clip_inspector.set_candidate(candidate)
        self._timeline_canvas.set_trim_candidate(candidate)

    def _on_inspector_apply_requested(
        self,
        candidate: TimelineEditCandidate,
    ) -> None:
        self._confirm_and_commit_edit(
            candidate,
            title="确认精确裁剪与全局波纹",
            confirm_text="确认并应用",
            success_text="精确裁剪与全局波纹已应用并自动保存",
        )

    def _on_track_lock_requested(
        self,
        track_id: str,
        locked: bool,
    ) -> None:
        commands = getattr(self._session, "commands", None)
        if commands is None:
            return
        self._cancel_edit_preview()
        self._apply_command_result(
            commands.set_track_locked(track_id, locked),
            success_text=(
                "轨道已锁定并自动保存"
                if locked
                else "轨道已解锁并自动保存"
            ),
        )

    def _on_clip_context_requested(
        self,
        _clip_id: str,
        global_position,
    ) -> None:
        menu = QMenu(self)
        split_action = menu.addAction("在播放头处分割\tCtrl+B")
        assert split_action is not None
        split_action.setEnabled(self._btn_split_clip.isEnabled())
        split_action.triggered.connect(self._on_split_clip)
        properties_action = menu.addAction("片段属性")
        assert properties_action is not None
        properties_action.setEnabled(self._btn_clip_inspector.isEnabled())
        properties_action.triggered.connect(self._open_clip_inspector)
        delete_action = menu.addAction("删除片段并执行全局波纹\tDelete")
        assert delete_action is not None
        delete_action.setEnabled(self._btn_delete_clip.isEnabled())
        delete_action.triggered.connect(self._on_delete_clip)
        menu.exec_(global_position)

    def _confirm_and_commit_edit(
        self,
        candidate: TimelineEditCandidate,
        *,
        title: str,
        confirm_text: str,
        success_text: str,
    ) -> None:
        accepted = TimelineImpactDialog.execute(
            self,
            candidate,
            title=title,
            confirm_text=confirm_text,
            locate_callback=self._locate_edit_conflict,
        )
        if not accepted:
            self._cancel_edit_preview()
            if candidate.conflicts:
                self._show_edit_candidate_error(candidate)
            else:
                self._save_status.setText(
                    "已取消候选 · 正式时间线未改变"
                )
            return
        if not candidate.valid:
            self._show_edit_candidate_error(candidate)
            return
        self._commit_edit_candidate(
            candidate,
            success_text=success_text,
        )

    def _commit_edit_candidate(
        self,
        candidate: TimelineEditCandidate,
        *,
        success_text: str,
    ) -> None:
        commands = getattr(self._session, "commands", None)
        if commands is None:
            return
        result = commands.commit_edit_candidate(candidate)
        self._cancel_edit_preview()
        self._apply_command_result(
            result,
            success_text=success_text,
            preferred_clip_ids=candidate.selected_clip_ids,
        )

    def _show_edit_candidate_error(
        self,
        candidate: TimelineEditCandidate,
    ) -> None:
        detail = "；".join(
            conflict.message for conflict in candidate.conflicts
        )
        self._show_timeline_error(detail or "剪辑候选无效")

    def _locate_edit_conflict(
        self,
        track_id: str,
        clip_id: str,
    ) -> None:
        if clip_id and self._clip_by_id(clip_id) is not None:
            clip = self._clip_by_id(clip_id)
            assert clip is not None
            self._timeline_canvas.select_clip(clip_id)
            self._on_clip_selected(clip_id, clip.track_id)
        elif track_id and self._track_by_id(track_id) is not None:
            self._timeline_canvas.select_track(track_id)
            self._on_track_selected(track_id)
        self._save_status.setText("已定位首个全局波纹冲突")

    def _pause_for_edit(self) -> None:
        runtime = self._playback_runtime
        if (
            runtime is not None
            and runtime.snapshot().state == PlaybackState.PLAYING
        ):
            self._render_playback_snapshot(runtime.pause())

    def _cancel_edit_preview(self) -> None:
        had_preview = self._inspector_candidate is not None
        self._inspector_candidate = None
        if hasattr(self, "_timeline_canvas"):
            had_preview = had_preview or self._timeline_canvas.trim_active
            self._timeline_canvas.cancel_trim()
            if had_preview and self._session is not None and bool(
                getattr(self._session, "ready", False)
            ):
                self._timeline_canvas.set_timeline(self._session.timeline)
                state = self._session.view_state
                self._timeline_canvas.select_track(state.selected_track_id)
                self._timeline_canvas.select_clip(state.selected_clip_id)

    def _on_clip_selected(self, clip_id: str, track_id: str) -> None:
        session = self._session
        if session is not None:
            session.update_view_state(
                selected_clip_id=clip_id,
                selected_track_id=track_id,
            )
        if session is None:
            return
        self._refresh_selection_summary(clip_id)
        if self._clip_inspector.isVisible():
            self._load_selected_clip_in_inspector()
        self._sync_command_controls()

    def _refresh_selection_summary(self, clip_id: str | None) -> None:
        clip = self._clip_by_id(clip_id)
        self._selection_summary.setText(
            f"已选 {clip.clip_id} · 源 "
            f"{_format_us(clip.source_start_us)}–"
            f"{_format_us(clip.source_start_us + clip.source_duration_us)}"
            if clip is not None
            else "未选择片段"
        )

    def _on_track_selected(self, track_id: str) -> None:
        if self._session is not None:
            self._session.update_view_state(
                selected_track_id=track_id,
                selected_clip_id=None,
            )
        track = self._track_by_id(track_id)
        self._selection_summary.setText(
            f"已选轨道：{track.name}" if track is not None else "未选择片段"
        )
        self._cancel_edit_preview()
        self._clip_inspector.hide()
        self._sync_command_controls()

    def _on_playhead_requested(self, value_us: int) -> None:
        if self._session is not None:
            self._session.update_view_state(playhead_us=value_us)
        self._sync_command_controls()
        runtime = self._playback_runtime
        if (
            runtime is not None
            and runtime.snapshot().state != PlaybackState.STOPPED
        ):
            self._render_playback_snapshot(runtime.seek(value_us))
            return
        self._time_label.setText(
            f"{_format_us(value_us)} / {_format_us(self._timeline_end_us())}"
        )

    def _on_clip_move_requested(
        self,
        clip_id: str,
        start_us: int,
        track_id: str,
    ) -> None:
        commands = getattr(self._session, "commands", None)
        if commands is None:
            return
        health = self._clip_health.get(clip_id)
        if health is not None and not health.move_editable:
            self._show_timeline_error(health.reason or "当前片段不可移动")
            return
        self._apply_command_result(
            commands.move_clip(
                clip_id,
                timeline_start_us=start_us,
                target_track_id=track_id,
            ),
            success_text="片段位置已更新并自动保存",
        )

    def _change_zoom(self, factor: float) -> None:
        current = (
            self._timeline_canvas.scale.pixels_per_second
            / DEFAULT_TIMELINE_PIXELS_PER_SECOND
        )
        self._timeline_canvas.set_zoom(current * factor)

    def _fit_timeline(self) -> None:
        viewport = self._timeline_scroll.viewport()
        assert viewport is not None
        self._timeline_canvas.fit_timeline(viewport.width())

    def _on_canvas_zoom_changed(self, zoom: float, origin_us: int) -> None:
        self._zoom_label.setText(_format_zoom(zoom))
        if self._session is not None:
            self._session.update_view_state(
                zoom=zoom,
                horizontal_scroll_us=origin_us,
            )

    def _on_horizontal_scroll_changed(self, value: int) -> None:
        time_us = self._timeline_canvas.scale.x_to_time(
            value + self._timeline_canvas.track_header_width
        )
        if self._session is not None:
            self._session.update_view_state(horizontal_scroll_us=time_us)

    def _on_vertical_scroll_changed(self, value: int) -> None:
        if self._session is not None:
            self._session.update_view_state(vertical_scroll=value)

    def _store_splitter_ratio(self, ratio: float) -> None:
        if self._session is not None:
            self._session.update_view_state(splitter_ratio=ratio)

    def _apply_command_result(
        self,
        result,
        *,
        success_text: str,
        preferred_clip_ids: tuple[str, ...] = (),
    ) -> None:
        if not result.ok:
            commands = getattr(self._session, "commands", None)
            if bool(getattr(commands, "has_pending_save", False)):
                self._pending_success_text = success_text
                self._show_save_failure(
                    str(result.stage),
                    str(result.error or "操作未生效"),
                )
                return
            self._show_timeline_error(
                f"{result.stage}：{result.error or '操作未生效'}"
            )
            return
        self._hide_save_error()
        affected = tuple(result.affected_clip_ids)
        selected_clip_id = (
            preferred_clip_ids[0]
            if preferred_clip_ids
            else (
                affected[0]
                if affected
                else self._timeline_canvas.selected_clip_id()
            )
        )
        valid_clip_ids = (
            {
                clip.clip_id
                for clip in self._session.timeline.clips
            }
            if self._session is not None
            else set()
        )
        if selected_clip_id not in valid_clip_ids:
            selected_clip_id = None
        selected_track_id = (
            tuple(result.affected_track_ids)[0]
            if result.affected_track_ids
            else self._timeline_canvas.selected_track_id()
        )
        if self._session is not None:
            self._session.update_view_state(
                selected_clip_id=selected_clip_id,
                selected_track_id=selected_track_id,
            )
        self._save_status.setText(success_text)
        self._refresh_timeline()
        self._rebuild_playback_after_edit()

    def _refresh_timeline(self) -> None:
        if self._session is None or not bool(getattr(self._session, "ready", False)):
            return
        timeline = self._session.timeline
        self._timeline_canvas.set_timeline(timeline)
        self._refresh_clip_health()
        state = self._session.view_state
        self._timeline_canvas.select_track(state.selected_track_id)
        self._timeline_canvas.select_clip(state.selected_clip_id)
        self._refresh_selection_summary(state.selected_clip_id)
        self._time_label.setText(
            f"{_format_us(state.playhead_us)} / {_format_us(self._timeline_end_us())}"
        )
        self._set_editor_enabled(
            not bool(getattr(self._session, "read_only", False))
            and str(getattr(self._session, "status", ""))
            in {"ready", "available", "empty"}
        )
        if self._clip_inspector.isVisible():
            if not self._load_selected_clip_in_inspector():
                self._clip_inspector.hide()

    def _show_timeline_error(self, message: str) -> None:
        self._save_status.setText(f"未保存：{message}")

    def _show_save_failure(self, stage: str, error: str) -> None:
        external_conflict = stage == "external_conflict"
        self._save_error_message.setText(
            "项目文件已在外部修改。QuickRec 未覆盖外部版本，"
            "请选择重新加载或保存恢复副本。"
            if external_conflict
            else f"时间线保存失败（{stage}）：{error}"
        )
        self._btn_retry_save.setVisible(not external_conflict)
        self._btn_error_diagnostics.setVisible(not external_conflict)
        self._btn_discard_change.setVisible(not external_conflict)
        self._btn_reload_external.setVisible(external_conflict)
        self._btn_save_recovery_copy.setVisible(external_conflict)
        self._btn_cancel_conflict.setVisible(external_conflict)
        self._save_error_bar.show()
        self._save_status.setText("未保存 · 等待处理")
        self._set_editor_enabled(False)

    def _hide_save_error(self) -> None:
        self._save_error_bar.hide()

    def _retry_pending_save(self) -> None:
        commands = getattr(self._session, "commands", None)
        retry = getattr(commands, "retry_pending_save", None)
        if not callable(retry):
            self._show_timeline_error("当前会话无法重试保存")
            return
        self._apply_command_result(
            retry(),
            success_text=self._pending_success_text,
        )

    def _discard_pending_save(self) -> None:
        commands = getattr(self._session, "commands", None)
        discard = getattr(commands, "discard_pending_save", None)
        if not callable(discard):
            self._show_timeline_error("当前会话无法放弃失败修改")
            return
        result = discard()
        if not result.ok:
            self._show_timeline_error(
                f"{result.stage}：{result.error or '放弃失败'}"
            )
            return
        self._hide_save_error()
        self._save_status.setText("已放弃本次修改 · 仍使用上次已保存状态")
        self._refresh_timeline()

    def _reload_external_project(self) -> None:
        commands = getattr(self._session, "commands", None)
        reload_project = getattr(commands, "reload_external_project", None)
        if not callable(reload_project):
            self._show_timeline_error("当前会话无法重新加载项目")
            return
        result = reload_project()
        if not result.ok:
            self._show_save_failure(
                str(result.stage),
                str(result.error or "重新加载失败"),
            )
            return
        assert self._session is not None
        self.set_session(self._session)
        self._save_status.setText("已重新加载外部版本 · 未覆盖外部修改")

    def _save_external_recovery_copy(self) -> None:
        commands = getattr(self._session, "commands", None)
        save_copy = getattr(commands, "save_pending_recovery_copy", None)
        if not callable(save_copy):
            self._show_timeline_error("当前会话无法保存恢复副本")
            return
        result = save_copy()
        if not result.ok:
            self._show_save_failure(
                str(result.stage),
                str(result.error or "恢复副本保存失败"),
            )
            return
        assert self._session is not None
        recovery_path = str(result.recovery_path)
        self.set_session(self._session)
        self._save_status.setText(
            f"恢复副本已保存：{Path(recovery_path).name}"
        )

    def _cancel_external_conflict(self) -> None:
        self._save_status.setText(
            "冲突尚未处理 · 未覆盖外部版本，候选修改仍保留"
        )

    def _open_clip_inspector(self) -> None:
        if not self._btn_clip_inspector.isEnabled():
            self._show_timeline_error("当前片段不可精确裁剪")
            return
        if not self._load_selected_clip_in_inspector():
            return
        self._position_clip_inspector()
        self._clip_inspector.show()
        self._clip_inspector.raise_()
        self._clip_inspector.setFocus(Qt.OtherFocusReason)

    def _load_selected_clip_in_inspector(self) -> bool:
        clip = self._clip_by_id(self._timeline_canvas.selected_clip_id())
        track = self._track_by_id(clip.track_id) if clip is not None else None
        session = self._session
        if clip is None or track is None or session is None:
            self._show_timeline_error("请先选择一个片段")
            return False
        material = next(
            (
                item
                for item in session.project.materials
                if item.material_id == clip.material_id
            ),
            None,
        )
        if material is None:
            self._show_timeline_error("片段引用的项目素材不存在")
            return False
        descriptor = next(
            (
                item
                for item in self._current_materials
                if isinstance(item, ProjectMaterialDescriptor)
                and item.material_id == clip.material_id
            ),
            None,
        )
        metadata = material.metadata_snapshot
        try:
            duration_us = round(
                float(
                    descriptor.duration_sec
                    if descriptor is not None
                    and descriptor.duration_sec is not None
                    else metadata.get("duration_sec", 0)
                )
                * 1_000_000
            )
        except (TypeError, ValueError):
            duration_us = 0
        try:
            fps_value = float(
                descriptor.fps
                if descriptor is not None and descriptor.fps is not None
                else metadata.get("fps")
            )
            fps = fps_value if fps_value > 0 else None
        except (TypeError, ValueError):
            fps = None
        linked_count = (
            sum(
                item.link_group_id == clip.link_group_id
                for item in session.timeline.clips
            )
            if clip.link_group_id
            else 1
        )
        health = self._clip_health.get(clip.clip_id)
        file_exists = (
            bool(descriptor.file_exists)
            if descriptor is not None
            else Path(material.last_known_path).is_file()
        )
        editable = bool(
            getattr(self, "_writable", False)
            and not track.locked
            and file_exists
            and (health is None or health.range_editable)
        )
        self._clip_inspector.load_clip(
            clip,
            material_name=(
                descriptor.file_name
                if descriptor is not None
                else material.file_name
            ),
            track_name=track.name,
            material_duration_us=duration_us,
            fps=fps,
            linked_clip_count=linked_count,
            editable=editable,
        )
        if health is not None and health.status == "link_error":
            self._show_timeline_error(
                "关联异常，当前片段组只读；请查看诊断或从备份恢复"
            )
        elif not file_exists:
            self._show_timeline_error("素材文件缺失，裁剪和分割已禁用")
        return True

    def _clip_by_id(self, clip_id: str | None) -> TimelineClip | None:
        if self._session is None or clip_id is None:
            return None
        return next(
            (
                item
                for item in self._session.timeline.clips
                if item.clip_id == clip_id
            ),
            None,
        )

    def _track_by_id(self, track_id: str | None) -> TimelineTrack | None:
        if self._session is None or track_id is None:
            return None
        return next(
            (
                item
                for item in self._session.timeline.tracks
                if item.track_id == track_id
            ),
            None,
        )

    def _selected_track(self) -> TimelineTrack | None:
        return self._track_by_id(self._timeline_canvas.selected_track_id())

    def _timeline_end_us(self) -> int:
        if self._session is None:
            return 0
        return max(
            (
                item.timeline_end_us
                for item in self._session.timeline.clips
            ),
            default=0,
        )

    def set_recording_active(self, active: bool) -> None:
        self._apply_recording_status(bool(active))
        if self._session is not None:
            setter = getattr(self._session, "set_recording_active", None)
            if callable(setter):
                setter(active)
            self._set_editor_enabled(
                bool(getattr(self._session, "ready", False))
                and not bool(getattr(self._session, "read_only", False))
                and str(getattr(self._session, "status", ""))
                in {"ready", "available", "empty"}
            )
            commands = getattr(self._session, "commands", None)
            if not bool(getattr(commands, "has_pending_save", False)):
                self._save_status.setText(
                    self._session_save_status_text(self._session)
                )
            self._set_timeline_recovery_actions(self._session)

    @staticmethod
    def _session_save_status_text(session: Any) -> str:
        project = session.project
        if project.archived_at:
            return "项目已归档 · 只读查看"
        if bool(getattr(session, "read_only", False)):
            return "项目文件只读 · 编辑操作已禁用"
        if str(getattr(session, "status", "ready")) == "empty":
            return "尚未创建时间线 · 首次编辑后自动保存"
        return "已自动保存"

    def _apply_recording_status(self, active: bool) -> None:
        self._recording_status.setVisible(active)
        self._recording_status.setText(
            "录制中 · 请使用浮动工具栏控制" if active else ""
        )
        self._btn_record.setEnabled(not active)

    def _create_lazy_playback_runtime(self) -> None:
        session = self._session
        if (
            session is None
            or not bool(getattr(session, "ready", False))
            or not hasattr(session, "timeline")
            or not hasattr(session, "project")
        ):
            self._btn_play.setEnabled(False)
            return
        playback_project = self._resolved_playback_project()
        runtime = self._playback_runtime_factory(
            playback_project,
            session.timeline,
        )
        self._playback_runtime = runtime
        attach = getattr(session, "attach_media", None)
        if callable(attach):
            attach(runtime)
        duration = timeline_duration_us(session.timeline)
        self._btn_play.setEnabled(duration > 0)
        self._set_playback_button_state(playing=False)
        self._btn_retry_playback.hide()
        self._preview_status.setText("未播放")
        self._preview_image = None
        self._preview_surface.setPixmap(QPixmap())
        self._preview_surface.setText(
            "时间线为空" if duration <= 0 else "点击播放预览时间线"
        )
        state = getattr(session, "view_state", None)
        position_us = int(getattr(state, "playhead_us", 0))
        self._time_label.setText(
            f"{_format_us(position_us)} / {_format_us(duration)}"
        )

    def _toggle_playback(self) -> None:
        runtime = self._playback_runtime
        if runtime is None:
            return
        current = runtime.snapshot()
        if current.state == PlaybackState.PLAYING:
            self._render_playback_snapshot(runtime.pause())
            return
        snapshot = runtime.play()
        snapshot = self._resolve_audio_decision(runtime, snapshot)
        self._render_playback_snapshot(snapshot)

    def _on_playback_tick(self) -> None:
        runtime = self._playback_runtime
        if runtime is not None:
            snapshot = self._resolve_audio_decision(
                runtime,
                runtime.tick(),
            )
            self._render_playback_snapshot(snapshot)

    def _resolve_audio_decision(
        self,
        runtime: PlaybackRuntime,
        snapshot: PlaybackSnapshot,
    ) -> PlaybackSnapshot:
        if not snapshot.needs_audio_decision:
            return snapshot
        if self._request_audio_decision() == "mute":
            runtime.continue_without_audio()
            return runtime.play()
        return runtime.cancel_audio_start()

    def _render_playback_snapshot(
        self,
        snapshot: PlaybackSnapshot,
    ) -> None:
        playing = snapshot.state == PlaybackState.PLAYING
        self._playback_timer.setInterval(16)
        if playing and not self._playback_timer.isActive():
            self._playback_timer.start()
        elif not playing:
            self._playback_timer.stop()
        self._set_playback_button_state(playing=playing)
        self._btn_play.setEnabled(snapshot.duration_us > 0)
        self._btn_retry_playback.setVisible(
            snapshot.state == PlaybackState.ERROR
        )
        if self._session is not None:
            updater = getattr(self._session, "update_view_state", None)
            if callable(updater):
                updater(playhead_us=snapshot.position_us)
        self._timeline_canvas.set_playhead(snapshot.position_us)
        self._time_label.setText(
            f"{_format_us(snapshot.position_us)} / "
            f"{_format_us(snapshot.duration_us)}"
        )

        frame = snapshot.frame
        if frame.video_status == "ready" and frame.video_frame is not None:
            self._set_preview_frame(frame.video_frame)
        elif frame.buffering or frame.video_status == "loading":
            self._set_preview_message("正在准备当前片段…")
        elif frame.video_status in {"error", "missing"}:
            self._set_preview_message(
                snapshot.error or frame.error or "当前视频片段无法解码"
            )
        elif frame.video_status == "blank":
            self._set_preview_message("当前位置没有视频画面")

        if snapshot.needs_audio_decision:
            status = "音频设备不可用"
        elif snapshot.muted:
            status = "无声播放"
        elif snapshot.state == PlaybackState.PLAYING:
            status = "播放中"
        elif snapshot.state == PlaybackState.PAUSED:
            status = "已暂停"
        elif snapshot.state == PlaybackState.ENDED:
            status = "播放结束"
        elif snapshot.state == PlaybackState.ERROR:
            status = snapshot.error or "播放失败"
        else:
            status = "未播放"
        self._preview_status.setText(status)

    def _set_playback_button_state(self, *, playing: bool) -> None:
        label = "暂停" if playing else "播放"
        icon_name = "pause" if playing else "play"
        if self._btn_play.text() != label:
            self._btn_play.setText(label)
        if self._btn_play.property("playbackIcon") != icon_name:
            set_button_icon(self._btn_play, icon_name)
            self._btn_play.setProperty("playbackIcon", icon_name)

    def _set_preview_frame(self, frame: Any) -> None:
        array = np.ascontiguousarray(frame, dtype=np.uint8)
        if array.ndim != 3 or array.shape[2] != 3:
            self._set_preview_message("视频帧格式不受支持")
            return
        height, width, _channels = array.shape
        image = QImage(
            array.data,
            width,
            height,
            int(array.strides[0]),
            QImage.Format_RGB888,
        ).copy()
        self._preview_image = image
        self._apply_preview_image()

    def _apply_preview_image(self) -> None:
        image = self._preview_image
        if image is None or image.isNull():
            return
        target = self._preview_surface.size()
        pixmap = QPixmap.fromImage(image).scaled(
            target,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._preview_surface.setPixmap(pixmap)

    def _set_preview_message(self, message: str) -> None:
        self._preview_image = None
        self._preview_surface.setPixmap(QPixmap())
        self._preview_surface.setText(message)

    def _request_audio_decision(self) -> str:
        if self._audio_decision_provider is not None:
            return str(self._audio_decision_provider())
        dialog = QMessageBox(self)
        dialog.setWindowTitle("音频设备不可用")
        dialog.setText("当前无法打开音频输出设备。是否无声继续预览？")
        mute_button = dialog.addButton("无声继续", QMessageBox.AcceptRole)
        dialog.addButton("取消播放", QMessageBox.RejectRole)
        dialog.exec_()
        return "mute" if dialog.clickedButton() is mute_button else "cancel"

    def _retry_playback(self) -> None:
        session = self._session
        if session is None or not bool(getattr(session, "ready", False)):
            self._show_timeline_error("当前项目尚未准备好，无法重试播放")
            return
        self._release_playback()
        self._create_lazy_playback_runtime()
        self._toggle_playback()

    def _rebuild_playback_after_edit(self) -> None:
        runtime = self._playback_runtime
        session = self._session
        if session is None:
            return
        if runtime is None:
            self._create_lazy_playback_runtime()
            return
        self._render_playback_snapshot(
            runtime.replace_timeline(
                self._resolved_playback_project(),
                session.timeline,
            )
        )

    def _resolved_playback_project(self):
        assert self._session is not None
        descriptors = [
            item
            for item in self._current_materials
            if isinstance(item, ProjectMaterialDescriptor)
        ]
        return resolve_project_media_sources(
            self._session.project,
            descriptors,
        )

    def _release_playback(self) -> None:
        if hasattr(self, "_playback_timer"):
            self._playback_timer.stop()
        runtime = self._playback_runtime
        session = self._session
        if session is not None:
            release = getattr(session, "release_media", None)
            if callable(release):
                release()
            elif runtime is not None:
                runtime.release()
        elif runtime is not None:
            runtime.release()
        self._playback_runtime = None
        self._preview_image = None

    def _filter_materials(self, text: str) -> None:
        keyword = text.strip().casefold()
        for row in range(self._material_list.count()):
            item = self._material_list.item(row)
            assert item is not None
            item.setHidden(bool(keyword) and keyword not in item.text().casefold())

    def _toggle_materials(self) -> None:
        panel = _required_splitter_widget(self._workspace_splitter, 0)
        visible = panel.isVisible()
        panel.setVisible(not visible)
        self._btn_collapse_materials.setText("展开" if visible else "收起")
        if self._session is not None:
            updater = getattr(self._session, "update_view_state", None)
            if callable(updater):
                updater(materials_collapsed=visible)

    def _toggle_preview_maximized(self) -> None:
        timeline = _required_splitter_widget(self._main_splitter, 1)
        maximize = timeline.isVisible()
        timeline.setVisible(not maximize)
        _required_splitter_widget(self._workspace_splitter, 0).setVisible(True)
        self._btn_maximize_preview.setText("恢复分栏" if maximize else "放大预览")
        self._btn_focus_timeline.setEnabled(not maximize)
        if self._session is not None:
            updater = getattr(self._session, "update_view_state", None)
            if callable(updater):
                updater(
                    preview_maximized=maximize,
                    timeline_focused=False,
                )

    def _toggle_timeline_focus(self) -> None:
        preview = _required_splitter_widget(self._main_splitter, 0)
        focus = preview.isVisible()
        preview.setVisible(not focus)
        _required_splitter_widget(self._main_splitter, 1).setVisible(True)
        self._btn_focus_timeline.setText("显示预览" if focus else "专注时间线")
        self._btn_maximize_preview.setEnabled(not focus)
        if self._session is not None:
            updater = getattr(self._session, "update_view_state", None)
            if callable(updater):
                updater(
                    timeline_focused=focus,
                    preview_maximized=False,
                )

    def _emit_return_to_project(self) -> None:
        if self.project_id is not None:
            self.return_to_project_requested.emit(self.project_id)

    def _emit_open_materials(self) -> None:
        if self.project_id is not None:
            self.open_material_workspace_requested.emit(self.project_id)

    def _emit_open_diagnostics(self) -> None:
        if self.project_id is not None:
            self.open_diagnostics_requested.emit(self.project_id)

    def _emit_export(self) -> None:
        if self.project_id is not None:
            self.export_requested.emit(self.project_id)

    def _emit_start_recording(self, mode: str) -> None:
        if self.project_id is not None:
            self.start_recording_requested.emit(self.project_id, mode)

    def _request_close(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:
        self._cancel_edit_preview()
        self._clip_inspector.hide()
        if self._shutting_down:
            self._release_playback()
            event.accept()
            return
        self.hide()
        self.hidden_requested.emit()
        event.ignore()

    def shutdown(self) -> None:
        self._shutting_down = True
        self._release_playback()
        self.close()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_clip_inspector()
        if self._preview_image is not None:
            self._apply_preview_image()

    def diagnostic_summary(self) -> dict[str, object]:
        session = self._session
        commands = getattr(session, "commands", None)
        command_summary: dict[str, object] = (
            dict(commands.diagnostic_summary())
            if commands is not None
            and callable(getattr(commands, "diagnostic_summary", None))
            else {}
        )
        health_summary = summarize_timeline_health(self._clip_health)
        runtime = self._playback_runtime
        playback: dict[str, object]
        if runtime is None:
            playback = {
                "backend": "PyAV",
                "backend_version": "18.0.0",
                "state": "not_initialized",
            }
        else:
            playback = dict(runtime.diagnostic_summary())
        playback.update(command_summary)
        playback.update(
            {
                "available_clips": health_summary["available"],
                "missing_clips": health_summary["missing"],
                "link_error_clips": health_summary["link_error"],
            }
        )
        return playback


class TimelineEditorCoordinator:
    """维护全局唯一剪辑窗口及当前项目会话。"""

    def __init__(
        self,
        window_factory: Callable[[], Any],
        session_registry: TimelineSessionRegistry | Any,
    ) -> None:
        self._window_factory = window_factory
        self._sessions = session_registry
        self._window: Any = None

    @property
    def window(self) -> Any:
        return self._window

    def open(self, project_id: str) -> Any:
        session = self._sessions.open(project_id)
        first_open = self._window is None
        if first_open:
            self._window = self._window_factory()
        self._window.set_session(session)
        if first_open:
            self._window.showMaximized()
        else:
            self._window.show()
        self._window.raise_()
        self._window.activateWindow()
        return self._window

    def hide(self) -> None:
        if self._window is not None:
            self._window.hide()
        self._sessions.close_current()

    def suspend(self) -> None:
        """录制选择与捕获期间仅隐藏窗口，保留当前项目会话。"""
        if self._window is not None:
            self._window.hide()

    def set_recording_active(self, active: bool) -> None:
        self._sessions.set_recording_active(active)
        if self._window is not None:
            setter = getattr(self._window, "set_recording_active", None)
            if callable(setter):
                setter(active)

    def refresh_project(self, project_id: str) -> bool:
        """刷新当前已打开项目，不创建或激活其他剪辑窗口。"""
        current = self._sessions.current_session
        if (
            self._window is None
            or current is None
            or current.project_id != str(project_id)
        ):
            return False
        refresh = getattr(current, "refresh_project_snapshot", None)
        if callable(refresh):
            result = refresh()
            if not bool(getattr(result, "ok", result)):
                return False
        self._window.set_session(current)
        return True

    def shutdown(self) -> None:
        if self._window is not None:
            shutdown = getattr(self._window, "shutdown", None)
            if callable(shutdown):
                shutdown()
            else:
                self._window.hide()
        self._sessions.shutdown()

    def diagnostic_summary(self) -> dict[str, object]:
        if self._window is None:
            return {
                "backend": "PyAV",
                "backend_version": "18.0.0",
                "state": "not_initialized",
            }
        summary = getattr(self._window, "diagnostic_summary", None)
        if callable(summary):
            return dict(summary())
        return {"state": "unavailable"}


def _format_us(value: int) -> str:
    total_ms = max(0, int(value)) // 1000
    minutes, remainder = divmod(total_ms, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def _format_zoom(value: float) -> str:
    percent = max(0.0, float(value) * 100)
    if percent < 10:
        return f"{percent:.1f}%"
    return f"{round(percent)}%"


def _create_playback_runtime(project: Any, timeline: Any) -> PlaybackRuntime:
    return PlaybackRuntime(project, timeline, PyAVPlaybackBackend())


def _required_splitter_widget(
    splitter: QSplitter,
    index: int,
) -> QWidget:
    widget = splitter.widget(index)
    if widget is None:
        raise RuntimeError(f"splitter widget is missing at index {index}")
    return widget


_EDITOR_STYLESHEET = """
QMainWindow#quickrecTimelineEditor {
    background: #F7F9FC;
}
QFrame#timelineCommandBar {
    background: #FFFFFF;
    border-bottom: 1px solid #D8DEE8;
}
QFrame#timelineSaveErrorBar {
    background: #FFF4F2;
    border-bottom: 1px solid #F0B8B0;
}
QLabel#timelineSaveErrorMessage {
    color: #8F2D23;
    font-weight: 600;
}
QLabel#timelineProjectName {
    color: #172033;
    font-size: 15px;
    font-weight: 700;
}
QLabel#timelineRecordingStatus {
    color: #A66309;
    background: #FFF3D6;
    border: 1px solid #E6C36A;
    border-radius: 4px;
    padding: 6px 9px;
}
QLabel#timelineRippleMode {
    color: #1457D9;
    background: #E8F0FF;
    border: 1px solid #B8CDF8;
    border-radius: 4px;
    padding: 6px 9px;
    font-weight: 600;
}
QFrame#timelineMaterialRail,
QFrame#timelinePreviewPanel,
QFrame#timelinePanel {
    background: #FFFFFF;
    border: 1px solid #D8DEE8;
}
QLabel#timelinePreviewSurface {
    color: #CAD4E2;
    background: #171C25;
    border: 0;
}
QLabel#timelineCanvasPlaceholder {
    color: #526077;
    background: #F1F4F8;
    border: 1px solid #D8DEE8;
    padding: 18px;
}
QFrame#clipInspector {
    background: #FFFFFF;
    border: 1px solid #C2CAD7;
    border-radius: 6px;
}
QFrame#clipInspectorImpact {
    background: #E8F0FF;
    border: 1px solid #B8CDF8;
    border-radius: 5px;
}
QLabel#clipInspectorValidation {
    color: #526077;
}
QFrame#timelineImpactConflict {
    background: #FDECEA;
    border: 1px solid #E8AAA5;
    border-radius: 5px;
}
QFrame#timelineImpactSafe {
    background: #E6F5ED;
    border: 1px solid #A9D8BF;
    border-radius: 5px;
}
"""
