"""QuickRec Lite 主程序入口。"""

import ctypes
import logging
import os
import sys
from collections.abc import Callable
from typing import Any

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication

from config import ConfigManager
from hotkey.hotkey_manager import HotkeyManager
from recorder.recorder_manager import RecorderManager, RecorderState
from recorder.workflow import RecordingWorkflow
from ui.config_migration_dialog import ConfigMigrationDialog
from ui.settings_dialog import SettingsDialog
from ui.toolbar import RecordingToolbar
from ui.tray_icon import TrayIcon
from utils.disk_checker import DiskChecker, show_disk_warning
from utils.config_migration import LiteConfigMigration
from utils.product_identity import DISPLAY_NAME, PRODUCT_ID
from utils.single_instance import SingleInstanceGuard

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


def ensure_initial_config(
    config: ConfigManager,
    *,
    dialog_factory: Callable[..., Any] = ConfigMigrationDialog,
) -> bool:
    """完成首次白名单迁移；用户取消时阻止本次应用启动。"""
    if not hasattr(config, "config_path"):
        return True
    migration = LiteConfigMigration(config)
    if not migration.should_offer():
        return True
    dialog = dialog_factory(migration)
    return int(dialog.exec_()) == 1


class _SavedBridge(QObject):
    """将编码线程的回调安全转发到 Qt 主线程"""
    saved = pyqtSignal(str)


class _HotkeyBridge(QObject):
    """将 pynput 线程的快捷键回调安全转发到 Qt 主线程"""
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()


class QuickRecApp:
    """QuickRec 应用主类"""

    def __init__(self, instance_guard: SingleInstanceGuard | None = None):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setStyle("Fusion")

        # 初始化模块
        self._config = ConfigManager()
        self._startup_cancelled = not ensure_initial_config(self._config)
        if self._startup_cancelled:
            return
        self._recorder = RecorderManager(self._config, on_saved=self._on_saved)
        self._workflow = RecordingWorkflow(self._recorder)
        self._recorder.set_event_handler(self._workflow.handle_event)
        self._hotkey = HotkeyManager()
        self._toolbar = None
        self._config_saved_pending = False
        self._instance_guard = instance_guard
        self._activation_timer = None

        # 编码完成信号桥
        self._saved_bridge = _SavedBridge()
        self._saved_bridge.saved.connect(self._handle_saved)

        # 快捷键信号桥
        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.start_requested.connect(self._on_start_fullscreen)
        self._hotkey_bridge.stop_requested.connect(self._on_stop_recording)
        self._hotkey_bridge.pause_requested.connect(self._on_pause_resume)

        # 初始化托盘
        self._tray = TrayIcon(
            config=self._config,
            callbacks={
                "start_fullscreen": self._on_start_fullscreen,
                "pause_resume": self._on_pause_resume,
                "stop": self._on_stop_recording,
                "settings": self._show_settings,
                "exit": self._on_exit,
            }
        )

        # 绑定快捷键
        self._setup_hotkeys()
        self._hotkey.start_listening()

        if self._instance_guard is not None:
            self._activation_timer = QTimer()
            self._activation_timer.timeout.connect(self._poll_activation_request)
            self._activation_timer.start(250)

    def run(self):
        """启动应用"""
        if self._startup_cancelled:
            return 0
        self._tray.show()
        logger.info("%s 已启动", DISPLAY_NAME)
        return self._app.exec_()

    def _poll_activation_request(self):
        if self._instance_guard and self._instance_guard.consume_activation_request():
            self._tray.show_notification("应用已在运行，可从托盘继续操作。")

    def _setup_hotkeys(self):
        """绑定快捷键（通过信号桥转发到主线程）"""
        shortcut_start = self._config.get("shortcut_start", "Ctrl+Alt+R")
        shortcut_stop = self._config.get("shortcut_stop", "Ctrl+Alt+S")
        shortcut_pause = self._config.get("shortcut_pause", "Ctrl+Alt+P")

        bindings = [
            (shortcut_start, self._hotkey_bridge.start_requested.emit),
            (shortcut_stop, self._hotkey_bridge.stop_requested.emit),
            (shortcut_pause, self._hotkey_bridge.pause_requested.emit),
        ]
        if hasattr(self._hotkey, "replace_bindings"):
            if not self._hotkey.replace_bindings(bindings):
                logger.error("快捷键候选集合冲突，保留原有效绑定")
                return False
        else:
            for shortcut, callback in bindings:
                self._hotkey.register(shortcut, callback)
        return True

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
        if not self._check_disk_space():
            return

        self._show_toolbar()
        self._do_start_fullscreen()

    def _do_start_fullscreen(self):
        """实际启动全屏录制。"""
        if not self._workflow.start_fullscreen():
            logger.error("全屏录制启动失败")
            self._tray.show_notification("录制启动失败，请检查 FFmpeg 或录制环境")
            self._hide_toolbar()
            return
        if self._toolbar:
            self._toolbar.start_recording_timer()
        self._tray.set_recording_state(True)

    # --- 录制控制 ---

    def _on_stop_recording(self):
        """停止录制"""
        state = self._workflow.get_state()
        if state == RecorderState.IDLE or state == RecorderState.SAVING:
            return

        self._workflow.stop()
        if self._toolbar:
            self._toolbar.show_saving()


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
        self._hide_toolbar()

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

            # v1.1: Toast 通知带"打开文件夹"按钮
            self._tray.show_notification_with_action(
                title="录制已保存",
                msg=f"{os.path.basename(output_path)} ({size_str})",
                action_label="打开文件夹",
                output_path=output_path,
            )

            # v1.1: 工具栏显示结果条
            if self._toolbar:
                self._toolbar.show_result(output_path, size_str)
        else:
            logger.error("编码保存失败")
            self._tray.show_notification("保存失败")
            self._hide_toolbar()

        self._tray.set_recording_state(False)

    # --- 设置 ---

    def _show_settings(self):
        """显示设置对话框"""
        # 打开设置期间暂停全局快捷键，避免与快捷键录制控件冲突
        self._hotkey.stop_listening()
        self._config_saved_pending = False
        dialog = SettingsDialog(self._config)
        dialog.config_saved.connect(self._on_config_saved_pend)
        dialog.exec_()

        # 对话框关闭后，统一重绑定并重新启动快捷键监听
        if self._config_saved_pending:
            # 配置已保存，用新配置重绑定
            if hasattr(self._hotkey, "replace_bindings"):
                self._setup_hotkeys()
            else:
                self._hotkey.unregister_all()
                self._setup_hotkeys()
        self._hotkey.start_listening()

    def _on_config_saved_pend(self):
        """配置保存后标记需要重绑定（不立即操作 pynput，避免对话框内冲突）"""
        self._config_saved_pending = True

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
        self._hide_toolbar()
        self._hotkey.stop_listening()
        self._tray.hide()
        self._app.quit()
        logger.info("QuickRec 已退出")


def run_lite_app(
    *,
    guard: SingleInstanceGuard | None = None,
    app_factory: Callable[..., Any] = QuickRecApp,
) -> int:
    """在 Lite 产品身份下运行应用，并保证内核句柄可靠释放。"""
    active_guard = guard or SingleInstanceGuard(PRODUCT_ID)
    try:
        if not active_guard.acquire():
            return 0
        app = app_factory(instance_guard=active_guard)
        return int(app.run())
    finally:
        active_guard.close()


def main():
    """程序入口"""
    try:
        _enable_dpi_awareness()
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        sys.exit(run_lite_app())
    except Exception as e:
        logger.exception(f"QuickRec 异常退出: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
