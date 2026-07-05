import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.hardware_smoke import (
    ExitCode,
    SmokeResult,
    check_log_markers,
    check_no_new_ffmpeg_processes,
    check_no_new_session_dirs,
    check_output_file,
    check_video_duration,
    check_video_stream,
    run_smoke,
)


class FakeRecorderManager:
    def __init__(self, config, on_saved=None, on_event=None):
        self.config = config
        self.on_saved = on_saved
        self.output_path = ""
        self.started = False
        self.stopped = False

    def start_fullscreen(self):
        self.started = True
        self.output_path = os.path.join(self.config.get("save_path"), "hardware-smoke.mp4")
        return True

    def stop(self):
        self.stopped = True
        with open(self.output_path, "wb") as output:
            output.write(b"fake mp4 data")
        if self.on_saved:
            self.on_saved(self.output_path)
        return ""

    def wait_until_idle(self, timeout=60.0):
        return True


class TestHardwareSmoke(unittest.TestCase):
    def test_check_output_file_rejects_missing_file(self):
        result = check_output_file("missing.mp4", min_size=1)

        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, ExitCode.FILE_CHECK_FAILED)

    def test_check_output_file_accepts_non_empty_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "out.mp4")
            with open(path, "wb") as output:
                output.write(b"mp4")

            result = check_output_file(path, min_size=1)

        self.assertTrue(result.ok)
        self.assertEqual(result.exit_code, ExitCode.OK)

    def test_check_log_markers_requires_key_stages(self):
        result = check_log_markers(
            "capture started\nencoding started\nsaved file\n",
            required=("capture", "encoding", "audio", "saved"),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, ExitCode.LOG_CHECK_FAILED)
        self.assertIn("audio", result.message)

    def test_check_video_stream_uses_ffmpeg_metadata(self):
        with patch("scripts.hardware_smoke.subprocess.run") as run:
            run.return_value.stderr = b"Input #0\nStream #0:0: Video: h264\n"

            result = check_video_stream("out.mp4", "ffmpeg.exe")

        self.assertTrue(result.ok)
        self.assertEqual(result.exit_code, ExitCode.OK)

    def test_check_video_stream_rejects_file_without_video_stream(self):
        with patch("scripts.hardware_smoke.subprocess.run") as run:
            run.return_value.stderr = b"Input #0\nStream #0:0: Audio: aac\n"

            result = check_video_stream("out.mp4", "ffmpeg.exe")

        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, ExitCode.FILE_CHECK_FAILED)

    def test_check_video_duration_accepts_expected_duration(self):
        with patch("scripts.hardware_smoke.subprocess.run") as run:
            run.return_value.stderr = b"Duration: 00:00:03.20, start: 0.000000\nStream #0:0: Video: h264\n"

            result = check_video_duration("out.mp4", "ffmpeg.exe", expected_duration=3.0)

        self.assertTrue(result.ok)
        self.assertEqual(result.exit_code, ExitCode.OK)

    def test_check_video_duration_rejects_too_short_file(self):
        with patch("scripts.hardware_smoke.subprocess.run") as run:
            run.return_value.stderr = b"Duration: 00:00:00.05, start: 0.000000\nStream #0:0: Video: h264\n"

            result = check_video_duration("out.mp4", "ffmpeg.exe", expected_duration=3.0)

        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, ExitCode.FILE_CHECK_FAILED)

    def test_check_no_new_ffmpeg_processes_rejects_residual_process(self):
        result = check_no_new_ffmpeg_processes(before={"100"}, after={"100", "200"})

        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, ExitCode.ENCODING_FAILED)

    def test_check_no_new_session_dirs_rejects_residual_dir(self):
        result = check_no_new_session_dirs(before={"session_1_1"}, after={"session_1_1", "session_2_2"})

        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, ExitCode.FILE_CHECK_FAILED)

    def test_run_smoke_records_and_validates_file_with_mock_recorder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.hardware_smoke.RecorderManager", FakeRecorderManager), \
                    patch("scripts.hardware_smoke.check_video_stream", return_value=SmokeResult(True, ExitCode.OK, "ok")), \
                    patch("scripts.hardware_smoke.check_video_duration", return_value=SmokeResult(True, ExitCode.OK, "ok")), \
                    patch("scripts.hardware_smoke.check_no_new_ffmpeg_processes", return_value=SmokeResult(True, ExitCode.OK, "ok")), \
                    patch("scripts.hardware_smoke.check_no_new_session_dirs", return_value=SmokeResult(True, ExitCode.OK, "ok")):
                result = run_smoke(duration=0.01, output_dir=temp_dir, min_size=1)

        self.assertIsInstance(result, SmokeResult)
        self.assertTrue(result.ok)
        self.assertEqual(result.exit_code, ExitCode.OK)

    def test_run_smoke_checks_required_log_markers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scripts.hardware_smoke.RecorderManager", FakeRecorderManager), \
                    patch("scripts.hardware_smoke.check_video_stream", return_value=SmokeResult(True, ExitCode.OK, "ok")), \
                    patch("scripts.hardware_smoke.check_video_duration", return_value=SmokeResult(True, ExitCode.OK, "ok")), \
                    patch("scripts.hardware_smoke.check_no_new_ffmpeg_processes", return_value=SmokeResult(True, ExitCode.OK, "ok")), \
                    patch("scripts.hardware_smoke.check_no_new_session_dirs", return_value=SmokeResult(True, ExitCode.OK, "ok")), \
                    patch("scripts.hardware_smoke.check_log_markers", return_value=SmokeResult(False, ExitCode.LOG_CHECK_FAILED, "missing")):
                result = run_smoke(duration=0.01, output_dir=temp_dir, min_size=1)

        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, ExitCode.LOG_CHECK_FAILED)

    def test_run_smoke_rejects_non_fullscreen_mode(self):
        result = run_smoke(duration=0.01, output_dir="", mode="window")

        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, ExitCode.CAPTURE_FAILED)


if __name__ == "__main__":
    unittest.main()
