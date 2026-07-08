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

    def test_lite_idle_menu_hides_region_and_window_recording(self):
        """Lite v0 只暴露全屏录制入口"""
        tray = TrayIcon()
        labels = [item.text for item in tray._build_idle_menu()]

        self.assertTrue(any("全屏录制" in label for label in labels))
        self.assertFalse(any("区域录制" in label for label in labels))
        self.assertFalse(any("窗口录制" in label for label in labels))


if __name__ == "__main__":
    unittest.main()
