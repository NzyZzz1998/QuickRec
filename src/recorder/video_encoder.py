"""
视频编码模块（v1.3 重写）

使用 FFmpeg subprocess pipe 实现 H.264 实时编码。
dxcam BGR24 帧直接通过 stdin pipe 送 FFmpeg，无需 JPEG 临时文件。
停止录制后文件几乎即时可用（无音频时）。
"""

import logging
import subprocess

import numpy as np

logger = logging.getLogger("QuickRec")

# H.264 固定编码参数（不暴露给用户）
_CRF = 23
_PRESET = "medium"


class VideoEncoder:
    """H.264 视频编码器（FFmpeg pipe）"""

    def __init__(self, output_path: str, fps: int, frame_size: tuple, ffmpeg_path: str):
        """
        Args:
            output_path: 输出 MP4 文件路径
            fps: 帧率
            frame_size: (width, height)
            ffmpeg_path: FFmpeg 可执行文件路径
        """
        self._output_path = output_path
        self._fps = fps
        self._frame_size = frame_size
        self._frame_count = 0
        self._is_open = False

        w, h = frame_size
        cmd = [
            ffmpeg_path, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{w}x{h}",
            "-r", str(fps),
            "-pix_fmt", "bgr24",
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-crf", str(_CRF),
            "-preset", _PRESET,
            "-pix_fmt", "yuv420p",
            output_path,
        ]

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self._is_open = True

    def write_frame(self, frame: np.ndarray) -> bool:
        """写入一帧 BGR24 数据到 FFmpeg stdin"""
        if not self._is_open:
            return False
        try:
            self._proc.stdin.write(frame.tobytes())
            self._frame_count += 1
            return True
        except (BrokenPipeError, OSError):
            self._is_open = False
            return False

    def close(self) -> bool:
        """关闭 stdin，等待 FFmpeg 完成编码"""
        if not self._is_open:
            return True
        self._is_open = False
        try:
            self._proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            self._proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
            logger.error("FFmpeg 编码超时，已强制终止")
            return False
        if self._proc.returncode != 0:
            err = self._proc.stderr.read().decode(errors="replace")
            logger.error(f"FFmpeg 编码失败 (returncode={self._proc.returncode}): {err}")
            return False
        logger.info(f"视频编码完成: {self._output_path} ({self._frame_count} 帧)")
        return True

    def is_open(self) -> bool:
        return self._is_open

    def get_frame_count(self) -> int:
        return self._frame_count

    def __del__(self):
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
        except Exception:
            pass
