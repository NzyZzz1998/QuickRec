"""
TrayIcon 单元测试

注：pystray 在无桌面环境时有限制，主要测试基础功能。
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

        self.assertIn("打开工作台", labels)
        self.assertIn("素材库", labels)
        self.assertNotIn("最近录制", labels)
        self.assertIn("诊断", labels)
        self.assertIn("复制诊断信息", labels)
        self.assertIn("打开日志目录", labels)
        self.assertIn("导出诊断文件", labels)

    def test_recording_menu_contains_diagnostic_entries(self):
        tray = TrayIcon()

        menu = tray._build_recording_menu()
        labels = [item.text for item in menu.items if hasattr(item, "text")]

        self.assertIn("打开工作台", labels)
        self.assertIn("素材库", labels)
        self.assertNotIn("最近录制", labels)
        self.assertIn("诊断", labels)
        self.assertIn("复制诊断信息", labels)
        self.assertIn("打开日志目录", labels)
        self.assertIn("导出诊断文件", labels)

    def test_menu_labels_do_not_mix_emoji_or_character_icons(self):
        tray = TrayIcon()
        labels = [
            item.text
            for menu in (tray._build_idle_menu(), tray._build_recording_menu())
            for item in menu.items
            if hasattr(item, "text")
        ]

        for symbol in ("▶", "⏸", "⏹", "✕", "▢", "🖥", "⚙", "📁"):
            self.assertFalse(any(symbol in label for label in labels), symbol)

    def test_diagnostic_callbacks_are_forwarded_by_signal_bridge(self):
        calls = []
        tray = TrayIcon(callbacks={
            "material_library": lambda: calls.append("material"),
            "copy_diagnostic": lambda: calls.append("copy"),
            "open_diagnostic_dir": lambda: calls.append("open"),
            "export_diagnostic": lambda: calls.append("export"),
        })

        tray._handle_material_library()
        tray._handle_copy_diagnostic()
        tray._handle_open_diagnostic_dir()
        tray._handle_export_diagnostic()

        self.assertEqual(calls, ["material", "copy", "open", "export"])

    def test_workbench_routes_are_forwarded_by_signal_bridge(self):
        calls = []
        tray = TrayIcon(callbacks={
            "open_workbench": lambda: calls.append("recording"),
            "settings": lambda: calls.append("settings"),
            "material_library": lambda: calls.append("materials"),
            "diagnostics": lambda: calls.append("diagnostics"),
        })

        tray._handle_open_workbench()
        tray._handle_settings()
        tray._handle_material_library()
        tray._handle_diagnostics()

        self.assertEqual(calls, ["recording", "settings", "materials", "diagnostics"])

    def test_exit_stops_pystray_before_quitting_qapplication(self):
        calls = []

        class FakeIcon:
            def stop(self):
                calls.append("stop")

        tray = TrayIcon(callbacks={"exit": lambda: calls.append("callback")})
        tray._icon = FakeIcon()

        with patch(
            "ui.tray_icon.QApplication.quit",
            side_effect=lambda: calls.append("quit"),
        ):
            tray._handle_exit()

        self.assertEqual(calls, ["callback", "stop", "quit"])


if __name__ == "__main__":
    unittest.main()
