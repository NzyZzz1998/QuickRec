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

from PyQt5.QtWidgets import QApplication, QDialog

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from config import ConfigManager, ConfigSaveResult
from ui.settings_dialog import SettingsDialog
from unittest.mock import patch


class TestSettingsDialog(unittest.TestCase):
    """SettingsDialog 测试类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigManager.__new__(ConfigManager)
        self.config.config_path = Path(self.temp_dir) / "config.json"
        self.config._config = ConfigManager.defaults.copy()
        self.config._config["save_path"] = self.temp_dir
        self.config._persisted_config = self.config._config.copy()

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
        with patch("ui.settings_dialog.is_autostart_enabled", return_value=False), \
             patch("ui.settings_dialog.enable_autostart", return_value=True), \
             patch("ui.settings_dialog.disable_autostart", return_value=True):
            dialog._save_config()

        self.assertEqual(self.config.get("quality"), "native")
        self.assertEqual(self.config.get("fps"), 60)
        self.assertNotIn("show_countdown", self.config.snapshot())
        self.assertNotIn("mouse_highlight", self.config.snapshot())
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_save_failure_keeps_dialog_open_and_preserves_config(self):
        dialog = SettingsDialog(self.config)
        old_config = self.config.snapshot()
        dialog._combo_audio_source.setCurrentIndex(1)
        with patch.object(
            self.config,
            "save_candidate",
            return_value=ConfigSaveResult(False, "replace", "blocked"),
        ), patch("ui.settings_dialog.is_autostart_enabled", return_value=False):
            dialog._save_config()

        self.assertEqual(dialog.result(), QDialog.Rejected)
        self.assertEqual(self.config.snapshot(), old_config)
        self.assertIn("blocked", dialog._status_label.text())

    def test_config_failure_rolls_back_autostart_change(self):
        dialog = SettingsDialog(self.config)
        dialog._cb_auto_start.setChecked(True)
        with patch.object(
            self.config,
            "save_candidate",
            return_value=ConfigSaveResult(False, "replace", "blocked"),
        ), patch("ui.settings_dialog.is_autostart_enabled", return_value=False), \
             patch("ui.settings_dialog.enable_autostart", return_value=True) as enable, \
             patch("ui.settings_dialog.disable_autostart", return_value=True) as disable:
            dialog._save_config()

        enable.assert_called_once()
        disable.assert_called_once()
        self.assertEqual(dialog.result(), QDialog.Rejected)

    def test_duplicate_shortcuts_are_rejected_before_save(self):
        dialog = SettingsDialog(self.config)
        dialog._shortcut_stop.setText(dialog._shortcut_start.text())
        with patch.object(self.config, "save_candidate") as save_candidate:
            dialog._save_config()

        save_candidate.assert_not_called()
        self.assertIn("不能重复", dialog._status_label.text())
        self.assertEqual(dialog.result(), QDialog.Rejected)

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
