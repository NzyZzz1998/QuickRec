import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ffmpeg_capability_check import (
    CapabilityResult,
    check_encoders,
    check_mixed_output,
    run_capability_check,
)


class TestFfmpegCapabilityCheck(unittest.TestCase):
    def test_check_encoders_requires_libx264_and_aac(self):
        with patch("scripts.ffmpeg_capability_check.subprocess.run") as run:
            run.return_value.stdout = " V....D libx264\n A....D aac\n"

            result = check_encoders("ffmpeg.exe")

        self.assertTrue(result.ok)

    def test_check_encoders_reports_missing_encoder(self):
        with patch("scripts.ffmpeg_capability_check.subprocess.run") as run:
            run.return_value.stdout = " A....D aac\n"

            result = check_encoders("ffmpeg.exe")

        self.assertFalse(result.ok)
        self.assertIn("libx264", result.message)

    def test_check_mixed_output_requires_video_and_aac_audio(self):
        with patch("scripts.ffmpeg_capability_check.subprocess.run") as run:
            run.return_value.stdout = "Stream #0:0: Video: h264\nStream #0:1: Audio: aac\n"

            result = check_mixed_output("ffmpeg.exe", "mixed.mp4")

        self.assertTrue(result.ok)

    def test_check_mixed_output_reports_missing_audio(self):
        with patch("scripts.ffmpeg_capability_check.subprocess.run") as run:
            run.return_value.stdout = "Stream #0:0: Video: h264\n"

            result = check_mixed_output("ffmpeg.exe", "mixed.mp4")

        self.assertFalse(result.ok)
        self.assertIn("Audio", result.message)

    def test_run_capability_check_runs_expected_ffmpeg_steps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ffmpeg = str(Path(temp_dir) / "ffmpeg.exe")
            Path(ffmpeg).write_bytes(b"fake")
            with patch("scripts.ffmpeg_capability_check.check_encoders", return_value=CapabilityResult(True, "ok")), \
                    patch("scripts.ffmpeg_capability_check.check_mixed_output", return_value=CapabilityResult(True, "ok")), \
                    patch("scripts.ffmpeg_capability_check._run_ffmpeg", return_value=CapabilityResult(True, "ok")) as run:
                result = run_capability_check(ffmpeg, temp_dir)

        self.assertTrue(result.ok)
        self.assertEqual(run.call_count, 4)


if __name__ == "__main__":
    unittest.main()
