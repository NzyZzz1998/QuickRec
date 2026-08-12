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


class _FakeCamera:
    def __init__(self, frames=None):
        self.frames = list(frames or [])
        self.start_calls = []
        self.release_calls = 0

    def start(self, *, target_fps, region, video_mode=True):
        self.start_calls.append((target_fps, region, video_mode))

    def grab(self, *args, **kwargs):
        return self.frames.pop(0) if self.frames else None

    def get_latest_frame(self):
        raise AssertionError("capture_frame must not use blocking get_latest_frame")

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


class TestScreenCapturerStability(unittest.TestCase):
    def test_start_uses_fixed_lite_fps_and_video_mode(self):
        camera = _FakeCamera([np.zeros((20, 30, 3), dtype=np.uint8)])
        create = Mock(return_value=camera)
        capturer = ScreenCapturer(target_fps=60)

        with patch.dict(sys.modules, {"dxcam": SimpleNamespace(create=create)}):
            capturer.start()

        self.assertEqual(camera.start_calls, [(60, None, True)])

    def test_static_desktop_reuses_initial_frame_without_blocking(self):
        expected = np.zeros((20, 30, 3), dtype=np.uint8)
        camera = _FakeCamera([expected])
        create = Mock(return_value=camera)
        capturer = ScreenCapturer(target_fps=60)

        with patch.dict(sys.modules, {"dxcam": SimpleNamespace(create=create)}):
            capturer.start()
            frame = capturer.capture_frame()

        self.assertIs(frame, expected)

    def test_request_stop_signals_dxcam_events(self):
        camera = _AsyncStopCamera()
        capturer = ScreenCapturer()
        capturer._camera = camera
        capturer._started = True

        self.assertTrue(capturer.request_stop())
        self.assertTrue(camera._DXCamera__stop_capture.is_set())
        self.assertTrue(camera._DXCamera__frame_available.is_set())
        self.assertEqual(camera.release_calls, 0)

    def test_close_returns_when_dxcam_release_stalls(self):
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

        camera.allow_release.set()
        capturer._release_thread.join(timeout=1)
        self.assertFalse(capturer._release_thread.is_alive())


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

    def test_get_monitor_size_fullscreen(self):
        """测试全屏模式获取显示器尺寸"""
        capturer = ScreenCapturer()
        try:
            size = capturer.get_monitor_size()
            self.assertGreater(size[0], 0)  # width > 0
            self.assertGreater(size[1], 0)  # height > 0
        finally:
            capturer.close()

    def test_consecutive_frames(self):
        """测试连续捕获（帧率稳定性）"""
        import time
        capturer = ScreenCapturer()
        try:
            start = time.time()
            for _ in range(10):
                frame = capturer.capture_frame()
                self.assertGreater(frame.shape[0], 0)
            elapsed = time.time() - start
            # 10帧应在合理时间内完成（< 2秒）
            self.assertLess(elapsed, 2.0)
        finally:
            capturer.close()

    def test_close_and_reuse(self):
        """测试 close 后不可再捕获"""
        capturer = ScreenCapturer()
        capturer.close()
        # close 后再捕获应报错
        with self.assertRaises(Exception):
            capturer.capture_frame()


if __name__ == "__main__":
    unittest.main()
