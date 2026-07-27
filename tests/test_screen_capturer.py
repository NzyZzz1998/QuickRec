"""
ScreenCapturer 单元测试
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pytest

from recorder.screen_capturer import ScreenCapturer


class _BufferedCameraWithoutNewFrame:
    def __init__(self):
        self.grab_calls = 0

    def grab(self):
        self.grab_calls += 1
        return None

    def get_latest_frame(self):
        raise AssertionError("capture_frame must not use the blocking dxcam API")


class _FakeCamera:
    def __init__(self, frames=None, *, start_error=None):
        self.frames = list(frames or [])
        self.start_error = start_error
        self.start_calls = []
        self.stop_calls = 0
        self.release_calls = 0

    def start(self, *, target_fps, region, video_mode=True):
        self.start_calls.append((target_fps, region, video_mode))
        if self.start_error is not None:
            raise self.start_error

    def grab(self):
        return self.frames.pop(0) if self.frames else None

    def stop(self):
        self.stop_calls += 1

    def release(self):
        self.release_calls += 1


class _BlockingReleaseCamera(_FakeCamera):
    def __init__(self):
        super().__init__()
        self.release_started = threading.Event()
        self.allow_release = threading.Event()

    def release(self):
        self.release_calls += 1
        self.release_started.set()
        self.allow_release.wait(timeout=2)


class _AsyncStopCamera(_FakeCamera):
    def __init__(self):
        super().__init__()
        self._DXCamera__stop_capture = threading.Event()
        self._DXCamera__frame_available = threading.Event()


class TestScreenCapturerNonBlocking(unittest.TestCase):
    def test_capture_frame_returns_none_before_start(self):
        self.assertIsNone(ScreenCapturer().capture_frame())

    def test_capture_frame_does_not_block_when_dxcam_has_no_new_frame(self):
        camera = _BufferedCameraWithoutNewFrame()
        capturer = ScreenCapturer()
        capturer._camera = camera
        capturer._started = True

        frame = capturer.capture_frame()

        self.assertIsNone(frame)
        self.assertEqual(camera.grab_calls, 2)

    def test_capture_frame_returns_buffered_frame_without_retry(self):
        expected = np.zeros((20, 30, 3), dtype=np.uint8)
        camera = _FakeCamera([expected])
        capturer = ScreenCapturer()
        capturer._camera = camera
        capturer._started = True

        frame = capturer.capture_frame()

        self.assertIs(frame, expected)
        self.assertEqual(camera.frames, [])

    def test_start_creates_dxcam_with_expected_region(self):
        camera = _FakeCamera()
        create = Mock(return_value=camera)
        capturer = ScreenCapturer(region=(10, 20, 321, 241))

        with patch.dict(sys.modules, {"dxcam": SimpleNamespace(create=create)}):
            capturer.start()

        create.assert_called_once_with(output_idx=0, output_color="BGR")
        self.assertEqual(camera.start_calls, [(60, (10, 20, 330, 260), True)])
        self.assertTrue(capturer._started)
        self.assertEqual(capturer._last_dxcam_region, (10, 20, 330, 260))

    def test_invalid_region_is_rejected(self):
        with self.assertRaises(ValueError):
            ScreenCapturer(region=(0, 0, 1, 1))

    def test_update_region_skips_unchanged_region(self):
        capturer = ScreenCapturer(region=(10, 20, 320, 240))
        camera = _FakeCamera()
        capturer._camera = camera
        capturer._started = True
        capturer._last_dxcam_region = capturer._dxcam_region

        capturer.update_region((10, 20, 320, 240))

        self.assertEqual(camera.stop_calls, 0)
        self.assertEqual(camera.release_calls, 0)

    def test_update_region_rebuilds_running_camera(self):
        old_camera = _FakeCamera()
        new_camera = _FakeCamera()
        create = Mock(return_value=new_camera)
        capturer = ScreenCapturer(region=(0, 0, 320, 240))
        capturer._camera = old_camera
        capturer._started = True
        capturer._last_dxcam_region = capturer._dxcam_region

        with patch.dict(sys.modules, {"dxcam": SimpleNamespace(create=create)}):
            capturer.update_region((11, 22, 333, 245))

        self.assertEqual(old_camera.stop_calls, 1)
        self.assertEqual(old_camera.release_calls, 1)
        self.assertEqual(new_camera.start_calls, [(60, (11, 22, 343, 266), True)])
        self.assertIs(capturer._camera, new_camera)
        self.assertTrue(capturer._started)

    def test_update_region_failure_leaves_clean_state(self):
        old_camera = _FakeCamera()
        failed_camera = _FakeCamera(start_error=RuntimeError("capture failed"))
        capturer = ScreenCapturer(region=(0, 0, 320, 240))
        capturer._camera = old_camera
        capturer._started = True
        capturer._last_dxcam_region = capturer._dxcam_region

        with patch.dict(
            sys.modules,
            {"dxcam": SimpleNamespace(create=Mock(return_value=failed_camera))},
        ):
            capturer.update_region((20, 30, 320, 240))

        self.assertEqual(failed_camera.release_calls, 1)
        self.assertIsNone(capturer._camera)
        self.assertFalse(capturer._started)

    def test_update_region_rejects_invalid_dimensions(self):
        capturer = ScreenCapturer(region=(0, 0, 320, 240))

        with self.assertRaises(ValueError):
            capturer.update_region((0, 0, 1, 1))

    def test_region_accessors_use_normalized_dimensions(self):
        capturer = ScreenCapturer(region=(10, 20, 321, 241))

        self.assertEqual(capturer.get_capture_region(), (10, 20, 320, 240))
        self.assertEqual(capturer.get_monitor_size(), (320, 240))

    def test_close_releases_camera_and_resets_state(self):
        camera = _FakeCamera()
        capturer = ScreenCapturer()
        capturer._camera = camera
        capturer._started = True

        capturer.close()

        self.assertEqual(camera.stop_calls, 0)
        self.assertEqual(camera.release_calls, 1)
        self.assertIsNone(capturer._camera)
        self.assertFalse(capturer._started)

    def test_close_does_not_block_recording_finalization_when_dxcam_release_stalls(self):
        camera = _BlockingReleaseCamera()
        capturer = ScreenCapturer()
        capturer._camera = camera
        capturer._started = True
        capturer._release_timeout_seconds = 0.02

        started = time.perf_counter()
        capturer.close()
        elapsed = time.perf_counter() - started

        self.assertTrue(camera.release_started.is_set())
        self.assertLess(elapsed, 0.2)
        self.assertIsNone(capturer._camera)
        self.assertFalse(capturer._started)

        camera.allow_release.set()
        capturer._release_thread.join(timeout=1)
        self.assertFalse(capturer._release_thread.is_alive())

    def test_request_stop_signals_dxcam_without_waiting_for_release(self):
        camera = _AsyncStopCamera()
        capturer = ScreenCapturer()
        capturer._camera = camera
        capturer._started = True

        requested = capturer.request_stop()

        self.assertTrue(requested)
        self.assertTrue(camera._DXCamera__stop_capture.is_set())
        self.assertTrue(camera._DXCamera__frame_available.is_set())
        self.assertEqual(camera.stop_calls, 0)
        self.assertEqual(camera.release_calls, 0)
        self.assertIs(capturer._camera, camera)

    def test_request_stop_falls_back_when_dxcam_contract_is_unavailable(self):
        capturer = ScreenCapturer()
        capturer._camera = _FakeCamera()
        capturer._started = True

        self.assertFalse(capturer.request_stop())

    def test_120fps_keeps_static_desktop_frames_available(self):
        camera = _FakeCamera()
        create = Mock(return_value=camera)
        capturer = ScreenCapturer(target_fps=120)

        with patch.dict(sys.modules, {"dxcam": SimpleNamespace(create=create)}):
            capturer.start()

        self.assertEqual(camera.start_calls, [(120, None, True)])

    def test_120fps_reuses_prestart_frame_when_ring_buffer_is_still_empty(self):
        expected = np.zeros((20, 30, 3), dtype=np.uint8)
        camera = _FakeCamera([expected])
        create = Mock(return_value=camera)
        capturer = ScreenCapturer(target_fps=120)

        with patch.dict(sys.modules, {"dxcam": SimpleNamespace(create=create)}):
            capturer.start()
            frame = capturer.capture_frame()

        self.assertIs(frame, expected)

    def test_region_restart_preserves_effective_target_fps(self):
        old_camera = _FakeCamera()
        new_camera = _FakeCamera()
        capturer = ScreenCapturer(region=(0, 0, 320, 240), target_fps=60)
        capturer._camera = old_camera
        capturer._started = True

        with patch.dict(
            sys.modules,
            {"dxcam": SimpleNamespace(create=Mock(return_value=new_camera))},
        ):
            capturer.update_region((10, 20, 320, 240))

        self.assertEqual(new_camera.start_calls, [(60, (10, 20, 330, 260), True)])


@pytest.mark.hardware
class TestScreenCapturer(unittest.TestCase):
    """ScreenCapturer 测试类"""

    def test_fullscreen_capture(self):
        """测试全屏捕获返回正确分辨率的帧"""
        capturer = ScreenCapturer()
        try:
            frame = capturer.capture_frame()
            self.assertIsInstance(frame, np.ndarray)
            self.assertEqual(len(frame.shape), 3)
            self.assertEqual(frame.shape[2], 3)  # BGR 3通道
            # 帧宽高应大于0
            self.assertGreater(frame.shape[0], 0)  # height
            self.assertGreater(frame.shape[1], 0)  # width
        finally:
            capturer.close()

    def test_region_capture(self):
        """测试区域捕获返回指定尺寸的帧"""
        region = (100, 100, 320, 240)
        capturer = ScreenCapturer(region=region)
        try:
            frame = capturer.capture_frame()
            self.assertEqual(frame.shape[0], 240)  # height
            self.assertEqual(frame.shape[1], 320)  # width
            self.assertEqual(frame.shape[2], 3)    # BGR
        finally:
            capturer.close()

    def test_get_monitor_size_fullscreen(self):
        """测试全屏模式获取显示器尺寸"""
        capturer = ScreenCapturer()
        try:
            size = capturer.get_monitor_size()
            self.assertGreater(size[0], 0)  # width > 0
            self.assertGreater(size[1], 0)  # height > 0
        finally:
            capturer.close()

    def test_get_monitor_size_region(self):
        """测试区域模式获取指定尺寸"""
        region = (100, 100, 320, 240)
        capturer = ScreenCapturer(region=region)
        try:
            size = capturer.get_monitor_size()
            self.assertEqual(size, (320, 240))
        finally:
            capturer.close()

    def test_region_size_is_normalized_to_even_dimensions(self):
        capturer = ScreenCapturer(region=(10, 20, 321, 241))

        self.assertEqual(capturer._region, (10, 20, 320, 240))
        self.assertEqual(capturer._dxcam_region, (10, 20, 330, 260))

    def test_update_region_normalizes_to_even_dimensions(self):
        capturer = ScreenCapturer(region=(0, 0, 200, 200))

        capturer.update_region((11, 22, 333, 245))

        self.assertEqual(capturer._region, (11, 22, 332, 244))
        self.assertEqual(capturer._dxcam_region, (11, 22, 343, 266))

    def test_consecutive_frames(self):
        """测试连续捕获（帧率稳定性）"""
        import time
        capturer = ScreenCapturer(region=(0, 0, 200, 200))
        try:
            start = time.time()
            for _ in range(10):
                frame = capturer.capture_frame()
                self.assertEqual(frame.shape[0], 200)
            elapsed = time.time() - start
            # 10帧应在合理时间内完成（< 2秒）
            self.assertLess(elapsed, 2.0)
        finally:
            capturer.close()

    def test_close_and_reuse(self):
        """测试 close 后不可再捕获"""
        capturer = ScreenCapturer(region=(0, 0, 200, 200))
        capturer.close()
        # close 后再捕获应报错
        with self.assertRaises(Exception):
            capturer.capture_frame()


if __name__ == "__main__":
    unittest.main()
