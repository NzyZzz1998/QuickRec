"""
屏幕捕获模块

使用 dxcam 通过 DirectX 快速捕获屏幕帧。
"""

import dxcam


class ScreenCapturer:
    """屏幕捕获器（基于 dxcam）"""

    def __init__(self, region: tuple = None):
        """
        初始化屏幕捕获器

        Args:
            region: 捕获区域 (left, top, width, height)
                   None 表示全屏捕获
        """
        self._region = region
        self._camera = dxcam.create(output_idx=0, output_color="BGR")

        if region:
            left, top, width, height = region
            # dxcam 用 region=(left, top, right, bottom)
            self._dxcam_region = (left, top, left + width, top + height)
        else:
            self._dxcam_region = None

        # 启动捕获（预加载，减少首帧延迟）
        self._camera.start(target_fps=60, region=self._dxcam_region)

    def capture_frame(self):
        """
        捕获一帧

        Returns:
            numpy ndarray，形状 (height, width, 3)，BGR 颜色空间
        """
        frame = self._camera.get_latest_frame()
        if frame is None:
            # 首帧可能为 None，重试一次
            import time
            time.sleep(0.01)
            frame = self._camera.get_latest_frame()
        return frame

    def get_monitor_size(self) -> tuple:
        """
        获取当前捕获区域的尺寸

        Returns:
            (width, height)
        """
        if self._dxcam_region:
            left, top, right, bottom = self._dxcam_region
            return (right - left, bottom - top)
        else:
            # 全屏：从 dxcam 获取
            import ctypes
            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))

    def close(self):
        """释放资源"""
        if self._camera:
            self._camera.stop()
            self._camera.release()
            self._camera = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass