"""
磁盘空间检查模块

检查目标磁盘是否有足够空间继续录制。
"""

import os
import shutil


# 码率 (bps) -> MB/分钟 映射
BITRATE = {
    "high": 8_000_000,     # 8000 kbps
    "medium": 4_000_000,   # 4000 kbps
    "low": 2_000_000,      # 2000 kbps
}

BYTES_PER_MB = 1024 * 1024


class DiskChecker:
    """磁盘空间检查"""

    @staticmethod
    def get_free_space(path: str) -> int:
        """
        获取指定路径所在磁盘的可用空间

        Args:
            path: 文件或目录路径

        Returns:
            可用字节数
        """
        # 如果 path 是文件，取其所在目录
        if os.path.isfile(path):
            path = os.path.dirname(path)
        _, _, free = shutil.disk_usage(path)
        return free

    @staticmethod
    def estimate_size_per_minute(quality: str, fps: int = 30) -> int:
        """
        估算每分钟录制的文件大小

        Args:
            quality: 画质等级 (high / medium / low)
            fps: 帧率

        Returns:
            估算大小 (MB)
        """
        bitrate = BITRATE.get(quality, BITRATE["medium"])
        # 每秒字节数 -> 分钟
        bytes_per_sec = bitrate / 8
        bytes_per_min = bytes_per_sec * 60
        return int(bytes_per_min / BYTES_PER_MB)

    @staticmethod
    def is_low_space(path: str, quality: str = "medium", buffer_minutes: int = 5) -> bool:
        """
        判断磁盘空间是否低于阈值

        Args:
            path: 文件路径
            quality: 画质等级
            buffer_minutes: 保留的缓冲分钟数

        Returns:
            True 表示空间不足
        """
        size_per_min = DiskChecker.estimate_size_per_minute(quality)
        threshold = size_per_min * buffer_minutes  # 保留 buffer_minutes 分钟的录制空间
        free = DiskChecker.get_free_space(path)
        return free < threshold * BYTES_PER_MB
