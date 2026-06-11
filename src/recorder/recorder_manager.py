"""
录制控制模块

协调屏幕捕获和视频编码，管理录制生命周期。
"""

import threading
import time
from enum import Enum

from config import ConfigManager
from recorder.screen_capturer import ScreenCapturer
from recorder.video_encoder import VideoEncoder
from utils.disk_checker import DiskChecker
from utils.file_namer import FileNamer


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
        self._pause_event = threading.Event()
        self._start_time: float = 0
        self._pause_duration: float = 0
        self._pause_start: float = 0
        self._output_path: str = ""
        self._lock = threading.Lock()

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
            self._pause_event.set()
            self._pause_start = time.time()
        return True

    def resume(self) -> bool:
        """恢复录制"""
        with self._lock:
            if self._state != RecorderState.PAUSED:
                return False
            self._state = RecorderState.RECORDING
            self._pause_event.clear()
            self._pause_duration += time.time() - self._pause_start
        return True

    def stop(self) -> str:
        """停止录制，返回文件路径"""
        with self._lock:
            if self._state == RecorderState.IDLE:
                return ""
            self._state = RecorderState.STOPPING

        self._stop_event.set()
        if self._state == RecorderState.PAUSED:
            self._pause_event.clear()

        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=5.0)

        if self._encoder:
            self._encoder.close()
            self._encoder = None

        if self._capturer:
            self._capturer.close()
            self._capturer = None

        with self._lock:
            self._state = RecorderState.IDLE

        return self._output_path

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
            self._pause_event.clear()
            self._pause_duration = 0
            self._start_time = time.time()
            self._state = RecorderState.RECORDING

            # 启动录制线程
            self._record_thread = threading.Thread(
                target=self._record_loop, daemon=True
            )
            self._record_thread.start()

        return True

    def _record_loop(self):
        """录制线程主循环"""
        fps = self._config.get("fps", 30)
        frame_interval = 1.0 / fps

        while not self._stop_event.is_set():
            # 暂停等待
            if self._pause_event.is_set():
                time.sleep(0.05)
                continue

            loop_start = time.time()

            try:
                frame = self._capturer.capture_frame()
                if not self._encoder.write_frame(frame):
                    # 写入失败（可能磁盘满），停止录制
                    break
            except Exception:
                break

            # 控制帧率
            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)