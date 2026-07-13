import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.recycle_bin import recycle_file


class TestRecycleBin(unittest.TestCase):
    @patch("utils.recycle_bin.send2trash")
    def test_recycle_file_sends_existing_file_to_os_trash(self, send_to_trash):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "QuickRec_demo.mp4"
            video.write_bytes(b"video")

            result = recycle_file(video)

        self.assertTrue(result.ok)
        send_to_trash.assert_called_once_with(str(video))

    @patch("utils.recycle_bin.send2trash", side_effect=OSError("recycle failed"))
    def test_recycle_file_reports_failure_without_permanent_delete(self, _send_to_trash):
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "QuickRec_demo.mp4"
            video.write_bytes(b"video")

            result = recycle_file(video)

        self.assertFalse(result.ok)
        self.assertIn("recycle failed", result.error)

    def test_recycle_file_rejects_missing_path(self):
        result = recycle_file("missing.mp4")

        self.assertFalse(result.ok)
        self.assertIn("does not exist", result.error)


if __name__ == "__main__":
    unittest.main()
