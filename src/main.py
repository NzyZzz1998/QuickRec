"""
QuickRec 主程序入口

初始化所有模块，启动应用。
"""

import sys
import logging

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt

from config import ConfigManager
from recorder.recorder_manager import RecorderManager, RecorderState
from ui.area_selector import AreaSelector
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
        self._recorder = RecorderManager(self._config)
        self._hotkey = HotkeyManager()
        self._toolbar = None
        self._area_selector = None

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
        state = self._recorder.get_state()
        if state != RecorderState.IDLE:
            return

        # 显示区域选择器
        self._area_selector = AreaSelector()
        self._area_selector.region_selected.connect(self._on_region_selected)
        self._area_selector.cancelled.connect(self._on_area_cancelled)
        self._area_selector.show_fullscreen()

    def _on_region_selected(self, x, y, w, h):
        """区域选择完成，开始录制"""
        region = (x, y, w, h)
        if not self._recorder.start_region(region):
            logger.error("录制启动失败")
            return
        self._show_toolbar()

    def _on_area_cancelled(self):
        """区域选择取消"""
        logger.info("区域选择已取消")

    def _on_stop_recording(self):
        """停止录制"""
        if self._recorder.get_state() == RecorderState.IDLE:
            return

        output_path = self._recorder.stop()
        if output_path:
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
            self._recorder.stop()
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

    def _on_exit(self):
        """退出程序"""
        # 如果正在录制，先停止
        if self._recorder.get_state() != RecorderState.IDLE:
            self._recorder.stop()

        self._hide_toolbar()
        self._hotkey.unregister_all()
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