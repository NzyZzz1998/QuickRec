"""
屏幕捕获模块

使用 dxcam 通过 DirectX 快速捕获屏幕帧。
dxcam 的创建和销毁都在调用线程中执行，避免跨线程问题。
"""

import logging

from utils.window_geometry import normalize_capture_region

logger = logging.getLogger("QuickRec")


class ScreenCapturer:
    """屏幕捕获器（基于 dxcam）"""

    def __init__(self, region: tuple = None):
        """
        初始化屏幕捕获器

        Args:
            region: 捕获区域 (left, top, width, height)
                   None 表示全屏捕获
        """
        self._region = normalize_capture_region(region) if region else None
        if region and self._region is None:
            raise ValueError(f"invalid capture region: {region}")
        self._camera = None
        self._started = False
        self._last_dxcam_region = None  # 上一次 dxcam 使用的 region，避免重复重启

        if self._region:
            left, top, width, height = self._region
            # dxcam 用 region=(left, top, right, bottom)
            self._dxcam_region = (left, top, left + width, top + height)
        else:
            self._dxcam_region = None

    def start(self):
        """启动捕获（延迟初始化，应在录制线程中调用）"""
        import dxcam
        self._camera = dxcam.create(output_idx=0, output_color="BGR")
        if self._dxcam_region:
            logger.info(f"ScreenCapturer region: {self._dxcam_region}")
        self._camera.start(target_fps=60, region=self._dxcam_region)
        self._last_dxcam_region = self._dxcam_region
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

    def update_region(self, region: tuple):
        """动态更新捕获区域（用于窗口录制跟踪窗口位置）

        Args:
            region: (left, top, width, height) 新的捕获区域
        """
        normalized = normalize_capture_region(region)
        if normalized is None:
            raise ValueError(f"invalid capture region: {region}")
        self._region = normalized
        left, top, width, height = normalized
        new_dxcam_region = (left, top, left + width, top + height)

        # 与上次相同则跳过重启，避免每帧都重建 dxcam
        if self._last_dxcam_region == new_dxcam_region:
            return

        self._dxcam_region = new_dxcam_region
        self._last_dxcam_region = new_dxcam_region

        if self._camera and self._started:
            try:
                self._camera.stop()
                self._camera.release()
                import dxcam
                self._camera = dxcam.create(output_idx=0, output_color="BGR")
                self._camera.start(target_fps=60, region=self._dxcam_region)
            except Exception as e:
                logger.error(f"更新捕获区域失败: {e}")
                # 重建失败时确保状态干净，避免后续 capture_frame 在坏状态上调用
                try:
                    if self._camera:
                        self._camera.release()
                except Exception:
                    pass
                self._camera = None
                self._started = False

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

    def get_capture_region(self) -> tuple | None:
        return self._region

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
