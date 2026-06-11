"""
FileNamer 单元测试
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.file_namer import FileNamer


class TestFileNamer(unittest.TestCase):
    """FileNamer 测试类"""

    def setUp(self):
        """测试前准备：使用临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.fake_save_dir = Path(self.temp_dir) / "fake_recordings"

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_filename_format(self):
        """测试文件名格式正确"""
        path = FileNamer.generate(str(self.fake_save_dir))
        filename = Path(path).name

        import re
        pattern = r"^QuickRec_\d{8}_\d{6}\.mp4$"
        self.assertRegex(
            filename,
            pattern,
            f"文件名 {filename} 不符合格式 QuickRec_YYYYMMDD_HHmmss.mp4"
        )

    def test_filename_contains_current_date(self):
        """测试文件名包含当前日期"""
        path = FileNamer.generate(str(self.fake_save_dir))
        filename = Path(path).name

        today = datetime.now().strftime("%Y%m%d")
        self.assertIn(today, filename)

    def test_auto_create_directory(self):
        """测试目录不存在时自动创建"""
        self.assertFalse(self.fake_save_dir.exists())

        FileNamer.generate(str(self.fake_save_dir))

        self.assertTrue(self.fake_save_dir.exists())

    def test_conflict_increment(self):
        """测试文件名冲突时序号递增"""
        # 生成第一个文件名并创建文件
        path1 = FileNamer.generate(str(self.fake_save_dir))
        Path(path1).write_text("fake1")

        # 第二次应该生成 _001
        path2 = FileNamer.generate(str(self.fake_save_dir))
        Path(path2).write_text("fake2")

        # 第三次应该生成 _002
        path3 = FileNamer.generate(str(self.fake_save_dir))

        self.assertNotEqual(path1, path2)
        self.assertNotEqual(path2, path3)
        self.assertIn("_001", path2)
        self.assertIn("_002", path3)
        self.assertTrue(path2.endswith(".mp4"))
        self.assertTrue(path3.endswith(".mp4"))

    def test_custom_prefix(self):
        """测试自定义前缀"""
        path = FileNamer.generate(str(self.fake_save_dir), prefix="Test")
        filename = Path(path).name

        self.assertTrue(filename.startswith("Test_"))


if __name__ == "__main__":
    unittest.main()
