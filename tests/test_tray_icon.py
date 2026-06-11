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


if __name__ == "__main__":
    unittest.main()