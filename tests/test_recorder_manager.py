import os
import shutil
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ConfigManager
from recorder.events import RecordingEventType
from recorder.recorder_manager import RecorderManager, RecorderState
from recorder.state_machine import RecordingStateMachine


class FakeScreenCapturer:
    instances = []

    def __init__(self, region=None, target_fps=60):
        self.region = region
        self.target_fps = target_fps
        self._started = False
        self.update_calls = []
        self.request_stop_calls = 0
        FakeScreenCapturer.instances.append(self)

    def start(self):
        self._started = True

    def capture_frame(self):
        return np.zeros((240, 320, 3), dtype=np.uint8)

    def get_monitor_size(self):
        return (320, 240)

    def update_region(self, region):
        self.region = region
        self.update_calls.append(region)

    def get_capture_region(self):
        return self.region

    def close(self):
        self._started = False

    def request_stop(self):
        self.request_stop_calls += 1
        return True


class FailingStartScreenCapturer(FakeScreenCapturer):
    def start(self):
        raise RuntimeError("capture unavailable")


class FakeVideoEncoder:
    def __init__(self, output_path, fps, frame_size, ffmpeg_path):
        self.output_path = output_path
        self.frame_count = 0
        self.open = True

    def write_frame(self, frame):
        if not self.open:
            return False
        self.frame_count += 1
        return True

    def close(self):
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        with open(self.output_path, "wb") as f:
            f.write(b"fake mp4")
        self.open = False
        return True


class FailingVideoEncoder:
    def __init__(self, output_path, fps, frame_size, ffmpeg_path):
        raise FileNotFoundError(ffmpeg_path)


class FailingWriteVideoEncoder(FakeVideoEncoder):
    def write_frame(self, frame):
        self.open = False
        return False

    def close(self):
        self.open = False
        return False


class FakeTimerResolution:
    def __init__(self):
        self.begin_calls = 0
        self.end_calls = 0

    def begin(self):
        self.begin_calls += 1

    def end(self):
        self.end_calls += 1


class FakeAudioCapturer:
    should_start = True
    instances = []

    def __init__(self, source, output_dir):
        self.source = source
        self.output_dir = output_dir
        self.stopped = False
        FakeAudioCapturer.instances.append(self)

    def start(self, output_stem=""):
        return self.should_start

    def stop(self):
        self.stopped = True
        path = os.path.join(self.output_dir, "audio.wav")
        with open(path, "wb") as f:
            f.write(b"fake wav")
        return path


class TestRecorderManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigManager.__new__(ConfigManager)
        self.config._config_path = os.path.join(self.temp_dir, "config.json")
        self.config._config = {
            "save_path": self.temp_dir,
            "quality": "low",
            "fps": 30,
            "audio_source": "none",
        }
        FakeScreenCapturer.instances = []
        FakeAudioCapturer.instances = []

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _patch_runtime(self):
        return patch.multiple(
            "recorder.recorder_manager",
            ScreenCapturer=FakeScreenCapturer,
            VideoEncoder=FakeVideoEncoder,
        )

    def _write_wav(self, name: str, channels: int = 1, frames: int = 32) -> str:
        path = os.path.join(self.temp_dir, name)
        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(48000)
            wav_file.writeframes(b"\0\0" * channels * frames)
        return path

    def test_initial_state_is_idle(self):
        manager = RecorderManager(self.config)
        self.assertEqual(manager.get_state(), RecorderState.IDLE)
        self.assertIsInstance(manager._state_machine, RecordingStateMachine)

    def test_public_event_handler_can_be_replaced(self):
        events = []
        manager = RecorderManager(self.config)
        manager.set_event_handler(events.append)
        manager._session_dir = tempfile.mkdtemp(dir=self.temp_dir)
        manager._video_temp_path = os.path.join(manager._session_dir, "missing.mp4")
        manager._output_path = os.path.join(self.temp_dir, "final.mp4")
        manager._audio_temp_paths = []
        manager._ffmpeg_path = "ffmpeg.exe"

        manager._finalize()

        self.assertEqual(events[-1].type, RecordingEventType.FAILED)

    def test_start_fullscreen_changes_state(self):
        with self._patch_runtime(), patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config)
            timer = FakeTimerResolution()
            manager._timer_resolution = timer
            try:
                self.assertTrue(manager.start_fullscreen())
                self.assertEqual(manager.get_state(), RecorderState.RECORDING)
                self.assertEqual(manager._fps, 60)
                self.assertEqual(manager._encode_size, manager._frame_size)
            finally:
                if manager.get_state() != RecorderState.IDLE:
                    manager.stop()
                    manager.wait_until_idle(timeout=2)
            self.assertEqual(timer.begin_calls, 1)
            self.assertEqual(timer.end_calls, 1)

    def test_pause_resume_state_flow(self):
        with self._patch_runtime(), patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config)
            try:
                manager.start_fullscreen()
                self.assertTrue(manager.pause())
                self.assertEqual(manager.get_state(), RecorderState.PAUSED)
                self.assertFalse(manager.pause())
                self.assertTrue(manager.resume())
                self.assertEqual(manager.get_state(), RecorderState.RECORDING)
                self.assertFalse(manager.resume())
            finally:
                manager.stop()
                manager.wait_until_idle(timeout=2)

    def test_stop_is_async_and_reports_saved_path_by_callback(self):
        saved_paths = []
        with self._patch_runtime(), patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config, on_saved=saved_paths.append)
            manager.start_fullscreen()
            time.sleep(0.05)

            self.assertEqual(manager.stop(), "")
            manager.wait_until_idle(timeout=2)

        self.assertEqual(len(saved_paths), 1)
        self.assertTrue(saved_paths[0].endswith(".mp4"))
        self.assertTrue(os.path.exists(saved_paths[0]))
        self.assertEqual(manager.get_state(), RecorderState.IDLE)

    def test_stop_when_idle_returns_empty(self):
        manager = RecorderManager(self.config)
        self.assertEqual(manager.stop(), "")

    def test_stop_requests_non_blocking_capture_shutdown(self):
        with self._patch_runtime(), patch.object(
            RecorderManager,
            "_get_ffmpeg_path",
            return_value="ffmpeg.exe",
        ):
            manager = RecorderManager(self.config)
            self.assertTrue(manager.start_fullscreen())
            capturer = FakeScreenCapturer.instances[-1]

            manager.stop()
            manager.wait_until_idle(timeout=2)

        self.assertEqual(capturer.request_stop_calls, 1)

    def test_lite_recording_uses_fixed_60_fps_for_capture_and_disk_guard(self):
        with self._patch_runtime(), patch.object(
            RecorderManager,
            "_get_ffmpeg_path",
            return_value="ffmpeg.exe",
        ), patch("recorder.recorder_manager.DiskChecker.is_low_space", return_value=False) as low_space:
            manager = RecorderManager(self.config)
            self.assertTrue(manager.start_fullscreen())
            manager.stop()
            manager.wait_until_idle(timeout=2)

        self.assertEqual(FakeScreenCapturer.instances[-1].target_fps, 60)
        self.assertTrue(any(call.kwargs.get("fps") == 60 for call in low_space.call_args_list))

    def test_wait_until_idle_returns_true_when_already_idle(self):
        manager = RecorderManager(self.config)

        self.assertTrue(manager.wait_until_idle(timeout=0.01))

    def test_wait_until_idle_returns_false_on_timeout(self):
        manager = RecorderManager(self.config)
        manager._state_machine.transition_to(RecorderState.RECORDING)

        self.assertFalse(manager.wait_until_idle(timeout=0.01))

    def test_elapsed_time_format(self):
        with self._patch_runtime(), patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config)
            self.assertEqual(manager.get_elapsed(), "00:00")
            try:
                manager.start_fullscreen()
                time.sleep(0.1)
                self.assertRegex(manager.get_elapsed(), r"\d{2}:\d{2}")
            finally:
                manager.stop()
                manager.wait_until_idle(timeout=2)

    def test_consecutive_start_stop_uses_async_saved_callback(self):
        saved_paths = []
        with self._patch_runtime(), patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config, on_saved=saved_paths.append)
            for _ in range(3):
                self.assertTrue(manager.start_fullscreen())
                time.sleep(0.05)
                self.assertEqual(manager.stop(), "")
                manager.wait_until_idle(timeout=2)
                self.assertEqual(manager.get_state(), RecorderState.IDLE)

        self.assertEqual(len(saved_paths), 3)
        self.assertTrue(all(path.endswith(".mp4") for path in saved_paths))
        self.assertTrue(all(os.path.exists(path) for path in saved_paths))

    def test_start_returns_false_when_already_recording(self):
        with self._patch_runtime(), patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config)
            try:
                self.assertTrue(manager.start_fullscreen())
                self.assertFalse(manager.start_fullscreen())
            finally:
                manager.stop()
                manager.wait_until_idle(timeout=2)

    def test_start_returns_false_when_disk_space_is_low(self):
        with patch("recorder.recorder_manager.DiskChecker.is_low_space", return_value=True):
            manager = RecorderManager(self.config)

            self.assertFalse(manager.start_fullscreen())
            self.assertEqual(manager.get_state(), RecorderState.IDLE)

    def test_start_returns_false_when_ffmpeg_is_missing(self):
        with self._patch_runtime(), patch.object(RecorderManager, "_get_ffmpeg_path", return_value=""):
            manager = RecorderManager(self.config)

            self.assertFalse(manager.start_fullscreen())
            self.assertEqual(manager.get_state(), RecorderState.IDLE)
            self.assertEqual(manager._session_dir, "")

    def test_cancel_stop_cleans_session_without_saved_callback(self):
        saved_paths = []
        with self._patch_runtime(), patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config, on_saved=saved_paths.append)
            manager.start_fullscreen()
            session_dir = manager._session_dir
            time.sleep(0.05)

            self.assertEqual(manager.stop(cancel=True), "")
            manager.wait_until_idle(timeout=2)

        self.assertEqual(saved_paths, [])
        self.assertFalse(os.path.exists(session_dir))
        self.assertEqual(manager.get_state(), RecorderState.IDLE)

    def test_audio_start_failure_degrades_to_silent_recording(self):
        self.config._config["audio_source"] = "system"
        FakeAudioCapturer.should_start = False
        with self._patch_runtime(), \
                patch("recorder.recorder_manager.AudioCapturer", FakeAudioCapturer), \
                patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config)
            try:
                self.assertTrue(manager.start_fullscreen())
                self.assertIsNone(manager._audio_capturer)
            finally:
                FakeAudioCapturer.should_start = True
                manager.stop()
                manager.wait_until_idle(timeout=2)

    def test_audio_stop_paths_are_mixed_before_finalize(self):
        self.config._config["audio_source"] = "system"
        saved_paths = []
        with self._patch_runtime(), \
                patch("recorder.recorder_manager.AudioCapturer", FakeAudioCapturer), \
                patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"), \
                patch.object(RecorderManager, "_mix_audio", wraps=lambda video, audio: video):
            manager = RecorderManager(self.config, on_saved=saved_paths.append)
            manager.start_fullscreen()
            time.sleep(0.05)
            manager.stop()
            manager.wait_until_idle(timeout=2)

        self.assertEqual(len(saved_paths), 1)
        self.assertTrue(os.path.exists(saved_paths[0]))

    def test_audio_preflight_degrades_both_to_microphone_before_starting_audio(self):
        self.config._config["audio_source"] = "both"
        with self._patch_runtime(), \
                patch("recorder.recorder_manager.AudioCapturer", FakeAudioCapturer), \
                patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"), \
                patch.object(RecorderManager, "_probe_audio_sources", return_value=(False, True)):
            manager = RecorderManager(self.config)
            try:
                self.assertTrue(manager.start_fullscreen())
                self.assertEqual(manager.get_audio_preflight().requested_source, "both")
                self.assertEqual(manager.get_audio_preflight().final_source, "microphone")
                self.assertTrue(manager.get_audio_preflight().degraded)
                self.assertEqual(manager.get_audio_preflight().reason, "system_unavailable")
                self.assertEqual(FakeAudioCapturer.instances[-1].source, "microphone")
            finally:
                manager.stop()
                manager.wait_until_idle(timeout=2)

    def test_audio_preflight_disables_audio_when_requested_source_unavailable(self):
        self.config._config["audio_source"] = "system"
        with self._patch_runtime(), \
                patch("recorder.recorder_manager.AudioCapturer", FakeAudioCapturer), \
                patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"), \
                patch.object(RecorderManager, "_probe_audio_sources", return_value=(False, True)):
            manager = RecorderManager(self.config)
            try:
                self.assertTrue(manager.start_fullscreen())
                self.assertEqual(manager.get_audio_preflight().final_source, "none")
                self.assertTrue(manager.get_audio_preflight().degraded)
                self.assertIsNone(manager._audio_capturer)
                self.assertEqual(FakeAudioCapturer.instances, [])
            finally:
                manager.stop()
                manager.wait_until_idle(timeout=2)

    def test_probe_audio_sources_uses_audio_capturer_lightweight_probes(self):
        class ProbeAudioCapturer:
            @staticmethod
            def probe_system_available():
                return False

            @staticmethod
            def probe_microphone_available():
                return True

        with patch("recorder.recorder_manager.AudioCapturer", ProbeAudioCapturer):
            manager = RecorderManager(self.config)

            self.assertEqual(manager._probe_audio_sources("both"), (False, True))
            self.assertEqual(manager._probe_audio_sources("system"), (False, False))
            self.assertEqual(manager._probe_audio_sources("microphone"), (False, True))

    def test_fullscreen_keeps_cursor_overlay(self):
        import recorder.recorder_manager as recorder_manager

        manager = RecorderManager(self.config)
        manager._frame_size = (100, 50)
        manager._encode_size = (100, 50)
        manager._capturer = FakeScreenCapturer()
        frame = np.zeros((50, 100, 3), dtype=np.uint8)
        multipliers = []

        def fake_draw_cursor(frame_arg, capture_region, size_multiplier=1.0):
            multipliers.append(size_multiplier)
            return frame_arg

        with patch.object(recorder_manager, "draw_cursor", side_effect=fake_draw_cursor):
            manager._prepare_frame_for_encoding(frame)

        self.assertEqual(multipliers, [1.0])

    def test_mix_audio_builds_single_audio_command(self):
        manager = RecorderManager(self.config)
        manager._session_dir = self.temp_dir
        manager._ffmpeg_path = "ffmpeg.exe"
        audio_path = self._write_wav("audio.wav")

        with patch("recorder.recorder_manager.subprocess.run") as run:
            result = manager._mix_audio("video.mp4", [audio_path])

        self.assertEqual(result, os.path.join(self.temp_dir, "mixed.mp4"))
        cmd = run.call_args.args[0]
        self.assertIn("-shortest", cmd)
        self.assertNotIn("-filter_complex", cmd)

    def test_mix_audio_builds_two_audio_stereo_amix_command(self):
        manager = RecorderManager(self.config)
        manager._session_dir = self.temp_dir
        manager._ffmpeg_path = "ffmpeg.exe"
        system_path = self._write_wav("system.wav", channels=2)
        mic_path = self._write_wav("mic.wav")

        with patch("recorder.recorder_manager.subprocess.run") as run:
            result = manager._mix_audio("video.mp4", [system_path, mic_path])

        self.assertEqual(result, os.path.join(self.temp_dir, "mixed.mp4"))
        cmd = run.call_args.args[0]
        self.assertIn("-filter_complex", cmd)
        filter_graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("aformat=sample_rates=48000:channel_layouts=stereo", filter_graph)
        self.assertIn("amix=inputs=2", filter_graph)
        self.assertNotIn("amerge", filter_graph)

    def test_mix_audio_trims_track_started_before_first_video_frame(self):
        manager = RecorderManager(self.config)
        manager._session_dir = self.temp_dir
        manager._ffmpeg_path = "ffmpeg.exe"
        manager._video_started_at = 10.125
        audio_path = self._write_wav("early-audio.wav")
        manager._audio_track_start_times = {audio_path: 10.0}
        manager._audio_track_latency_seconds = {audio_path: 0.05}

        with patch("recorder.recorder_manager.subprocess.run") as run:
            manager._mix_audio("video.mp4", [audio_path])

        cmd = run.call_args.args[0]
        filter_graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("atrim=start=0.075000", filter_graph)
        self.assertIn("asetpts=PTS-STARTPTS", filter_graph)

    def test_mix_audio_delays_track_started_after_first_video_frame(self):
        manager = RecorderManager(self.config)
        manager._session_dir = self.temp_dir
        manager._ffmpeg_path = "ffmpeg.exe"
        manager._video_started_at = 10.0
        audio_path = self._write_wav("late-audio.wav")
        manager._audio_track_start_times = {audio_path: 10.08}
        manager._audio_track_latency_seconds = {audio_path: 0.0}

        with patch("recorder.recorder_manager.subprocess.run") as run:
            manager._mix_audio("video.mp4", [audio_path])

        cmd = run.call_args.args[0]
        filter_graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("adelay=80:all=1", filter_graph)

    def test_mix_audio_aligns_system_and_microphone_tracks_independently(self):
        manager = RecorderManager(self.config)
        manager._session_dir = self.temp_dir
        manager._ffmpeg_path = "ffmpeg.exe"
        manager._video_started_at = 10.1
        system_path = self._write_wav("system.wav")
        microphone_path = self._write_wav("microphone.wav")
        manager._audio_track_start_times = {system_path: 9.98, microphone_path: 10.14}
        manager._audio_track_latency_seconds = {system_path: 0.05, microphone_path: 0.0}

        with patch("recorder.recorder_manager.subprocess.run") as run:
            manager._mix_audio("video.mp4", [system_path, microphone_path])

        cmd = run.call_args.args[0]
        filter_graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("[1:a]atrim=start=0.070000", filter_graph)
        self.assertIn("[2:a]adelay=40:all=1", filter_graph)
        self.assertIn("[aligned1][aligned2]amix=inputs=2", filter_graph)

    def test_mix_audio_returns_empty_on_ffmpeg_failure(self):
        manager = RecorderManager(self.config)
        manager._session_dir = self.temp_dir
        manager._ffmpeg_path = "ffmpeg.exe"

        with patch("recorder.recorder_manager.subprocess.run", side_effect=RuntimeError("boom")):
            self.assertEqual(manager._mix_audio("video.mp4", ["audio.wav"]), "")

    def test_mix_audio_skips_empty_wav_files(self):
        manager = RecorderManager(self.config)
        manager._session_dir = self.temp_dir
        manager._ffmpeg_path = "ffmpeg.exe"
        empty_wav = os.path.join(self.temp_dir, "empty.wav")
        with wave.open(empty_wav, "wb") as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(48000)

        with patch("recorder.recorder_manager.subprocess.run") as run:
            result = manager._mix_audio("video.mp4", [empty_wav])

        self.assertEqual(result, "")
        run.assert_not_called()

    def test_encoder_start_failure_emits_failed_event_and_resets_state(self):
        saved_paths = []
        events = []
        with patch.multiple(
                "recorder.recorder_manager",
                ScreenCapturer=FakeScreenCapturer,
                VideoEncoder=FailingVideoEncoder), \
                patch.object(RecorderManager, "_get_ffmpeg_path", return_value="missing-ffmpeg.exe"):
            manager = RecorderManager(self.config, on_saved=saved_paths.append, on_event=events.append)
            timer = FakeTimerResolution()
            manager._timer_resolution = timer

            self.assertTrue(manager.start_fullscreen())
            manager.wait_until_idle(timeout=2)

        self.assertEqual(manager.get_state(), RecorderState.IDLE)
        self.assertEqual(saved_paths, [""])
        self.assertEqual(events[-1].type, RecordingEventType.FAILED)
        self.assertIn("ffmpeg start failed", events[-1].reason)
        self.assertEqual(timer.begin_calls, 1)
        self.assertEqual(timer.end_calls, 1)

    def test_frame_write_failure_reports_failed_event_and_resets_state(self):
        saved_paths = []
        events = []
        with patch.multiple(
                "recorder.recorder_manager",
                ScreenCapturer=FakeScreenCapturer,
                VideoEncoder=FailingWriteVideoEncoder), \
                patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config, on_saved=saved_paths.append, on_event=events.append)
            timer = FakeTimerResolution()
            manager._timer_resolution = timer

            self.assertTrue(manager.start_fullscreen())
            manager.wait_until_idle(timeout=2)

        self.assertEqual(manager.get_state(), RecorderState.IDLE)
        self.assertEqual(saved_paths, [""])
        self.assertEqual(events[-1].type, RecordingEventType.FAILED)
        self.assertEqual(events[-1].reason, "video frame write failed")
        self.assertEqual(timer.begin_calls, 1)
        self.assertEqual(timer.end_calls, 1)

    def test_screen_capture_start_failure_reports_failed_event_and_resets_state(self):
        saved_paths = []
        events = []
        with patch.multiple(
                "recorder.recorder_manager",
                ScreenCapturer=FailingStartScreenCapturer,
                VideoEncoder=FakeVideoEncoder), \
                patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config, on_saved=saved_paths.append, on_event=events.append)
            timer = FakeTimerResolution()
            manager._timer_resolution = timer

            self.assertTrue(manager.start_fullscreen())
            manager.wait_until_idle(timeout=2)

        self.assertEqual(manager.get_state(), RecorderState.IDLE)
        self.assertEqual(saved_paths, [""])
        self.assertEqual(events[-1].type, RecordingEventType.FAILED)
        self.assertIn("screen capture start failed", events[-1].reason)
        self.assertEqual(timer.begin_calls, 1)
        self.assertEqual(timer.end_calls, 1)

    def test_runtime_low_disk_reports_failed_event_and_resets_state(self):
        saved_paths = []
        events = []
        with self._patch_runtime(), \
                patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"), \
                patch("recorder.recorder_manager.DiskChecker.is_low_space", side_effect=[False, True]):
            manager = RecorderManager(self.config, on_saved=saved_paths.append, on_event=events.append)
            timer = FakeTimerResolution()
            manager._timer_resolution = timer
            manager._disk_check_interval = 0.0

            self.assertTrue(manager.start_fullscreen())
            manager.wait_until_idle(timeout=2)

        self.assertEqual(manager.get_state(), RecorderState.IDLE)
        self.assertEqual(saved_paths, [""])
        self.assertEqual(events[-1].type, RecordingEventType.FAILED)
        self.assertEqual(events[-1].reason, "disk space became low during recording")
        self.assertEqual(timer.begin_calls, 1)
        self.assertEqual(timer.end_calls, 1)

    def test_finalize_moves_mixed_audio_output_and_calls_callback(self):
        saved_paths = []
        events = []
        manager = RecorderManager(self.config, on_saved=saved_paths.append, on_event=events.append)
        manager._session_dir = tempfile.mkdtemp(dir=self.temp_dir)
        manager._video_temp_path = os.path.join(manager._session_dir, "video.mp4")
        manager._output_path = os.path.join(self.temp_dir, "final.mp4")
        manager._audio_temp_paths = ["audio.wav"]
        manager._ffmpeg_path = "ffmpeg.exe"
        mixed = os.path.join(manager._session_dir, "mixed.mp4")
        with open(manager._video_temp_path, "wb") as f:
            f.write(b"video")
        with open(mixed, "wb") as f:
            f.write(b"mixed")

        with patch.object(manager, "_mix_audio", return_value=mixed):
            manager._finalize()

        self.assertEqual(saved_paths, [manager._output_path])
        self.assertEqual(events[-1].type, RecordingEventType.SAVED)
        self.assertEqual(events[-1].output_path, manager._output_path)
        self.assertTrue(os.path.exists(manager._output_path))
        self.assertEqual(manager.get_state(), RecorderState.IDLE)

    def test_finalize_reports_empty_path_on_move_failure(self):
        saved_paths = []
        events = []
        manager = RecorderManager(self.config, on_saved=saved_paths.append, on_event=events.append)
        manager._session_dir = tempfile.mkdtemp(dir=self.temp_dir)
        manager._video_temp_path = os.path.join(manager._session_dir, "missing.mp4")
        manager._output_path = os.path.join(self.temp_dir, "final.mp4")
        manager._audio_temp_paths = []
        manager._ffmpeg_path = "ffmpeg.exe"

        manager._finalize()

        self.assertEqual(saved_paths, [""])
        self.assertEqual(events[-1].type, RecordingEventType.FAILED)
        self.assertEqual(manager.get_state(), RecorderState.IDLE)

    def test_get_ffmpeg_path_prefers_frozen_meipass_candidate(self):

        original_frozen = getattr(sys, "frozen", None)
        original_meipass = getattr(sys, "_MEIPASS", None)
        sys.frozen = True
        sys._MEIPASS = "bundle"
        try:
            with patch("recorder.recorder_manager.os.path.isfile", side_effect=lambda p: p == os.path.join("bundle", "ffmpeg", "ffmpeg.exe")):
                self.assertEqual(RecorderManager._get_ffmpeg_path(), os.path.join("bundle", "ffmpeg", "ffmpeg.exe"))
        finally:
            if original_frozen is None:
                del sys.frozen
            else:
                sys.frozen = original_frozen
            if original_meipass is None:
                del sys._MEIPASS
            else:
                sys._MEIPASS = original_meipass

    def test_get_ffmpeg_path_falls_back_to_path_lookup(self):
        with patch("recorder.recorder_manager.os.path.isfile", return_value=False), \
                patch("shutil.which", return_value="C:/bin/ffmpeg.exe"):
            self.assertEqual(RecorderManager._get_ffmpeg_path(), "C:/bin/ffmpeg.exe")

if __name__ == "__main__":
    unittest.main()
