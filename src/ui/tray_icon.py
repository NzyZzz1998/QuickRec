"""
系统托盘模块

管理系统托盘图标和菜单。

关键设计：pystray 的运行循环在独立线程，回调也在该线程执行。
不能直接在 pystray 回调中操作 Qt 组件，必须通过信号转发到 Qt 主线程。

v1.1 新增：动态菜单切换 + Toast 通知增强。
"""

import os
import subprocess
import logging

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger("QuickRec")


class _SignalBridge(QObject):
    """将 pystray 线程的回调转发到 Qt 主线程"""

    start_fullscreen_requested = pyqtSignal()
    start_region_requested = pyqtSignal()
    start_window_requested = pyqtSignal()    # v1.2 新增
    pause_resume_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    exit_requested = pyqtSignal()


class TrayIcon:
    """系统托盘图标

    v1.1 新增：
    - 动态菜单切换（空闲/录制中/暂停）
    - Toast 通知增强（winotify 降级链）
    - 录制状态管理
    """

    def __init__(self, config=None, callbacks=None):
        """
        Args:
            config: ConfigManager 实例
            callbacks: 回调函数映射
                "start_fullscreen": func,  — 全屏录制
                "start_region": func,      — 区域录制（v1.1 新增）
                "pause_resume": func,      — 暂停/继续（v1.1 新增）
                "stop": func,              — 停止录制（v1.1 新增）
                "settings": func,
                "exit": func,
        """
        self._config = config
        self._callbacks = callbacks or {}
        self._icon = None

        # v1.1: 录制状态标志
        self._is_recording = False
        self._is_paused = False

        # 信号桥：将 pystray 线程回调转发到 Qt 主线程
        self._bridge = _SignalBridge()
        self._bridge.start_fullscreen_requested.connect(self._handle_start_fullscreen)
        self._bridge.start_region_requested.connect(self._handle_start_region)
        self._bridge.start_window_requested.connect(self._handle_start_window)
        self._bridge.pause_resume_requested.connect(self._handle_pause_resume)
        self._bridge.stop_requested.connect(self._handle_stop)
        self._bridge.settings_requested.connect(self._handle_settings)
        self._bridge.exit_requested.connect(self._handle_exit)

    def _create_icon_image(self):
        """创建默认托盘图标"""
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        dc = ImageDraw.Draw(img)
        dc.ellipse([8, 8, 56, 56], fill="#e74c3c", outline="#c0392b", width=2)
        dc.ellipse([20, 20, 44, 44], fill="#c0392b")
        return img

    def _build_idle_menu(self):
        """构建空闲状态菜单"""
        return pystray.Menu(
            pystray.MenuItem("▶ 全屏录制", self._on_start_fullscreen),
            pystray.MenuItem("▢ 区域录制", self._on_start_region),
            pystray.MenuItem("🖥 窗口录制", self._on_start_window),
            pystray.MenuItem("⚙ 设置", self._on_settings),
            pystray.MenuItem("📁 打开保存文件夹", self._on_open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("✕ 退出", self._on_exit),
        )

    def _build_recording_menu(self):
        """构建录制中菜单"""
        # 暂停/继续按钮：根据暂停状态切换文字
        pause_text = "▶ 继续录制" if self._is_paused else "⏸ 暂停录制"
        return pystray.Menu(
            pystray.MenuItem(pause_text, self._on_pause_resume),
            pystray.MenuItem("⏹ 停止录制", self._on_stop),
            pystray.MenuItem("⚙ 设置", self._on_settings),
            pystray.MenuItem("📁 打开保存文件夹", self._on_open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("✕ 退出", self._on_exit),
        )

    def set_recording_state(self, recording: bool, paused: bool = False):
        """切换菜单状态：空闲菜单 ↔ 录制中菜单

        Args:
            recording: 是否正在录制
            paused: 是否暂停
        """
        self._is_recording = recording
        self._is_paused = paused
        self._rebuild_menu()

    def _rebuild_menu(self):
        """重建并更新菜单"""
        if self._icon:
            if self._is_recording:
                self._icon.menu = self._build_recording_menu()
            else:
                self._icon.menu = self._build_idle_menu()
            self._icon.update_menu()

    # --- pystray 线程回调（只发信号，不操作 Qt） ---

    def _on_start_fullscreen(self, icon, item):
        self._bridge.start_fullscreen_requested.emit()

    def _on_start_region(self, icon, item):
        self._bridge.start_region_requested.emit()

    def _on_start_window(self, icon, item):
        self._bridge.start_window_requested.emit()

    def _on_pause_resume(self, icon, item):
        self._bridge.pause_resume_requested.emit()

    def _on_stop(self, icon, item):
        self._bridge.stop_requested.emit()

    def _on_settings(self, icon, item):
        self._bridge.settings_requested.emit()

    def _on_exit(self, icon, item):
        self._bridge.exit_requested.emit()

    # --- Qt 主线程处理 ---

    def _handle_start_fullscreen(self):
        if "start_fullscreen" in self._callbacks:
            self._callbacks["start_fullscreen"]()

    def _handle_start_region(self):
        if "start_region" in self._callbacks:
            self._callbacks["start_region"]()

    def _handle_start_window(self):
        if "start_window" in self._callbacks:
            self._callbacks["start_window"]()

    def _handle_pause_resume(self):
        if "pause_resume" in self._callbacks:
            self._callbacks["pause_resume"]()

    def _handle_stop(self):
        if "stop" in self._callbacks:
            self._callbacks["stop"]()

    def _handle_settings(self):
        if "settings" in self._callbacks:
            self._callbacks["settings"]()

    def _handle_exit(self):
        if "exit" in self._callbacks:
            self._callbacks["exit"]()
        QTimer.singleShot(0, self._stop_icon)
        QApplication.quit()

    def _stop_icon(self):
        """安全停止 pystray 图标"""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _on_open_folder(self, icon, item):
        """打开保存文件夹（纯 IO 操作，无需转发线程）"""
        if self._config:
            path = self._config.get("save_path", "")
            if path and os.path.exists(path):
                subprocess.run(["explorer.exe", path])

    def show(self):
        """显示托盘图标"""
        if self._icon is None:
            self._icon = pystray.Icon(
                name="QuickRec",
                icon=self._create_icon_image(),
                title="QuickRec - 录屏工具",
                menu=self._build_idle_menu(),
            )
            self._icon.run_detached()

    def hide(self):
        """隐藏托盘图标"""
        if self._icon:
            self._icon.visible = False

    def show_notification(self, msg: str, title: str = "QuickRec"):
        """弹出系统通知"""
        if self._icon:
            self._icon.notify(msg, title)

    def show_notification_with_action(self, title: str, msg: str,
                                       action_label: str = "打开文件夹",
                                       output_path: str = ""):
        """显示带操作按钮的 Toast 通知

        降级链：winotify → pystray.notify()
        """
        # 优先使用 winotify（Windows 10/11 Toast 通知）
        try:
            from winotify import Notification
            toast = Notification(
                app_id="QuickRec",
                title=title,
                msg=msg,
            )
            if output_path:
                # 添加"打开文件夹"按钮。
                # winotify 的 action 使用 protocol 激活，launch 必须是 URI，
                # 因此用 file:/// 目录 URI 打开视频所在文件夹（无法选中具体文件）。
                folder = os.path.dirname(output_path)
                try:
                    from pathlib import Path
                    launch_uri = Path(folder).as_uri()
                except Exception:
                    launch_uri = folder
                toast.add_actions(label=action_label, launch=launch_uri)
            toast.show()
            logger.info(f"winotify 通知已发送: {title}")
            return
        except Exception as e:
            logger.debug(f"winotify 不可用，降级为 pystray 通知: {e}")

        # 降级：pystray 纯文本通知
        self.show_notification(msg, title)