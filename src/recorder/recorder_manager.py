"""
录制控制模块（v1.3 重构）

v1.3 变更：
- 去除 JPEG 临时文件方案，改为 FFmpeg pipe 实时编码
- 接入 TempCleaner 会话目录管理
- 恢复 RecordMode.WINDOW 窗口录制模式
"""

import ctypes
import ctypes.wintypes
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from enum import Enum

import cv2

from PyQt5.QtCore import QObject, pyqtSignal

from config import ConfigManager
from recorder.screen_capturer import ScreenCapturer
from recorder.video_encoder import VideoEncoder
from recorder.audio_capturer import AudioCapturer, AudioSource
from utils.disk_checker import DiskChecker
from utils.file_namer import FileNamer
from utils.temp_cleaner import TempCleaner

logger = logging.getLogger("QuickRec")

try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass


class RecorderState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"
    SAVING = "saving"


class RecordMode(Enum):
    FULLSCREEN = "fullscreen"
    REGION = "region"
    WINDOW = "window"


class _WindowLostBridge(QObject):
    window_lost = pyqtSignal(str)  # "closed" / "minimized"


class RecorderManager:
    """录制管理器（v1.3：FFmpeg pipe + TempCleaner + 窗口录制）"""

    def __init__(self, config: ConfigManager = None, on_saved=None):
        self._config = config or ConfigManager()
        self._state = RecorderState.IDLE
        self._mode = RecordMode.FULLSCREEN
        self._capturer: ScreenCapturer = None
        self._encoder: VideoEncoder = None
        self._record_thread: threading.Thread = None
        self._finalize_thread: threading.Thread = None
        self._stop_thread: threading.Thread = None
        self._stop_event = threading.Event()
        self._resume_event = threading.Event()
        self._start_time: float = 0
        self._pause_duration: float = 0
        self._pause_start: float = 0
        self._output_path: str = ""
        self._lock = threading.Lock()
        self._cancelled = False
        self._fps: int = 30
        self._frame_size: tuple = (0, 0)
        self._encode_size: tuple = (0, 0)
        self._ffmpeg_path: str = ""

        # TempCleaner 会话目录
        self._session_dir: str = ""
        self._video_temp_path: str = ""

        # 音频
        self._audio_capturer: AudioCapturer = None
        self._audio_source: str = AudioSource.NONE
        self._audio_temp_paths: list = []

        # 窗口录制
        self._window_hwnd: int = None
        self._window_title: str = ""
        self._window_lost_bridge = _WindowLostBridge()

        self._on_saved = on_saved

    # --- 公共接口 ---

    def start_fullscreen(self) -> bool:
        self._mode = RecordMode.FULLSCREEN
        return self._start(region=None)

    def start_region(self, region: tuple) -> bool:
        self._mode = RecordMode.REGION
        return self._start(region=region)

    def start_window(self, hwnd: int) -> bool:
        if not ctypes.windll.user32.IsWindow(hwnd):
            logger.error(f"无效窗口句柄: {hwnd}")
            return False
        self._window_title = self._get_window_title(hwnd)
        self._window_hwnd = hwnd
        self._mode = RecordMode.WINDOW
        rect = self._get_window_rect(hwnd)
        if rect is None:
            logger.error(f"无法获取窗口位置: hwnd={hwnd}")
            return False
        region = (rect.left(), rect.top(), rect.width(), rect.height())
        return self._start(region=region)

    def pause(self) -> bool:
        with self._lock:
            if self._state != RecorderState.RECORDING:
                return False
            self._state = RecorderState.PAUSED
            self._pause_start = time.time()
        self._resume_event.clear()
        return True

    def resume(self) -> bool:
        with self._lock:
            if self._state != RecorderState.PAUSED:
                return False
            self._state = RecorderState.RECORDING
            self._pause_duration += time.time() - self._pause_start
        self._resume_event.set()
        return True

    def stop(self, cancel: bool = False) -> str:
        with self._lock:
            if self._state in (RecorderState.IDLE, RecorderState.SAVING, RecorderState.STOPPING):
                return ""
            self._state = RecorderState.STOPPING
        self._cancelled = cancel
        self._stop_event.set()
        self._resume_event.set()
        self._stop_thread = threading.Thread(target=self._stop_and_encode, daemon=True)
        self._stop_thread.start()
        return ""

    def get_state(self) -> RecorderState:
        return self._state

    def get_elapsed(self) -> str:
        if self._state == RecorderState.IDLE:
            return "00:00"
        elapsed = time.time() - self._start_time - self._pause_duration
        if self._state == RecorderState.PAUSED:
            elapsed -= (time.time() - self._pause_start)
        minutes = int(elapsed) // 60
        seconds = int(elapsed) % 60
        return f"{minutes:02d}:{seconds:02d}"

    def is_saving(self) -> bool:
        return self._state == RecorderState.SAVING

    def wait_until_idle(self, timeout: float = 60.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._state == RecorderState.IDLE:
                return
            time.sleep(0.1)

    def get_mode(self) -> RecordMode:
        return self._mode

    # --- 内部实现 ---

    def _start(self, region=None) -> bool:
        with self._lock:
            if self._state != RecorderState.IDLE:
                return False

            save_path = self._config.get("save_path")
            quality = self._config.get("quality", "high")
            if DiskChecker.is_low_space(save_path, quality):
                return False

            self._capturer = ScreenCapturer(region=region)
            self._frame_size = self._capturer.get_monitor_size()
            self._encode_size = self._get_target_size() or self._frame_size
            self._fps = self._config.get("fps", 30)
            self._output_path = FileNamer.generate(save_path)
            self._ffmpeg_path = self._get_ffmpeg_path()

            # 创建会话目录
            self._session_dir = TempCleaner.create_session_dir()
            TempCleaner.register_atexit(self._session_dir)
            self._video_temp_path = os.path.join(self._session_dir, "video.mp4")

            # 音频初始化（输出到会话目录）
            self._audio_temp_paths = []
            self._audio_capturer = None
            audio_source_str = self._config.get("audio_source", "none")
            self._audio_source = audio_source_str
            if audio_source_str != AudioSource.NONE and self._ffmpeg_path:
                try:
                    self._audio_capturer = AudioCapturer(
                        source=audio_source_str,
                        output_dir=self._session_dir,
                    )
                    if not self._audio_capturer.start(output_stem="audio"):
                        logger.warning("音频捕获初始化失败，继续无声录制")
                        self._audio_capturer = None
                except Exception as e:
                    logger.warning(f"音频捕获初始化异常: {e}")
                    self._audio_capturer = None

            self._stop_event.clear()
            self._resume_event.set()
            self._pause_duration = 0
            self._cancelled = False
            self._start_time = time.time()
            self._state = RecorderState.RECORDING

            self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
            self._record_thread.start()
        return True

    def _record_loop(self):
        """录制线程：dxcam → cv2.resize（如需）→ FFmpeg pipe"""
        try:
            self._capturer.start()
        except Exception as e:
            logger.error(f"屏幕捕获器启动失败: {e}")
            self._stop_event.set()
            return

        self._encoder = VideoEncoder(
            output_path=self._video_temp_path,
            fps=self._fps,
            frame_size=self._encode_size,
            ffmpeg_path=self._ffmpeg_path,
        )

        fps = self._fps
        frame_interval = 1.0 / fps
        rec_start = time.time()
        frames_written = 0
        was_paused = False
        last_window_update = 0

        while not self._stop_event.is_set():
            if not self._resume_event.wait(timeout=0.1):
                if self._stop_event.is_set():
                    break
                was_paused = True
                continue

            if self._stop_event.is_set():
                break

            if was_paused:
                rec_start = time.time() - frames_written * frame_interval
                was_paused = False

            # 窗口模式：200ms 更新捕获区域
            if self._mode == RecordMode.WINDOW and self._window_hwnd:
                now = time.time()
                if now - last_window_update >= 0.2:
                    rect = self._get_window_rect(self._window_hwnd)
                    if rect is None:
                        user32 = ctypes.windll.user32
                        reason = "closed" if not user32.IsWindow(self._window_hwnd) else "minimized"
                        logger.info(f"录制窗口丢失: {reason}")
                        self._window_lost_bridge.window_lost.emit(reason)
                        break
                    self._capturer.update_region(
                        (rect.left(), rect.top(), rect.width(), rect.height())
                    )
                    last_window_update = now

            try:
                frame = self._capturer.capture_frame()
            except Exception:
                break
            if frame is None:
                if not self._capturer._started:
                    break
                continue

            # 画质缩放（写 pipe 前）
            if self._encode_size != self._frame_size:
                frame = cv2.resize(frame, self._encode_size, interpolation=cv2.INTER_LINEAR)

            target_frame = int((time.time() - rec_start) / frame_interval)
            while frames_written < target_frame:
                if not self._encoder.write_frame(frame):
                    break
                frames_written += 1

            if not self._encoder.write_frame(frame):
                break
            frames_written += 1

            next_time = rec_start + frames_written * frame_interval
            wait = next_time - time.time()
            if wait > 0.002:
                time.sleep(max(wait - 0.001, 0.001))

        # 关闭编码器（FFmpeg flush）
        if self._encoder:
            self._encoder.close()
            self._encoder = None

        if self._capturer:
            try:
                self._capturer.close()
            except Exception:
                pass
            self._capturer = None

        logger.info(f"录制线程结束，frames={frames_written}")

    def _stop_and_encode(self):
        # 等待录制线程完成 encoder.close()（FFmpeg flush 可能需要数十秒）
        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join()

        # 停止音频
        self._audio_temp_paths = []
        if self._audio_capturer:
            try:
                paths = self._audio_capturer.stop()
                self._audio_temp_paths = [p for p in (paths if isinstance(paths, list) else [paths]) if p and os.path.exists(p)]
            except Exception as e:
                logger.error(f"停止音频捕获异常: {e}")
            self._audio_capturer = None

        if self._cancelled:
            TempCleaner.cleanup_session(self._session_dir)
            with self._lock:
                self._state = RecorderState.IDLE
            return

        with self._lock:
            self._state = RecorderState.SAVING

        self._finalize_thread = threading.Thread(target=self._finalize, daemon=True)
        self._finalize_thread.start()

    def _finalize(self):
        """最终化：音频混合 → 移动到输出路径 → 清理"""
        result_path = ""
        try:
            video_path = self._video_temp_path

            if self._audio_temp_paths and self._ffmpeg_path:
                mixed = self._mix_audio(video_path, self._audio_temp_paths)
                if mixed:
                    video_path = mixed

            shutil.move(video_path, self._output_path)
            result_path = self._output_path
        except Exception as e:
            logger.error(f"最终化失败: {e}")
        finally:
            TempCleaner.cleanup_session(self._session_dir)
            with self._lock:
                self._state = RecorderState.IDLE
            if self._on_saved:
                try:
                    self._on_saved(result_path)
                except Exception as e:
                    logger.error(f"on_saved 回调异常: {e}")

    def _mix_audio(self, video_path: str, audio_paths: list) -> str:
        """FFmpeg 混合音视频，返回混合后路径（session_dir/mixed.mp4）"""
        mixed = os.path.join(self._session_dir, "mixed.mp4")
        cmd = [self._ffmpeg_path, "-y", "-i", video_path]
        for ap in audio_paths:
            cmd.extend(["-i", ap])
        if len(audio_paths) == 1:
            cmd.extend(["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", mixed])
        else:
            cmd.extend([
                "-filter_complex", "[1:a][2:a]amerge=inputs=2[a]",
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", mixed,
            ])
        try:
            subprocess.run(cmd, check=True, timeout=120,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            return mixed
        except Exception as e:
            logger.error(f"音频混合失败: {e}")
            return ""

    def _get_target_size(self):
        quality = self._config.get("quality", "native")
        target = ConfigManager.QUALITY_SIZES.get(quality)
        if target is None:
            return None
        if self._mode == RecordMode.REGION and self._frame_size:
            fw, fh = self._frame_size
            tw, th = target
            src_ratio = fw / fh
            dst_ratio = tw / th
            if src_ratio > dst_ratio:
                new_w, new_h = tw, int(tw / src_ratio)
            else:
                new_w, new_h = int(th * src_ratio), th
            return (new_w & ~1, new_h & ~1)
        return target

    @staticmethod
    def _get_ffmpeg_path() -> str:
        if getattr(sys, 'frozen', False):
            candidates = []
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                candidates.append(os.path.join(meipass, "ffmpeg", "ffmpeg.exe"))
            candidates.append(os.path.join(os.path.dirname(sys.executable), "ffmpeg", "ffmpeg.exe"))
            for p in candidates:
                if os.path.isfile(p):
                    return p
        dev_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local = os.path.join(dev_dir, "ffmpeg", "ffmpeg.exe")
        if os.path.isfile(local):
            return local
        import shutil as _sh
        return _sh.which("ffmpeg") or ""

    @staticmethod
    def _get_window_rect(hwnd: int):
        """获取窗口客户区屏幕坐标（GetClientRect + ClientToScreen）"""
        user32 = ctypes.windll.user32
        if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return None
        client_rect = ctypes.wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(client_rect))
        w, h = client_rect.right, client_rect.bottom
        if w < 10 or h < 10:
            return None
        pt = ctypes.wintypes.POINT()
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        from PyQt5.QtCore import QRect
        return QRect(pt.x, pt.y, w, h)

    @staticmethod
    def _get_window_title(hwnd: int) -> str:
        n = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return ""
        buf = ctypes.create_unicode_buffer(n + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value
