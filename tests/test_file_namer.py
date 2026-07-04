import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.file_namer import FileNamer


class TestFileNamer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.fake_save_dir = Path(self.temp_dir) / "fake_recordings"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_filename_format(self):
        path = FileNamer.generate(str(self.fake_save_dir))
        filename = Path(path).name

        self.assertRegex(filename, r"^QuickRec_\d{8}_\d{6}\.mp4$")

    def test_filename_contains_current_date(self):
        path = FileNamer.generate(str(self.fake_save_dir))
        filename = Path(path).name

        today = datetime.now().strftime("%Y%m%d")
        self.assertIn(today, filename)

    def test_auto_create_directory(self):
        self.assertFalse(self.fake_save_dir.exists())

        FileNamer.generate(str(self.fake_save_dir))

        self.assertTrue(self.fake_save_dir.exists())

    def test_conflict_increment(self):
        fixed_now = datetime(2026, 7, 4, 12, 0, 0)
        with patch("utils.file_namer.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_now
            path1 = FileNamer.generate(str(self.fake_save_dir))
            Path(path1).write_text("fake1")

            path2 = FileNamer.generate(str(self.fake_save_dir))
            Path(path2).write_text("fake2")

            path3 = FileNamer.generate(str(self.fake_save_dir))

        self.assertNotEqual(path1, path2)
        self.assertNotEqual(path2, path3)
        self.assertIn("_001", path2)
        self.assertIn("_002", path3)
        self.assertTrue(path2.endswith(".mp4"))
        self.assertTrue(path3.endswith(".mp4"))

    def test_custom_prefix(self):
        path = FileNamer.generate(str(self.fake_save_dir), prefix="Test")
        filename = Path(path).name

        self.assertTrue(filename.startswith("Test_"))


if __name__ == "__main__":
    unittest.main()
