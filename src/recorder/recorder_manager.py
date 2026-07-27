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
from recorder.capture_metrics import evaluate_capture_gate, normalize_completion_times
from recorder.events import RecordingEvent
from recorder.frame_resize import resize_bgr_frame
from recorder.frame_schedule import due_frame_count
from recorder.screen_capturer import ScreenCapturer
from recorder.state_machine import RecordingState, RecordingStateMachine
from recorder.timer_resolution import TimerResolution
from recorder.video_encoder import VideoEncoder
from recorder.window_diagnostics import WindowFailureReason, WindowRecordingDiagnostic
from services.recording_profile import EffectiveRecordingProfile, resolve_recording_profile
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
        self._recording_ready = threading.Event()
        self._finalize_thread: threading.Thread = None
        self._stop_thread: threading.Thread = None
        self._stop_event = threading.Event()
        self._resume_event = threading.Event()
        self._start_time: float = 0
        self._pause_duration: float = 0
        self._pause_start: float = 0
        self._last_duration_sec: float = 0
        self._output_path: str = ""
        self._lock = threading.Lock()
        self._cancelled = False
        self._fps: int = 30
        self._next_fps_override: int | None = None
        self._profile_notice: str = ""
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
        self._audio_track_start_times: dict[str, float] = {}
        self._audio_track_latency_seconds: dict[str, float] = {}
        self._video_started_at: float | None = None

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
        self._last_result_path = ""
        self._last_failure_reason = ""
        self._disk_check_interval = 1.0
        self._last_disk_check = 0.0
        self._last_performance: dict[str, float | int | bool | tuple[str, ...] | None] = {}

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
        return not DiskChecker.is_low_space(save_path, quality, fps=self._fps)

    def _finish_failed_recording(self, reason: str) -> None:
        self._last_result_path = ""
        self._last_failure_reason = reason
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

    def set_next_fps_override(self, fps: int | None) -> None:
        self._next_fps_override = int(fps) if fps is not None else None

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
            previous_state = self._state_machine.state
            if not self._state_machine.transition_to(RecorderState.STOPPING):
                return ""
            self._last_duration_sec = self._calculate_elapsed_seconds(previous_state)
        self._cancelled = cancel
        self._stop_event.set()
        self._resume_event.set()
        capturer = self._capturer
        if capturer is not None and hasattr(capturer, "request_stop"):
            try:
                capturer.request_stop()
            except Exception:
                logger.exception("DXCamera asynchronous stop request failed")
        self._stop_thread = threading.Thread(target=self._stop_and_encode, daemon=True)
        self._stop_thread.start()
        return ""

    def get_state(self) -> RecorderState:
        return self._state_machine.state

    def get_elapsed(self) -> str:
        state = self.get_state()
        if state == RecorderState.IDLE:
            return "00:00"
        elapsed = self._calculate_elapsed_seconds(state)
        minutes = int(elapsed) // 60
        seconds = int(elapsed) % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _calculate_elapsed_seconds(self, state: RecorderState) -> float:
        elapsed = time.time() - self._start_time - self._pause_duration
        if state == RecorderState.PAUSED:
            elapsed -= time.time() - self._pause_start
        return max(0.0, elapsed)

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

    def get_last_recording_metadata(
        self,
    ) -> dict[str, float | int | str | bool | tuple[str, ...] | None]:
        """返回最终化回调可直接入库的会话已知元数据。"""
        width, height = self._encode_size if self._encode_size else (0, 0)
        metadata: dict[str, float | int | str | bool | tuple[str, ...] | None] = {
            "duration_sec": self._last_duration_sec or None,
            "width": width or None,
            "height": height or None,
            "fps": float(self._fps) if self._fps else None,
            "mode": self._mode.value,
            "audio_source": self._audio_source,
        }
        metadata.update(self._last_performance)
        return metadata

    def get_window_hwnd(self) -> int:
        return self._window_hwnd

    def get_last_window_diagnostic(self) -> WindowRecordingDiagnostic:
        return self._last_window_diagnostic

    def get_audio_preflight(self) -> AudioPreflightResult:
        return self._audio_preflight

    def get_diagnostic_context(self) -> dict:
        """返回诊断导出所需的只读录制上下文。"""
        window = self._last_window_diagnostic
        audio = self._audio_preflight
        ffmpeg_path = self._ffmpeg_path or self._get_ffmpeg_path()
        return {
            "config": {
                "save_path": self._config.get("save_path"),
                "audio_source": self._config.get("audio_source"),
                "quality": self._config.get("quality"),
                "fps": self._config.get("fps"),
            },
            "recorder": {
                "state": self.get_state().value,
                "mode": self._mode.value,
                "output_path": self._output_path,
                "session_dir": self._session_dir,
                "last_result": self._last_result_path,
                "last_failure_reason": self._last_failure_reason or self._recording_failed_reason,
                "performance": dict(self._last_performance),
            },
            "ffmpeg": {
                "path": ffmpeg_path,
                "exists": bool(ffmpeg_path and os.path.isfile(ffmpeg_path)),
                "frozen": bool(getattr(sys, "frozen", False)),
            },
            "audio": {
                "requested_source": audio.requested_source,
                "final_source": audio.final_source,
                "system_available": audio.system_available,
                "microphone_available": audio.microphone_available,
                "degraded": audio.degraded,
                "reason": audio.reason,
            },
            "window": {
                "hwnd": window.hwnd,
                "title": window.title,
                "mode": window.mode,
                "stage": window.stage,
                "reason": window.reason.value,
                "rect": window.rect,
                "foreground_result": window.foreground_result,
            },
        }

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
            quality = self._config.get("quality", "high")
            configured_fps = (
                self._next_fps_override
                if self._next_fps_override is not None
                else int(self._config.get("fps", 30))
            )
            capture_fps = (
                60
                if configured_fps == 120 and self._mode != RecordMode.FULLSCREEN
                else configured_fps
            )
            if DiskChecker.is_low_space(save_path, quality, fps=capture_fps):
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

            self._next_fps_override = None
            self._capturer = ScreenCapturer(region=region, target_fps=capture_fps)
            if self._mode == RecordMode.WINDOW and region is not None:
                self._frame_size = (region[2], region[3])
            else:
                self._frame_size = self._capturer.get_monitor_size()
            profile = self._resolve_effective_profile(
                self._frame_size,
                configured_fps=configured_fps,
            )
            self._encode_size = profile.output_size
            self._fps = profile.effective_fps
            self._profile_notice = profile.notice
            if self._profile_notice:
                logger.info(self._profile_notice)
            self._output_path = FileNamer.generate(save_path)
            self._ffmpeg_path = self._get_ffmpeg_path()
            if not self._ffmpeg_path:
                logger.error("FFmpeg not found; recording cannot start")
                self._last_result_path = ""
                self._last_failure_reason = "ffmpeg not found"
                return False

            # 创建会话目录
            self._session_dir = TempCleaner.create_session_dir()
            TempCleaner.register_atexit(self._session_dir)
            self._video_temp_path = os.path.join(self._session_dir, "video.mp4")

            # 音频初始化（输出到会话目录）
            self._audio_temp_paths = []
            self._audio_track_start_times = {}
            self._audio_track_latency_seconds = {}
            self._video_started_at = None
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
            self._recording_ready.clear()
            self._resume_event.set()
            self._pause_duration = 0
            self._cancelled = False
            self._recording_failed_reason = ""
            self._last_performance = {}
            self._last_disk_check = 0.0
            self._start_time = time.time()
            self._state_machine.transition_to(RecorderState.RECORDING)
            self._timer_resolution.begin()

            self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
            self._record_thread.start()
        if not self._recording_ready.wait(timeout=10):
            logger.error("recording backend did not become ready in time")
            self._stop_event.set()
            return False
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
            self._recording_failed_reason = f"screen capture start failed: {e}"
            self._stop_event.set()
            self._recording_ready.set()
            self._finish_failed_recording(self._recording_failed_reason)
            return

        try:
            self._encoder = VideoEncoder(
                output_path=self._video_temp_path,
                fps=self._fps,
                frame_size=self._encode_size,
                ffmpeg_path=self._ffmpeg_path,
                high_frame_rate=self._fps >= 120,
            )
        except Exception as e:
            logger.error(f"FFmpeg encoder start failed: {e}")
            if self._capturer:
                try:
                    self._capturer.close()
                except Exception:
                    pass
                self._capturer = None
            self._recording_failed_reason = f"ffmpeg start failed: {e}"
            self._recording_ready.set()
            self._finish_failed_recording(self._recording_failed_reason)
            return

        fps = self._fps
        frame_interval = 1.0 / fps
        rec_start = time.time()
        self._start_time = rec_start
        self._recording_ready.set()
        captured_frames = 0
        frames_written = 0
        was_paused = False
        last_window_update = 0

        while not self._stop_event.is_set():
            frame_captured_at = time.perf_counter()
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
                    frame_captured_at = time.perf_counter()
                except Exception:
                    break
                if frame is None:
                    if not self._capturer._started:
                        break
                    continue
                captured_frames += 1
                if self._mode == RecordMode.WINDOW:
                    self._last_window_frame = frame.copy()

            frame = self._prepare_frame_for_encoding(frame)

            due_frames = due_frame_count(
                elapsed_seconds=time.time() - rec_start,
                target_fps=fps,
                submitted_frames=frames_written,
            )
            for _ in range(due_frames):
                if not self._encoder.write_frame(
                    frame,
                    cancel_event=self._stop_event,
                    timeout_seconds=1.0 if fps >= 120 else None,
                ):
                    if self._stop_event.is_set():
                        break
                    self._recording_failed_reason = "video frame write failed"
                    self._stop_event.set()
                    break
                if frames_written == 0:
                    self._video_started_at = frame_captured_at
                    logger.info(
                        "video timeline started: monotonic=%.6f",
                        self._video_started_at,
                    )
                frames_written += 1

            if self._stop_event.is_set():
                break

            next_time = rec_start + frames_written * frame_interval
            wait = next_time - time.time()
            if wait > 0.002:
                time.sleep(max(wait - 0.001, 0.001))

        # 关闭编码器（FFmpeg flush）
        if self._encoder:
            encoder_ok = self._encoder.close()
            logger.info("recording cleanup stage: encoder_closed")
            logger.info("recording cleanup stage: performance_snapshot_started")
            self._capture_last_performance(
                self._encoder,
                captured_frames=captured_frames,
                submitted_frames=frames_written,
            )
            logger.info("recording cleanup stage: performance_snapshot_completed")
            if not encoder_ok and not self._recording_failed_reason:
                self._recording_failed_reason = "video encoder did not complete successfully"
            self._encoder = None

        if self._capturer:
            try:
                logger.info("recording cleanup stage: capturer_close_started")
                self._capturer.close()
                logger.info("recording cleanup stage: capturer_close_completed")
            except Exception:
                logger.exception("recording cleanup stage: capturer_close_failed")
            self._capturer = None

        logger.info(f"录制线程结束，frames={frames_written}")

        if self._recording_failed_reason:
            self._finish_failed_recording(self._recording_failed_reason)
            return

        self._timer_resolution.end()

    def _capture_last_performance(
        self,
        encoder,
        *,
        captured_frames: int | None = None,
        submitted_frames: int,
    ) -> None:
        if self._fps < 120 or not hasattr(encoder, "get_performance_snapshot"):
            self._last_performance = {
                "target_fps": self._fps,
                "captured_frames": captured_frames,
                "submitted_frames": submitted_frames,
            }
            return

        performance = encoder.get_performance_snapshot()
        completion_times = normalize_completion_times(
            performance.completion_times,
            target_fps=self._fps,
        )
        measured_duration = max(
            self._last_duration_sec,
            completion_times[-1] if completion_times else 0.0,
            submitted_frames / self._fps if submitted_frames else 0.0,
        )
        if measured_duration <= 0:
            self._last_performance = {
                "target_fps": self._fps,
                "captured_frames": captured_frames,
                "submitted_frames": submitted_frames,
                "completed_frames": performance.completed_frames,
                "stable": False,
                "performance_reasons": ("no_completed_frames",),
            }
            return

        gate = evaluate_capture_gate(
            frame_times=completion_times,
            backlog_samples=performance.backlog_samples,
            duration_seconds=measured_duration,
        )
        self._last_performance = {
            "target_fps": self._fps,
            "captured_frames": captured_frames,
            "submitted_frames": submitted_frames,
            "completed_frames": gate.encoded_frames,
            "average_fps": gate.average_fps,
            "minimum_one_second_fps": gate.minimum_one_second_fps,
            "maximum_backlog_ms": gate.maximum_backlog_ms,
            "dropped_frames": gate.dropped_frames,
            "stable": gate.passed,
            "performance_reasons": gate.reasons,
        }
        log = logger.info if gate.passed else logger.warning
        log(
            "120 FPS recording performance: stable=%s average_fps=%.3f "
            "minimum_one_second_fps=%d maximum_backlog_ms=%.3f "
            "submitted_frames=%d completed_frames=%d dropped_frames=%d reasons=%s",
            gate.passed,
            gate.average_fps,
            gate.minimum_one_second_fps,
            gate.maximum_backlog_ms,
            submitted_frames,
            gate.encoded_frames,
            gate.dropped_frames,
            ",".join(gate.reasons) or "none",
        )

    def _prepare_frame_for_encoding(self, frame):
        if self._mode == RecordMode.WINDOW and (frame.shape[1], frame.shape[0]) != self._frame_size:
            frame = resize_bgr_frame(frame, self._frame_size)

        if self._encode_size != self._frame_size:
            frame = resize_bgr_frame(frame, self._encode_size)

        return frame

    def _stop_and_encode(self):
        # 等待录制线程完成 encoder.close()（FFmpeg flush 可能需要数十秒）
        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join()

        # 停止音频
        if self._recording_failed_reason:
            return

        self._audio_temp_paths = []
        self._audio_track_start_times = {}
        self._audio_track_latency_seconds = {}
        if self._audio_capturer:
            try:
                paths = self._audio_capturer.stop()
                self._audio_temp_paths = [p for p in (paths if isinstance(paths, list) else [paths]) if p and os.path.exists(p)]
                self._audio_track_start_times = (
                    self._audio_capturer.get_track_start_times()
                )
                self._audio_track_latency_seconds = (
                    self._audio_capturer.get_track_latency_seconds()
                )
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
            self._last_failure_reason = f"finalize failed: {e}"
        finally:
            self._last_result_path = result_path
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
        alignment_filters = self._build_audio_alignment_filters(audio_paths)
        if alignment_filters:
            filter_parts, output_labels = alignment_filters
            if len(output_labels) == 1:
                filter_parts.append(f"{output_labels[0]}anull[a]")
            else:
                filter_parts.append(
                    "".join(output_labels)
                    + f"amix=inputs={len(output_labels)}:"
                    "duration=longest:dropout_transition=0[a]"
                )
            cmd.extend([
                "-filter_complex", ";".join(filter_parts),
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-ac", "2",
                "-b:a", "192k", "-shortest", mixed,
            ])
        elif len(audio_paths) == 1:
            cmd.extend([
                "-c:v", "copy", "-c:a", "aac", "-ac", "2",
                "-b:a", "192k", "-shortest", mixed,
            ])
        else:
            cmd.extend([
                "-filter_complex",
                "[1:a]aformat=sample_rates=48000:channel_layouts=stereo[sys];"
                "[2:a]aformat=sample_rates=48000:channel_layouts=stereo[mic];"
                "[sys][mic]amix=inputs=2:duration=longest:dropout_transition=0[a]",
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", mixed,
            ])
        try:
            subprocess.run(cmd, check=True, timeout=120,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            return mixed
        except Exception as e:
            logger.error(f"音频混合失败: {e}")
            self._last_failure_reason = f"audio mix failed: {e}"
            return ""

    def _build_audio_alignment_filters(
        self,
        audio_paths: list[str],
    ) -> tuple[list[str], list[str]] | None:
        if self._video_started_at is None:
            return None

        filters: list[str] = []
        labels: list[str] = []
        for index, path in enumerate(audio_paths, start=1):
            audio_started_at = self._audio_track_start_times.get(path)
            if audio_started_at is None:
                logger.warning("audio alignment timestamp missing: path=%s", path)
                return None

            device_latency_seconds = self._audio_track_latency_seconds.get(path, 0.0)
            effective_audio_started_at = audio_started_at + device_latency_seconds
            offset_seconds = self._video_started_at - effective_audio_started_at
            if abs(offset_seconds) > 5.0:
                logger.warning(
                    "audio alignment offset rejected: path=%s offset_ms=%.3f",
                    path,
                    offset_seconds * 1000,
                )
                return None

            if offset_seconds >= 0:
                alignment = f"atrim=start={offset_seconds:.6f}"
            else:
                delay_ms = max(0, round(-offset_seconds * 1000))
                alignment = f"adelay={delay_ms}:all=1"
            label = f"[aligned{index}]"
            filters.append(
                f"[{index}:a]{alignment},asetpts=PTS-STARTPTS,"
                f"aformat=sample_rates=48000:channel_layouts=stereo{label}"
            )
            labels.append(label)
            logger.info(
                "audio timeline alignment: path=%s audio_start=%.6f "
                "device_latency_ms=%.3f effective_audio_start=%.6f "
                "video_start=%.6f offset_ms=%.3f operation=%s",
                path,
                audio_started_at,
                device_latency_seconds * 1000,
                effective_audio_started_at,
                self._video_started_at,
                offset_seconds * 1000,
                "trim" if offset_seconds >= 0 else "delay",
            )
        return filters, labels

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

    def _resolve_effective_profile(
        self,
        source_size: tuple[int, int],
        *,
        configured_fps: int | None = None,
    ) -> EffectiveRecordingProfile:
        return resolve_recording_profile(
            configured_fps=(
                int(self._config.get("fps", 30))
                if configured_fps is None
                else configured_fps
            ),
            mode=self._mode.value,
            source_size=source_size,
            quality=self._config.get("quality", "native"),
        )

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
        if getattr(sys, "frozen", False):
            candidates = []
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(os.path.join(meipass, "ffmpeg", "ffmpeg.exe"))
            candidates.append(
                os.path.join(
                    os.path.dirname(sys.executable),
                    "ffmpeg",
                    "ffmpeg.exe",
                )
            )
            for path in candidates:
                if os.path.isfile(path):
                    return path
        dev_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
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
