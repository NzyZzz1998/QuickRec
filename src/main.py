"""
QuickRec 主程序入口

初始化所有模块，启动应用。
"""

import sys
import logging
import time

from PyQt5.QtWidgets import QApplication, QMessageBox

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
        """绑定快捷键"""
        shortcut_start = self._config.get("shortcut_start", "Ctrl+Shift+R")
        shortcut_stop = self._config.get("shortcut_stop", "Ctrl+Shift+S")
        shortcut_pause = self._config.get("shortcut_pause", "Ctrl+Shift+P")

        self._hotkey.register(shortcut_start, self._on_start_recording)
        self._hotkey.register(shortcut_stop, self._on_stop_recording)
        self._hotkey.register(shortcut_pause, self._on_pause_resume)

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
        if self._recorder.get_state() == RecorderState.IDLE:
            return

        output_path = self._recorder.stop()
        if self._recorder.is_saving():
            # 正在后台编码，toolbar 显示"保存中..."
            if self._toolbar:
                self._toolbar.show_saving()
        elif output_path:
            logger.info(f"录制已保存: {output_path}")
            self._tray.show_notification(f"录制已保存\n{output_path}")
            self._hide_toolbar()

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
        if self._recorder.get_state() != RecorderState.IDLE:
            self._recorder.stop(cancel=True)
        self._tray.show_notification("录制已取消")
        self._hide_toolbar()

    def _on_saved(self, output_path: str):
        """编码完成回调（从编码线程调用，需通过 QTimer 转到主线程）"""
        # 使用 QTimer 在主线程中执行 UI 操作
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._handle_saved(output_path))

    def _handle_saved(self, output_path: str):
        """主线程中处理编码完成"""
        if output_path:
            logger.info(f"录制已保存: {output_path}")
            self._tray.show_notification(f"录制已保存\n{output_path}")
        else:
            logger.error("编码保存失败")
            self._tray.show_notification("保存失败")
        self._hide_toolbar()

    def _show_settings(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self._config)
        dialog.config_saved.connect(self._on_config_saved)
        dialog.exec_()

    def _on_config_saved(self):
        """配置保存后重新绑定快捷键"""
        self._hotkey.unregister_all()
        self._setup_hotkeys()
        self._hotkey.start_listening()

    def _on_exit(self):
        """退出程序"""
        if self._recorder.get_state() != RecorderState.IDLE:
            self._recorder.stop()

        # 等待编码完成
        for _ in range(50):  # 最多等 5 秒
            if self._recorder.get_state() == RecorderState.IDLE:
                break
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            time.sleep(0.1)

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