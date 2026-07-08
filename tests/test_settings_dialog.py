"""
SettingsDialog 单元测试
"""

import os
import tempfile
import unittest

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from config import ConfigManager
from ui.settings_dialog import SettingsDialog
from unittest.mock import patch


class TestSettingsDialog(unittest.TestCase):
    """SettingsDialog 测试类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigManager.__new__(ConfigManager)
        self.config._config_path = os.path.join(self.temp_dir, "config.json")
        self.config._config = ConfigManager.defaults.copy()
        self.config._config["save_path"] = self.temp_dir

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dialog_creation(self):
        """测试对话框创建"""
        dialog = SettingsDialog(self.config)
        self.assertEqual(dialog.windowTitle(), "QuickRec Lite 设置")

    def test_load_config_values(self):
        """测试加载配置值到控件"""
        dialog = SettingsDialog(self.config)
        self.assertEqual(dialog._edit_save_path.text(), self.temp_dir)
        self.assertFalse(hasattr(dialog, "_combo_quality"))
        self.assertFalse(hasattr(dialog, "_combo_fps"))
        self.assertFalse(hasattr(dialog, "_shortcut_area"))
        self.assertFalse(hasattr(dialog, "_shortcut_window"))
        self.assertFalse(hasattr(dialog, "_cb_countdown"))
        self.assertFalse(hasattr(dialog, "_cb_mouse_highlight"))

    def test_save_config_updates_values(self):
        """测试保存配置更新值"""
        dialog = SettingsDialog(self.config)
        # v1.2: save_config 会操作注册表，mock掉
        with patch("ui.settings_dialog.enable_autostart"), \
             patch("ui.settings_dialog.disable_autostart"):
            dialog._save_config()

        self.assertEqual(self.config.get("quality"), "native")
        self.assertEqual(self.config.get("fps"), 60)
        self.assertEqual(self.config.get("show_countdown"), False)
        self.assertEqual(self.config.get("mouse_highlight"), False)

    def test_browse_updates_path(self):
        """测试 Browse 更新路径（仅检查可设置文本）"""
        dialog = SettingsDialog(self.config)
        dialog._edit_save_path.setText("/new/path")
        self.assertEqual(dialog._edit_save_path.text(), "/new/path")

    def test_signal_defined(self):
        """测试信号定义"""
        dialog = SettingsDialog(self.config)
        self.assertTrue(hasattr(dialog, 'config_saved'))


if __name__ == "__main__":
    unittest.main()
