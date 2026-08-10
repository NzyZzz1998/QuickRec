"""
QuickRec 主程序入口

初始化所有模块，启动应用。

v1.1 新增：
- _AreaBridge 信号桥（区域选择器）
- _HotkeyBridge.area_requested 信号（区域录制快捷键）
- 区域录制流程
- 托盘回调扩展（start_fullscreen / start_region / pause_resume / stop）
- Toast 通知增强
- 工具栏结果条

v1.2 新增：
- _WindowBridge / _WindowLostBridge 信号桥（窗口选择器、窗口丢失）
- _HotkeyBridge.window_requested 信号（窗口录制快捷键）
- 窗口录制流程
- 倒计时流程
- 鼠标高亮控制
- 窗口边框高亮生命周期管理
"""

import ctypes
import logging
import os
import platform
import sys
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QLineEdit, QMessageBox

from config import ConfigManager
from exporting.diagnostics import build_export_diagnostic_summary
from exporting.exit_coordinator import (
    ExportExitAction,
    ExportExitCoordinator,
)
from exporting.ingestion import ExportIngestionCoordinator
from exporting.models import ExportStage
from exporting.plan_builder import ExportPlanBuilder
from exporting.queue_service import ExportQueueService
from exporting.queue_store import ExportQueueStore, resolve_export_queue_file
from hotkey.hotkey_manager import HotkeyManager
from recorder.events import RecordingEvent, RecordingEventType
from recorder.recorder_manager import RecorderManager, RecorderState, RecordMode
from recorder.workflow import RecordingWorkflow
from services.capture_capability_runtime import CaptureCapabilityRuntime
from services.material_ingestion import (
    IngestionResult,
    MaterialIngestionCoordinator,
    StartupRetrySummary,
)
from services.media_operation_guard import MediaOperationGuard
from services.pending_recordings import PendingRecordingService
from services.project_library import ProjectLibraryService
from services.project_materials import ProjectMaterialQueryService
from services.project_recording import ProjectRecordingCoordinator
from services.recording_library import MigrationResult, RecordingLibraryService
from services.single_instance import FULL_PRODUCT_ID, SingleInstanceGuard
from services.thumbnail_coordinator import ThumbnailCoordinator
from services.thumbnail_service import ThumbnailService
from services.timeline_session import TimelineSession, TimelineSessionRegistry
from services.workbench_navigation import WorkbenchNavigationController
from ui.area_selector import AreaSelector
from ui.capture_self_test_dialog import CaptureSelfTestDialog
from ui.click_highlighter import ClickHighlighter
from ui.export_dialogs import ExportConfigDialog, ExportDialogContext
from ui.export_page import ExportPage
from ui.material_library_dialog import MaterialLibraryDialog
from ui.project_page import ProjectPage
from ui.qt_localization import install_qt_zh_cn
from ui.settings_dialog import SettingsDialog
from ui.timeline_editor_window import (
    TimelineEditorCoordinator,
    TimelineEditorWindow,
)
from ui.toolbar import RecordingToolbar
from ui.toolbar_placement import select_target_screen_index
from ui.tray_icon import TrayIcon
from ui.window_highlighter import WindowHighlighter
from ui.window_selector import WindowSelector
from ui.workbench_pages import DiagnosticPage, RecordingPage
from ui.workbench_window import WorkbenchCoordinator, WorkbenchPage, WorkbenchWindow
from utils.diagnostics import (
    DiagnosticSnapshot,
    export_diagnostic_file,
    format_snapshot_text,
    initialize_file_logging,
    open_diagnostic_dir,
    read_recent_log_lines,
    resolve_diagnostic_dir,
)
from utils.disk_checker import DiskChecker, show_disk_warning
from utils.media_metadata import resolve_ffmpeg_path
from utils.pending_recording_store import resolve_pending_file
from utils.project_store import resolve_project_index
from utils.recording_library_store import resolve_library_file
from utils.thumbnail_cache import ThumbnailCacheStore, resolve_thumbnail_cache_root
from version import APP_VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("QuickRec")


def _enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class _SavedBridge(QObject):
    """将编码线程的回调安全转发到 Qt 主线程"""
    saved = pyqtSignal(str)


class _HotkeyBridge(QObject):
    """将 pynput 线程的快捷键回调安全转发到 Qt 主线程"""
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    area_requested = pyqtSignal()
    window_requested = pyqtSignal()


class _AreaBridge(QObject):
    """区域选择器信号桥"""
    region_selected = pyqtSignal(int, int, int, int)
    cancelled = pyqtSignal()


class _WindowBridge(QObject):
    """窗口选择器信号桥"""
    window_selected = pyqtSignal(int, str)  # (hwnd, title)
    cancelled = pyqtSignal()


class _WindowLostBridge(QObject):
    """窗口丢失信号桥（录制线程 → Qt 主线程）"""
    window_lost = pyqtSignal(str)  # "closed" / "minimized"


class _MigrationBridge(QObject):
    initial_migration_finished = pyqtSignal(object)


class _PendingRetryBridge(QObject):
    finished = pyqtSignal(object)


class _ExportBridge(QObject):
    succeeded = pyqtSignal(object)
    terminal = pyqtSignal(object)


class QuickRecApp:
    """QuickRec 应用主类"""

    def __init__(
        self,
        *,
        instance_guard: SingleInstanceGuard | None = None,
    ):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setStyle("Fusion")
        self._qt_translator = install_qt_zh_cn(self._app)
        self._instance_guard = instance_guard
        self._instance_activation_timer: QTimer | None = None
        if instance_guard is not None:
            self._instance_activation_timer = QTimer(self._app)
            self._instance_activation_timer.setInterval(250)
            self._instance_activation_timer.timeout.connect(
                self._poll_instance_activation
            )
            self._instance_activation_timer.start()

        # 初始化模块
        self._config = ConfigManager()
        self._media_operation_guard = MediaOperationGuard()
        log_result = initialize_file_logging(self._config, logger)
        if not log_result.ok:
            logger.warning(f"diagnostic file logging unavailable: {log_result.error}")
        self._recorder = RecorderManager(self._config)
        self._capture_capability = CaptureCapabilityRuntime(
            save_path=lambda: str(self._config.get("save_path", "")),
            ffmpeg_path=resolve_ffmpeg_path(),
        )
        self._workflow = RecordingWorkflow(self._recorder)
        self._workflow.subscribe(self._on_recording_event)
        self._recorder.set_event_handler(self._workflow.handle_event)
        self._hotkey = HotkeyManager()
        self._toolbar = None
        self._library_service = RecordingLibraryService(resolve_library_file())
        self._project_service = ProjectLibraryService(
            resolve_project_index(),
            default_root=self._config.get("project_root_path", ""),
        )
        self._pending_service = PendingRecordingService(resolve_pending_file())
        self._ingestion_coordinator = MaterialIngestionCoordinator(
            self._library_service,
            self._pending_service,
        )
        self._project_recording_coordinator = ProjectRecordingCoordinator(
            self._project_service,
            self._library_service,
        )
        self._ensure_export_runtime()
        self._export_page = None
        self._export_dialog = None
        self._ensure_thumbnail_runtime()
        self._pending_ids_by_output: dict[str, str] = {}
        self._material_library_dialog = None
        self._project_page = None
        self._recording_page = None
        self._settings_page = None
        self._diagnostic_page = None
        self._recording_source: str | None = None
        self._recording_mode = ""
        self._active_project_recording_id: str | None = None
        self._last_save_path = str(self._config.get("save_path", ""))
        self._workbench = WorkbenchCoordinator(self._create_workbench_window)
        self._workbench_navigation = self._create_workbench_navigation()
        self._timeline_sessions = TimelineSessionRegistry(
            lambda project_id: TimelineSession(
                self._project_service,
                project_id,
            )
        )
        self._timeline_editor = TimelineEditorCoordinator(
            self._create_timeline_editor_window,
            self._timeline_sessions,
        )
        self._initial_migration_result: MigrationResult | None = None
        self._migration_thread: threading.Thread | None = None
        self._pending_retry_thread: threading.Thread | None = None
        self._config_saved_pending = False

        # v1.2 新增模块
        self._click_highlighter = ClickHighlighter()
        self._window_highlighter = None
        self._window_selector = None

        # 编码完成信号桥
        self._saved_bridge = _SavedBridge()
        self._saved_bridge.saved.connect(self._handle_saved)
        self._migration_bridge = _MigrationBridge()
        self._migration_bridge.initial_migration_finished.connect(
            self._on_initial_migration_finished
        )
        self._pending_retry_bridge = _PendingRetryBridge()
        self._pending_retry_bridge.finished.connect(self._on_pending_retry_finished)
        self._export_bridge = _ExportBridge()
        self._export_bridge.succeeded.connect(self._on_export_succeeded)
        self._export_bridge.terminal.connect(self._on_export_terminal)
        self._export_queue_service.subscribe_succeeded(
            self._export_bridge.succeeded.emit
        )
        self._export_queue_service.subscribe_terminal(
            self._export_bridge.terminal.emit
        )
        self._export_ingestion_coordinator.recover_pending()

        # 快捷键信号桥
        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.start_requested.connect(
            lambda: self._run_hotkey_action(
                lambda: self._on_start_fullscreen(source="hotkey")
            )
        )
        self._hotkey_bridge.stop_requested.connect(
            lambda: self._run_hotkey_action(self._on_stop_recording)
        )
        self._hotkey_bridge.pause_requested.connect(
            lambda: self._run_hotkey_action(self._on_pause_resume)
        )
        self._hotkey_bridge.area_requested.connect(
            lambda: self._run_hotkey_action(
                lambda: self._on_start_region(source="hotkey")
            )
        )
        self._hotkey_bridge.window_requested.connect(
            lambda: self._run_hotkey_action(
                lambda: self._on_start_window(source="hotkey")
            )
        )

        # 区域选择器信号桥
        self._area_bridge = _AreaBridge()
        self._area_bridge.region_selected.connect(self._on_region_selected)
        self._area_bridge.cancelled.connect(self._on_selection_cancelled)

        # 窗口选择器信号桥
        self._window_bridge = _WindowBridge()
        self._window_bridge.window_selected.connect(self._on_window_selected)
        self._window_bridge.cancelled.connect(self._on_window_cancelled)

        # 窗口丢失信号桥
        self._window_lost_bridge = _WindowLostBridge()
        self._window_lost_bridge.window_lost.connect(self._on_window_lost)
        self._recorder.connect_window_lost(self._window_lost_bridge.window_lost.emit)

        # 初始化托盘
        self._tray = TrayIcon(
            config=self._config,
            callbacks={
                "open_workbench": lambda: self._show_workbench(),
                "start_fullscreen": lambda: self._on_start_fullscreen(source="tray"),
                "start_region": lambda: self._on_start_region(source="tray"),
                "start_window": lambda: self._on_start_window(source="tray"),
                "pause_resume": self._on_pause_resume,
                "stop": self._on_stop_recording,
                "settings": lambda: self._show_workbench(WorkbenchPage.SETTINGS),
                "material_library": lambda: self._show_workbench(WorkbenchPage.MATERIALS),
                "diagnostics": lambda: self._show_workbench(WorkbenchPage.DIAGNOSTICS),
                "copy_diagnostic": self._on_copy_diagnostic_info,
                "open_diagnostic_dir": self._on_open_diagnostic_dir,
                "export_diagnostic": self._on_export_diagnostic_file,
                "exit": self._on_exit,
            }
        )

        # 绑定快捷键
        self._setup_hotkeys()
        self._hotkey.start_listening()

    def _ensure_export_runtime(self) -> None:
        if getattr(self, "_export_queue_service", None) is not None:
            return
        operation_guard = getattr(self, "_media_operation_guard", None)
        if operation_guard is None:
            operation_guard = MediaOperationGuard()
            self._media_operation_guard = operation_guard
        queue_path = (
            resolve_export_queue_file()
            if hasattr(self, "_app")
            else Path(self._config.config_path).parent
            / "Exports"
            / "queue.json"
        )
        self._export_queue_store = ExportQueueStore(queue_path)
        self._export_queue_service = ExportQueueService(
            self._export_queue_store,
            operation_guard=operation_guard,
        )
        export_queue_result = self._export_queue_service.initialize()
        if not export_queue_result.ok:
            logger.error(
                "export queue initialization failed: %s",
                export_queue_result.message,
            )
        elif export_queue_result.read_only:
            logger.warning(
                "export queue opened read-only: %s",
                export_queue_result.message,
            )
        self._export_ingestion_coordinator = ExportIngestionCoordinator(
            self._export_queue_service,
            self._library_service,
        )
        self._export_plan_builder = ExportPlanBuilder()
        self._export_exit_coordinator = ExportExitCoordinator(
            self._export_queue_service
        )

    def _ensure_thumbnail_runtime(self) -> None:
        if getattr(self, "_thumbnail_coordinator", None) is not None:
            return
        cache_root = (
            resolve_thumbnail_cache_root()
            if hasattr(self, "_app")
            else Path(self._config.config_path).parent
            / "ThumbnailCache"
            / "v1"
        )
        self._thumbnail_cache = ThumbnailCacheStore(
            cache_root
        )
        self._thumbnail_service = ThumbnailService(self._thumbnail_cache)
        self._thumbnail_coordinator = ThumbnailCoordinator(
            self._thumbnail_service,
            max_workers=2,
            max_retries=1,
        )
        self._project_material_query = ProjectMaterialQueryService(
            self._thumbnail_cache,
            coordinator=self._thumbnail_coordinator,
        )
        prune = self._thumbnail_cache.prune()
        if not prune.ok:
            logger.warning("thumbnail cache prune failed: %s", prune.error)

    def _create_workbench_window(self) -> WorkbenchWindow:
        self._ensure_export_runtime()
        self._ensure_thumbnail_runtime()
        self._recording_page = RecordingPage(
            self._config,
            availability_provider=self._recording_operation_availability,
        )
        self._material_library_dialog = MaterialLibraryDialog(
            self._library_service,
            pending_service=self._pending_service,
            ingestion_coordinator=self._ingestion_coordinator,
            current_save_dir=self._config.get("save_path", ""),
            embedded=True,
        )
        self._project_page = ProjectPage(
            self._project_service,
            self._library_service,
            material_query=self._project_material_query,
            thumbnail_coordinator=self._thumbnail_coordinator,
            timeline_command_provider=lambda project_id: (
                self._timeline_sessions.get(project_id).commands
            ),
            editing_fps_provider=lambda: self._config.get("fps", 30),
        )
        self._settings_page = SettingsDialog(
            self._config,
            embedded=True,
            capture_capability=getattr(self, "_capture_capability", None),
        )
        self._diagnostic_page = DiagnosticPage(self._config)
        self._export_page = ExportPage(
            self._export_queue_service,
            ingestion_coordinator=self._export_ingestion_coordinator,
            project_linker=getattr(self, "_project_recording_coordinator", None),
        )
        capability_runtime = getattr(self, "_capture_capability", None)
        if capability_runtime is not None:
            capability_context = capability_runtime.diagnostic_context()
            if capability_context["ready"]:
                capability_text = (
                    f"已通过 · 平均 {capability_context['average_fps']} FPS · "
                    f"最低每秒 {capability_context['minimum_one_second_fps']} FPS · "
                    f"{capability_context['checked_at']}"
                )
            else:
                capability_text = f"未就绪 · {capability_context['reason']}"
            self._diagnostic_page.set_capture_capability_status(capability_text)

        self._recording_page.start_fullscreen_requested.connect(
            lambda: self._on_start_fullscreen(source="workbench")
        )
        self._recording_page.start_region_requested.connect(
            lambda: self._on_start_region(source="workbench")
        )
        self._recording_page.start_window_requested.connect(
            lambda: self._on_start_window(source="workbench")
        )
        self._recording_page.open_settings_requested.connect(
            lambda: self._show_workbench(WorkbenchPage.SETTINGS)
        )
        self._recording_page.open_material_requested.connect(
            lambda: self._show_workbench(WorkbenchPage.MATERIALS)
        )
        self._recording_page.open_file_requested.connect(self._on_open_file)
        self._recording_page.open_folder_requested.connect(self._on_open_folder)
        self._recording_page.retry_material_requested.connect(self._retry_material_item)
        self._material_library_dialog.add_to_project_requested.connect(
            self._on_material_add_to_project
        )
        self._material_library_dialog.pending_retry_succeeded.connect(
            self._on_material_pending_retry_succeeded
        )
        self._project_page.start_recording_requested.connect(
            self._on_start_project_recording
        )
        self._project_page.open_diagnostics_requested.connect(
            lambda: self._show_workbench(WorkbenchPage.DIAGNOSTICS)
        )
        self._project_page.open_material_requested.connect(self._on_open_file)
        self._project_page.open_material_folder_requested.connect(
            self._on_open_folder
        )
        self._project_page.show_material_in_library_requested.connect(
            self._show_project_material_in_library
        )
        self._project_page.open_timeline_requested.connect(
            self._show_timeline_editor
        )
        self._project_page.project_content_changed.connect(
            self._timeline_editor.refresh_project
        )
        self._export_page.new_export_requested.connect(
            self._show_export_dialog
        )
        self._export_page.open_diagnostics_requested.connect(
            lambda _job_id: self._show_workbench(WorkbenchPage.DIAGNOSTICS)
        )
        self._export_page.show_material_requested.connect(
            self._show_export_material
        )
        self._material_library_dialog.return_to_project_requested.connect(
            self._return_to_project_material
        )
        self._material_library_dialog.material_relinked.connect(
            self._on_material_relinked
        )

        self._settings_page.config_saved.connect(self._on_workbench_config_saved)
        self._settings_page.open_capture_diagnostics_requested.connect(
            lambda: self._show_workbench(WorkbenchPage.DIAGNOSTICS)
        )
        self._diagnostic_page.config_saved.connect(self._on_workbench_config_saved)
        self._diagnostic_page.copy_diagnostic_requested.connect(
            lambda path: self._on_copy_diagnostic_info(path, self._diagnostic_page)
        )
        self._diagnostic_page.open_diagnostic_dir_requested.connect(
            lambda path: self._on_open_diagnostic_dir(path, self._diagnostic_page)
        )
        self._diagnostic_page.export_diagnostic_requested.connect(
            lambda path: self._on_export_diagnostic_file(path, self._diagnostic_page)
        )

        window = WorkbenchWindow(
            pages={
                WorkbenchPage.RECORDING: self._recording_page,
                WorkbenchPage.MATERIALS: self._material_library_dialog,
                WorkbenchPage.PROJECTS: self._project_page,
                WorkbenchPage.EXPORTS: self._export_page,
                WorkbenchPage.SETTINGS: self._settings_page,
                WorkbenchPage.DIAGNOSTICS: self._diagnostic_page,
            },
            saved_geometry=self._config.get("workbench_geometry", {}),
        )
        window.geometry_changed.connect(self._save_workbench_geometry)
        window.page_changed.connect(self._on_workbench_page_changed)
        if self._initial_migration_result is not None:
            self._material_library_dialog.show_migration_result(
                self._initial_migration_result
            )
        self._sync_workbench_recording_state()
        self._sync_recording_operation_availability()
        return window

    def _create_timeline_editor_window(self) -> TimelineEditorWindow:
        window = TimelineEditorWindow(
            material_provider=self._describe_timeline_materials,
        )
        window.return_to_project_requested.connect(
            self._return_from_timeline_editor
        )
        window.open_material_workspace_requested.connect(
            self._open_materials_from_timeline_editor
        )
        window.open_diagnostics_requested.connect(
            self._open_diagnostics_from_timeline_editor
        )
        window.export_requested.connect(self._show_export_dialog)
        window.start_recording_requested.connect(
            self._on_start_timeline_recording
        )
        window.hidden_requested.connect(self._timeline_sessions.close_current)
        return window

    def _resolve_export_project_id(
        self,
        preferred_project_id: str | None = None,
    ) -> str | None:
        if preferred_project_id:
            return str(preferred_project_id)
        timeline_sessions = getattr(self, "_timeline_sessions", None)
        current_session = (
            timeline_sessions.current_session
            if timeline_sessions is not None
            else None
        )
        if current_session is not None:
            return str(current_session.project_id)
        project_page = getattr(self, "_project_page", None)
        selected = getattr(project_page, "selected_project_id", None)
        if selected:
            return str(selected)
        entries = self._project_service.list_entries()
        active = next(
            (
                entry
                for entry in entries
                if not getattr(entry, "archived_at", None)
            ),
            None,
        )
        return str(active.project_id) if active is not None else None

    def _show_export_dialog(
        self,
        project_id: str | None = None,
    ) -> ExportConfigDialog | None:
        target_id = self._resolve_export_project_id(project_id)
        if target_id is None:
            self._tray.show_notification("请先创建或打开一个项目")
            return None
        entry = self._project_service.get_entry(target_id)
        loaded = self._project_service.get_project(target_id)
        if entry is None or not loaded.ok or loaded.project is None:
            self._tray.show_notification("项目不可用，无法创建导出任务")
            return None

        current_session = getattr(
            getattr(self, "_timeline_sessions", None),
            "current_session",
            None,
        )
        commands = (
            current_session.commands
            if current_session is not None
            and str(current_session.project_id) == target_id
            else None
        )
        save_pending = bool(
            getattr(commands, "has_pending_save", False)
        )
        external_conflict = (
            str(getattr(commands, "pending_save_stage", ""))
            == "external_conflict"
        )
        defaults = self._config.get_export_defaults(
            target_id,
            project_path=entry.file_path,
        )
        context = ExportDialogContext(
            project_id=target_id,
            project_name=loaded.project.name,
            project_path=str(entry.file_path),
            output_directory=defaults.directory,
            project_saved=True,
            save_pending=save_pending,
            external_conflict=external_conflict,
            incomplete_job_count=sum(
                job.is_incomplete
                for job in self._export_queue_service.state.jobs
            ),
        )
        dialog = ExportConfigDialog(
            context,
            plan_builder=self._export_plan_builder,
            queue_service=self._export_queue_service,
            defaults=defaults.to_dict(),
            parent=None,
        )
        dialog.queued.connect(self._on_export_queued)
        dialog.finished.connect(
            lambda _result, current=dialog: self._release_export_dialog(
                current
            )
        )
        self._export_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def _release_export_dialog(self, dialog: ExportConfigDialog) -> None:
        if self._export_dialog is dialog:
            self._export_dialog = None

    def _on_export_queued(self, job_id: str) -> None:
        page = getattr(self, "_export_page", None)
        if page is not None:
            page.refresh()
            page.select_job(job_id)
        self._tray.show_notification("导出任务已加入队列")

    def _on_export_succeeded(self, job) -> None:
        plan = job.plan
        saved = self._config.remember_successful_export(
            plan.project.project_id,
            width=plan.output.width,
            height=plan.output.height,
            fps=plan.output.fps,
            directory=plan.output.directory,
        )
        if not saved.ok:
            logger.warning(
                "export preferences save failed: stage=%s message=%s",
                saved.stage,
                saved.message,
            )
        page = getattr(self, "_export_page", None)
        if page is not None:
            page.refresh()
        tray = getattr(self, "_tray", None)
        if tray is not None:
            tray.show_notification(
                f"导出已完成：{Path(job.output_path or plan.output.target_path).name}"
            )

    def _on_export_terminal(self, job) -> None:
        page = getattr(self, "_export_page", None)
        if page is not None:
            page.refresh()
        tray = getattr(self, "_tray", None)
        if tray is None:
            return
        if job.status == ExportStage.FAILED:
            tray.show_notification("导出失败，请在导出页查看诊断并重试")
        elif job.status == ExportStage.INTERRUPTED:
            tray.show_notification("导出已中断，可在导出页继续处理")

    def _show_export_material(self, material_id: str) -> None:
        self._show_workbench(WorkbenchPage.MATERIALS)
        page = getattr(self, "_material_library_dialog", None)
        if page is not None:
            found = page.focus_material(material_id)
            if not found:
                logger.warning(
                    "export material not found in global library: material_id=%s",
                    material_id,
                )

    def _describe_timeline_materials(self, project):
        loaded = self._library_service.load()
        library_items = loaded.items if loaded.ok else []
        return self._project_material_query.describe(project, library_items)

    def _save_workbench_geometry(self, geometry: dict[str, object]) -> None:
        candidate = self._config.snapshot()
        candidate["workbench_geometry"] = dict(geometry)
        result = self._config.save_candidate(candidate)
        if not result.ok:
            logger.warning(
                "workbench geometry save failed: stage=%s error=%s",
                result.stage,
                result.message,
            )

    def _create_workbench_navigation(
        self,
    ) -> WorkbenchNavigationController[WorkbenchWindow]:
        page_attributes = {
            WorkbenchPage.RECORDING.value: "_recording_page",
            WorkbenchPage.MATERIALS.value: "_material_library_dialog",
            WorkbenchPage.PROJECTS.value: "_project_page",
            WorkbenchPage.EXPORTS.value: "_export_page",
            WorkbenchPage.SETTINGS.value: "_settings_page",
            WorkbenchPage.DIAGNOSTICS.value: "_diagnostic_page",
        }

        def resolve_page(page_key: str) -> object | None:
            attribute = page_attributes.get(page_key)
            return getattr(self, attribute, None) if attribute else None

        def open_window(page: object | None) -> WorkbenchWindow:
            workbench = getattr(self, "_workbench", None)
            if workbench is None:
                raise RuntimeError("workbench coordinator is not initialized")
            return workbench.open(page)

        return WorkbenchNavigationController(
            open_window=open_window,
            resolve_page=resolve_page,
            sync_runtime=self._sync_workbench_recording_state,
            is_recording_active=lambda: (
                self._workflow.get_state() != RecorderState.IDLE
            ),
        )

    def _ensure_workbench_navigation(
        self,
    ) -> WorkbenchNavigationController[WorkbenchWindow]:
        navigation = getattr(self, "_workbench_navigation", None)
        if navigation is None:
            navigation = self._create_workbench_navigation()
            self._workbench_navigation = navigation
        return navigation

    def _show_workbench(self, page: WorkbenchPage | None = None) -> WorkbenchWindow:
        return self._ensure_workbench_navigation().open(page)

    def _poll_instance_activation(self) -> None:
        guard = getattr(self, "_instance_guard", None)
        if guard is None:
            return
        try:
            requested = guard.consume_activation_request()
        except OSError:
            logger.exception("single-instance activation polling failed")
            return
        if requested:
            logger.info("secondary launch requested workbench activation")
            self._show_workbench()

    def _show_timeline_editor(self, project_id: str):
        return self._timeline_editor.open(project_id)

    def _return_from_timeline_editor(self, project_id: str) -> None:
        self._show_workbench(WorkbenchPage.PROJECTS)
        project_page = getattr(self, "_project_page", None)
        focus = getattr(project_page, "focus_project", None)
        if callable(focus):
            focus(project_id)

    def _open_materials_from_timeline_editor(self, _project_id: str) -> None:
        self._show_workbench(WorkbenchPage.MATERIALS)

    def _open_diagnostics_from_timeline_editor(
        self,
        _project_id: str,
    ) -> None:
        self._show_workbench(WorkbenchPage.DIAGNOSTICS)

    def _on_material_relinked(self, material_id: str) -> None:
        project_page = getattr(self, "_project_page", None)
        if project_page is not None:
            project_page.reload()
        session = self._timeline_sessions.current_session
        if session is None:
            return
        if any(
            item.material_id == material_id
            for item in session.project.materials
        ):
            self._timeline_editor.refresh_project(session.project_id)

    def _on_workbench_page_changed(self, page: WorkbenchPage) -> None:
        self._ensure_workbench_navigation().page_changed(page)

    def _on_workbench_config_saved(self) -> None:
        current_save_path = str(self._config.get("save_path", ""))
        self._hotkey.stop_listening()
        self._hotkey.unregister_all()
        self._setup_hotkeys()
        self._hotkey.start_listening()
        if self._recording_page is not None:
            self._recording_page.refresh_summary()
        if self._material_library_dialog is not None:
            self._material_library_dialog.set_current_save_dir(current_save_path)
        if self._project_service is not None:
            project_root = str(self._config.get("project_root_path", "") or "")
            if project_root:
                self._project_service.default_root = Path(project_root)
        if current_save_path and current_save_path != self._last_save_path:
            self._handle_save_path_changed(current_save_path)
        self._last_save_path = current_save_path

    def _on_material_add_to_project(self, material) -> None:
        project_page = getattr(self, "_project_page", None)
        if project_page is None:
            self._show_workbench(WorkbenchPage.PROJECTS)
            project_page = self._project_page
        if project_page is not None:
            self._show_workbench(WorkbenchPage.PROJECTS)
            project_page.prompt_add_material(material)

    def _on_material_pending_retry_succeeded(self, result: IngestionResult) -> None:
        if not result.project_id or not result.material_id:
            return
        linked = self._project_recording_coordinator.link_material(
            result.project_id,
            result.material_id,
        )
        if self._project_page is not None:
            self._project_page.reload()
        if self._material_library_dialog is not None:
            self._material_library_dialog.show_pending_project_link_result(
                ok=linked.ok,
                error=linked.error,
            )
        if not linked.ok:
            logger.warning(
                "pending project link failed after material library retry: "
                "project_id=%s material_id=%s stage=%s error=%s",
                result.project_id,
                result.material_id,
                linked.stage,
                linked.error,
            )

    def _show_project_material_in_library(
        self,
        project_id: str,
        material_id: str,
    ) -> None:
        loaded = self._project_service.get_project(project_id)
        project_name = (
            loaded.project.name
            if loaded.ok and loaded.project is not None
            else project_id
        )
        self._show_workbench(WorkbenchPage.MATERIALS)
        if self._material_library_dialog is not None:
            found = self._material_library_dialog.focus_material(
                material_id,
                source_project_id=project_id,
                source_project_name=project_name,
            )
            if not found:
                logger.warning(
                    "project material not found in global library: "
                    "project_id=%s material_id=%s",
                    project_id,
                    material_id,
                )

    def _return_to_project_material(
        self,
        project_id: str,
        material_id: str,
    ) -> None:
        self._show_workbench(WorkbenchPage.PROJECTS)
        if self._project_page is not None:
            self._project_page.focus_project_material(
                project_id,
                material_id,
            )

    def _on_start_project_recording(self, project_id: str, mode: str) -> None:
        if mode not in {"fullscreen", "region", "window"}:
            QMessageBox.warning(
                None,
                "无法开始项目录制",
                "不支持当前录制模式，请重新选择。",
            )
            return
        if not self._validate_project_recording_target(project_id):
            return
        self._active_project_recording_id = project_id
        if mode == "fullscreen":
            self._on_start_fullscreen(source="project")
        elif mode == "region":
            self._on_start_region(source="project")
        elif mode == "window":
            self._on_start_window(source="project")

    def _validate_project_recording_target(self, project_id: str) -> bool:
        loaded = self._project_service.get_project(project_id)
        if (
            not loaded.ok
            or loaded.project is None
            or loaded.project.archived_at
            or loaded.status != "available"
        ):
            QMessageBox.warning(
                None,
                "无法开始项目录制",
                "项目当前不可写，请刷新项目状态后重试。",
            )
            return False
        return True

    def _on_start_timeline_recording(self, project_id: str, mode: str) -> None:
        if mode not in {"fullscreen", "region", "window"}:
            QMessageBox.warning(
                None,
                "无法开始项目录制",
                "不支持当前录制模式，请重新选择。",
            )
            return
        if not self._validate_project_recording_target(project_id):
            return
        self._active_project_recording_id = project_id
        if mode == "fullscreen":
            self._on_start_fullscreen(source="timeline")
        elif mode == "region":
            self._on_start_region(source="timeline")
        elif mode == "window":
            self._on_start_window(source="timeline")

    def _sync_workbench_recording_state(self) -> None:
        page = getattr(self, "_recording_page", None)
        workflow = getattr(self, "_workflow", None)
        state = (
            workflow.get_state()
            if workflow is not None
            else RecorderState.IDLE
        )
        state_name = {
            RecorderState.IDLE: "idle",
            RecorderState.RECORDING: "recording",
            RecorderState.PAUSED: "paused",
            RecorderState.SAVING: "saving",
        }.get(state, "idle")
        thumbnail_coordinator = getattr(
            self,
            "_thumbnail_coordinator",
            None,
        )
        if thumbnail_coordinator is not None:
            preview_pause_required = (
                state != RecorderState.IDLE
                or getattr(self, "_recording_source", None) is not None
            )
            thumbnail_coordinator.set_execution_paused(
                preview_pause_required,
                reason=f"recorder_{state_name}",
            )
        mode = getattr(getattr(self, "_recorder", None), "get_mode", lambda: "")()
        if page is not None:
            page.set_recording_state(
                state_name,
                mode=(
                    ""
                    if state == RecorderState.IDLE
                    else getattr(mode, "value", str(mode or ""))
                ),
            )
        workbench = getattr(self, "_workbench", None)
        window = getattr(workbench, "window", None)
        if window is not None:
            window.set_runtime_status(state_name)
        settings = getattr(self, "_settings_page", None)
        if settings is not None:
            settings.set_recording_active(state != RecorderState.IDLE)
        timeline_editor = getattr(self, "_timeline_editor", None)
        if timeline_editor is not None:
            timeline_editor.set_recording_active(state != RecorderState.IDLE)

    def _begin_recording_request(self, source: str, mode: str) -> None:
        self._recording_source = source
        self._recording_mode = mode
        thumbnail_coordinator = getattr(
            self,
            "_thumbnail_coordinator",
            None,
        )
        if thumbnail_coordinator is not None:
            thumbnail_coordinator.set_execution_paused(
                True,
                reason=f"recording_request_{mode}",
            )
        page = getattr(self, "_recording_page", None)
        if page is not None:
            page.clear_result()
            page.set_recording_state(
                "selecting" if mode in {"region", "window"} else "starting",
                mode=mode,
            )
        if source in {"workbench", "project", "timeline"}:
            self._workbench.hide()
        if source == "timeline":
            self._timeline_editor.suspend()

    def _set_recording_request_state(self, state: str) -> None:
        page = getattr(self, "_recording_page", None)
        if page is not None:
            page.set_recording_state(state, mode=getattr(self, "_recording_mode", ""))
        workbench = getattr(self, "_workbench", None)
        window = getattr(workbench, "window", None)
        if window is not None:
            window.set_runtime_status(state)
        settings = getattr(self, "_settings_page", None)
        if settings is not None:
            settings.set_recording_active(state != "idle")
        timeline_editor = getattr(self, "_timeline_editor", None)
        if timeline_editor is not None:
            timeline_editor.set_recording_active(state != "idle")

    def _finish_recording_request(self, *, restore_workbench: bool) -> None:
        source = getattr(self, "_recording_source", None)
        self._release_recording_operation()
        self._recording_source = None
        self._recording_mode = ""
        thumbnail_coordinator = getattr(
            self,
            "_thumbnail_coordinator",
            None,
        )
        if thumbnail_coordinator is not None:
            thumbnail_coordinator.set_execution_paused(
                False,
                reason="recording_request_finished",
            )
        if restore_workbench and source in {"workbench", "project", "timeline"}:
            if source == "timeline":
                project_id = getattr(
                    self,
                    "_active_project_recording_id",
                    None,
                )
                self._set_recording_request_state("idle")
                if project_id is not None:
                    self._timeline_editor.open(project_id)
                self._active_project_recording_id = None
                return
            target_page = (
                WorkbenchPage.PROJECTS
                if source == "project"
                else WorkbenchPage.RECORDING
            )
            self._show_workbench(target_page)
        else:
            self._set_recording_request_state("idle")
        if source in {"project", "timeline"}:
            self._active_project_recording_id = None

    def run(self):
        """启动应用"""
        self._tray.show()
        self._start_initial_migration()
        self._start_pending_retry()
        logger.info("QuickRec 已启动")
        return self._app.exec_()

    def _start_pending_retry(self) -> None:
        if self._pending_retry_thread is not None and self._pending_retry_thread.is_alive():
            return

        def retry_pending() -> None:
            save_path = self._config.get("save_path", "")
            summary = self._ingestion_coordinator.retry_startup(save_path)
            self._pending_retry_bridge.finished.emit(summary)

        self._pending_retry_thread = threading.Thread(
            target=retry_pending,
            name="QuickRecPendingRetry",
            daemon=True,
        )
        self._pending_retry_thread.start()

    def _on_pending_retry_finished(self, summary: StartupRetrySummary) -> None:
        project_recovered = 0
        for result in summary.recovered:
            if result.project_id and result.material_id:
                linked = self._project_recording_coordinator.link_material(
                    result.project_id,
                    result.material_id,
                )
                project_recovered += int(linked.ok)
                if not linked.ok:
                    logger.warning(
                        "pending project link failed after startup retry: "
                        "project_id=%s material_id=%s stage=%s error=%s",
                        result.project_id,
                        result.material_id,
                        linked.stage,
                        linked.error,
                    )
        if summary.succeeded_count:
            self._tray.show_notification(f"已恢复 {summary.succeeded_count} 条录制")
        if self._material_library_dialog is not None:
            self._material_library_dialog.reload()
        project_page = getattr(self, "_project_page", None)
        if project_page is not None and project_recovered:
            project_page.reload()

    def _start_initial_migration(self) -> None:
        if self._migration_thread is not None and self._migration_thread.is_alive():
            return

        def migrate() -> None:
            result = self._run_initial_migration()
            if result is not None:
                self._migration_bridge.initial_migration_finished.emit(result)

        self._migration_thread = threading.Thread(
            target=migrate,
            name="QuickRecLibraryMigration",
            daemon=True,
        )
        self._migration_thread.start()

    def _run_initial_migration(self) -> MigrationResult | None:
        save_path = Path(self._config.get("save_path", ""))
        source = save_path / "QuickRecMetadata" / "recordings.json"
        if not source.is_file() or self._library_service.has_processed_source(source):
            return None
        logger.info("material library migration started: %s", source)
        result = self._library_service.migrate_v1_history(
            source,
            imported_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        if result.ok:
            logger.info(
                "material library migration completed: added=%s duplicate=%s skipped=%s pruned=%s",
                result.added_count,
                result.duplicate_count,
                result.skipped_count,
                result.pruned_count,
            )
        else:
            logger.warning("material library migration failed: %s", result.error)
        return result

    def _register_save_path_legacy_prompt(self, save_path: str | Path) -> Path | None:
        source = Path(save_path) / "QuickRecMetadata" / "recordings.json"
        if not source.is_file() or self._library_service.has_source_status(source):
            return None
        written = self._library_service.mark_source_status(
            source,
            status="prompted",
            changed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        if not written.ok:
            logger.warning("material migration prompt status save failed: %s", written.error)
            return None
        return source

    def _handle_save_path_changed(self, save_path: str | Path) -> None:
        source = self._register_save_path_legacy_prompt(save_path)
        if source is None:
            return
        self._tray.show_notification("新保存目录包含旧录制历史，可在素材库中导入")
        self._show_material_library()
        self._material_library_dialog.show_legacy_source_prompt(source)

    def _on_initial_migration_finished(self, result: MigrationResult) -> None:
        self._initial_migration_result = result
        if result.ok:
            self._tray.show_notification(
                f"素材迁移完成：新增 {result.added_count} 条，重复 {result.duplicate_count} 条"
            )
        else:
            self._tray.show_notification("素材迁移失败，请打开素材库重试或稍后处理")
        if self._material_library_dialog is not None:
            self._material_library_dialog.show_migration_result(result)

    def _setup_hotkeys(self):
        """绑定快捷键（通过信号桥转发到主线程）"""
        shortcut_start = self._config.get("shortcut_start", "Ctrl+Shift+R")
        shortcut_stop = self._config.get("shortcut_stop", "Ctrl+Shift+S")
        shortcut_pause = self._config.get("shortcut_pause", "Ctrl+Shift+P")
        shortcut_area = self._config.get("shortcut_area", "Ctrl+Shift+A")
        shortcut_window = self._config.get("shortcut_window", "Ctrl+Shift+W")

        self._hotkey.register(shortcut_start, self._hotkey_bridge.start_requested.emit)
        self._hotkey.register(shortcut_stop, self._hotkey_bridge.stop_requested.emit)
        self._hotkey.register(shortcut_pause, self._hotkey_bridge.pause_requested.emit)
        self._hotkey.register(shortcut_area, self._hotkey_bridge.area_requested.emit)
        self._hotkey.register(shortcut_window, self._hotkey_bridge.window_requested.emit)

    @staticmethod
    def _is_text_input_focused() -> bool:
        return isinstance(QApplication.focusWidget(), QLineEdit)

    def _run_hotkey_action(self, callback: Callable[[], None]) -> None:
        if self._is_text_input_focused():
            logger.debug("全局快捷键已忽略：QuickRec 文本输入框正在编辑")
            return
        callback()

    # --- 全屏录制 ---

    def _check_disk_space(self) -> bool:
        """录制前磁盘空间检查，返回 True 表示可以继续"""
        save_path = self._config.get("save_path")
        status, free_mb = DiskChecker.check_before_recording(save_path)
        if status == "block":
            show_disk_warning(free_mb, block=True)
            return False
        if status == "warn":
            return show_disk_warning(free_mb, block=False)
        return True

    def _can_start_recording_request(self) -> bool:
        guard = getattr(self, "_media_operation_guard", None)
        if guard is None:
            return True
        decision = guard.can_begin_recording()
        if decision.ok:
            return True
        logger.warning("recording blocked by export runtime")
        tray = getattr(self, "_tray", None)
        if tray is not None:
            tray.show_notification(
                "导出任务正在运行，请等待完成或先取消导出"
            )
        return False

    def _recording_operation_availability(self) -> tuple[bool, str]:
        guard = getattr(self, "_media_operation_guard", None)
        if guard is None:
            return True, ""
        decision = guard.can_begin_recording()
        if decision.ok:
            return True, ""
        return (
            False,
            "导出正在占用编码资源，请等待完成或取消导出。",
        )

    def _sync_recording_operation_availability(self) -> None:
        page = getattr(self, "_recording_page", None)
        setter = getattr(page, "set_recording_blocked", None)
        if not callable(setter):
            return
        allowed, reason = self._recording_operation_availability()
        setter(not allowed, reason=reason)

    def _acquire_recording_operation(self) -> bool:
        guard = getattr(self, "_media_operation_guard", None)
        if guard is None:
            return True
        decision = guard.try_begin_recording()
        if decision.ok:
            return True
        logger.warning("recording start lost export runtime race")
        tray = getattr(self, "_tray", None)
        if tray is not None:
            tray.show_notification(
                "导出任务已经开始，本次录制未启动"
            )
        return False

    def _release_recording_operation(self) -> None:
        guard = getattr(self, "_media_operation_guard", None)
        if guard is not None:
            guard.release_recording()

    def _on_start_fullscreen(self, *, source: str = "tray"):
        """开始全屏录制"""
        if self._workflow.get_state() != RecorderState.IDLE:
            return
        if not self._can_start_recording_request():
            return
        if self._toolbar and self._toolbar.is_countdown_mode():
            self._on_countdown_esc()
            return
        if not self._check_120_capture_readiness():
            return
        if not self._check_disk_space():
            return
        self._begin_recording_request(source, "fullscreen")

        # v1.2: 检查倒计时配置
        if self._config.get("show_countdown", False):
            self._set_recording_request_state("countdown")
            self._show_toolbar(mode="fullscreen", output_index=0)
            self._toolbar.start_countdown(
                self._config.get("countdown_seconds", 3)
            )
            self._toolbar.countdown_finished.connect(self._do_start_fullscreen)
            # 倒计时期间全局 ESC 可取消
            self._hotkey.set_esc_callback(self._on_countdown_esc)
        else:
            self._show_toolbar(mode="fullscreen", output_index=0)
            self._do_start_fullscreen()

    def _check_120_capture_readiness(self) -> bool:
        if int(self._config.get("fps", 30)) != 120:
            return True
        inspection = self._capture_capability.inspect()
        if inspection.readiness.ready:
            return True

        box = QMessageBox()
        box.setWindowTitle("需要重新检测 120 FPS")
        box.setText(inspection.readiness.reason)
        box.setInformativeText(
            "可以重新运行约 5 秒能力检测，或仅将本次全屏录制改用 60 FPS。"
        )
        retry = box.addButton("重新检测", QMessageBox.AcceptRole)
        use_60 = box.addButton("本次改用 60 FPS", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Cancel)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is retry:
            result = CaptureSelfTestDialog.execute(self._capture_capability)
            return bool(result and result.passed)
        if clicked is use_60:
            self._recorder.set_next_fps_override(60)
            self._tray.show_notification("本次全屏录制将使用 60 FPS")
            return True
        return False

    def _do_start_fullscreen(self):
        """倒计时结束后的实际全屏录制启动"""
        self._hotkey.set_esc_callback(None)  # 清除 ESC 回调
        if not self._acquire_recording_operation():
            self._hide_toolbar()
            self._finish_recording_request(restore_workbench=True)
            return
        if not self._workflow.start_fullscreen():
            logger.error("全屏录制启动失败")
            self._tray.show_notification("录制启动失败，请检查 FFmpeg 或录制环境")
            self._hide_toolbar()
            self._finish_recording_request(restore_workbench=True)
            return
        if self._toolbar:
            self._toolbar.start_recording_timer()
        self._tray.set_recording_state(True)
        self._set_recording_request_state("recording")
        self._update_highlight_state()

    # --- 区域录制 ---

    def _on_start_region(self, *, source: str = "tray"):
        """区域录制：显示区域选择器"""
        if self._workflow.get_state() != RecorderState.IDLE:
            return
        if not self._can_start_recording_request():
            return
        if self._toolbar and self._toolbar.is_countdown_mode():
            self._on_countdown_esc()
            return
        if not self._check_disk_space():
            return
        self._begin_recording_request(source, "region")

        self._area_selector = AreaSelector()
        self._area_selector.region_selected.connect(
            lambda x, y, w, h: self._area_bridge.region_selected.emit(x, y, w, h)
        )
        self._area_selector.cancelled.connect(self._area_bridge.cancelled.emit)
        self._area_selector.show_fullscreen()

    def _on_region_selected(self, x, y, w, h):
        """区域选择完成：开始录制"""
        self._area_selector = None
        if self._config.get("show_countdown", False):
            self._set_recording_request_state("countdown")
            self._show_toolbar(
                mode="region",
                target_rect=(x, y, w, h),
            )
            self._toolbar.start_countdown(
                self._config.get("countdown_seconds", 3)
            )
            self._toolbar.countdown_finished.connect(
                lambda: self._do_start_region(x, y, w, h)
            )
            self._hotkey.set_esc_callback(self._on_countdown_esc)
        else:
            self._show_toolbar(
                mode="region",
                target_rect=(x, y, w, h),
            )
            self._do_start_region(x, y, w, h)

    def _do_start_region(self, x, y, w, h):
        """区域录制实际启动"""
        self._hotkey.set_esc_callback(None)
        if not self._acquire_recording_operation():
            self._hide_toolbar()
            self._finish_recording_request(restore_workbench=True)
            return
        if not self._workflow.start_region((x, y, w, h)):
            logger.error("区域录制启动失败")
            self._tray.show_notification("录制启动失败，请检查 FFmpeg 或录制环境")
            self._hide_toolbar()
            self._finish_recording_request(restore_workbench=True)
            return
        if self._toolbar:
            self._toolbar.start_recording_timer()
        self._tray.set_recording_state(True)
        self._set_recording_request_state("recording")
        self._update_highlight_state()

    def _on_selection_cancelled(self):
        """区域选择取消"""
        self._area_selector = None
        self._finish_recording_request(restore_workbench=True)

    def _on_countdown_esc(self):
        """全局 ESC 回调：倒计时期间取消倒计时"""
        if self._toolbar and self._toolbar.is_countdown_mode():
            self._toolbar.cancel_countdown()
            self._hide_toolbar()
            self._hotkey.set_esc_callback(None)
            # 窗口录制模式下取消倒计时需同时隐藏边框高亮
            if self._window_highlighter:
                self._window_highlighter.hide_highlight()
                self._window_highlighter = None
            self._finish_recording_request(restore_workbench=True)

    # --- 窗口录制 ---

    def _on_start_window(self, *, source: str = "tray"):
        """窗口录制：显示窗口选择器"""
        if self._workflow.get_state() != RecorderState.IDLE:
            return
        if not self._can_start_recording_request():
            return
        if self._toolbar and self._toolbar.is_countdown_mode():
            self._on_countdown_esc()
            return
        if not self._check_disk_space():
            return
        self._begin_recording_request(source, "window")
        self._window_selector = WindowSelector()
        self._window_selector.window_selected.connect(
            lambda hwnd, title: self._window_bridge.window_selected.emit(hwnd, title)
        )
        self._window_selector.cancelled.connect(self._window_bridge.cancelled.emit)
        self._window_selector.exec_()

    def _on_window_selected(self, hwnd: int, title: str):
        """窗口选择完成"""
        self._window_selector = None
        user32 = ctypes.windll.user32
        # 恢复最小化窗口（同步一次，主线程不阻塞）
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        # 绕过 Windows 前台锁定：模拟 Alt 键 + 置前台
        user32.keybd_event(0x12, 0x38, 0, 0)         # VK_MENU down
        user32.keybd_event(0x12, 0x38, 0x0002, 0)    # VK_MENU up
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        # 用异步延迟等待窗口激活与绘制完成，避免主线程长阻塞导致 GUI 卡死/闪退
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(400, lambda: self._after_window_foreground(hwnd))

    def _after_window_foreground(self, hwnd: int):
        """窗口置前台后的异步续逻辑（主线程，已让出事件循环）"""
        user32 = ctypes.windll.user32
        if not user32.IsWindow(hwnd):
            logger.warning("目标窗口已不存在，取消窗口录制")
            self._tray.show_notification("目标窗口已关闭")
            self._finish_recording_request(restore_workbench=True)
            return
        self._window_highlighter = WindowHighlighter(hwnd)
        self._window_highlighter.show_highlight()
        target_geometry = self._window_highlighter.geometry()
        target_rect = (
            target_geometry.x(),
            target_geometry.y(),
            target_geometry.width(),
            target_geometry.height(),
        )
        if self._config.get("show_countdown", False):
            self._set_recording_request_state("countdown")
            self._show_toolbar(mode="window", target_rect=target_rect)
            self._toolbar.start_countdown(self._config.get("countdown_seconds", 3))
            self._toolbar.countdown_finished.connect(lambda: self._do_start_window(hwnd))
            self._hotkey.set_esc_callback(self._on_countdown_esc)
        else:
            self._show_toolbar(mode="window", target_rect=target_rect)
            self._do_start_window(hwnd)

    def _do_start_window(self, hwnd: int):
        """窗口录制实际启动"""
        self._hotkey.set_esc_callback(None)
        if not self._acquire_recording_operation():
            self._hide_toolbar()
            self._finish_recording_request(restore_workbench=True)
            return
        if not self._workflow.start_window(hwnd):
            logger.error("窗口录制启动失败")
            self._hide_toolbar()
            if self._window_highlighter:
                self._window_highlighter.hide_highlight()
                self._window_highlighter = None
            # 告知用户失败原因（特殊窗口/最小化恢复未完成）
            self._tray.show_notification("窗口录制启动失败：无法获取窗口区域")
            self._finish_recording_request(restore_workbench=True)
            return
        if self._window_highlighter:
            self._window_highlighter.hide_highlight()
            self._window_highlighter = None
        if self._toolbar:
            self._toolbar.start_recording_timer()
        self._tray.set_recording_state(True)
        self._set_recording_request_state("recording")
        self._update_highlight_state()

    def _on_window_cancelled(self):
        self._window_selector = None
        self._finish_recording_request(restore_workbench=True)

    def _on_window_lost(self, reason: str):
        """窗口丢失：简化处理（无 QMessageBox）"""
        if self._window_highlighter:
            self._window_highlighter.hide_highlight()
            self._window_highlighter = None
        if reason == "closed":
            self._tray.show_notification("录制窗口已关闭，视频已保存")
            self._on_stop_recording()
        elif reason == "minimized":
            self._workflow.pause()
            if self._toolbar:
                self._toolbar.set_paused(True)
            self._tray.set_recording_state(True, paused=True)
            self._tray.show_notification("录制窗口已最小化，录制已暂停。恢复窗口后点击\"继续\"继续录制。")

    # --- 录制控制 ---

    def _on_stop_recording(self):
        """停止录制"""
        state = self._workflow.get_state()
        if state == RecorderState.IDLE or state == RecorderState.SAVING:
            return

        self._workflow.stop()
        self._set_recording_request_state("saving")
        if self._toolbar:
            self._toolbar.show_saving()

        # v1.2: 停止录制时立即停止鼠标高亮（不等编码完成）
        self._click_highlighter.stop()

    def _on_pause_resume(self):
        """暂停/恢复录制"""
        state = self._workflow.get_state()
        if state == RecorderState.RECORDING:
            self._workflow.pause()
            if self._toolbar:
                self._toolbar.set_paused(True)
            self._tray.set_recording_state(True, paused=True)
            self._set_recording_request_state("paused")
        elif state == RecorderState.PAUSED:
            self._workflow.resume()
            if self._toolbar:
                self._toolbar.set_paused(False)
            self._tray.set_recording_state(True, paused=False)
            self._set_recording_request_state("recording")

    # --- 工具栏 ---

    def _show_toolbar(
        self,
        *,
        mode: str = "fullscreen",
        target_rect: tuple[int, int, int, int] | None = None,
        output_index: int | None = None,
    ):
        """显示录制工具栏"""
        screens = QApplication.screens()
        target_screen = None
        if screens:
            primary = QApplication.primaryScreen()
            primary_index = next(
                (
                    index
                    for index, screen in enumerate(screens)
                    if screen is primary
                ),
                0,
            )
            screen_rects = [
                (
                    screen.geometry().x(),
                    screen.geometry().y(),
                    screen.geometry().width(),
                    screen.geometry().height(),
                )
                for screen in screens
            ]
            screen_index = select_target_screen_index(
                screen_rects,
                mode=mode,
                target_rect=target_rect,
                output_index=output_index,
                primary_index=primary_index,
            )
            target_screen = screens[screen_index]
        self._toolbar = RecordingToolbar(target_screen=target_screen)
        self._toolbar.paused.connect(self._on_pause_resume)
        self._toolbar.resumed.connect(self._on_pause_resume)
        self._toolbar.stopped.connect(self._on_stop_recording)
        self._toolbar.cancelled.connect(self._on_cancel_recording)

        # v1.1: 结果条信号连接
        self._toolbar.open_folder_requested.connect(self._on_open_folder)
        self._toolbar.open_file_requested.connect(self._on_open_file)
        self._toolbar.material_library_requested.connect(self._show_material_library)
        self._toolbar.retry_material_requested.connect(self._retry_material_item)

        self._toolbar.show()

    def _hide_toolbar(self):
        """隐藏录制工具栏"""
        if self._toolbar:
            self._toolbar.stop_recording_timer()
            self._toolbar.close()
            self._toolbar = None

    def _on_cancel_recording(self):
        """取消录制"""
        state = self._workflow.get_state()
        if state != RecorderState.IDLE and state != RecorderState.SAVING:
            self._workflow.stop(cancel=True)
        self._tray.show_notification("录制已取消")
        self._tray.set_recording_state(False)
        if self._window_highlighter:
            self._window_highlighter.hide_highlight()
            self._window_highlighter = None
        self._click_highlighter.stop()
        self._hide_toolbar()
        self._finish_recording_request(restore_workbench=True)

    # --- 鼠标高亮控制（v1.2 新增） ---

    def _update_highlight_state(self):
        """根据配置和录制状态决定是否启动/停止高亮"""
        recorder_mode = self._recorder.get_mode() if self._recorder else None
        should_enable = (
            self._config.get("mouse_highlight", False)
            and self._workflow.get_state() == RecorderState.RECORDING
            and recorder_mode != RecordMode.WINDOW
        )
        if should_enable and not self._click_highlighter.is_running():
            self._click_highlighter.start()
        elif not should_enable and self._click_highlighter.is_running():
            self._click_highlighter.stop()

    # --- 结果条回调 ---

    def _on_open_folder(self, output_path: str = ""):
        """结果条：打开文件夹并选中文件"""
        import subprocess
        toolbar_path = (
            self._toolbar._output_path
            if self._toolbar
            and hasattr(self._toolbar, "_output_path")
            and self._toolbar._output_path
            else ""
        )
        if output_path or toolbar_path:
            path = os.path.normpath(output_path or toolbar_path)
            try:
                if os.path.exists(path):
                    subprocess.run(["explorer.exe", "/select,", path])
                else:
                    os.startfile(os.path.dirname(path))
            except Exception:
                pass

    def _on_open_file(self, output_path: str = ""):
        """结果条：用默认播放器打开视频文件"""
        toolbar_path = (
            self._toolbar._output_path
            if self._toolbar
            and hasattr(self._toolbar, "_output_path")
            and self._toolbar._output_path
            else ""
        )
        if output_path or toolbar_path:
            path = output_path or toolbar_path
            try:
                os.startfile(path)
            except Exception:
                pass

    # --- 编码完成回调 ---

    def _on_recording_event(self, event: RecordingEvent) -> None:
        """将唯一录制完成事实转交 Qt 主线程。"""
        if event.type is RecordingEventType.SAVED:
            self._on_saved(event.output_path)
        elif event.type is RecordingEventType.FAILED:
            self._on_saved("")

    def _on_saved(self, output_path: str):
        """编码完成回调（从编码线程调用，通过信号桥安全转发到主线程）"""
        logger.info(f"收到编码完成回调: {output_path}")
        self._saved_bridge.saved.emit(output_path)

    def _handle_saved(self, output_path: str):
        """主线程中处理编码完成"""
        logger.info(f"主线程处理编码完成: {output_path}")
        source = getattr(self, "_recording_source", None)
        project_id = (
            getattr(self, "_active_project_recording_id", None)
            if source in {"project", "timeline"}
            else None
        )
        if output_path:
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            size_str = f"{file_size_mb:.1f}MB"
            logger.info(f"录制已保存: {output_path}")
            metadata = (
                self._recorder.get_last_recording_metadata()
                if self._recorder and hasattr(self._recorder, "get_last_recording_metadata")
                else {}
            )
            performance_text = ""
            performance_stable = True
            if metadata.get("target_fps") == 120:
                average = metadata.get("average_fps")
                minimum = metadata.get("minimum_one_second_fps")
                performance_stable = bool(metadata.get("stable", False))
                if isinstance(average, (int, float)) and isinstance(minimum, (int, float)):
                    performance_text = (
                        f"目标 120 FPS · 平均 {float(average):.1f} FPS · "
                        f"最低每秒 {int(minimum)} FPS"
                    )
                if not performance_stable:
                    performance_text = (
                        f"{performance_text} · " if performance_text else ""
                    ) + "未稳定达到 120 FPS，视频已正常保存"
                    self._tray.show_notification(
                        "录制已保存，但本次未稳定达到 120 FPS"
                    )
            ingestion = self._save_material_item(
                output_path,
                project_id=project_id,
            )
            index_ok = ingestion.formal_indexed
            project_linked = False
            project_message = ""
            if project_id and index_ok:
                linked = self._project_recording_coordinator.link_material(
                    project_id,
                    ingestion.material_id,
                )
                project_linked = linked.ok
                if not linked.ok:
                    project_message = "素材已入库，但项目关联失败，可在项目页重试"
                    logger.warning(
                        "project recording link failed: "
                        "project_id=%s material_id=%s stage=%s error=%s",
                        project_id,
                        ingestion.material_id,
                        linked.stage,
                        linked.error,
                    )
            elif project_id:
                project_message = "素材待重试入库，成功后将继续关联项目"
            if ingestion.pending_id:
                self._pending_ids_by_output[self._normalize_output_path(output_path)] = (
                    ingestion.pending_id
                )
            material_dialog = getattr(self, "_material_library_dialog", None)
            if material_dialog is not None:
                material_dialog.reload()
            if not index_ok:
                self._tray.show_notification("录制已保存，但素材索引写入失败")

            # v1.1: Toast 通知带"打开文件夹"按钮
            self._tray.show_notification_with_action(
                title="录制已保存",
                msg=f"{os.path.basename(output_path)} ({size_str})",
                action_label="打开文件夹",
                output_path=output_path,
            )

            # v1.1: 工具栏显示结果条
            if source in {"project", "timeline"} and project_id and self._project_page is not None:
                self._hide_toolbar()
                self._finish_recording_request(restore_workbench=True)
                self._project_page.show_recording_result(
                    project_id,
                    video_saved=True,
                    material_indexed=index_ok,
                    project_linked=project_linked,
                    message=project_message,
                )
            elif source == "workbench" and self._recording_page is not None:
                self._recording_page.show_result(
                    output_path,
                    size_str,
                    index_ok=index_ok,
                    performance_text=performance_text,
                    performance_stable=performance_stable,
                )
                self._hide_toolbar()
                self._finish_recording_request(restore_workbench=True)
            elif self._toolbar:
                self._toolbar.show_result(output_path, size_str, index_ok=index_ok)
                self._finish_recording_request(restore_workbench=False)
            else:
                self._finish_recording_request(restore_workbench=False)
        else:
            logger.error("编码保存失败")
            self._tray.show_notification("保存失败")
            self._hide_toolbar()
            if source in {"project", "timeline"} and project_id and self._project_page is not None:
                self._finish_recording_request(restore_workbench=True)
                self._project_page.show_recording_result(
                    project_id,
                    video_saved=False,
                    material_indexed=False,
                    project_linked=False,
                    message="编码器未生成可用输出文件。",
                )
            elif source == "workbench" and self._recording_page is not None:
                self._recording_page.show_failure("编码器未生成可用输出文件。")
                self._finish_recording_request(restore_workbench=True)
            else:
                self._finish_recording_request(restore_workbench=True)

        self._tray.set_recording_state(False)
        if self._window_highlighter:
            self._window_highlighter.hide_highlight()
            self._window_highlighter = None
        self._click_highlighter.stop()

    def _save_material_item(
        self,
        output_path: str,
        *,
        project_id: str | None = None,
    ) -> IngestionResult:
        try:
            metadata = (
                self._recorder.get_last_recording_metadata()
                if self._recorder and hasattr(self._recorder, "get_last_recording_metadata")
                else {}
            )
            mode = self._recorder.get_mode() if self._recorder else "unknown"
            metadata.setdefault("mode", getattr(mode, "value", str(mode)))
            metadata.setdefault("audio_source", self._config.get("audio_source", "none"))
            result = self._ingestion_coordinator.ingest_saved_recording(
                output_path,
                metadata=metadata,
                diagnostic_dir=self._config.get_diagnostic_dir(),
                project_id=project_id,
            )
            if not result.formal_indexed:
                logger.warning(
                    "material ingestion deferred: pending_id=%s persisted=%s error_code=%s error=%s",
                    result.pending_id,
                    result.pending_persisted,
                    result.error_code,
                    result.error,
                )
            return result
        except Exception as exc:
            logger.warning(f"material library save failed: {exc}")
            return IngestionResult(True, False, error_code="INGESTION_UNEXPECTED", error=str(exc))

    def _retry_material_item(self, output_path: str) -> None:
        normalized = self._normalize_output_path(output_path)
        pending_id = self._pending_ids_by_output.get(normalized)
        if pending_id is None:
            loaded = self._pending_service.load(Path(output_path).parent)
            if loaded.ok:
                pending = next(
                    (
                        item
                        for item in loaded.items
                        if self._normalize_output_path(item.file_path) == normalized
                    ),
                    None,
                )
                pending_id = pending.pending_id if pending else None
        if pending_id is None:
            self._tray.show_notification("未找到待入库记录，请在素材库中查看")
            return
        result = self._ingestion_coordinator.retry(
            pending_id,
            current_save_dir=Path(output_path).parent,
        )
        if result.formal_indexed:
            self._pending_ids_by_output.pop(normalized, None)
            project_linked = True
            if result.project_id:
                linked = self._project_recording_coordinator.link_material(
                    result.project_id,
                    result.material_id,
                )
                project_linked = linked.ok
                if self._project_page is not None:
                    self._project_page.reload()
                if not linked.ok:
                    logger.warning(
                        "project link failed after manual retry: "
                        "project_id=%s material_id=%s stage=%s error=%s",
                        result.project_id,
                        result.material_id,
                        linked.stage,
                        linked.error,
                    )
            self._tray.show_notification(
                "素材已加入素材库"
                if project_linked
                else "素材已入库，但项目关联失败"
            )
            if self._toolbar:
                self._toolbar.mark_material_index_saved()
        else:
            self._tray.show_notification("素材索引写入仍然失败，请检查诊断日志")

    @staticmethod
    def _normalize_output_path(path: str | Path) -> str:
        return os.path.normcase(os.path.abspath(str(path)))

    def _show_material_library(self):
        return self._show_workbench(WorkbenchPage.MATERIALS)

    # --- 设置 ---

    def _show_settings(self):
        """显示设置对话框"""
        # 打开设置期间暂停全局快捷键，避免与快捷键录制控件冲突
        self._hotkey.stop_listening()
        self._config_saved_pending = False
        save_path_before = self._config.get("save_path", "")
        dialog = SettingsDialog(
            self._config,
            capture_capability=self._capture_capability,
        )
        dialog.config_saved.connect(self._on_config_saved_pend)
        dialog.open_capture_diagnostics_requested.connect(
            lambda: self._show_workbench(WorkbenchPage.DIAGNOSTICS)
        )
        dialog.copy_diagnostic_requested.connect(
            lambda path: self._on_copy_diagnostic_info(path, dialog)
        )
        dialog.open_diagnostic_dir_requested.connect(
            lambda path: self._on_open_diagnostic_dir(path, dialog)
        )
        dialog.export_diagnostic_requested.connect(
            lambda path: self._on_export_diagnostic_file(path, dialog)
        )
        dialog.exec_()

        save_path_after = self._config.get("save_path", "")
        if save_path_after and save_path_after != save_path_before:
            self._handle_save_path_changed(save_path_after)

        # 对话框关闭后，统一重绑定并重新启动快捷键监听
        if self._config_saved_pending:
            # 配置已保存，用新配置重绑定
            self._hotkey.unregister_all()
            self._setup_hotkeys()
        self._hotkey.start_listening()

    def _on_config_saved_pend(self):
        """配置保存后标记需要重绑定（不立即操作 pynput，避免对话框内冲突）"""
        self._config_saved_pending = True

    # --- 诊断导出 ---

    def _build_diagnostic_text(self, diagnostic_dir: str | None = None) -> str:
        directory = resolve_diagnostic_dir(self._config, diagnostic_dir)
        context = self._recorder.get_diagnostic_context() if self._recorder else {}
        config_context = dict(context.get("config", {}))
        config_context["diagnostic_dir"] = str(directory)
        capability_runtime = getattr(self, "_capture_capability", None)
        if capability_runtime is not None:
            config_context["capture_120"] = capability_runtime.diagnostic_context()
        recorder_context = context.get("recorder", {})
        failure = recorder_context.get("last_failure_reason", "")
        thumbnail_coordinator = getattr(
            self,
            "_thumbnail_coordinator",
            None,
        )
        thumbnail_context = (
            thumbnail_coordinator.diagnostic_summary(limit=10)
            if thumbnail_coordinator is not None
            else {}
        )
        timeline_editor = getattr(self, "_timeline_editor", None)
        playback_context = (
            timeline_editor.diagnostic_summary()
            if timeline_editor is not None
            else {"state": "not_initialized"}
        )
        export_queue = getattr(self, "_export_queue_service", None)
        export_context = (
            build_export_diagnostic_summary(export_queue.state)
            if export_queue is not None
            else {"state": "not_initialized"}
        )
        snapshot = DiagnosticSnapshot(
            app={
                "version": APP_VERSION,
                "python": sys.version.split()[0],
                "windows": platform.platform(),
                "frozen": bool(getattr(sys, "frozen", False)),
            },
            config=config_context,
            recorder=recorder_context,
            ffmpeg=context.get("ffmpeg", {}),
            audio=context.get("audio", {}),
            window=context.get("window", {}),
            thumbnail=thumbnail_context,
            playback=playback_context,
            exports=export_context,
            errors=[failure] if failure else [],
            recent_logs=read_recent_log_lines(directory / "quickrec.log", max_lines=100),
        )
        return format_snapshot_text(snapshot)

    def _set_diagnostic_feedback(self, dialog, text: str) -> None:
        if dialog and hasattr(dialog, "set_diagnostic_status"):
            dialog.set_diagnostic_status(text)

    def _on_copy_diagnostic_info(self, diagnostic_dir: str | None = None, dialog=None):
        try:
            clipboard = QApplication.clipboard()
            if clipboard is None:
                raise RuntimeError("clipboard is unavailable")
            clipboard.setText(self._build_diagnostic_text(diagnostic_dir))
            logger.info("diagnostic copied")
            self._tray.show_notification("诊断信息已复制")
            self._set_diagnostic_feedback(dialog, "诊断信息已复制")
            return True
        except Exception as e:
            logger.error(f"diagnostic copy failed: {e}")
            self._tray.show_notification("复制失败，请导出诊断文件")
            self._set_diagnostic_feedback(dialog, "复制失败，请导出诊断文件")
            return False

    def _on_open_diagnostic_dir(self, diagnostic_dir: str | None = None, dialog=None):
        directory = resolve_diagnostic_dir(self._config, diagnostic_dir)
        result = open_diagnostic_dir(directory)
        if result.ok:
            logger.info(f"diagnostic directory opened: {result.path}")
            self._set_diagnostic_feedback(dialog, f"日志目录已打开：{result.path}")
            return True
        logger.error(f"diagnostic directory open failed: {result.error}")
        self._tray.show_notification("无法打开日志目录")
        self._set_diagnostic_feedback(dialog, "无法打开日志目录")
        return False

    def _on_export_diagnostic_file(self, diagnostic_dir: str | None = None, dialog=None):
        directory = resolve_diagnostic_dir(self._config, diagnostic_dir)
        result = export_diagnostic_file(self._build_diagnostic_text(str(directory)), directory)
        if result.ok:
            logger.info(f"diagnostic exported: {result.path}")
            self._tray.show_notification("诊断文件已导出")
            self._set_diagnostic_feedback(dialog, f"诊断文件已导出：{result.path}")
            return True
        logger.error(f"diagnostic export failed: {result.error}")
        self._tray.show_notification("导出失败，请检查诊断目录权限")
        self._set_diagnostic_feedback(dialog, "导出失败，请检查诊断目录权限")
        return False

    # --- 退出 ---

    def _confirm_export_exit(self) -> bool:
        coordinator = getattr(self, "_export_exit_coordinator", None)
        queue = getattr(self, "_export_queue_service", None)
        if coordinator is None or queue is None or queue.active_job_id is None:
            return True

        box = QMessageBox()
        box.setWindowTitle("导出任务正在运行")
        box.setIcon(QMessageBox.Warning)
        box.setText("当前导出任务尚未完成。")
        box.setInformativeText(
            "关闭工作台不会影响导出。若退出 QuickRec，可安全中断当前尝试，"
            "任务将在下次启动后保持为可重试状态。"
        )
        continue_button = box.addButton(
            "继续导出并留在托盘",
            QMessageBox.RejectRole,
        )
        interrupt_button = box.addButton(
            "安全中断并退出",
            QMessageBox.DestructiveRole,
        )
        return_button = box.addButton(
            "返回应用",
            QMessageBox.AcceptRole,
        )
        box.setDefaultButton(continue_button)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is not interrupt_button:
            action = (
                ExportExitAction.CONTINUE_BACKGROUND
                if clicked is continue_button
                else ExportExitAction.RETURN_TO_APP
            )
            coordinator.request_exit(action)
            if clicked is return_button:
                self._show_workbench(WorkbenchPage.EXPORTS)
            return False
        result = coordinator.request_exit(
            ExportExitAction.INTERRUPT_AND_EXIT,
            timeout=30.0,
        )
        if result.should_exit:
            return True
        QMessageBox.warning(
            None,
            "暂时无法退出",
            result.message or "导出任务尚未安全停止，请稍后重试。",
        )
        return False

    def _on_exit(self):
        """退出程序"""
        if not self._confirm_export_exit():
            return
        activation_timer = getattr(
            self,
            "_instance_activation_timer",
            None,
        )
        if activation_timer is not None:
            activation_timer.stop()
        state = self._workflow.get_state()
        if state != RecorderState.IDLE:
            self._workflow.stop()

        # 等待录制停止和编码完成（stop 现在是非阻塞的）
        if not self._workflow.wait_until_idle(timeout=60):
            logger.error("Recorder did not become idle before exit timeout")
        self._release_recording_operation()
        # 确保处理完所有编码完成信号
        from PyQt5.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        if self._window_highlighter:
            self._window_highlighter.hide_highlight()
            self._window_highlighter = None
        self._click_highlighter.stop()

        self._hide_toolbar()
        if hasattr(self, "_workbench"):
            self._workbench.hide()
        timeline_editor = getattr(self, "_timeline_editor", None)
        if timeline_editor is not None:
            timeline_editor.shutdown()
        thumbnail_coordinator = getattr(
            self,
            "_thumbnail_coordinator",
            None,
        )
        if thumbnail_coordinator is not None:
            thumbnail_coordinator.shutdown(cancel_pending=True, wait=True)
        self._hotkey.stop_listening()
        self._tray.hide()
        self._app.quit()
        logger.info("QuickRec 已退出")


def main():
    """程序入口"""
    instance_guard = None
    try:
        instance_guard = SingleInstanceGuard(FULL_PRODUCT_ID)
        if not instance_guard.acquire():
            if instance_guard.activation_signal_sent:
                logger.info("existing QuickRec Full instance activated")
            else:
                logger.warning(
                    "QuickRec Full is already running, but activation "
                    "signal could not be delivered"
                )
            return
        _enable_dpi_awareness()
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        app = QuickRecApp(instance_guard=instance_guard)
        sys.exit(app.run())
    except Exception as e:
        logger.exception(f"QuickRec 异常退出: {e}")
        sys.exit(1)
    finally:
        if instance_guard is not None:
            instance_guard.close()


if __name__ == "__main__":
    main()
