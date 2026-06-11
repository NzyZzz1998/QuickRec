"""
屏幕捕获模块

使用 mss 捕获屏幕或指定区域的图像帧。
"""

import numpy as np
from mss import MSS


class ScreenCapturer:
    """屏幕捕获器"""

    def __init__(self, region: tuple = None):
        """
        初始化屏幕捕获器

        Args:
            region: 捕获区域 (left, top, width, height)
                   None 表示全屏捕获
        """
        self._sct = MSS()
        self._region = region

        if region:
            left, top, width, height = region
            self._monitor = {
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            }
        else:
            # 全屏：使用主显示器
            self._monitor = self._sct.monitors[1]

    def capture_frame(self) -> np.ndarray:
        """
        捕获一帧

        Returns:
            numpy ndarray，形状 (height, width, 3)，BGR 颜色空间
        """
        screenshot = self._sct.grab(self._monitor)
        # mss 返回 BGRA，转为 BGR
        frame = np.array(screenshot, dtype=np.uint8)
        frame = frame[:, :, :3]  # 去掉 alpha 通道
        return frame

    def get_monitor_size(self) -> tuple:
        """
        获取当前捕获区域的尺寸

        Returns:
            (width, height)
        """
        return (self._monitor["width"], self._monitor["height"])

    def close(self):
        """释放资源"""
        self._sct.close()

    def __del__(self):
        self.close()