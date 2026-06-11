"""
DiskChecker 单元测试
"""

import os
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.disk_checker import DiskChecker, BITRATE, BYTES_PER_MB


class TestDiskChecker(unittest.TestCase):
    """DiskChecker 测试类"""

    def test_estimate_size_per_minute(self):
        """测试估算文件大小"""
        # 8000kbps = ~60MB/min (十进制 MB 约 57MB，二进制 MB 约 60)
        high = DiskChecker.estimate_size_per_minute("high")
        self.assertAlmostEqual(high, 60, delta=5)

        medium = DiskChecker.estimate_size_per_minute("medium")
        self.assertAlmostEqual(medium, 30, delta=3)

        low = DiskChecker.estimate_size_per_minute("low")
        self.assertAlmostEqual(low, 15, delta=2)

    def test_estimate_size_unknown_quality(self):
        """测试未知画质的默认值"""
        result = DiskChecker.estimate_size_per_minute("unknown")
        expected = DiskChecker.estimate_size_per_minute("medium")
        self.assertEqual(result, expected)

    def test_get_free_space(self):
        """测试获取磁盘可用空间"""
        # 使用当前系统目录
        free = DiskChecker.get_free_space("C:/")
        self.assertIsInstance(free, int)
        self.assertGreater(free, 0)

    def test_get_free_space_with_file_path(self):
        """测试传入文件路径时返回所在目录空间"""
        free = DiskChecker.get_free_space(__file__)
        self.assertIsInstance(free, int)
        self.assertGreater(free, 0)

    def test_is_low_space_true(self):
        """测试空间不足判断"""
        # 用一个极小的目录（临时目录通常很大，这里测试逻辑）
        free = DiskChecker.get_free_space("C:/")
        # 1TB 的阈值肯定不够，应该返回 True
        self.assertTrue(DiskChecker.is_low_space("C:/", buffer_minutes=10_000_000))

    def test_is_low_space_false(self):
        """测试空间充足判断"""
        # 1 分钟 buffer 通常足够
        self.assertFalse(DiskChecker.is_low_space("C:/", "low", buffer_minutes=1))


if __name__ == "__main__":
    unittest.main()
