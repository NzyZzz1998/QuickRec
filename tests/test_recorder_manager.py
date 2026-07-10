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
from recorder.recorder_manager import RecorderManager, RecorderState, RecordMode
from recorder.state_machine import RecordingStateMachine
from recorder.window_diagnostics import WindowFailureReason


class FakeScreenCapturer:
    instances = []

    def __init__(self, region=None):
        self.region = region
        self._started = False
        self.update_calls = []
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

    def test_diagnostic_context_contains_recorder_state_and_paths(self):
        manager = RecorderManager(self.config)
        manager._mode = RecordMode.REGION
        manager._output_path = os.path.join(self.temp_dir, "out.mp4")
        manager._session_dir = os.path.join(self.temp_dir, "session")
        manager._last_result_path = manager._output_path

        context = manager.get_diagnostic_context()

        self.assertEqual(context["recorder"]["state"], "idle")
        self.assertEqual(context["recorder"]["mode"], "region")
        self.assertEqual(context["recorder"]["output_path"], manager._output_path)
        self.assertEqual(context["recorder"]["session_dir"], manager._session_dir)
        self.assertEqual(context["recorder"]["last_result"], manager._output_path)

    def test_diagnostic_context_contains_ffmpeg_audio_and_window_context(self):
        manager = RecorderManager(self.config)
        manager._ffmpeg_path = os.path.join(self.temp_dir, "ffmpeg.exe")
        Path(manager._ffmpeg_path).write_text("fake", encoding="utf-8")
        manager._audio_preflight = manager._audio_preflight.__class__(
            requested_source="both",
            final_source="microphone",
            system_available=False,
            microphone_available=True,
            degraded=True,
            reason="system_unavailable",
        )
        manager._record_window_diagnostic(
            reason=WindowFailureReason.RECT_UNAVAILABLE,
            hwnd=123,
            title="Demo",
            stage="get_window_rect",
            rect=(1, 2, 300, 200),
            foreground_result="not_attempted",
        )

        context = manager.get_diagnostic_context()

        self.assertEqual(context["ffmpeg"]["path"], manager._ffmpeg_path)
        self.assertTrue(context["ffmpeg"]["exists"])
        self.assertEqual(context["audio"]["requested_source"], "both")
        self.assertEqual(context["audio"]["final_source"], "microphone")
        self.assertTrue(context["audio"]["degraded"])
        self.assertEqual(context["audio"]["reason"], "system_unavailable")
        self.assertEqual(context["window"]["hwnd"], 123)
        self.assertEqual(context["window"]["title"], "Demo")
        self.assertEqual(context["window"]["reason"], "rect_unavailable")

    def test_finalize_failure_is_exposed_in_diagnostic_context(self):
        manager = RecorderManager(self.config)
        manager._session_dir = tempfile.mkdtemp(dir=self.temp_dir)
        manager._video_temp_path = os.path.join(manager._session_dir, "missing.mp4")
        manager._output_path = os.path.join(self.temp_dir, "final.mp4")
        manager._audio_temp_paths = []
        manager._ffmpeg_path = "ffmpeg.exe"

        manager._finalize()

        context = manager.get_diagnostic_context()
        self.assertEqual(context["recorder"]["last_result"], "")
        self.assertIn("finalize failed", context["recorder"]["last_failure_reason"])

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

    def test_public_window_lost_connection_forwards_reason(self):
        reasons = []
        manager = RecorderManager(self.config)
        manager.connect_window_lost(reasons.append)

        manager._window_lost_bridge.window_lost.emit("closed")

        self.assertEqual(reasons, ["closed"])

    def test_start_fullscreen_changes_state(self):
        with self._patch_runtime(), patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config)
            timer = FakeTimerResolution()
            manager._timer_resolution = timer
            try:
                self.assertTrue(manager.start_fullscreen())
                self.assertEqual(manager.get_state(), RecorderState.RECORDING)
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

    def test_start_region_sets_region_mode_and_uses_region_size(self):
        with self._patch_runtime(), patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"):
            manager = RecorderManager(self.config)
            try:
                self.assertTrue(manager.start_region((10, 20, 320, 240)))
                self.assertEqual(manager.get_mode(), RecordMode.REGION)
                self.assertEqual(manager._capturer.region, (10, 20, 320, 240))
            finally:
                manager.stop()
                manager.wait_until_idle(timeout=2)

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

    def test_get_target_size_preserves_region_aspect_ratio(self):
        manager = RecorderManager(self.config)
        manager._mode = RecordMode.REGION
        manager._frame_size = (1000, 500)
        self.config._config["quality"] = "medium"

        self.assertEqual(manager._get_target_size(), (1280, 640))

    def test_get_target_size_preserves_window_native_size_for_high_quality(self):
        manager = RecorderManager(self.config)
        manager._mode = RecordMode.WINDOW
        manager._frame_size = (3000, 1800)
        self.config._config["quality"] = "high"

        self.assertIsNone(manager._get_target_size())

    def test_get_target_size_scales_window_with_aspect_ratio_for_medium_quality(self):
        manager = RecorderManager(self.config)
        manager._mode = RecordMode.WINDOW
        manager._frame_size = (3000, 1800)
        self.config._config["quality"] = "medium"

        self.assertEqual(manager._get_target_size(), (1200, 720))

    def test_get_target_size_returns_none_for_native_quality(self):
        manager = RecorderManager(self.config)
        self.config._config["quality"] = "native"

        self.assertIsNone(manager._get_target_size())

    def test_window_mode_uses_window_region_capture_and_window_frame_size(self):
        with self._patch_runtime(), \
                patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"), \
                patch.object(RecorderManager, "_get_window_rect") as get_rect:
            get_rect.return_value = type(
                "Rect",
                (),
                {
                    "left": lambda self: 40,
                    "top": lambda self: 50,
                    "width": lambda self: 100,
                    "height": lambda self: 80,
                },
            )()

            class FakeUser32:
                def IsWindow(self, hwnd):
                    return True

                def GetWindowTextLengthW(self, hwnd):
                    return 0

            import recorder.recorder_manager as recorder_manager
            original_user32 = recorder_manager.ctypes.windll.user32
            recorder_manager.ctypes.windll.user32 = FakeUser32()
            manager = RecorderManager(self.config)
            try:
                self.assertTrue(manager.start_window(123))
                self.assertEqual(manager._capturer.region, (40, 50, 100, 80))
                self.assertEqual(manager._frame_size, (100, 80))
            finally:
                if manager.get_state() != RecorderState.IDLE:
                    manager.stop()
                    manager.wait_until_idle(timeout=2)
                recorder_manager.ctypes.windll.user32 = original_user32

    def test_window_region_change_freezes_until_region_is_stable(self):
        manager = RecorderManager(self.config)
        manager._mode = RecordMode.WINDOW
        manager._capturer = FakeScreenCapturer(region=(10, 20, 100, 80))
        manager._window_region = (10, 20, 100, 80)

        self.assertTrue(manager._update_window_capture_region((30, 40, 100, 80), now=1.0))
        self.assertEqual(manager._capturer.update_calls, [])
        self.assertEqual(manager._pending_window_region, (30, 40, 100, 80))

        self.assertTrue(manager._update_window_capture_region((30, 40, 100, 80), now=1.3))
        self.assertEqual(manager._capturer.update_calls, [])

        self.assertFalse(manager._update_window_capture_region((30, 40, 100, 80), now=1.5))
        self.assertEqual(manager._capturer.update_calls, [(30, 40, 100, 80)])
        self.assertEqual(manager._window_region, (30, 40, 100, 80))
        self.assertIsNone(manager._pending_window_region)

    def test_window_recording_checks_window_position_every_frame(self):
        import recorder.recorder_manager as recorder_manager

        self.assertEqual(recorder_manager._WINDOW_CAPTURE_UPDATE_INTERVAL, 0.0)

    def test_window_frame_is_resized_without_cursor_overlay(self):
        import recorder.recorder_manager as recorder_manager

        manager = RecorderManager(self.config)
        manager._mode = RecordMode.WINDOW
        manager._frame_size = (200, 100)
        manager._encode_size = (200, 100)
        manager._capturer = FakeScreenCapturer(region=(0, 0, 100, 50))
        frame = np.zeros((50, 100, 3), dtype=np.uint8)

        with patch.object(
            recorder_manager,
            "draw_cursor",
            side_effect=AssertionError("window mode must not overlay cursor"),
            create=True,
        ):
            result = manager._prepare_frame_for_encoding(frame)

        self.assertEqual(result.shape, (100, 200, 3))

    def test_region_mode_does_not_overlay_cursor(self):
        import recorder.recorder_manager as recorder_manager

        manager = RecorderManager(self.config)
        manager._mode = RecordMode.REGION
        manager._frame_size = (100, 50)
        manager._encode_size = (100, 50)
        manager._capturer = FakeScreenCapturer(region=(0, 0, 100, 50))
        frame = np.zeros((50, 100, 3), dtype=np.uint8)

        with patch.object(
            recorder_manager,
            "draw_cursor",
            side_effect=AssertionError("region mode must not overlay cursor"),
            create=True,
        ):
            result = manager._prepare_frame_for_encoding(frame)

        self.assertIs(result, frame)
        self.assertTrue(np.all(result == 0))

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

    def test_mix_audio_builds_two_audio_amerge_command(self):
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
        self.assertIn("[1:a][2:a]amerge=inputs=2[a]", cmd)

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

    def test_window_capture_start_failure_records_backend_diagnostic(self):
        class FakeUser32:
            def IsWindow(self, hwnd):
                return True

            def GetWindowTextLengthW(self, hwnd):
                return 0

        rect = type(
            "Rect",
            (),
            {
                "left": lambda self: 40,
                "top": lambda self: 50,
                "width": lambda self: 100,
                "height": lambda self: 80,
            },
        )()

        import recorder.recorder_manager as recorder_manager
        original_user32 = recorder_manager.ctypes.windll.user32
        recorder_manager.ctypes.windll.user32 = FakeUser32()
        try:
            with patch.multiple(
                    "recorder.recorder_manager",
                    ScreenCapturer=FailingStartScreenCapturer,
                    VideoEncoder=FakeVideoEncoder), \
                    patch.object(RecorderManager, "_get_ffmpeg_path", return_value="ffmpeg.exe"), \
                    patch.object(RecorderManager, "_get_window_rect", return_value=rect):
                manager = RecorderManager(self.config)

                self.assertTrue(manager.start_window(123))
                manager.wait_until_idle(timeout=2)

            diagnostic = manager.get_last_window_diagnostic()
            self.assertEqual(diagnostic.reason, WindowFailureReason.CAPTURE_BACKEND_FAILED)
            self.assertEqual(diagnostic.hwnd, 123)
            self.assertEqual(diagnostic.mode, "window")
            self.assertEqual(diagnostic.stage, "capture_start")
            self.assertEqual(diagnostic.rect, (40, 50, 100, 80))
        finally:
            recorder_manager.ctypes.windll.user32 = original_user32

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

    def test_start_window_rejects_invalid_window(self):
        class FakeUser32:
            def IsWindow(self, hwnd):
                return False

        import recorder.recorder_manager as recorder_manager
        original_user32 = recorder_manager.ctypes.windll.user32
        recorder_manager.ctypes.windll.user32 = FakeUser32()
        try:
            manager = RecorderManager(self.config)
            self.assertFalse(manager.start_window(123))
            diagnostic = manager.get_last_window_diagnostic()
            self.assertEqual(diagnostic.reason, WindowFailureReason.UNSUPPORTED_WINDOW)
            self.assertEqual(diagnostic.hwnd, 123)
            self.assertEqual(diagnostic.mode, "window")
            self.assertEqual(diagnostic.stage, "is_window")
        finally:
            recorder_manager.ctypes.windll.user32 = original_user32

    def test_start_window_rejects_window_without_rect(self):
        class FakeUser32:
            def IsWindow(self, hwnd):
                return True

            def GetWindowTextLengthW(self, hwnd):
                return 0

        import recorder.recorder_manager as recorder_manager
        original_user32 = recorder_manager.ctypes.windll.user32
        recorder_manager.ctypes.windll.user32 = FakeUser32()
        try:
            manager = RecorderManager(self.config)
            with patch.object(RecorderManager, "_get_window_rect", return_value=None):
                self.assertFalse(manager.start_window(123))
                self.assertEqual(manager.get_window_hwnd(), 123)
                diagnostic = manager.get_last_window_diagnostic()
                self.assertEqual(diagnostic.reason, WindowFailureReason.RECT_UNAVAILABLE)
                self.assertEqual(diagnostic.hwnd, 123)
                self.assertEqual(diagnostic.title, "")
                self.assertEqual(diagnostic.mode, "window")
                self.assertEqual(diagnostic.stage, "get_window_rect")
                self.assertIsNone(diagnostic.rect)
                self.assertEqual(diagnostic.foreground_result, "not_attempted")
        finally:
            recorder_manager.ctypes.windll.user32 = original_user32

    def test_get_window_rect_returns_none_for_tiny_client_area(self):
        class RectUser32:
            def IsWindow(self, hwnd):
                return True

            def IsWindowVisible(self, hwnd):
                return True

            def IsIconic(self, hwnd):
                return False

            def GetClientRect(self, hwnd, rect_ref):
                rect_ref._obj.right = 5
                rect_ref._obj.bottom = 5
                return True

        import utils.window_geometry as window_geometry
        original_user32 = window_geometry.ctypes.windll.user32
        window_geometry.ctypes.windll.user32 = RectUser32()
        try:
            self.assertIsNone(RecorderManager._get_window_rect(123))
        finally:
            window_geometry.ctypes.windll.user32 = original_user32

    def test_get_window_rect_normalizes_odd_client_size(self):
        class RectUser32:
            def IsWindow(self, hwnd):
                return True

            def IsWindowVisible(self, hwnd):
                return True

            def IsIconic(self, hwnd):
                return False

            def GetClientRect(self, hwnd, rect_ref):
                rect_ref._obj.right = 321
                rect_ref._obj.bottom = 241
                return True

            def ClientToScreen(self, hwnd, point_ref):
                point_ref._obj.x = 10
                point_ref._obj.y = 20
                return True

        import utils.window_geometry as window_geometry
        original_user32 = window_geometry.ctypes.windll.user32
        window_geometry.ctypes.windll.user32 = RectUser32()
        try:
            rect = RecorderManager._get_window_rect(123)
            self.assertEqual((rect.left(), rect.top(), rect.width(), rect.height()), (10, 20, 320, 240))
        finally:
            window_geometry.ctypes.windll.user32 = original_user32


if __name__ == "__main__":
    unittest.main()
