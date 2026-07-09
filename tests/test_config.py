"""
ConfigManager 单元测试
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ConfigManager


class TestConfigManager(unittest.TestCase):
    """ConfigManager 测试类"""

    def setUp(self):
        """测试前准备：使用临时目录"""
        self.base_temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.base_temp_dir) / "config" / "config.json"

        self.config = ConfigManager.__new__(ConfigManager)
        self.config.config_path = self.config_path
        self.config._config = ConfigManager.defaults.copy()

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.base_temp_dir, ignore_errors=True)

    def test_default_values(self):
        """测试默认值加载"""
        self.assertEqual(self.config.get("quality"), "high")
        self.assertEqual(self.config.get("fps"), 30)
        self.assertEqual(self.config.get("shortcut_start"), "Ctrl+Shift+R")
        self.assertEqual(self.config.get("shortcut_stop"), "Ctrl+Shift+S")
        self.assertEqual(self.config.get("shortcut_pause"), "Ctrl+Shift+P")
        self.assertEqual(self.config.get("show_countdown"), False)
        self.assertEqual(self.config.get("countdown_seconds"), 3)
        self.assertTrue("Videos" in self.config.get("save_path"))
        self.assertEqual(self.config.get("diagnostic_keep_days"), 7)
        self.assertFalse(self.config.get("diagnostic_dir_customized"))

    def test_default_diagnostic_dir_uses_save_path(self):
        """未自定义诊断目录时使用保存路径下的 QuickRecDiagnostics"""
        save_path = str(Path(self.base_temp_dir) / "videos")
        self.config.set("save_path", save_path)

        self.assertEqual(
            self.config.get_diagnostic_dir(),
            str(Path(save_path) / "QuickRecDiagnostics"),
        )

    def test_default_diagnostic_dir_follows_save_path_change(self):
        """未自定义诊断目录时保存路径变化会同步诊断目录"""
        new_save_path = str(Path(self.base_temp_dir) / "new-videos")

        self.config.update_save_path(new_save_path)

        self.assertEqual(self.config.get("save_path"), new_save_path)
        self.assertEqual(
            self.config.get_diagnostic_dir(),
            str(Path(new_save_path) / "QuickRecDiagnostics"),
        )
        self.assertEqual(self.config.get("diagnostic_dir"), "")
        self.assertFalse(self.config.get("diagnostic_dir_customized"))

    def test_custom_diagnostic_dir_does_not_follow_save_path_change(self):
        """已自定义诊断目录时保存路径变化不会覆盖诊断目录"""
        custom_dir = str(Path(self.base_temp_dir) / "diagnostics")
        new_save_path = str(Path(self.base_temp_dir) / "new-videos")

        self.config.update_diagnostic_dir(custom_dir)
        self.config.update_save_path(new_save_path)

        self.assertEqual(self.config.get("save_path"), new_save_path)
        self.assertEqual(self.config.get_diagnostic_dir(), custom_dir)
        self.assertEqual(self.config.get("diagnostic_dir"), custom_dir)
        self.assertTrue(self.config.get("diagnostic_dir_customized"))

    def test_empty_custom_diagnostic_dir_keeps_previous_value(self):
        """空诊断目录输入不覆盖原值"""
        custom_dir = str(Path(self.base_temp_dir) / "diagnostics")
        self.config.update_diagnostic_dir(custom_dir)

        self.config.update_diagnostic_dir("")

        self.assertEqual(self.config.get_diagnostic_dir(), custom_dir)

    def test_legacy_config_without_diagnostic_fields_loads(self):
        """旧配置缺少诊断字段时可正常加载并补默认值"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"save_path": str(Path(self.base_temp_dir) / "videos")}, f)

        self.config.load()

        self.assertEqual(self.config.get("diagnostic_dir"), "")
        self.assertEqual(self.config.get("diagnostic_keep_days"), 7)
        self.assertFalse(self.config.get("diagnostic_dir_customized"))

    def test_utf8_bom_config_loads(self):
        """带 UTF-8 BOM 的历史配置可正常加载"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8-sig") as f:
            json.dump({"quality": "medium", "fps": 60}, f)

        self.config.load()

        self.assertEqual(self.config.get("quality"), "medium")
        self.assertEqual(self.config.get("fps"), 60)

    def test_get_with_default(self):
        """测试 get 方法的 default 参数"""
        self.assertIsNone(self.config.get("nonexistent"))
        self.assertEqual(self.config.get("nonexistent", "default"), "default")

    def test_set_and_get(self):
        """测试 set 和 get"""
        self.config.set("quality", "medium")
        self.assertEqual(self.config.get("quality"), "medium")

        self.config.set("fps", 60)
        self.assertEqual(self.config.get("fps"), 60)

    def test_save_and_load(self):
        """测试 save 和 load 一致性"""
        self.config.set("quality", "low")
        self.config.set("fps", 60)
        self.config.save()

        # 创建新的实例并加载
        new_config = ConfigManager.__new__(ConfigManager)
        new_config.config_path = self.config_path
        new_config._config = ConfigManager.defaults.copy()
        new_config.load()

        self.assertEqual(new_config.get("quality"), "low")
        self.assertEqual(new_config.get("fps"), 60)

    def test_file_not_exist(self):
        """测试文件不存在时使用默认值"""
        self.assertFalse(self.config_path.exists())
        self.config.load()

        # 应该使用默认值
        self.assertEqual(self.config.get("quality"), "high")
        self.assertEqual(self.config.get("fps"), 30)

    def test_corrupted_file(self):
        """测试文件损坏时恢复默认值"""
        # 写入损坏的 JSON
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            f.write("{invalid json content}")

        self.config.load()

        # 应该恢复默认值
        self.assertEqual(self.config.get("quality"), "high")
        self.assertEqual(self.config.get("fps"), 30)

    def test_reset(self):
        """测试 reset 方法"""
        self.config.set("quality", "low")
        self.config.set("fps", 60)
        self.config.reset()

        self.assertEqual(self.config.get("quality"), "high")
        self.assertEqual(self.config.get("fps"), 30)

    def test_auto_create_directory(self):
        """测试自动创建目录"""
        self.assertFalse(self.config_path.parent.exists())
        self.config.save()

        self.assertTrue(self.config_path.parent.exists())
        self.assertTrue(self.config_path.exists())


if __name__ == "__main__":
    unittest.main()
