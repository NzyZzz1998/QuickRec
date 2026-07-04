import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recorder.video_encoder import VideoEncoder


class FakeProcess:
    def __init__(self, returncode=0):
        self.stdin = io.BytesIO()
        self.returncode = returncode
        self.killed = False
        self.terminated = False

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def terminate(self):
        self.terminated = True


class TestVideoEncoder(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.file_path = os.path.join(self.temp_dir, "test_output.mp4")
        self.frame_size = (320, 240)
        self.fps = 30
        self.ffmpeg_path = "ffmpeg.exe"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_frame(self):
        return np.zeros((self.frame_size[1], self.frame_size[0], 3), dtype=np.uint8)

    @patch("recorder.video_encoder.subprocess.Popen")
    def test_write_and_close_uses_ffmpeg_pipe(self, popen):
        popen.return_value = FakeProcess()

        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size, self.ffmpeg_path)
        for _ in range(30):
            self.assertTrue(encoder.write_frame(self._make_frame()))

        self.assertEqual(encoder.get_frame_count(), 30)
        self.assertTrue(encoder.is_open())
        self.assertTrue(encoder.close())
        self.assertFalse(encoder.is_open())

        cmd = popen.call_args.args[0]
        self.assertEqual(cmd[0], self.ffmpeg_path)
        self.assertIn("libx264", cmd)
        self.assertIn("pipe:0", cmd)

    @patch("recorder.video_encoder.subprocess.Popen")
    def test_auto_create_directory_before_starting_ffmpeg(self, popen):
        popen.return_value = FakeProcess()
        nested_dir = os.path.join(self.temp_dir, "sub", "dir")
        file_path = os.path.join(nested_dir, "output.mp4")

        encoder = VideoEncoder(file_path, self.fps, self.frame_size, self.ffmpeg_path)
        encoder.close()

        self.assertTrue(os.path.isdir(nested_dir))

    @patch("recorder.video_encoder.subprocess.Popen")
    def test_write_after_close_returns_false(self, popen):
        popen.return_value = FakeProcess()
        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size, self.ffmpeg_path)
        encoder.close()

        self.assertFalse(encoder.write_frame(self._make_frame()))

    @patch("recorder.video_encoder.subprocess.Popen")
    def test_frame_count_accurate(self, popen):
        popen.return_value = FakeProcess()
        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size, self.ffmpeg_path)

        for i in range(50):
            encoder.write_frame(self._make_frame())
            self.assertEqual(encoder.get_frame_count(), i + 1)

        encoder.close()

    @patch("recorder.video_encoder.subprocess.Popen")
    def test_close_reports_ffmpeg_failure(self, popen):
        popen.return_value = FakeProcess(returncode=1)
        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size, self.ffmpeg_path)
        encoder.write_frame(self._make_frame())

        self.assertFalse(encoder.close())
        self.assertFalse(encoder.is_open())

    @patch("recorder.video_encoder.subprocess.Popen")
    def test_write_frame_handles_broken_pipe(self, popen):
        class BrokenStdin:
            def write(self, _):
                raise BrokenPipeError()

            def close(self):
                pass

        proc = FakeProcess()
        proc.stdin = BrokenStdin()
        popen.return_value = proc
        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size, self.ffmpeg_path)

        self.assertFalse(encoder.write_frame(self._make_frame()))
        self.assertFalse(encoder.is_open())

    @patch("recorder.video_encoder.subprocess.Popen")
    def test_close_kills_ffmpeg_on_timeout(self, popen):
        class TimeoutProcess(FakeProcess):
            def wait(self, timeout=None):
                if not self.killed:
                    raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=timeout)
                return self.returncode

        proc = TimeoutProcess()
        popen.return_value = proc
        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size, self.ffmpeg_path)

        self.assertFalse(encoder.close())
        self.assertTrue(proc.killed)

    @patch("recorder.video_encoder.subprocess.Popen")
    def test_del_terminates_open_process(self, popen):
        proc = FakeProcess(returncode=None)
        popen.return_value = proc
        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size, self.ffmpeg_path)

        encoder.__del__()

        self.assertTrue(proc.terminated)


if __name__ == "__main__":
    unittest.main()
