"""
QuickRec 主程序入口

初始化所有模块，启动应用。
"""

import sys
import logging
import time

from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from config import ConfigManager
from recorder.recorder_manager import RecorderManager, RecorderState
from ui.toolbar import RecordingToolbar
from ui.settings_dialog import SettingsDialog
from ui.tray_icon import TrayIcon
from hotkey.hotkey_manager import HotkeyManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("QuickRec")


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

    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)

        # 初始化模块
        self._config = ConfigManager()
        self._recorder = RecorderManager(self._config, on_saved=self._on_saved)
        self._hotkey = HotkeyManager()
        self._toolbar = None
        self._config_saved_pending = False

        # 编码完成信号桥：从编码线程安全转发到主线程
        self._saved_bridge = _SavedBridge()
        self._saved_bridge.saved.connect(self._handle_saved)

        # 快捷键信号桥：从 pynput 线程安全转发到主线程
        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.start_requested.connect(self._on_start_recording)
        self._hotkey_bridge.stop_requested.connect(self._on_stop_recording)
        self._hotkey_bridge.pause_requested.connect(self._on_pause_resume)

        # 初始化托盘
        self._tray = TrayIcon(
            config=self._config,
            callbacks={
                "start": self._on_start_recording,
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

        self._hotkey.register(shortcut_start, self._hotkey_bridge.start_requested.emit)
        self._hotkey.register(shortcut_stop, self._hotkey_bridge.stop_requested.emit)
        self._hotkey.register(shortcut_pause, self._hotkey_bridge.pause_requested.emit)

    def _on_start_recording(self):
        """开始全屏录制"""
        if self._recorder.get_state() != RecorderState.IDLE:
            return

        if not self._recorder.start_fullscreen():
            logger.error("全屏录制启动失败")
            return
        self._show_toolbar()

    def _on_stop_recording(self):
        """停止录制"""
        state = self._recorder.get_state()
        if state == RecorderState.IDLE or state == RecorderState.SAVING:
            return

        self._recorder.stop()
        # stop() 现在是非阻塞的，后台线程会处理录制结束和编码启动
        # 状态从 RECORDING/PAUSED → STOPPING → SAVING（由后台线程切换）
        # 工具栏先显示"保存中..."，编码完成后 on_saved 回调会隐藏工具栏
        if self._toolbar:
            self._toolbar.show_saving()

    def _on_pause_resume(self):
        """暂停/恢复录制"""
        state = self._recorder.get_state()
        if state == RecorderState.RECORDING:
            self._recorder.pause()
            if self._toolbar:
                self._toolbar.set_paused(True)
        elif state == RecorderState.PAUSED:
            self._recorder.resume()
            if self._toolbar:
                self._toolbar.set_paused(False)

    def _show_toolbar(self):
        """显示录制工具栏"""
        self._toolbar = RecordingToolbar()
        self._toolbar.paused.connect(self._on_pause_resume)
        self._toolbar.resumed.connect(self._on_pause_resume)
        self._toolbar.stopped.connect(self._on_stop_recording)
        self._toolbar.cancelled.connect(self._on_cancel_recording)
        self._toolbar.start_countdown()
        self._toolbar.show()

    def _hide_toolbar(self):
        """隐藏录制工具栏"""
        if self._toolbar:
            self._toolbar.stop_countdown()
            self._toolbar.close()
            self._toolbar = None

    def _on_cancel_recording(self):
        """取消录制"""
        state = self._recorder.get_state()
        if state != RecorderState.IDLE and state != RecorderState.SAVING:
            self._recorder.stop(cancel=True)
        self._tray.show_notification("录制已取消")
        self._hide_toolbar()

    def _on_saved(self, output_path: str):
        """编码完成回调（从编码线程调用，通过信号桥安全转发到主线程）"""
        logger.info(f"收到编码完成回调: {output_path}")
        self._saved_bridge.saved.emit(output_path)

    def _handle_saved(self, output_path: str):
        """主线程中处理编码完成"""
        logger.info(f"主线程处理编码完成: {output_path}")
        if output_path:
            logger.info(f"录制已保存: {output_path}")
            self._tray.show_notification(f"录制已保存\n{output_path}")
        else:
            logger.error("编码保存失败")
            self._tray.show_notification("保存失败")
        logger.info("隐藏工具栏")
        self._hide_toolbar()

    def _show_settings(self):
        """显示设置对话框"""
        # 打开设置期间暂停全局快捷键，避免与快捷键录制控件冲突
        self._hotkey.stop_listening()
        self._config_saved_pending = False  # 标记是否需要重绑定
        dialog = SettingsDialog(self._config)
        dialog.config_saved.connect(self._on_config_saved_pend)
        result = dialog.exec_()

        # 对话框关闭后，统一重绑定并重新启动快捷键监听
        if self._config_saved_pending:
            # 配置已保存，用新配置重绑定
            self._hotkey.unregister_all()
            self._setup_hotkeys()
        self._hotkey.start_listening()

    def _on_config_saved_pend(self):
        """配置保存后标记需要重绑定（不立即操作 pynput，避免对话框内冲突）"""
        self._config_saved_pending = True

    def _on_exit(self):
        """退出程序"""
        state = self._recorder.get_state()
        if state != RecorderState.IDLE:
            self._recorder.stop()

        # 等待录制停止和编码完成（stop 现在是非阻塞的）
        self._recorder.wait_until_idle(timeout=60)
        # 确保处理完所有编码完成信号
        from PyQt5.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        self._hide_toolbar()
        self._hotkey.stop_listening()
        self._tray.hide()
        self._app.quit()
        logger.info("QuickRec 已退出")


def main():
    """程序入口"""
    try:
        app = QuickRecApp()
        sys.exit(app.run())
    except Exception as e:
        logger.exception(f"QuickRec 异常退出: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()