"""
录制控制模块

协调屏幕捕获和视频编码，管理录制生命周期。
帧缓存模式：录制时帧以JPEG压缩写入临时文件，停止后后台解码写入VideoWriter。
内存占用始终为MB级（仅文件句柄+单帧缓冲），适合长时间录制。

v1.1 新增：录制模式（全屏/区域）、音频集成、FFmpeg 混合。
"""

import logging
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from enum import Enum

import ctypes
import cv2
import numpy as np

from config import ConfigManager
from recorder.screen_capturer import ScreenCapturer
from recorder.video_encoder import VideoEncoder
from recorder.audio_capturer import AudioCapturer, AudioSource
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


class RecordMode(Enum):
    """录制模式枚举"""
    FULLSCREEN = "fullscreen"
    REGION = "region"


class RecorderManager:
    """录制管理器"""

    def __init__(self, config: ConfigManager = None, on_saved=None):
        self._config = config or ConfigManager()
        self._state = RecorderState.IDLE
        self._mode = RecordMode.FULLSCREEN
        self._capturer: ScreenCapturer = None
        self._encoder: VideoEncoder = None
        self._record_thread: threading.Thread = None
        self._encode_thread: threading.Thread = None
        self._stop_thread: threading.Thread = None
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
        self._encode_size: tuple = (0, 0)

        # v1.1: 音频相关字段
        self._audio_capturer: AudioCapturer = None
        self._audio_source: str = AudioSource.NONE
        self._ffmpeg_path: str = ""
        self._audio_temp_paths: list = []

        # 编码完成回调
        self._on_saved = on_saved

    def start_fullscreen(self) -> bool:
        """开始全屏录制"""
        self._mode = RecordMode.FULLSCREEN
        return self._start(region=None)

    def start_region(self, region: tuple) -> bool:
        """开始区域录制

        Args:
            region: (left, top, width, height)
        """
        self._mode = RecordMode.REGION
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
        """停止录制，立即返回（不阻塞主线程）

        录制线程的等待、文件清理和编码启动全部在后台线程中完成。

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
            if self._state == RecorderState.STOPPING:
                return ""
            self._state = RecorderState.STOPPING

        self._cancelled = cancel

        # 设置停止事件，并唤醒可能阻塞在暂停等待的线程
        self._stop_event.set()
        self._resume_event.set()

        # 在后台线程中等待录制结束、清理并启动编码，不阻塞主线程
        self._stop_thread = threading.Thread(
            target=self._stop_and_encode, daemon=True
        )
        self._stop_thread.start()
        return ""

    def _stop_and_encode(self):
        """后台线程：等待录制结束、清理文件、启动编码"""
        # 等待录制线程结束
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

        # v1.1: 停止音频捕获
        self._audio_temp_paths = []
        if self._audio_capturer:
            try:
                paths = self._audio_capturer.stop()
                self._audio_temp_paths = paths if isinstance(paths, list) else [paths]
            except Exception as e:
                logger.error(f"停止音频捕获异常: {e}")
            self._audio_capturer = None

        # 取消录制时：删除临时文件和音频临时文件
        if self._cancelled:
            for p in self._audio_temp_paths:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            self._audio_temp_paths = []
            self._cleanup_temp_file()
            with self._lock:
                self._state = RecorderState.IDLE
            return

        # 启动后台编码线程
        with self._lock:
            self._state = RecorderState.SAVING

        self._encode_thread = threading.Thread(
            target=self._encode_loop, daemon=True
        )
        self._encode_thread.start()

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

    def wait_until_idle(self, timeout: float = 60.0):
        """等待录制器回到 IDLE 状态（用于退出时等待编码完成）

        Args:
            timeout: 最大等待时间（秒）
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._state == RecorderState.IDLE:
                return
            time.sleep(0.1)

    def get_mode(self) -> RecordMode:
        """获取当前录制模式"""
        return self._mode

    @staticmethod
    def _get_ffmpeg_path() -> str:
        """定位 FFmpeg 可执行文件

        搜索顺序:
        1. 应用目录下的 ffmpeg/ffmpeg.exe（打包内置）
        2. 项目目录下的 ffmpeg/ffmpeg.exe（开发环境）
        3. 系统 PATH 环境变量
        4. 返回空字符串（无音频混合能力）
        """
        # 1. 打包后：sys.executable 所在目录
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
            local_ffmpeg = os.path.join(app_dir, "ffmpeg", "ffmpeg.exe")
            if os.path.isfile(local_ffmpeg):
                return local_ffmpeg

        # 2. 开发环境：项目根目录（src/recorder/ → src/ → 项目根）
        dev_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_ffmpeg = os.path.join(dev_dir, "ffmpeg", "ffmpeg.exe")
        if os.path.isfile(local_ffmpeg):
            return local_ffmpeg

        # 3. 系统 PATH
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg

        # 4. 未找到
        return ""

    @staticmethod
    def _compress_frame(frame):
        """将BGR帧压缩为JPEG字节"""
        _, encoded = cv2.imencode('.jpg', frame, _JPEG_PARAMS)
        return encoded.tobytes()

    def _get_target_size(self):
        """根据画质配置获取目标分辨率 (width, height)，None 表示原始尺寸

        区域录制时保持选区宽高比，不强制拉伸到 16:9。
        """
        quality = self._config.get("quality", "native")
        target = ConfigManager.QUALITY_SIZES.get(quality)
        if target is None:
            return None

        # 区域录制时保持选区宽高比
        if self._mode == RecordMode.REGION and self._frame_size:
            fw, fh = self._frame_size
            tw, th = target
            # 按宽高比缩放：选区宽高比 vs 目标宽高比
            src_ratio = fw / fh
            dst_ratio = tw / th
            if src_ratio > dst_ratio:
                # 选区更宽，以目标宽度为准，高度按比例缩放
                new_w = tw
                new_h = int(tw / src_ratio)
            else:
                # 选区更高，以目标高度为准，宽度按比例缩放
                new_h = th
                new_w = int(th * src_ratio)
            # 确保偶数（编码要求）
            return (new_w & ~1, new_h & ~1)

        return target

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

            # 创建捕获器（延迟启动，在录制线程中调用 start()）
            self._capturer = ScreenCapturer(region=region)
            self._frame_size = self._capturer.get_monitor_size()

            # 计算编码用的目标尺寸（画质缩放）
            target = self._get_target_size()
            if target:
                self._encode_size = target
            else:
                self._encode_size = self._frame_size

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

            # v1.1: 音频初始化
            self._audio_temp_paths = []
            self._audio_capturer = None
            audio_source_str = self._config.get("audio_source", "none")
            self._audio_source = audio_source_str  # 保存配置值
            self._ffmpeg_path = self._get_ffmpeg_path()

            if audio_source_str != AudioSource.NONE:
                try:
                    output_dir = os.path.dirname(self._output_path)
                    output_stem = os.path.splitext(os.path.basename(self._output_path))[0]
                    self._audio_capturer = AudioCapturer(
                        source=audio_source_str,
                        output_dir=output_dir,
                    )
                    if not self._audio_capturer.start(output_stem=output_stem):
                        logger.warning("音频捕获初始化失败，继续无声录制")
                        self._audio_capturer = None
                        self._audio_source = AudioSource.NONE
                except Exception as e:
                    logger.warning(f"音频捕获初始化异常，继续无声录制: {e}")
                    self._audio_capturer = None
                    self._audio_source = AudioSource.NONE

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
        # 在录制线程中启动 dxcam，避免在主线程中初始化导致阻塞
        try:
            self._capturer.start()
        except Exception as e:
            logger.error(f"屏幕捕获器启动失败: {e}")
            self._stop_event.set()

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

            # 等待到下一帧时刻（使用 time.sleep 释放 GIL，避免忙等待冻结主线程）
            next_time = rec_start + frames_written * frame_interval
            wait = next_time - time.time()
            if wait > 0.002:
                time.sleep(max(wait - 0.001, 0.001))

        self._total_frames = frames_written

        # 确保数据刷盘
        if fh and not fh.closed:
            fh.flush()

        logger.info(
            f"录制结束，写入 {self._total_frames} 帧到临时文件 "
            f"({os.path.getsize(self._temp_file) // (1024*1024)}MB)"
        )

    def _encode_loop(self):
        """后台编码线程：从临时文件读取JPEG帧并写入VideoWriter，然后混入音频"""
        try:
            total = self._total_frames
            logger.info(f"开始编码保存，共 {total} 帧...")

            encoder = VideoEncoder(self._output_path, self._fps, self._encode_size)

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

                    # 解压并缩放帧
                    frame = cv2.imdecode(
                        np.frombuffer(jpeg_data, dtype=np.uint8),
                        cv2.IMREAD_COLOR
                    )
                    if frame is None:
                        logger.error(f"解码失败，第 {i} 帧")
                        raise RuntimeError("JPEG 解码失败")

                    # 按画质缩放
                    if self._encode_size != self._frame_size:
                        frame = cv2.resize(
                            frame, self._encode_size,
                            interpolation=cv2.INTER_LINEAR
                        )

                    if not encoder.write_frame(frame):
                        logger.error(f"解码/编码失败，第 {i} 帧")
                        raise RuntimeError("解码/编码写入失败")

            encoder.close()

            logger.info(f"视频编码完成: {self._output_path} ({total} 帧)")

            # v1.1: 音频混合步骤
            result_path = self._mix_audio_if_available()

            if not result_path:
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

            # v1.1: 清理音频临时文件
            for p in self._audio_temp_paths:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            self._audio_temp_paths = []

            with self._lock:
                self._state = RecorderState.IDLE

            # 通知主线程编码完成
            if self._on_saved:
                try:
                    logger.info(f"编码完成回调，即将通知主线程: {result_path}")
                    self._on_saved(result_path)
                except Exception as e:
                    logger.error(f"编码完成回调异常: {e}")

    def _mix_audio_if_available(self) -> str:
        """尝试将音频混入视频文件

        Returns:
            混合后的文件路径，无音频时返回空字符串
        """
        if not self._audio_temp_paths:
            return ""

        if not self._ffmpeg_path:
            logger.warning("FFmpeg 不可用，无法混入音频，保留纯视频")
            return ""

        temp_video = self._output_path + ".video_only.mp4"
        try:
            os.rename(self._output_path, temp_video)
        except OSError as e:
            logger.error(f"重命名视频文件失败: {e}")
            return ""

        try:
            self._mix_audio_video(temp_video, self._audio_temp_paths, self._output_path)
            # 成功：删除临时纯视频文件
            try:
                os.remove(temp_video)
            except OSError:
                pass
            logger.info(f"音频混合完成: {self._output_path}")
            return self._output_path
        except Exception as e:
            logger.error(f"音频混合失败，恢复纯视频: {e}")
            # 降级：恢复纯视频文件
            if os.path.exists(temp_video):
                try:
                    os.replace(temp_video, self._output_path)
                except OSError:
                    pass
            return ""

    def _mix_audio_video(self, video_path: str, audio_paths: list, output_path: str):
        """使用 FFmpeg 混合音视频

        Args:
            video_path: 纯视频文件路径
            audio_paths: 音频 WAV 文件路径列表（1或2个）
            output_path: 最终输出文件路径
        """
        cmd = [self._ffmpeg_path, "-y", "-i", video_path]

        # 每个音频源作为独立输入
        for audio_path in audio_paths:
            cmd.extend(["-i", audio_path])

        if len(audio_paths) == 1:
            # 单音频源：直接混入
            cmd.extend([
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
            ])
        elif len(audio_paths) == 2:
            # BOTH 模式：使用 amerge 滤镜合并系统声音和麦克风
            cmd.extend([
                "-filter_complex", "[1:a][2:a]amerge=inputs=2[a]",
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
            ])

        cmd.append(output_path)

        logger.info(f"FFmpeg 混合命令: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, check=True, timeout=120,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        logger.info(f"FFmpeg 混合完成, 返回码: {result.returncode}")

    def _cleanup_temp_file(self):
        """清理临时文件"""
        if self._temp_file and os.path.exists(self._temp_file):
            try:
                os.remove(self._temp_file)
                logger.info(f"已删除临时文件: {self._temp_file}")
            except OSError:
                pass
        self._temp_file = ""