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

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication, QLineEdit

from config import ConfigManager
from hotkey.hotkey_manager import HotkeyManager
from recorder.recorder_manager import RecorderManager, RecorderState, RecordMode
from recorder.workflow import RecordingWorkflow
from services.material_ingestion import (
    IngestionResult,
    MaterialIngestionCoordinator,
    StartupRetrySummary,
)
from services.pending_recordings import PendingRecordingService
from services.recording_library import MigrationResult, RecordingLibraryService
from ui.area_selector import AreaSelector
from ui.click_highlighter import ClickHighlighter
from ui.material_library_dialog import MaterialLibraryDialog
from ui.settings_dialog import SettingsDialog
from ui.toolbar import RecordingToolbar
from ui.tray_icon import TrayIcon
from ui.window_highlighter import WindowHighlighter
from ui.window_selector import WindowSelector
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
from utils.pending_recording_store import resolve_pending_file
from utils.recording_library_store import resolve_library_file
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


class QuickRecApp:
    """QuickRec 应用主类"""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setStyle("Fusion")

        # 初始化模块
        self._config = ConfigManager()
        log_result = initialize_file_logging(self._config, logger)
        if not log_result.ok:
            logger.warning(f"diagnostic file logging unavailable: {log_result.error}")
        self._recorder = RecorderManager(self._config, on_saved=self._on_saved)
        self._workflow = RecordingWorkflow(self._recorder)
        self._recorder.set_event_handler(self._workflow.handle_event)
        self._hotkey = HotkeyManager()
        self._toolbar = None
        self._library_service = RecordingLibraryService(resolve_library_file())
        self._pending_service = PendingRecordingService(resolve_pending_file())
        self._ingestion_coordinator = MaterialIngestionCoordinator(
            self._library_service,
            self._pending_service,
        )
        self._pending_ids_by_output: dict[str, str] = {}
        self._material_library_dialog = None
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

        # 快捷键信号桥
        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.start_requested.connect(
            lambda: self._run_hotkey_action(self._on_start_fullscreen)
        )
        self._hotkey_bridge.stop_requested.connect(
            lambda: self._run_hotkey_action(self._on_stop_recording)
        )
        self._hotkey_bridge.pause_requested.connect(
            lambda: self._run_hotkey_action(self._on_pause_resume)
        )
        self._hotkey_bridge.area_requested.connect(
            lambda: self._run_hotkey_action(self._on_start_region)
        )
        self._hotkey_bridge.window_requested.connect(
            lambda: self._run_hotkey_action(self._on_start_window)
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
                "start_fullscreen": self._on_start_fullscreen,
                "start_region": self._on_start_region,
                "start_window": self._on_start_window,   # 延期：窗口录制
                "pause_resume": self._on_pause_resume,
                "stop": self._on_stop_recording,
                "settings": self._show_settings,
                "material_library": self._show_material_library,
                "copy_diagnostic": self._on_copy_diagnostic_info,
                "open_diagnostic_dir": self._on_open_diagnostic_dir,
                "export_diagnostic": self._on_export_diagnostic_file,
                "exit": self._on_exit,
            }
        )

        # 绑定快捷键
        self._setup_hotkeys()
        self._hotkey.start_listening()

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
        if summary.succeeded_count:
            self._tray.show_notification(f"已恢复 {summary.succeeded_count} 条录制")
        if self._material_library_dialog is not None:
            self._material_library_dialog.reload()

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

    def _on_start_fullscreen(self):
        """开始全屏录制"""
        if self._workflow.get_state() != RecorderState.IDLE:
            return
        if self._toolbar and self._toolbar.is_countdown_mode():
            self._on_countdown_esc()
            return
        if not self._check_disk_space():
            return

        # v1.2: 检查倒计时配置
        if self._config.get("show_countdown", False):
            self._show_toolbar()
            self._toolbar.start_countdown(
                self._config.get("countdown_seconds", 3)
            )
            self._toolbar.countdown_finished.connect(self._do_start_fullscreen)
            # 倒计时期间全局 ESC 可取消
            self._hotkey.set_esc_callback(self._on_countdown_esc)
        else:
            self._show_toolbar()
            self._do_start_fullscreen()

    def _do_start_fullscreen(self):
        """倒计时结束后的实际全屏录制启动"""
        self._hotkey.set_esc_callback(None)  # 清除 ESC 回调
        if not self._workflow.start_fullscreen():
            logger.error("全屏录制启动失败")
            self._tray.show_notification("录制启动失败，请检查 FFmpeg 或录制环境")
            self._hide_toolbar()
            return
        if self._toolbar:
            self._toolbar.start_recording_timer()
        self._tray.set_recording_state(True)
        self._update_highlight_state()

    # --- 区域录制 ---

    def _on_start_region(self):
        """区域录制：显示区域选择器"""
        if self._workflow.get_state() != RecorderState.IDLE:
            return
        if self._toolbar and self._toolbar.is_countdown_mode():
            self._on_countdown_esc()
            return
        if not self._check_disk_space():
            return

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
            self._show_toolbar()
            self._toolbar.start_countdown(
                self._config.get("countdown_seconds", 3)
            )
            self._toolbar.countdown_finished.connect(
                lambda: self._do_start_region(x, y, w, h)
            )
            self._hotkey.set_esc_callback(self._on_countdown_esc)
        else:
            self._show_toolbar()
            self._do_start_region(x, y, w, h)

    def _do_start_region(self, x, y, w, h):
        """区域录制实际启动"""
        self._hotkey.set_esc_callback(None)
        if not self._workflow.start_region((x, y, w, h)):
            logger.error("区域录制启动失败")
            self._tray.show_notification("录制启动失败，请检查 FFmpeg 或录制环境")
            self._hide_toolbar()
            return
        if self._toolbar:
            self._toolbar.start_recording_timer()
        self._tray.set_recording_state(True)
        self._update_highlight_state()

    def _on_selection_cancelled(self):
        """区域选择取消"""
        self._area_selector = None

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

    # --- 窗口录制 ---

    def _on_start_window(self):
        """窗口录制：显示窗口选择器"""
        if self._workflow.get_state() != RecorderState.IDLE:
            return
        if self._toolbar and self._toolbar.is_countdown_mode():
            self._on_countdown_esc()
            return
        if not self._check_disk_space():
            return
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
            return
        self._window_highlighter = WindowHighlighter(hwnd)
        self._window_highlighter.show_highlight()
        if self._config.get("show_countdown", False):
            self._show_toolbar()
            self._toolbar.start_countdown(self._config.get("countdown_seconds", 3))
            self._toolbar.countdown_finished.connect(lambda: self._do_start_window(hwnd))
            self._hotkey.set_esc_callback(self._on_countdown_esc)
        else:
            self._show_toolbar()
            self._do_start_window(hwnd)

    def _do_start_window(self, hwnd: int):
        """窗口录制实际启动"""
        self._hotkey.set_esc_callback(None)
        if not self._workflow.start_window(hwnd):
            logger.error("窗口录制启动失败")
            self._hide_toolbar()
            if self._window_highlighter:
                self._window_highlighter.hide_highlight()
                self._window_highlighter = None
            # 告知用户失败原因（特殊窗口/最小化恢复未完成）
            self._tray.show_notification("窗口录制启动失败：无法获取窗口区域")
            return
        if self._window_highlighter:
            self._window_highlighter.hide_highlight()
            self._window_highlighter = None
        if self._toolbar:
            self._toolbar.start_recording_timer()
        self._tray.set_recording_state(True)
        self._update_highlight_state()

    def _on_window_cancelled(self):
        self._window_selector = None

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
        elif state == RecorderState.PAUSED:
            self._workflow.resume()
            if self._toolbar:
                self._toolbar.set_paused(False)
            self._tray.set_recording_state(True, paused=False)

    # --- 工具栏 ---

    def _show_toolbar(self):
        """显示录制工具栏"""
        self._toolbar = RecordingToolbar()
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

    def _on_open_folder(self):
        """结果条：打开文件夹并选中文件"""
        import subprocess
        if self._toolbar and hasattr(self._toolbar, '_output_path') and self._toolbar._output_path:
            path = os.path.normpath(self._toolbar._output_path)
            try:
                if os.path.exists(path):
                    subprocess.run(["explorer.exe", f"/select,{path}"])
                else:
                    os.startfile(os.path.dirname(path))
            except Exception:
                pass

    def _on_open_file(self):
        """结果条：用默认播放器打开视频文件"""
        if self._toolbar and hasattr(self._toolbar, '_output_path') and self._toolbar._output_path:
            path = self._toolbar._output_path
            try:
                os.startfile(path)
            except Exception:
                pass

    # --- 编码完成回调 ---

    def _on_saved(self, output_path: str):
        """编码完成回调（从编码线程调用，通过信号桥安全转发到主线程）"""
        logger.info(f"收到编码完成回调: {output_path}")
        self._saved_bridge.saved.emit(output_path)

    def _handle_saved(self, output_path: str):
        """主线程中处理编码完成"""
        logger.info(f"主线程处理编码完成: {output_path}")
        if output_path:
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            size_str = f"{file_size_mb:.1f}MB"
            logger.info(f"录制已保存: {output_path}")
            ingestion = self._save_material_item(output_path)
            index_ok = ingestion.formal_indexed
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
            if self._toolbar:
                self._toolbar.show_result(output_path, size_str, index_ok=index_ok)
        else:
            logger.error("编码保存失败")
            self._tray.show_notification("保存失败")
            self._hide_toolbar()

        self._tray.set_recording_state(False)
        if self._window_highlighter:
            self._window_highlighter.hide_highlight()
            self._window_highlighter = None
        self._click_highlighter.stop()

    def _save_material_item(self, output_path: str) -> IngestionResult:
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
            self._tray.show_notification("素材已加入素材库")
            if self._toolbar:
                self._toolbar.mark_material_index_saved()
        else:
            self._tray.show_notification("素材索引写入仍然失败，请检查诊断日志")

    @staticmethod
    def _normalize_output_path(path: str | Path) -> str:
        return os.path.normcase(os.path.abspath(str(path)))

    def _show_material_library(self):
        if self._material_library_dialog is None:
            self._material_library_dialog = MaterialLibraryDialog(
                self._library_service,
                pending_service=self._pending_service,
                ingestion_coordinator=self._ingestion_coordinator,
                current_save_dir=self._config.get("save_path", ""),
            )
            if self._initial_migration_result is not None:
                self._material_library_dialog.show_migration_result(self._initial_migration_result)
        else:
            self._material_library_dialog.reload()
        self._material_library_dialog.show()
        self._material_library_dialog.raise_()
        self._material_library_dialog.activateWindow()

    # --- 设置 ---

    def _show_settings(self):
        """显示设置对话框"""
        # 打开设置期间暂停全局快捷键，避免与快捷键录制控件冲突
        self._hotkey.stop_listening()
        self._config_saved_pending = False
        save_path_before = self._config.get("save_path", "")
        dialog = SettingsDialog(self._config)
        dialog.config_saved.connect(self._on_config_saved_pend)
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
        recorder_context = context.get("recorder", {})
        failure = recorder_context.get("last_failure_reason", "")
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

    def _on_exit(self):
        """退出程序"""
        state = self._workflow.get_state()
        if state != RecorderState.IDLE:
            self._workflow.stop()

        # 等待录制停止和编码完成（stop 现在是非阻塞的）
        if not self._workflow.wait_until_idle(timeout=60):
            logger.error("Recorder did not become idle before exit timeout")
        # 确保处理完所有编码完成信号
        from PyQt5.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        if self._window_highlighter:
            self._window_highlighter.hide_highlight()
            self._window_highlighter = None
        self._click_highlighter.stop()

        self._hide_toolbar()
        self._hotkey.stop_listening()
        self._tray.hide()
        self._app.quit()
        logger.info("QuickRec 已退出")


def main():
    """程序入口"""
    try:
        _enable_dpi_awareness()
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        app = QuickRecApp()
        sys.exit(app.run())
    except Exception as e:
        logger.exception(f"QuickRec 异常退出: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
