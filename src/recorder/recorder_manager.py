"""
录制控制模块

协调屏幕捕获和视频编码，管理录制生命周期。
帧缓存模式：录制时帧以JPEG压缩写入临时文件，停止后后台解码写入VideoWriter。
内存占用始终为MB级（仅文件句柄+单帧缓冲），适合长时间录制。
"""

import logging
import os
import struct
import threading
import time
from enum import Enum

import ctypes
import cv2
import numpy as np

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

# JPEG 压缩参数
_JPEG_QUALITY = 95
_JPEG_PARAMS = [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY]


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

        # 临时文件缓存（JPEG帧写入磁盘，非内存）
        self._temp_file: str = ""
        self._temp_file_handle = None
        self._total_frames: int = 0
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
            始终返回空字符串（编码异步进行），通过 on_saved 回调通知结果
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

        # 关闭临时文件
        if self._temp_file_handle:
            self._temp_file_handle.close()
            self._temp_file_handle = None

        # 关闭捕获器
        if self._capturer:
            self._capturer.close()
            self._capturer = None

        # 取消录制时：删除临时文件，不编码
        if cancel:
            self._cleanup_temp_file()
            with self._lock:
                self._state = RecorderState.IDLE
            return ""

        # 启动后台编码线程
        with self._lock:
            self._state = RecorderState.SAVING

        self._encode_thread = threading.Thread(
            target=self._encode_loop, daemon=True
        )
        self._encode_thread.start()
        return ""

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

    @staticmethod
    def _compress_frame(frame):
        """将BGR帧压缩为JPEG字节"""
        _, encoded = cv2.imencode('.jpg', frame, _JPEG_PARAMS)
        return encoded.tobytes()

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

            # 创建捕获器
            self._capturer = ScreenCapturer(region=region)
            self._frame_size = self._capturer.get_monitor_size()

            fps = self._config.get("fps", 30)
            self._output_path = FileNamer.generate(save_path)

            # 创建临时文件（与输出文件同目录）
            self._temp_file = self._output_path + ".tmp"
            try:
                self._temp_file_handle = open(self._temp_file, "wb")
            except OSError as e:
                logger.error(f"创建临时文件失败: {e}")
                self._capturer.close()
                self._capturer = None
                return False

            # 初始化帧计数
            self._total_frames = 0
            self._fps = fps

            self._stop_event.clear()
            self._resume_event.set()
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

        帧以JPEG压缩后写入临时文件（TLV格式：4字节长度+帧数据）。
        录制循环仅包含截图+压缩+写盘，无编码开销，足以稳定60fps。
        暂停期间保留帧计数，恢复时调整时间基准使帧号连续。
        """
        fps = self._fps
        frame_interval = 1.0 / fps
        rec_start = time.time()
        frames_written = 0
        was_paused = False
        fh = self._temp_file_handle

        while not self._stop_event.is_set():
            # 暂停等待
            if not self._resume_event.wait(timeout=0.1):
                if self._stop_event.is_set():
                    break
                was_paused = True
                continue

            if self._stop_event.is_set():
                break

            # 从暂停恢复：调整时间基准使帧号连续
            if was_paused:
                rec_start = time.time() - frames_written * frame_interval
                was_paused = False

            # 计算应该写到第几帧
            target_frame = int((time.time() - rec_start) / frame_interval)

            try:
                frame = self._capturer.capture_frame()
                if frame is None:
                    continue
            except Exception:
                break

            # JPEG压缩
            compressed = self._compress_frame(frame)
            size = len(compressed)

            # 补齐跳过的帧：用当前压缩帧填充时间间隙
            while frames_written < target_frame:
                fh.write(struct.pack("<I", size))
                fh.write(compressed)
                frames_written += 1

            # 写入当前帧
            fh.write(struct.pack("<I", size))
            fh.write(compressed)
            frames_written += 1

            # 等待到下一帧时刻
            next_time = rec_start + frames_written * frame_interval
            wait = next_time - time.time()
            if wait > 0.002:
                time.sleep(wait - 0.001)
            while time.time() < next_time:
                pass

        self._total_frames = frames_written

        # 确保数据刷盘
        if fh and not fh.closed:
            fh.flush()

        logger.info(
            f"录制结束，写入 {self._total_frames} 帧到临时文件 "
            f"({os.path.getsize(self._temp_file) // (1024*1024)}MB)"
        )

    def _encode_loop(self):
        """后台编码线程：从临时文件读取JPEG帧并写入VideoWriter"""
        try:
            total = self._total_frames
            logger.info(f"开始编码保存，共 {total} 帧...")

            encoder = VideoEncoder(self._output_path, self._fps, self._frame_size)

            with open(self._temp_file, "rb") as fh:
                for i in range(total):
                    # 读取帧长度（4字节小端无符号整数）
                    size_data = fh.read(4)
                    if len(size_data) < 4:
                        logger.error(f"读取帧长度失败，第 {i} 帧")
                        raise RuntimeError(f"临时文件读取失败，第 {i} 帧")

                    size = struct.unpack("<I", size_data)[0]
                    # 读取JPEG帧数据
                    jpeg_data = fh.read(size)
                    if len(jpeg_data) < size:
                        logger.error(f"读取帧数据失败，第 {i} 帧")
                        raise RuntimeError(f"临时文件读取失败，第 {i} 帧")

                    # 解压并写入编码器
                    frame = cv2.imdecode(
                        np.frombuffer(jpeg_data, dtype=np.uint8),
                        cv2.IMREAD_COLOR
                    )
                    if frame is None or not encoder.write_frame(frame):
                        logger.error(f"解码/编码失败，第 {i} 帧")
                        raise RuntimeError("解码/编码写入失败")

            encoder.close()

            logger.info(f"编码完成: {self._output_path} ({total} 帧)")
            result_path = self._output_path

        except Exception as e:
            logger.error(f"编码失败: {e}")
            result_path = ""
            if self._output_path and os.path.exists(self._output_path):
                try:
                    os.remove(self._output_path)
                except OSError:
                    pass

        finally:
            # 清理临时文件
            self._cleanup_temp_file()

            with self._lock:
                self._state = RecorderState.IDLE

            # 通知主线程编码完成
            if self._on_saved:
                try:
                    self._on_saved(result_path)
                except Exception:
                    pass

    def _cleanup_temp_file(self):
        """清理临时文件"""
        if self._temp_file and os.path.exists(self._temp_file):
            try:
                os.remove(self._temp_file)
                logger.info(f"已删除临时文件: {self._temp_file}")
            except OSError:
                pass
        self._temp_file = ""