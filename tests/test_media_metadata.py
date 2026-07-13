import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.media_metadata import probe_media, resolve_ffprobe_path


class TestMediaMetadata(unittest.TestCase):
    def test_resolve_ffprobe_path_finds_project_binary(self):
        path = resolve_ffprobe_path()

        self.assertTrue(path.endswith(str(Path("ffmpeg") / "ffprobe.exe")))
        self.assertTrue(Path(path).is_file())

    def test_resolve_ffprobe_path_prefers_frozen_meipass_binary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            meipass = Path(temp_dir)
            binary = meipass / "ffmpeg" / "ffprobe.exe"
            binary.parent.mkdir()
            binary.write_bytes(b"ffprobe")
            with patch.object(__import__("utils.media_metadata", fromlist=["sys"]).sys, "frozen", True, create=True), \
                    patch.object(__import__("utils.media_metadata", fromlist=["sys"]).sys, "_MEIPASS", str(meipass), create=True):
                path = resolve_ffprobe_path()

        self.assertEqual(path, str(binary))

    @patch("utils.media_metadata.shutil.which", return_value=None)
    @patch("utils.media_metadata.Path.is_file", return_value=False)
    def test_probe_media_reports_missing_ffprobe(self, _is_file, _which):
        result = probe_media("video.mp4")

        self.assertFalse(result.ok)
        self.assertIn("not found", result.error)

    @patch("utils.media_metadata.subprocess.run")
    def test_probe_media_parses_video_stream_and_duration(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "streams": [
                        {
                            "codec_type": "video",
                            "width": 1920,
                            "height": 1080,
                            "avg_frame_rate": "60000/1001",
                        }
                    ],
                    "format": {"duration": "12.5"},
                }
            ),
            stderr="",
        )

        result = probe_media("video.mp4", ffprobe_path="ffprobe.exe")

        self.assertTrue(result.ok)
        self.assertEqual(result.width, 1920)
        self.assertEqual(result.height, 1080)
        self.assertAlmostEqual(result.fps, 59.94, places=2)
        self.assertEqual(result.duration_sec, 12.5)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "strict")

    @patch("utils.media_metadata.subprocess.run")
    def test_probe_media_rejects_missing_required_metadata_fields(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"streams":[{"codec_type":"video","width":1920}],"format":{}}',
            stderr="",
        )

        result = probe_media("video.mp4", ffprobe_path="ffprobe.exe")

        self.assertFalse(result.ok)
        self.assertIn("missing", result.error.lower())

    @patch("utils.media_metadata.subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 5))
    def test_probe_media_reports_timeout(self, _run):
        result = probe_media("video.mp4", ffprobe_path="ffprobe.exe", timeout=5)

        self.assertFalse(result.ok)
        self.assertIn("timeout", result.error.lower())

    @patch("utils.media_metadata.subprocess.run", side_effect=OSError("cannot start"))
    def test_probe_media_reports_process_start_failure(self, _run):
        result = probe_media("video.mp4", ffprobe_path="ffprobe.exe")

        self.assertFalse(result.ok)
        self.assertIn("cannot start", result.error)

    @patch("utils.media_metadata.subprocess.run")
    def test_probe_media_reports_nonzero_exit(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="invalid media",
        )

        result = probe_media("video.mp4", ffprobe_path="ffprobe.exe")

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "invalid media")

    @patch("utils.media_metadata.subprocess.run")
    def test_probe_media_rejects_output_without_video_stream(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"streams":[],"format":{}}',
            stderr="",
        )

        result = probe_media("video.mp4", ffprobe_path="ffprobe.exe")

        self.assertFalse(result.ok)
        self.assertIn("invalid ffprobe output", result.error)

    def test_real_ffprobe_reads_controlled_video_when_available(self):
        ffprobe = resolve_ffprobe_path()
        ffmpeg = str(Path(ffprobe).with_name("ffmpeg.exe"))
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "sample.mp4"
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=320x240:d=0.2",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(video),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            result = probe_media(video, ffprobe_path=ffprobe)

        self.assertTrue(result.ok, result.error)
        self.assertEqual((result.width, result.height), (320, 240))
        self.assertGreater(result.duration_sec or 0, 0)


if __name__ == "__main__":
    unittest.main()
