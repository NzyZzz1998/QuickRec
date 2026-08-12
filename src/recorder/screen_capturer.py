"""
屏幕捕获模块

使用 dxcam 通过 DirectX 快速捕获屏幕帧。
dxcam 的创建和销毁都在调用线程中执行，避免跨线程问题。
"""

import logging
import threading

logger = logging.getLogger("QuickRec")


class ScreenCapturer:
    """屏幕捕获器（基于 dxcam）"""

    def __init__(
        self,
        target_fps: int = 60,
    ):
        """
        初始化屏幕捕获器

        Args:
            target_fps: Lite 全屏捕获目标帧率
        """
        self._camera = None
        self._started = False
        self._target_fps = max(int(target_fps), 1)
        self._fallback_frame = None
        self._release_thread: threading.Thread | None = None
        self._release_timeout_seconds = 1.0

    def start(self):
        """启动捕获（延迟初始化，应在录制线程中调用）"""
        import dxcam
        self._camera = dxcam.create(output_idx=0, output_color="BGR")
        self._fallback_frame = self._grab_initial_frame()
        self._start_camera()
        self._started = True

    def _start_camera(self) -> None:
        camera = self._camera
        if camera is None:
            raise RuntimeError("DXCamera is not initialized")
        camera.start(
            target_fps=self._target_fps,
            region=None,
            video_mode=True,
        )

    def capture_frame(self):
        """
        捕获一帧

        Returns:
            numpy ndarray，形状 (height, width, 3)，BGR 颜色空间
        """
        if not self._started:
            return None
        # get_latest_frame() 在静态桌面上可能无限等待新帧；grab() 只读取
        # 当前缓冲区，因此停止和取消始终能及时返回。
        frame = self._camera.grab()
        if frame is None:
            # 首帧可能为 None，短暂等待后重试
            import time
            time.sleep(0.01)
            frame = self._camera.grab()
        if frame is not None:
            self._fallback_frame = frame
        elif self._fallback_frame is not None:
            frame = self._fallback_frame
        return frame

    def _grab_initial_frame(self):
        camera = self._camera
        if camera is None:
            return None
        try:
            frame = camera.grab(region=None, new_frame_only=False)
        except TypeError:
            frame = camera.grab()
        if frame is not None:
            return frame
        return self._grab_desktop_fallback()

    def _grab_desktop_fallback(self):
        """在 DXCam 暂无首帧时准备一张静态桌面回退帧。"""
        try:
            import numpy as np
            from PIL import ImageGrab

            image = ImageGrab.grab(
                bbox=None,
                all_screens=False,
            ).convert("RGB")
            return np.asarray(image, dtype=np.uint8)[:, :, ::-1].copy()
        except Exception as exc:
            logger.warning(
                "static desktop fallback capture failed: error_type=%s",
                type(exc).__name__,
            )
            return None

    def get_monitor_size(self) -> tuple:
        """
        获取当前捕获区域的尺寸

        Returns:
            (width, height)
        """
        import ctypes
        user32 = ctypes.windll.user32
        return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))

    def request_stop(self) -> bool:
        """唤醒并请求 DXCam 捕获线程退出，不在调用线程等待释放。"""
        camera = self._camera
        if camera is None:
            return False
        stop_event = getattr(camera, "_DXCamera__stop_capture", None)
        frame_available = getattr(camera, "_DXCamera__frame_available", None)
        if not hasattr(stop_event, "set"):
            logger.info("DXCamera asynchronous stop is unavailable")
            return False
        stop_event.set()
        if hasattr(frame_available, "set"):
            frame_available.set()
        logger.info("DXCamera asynchronous stop requested")
        return True

    def close(self):
        """释放资源"""
        camera = self._camera
        self._camera = None
        self._started = False
        self._fallback_frame = None
        if camera is None:
            return

        def release_camera() -> None:
            try:
                camera.release()
            except Exception as exc:
                logger.warning("DXCamera release failed: %s", exc)

        self._release_thread = threading.Thread(
            target=release_camera,
            name="QuickRecLiteDXCameraRelease",
            daemon=True,
        )
        self._release_thread.start()
        self._release_thread.join(timeout=self._release_timeout_seconds)
        if self._release_thread.is_alive():
            logger.warning(
                "DXCamera release exceeded %.2fs; recording finalization continues",
                self._release_timeout_seconds,
            )

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
