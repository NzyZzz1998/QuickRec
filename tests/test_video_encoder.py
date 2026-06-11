"""
VideoEncoder 单元测试
"""

import os
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
from recorder.video_encoder import VideoEncoder


class TestVideoEncoder(unittest.TestCase):
    """VideoEncoder 测试类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.file_path = os.path.join(self.temp_dir, "test_output.mp4")
        self.frame_size = (320, 240)  # width, height
        self.fps = 30

    def tearDown(self):
        # 清理临时文件
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_frame(self):
        """生成测试帧 (240 height, 320 width, 3 BGR)"""
        return np.zeros((self.frame_size[1], self.frame_size[0], 3), dtype=np.uint8)

    def test_write_and_close(self):
        """测试写入帧并关闭生成有效 MP4"""
        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size)
        try:
            for _ in range(30):
                result = encoder.write_frame(self._make_frame())
                self.assertTrue(result)
            self.assertEqual(encoder.get_frame_count(), 30)
            self.assertTrue(encoder.is_open())
        finally:
            encoder.close()

        self.assertFalse(encoder.is_open())
        self.assertTrue(os.path.exists(self.file_path))
        self.assertGreater(os.path.getsize(self.file_path), 0)

    def test_close_then_read(self):
        """测试 close 后文件可被 OpenCV 读取"""
        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size)
        try:
            for _ in range(30):
                encoder.write_frame(self._make_frame())
        finally:
            encoder.close()

        import cv2
        cap = cv2.VideoCapture(self.file_path)
        self.assertTrue(cap.isOpened())
        # 验证帧数
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.assertGreater(frame_count, 0)
        cap.release()

    def test_auto_create_directory(self):
        """测试目录不存在时自动创建"""
        nested_dir = os.path.join(self.temp_dir, "sub", "dir")
        file_path = os.path.join(nested_dir, "output.mp4")
        encoder = VideoEncoder(file_path, self.fps, self.frame_size)
        try:
            encoder.write_frame(self._make_frame())
        finally:
            encoder.close()

        self.assertTrue(os.path.exists(file_path))

    def test_write_after_close_returns_false(self):
        """测试 close 后写入返回 False"""
        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size)
        encoder.close()

        result = encoder.write_frame(self._make_frame())
        self.assertFalse(result)

    def test_frame_count_accurate(self):
        """测试帧计数准确"""
        encoder = VideoEncoder(self.file_path, self.fps, self.frame_size)
        try:
            for i in range(50):
                encoder.write_frame(self._make_frame())
                self.assertEqual(encoder.get_frame_count(), i + 1)
        finally:
            encoder.close()


if __name__ == "__main__":
    unittest.main()