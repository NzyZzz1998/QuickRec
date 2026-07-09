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
        self.assertEqual(dialog.windowTitle(), "QuickRec 设置")

    def test_load_config_values(self):
        """测试加载配置值到控件"""
        dialog = SettingsDialog(self.config)
        self.assertEqual(dialog._edit_save_path.text(), self.temp_dir)
        # v1.2: 画质下拉框使用动态文本，验证 currentData
        self.assertEqual(dialog._combo_quality.currentData(), "high")
        self.assertEqual(dialog._combo_fps.currentText(), "30")

    def test_save_config_updates_values(self):
        """测试保存配置更新值"""
        dialog = SettingsDialog(self.config)
        # 切换到"低"画质
        for i in range(dialog._combo_quality.count()):
            if dialog._combo_quality.itemData(i) == "low":
                dialog._combo_quality.setCurrentIndex(i)
                break
        dialog._combo_fps.setCurrentText("60")
        # v1.2: save_config 会操作注册表，mock掉
        with patch("ui.settings_dialog.enable_autostart"), \
             patch("ui.settings_dialog.disable_autostart"):
            dialog._save_config()

        self.assertEqual(self.config.get("quality"), "low")
        self.assertEqual(self.config.get("fps"), 60)

    def test_diagnostic_controls_exist_and_load_default_dir(self):
        """测试诊断分组控件存在并加载默认目录"""
        dialog = SettingsDialog(self.config)

        self.assertTrue(hasattr(dialog, "_edit_diagnostic_dir"))
        self.assertTrue(hasattr(dialog, "_btn_copy_diagnostic"))
        self.assertTrue(hasattr(dialog, "_btn_open_diagnostic_dir"))
        self.assertTrue(hasattr(dialog, "_btn_export_diagnostic"))
        self.assertEqual(
            dialog._edit_diagnostic_dir.text(),
            str(Path(self.temp_dir) / "QuickRecDiagnostics"),
        )

    def test_save_config_updates_custom_diagnostic_dir(self):
        """测试保存诊断目录"""
        dialog = SettingsDialog(self.config)
        diagnostic_dir = str(Path(self.temp_dir) / "diagnostics")
        dialog._edit_diagnostic_dir.setText(diagnostic_dir)

        with patch("ui.settings_dialog.enable_autostart"), \
             patch("ui.settings_dialog.disable_autostart"):
            dialog._save_config()

        self.assertEqual(self.config.get_diagnostic_dir(), diagnostic_dir)

    def test_diagnostic_action_buttons_emit_current_dir(self):
        """测试诊断操作按钮携带当前输入目录"""
        dialog = SettingsDialog(self.config)
        diagnostic_dir = str(Path(self.temp_dir) / "diagnostics")
        dialog._edit_diagnostic_dir.setText(diagnostic_dir)
        copied = []
        opened = []
        exported = []
        dialog.copy_diagnostic_requested.connect(copied.append)
        dialog.open_diagnostic_dir_requested.connect(opened.append)
        dialog.export_diagnostic_requested.connect(exported.append)

        dialog._btn_copy_diagnostic.click()
        dialog._btn_open_diagnostic_dir.click()
        dialog._btn_export_diagnostic.click()

        self.assertEqual(copied, [diagnostic_dir])
        self.assertEqual(opened, [diagnostic_dir])
        self.assertEqual(exported, [diagnostic_dir])

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
