"""
录制控制模块（v1.3 重构）

v1.3 变更：
- 去除 JPEG 临时文件方案，改为 FFmpeg pipe 实时编码
- 接入 TempCleaner 会话目录管理
- 恢复 RecordMode.WINDOW 窗口录制模式
"""

import ctypes
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import wave
from collections.abc import Callable
from enum import Enum

from PyQt5.QtCore import QObject, pyqtSignal

from config import ConfigManager
from recorder.audio_capturer import AudioCapturer, AudioSource
from recorder.audio_preflight import AudioPreflightResult, plan_audio_source
from recorder.cursor_overlay import draw_cursor
from recorder.events import RecordingEvent
from recorder.frame_resize import resize_bgr_frame
from recorder.screen_capturer import ScreenCapturer
from recorder.state_machine import RecordingState, RecordingStateMachine
from recorder.timer_resolution import TimerResolution
from recorder.video_encoder import VideoEncoder
from recorder.window_diagnostics import WindowFailureReason, WindowRecordingDiagnostic
from utils.disk_checker import DiskChecker
from utils.file_namer import FileNamer
from utils.temp_cleaner import TempCleaner
from utils.window_geometry import get_window_client_rect, normalize_capture_region

logger = logging.getLogger("QuickRec")

RecorderState = RecordingState
_WINDOW_CAPTURE_UPDATE_INTERVAL = 0.0
_WINDOW_MOVE_STABLE_DELAY = 0.45

class RecordMode(Enum):
    FULLSCREEN = "fullscreen"
    REGION = "region"
    WINDOW = "window"


class _WindowLostBridge(QObject):
    window_lost = pyqtSignal(str)  # "closed" / "minimized"


class RecorderManager:
    """录制管理器（v1.3：FFmpeg pipe + TempCleaner + 窗口录制）"""

    def __init__(self, config: ConfigManager = None, on_saved=None, on_event=None):
        self._config = config or ConfigManager()
        self._state_machine = RecordingStateMachine()
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
        self._audio_preflight = AudioPreflightResult(
            requested_source=AudioSource.NONE,
            final_source=AudioSource.NONE,
            system_available=False,
            microphone_available=False,
        )
        self._audio_temp_paths: list = []

        # 窗口录制
        self._window_hwnd: int = None
        self._window_title: str = ""
        self._window_region: tuple[int, int, int, int] | None = None
        self._pending_window_region: tuple[int, int, int, int] | None = None
        self._last_window_diagnostic = WindowRecordingDiagnostic()
        self._last_window_move_time = 0.0
        self._last_window_frame = None
        self._window_lost_bridge = _WindowLostBridge()
        self._window_lost_emitted = False  # 防止窗口丢失信号重复 emit

        self._on_saved = on_saved
        self._on_event = on_event
        self._timer_resolution = TimerResolution()
        self._recording_failed_reason = ""
        self._disk_check_interval = 1.0
        self._last_disk_check = 0.0

    # --- 公共接口 ---

    def set_event_handler(self, callback: Callable[[RecordingEvent], None] | None) -> None:
        self._on_event = callback

    def connect_window_lost(self, callback: Callable[[str], None]) -> None:
        self._window_lost_bridge.window_lost.connect(callback)

    def _check_recording_disk_space(self, now: float) -> bool:
        if now - self._last_disk_check < self._disk_check_interval:
            return True
        self._last_disk_check = now
        save_path = self._config.get("save_path")
        quality = self._config.get("quality", "high")
        return not DiskChecker.is_low_space(save_path, quality)

    def _finish_failed_recording(self, reason: str) -> None:
        if self._audio_capturer:
            try:
                self._audio_capturer.stop()
            except Exception as e:
                logger.error(f"stop audio after recording failure failed: {e}")
            self._audio_capturer = None
        TempCleaner.cleanup_session(self._session_dir)
        with self._lock:
            self._state_machine.reset()
        if self._on_saved:
            try:
                self._on_saved("")
            except Exception as e:
                logger.error(f"on_saved callback failed: {e}")
        if self._on_event:
            try:
                self._on_event(RecordingEvent.failed(reason))
            except Exception as e:
                logger.error(f"on_event callback failed: {e}")
        self._timer_resolution.end()

    def start_fullscreen(self) -> bool:
        self._mode = RecordMode.FULLSCREEN
        return self._start(region=None)

    def start_region(self, region: tuple) -> bool:
        self._mode = RecordMode.REGION
        return self._start(region=region)

    def start_window(self, hwnd: int) -> bool:
        user32 = ctypes.windll.user32
        if not user32.IsWindow(hwnd):
            diagnostic = self._record_window_diagnostic(
                reason=WindowFailureReason.UNSUPPORTED_WINDOW,
                hwnd=hwnd,
                title="",
                stage="is_window",
            )
            logger.error(
                "window recording rejected: "
                f"reason={diagnostic.reason.value}, hwnd={diagnostic.hwnd}, "
                f"title={diagnostic.title!r}, mode={diagnostic.mode}, stage={diagnostic.stage}"
            )
            return False
        self._window_title = self._get_window_title(hwnd)
        self._window_hwnd = hwnd
        self._mode = RecordMode.WINDOW
        self._window_lost_emitted = False
        rect = self._get_window_rect(hwnd)
        if rect is None:
            diagnostic = self._record_window_diagnostic(
                reason=WindowFailureReason.RECT_UNAVAILABLE,
                hwnd=hwnd,
                title=self._window_title,
                stage="get_window_rect",
            )
            logger.error(
                "window recording rejected: "
                f"reason={diagnostic.reason.value}, hwnd={diagnostic.hwnd}, "
                f"title={diagnostic.title!r}, mode={diagnostic.mode}, stage={diagnostic.stage}, "
                f"rect={diagnostic.rect}, foreground_result={diagnostic.foreground_result}"
            )
            return False
        region = (rect.left(), rect.top(), rect.width(), rect.height())
        self._record_window_diagnostic(
            reason=WindowFailureReason.NONE,
            hwnd=hwnd,
            title=self._window_title,
            stage="ready",
            rect=region,
            foreground_result="not_attempted",
        )
        return self._start(region=region)

    def pause(self) -> bool:
        with self._lock:
            if not self._state_machine.transition_to(RecorderState.PAUSED):
                return False
            self._pause_start = time.time()
        self._resume_event.clear()
        return True

    def resume(self) -> bool:
        with self._lock:
            if not self._state_machine.transition_to(RecorderState.RECORDING):
                return False
            self._pause_duration += time.time() - self._pause_start
        self._resume_event.set()
        return True

    def stop(self, cancel: bool = False) -> str:
        with self._lock:
            if not self._state_machine.transition_to(RecorderState.STOPPING):
                return ""
        self._cancelled = cancel
        self._stop_event.set()
        self._resume_event.set()
        self._stop_thread = threading.Thread(target=self._stop_and_encode, daemon=True)
        self._stop_thread.start()
        return ""

    def get_state(self) -> RecorderState:
        return self._state_machine.state

    def get_elapsed(self) -> str:
        state = self.get_state()
        if state == RecorderState.IDLE:
            return "00:00"
        elapsed = time.time() - self._start_time - self._pause_duration
        if state == RecorderState.PAUSED:
            elapsed -= (time.time() - self._pause_start)
        minutes = int(elapsed) // 60
        seconds = int(elapsed) % 60
        return f"{minutes:02d}:{seconds:02d}"

    def is_saving(self) -> bool:
        return self.get_state() == RecorderState.SAVING

    def wait_until_idle(self, timeout: float = 60.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.get_state() == RecorderState.IDLE:
                return True
            time.sleep(0.1)
        return self.get_state() == RecorderState.IDLE

    def get_mode(self) -> RecordMode:
        return self._mode

    def get_window_hwnd(self) -> int:
        return self._window_hwnd

    def get_last_window_diagnostic(self) -> WindowRecordingDiagnostic:
        return self._last_window_diagnostic

    def get_audio_preflight(self) -> AudioPreflightResult:
        return self._audio_preflight

    # --- 内部实现 ---

    def _record_window_diagnostic(
        self,
        reason: WindowFailureReason,
        hwnd: int,
        title: str,
        stage: str,
        rect: tuple[int, int, int, int] | None = None,
        foreground_result: str = "not_attempted",
    ) -> WindowRecordingDiagnostic:
        diagnostic = WindowRecordingDiagnostic(
            reason=reason,
            hwnd=hwnd,
            title=title,
            mode=RecordMode.WINDOW.value,
            stage=stage,
            rect=rect,
            foreground_result=foreground_result,
        )
        self._last_window_diagnostic = diagnostic
        return diagnostic

    def _start(self, region=None) -> bool:
        with self._lock:
            if self.get_state() != RecorderState.IDLE:
                return False

            save_path = self._config.get("save_path")
            quality = "native"
            if DiskChecker.is_low_space(save_path, quality):
                return False
            if region is not None:
                normalized_region = normalize_capture_region(region)
                if normalized_region is None:
                    logger.error(f"invalid capture region: {region}")
                    return False
                region = normalized_region

            if self._mode == RecordMode.WINDOW and region is not None:
                self._window_region = region
                self._pending_window_region = None
                self._last_window_frame = None

            self._capturer = ScreenCapturer(region=region)
            if self._mode == RecordMode.WINDOW and region is not None:
                self._frame_size = (region[2], region[3])
            else:
                self._frame_size = self._capturer.get_monitor_size()
            self._encode_size = self._frame_size
            self._fps = 60
            self._output_path = FileNamer.generate(save_path)
            self._ffmpeg_path = self._get_ffmpeg_path()
            if not self._ffmpeg_path:
                logger.error("FFmpeg not found; recording cannot start")
                return False

            # 创建会话目录
            self._session_dir = TempCleaner.create_session_dir()
            TempCleaner.register_atexit(self._session_dir)
            self._video_temp_path = os.path.join(self._session_dir, "video.mp4")

            # 音频初始化（输出到会话目录）
            self._audio_temp_paths = []
            self._audio_capturer = None
            audio_source_str = self._config.get("audio_source", "none")
            system_available, microphone_available = self._probe_audio_sources(audio_source_str)
            self._audio_preflight = plan_audio_source(
                audio_source_str,
                system_available=system_available,
                microphone_available=microphone_available,
            )
            self._audio_source = self._audio_preflight.final_source
            if self._audio_preflight.degraded:
                logger.warning(
                    "audio preflight degraded: "
                    f"requested={self._audio_preflight.requested_source}, "
                    f"final={self._audio_preflight.final_source}, "
                    f"reason={self._audio_preflight.reason}, "
                    f"system_available={self._audio_preflight.system_available}, "
                    f"microphone_available={self._audio_preflight.microphone_available}"
                )
            if self._audio_source != AudioSource.NONE and self._ffmpeg_path:
                try:
                    self._audio_capturer = AudioCapturer(
                        source=self._audio_source,
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
            self._recording_failed_reason = ""
            self._last_disk_check = 0.0
            self._start_time = time.time()
            self._state_machine.transition_to(RecorderState.RECORDING)
            self._timer_resolution.begin()

            self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
            self._record_thread.start()
        return True

    def _record_loop(self):
        """录制线程：dxcam → resize（如需）→ FFmpeg pipe"""
        try:
            self._capturer.start()
        except Exception as e:
            logger.error(f"屏幕捕获器启动失败: {e}")
            if self._mode == RecordMode.WINDOW and self._window_hwnd:
                diagnostic = self._record_window_diagnostic(
                    reason=WindowFailureReason.CAPTURE_BACKEND_FAILED,
                    hwnd=self._window_hwnd,
                    title=self._window_title,
                    stage="capture_start",
                    rect=self._window_region,
                )
                logger.error(
                    "window recording capture backend failed: "
                    f"reason={diagnostic.reason.value}, hwnd={diagnostic.hwnd}, "
                    f"title={diagnostic.title!r}, mode={diagnostic.mode}, stage={diagnostic.stage}, "
                    f"rect={diagnostic.rect}"
                )
            self._stop_event.set()
            self._finish_failed_recording(f"screen capture start failed: {e}")
            return

        try:
            self._encoder = VideoEncoder(
                output_path=self._video_temp_path,
                fps=self._fps,
                frame_size=self._encode_size,
                ffmpeg_path=self._ffmpeg_path,
            )
        except Exception as e:
            logger.error(f"FFmpeg encoder start failed: {e}")
            if self._capturer:
                try:
                    self._capturer.close()
                except Exception:
                    pass
                self._capturer = None
            self._finish_failed_recording(f"ffmpeg start failed: {e}")
            return

        fps = self._fps
        frame_interval = 1.0 / fps
        rec_start = time.time()
        frames_written = 0
        was_paused = False
        last_window_update = 0

        while not self._stop_event.is_set():
            window_is_moving = self._pending_window_region is not None
            if not self._resume_event.wait(timeout=0.1):
                if self._stop_event.is_set():
                    break
                was_paused = True
                continue

            if self._stop_event.is_set():
                break

            now = time.time()
            if not self._check_recording_disk_space(now):
                self._recording_failed_reason = "disk space became low during recording"
                self._stop_event.set()
                break

            if was_paused:
                rec_start = now - frames_written * frame_interval
                was_paused = False

            # 窗口模式：100ms 更新捕获区域（与高亮边框同步）
            if self._mode == RecordMode.WINDOW and self._window_hwnd:
                now = time.time()
                if now - last_window_update >= _WINDOW_CAPTURE_UPDATE_INTERVAL:
                    rect = self._get_window_rect(self._window_hwnd)
                    if rect is None:
                        user32 = ctypes.windll.user32
                        if not user32.IsWindow(self._window_hwnd):
                            reason = "closed"
                        elif user32.IsIconic(self._window_hwnd):
                            reason = "minimized"
                        else:
                            reason = "closed"
                        if not self._window_lost_emitted:
                            logger.info(f"录制窗口丢失: {reason}")
                            self._window_lost_bridge.window_lost.emit(reason)
                            self._window_lost_emitted = True
                        if reason == "closed":
                            break
                        # minimized：录制线程立即自己同步暂停（不依赖 main 异步 pause）
                        # 清除 _resume_event 使下方 wait 阻塞，直到用户点"继续"
                        # main 线程会处理 UI 暂停；resume() 置位 event 唤醒
                        self._resume_event.clear()
                        while not self._stop_event.is_set():
                            if self._resume_event.wait(timeout=0.2):
                                break
                        self._window_lost_emitted = False
                        was_paused = True
                        continue
                    # 窗口恢复后清除标志
                    self._window_lost_emitted = False
                    last_window_update = now
                    window_is_moving = self._update_window_capture_region(
                        (rect.left(), rect.top(), rect.width(), rect.height()),
                        now=now,
                    )

            if window_is_moving and self._last_window_frame is not None:
                frame = self._last_window_frame
            else:
                try:
                    frame = self._capturer.capture_frame()
                except Exception:
                    break
                if frame is None:
                    if not self._capturer._started:
                        break
                    continue
                if self._mode == RecordMode.WINDOW:
                    self._last_window_frame = frame.copy()

            frame = self._prepare_frame_for_encoding(frame)

            target_frame = int((time.time() - rec_start) / frame_interval)
            while frames_written < target_frame:
                if not self._encoder.write_frame(frame):
                    self._recording_failed_reason = "video frame write failed"
                    self._stop_event.set()
                    break
                frames_written += 1

            if self._stop_event.is_set():
                break

            if not self._encoder.write_frame(frame):
                self._recording_failed_reason = "video frame write failed"
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

        if self._recording_failed_reason:
            self._finish_failed_recording(self._recording_failed_reason)
            return

        self._timer_resolution.end()

    def _prepare_frame_for_encoding(self, frame):
        if self._mode == RecordMode.WINDOW and (frame.shape[1], frame.shape[0]) != self._frame_size:
            frame = resize_bgr_frame(frame, self._frame_size)

        if self._encode_size != self._frame_size:
            frame = resize_bgr_frame(frame, self._encode_size)

        if self._mode == RecordMode.WINDOW:
            return frame

        capture_region = self._capturer.get_capture_region() if self._capturer else None
        return draw_cursor(frame, capture_region, size_multiplier=1.0)

    def _stop_and_encode(self):
        # 等待录制线程完成 encoder.close()（FFmpeg flush 可能需要数十秒）
        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join()

        # 停止音频
        if self._recording_failed_reason:
            return

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
                self._state_machine.reset()
            return

        with self._lock:
            self._state_machine.transition_to(RecorderState.SAVING)

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
                self._state_machine.reset()
            if self._on_saved:
                try:
                    self._on_saved(result_path)
                except Exception as e:
                    logger.error(f"on_saved 回调异常: {e}")

            if self._on_event:
                try:
                    event = RecordingEvent.saved(result_path) if result_path else RecordingEvent.failed("finalize failed")
                    self._on_event(event)
                except Exception as e:
                    logger.error(f"on_event callback failed: {e}")

    def _mix_audio(self, video_path: str, audio_paths: list) -> str:
        """FFmpeg 混合音视频，返回混合后路径（session_dir/mixed.mp4）"""
        audio_paths = [path for path in audio_paths if self._audio_has_samples(path)]
        if not audio_paths:
            logger.warning("音频文件无有效采样，跳过音频混合")
            return ""

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

    @staticmethod
    def _audio_has_samples(path: str) -> bool:
        try:
            if not path or not os.path.exists(path) or os.path.getsize(path) <= 44:
                return False
            with wave.open(path, "rb") as wav_file:
                return wav_file.getnframes() > 0
        except Exception as e:
            logger.warning(f"音频文件无效，跳过混合: {path}, {e}")
            return False

    def _probe_audio_sources(self, requested_source: str) -> tuple[bool, bool]:
        def probe(name: str) -> bool:
            method = getattr(AudioCapturer, name, None)
            if method is None:
                return True
            try:
                return bool(method())
            except Exception as e:
                logger.warning(f"audio preflight probe failed: {name}, {e}")
                return False

        if requested_source == AudioSource.NONE:
            return False, False
        if requested_source == AudioSource.SYSTEM:
            return probe("probe_system_available"), False
        if requested_source == AudioSource.MICROPHONE:
            return False, probe("probe_microphone_available")
        if requested_source == AudioSource.BOTH:
            return probe("probe_system_available"), probe("probe_microphone_available")
        return False, False

    def _get_target_size(self):
        quality = self._config.get("quality", "native")
        target = ConfigManager.QUALITY_SIZES.get(quality)
        if target is None:
            return None
        if self._mode == RecordMode.WINDOW and quality == "high":
            return None
        if self._mode in (RecordMode.REGION, RecordMode.WINDOW) and self._frame_size:
            return self._fit_size_with_aspect_ratio(self._frame_size, target)
        return target

    @staticmethod
    def _fit_size_with_aspect_ratio(source: tuple[int, int], target: tuple[int, int]) -> tuple[int, int]:
        fw, fh = source
        tw, th = target
        src_ratio = fw / fh
        dst_ratio = tw / th
        if src_ratio > dst_ratio:
            new_w, new_h = tw, int(tw / src_ratio)
        else:
            new_w, new_h = int(th * src_ratio), th
        return (max(new_w & ~1, 2), max(new_h & ~1, 2))

    def _update_window_capture_region(self, region: tuple[int, int, int, int], now: float) -> bool:
        if self._window_region is None:
            self._window_region = region
            return False
        if region == self._window_region and self._pending_window_region is None:
            return False

        if region != self._window_region:
            if region != self._pending_window_region:
                self._pending_window_region = region
                self._last_window_move_time = now
                return True
            if now - self._last_window_move_time < _WINDOW_MOVE_STABLE_DELAY:
                return True

        if self._pending_window_region is not None:
            self._capturer.update_region(self._pending_window_region)
            self._window_region = self._pending_window_region
            self._pending_window_region = None
            return False
        return False

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
        """获取窗口客户区屏幕坐标（GetClientRect + ClientToScreen）

        仅在窗口可见且非最小化时返回有效矩形，否则返回 None。
        窗口关闭/最小化判断由调用方通过 IsWindow/IsIconic 处理。
        """
        return get_window_client_rect(hwnd)

    @staticmethod
    def _get_window_title(hwnd: int) -> str:
        n = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return ""
        buf = ctypes.create_unicode_buffer(n + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value
