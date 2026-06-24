"""
磁盘空间检查模块

检查目标磁盘是否有足够空间继续录制。
v1.3 新增：录制前预警/阻断阈值检查。
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

# v1.3 新增：录制前预警阈值
WARN_THRESHOLD_MB = 1024    # < 1GB 弹窗告知
BLOCK_THRESHOLD_MB = 200    # < 200MB 阻断录制


class DiskChecker:
    """磁盘空间检查"""

    @staticmethod
    def get_free_space(path: str) -> int:
        if os.path.isfile(path):
            path = os.path.dirname(path)
        _, _, free = shutil.disk_usage(path)
        return free

    @staticmethod
    def estimate_size_per_minute(quality: str, fps: int = 30) -> int:
        bitrate = BITRATE.get(quality, BITRATE["medium"])
        bytes_per_sec = bitrate / 8
        bytes_per_min = bytes_per_sec * 60
        return int(bytes_per_min / BYTES_PER_MB)

    @staticmethod
    def is_low_space(path: str, quality: str = "medium", buffer_minutes: int = 5) -> bool:
        size_per_min = DiskChecker.estimate_size_per_minute(quality)
        threshold = size_per_min * buffer_minutes
        free = DiskChecker.get_free_space(path)
        return free < threshold * BYTES_PER_MB

    @staticmethod
    def check_before_recording(save_path: str) -> tuple:
        """检查录制前磁盘空间

        Returns:
            ("ok", free_mb)    — 空间充足
            ("warn", free_mb)  — < 1GB，建议提醒
            ("block", free_mb) — < 200MB，阻断录制
        """
        free_bytes = DiskChecker.get_free_space(save_path)
        free_mb = free_bytes // BYTES_PER_MB
        if free_mb < BLOCK_THRESHOLD_MB:
            return ("block", free_mb)
        if free_mb < WARN_THRESHOLD_MB:
            return ("warn", free_mb)
        return ("ok", free_mb)


def show_disk_warning(free_mb: int, block: bool, parent=None) -> bool:
    """显示磁盘空间不足对话框

    Args:
        free_mb: 剩余空间（MB）
        block: True=阻断（仅确定），False=预警（是/否）

    Returns:
        True=继续录制，False=取消或阻断
    """
    from PyQt5.QtWidgets import QMessageBox
    from PyQt5.QtCore import Qt

    if block:
        QMessageBox.critical(
            parent, "QuickRec",
            f"磁盘剩余空间严重不足（剩余 {free_mb} MB），无法开始录制。\n请清理磁盘后重试。",
        )
        return False

    reply = QMessageBox.warning(
        parent, "QuickRec",
        f"磁盘剩余空间不足（剩余 {free_mb} MB），录制可能中断。\n是否继续？",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    return reply == QMessageBox.Yes
