"""
录制控制模块

协调屏幕捕获和视频编码，管理录制生命周期。
方案3：录制时帧存入内存deque，停止后后台编码写入VideoWriter。
内存超2GB时自动回退实时编码模式。
"""

import logging
import os
import threading
import time
from collections import deque
from enum import Enum

import ctypes

from config import ConfigManager
from recorder.screen_capturer import ScreenCapturer
from recorder.video_encoder import VideoEncoder
from utils.disk_checker import DiskChecker
from utils.file_namer import FileNamer

logger = logging.getLogger("QuickRec")

# Windows 高精度定时器：将系统计时器分辨率提升到 1ms
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

# 内存缓存上限：2GB，超过后回退实时编码
MAX_MEMORY = 2 * 1024 * 1024 * 1024


class RecorderState(Enum):
    """录制状态枚举"""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"
    SAVING = "saving"


class RecorderManager:
    """录制管理器"""

    def __init__(self, config: ConfigManager = None, on_saved=None):
        self._config = config or ConfigManager()
        self._state = RecorderState.IDLE
        self._capturer: ScreenCapturer = None
        self._encoder: VideoEncoder = None
        self._record_thread: threading.Thread = None
        self._encode_thread: threading.Thread = None
        self._stop_event = threading.Event()
        # _resume_event: set() = 可以录制, clear() = 暂停中（线程等待）
        self._resume_event = threading.Event()
        self._start_time: float = 0
        self._pause_duration: float = 0
        self._pause_start: float = 0
        self._output_path: str = ""
        self._lock = threading.Lock()
        self._cancelled = False

        # 方案3：帧缓存
        self._frames: deque = deque()
        self._memory_used: int = 0
        self._realtime_mode: bool = False
        self._fps: int = 30
        self._frame_size: tuple = (0, 0)

        # 编码完成回调
        self._on_saved = on_saved

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

        Returns:
            实时编码模式：返回文件路径（或空字符串取消时）
            缓存编码模式：返回空字符串（编码异步进行），通过 on_saved 回调通知结果
        """
        with self._lock:
            if self._state == RecorderState.IDLE:
                return ""
            if self._state == RecorderState.SAVING:
                return ""
            self._state = RecorderState.STOPPING

        self._cancelled = cancel

        # 设置停止事件，并唤醒可能阻塞在暂停等待的线程
        self._stop_event.set()
        self._resume_event.set()

        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=5.0)

        # 关闭捕获器
        if self._capturer:
            self._capturer.close()
            self._capturer = None

        # 取消录制时：清空缓存，不编码
        if cancel:
            self._frames.clear()
            self._memory_used = 0
            if self._encoder:
                self._encoder.close()
                self._encoder = None
            if self._output_path and os.path.exists(self._output_path):
                try:
                    os.remove(self._output_path)
                    logger.info(f"取消录制，已删除文件: {self._output_path}")
                except OSError:
                    pass
            with self._lock:
                self._state = RecorderState.IDLE
            return ""

        # 实时编码模式：编码器已经在录制线程中，直接关闭即可
        if self._realtime_mode:
            if self._encoder:
                self._encoder.close()
                self._encoder = None
            with self._lock:
                self._state = RecorderState.IDLE
            logger.info(f"录制已保存: {self._output_path}")
            return self._output_path

        # 缓存编码模式：启动后台编码线程
        with self._lock:
            self._state = RecorderState.SAVING

        self._encode_thread = threading.Thread(
            target=self._encode_loop, daemon=True
        )
        self._encode_thread.start()
        return ""  # 编码异步进行，通过 on_saved 回调通知结果

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

    def is_saving(self) -> bool:
        """是否正在后台编码保存中"""
        return self._state == RecorderState.SAVING

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

            # 创建捕获器（不创建编码器，帧缓存到内存）
            self._capturer = ScreenCapturer(region=region)
            self._frame_size = self._capturer.get_monitor_size()

            fps = self._config.get("fps", 30)
            self._output_path = FileNamer.generate(save_path)

            # 方案3初始化：帧缓存模式
            self._frames = deque()
            self._memory_used = 0
            self._realtime_mode = False
            self._encoder = None
            self._fps = fps
            self._frame_size = self._frame_size

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

        缓存模式下仅将帧存入deque，无编码开销。
        内存超过阈值时自动切换实时编码模式。
        """
        fps = self._fps
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

            # 实时编码模式：直接写入 VideoWriter
            if self._realtime_mode:
                while frames_written < target_frame:
                    if not self._encoder.write_frame(frame):
                        return
                    frames_written += 1
                if not self._encoder.write_frame(frame):
                    break
                frames_written += 1
            else:
                # 缓存模式：帧存入内存
                self._frames.append(frame)
                self._memory_used += frame.nbytes
                frames_written += 1

                # 内存超限：切换到实时编码模式
                if self._memory_used > MAX_MEMORY:
                    logger.warning(f"帧缓存超过 {MAX_MEMORY // (1024*1024)}MB，切换实时编码模式")
                    self._realtime_mode = True
                    self._encoder = VideoEncoder(
                        self._output_path, self._fps, self._frame_size
                    )
                    # 将已缓存的帧全部写入编码器
                    while self._frames:
                        cached_frame = self._frames.popleft()
                        self._encoder.write_frame(cached_frame)
                    self._memory_used = 0

            # 等待到下一帧时刻
            next_time = rec_start + frames_written * frame_interval
            wait = next_time - time.time()
            if wait > 0.002:
                time.sleep(wait - 0.001)
            while time.time() < next_time:
                pass

    def _encode_loop(self):
        """后台编码线程：将缓存的帧写入 VideoWriter"""
        try:
            logger.info(f"开始编码保存，共 {len(self._frames)} 帧...")
            encoder = VideoEncoder(self._output_path, self._fps, self._frame_size)

            total = len(self._frames)
            for i, frame in enumerate(self._frames):
                if not encoder.write_frame(frame):
                    logger.error(f"编码写入失败，第 {i} 帧")
                    raise RuntimeError("编码写入失败")

            encoder.close()
            self._frames.clear()
            self._memory_used = 0

            logger.info(f"编码完成: {self._output_path} ({total} 帧)")
            result_path = self._output_path

        except Exception as e:
            logger.error(f"编码失败: {e}")
            result_path = ""
            # 清理：删除可能的不完整文件
            if self._output_path and os.path.exists(self._output_path):
                try:
                    os.remove(self._output_path)
                except OSError:
                    pass

        finally:
            with self._lock:
                self._state = RecorderState.IDLE

            # 通知主线程编码完成
            if self._on_saved:
                try:
                    self._on_saved(result_path)
                except Exception:
                    pass