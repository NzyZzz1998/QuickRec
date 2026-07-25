"""
视频编码模块（v1.3 重写）

使用 FFmpeg subprocess pipe 实现 H.264 实时编码。
dxcam BGR24 帧直接通过 stdin pipe 送 FFmpeg，无需 JPEG 临时文件。
停止录制后文件几乎即时可用（无音频时）。
"""

import logging
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger("QuickRec")

# H.264 固定编码参数（不暴露给用户）
# preset=superfast 降低编码缓冲，停止时 flush 近乎瞬时（lookahead=0）
_CRF = 23
_PRESET = "superfast"


@dataclass(frozen=True)
class EncoderPerformance:
    completed_frames: int
    completion_times: tuple[float, ...]
    backlog_samples: tuple[tuple[float, float], ...]


class VideoEncoder:
    """H.264 视频编码器（FFmpeg pipe）"""

    def __init__(
        self,
        output_path: str,
        fps: int,
        frame_size: tuple,
        ffmpeg_path: str,
        high_frame_rate: bool = False,
    ):
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
        self._high_frame_rate = high_frame_rate
        self._frame_queue: queue.Queue[tuple[int, np.ndarray] | None] | None = None
        self._worker: threading.Thread | None = None
        self._worker_error: BaseException | None = None
        self._performance_started = time.perf_counter()
        self._completion_times: list[float] = []
        self._backlog_samples: list[tuple[float, float]] = []

        output_dir = os.path.dirname(os.path.abspath(output_path))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        w, h = frame_size
        cmd = [
            ffmpeg_path, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{w}x{h}",
            "-r", str(fps),
            "-pix_fmt", "yuv420p" if high_frame_rate else "bgr24",
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-crf", str(_CRF),
            "-preset", _PRESET,
            "-tune", "zerolatency",
            "-pix_fmt", "yuv420p",
            output_path,
        ]

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            # stderr 必须丢到 DEVNULL；用 PIPE 而不读会让 FFmpeg 的进度日志
            # 填满 OS 缓冲（~64KB）后阻塞 FFmpeg 写 stderr，最终录制看似卡死、
            # 关闭时 wait 超时被 kill（v1.3 实测的 Bug）。
            stderr=subprocess.DEVNULL,
        )
        self._is_open = True
        if self._high_frame_rate:
            self._frame_queue = queue.Queue(maxsize=8)
            self._worker = threading.Thread(
                target=self._feed_high_frame_rate,
                name="QuickRec-EncoderFeed",
                daemon=True,
            )
            self._worker.start()

    def write_frame(
        self,
        frame: np.ndarray,
        *,
        cancel_event: threading.Event | None = None,
        timeout_seconds: float | None = None,
    ) -> bool:
        """写入一帧 BGR24 数据到 FFmpeg stdin"""
        if not self._is_open:
            return False
        if self._worker_error is not None:
            self._is_open = False
            return False
        if self._frame_queue is not None:
            deadline = (
                time.monotonic() + timeout_seconds
                if timeout_seconds is not None
                else None
            )
            while self._is_open:
                if cancel_event is not None and cancel_event.is_set():
                    return False
                if self._worker_error is not None:
                    self._is_open = False
                    return False
                if deadline is not None and time.monotonic() >= deadline:
                    logger.warning(
                        "high frame rate encoder queue remained full for %.3f seconds",
                        timeout_seconds,
                    )
                    return False
                try:
                    sequence = self._frame_count + 1
                    wait_timeout = 0.05
                    if deadline is not None:
                        wait_timeout = max(
                            min(deadline - time.monotonic(), wait_timeout),
                            0.001,
                        )
                    self._frame_queue.put((sequence, frame), timeout=wait_timeout)
                    self._frame_count += 1
                    return True
                except queue.Full:
                    continue
            return False
        try:
            assert self._proc.stdin is not None
            self._proc.stdin.write(frame.tobytes())
            self._frame_count += 1
            return True
        except (BrokenPipeError, OSError):
            self._is_open = False
            return False

    def _feed_high_frame_rate(self) -> None:
        assert self._frame_queue is not None
        try:
            while True:
                item = self._frame_queue.get()
                if item is None:
                    return
                sequence, frame = item
                prepared = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
                assert self._proc.stdin is not None
                self._proc.stdin.write(memoryview(prepared).cast("B"))
                elapsed = time.perf_counter() - self._performance_started
                self._completion_times.append(elapsed)
                ideal_elapsed = sequence / self._fps
                self._backlog_samples.append(
                    (elapsed, max(0.0, (elapsed - ideal_elapsed) * 1000.0))
                )
        except BaseException as exc:
            self._worker_error = exc

    def _finish_worker(self) -> bool:
        if self._worker is None or self._frame_queue is None:
            return True
        if self._worker_error is None:
            while self._worker.is_alive():
                try:
                    self._frame_queue.put(None, timeout=0.05)
                    break
                except queue.Full:
                    if self._worker_error is not None:
                        break
        self._worker.join(timeout=15)
        if self._worker.is_alive():
            logger.error("high frame rate encoder feed did not stop in time")
            return False
        if self._worker_error is not None:
            logger.error(f"high frame rate encoder feed failed: {self._worker_error}")
            return False
        return True

    def close(self) -> bool:
        """关闭 stdin，等待 FFmpeg 完成编码"""
        if not self._is_open:
            return self._worker_error is None
        self._is_open = False
        worker_ok = self._finish_worker()
        try:
            assert self._proc.stdin is not None
            self._proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            self._proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
            logger.error(f"FFmpeg 编码超时，已强制终止（{self._frame_count} 帧；stderr 已丢弃无法诊断）")
            return False
        if not worker_ok:
            return False
        if self._proc.returncode != 0:
            logger.error(f"FFmpeg 编码失败 (returncode={self._proc.returncode})")
            return False
        logger.info(f"视频编码完成: {self._output_path} ({self._frame_count} 帧)")
        return True

    def is_open(self) -> bool:
        return self._is_open

    def get_frame_count(self) -> int:
        return self._frame_count

    def get_performance_snapshot(self) -> EncoderPerformance:
        return EncoderPerformance(
            completed_frames=len(self._completion_times),
            completion_times=tuple(self._completion_times),
            backlog_samples=tuple(self._backlog_samples),
        )

    def __del__(self):
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
        except Exception:
            pass
