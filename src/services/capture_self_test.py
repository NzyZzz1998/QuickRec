from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Event

from recorder.capture_metrics import normalize_completion_times
from recorder.frame_resize import resize_bgr_frame
from recorder.frame_schedule import due_frame_count
from recorder.screen_capturer import ScreenCapturer
from recorder.video_encoder import VideoEncoder
from services.capture_capability import EnvironmentFingerprint, SelfTestMeasurement
from utils.media_metadata import probe_media

logger = logging.getLogger("QuickRec")


def _fit_1080p(source_size: tuple[int, int]) -> tuple[int, int]:
    width, height = source_size
    scale = min(1920 / width, 1080 / height, 1.0)
    return max(int(width * scale) & ~1, 2), max(int(height * scale) & ~1, 2)


class ProductionCaptureSelfTestRunner:
    """Run the 120 FPS gate through the production capture and encoder path."""

    def __init__(
        self,
        *,
        save_dir: str | Path,
        ffmpeg_path: str,
        ffprobe_path: str | None = None,
        duration_seconds: float = 5.0,
        progress: Callable[[str, int], None] | None = None,
        capturer_factory: Callable[..., ScreenCapturer] = ScreenCapturer,
        encoder_factory: Callable[..., VideoEncoder] = VideoEncoder,
        clock: Callable[[], float] = time.perf_counter,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.save_dir = Path(save_dir)
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.duration_seconds = duration_seconds
        self.progress = progress or (lambda _stage, _percent: None)
        self._capturer_factory = capturer_factory
        self._encoder_factory = encoder_factory
        self._clock = clock
        self._sleep = sleep

    def __call__(
        self,
        _fingerprint: EnvironmentFingerprint,
        cancel_event: Event,
    ) -> SelfTestMeasurement:
        self.save_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.save_dir / (
            f".quickrec-120-selftest-{datetime.now().strftime('%Y%m%d%H%M%S%f')}.mp4"
        )
        capturer: ScreenCapturer | None = None
        encoder: VideoEncoder | None = None
        self.progress("prepare", 0)
        try:
            capturer = self._capturer_factory(target_fps=120)
            source_size = capturer.get_monitor_size()
            output_size = _fit_1080p(source_size)
            capturer.start()
            encoder = self._encoder_factory(
                output_path=str(output_path),
                fps=120,
                frame_size=output_size,
                ffmpeg_path=self.ffmpeg_path,
                high_frame_rate=True,
            )
            started = self._clock()
            submitted = 0
            target_frames = round(self.duration_seconds * 120)
            self.progress("capture", 1)
            while not cancel_event.is_set() and submitted < target_frames:
                elapsed = self._clock() - started
                frame = capturer.capture_frame()
                if frame is None:
                    self._sleep(0.001)
                    continue
                if (frame.shape[1], frame.shape[0]) != output_size:
                    frame = resize_bgr_frame(frame, output_size)
                due = due_frame_count(
                    elapsed_seconds=elapsed,
                    target_fps=120,
                    submitted_frames=submitted,
                )
                for _ in range(min(due, target_frames - submitted)):
                    if not encoder.write_frame(
                        frame,
                        cancel_event=cancel_event,
                        timeout_seconds=1.0,
                    ):
                        if cancel_event.is_set():
                            break
                        raise RuntimeError("encoder feed failed")
                    submitted += 1
                if cancel_event.is_set():
                    break
                percent = min(int(elapsed / self.duration_seconds * 90), 89)
                self.progress("capture", max(percent, 1))
                if due == 0:
                    self._sleep(0.001)

            encoder_ok = encoder.close()
            performance = encoder.get_performance_snapshot()
            completion_times = normalize_completion_times(
                performance.completion_times,
                target_fps=120,
            )
            measured_duration = max(
                self.duration_seconds,
                completion_times[-1] if completion_times else self.duration_seconds,
            )
            encoder = None
            if cancel_event.is_set():
                return SelfTestMeasurement(
                    duration_seconds=measured_duration,
                    completion_times=completion_times,
                    backlog_samples=performance.backlog_samples,
                    output_path=output_path,
                    probe_ok=False,
                    failure_stage="cancelled",
                    failure_reason="self test cancelled",
                )
            if not encoder_ok:
                return self._failure(
                    output_path,
                    "encoding",
                    "FFmpeg did not complete successfully",
                    completion_times,
                    performance.backlog_samples,
                )
            self.progress("probe", 92)
            metadata = probe_media(
                output_path,
                ffprobe_path=self.ffprobe_path,
            )
            if (
                not metadata.ok
                or metadata.width != output_size[0]
                or metadata.height != output_size[1]
                or metadata.fps is None
                or abs(metadata.fps - 120) > 0.5
            ):
                return self._failure(
                    output_path,
                    "ffprobe",
                    metadata.error or "unexpected self-test output metadata",
                    completion_times,
                    performance.backlog_samples,
                )
            self.progress("complete", 100)
            return SelfTestMeasurement(
                duration_seconds=measured_duration,
                completion_times=completion_times,
                backlog_samples=performance.backlog_samples,
                output_path=output_path,
                probe_ok=True,
            )
        except Exception as exc:
            logger.exception("120 FPS self test failed")
            return self._failure(output_path, "runtime", str(exc))
        finally:
            if encoder is not None:
                encoder.close()
            if capturer is not None:
                capturer.close()

    def _failure(
        self,
        output_path: Path,
        stage: str,
        reason: str,
        completion_times: tuple[float, ...] = (),
        backlog_samples: tuple[tuple[float, float], ...] = (),
    ) -> SelfTestMeasurement:
        return SelfTestMeasurement(
            duration_seconds=self.duration_seconds,
            completion_times=completion_times,
            backlog_samples=backlog_samples,
            output_path=output_path,
            probe_ok=False,
            failure_stage=stage,
            failure_reason=reason,
        )
