"""
系统托盘模块

管理系统托盘图标和菜单。
"""

import os
import webbrowser
from threading import Thread

from PyQt5.QtWidgets import QApplication

import pystray
from PIL import Image, ImageDraw


class TrayIcon:
    """系统托盘图标"""

    def __init__(self, config=None, callbacks=None):
        """
        初始化托盘图标

        Args:
            config: ConfigManager 实例
            callbacks: 回调函数映射 {"start": func, "settings": func, "exit": func}
        """
        self._config = config
        self._callbacks = callbacks or {}
        self._icon = None
        self._menu_items = self._build_menu()

    def _create_icon_image(self):
        """创建默认托盘图标"""
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        dc = ImageDraw.Draw(img)

        # 绘制一个简单的圆形录制图标
        dc.ellipse([8, 8, 56, 56], fill="#e74c3c", outline="#c0392b", width=2)
        # 内圆
        dc.ellipse([20, 20, 44, 44], fill="#c0392b")

        return img

    def _build_menu(self):
        """构建托盘菜单"""
        return pystray.Menu(
            pystray.MenuItem("▶ 开始录制", self._on_start),
            pystray.MenuItem("⚙ 设置", self._on_settings),
            pystray.MenuItem("📁 打开保存文件夹", self._on_open_folder),
            pystray.MenuItem("---", None, visible=False),  # 占位
            pystray.MenuItem("✕ 退出", self._on_exit),
        )

    def _on_start(self, icon, item):
        """开始录制回调"""
        if "start" in self._callbacks:
            self._callbacks["start"]()

    def _on_settings(self, icon, item):
        """设置回调"""
        if "settings" in self._callbacks:
            self._callbacks["settings"]()

    def _on_open_folder(self, icon, item):
        """打开保存文件夹"""
        if self._config:
            path = self._config.get("save_path", "")
            if path and os.path.exists(path):
                webbrowser.open(path)

    def _on_exit(self, icon, item):
        """退出程序"""
        if "exit" in self._callbacks:
            self._callbacks["exit"]()
        if self._icon:
            self._icon.stop()
        QApplication.quit()

    def show(self):
        """显示托盘图标"""
        if self._icon is None:
            self._icon = pystray.Icon(
                name="QuickRec",
                icon=self._create_icon_image(),
                title="QuickRec - 录屏工具",
                menu=self._menu_items,
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

    def set_menu(self, menu_items):
        """设置托盘菜单（暂不实现动态菜单）"""
        pass