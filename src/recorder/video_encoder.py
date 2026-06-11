"""
视频编码模块

使用 OpenCV VideoWriter 将帧序列编码为 MP4 文件。
"""

import os
from pathlib import Path

import cv2
import numpy as np


class VideoEncoder:
    """视频编码器（基于 OpenCV VideoWriter）"""

    def __init__(self, file_path: str, fps: int, frame_size: tuple, bitrate: int = None):
        """
        初始化视频编码器

        Args:
            file_path: 输出 MP4 文件路径
            fps: 帧率
            frame_size: 帧尺寸 (width, height)
            bitrate: 码率 (bps)，None 则使用默认
        """
        self._file_path = file_path
        self._fps = fps
        self._frame_size = frame_size  # (width, height)
        self._frame_count = 0
        self._is_open = False

        # 确保目录存在
        directory = os.path.dirname(file_path)
        if directory:
            Path(directory).mkdir(parents=True, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(
            file_path, fourcc, fps, frame_size
        )

        if not self._writer.isOpened():
            raise RuntimeError(f"无法创建视频文件: {file_path}")

        self._is_open = True

    def write_frame(self, frame: np.ndarray) -> bool:
        """
        写入一帧

        Args:
            frame: BGR numpy ndarray, 形状为 (height, width, 3)

        Returns:
            True 写入成功, False 写入失败
        """
        if not self._is_open:
            return False

        try:
            self._writer.write(frame)
            self._frame_count += 1
            return True
        except Exception:
            return False

    def close(self):
        """完成写入并关闭文件"""
        if self._is_open:
            self._writer.release()
            self._is_open = False

    def is_open(self) -> bool:
        """编码器是否处于打开状态"""
        return self._is_open

    def get_frame_count(self) -> int:
        """已写入帧数"""
        return self._frame_count

    def __del__(self):
        self.close()