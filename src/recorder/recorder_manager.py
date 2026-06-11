"""
录制控制模块

协调屏幕捕获和视频编码，管理录制生命周期。
"""

import logging
import os
import threading
import time
from enum import Enum

import ctypes

from config import ConfigManager
from recorder.screen_capturer import ScreenCapturer
from recorder.video_encoder import VideoEncoder
from utils.disk_checker import DiskChecker
from utils.file_namer import FileNamer

logger = logging.getLogger("QuickRec")

# Windows 高精度定时器：将系统计时器分辨率提升到 1ms
# 默认约 15.6ms，导致 time.sleep() 不精确，高帧率下帧数不足
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass


class RecorderState(Enum):
    """录制状态枚举"""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"


class RecorderManager:
    """录制管理器"""

    def __init__(self, config: ConfigManager = None):
        self._config = config or ConfigManager()
        self._state = RecorderState.IDLE
        self._capturer: ScreenCapturer = None
        self._encoder: VideoEncoder = None
        self._record_thread: threading.Thread = None
        self._stop_event = threading.Event()
        # _resume_event: set() = 可以录制, clear() = 暂停中（线程等待）
        # 线程在暂停时 wait() 阻塞，resume 时 set() 唤醒
        self._resume_event = threading.Event()
        self._start_time: float = 0
        self._pause_duration: float = 0
        self._pause_start: float = 0
        self._output_path: str = ""
        self._lock = threading.Lock()
        self._cancelled = False

    def start_fullscreen(self) -> bool:
        """开始全屏录制"""
        return self._start(region=None)

    def start_region(self, region: tuple) -> bool:
        """开始区域录制

        Args:
            region: (left, top, width, height)
        """
        return self._start(region=region)

    def pause(self) -> bool:
        """暂停录制"""
        with self._lock:
            if self._state != RecorderState.RECORDING:
                return False
            self._state = RecorderState.PAUSED
            self._pause_start = time.time()
        # clear 使录制线程在 wait() 处阻塞
        self._resume_event.clear()
        return True

    def resume(self) -> bool:
        """恢复录制"""
        with self._lock:
            if self._state != RecorderState.PAUSED:
                return False
            self._state = RecorderState.RECORDING
            self._pause_duration += time.time() - self._pause_start
        # set 唤醒录制线程继续执行
        self._resume_event.set()
        return True

    def stop(self, cancel: bool = False) -> str:
        """停止录制，返回文件路径

        Args:
            cancel: True 表示取消录制，不保存文件
        """
        with self._lock:
            if self._state == RecorderState.IDLE:
                return ""
            self._state = RecorderState.STOPPING

        self._cancelled = cancel

        # 设置停止事件，并唤醒可能阻塞在暂停等待的线程
        self._stop_event.set()
        self._resume_event.set()

        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=5.0)

        if self._encoder:
            self._encoder.close()
            self._encoder = None

        if self._capturer:
            self._capturer.close()
            self._capturer = None

        # 取消录制时删除文件
        if cancel and self._output_path and os.path.exists(self._output_path):
            try:
                os.remove(self._output_path)
                logger.info(f"取消录制，已删除文件: {self._output_path}")
            except OSError:
                pass
            result = ""
        else:
            result = self._output_path

        with self._lock:
            self._state = RecorderState.IDLE

        return result

    def get_state(self) -> RecorderState:
        """获取当前状态"""
        return self._state

    def get_elapsed(self) -> str:
        """获取已录制时长，格式 MM:SS"""
        if self._state == RecorderState.IDLE:
            return "00:00"

        elapsed = time.time() - self._start_time - self._pause_duration
        if self._state == RecorderState.PAUSED:
            elapsed -= (time.time() - self._pause_start)

        minutes = int(elapsed) // 60
        seconds = int(elapsed) % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _start(self, region=None) -> bool:
        """内部启动录制"""
        with self._lock:
            if self._state != RecorderState.IDLE:
                return False

            # 检查磁盘空间
            save_path = self._config.get("save_path")
            quality = self._config.get("quality")
            if DiskChecker.is_low_space(save_path, quality):
                return False

            # 创建捕获器和编码器
            self._capturer = ScreenCapturer(region=region)
            size = self._capturer.get_monitor_size()

            fps = self._config.get("fps", 30)
            self._output_path = FileNamer.generate(save_path)
            self._encoder = VideoEncoder(self._output_path, fps, size)

            self._stop_event.clear()
            self._resume_event.set()  # 初始状态：允许录制
            self._pause_duration = 0
            self._cancelled = False
            self._start_time = time.time()
            self._state = RecorderState.RECORDING

            # 启动录制线程
            self._record_thread = threading.Thread(
                target=self._record_loop, daemon=True
            )
            self._record_thread.start()

        return True

    def _record_loop(self):
        """录制线程主循环

        使用绝对时间戳控制帧率，确保写入帧数与录制时长匹配。
        dxcam 内部线程捕获帧，get_latest_frame() 取最新帧。
        """
        fps = self._config.get("fps", 30)
        frame_interval = 1.0 / fps
        rec_start = time.time()
        frames_written = 0

        while not self._stop_event.is_set():
            # 暂停等待
            if not self._resume_event.wait(timeout=0.1):
                if self._stop_event.is_set():
                    break
                # 恢复后重置时间基准
                rec_start = time.time()
                frames_written = 0
                continue

            if self._stop_event.is_set():
                break

            # 计算应该写到第几帧
            target_frame = int((time.time() - rec_start) / frame_interval)

            try:
                frame = self._capturer.capture_frame()
                if frame is None:
                    continue
            except Exception:
                break

            # 补齐跳过的帧：用当前帧填充
            while frames_written < target_frame:
                if not self._encoder.write_frame(frame):
                    return
                frames_written += 1

            if not self._encoder.write_frame(frame):
                break
            frames_written += 1

            # 等待到下一帧时刻
            next_time = rec_start + frames_written * frame_interval
            wait = next_time - time.time()
            if wait > 0.002:
                time.sleep(wait - 0.001)
            while time.time() < next_time:
                pass