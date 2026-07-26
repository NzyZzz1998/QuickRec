from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from recorder.video_encoder import EncoderPerformance
from services.capture_capability import EnvironmentFingerprint
from services.capture_self_test import ProductionCaptureSelfTestRunner, _fit_1080p


def _fingerprint() -> EnvironmentFingerprint:
    return EnvironmentFingerprint(1, 1920, 1080, 120, "E:", "cpu", "gpu", "8", "libx264")


class FakeClock:
    def __init__(self) -> None:
        self.value = -0.01

    def __call__(self) -> float:
        self.value += 0.01
        return self.value


class FakeCapturer:
    instances: list[FakeCapturer] = []

    def __init__(self, *, target_fps: int) -> None:
        self.target_fps = target_fps
        self.started = False
        self.closed = False
        self.instances.append(self)

    def get_monitor_size(self) -> tuple[int, int]:
        return 320, 180

    def start(self) -> None:
        self.started = True

    def capture_frame(self):
        return np.zeros((180, 320, 3), dtype=np.uint8)

    def close(self) -> None:
        self.closed = True


class FakeEncoder:
    instances: list[FakeEncoder] = []
    close_ok = True

    def __init__(self, *, output_path: str, fps: int, frame_size, ffmpeg_path: str, high_frame_rate: bool) -> None:
        self.output_path = Path(output_path)
        self.fps = fps
        self.frame_size = frame_size
        self.ffmpeg_path = ffmpeg_path
        self.high_frame_rate = high_frame_rate
        self.frames = 0
        self.closed = False
        self.instances.append(self)

    def write_frame(
        self,
        _frame,
        *,
        cancel_event=None,
        timeout_seconds=None,
    ) -> bool:
        self.frames += 1
        return True

    def close(self) -> bool:
        self.closed = True
        self.output_path.write_bytes(b"video")
        return self.close_ok

    def get_performance_snapshot(self) -> EncoderPerformance:
        return EncoderPerformance(
            completed_frames=self.frames,
            completion_times=tuple(index / 120 for index in range(1, self.frames + 1)),
            backlog_samples=((0.02, 5.0),),
        )


def _runner(tmp_path: Path, progress=None) -> ProductionCaptureSelfTestRunner:
    FakeCapturer.instances.clear()
    FakeEncoder.instances.clear()
    FakeEncoder.close_ok = True
    return ProductionCaptureSelfTestRunner(
        save_dir=tmp_path,
        ffmpeg_path="ffmpeg.exe",
        ffprobe_path="ffprobe.exe",
        duration_seconds=0.05,
        progress=progress,
        capturer_factory=FakeCapturer,
        encoder_factory=FakeEncoder,
        clock=FakeClock(),
        sleep=lambda _seconds: None,
    )


def test_fit_1080p_preserves_aspect_ratio_and_even_dimensions():
    assert _fit_1080p((2560, 1440)) == (1920, 1080)
    assert _fit_1080p((321, 181)) == (320, 180)


def test_production_self_test_success_uses_production_contract(tmp_path, monkeypatch):
    progress: list[tuple[str, int]] = []
    monkeypatch.setattr(
        "services.capture_self_test.probe_media",
        lambda *_args, **_kwargs: SimpleNamespace(
            ok=True,
            width=320,
            height=180,
            fps=120.0,
            error="",
        ),
    )

    result = _runner(
        tmp_path,
        lambda stage, percent: progress.append((stage, percent)),
    )(_fingerprint(), threading.Event())

    assert result.probe_ok is True
    assert result.failure_stage == ""
    assert result.completion_times
    assert FakeCapturer.instances[0].target_fps == 120
    assert FakeCapturer.instances[0].closed is True
    assert FakeEncoder.instances[0].high_frame_rate is True
    assert ("complete", 100) in progress


def test_production_self_test_cancel_returns_cancelled_and_closes_resources(tmp_path):
    cancel = threading.Event()
    cancel.set()

    result = _runner(tmp_path)(_fingerprint(), cancel)

    assert result.failure_stage == "cancelled"
    assert result.probe_ok is False
    assert FakeEncoder.instances[0].closed is True
    assert FakeCapturer.instances[0].closed is True


def test_production_self_test_reports_encoder_completion_failure(tmp_path):
    runner = _runner(tmp_path)
    FakeEncoder.close_ok = False

    result = runner(_fingerprint(), threading.Event())

    assert result.failure_stage == "encoding"
    assert "FFmpeg" in result.failure_reason


def test_production_self_test_rejects_unexpected_probe_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "services.capture_self_test.probe_media",
        lambda *_args, **_kwargs: SimpleNamespace(
            ok=True,
            width=320,
            height=180,
            fps=60.0,
            error="",
        ),
    )

    result = _runner(tmp_path)(_fingerprint(), threading.Event())

    assert result.failure_stage == "ffprobe"
    assert result.probe_ok is False


def test_production_self_test_converts_runtime_exception_to_measurement(tmp_path):
    def fail_factory(**_kwargs):
        raise RuntimeError("capture unavailable")

    runner = ProductionCaptureSelfTestRunner(
        save_dir=tmp_path,
        ffmpeg_path="ffmpeg.exe",
        duration_seconds=0.05,
        capturer_factory=fail_factory,
    )

    result = runner(_fingerprint(), threading.Event())

    assert result.failure_stage == "runtime"
    assert result.failure_reason == "capture unavailable"
