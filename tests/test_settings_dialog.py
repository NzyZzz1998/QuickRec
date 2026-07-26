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

from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QApplication, QMessageBox

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from unittest.mock import Mock, patch

from config import ConfigManager, ConfigSaveResult
from ui.settings_dialog import SettingsDialog
from services.capture_capability import (
    CaptureReadiness,
    DisplayEnvironment,
    EnvironmentFingerprint,
    SelfTestResult,
)
from services.capture_capability_runtime import CapabilityInspection


class TestSettingsDialog(unittest.TestCase):
    """SettingsDialog 测试类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigManager.__new__(ConfigManager)
        self.config.config_path = Path(self.temp_dir) / "config.json"
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
             patch("ui.settings_dialog.disable_autostart"), \
             patch("ui.settings_dialog.is_autostart_enabled", return_value=False):
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
             patch("ui.settings_dialog.disable_autostart"), \
             patch("ui.settings_dialog.is_autostart_enabled", return_value=False):
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

    def test_save_failure_keeps_dialog_open_and_candidate_uncommitted(self):
        """持久化失败时不提交内存配置、不发成功信号、不关闭窗口"""
        dialog = SettingsDialog(self.config)
        dialog._combo_fps.setCurrentText("60")
        saved = []
        dialog.config_saved.connect(lambda: saved.append(True))
        failure = ConfigSaveResult(False, "replace", "replace failed", "")

        with patch.object(self.config, "save_candidate", return_value=failure), \
             patch.object(dialog, "accept") as accept, \
             patch.object(QMessageBox, "critical") as critical, \
             patch("ui.settings_dialog.is_autostart_enabled", return_value=False):
            dialog._save_config()

        self.assertEqual(self.config.get("fps"), 30)
        self.assertEqual(saved, [])
        accept.assert_not_called()
        critical.assert_called_once()
        self.assertTrue(dialog._btn_save.isEnabled())

    def test_autostart_failure_does_not_persist_candidate(self):
        """注册表副作用失败时不保存候选配置"""
        dialog = SettingsDialog(self.config)
        dialog._cb_auto_start.setChecked(True)
        dialog._combo_fps.setCurrentText("60")

        with patch("ui.settings_dialog.is_autostart_enabled", return_value=False), \
             patch("ui.settings_dialog.enable_autostart", return_value=False), \
             patch.object(self.config, "save_candidate") as save_candidate, \
             patch.object(QMessageBox, "critical"):
            dialog._save_config()

        save_candidate.assert_not_called()
        self.assertFalse(self.config.get("auto_start"))
        self.assertEqual(self.config.get("fps"), 30)

    def test_persistence_failure_rolls_back_autostart_side_effect(self):
        """注册表变更成功但配置失败时恢复原注册表状态"""
        dialog = SettingsDialog(self.config)
        dialog._cb_auto_start.setChecked(True)
        failure = ConfigSaveResult(False, "replace", "replace failed", "")

        with patch("ui.settings_dialog.is_autostart_enabled", return_value=False), \
             patch("ui.settings_dialog.enable_autostart", return_value=True) as enable, \
             patch("ui.settings_dialog.disable_autostart", return_value=True) as disable, \
             patch.object(self.config, "save_candidate", return_value=failure), \
             patch.object(QMessageBox, "critical"):
            dialog._save_config()

        enable.assert_called_once()
        disable.assert_called_once()
        self.assertFalse(self.config.get("auto_start"))

    def test_successful_save_commits_candidate_then_accepts(self):
        """保存成功后提交候选配置、发信号并关闭窗口"""
        dialog = SettingsDialog(self.config)
        dialog._combo_fps.setCurrentText("60")
        saved = []
        dialog.config_saved.connect(lambda: saved.append(True))

        with patch("ui.settings_dialog.is_autostart_enabled", return_value=False), \
             patch.object(dialog, "accept") as accept:
            dialog._save_config()

        self.assertEqual(self.config.get("fps"), 60)
        self.assertEqual(saved, [True])
        accept.assert_called_once()

    def test_embedded_settings_uses_draft_without_closing_after_save(self):
        page = SettingsDialog(self.config, embedded=True)
        page._combo_fps.setCurrentText("60")

        with patch("ui.settings_dialog.is_autostart_enabled", return_value=False), \
             patch.object(page, "accept") as accept:
            saved = page.save_changes()

        self.assertTrue(saved)
        self.assertFalse(page.is_dirty)
        self.assertEqual(self.config.get("fps"), 60)
        accept.assert_not_called()
        self.assertTrue(page._diagnostic_group.isHidden())

    def test_embedded_settings_discard_restores_persisted_values(self):
        page = SettingsDialog(self.config, embedded=True)
        page._combo_fps.setCurrentText("60")
        self.assertTrue(page.is_dirty)

        page.discard_changes()

        self.assertFalse(page.is_dirty)
        self.assertEqual(page._combo_fps.currentText(), "30")

    def test_embedded_settings_disables_recording_sensitive_controls(self):
        page = SettingsDialog(self.config, embedded=True)

        page.set_recording_active(True)

        self.assertFalse(page._edit_save_path.isEnabled())
        self.assertFalse(page._combo_quality.isEnabled())
        self.assertFalse(page._combo_fps.isEnabled())
        self.assertFalse(page._combo_audio_source.isEnabled())

    def test_embedded_settings_does_not_overwrite_diagnostic_page_value(self):
        page = SettingsDialog(self.config, embedded=True)
        diagnostic_dir = str(Path(self.temp_dir) / "new-diagnostics")
        diagnostic_candidate = self.config.snapshot()
        diagnostic_candidate["diagnostic_dir"] = diagnostic_dir
        diagnostic_candidate["diagnostic_dir_customized"] = True
        self.assertTrue(self.config.save_candidate(diagnostic_candidate).ok)
        page._combo_fps.setCurrentText("60")

        with patch("ui.settings_dialog.is_autostart_enabled", return_value=False):
            self.assertTrue(page.save_changes())

        self.assertEqual(self.config.get_diagnostic_dir(), diagnostic_dir)

    def test_embedded_settings_scroll_area_does_not_overlap_footer(self):
        page = SettingsDialog(self.config, embedded=True)
        page.resize(776, 580)
        page.show()
        QApplication.processEvents()

        scroll_bottom = page._scroll_area.mapTo(
            page,
            QPoint(0, page._scroll_area.height()),
        ).y()
        save_top = page._btn_save.mapTo(page, QPoint(0, 0)).y()

        self.assertLessEqual(scroll_bottom, save_top)
        self.assertGreater(page._scroll_area.verticalScrollBar().maximum(), 0)

    def _capture_runtime(self, *, ready: bool, refresh_hz: int = 120):
        runtime = Mock()
        runtime.inspect.return_value = CapabilityInspection(
            display=DisplayEnvironment(1, 1920, 1080, refresh_hz),
            fingerprint=EnvironmentFingerprint(
                1,
                1920,
                1080,
                refresh_hz,
                "E:",
                "cpu",
                "gpu",
                "ffmpeg",
                "libx264-superfast-yuv420p",
            ),
            readiness=CaptureReadiness(ready, "" if ready else "尚未检测"),
        )
        return runtime

    def test_120fps_is_disabled_when_refresh_rate_is_too_low(self):
        page = SettingsDialog(
            self.config,
            embedded=True,
            capture_capability=self._capture_runtime(ready=False, refresh_hz=60),
        )

        item = page._combo_fps.model().item(page._combo_fps.findText("120"))
        self.assertFalse(item.isEnabled())
        self.assertIn("119Hz", page._label_fps_capability.text())

    def test_120fps_self_test_pass_only_updates_unsaved_candidate(self):
        page = SettingsDialog(
            self.config,
            embedded=True,
            capture_capability=self._capture_runtime(ready=False),
        )
        passed = SelfTestResult(
            status="passed",
            passed=True,
            average_fps=120.1,
            minimum_one_second_fps=119,
        )

        with patch(
            "ui.settings_dialog.CaptureSelfTestDialog.execute",
            return_value=passed,
        ):
            page._combo_fps.setCurrentText("120")

        self.assertEqual(page._combo_fps.currentText(), "120")
        self.assertTrue(page.is_dirty)
        self.assertEqual(self.config.get("fps"), 30)

    def test_120fps_self_test_failure_restores_previous_draft(self):
        page = SettingsDialog(
            self.config,
            embedded=True,
            capture_capability=self._capture_runtime(ready=False),
        )

        with patch(
            "ui.settings_dialog.CaptureSelfTestDialog.execute",
            return_value=None,
        ):
            page._combo_fps.setCurrentText("120")

        self.assertEqual(page._combo_fps.currentText(), "30")
        self.assertEqual(self.config.get("fps"), 30)


if __name__ == "__main__":
    unittest.main()
