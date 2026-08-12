"""QuickRec Lite 全屏录制控制模块。"""

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import wave
from collections.abc import Callable

from config import ConfigManager
from recorder.audio_capturer import AudioCapturer, AudioSource
from recorder.audio_preflight import AudioPreflightResult, plan_audio_source
from recorder.cursor_overlay import draw_cursor
from recorder.events import RecordingEvent
from recorder.frame_schedule import due_frame_count
from recorder.screen_capturer import ScreenCapturer
from recorder.state_machine import RecordingState, RecordingStateMachine
from recorder.timer_resolution import TimerResolution
from recorder.video_encoder import VideoEncoder
from utils.disk_checker import DiskChecker
from utils.file_namer import FileNamer
from utils.temp_cleaner import TempCleaner

logger = logging.getLogger("QuickRec")

RecorderState = RecordingState


class RecorderManager:
    """Lite 全屏录制管理器（FFmpeg pipe + TempCleaner）。"""

    def __init__(self, config: ConfigManager = None, on_saved=None, on_event=None):
        self._config = config or ConfigManager()
        self._state_machine = RecordingStateMachine()
        self._capturer: ScreenCapturer = None
        self._encoder: VideoEncoder = None
        self._record_thread: threading.Thread | None = None
        self._finalize_thread: threading.Thread | None = None
        self._stop_thread: threading.Thread | None = None
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
        self._audio_track_start_times: dict[str, float] = {}
        self._audio_track_latency_seconds: dict[str, float] = {}
        self._video_started_at: float | None = None

        self._on_saved = on_saved
        self._on_event = on_event
        self._timer_resolution = TimerResolution()
        self._recording_failed_reason = ""
        self._disk_check_interval = 1.0
        self._last_disk_check = 0.0

    # --- 公共接口 ---

    def set_event_handler(self, callback: Callable[[RecordingEvent], None] | None) -> None:
        self._on_event = callback

    def _check_recording_disk_space(self, now: float) -> bool:
        if now - self._last_disk_check < self._disk_check_interval:
            return True
        self._last_disk_check = now
        save_path = self._config.get("save_path")
        quality = self._config.get("quality", "high")
        return not DiskChecker.is_low_space(save_path, quality, fps=60)

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
        return self._start()

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
        if self._capturer:
            request_stop = getattr(self._capturer, "request_stop", None)
            if callable(request_stop):
                request_stop()
        self._stop_thread = threading.Thread(target=self._stop_and_encode, daemon=True)
        self._stop_thread.start()
        return ""

    def get_state(self) -> RecordingState:
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

    def get_audio_preflight(self) -> AudioPreflightResult:
        return self._audio_preflight

    # --- 内部实现 ---

    def _start(self) -> bool:
        with self._lock:
            if self.get_state() != RecorderState.IDLE:
                return False

            save_path = self._config.get("save_path")
            quality = "native"
            if DiskChecker.is_low_space(save_path, quality, fps=60):
                return False
            self._capturer = ScreenCapturer(target_fps=60)
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

        while not self._stop_event.is_set():
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

            try:
                frame = self._capturer.capture_frame()
                frame_captured_at = time.perf_counter()
            except Exception:
                break
            if frame is None:
                if not self._capturer._started:
                    break
                continue

            frame = self._prepare_frame_for_encoding(frame)

            due_frames = due_frame_count(
                elapsed_seconds=time.time() - rec_start,
                target_fps=fps,
                submitted_frames=frames_written,
            )
            for _ in range(due_frames):
                if not self._encoder.write_frame(frame):
                    self._recording_failed_reason = "video frame write failed"
                    self._stop_event.set()
                    break
                if frames_written == 0:
                    self._video_started_at = frame_captured_at
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
        return draw_cursor(frame, None, size_multiplier=1.0)

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
                get_starts = getattr(self._audio_capturer, "get_track_start_times", None)
                get_latencies = getattr(self._audio_capturer, "get_track_latency_seconds", None)
                if get_starts:
                    self._audio_track_start_times = get_starts()
                if get_latencies:
                    self._audio_track_latency_seconds = get_latencies()
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
                "audio timeline alignment: path=%s offset_ms=%.3f operation=%s",
                path,
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
