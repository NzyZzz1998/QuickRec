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
import sys

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication

from config import ConfigManager
from hotkey.hotkey_manager import HotkeyManager
from recorder.recorder_manager import RecorderManager, RecorderState, RecordMode
from recorder.workflow import RecordingWorkflow
from ui.area_selector import AreaSelector
from ui.click_highlighter import ClickHighlighter
from ui.settings_dialog import SettingsDialog
from ui.toolbar import RecordingToolbar
from ui.tray_icon import TrayIcon
from ui.window_highlighter import WindowHighlighter
from ui.window_selector import WindowSelector
from utils.disk_checker import DiskChecker, show_disk_warning

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


class QuickRecApp:
    """QuickRec 应用主类"""

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setStyle("Fusion")

        # 初始化模块
        self._config = ConfigManager()
        self._recorder = RecorderManager(self._config, on_saved=self._on_saved)
        self._workflow = RecordingWorkflow(self._recorder)
        self._recorder.set_event_handler(self._workflow.handle_event)
        self._hotkey = HotkeyManager()
        self._toolbar = None
        self._config_saved_pending = False

        # v1.2 新增模块
        self._click_highlighter = ClickHighlighter()
        self._window_highlighter = None
        self._window_selector = None

        # 编码完成信号桥
        self._saved_bridge = _SavedBridge()
        self._saved_bridge.saved.connect(self._handle_saved)

        # 快捷键信号桥
        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.start_requested.connect(self._on_start_fullscreen)
        self._hotkey_bridge.stop_requested.connect(self._on_stop_recording)
        self._hotkey_bridge.pause_requested.connect(self._on_pause_resume)
        self._hotkey_bridge.area_requested.connect(self._on_start_region)
        self._hotkey_bridge.window_requested.connect(self._on_start_window)

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
                "exit": self._on_exit,
            }
        )

        # 绑定快捷键
        self._setup_hotkeys()
        self._hotkey.start_listening()

    def run(self):
        """启动应用"""
        self._tray.show()
        logger.info("QuickRec 已启动")
        return self._app.exec_()

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
        if self._window_highlighter:
            self._window_highlighter.hide_highlight()
            self._window_highlighter = None
        self._click_highlighter.stop()

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
