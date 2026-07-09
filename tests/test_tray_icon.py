"""
TrayIcon 单元测试

注：pystray 在无桌面环境时有限制，主要测试基础功能。
"""

import os
import tempfile
import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ui.tray_icon import TrayIcon


class TestTrayIcon(unittest.TestCase):
    """TrayIcon 测试类"""

    def test_creation(self):
        """测试创建 TrayIcon"""
        tray = TrayIcon()
        self.assertIsNone(tray._icon)

    def test_creation_with_config_and_callbacks(self):
        """测试带配置和回调创建"""
        config = {"save_path": tempfile.gettempdir()}
        callbacks = {"start": lambda: None, "exit": lambda: None}
        tray = TrayIcon(config=config, callbacks=callbacks)
        self.assertEqual(tray._callbacks, callbacks)

    def test_icon_image_creation(self):
        """测试图标图片创建"""
        tray = TrayIcon()
        img = tray._create_icon_image()
        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, "RGBA")

    def test_idle_menu_contains_diagnostic_entries(self):
        tray = TrayIcon()

        menu = tray._build_idle_menu()
        labels = [item.text for item in menu.items if hasattr(item, "text")]

        self.assertIn("复制诊断信息", labels)
        self.assertIn("打开日志目录", labels)
        self.assertIn("导出诊断文件", labels)

    def test_recording_menu_contains_diagnostic_entries(self):
        tray = TrayIcon()

        menu = tray._build_recording_menu()
        labels = [item.text for item in menu.items if hasattr(item, "text")]

        self.assertIn("复制诊断信息", labels)
        self.assertIn("打开日志目录", labels)
        self.assertIn("导出诊断文件", labels)

    def test_diagnostic_callbacks_are_forwarded_by_signal_bridge(self):
        calls = []
        tray = TrayIcon(callbacks={
            "copy_diagnostic": lambda: calls.append("copy"),
            "open_diagnostic_dir": lambda: calls.append("open"),
            "export_diagnostic": lambda: calls.append("export"),
        })

        tray._handle_copy_diagnostic()
        tray._handle_open_diagnostic_dir()
        tray._handle_export_diagnostic()

        self.assertEqual(calls, ["copy", "open", "export"])


if __name__ == "__main__":
    unittest.main()
