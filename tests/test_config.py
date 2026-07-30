"""
ConfigManager 单元测试
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ConfigManager, ConfigSaveResult, ExportProjectDefaults


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
        self.assertTrue(
            str(self.config.get("project_root_path")).endswith(
                str(Path("QuickRec") / "Projects")
            )
        )
        self.assertEqual(self.config.get("diagnostic_keep_days"), 7)
        self.assertEqual(self.config.get("workbench_geometry"), {})
        self.assertEqual(self.config.get("export_defaults_by_project"), {})
        self.assertFalse(self.config.get("diagnostic_dir_customized"))

    def test_export_defaults_fall_back_to_project_exports_directory(self):
        project_path = Path(self.base_temp_dir) / "项目 空格" / "demo.qrproj"

        defaults = self.config.get_export_defaults(
            "project-1",
            project_path=project_path,
        )

        self.assertEqual(
            defaults,
            ExportProjectDefaults(
                width=1920,
                height=1080,
                fps=60,
                directory=str(project_path.resolve().parent / "Exports"),
            ),
        )

    def test_successful_export_preferences_are_persisted_per_project(self):
        directory = Path(self.base_temp_dir) / "导出 目录"

        result = self.config.remember_successful_export(
            "project-1",
            width=1280,
            height=720,
            fps=120,
            directory=directory,
        )

        self.assertTrue(result.ok)
        self.assertEqual(
            self.config.get_export_defaults(
                "project-1",
                project_path=Path(self.base_temp_dir) / "project.qrproj",
            ),
            ExportProjectDefaults(1280, 720, 120, str(directory)),
        )
        persisted = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(
            persisted["export_defaults_by_project"]["project-1"],
            {
                "width": 1280,
                "height": 720,
                "fps": 120,
                "directory": str(directory),
            },
        )

    def test_export_preference_save_failure_has_zero_side_effects(self):
        original = {
            "width": 1920,
            "height": 1080,
            "fps": 60,
            "directory": str(Path(self.base_temp_dir) / "old"),
        }
        self.config._config["export_defaults_by_project"] = {
            "project-1": original
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(self.config._config, ensure_ascii=False),
            encoding="utf-8",
        )

        with patch("config.os.replace", side_effect=OSError("replace failed")):
            result = self.config.remember_successful_export(
                "project-1",
                width=1280,
                height=720,
                fps=30,
                directory=Path(self.base_temp_dir) / "new",
            )

        self.assertFalse(result.ok)
        self.assertEqual(
            self.config.get("export_defaults_by_project"),
            {"project-1": original},
        )
        persisted = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(
            persisted["export_defaults_by_project"],
            {"project-1": original},
        )

    def test_invalid_legacy_export_preferences_fall_back_without_rewrite(self):
        project_path = Path(self.base_temp_dir) / "project.qrproj"
        self.config._config["export_defaults_by_project"] = {
            "project-1": {
                "width": 1921,
                "height": 1080,
                "fps": 90,
                "directory": "",
            }
        }

        defaults = self.config.get_export_defaults(
            "project-1",
            project_path=project_path,
        )

        self.assertEqual(
            defaults,
            ExportProjectDefaults(
                1920,
                1080,
                60,
                str(project_path.resolve().parent / "Exports"),
            ),
        )

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
        result = self.config.save()

        # 创建新的实例并加载
        new_config = ConfigManager.__new__(ConfigManager)
        new_config.config_path = self.config_path
        new_config._config = ConfigManager.defaults.copy()
        new_config.load()

        self.assertTrue(result.ok)
        self.assertEqual(new_config.get("quality"), "low")
        self.assertEqual(new_config.get("fps"), 60)

    def test_save_candidate_directory_failure_preserves_memory_and_file(self):
        """配置目录不可写时不提交候选配置"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text('{"quality": "high"}', encoding="utf-8")
        candidate = {**self.config._config, "quality": "low"}

        with patch("config.Path.mkdir", side_effect=PermissionError("denied")):
            result = self.config.save_candidate(candidate)

        self.assertIsInstance(result, ConfigSaveResult)
        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "prepare_directory")
        self.assertEqual(self.config.get("quality"), "high")
        self.assertEqual(
            json.loads(self.config_path.read_text(encoding="utf-8"))["quality"],
            "high",
        )

    def test_save_candidate_temp_write_failure_preserves_memory_and_file(self):
        """临时文件写入失败时不污染正式文件"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text('{"quality": "high"}', encoding="utf-8")
        candidate = {**self.config._config, "quality": "low"}

        with patch("config.tempfile.NamedTemporaryFile", side_effect=OSError("write failed")):
            result = self.config.save_candidate(candidate)

        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "write_temp")
        self.assertEqual(self.config.get("quality"), "high")
        self.assertEqual(
            json.loads(self.config_path.read_text(encoding="utf-8"))["quality"],
            "high",
        )

    def test_save_candidate_replace_failure_preserves_memory_and_file(self):
        """原子替换失败时不提交候选配置并清理临时文件"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text('{"quality": "high"}', encoding="utf-8")
        candidate = {**self.config._config, "quality": "low"}

        with patch("config.os.replace", side_effect=OSError("replace failed")):
            result = self.config.save_candidate(candidate)

        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "replace")
        self.assertEqual(self.config.get("quality"), "high")
        self.assertEqual(
            json.loads(self.config_path.read_text(encoding="utf-8"))["quality"],
            "high",
        )
        self.assertEqual(
            [path for path in self.config_path.parent.iterdir() if path != self.config_path],
            [],
        )

    def test_save_candidate_commits_only_after_atomic_replace(self):
        """候选配置仅在正式文件替换成功后进入内存"""
        candidate = {**self.config._config, "quality": "low", "fps": 60}

        result = self.config.save_candidate(candidate)

        self.assertTrue(result.ok)
        self.assertEqual(result.stage, "complete")
        self.assertEqual(self.config.get("quality"), "low")
        self.assertEqual(self.config.get("fps"), 60)
        persisted = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["quality"], "low")
        self.assertEqual(persisted["fps"], 60)
        self.assertEqual(os.path.dirname(result.path), str(self.config_path.parent))

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

    def test_config_load_and_save_ignore_separate_export_queue_directory(self):
        appdata = Path(self.base_temp_dir) / "appdata"
        queue_path = appdata / "QuickRec" / "Exports" / "queue.json"
        queue_path.parent.mkdir(parents=True)
        queue_payload = b'{"schema_version":1,"paused":true,"jobs":[]}'
        queue_path.write_bytes(queue_payload)

        with patch.dict(os.environ, {"APPDATA": str(appdata)}):
            legacy_compatible_config = ConfigManager()
            legacy_compatible_config.set("quality", "medium")
            result = legacy_compatible_config.save()

        self.assertTrue(result.ok)
        self.assertEqual(queue_path.read_bytes(), queue_payload)


if __name__ == "__main__":
    unittest.main()
