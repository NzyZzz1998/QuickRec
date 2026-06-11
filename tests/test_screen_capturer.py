"""
ScreenCapturer 单元测试
"""

import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
from recorder.screen_capturer import ScreenCapturer


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