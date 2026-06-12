"""
屏幕捕获模块

使用 dxcam 通过 DirectX 快速捕获屏幕帧。
dxcam 的创建和销毁都在调用线程中执行，避免跨线程问题。
"""


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
        self._camera = None
        self._started = False

        if region:
            left, top, width, height = region
            # dxcam 用 region=(left, top, right, bottom)
            self._dxcam_region = (left, top, left + width, top + height)
        else:
            self._dxcam_region = None

    def start(self):
        """启动捕获（延迟初始化，应在录制线程中调用）"""
        import dxcam
        self._camera = dxcam.create(output_idx=0, output_color="BGR")
        self._camera.start(target_fps=60, region=self._dxcam_region)
        self._started = True

    def capture_frame(self):
        """
        捕获一帧

        Returns:
            numpy ndarray，形状 (height, width, 3)，BGR 颜色空间
        """
        if not self._started:
            return None
        frame = self._camera.get_latest_frame()
        if frame is None:
            # 首帧可能为 None，短暂等待后重试
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
            # 全屏：从系统获取
            import ctypes
            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))

    def close(self):
        """释放资源"""
        if self._camera:
            self._camera.stop()
            self._camera.release()
            self._camera = None
        self._started = False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass