from __future__ import annotations

import threading

from services.capture_capability import (
    CapabilityCache,
    DisplayEnvironment,
    EnvironmentFingerprint,
    SelfTestMeasurement,
)
from services.capture_capability_runtime import (
    CaptureCapabilityRuntime,
    resolve_capability_file,
)


def _display() -> DisplayEnvironment:
    return DisplayEnvironment(1, 1920, 1080, 120)


def _fingerprint(**_kwargs) -> EnvironmentFingerprint:
    return EnvironmentFingerprint(
        1,
        1920,
        1080,
        120,
        "E:",
        "cpu",
        "gpu",
        "8",
        "libx264-superfast",
    )


def test_capability_file_respects_isolated_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert resolve_capability_file() == tmp_path / "QuickRec" / "capture-capabilities.json"


def test_runtime_inspect_and_diagnostic_context_without_cache(tmp_path):
    runtime = CaptureCapabilityRuntime(
        save_path=lambda: r"E:\QR Test",
        ffmpeg_path="ffmpeg.exe",
        store_path=tmp_path / "capability.json",
        display_provider=_display,
        fingerprint_builder=_fingerprint,
    )

    inspection = runtime.inspect()
    context = runtime.diagnostic_context()

    assert inspection.readiness.ready is False
    assert context["ready"] is False
    assert context["resolution"] == "1920x1080"
    assert context["refresh_hz"] == 120
    assert context["checked_at"] == ""
    assert context["average_fps"] is None
    assert context["save_drive"] == "E:"


def test_runtime_diagnostic_context_reads_matching_cache(tmp_path):
    path = tmp_path / "capability.json"
    runtime = CaptureCapabilityRuntime(
        save_path=lambda: r"E:\QR Test",
        ffmpeg_path="ffmpeg.exe",
        store_path=path,
        display_provider=_display,
        fingerprint_builder=_fingerprint,
    )
    assert runtime._store.save(
        CapabilityCache(
            passed=True,
            checked_at="2026-07-25T10:00:00+08:00",
            average_fps=119.6,
            minimum_one_second_fps=117,
            fingerprint=_fingerprint(),
        )
    ).ok

    context = runtime.diagnostic_context()

    assert context["ready"] is True
    assert context["checked_at"] == "2026-07-25T10:00:00+08:00"
    assert context["average_fps"] == 119.6
    assert context["minimum_one_second_fps"] == 117


def test_runtime_run_builds_production_runner_and_persists_pass(
    tmp_path,
    monkeypatch,
):
    video = tmp_path / "selftest.mp4"
    video.write_bytes(b"video")
    measurement = SelfTestMeasurement(
        duration_seconds=5.0,
        completion_times=tuple(index / 120 for index in range(1, 601)),
        backlog_samples=((5.0, 5.0),),
        output_path=video,
        probe_ok=True,
    )
    calls = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            calls.update(kwargs)

        def __call__(self, _fingerprint, _cancel_event):
            return measurement

    monkeypatch.setattr(
        "services.capture_capability_runtime.ProductionCaptureSelfTestRunner",
        FakeRunner,
    )
    monkeypatch.setattr(
        "services.capture_capability_runtime.resolve_ffprobe_path",
        lambda: "ffprobe.exe",
    )
    runtime = CaptureCapabilityRuntime(
        save_path=lambda: str(tmp_path),
        ffmpeg_path="ffmpeg.exe",
        store_path=tmp_path / "capability.json",
        display_provider=_display,
        fingerprint_builder=_fingerprint,
    )

    result = runtime.run(threading.Event(), progress=lambda *_args: None)

    assert result.passed is True
    assert calls["save_dir"] == str(tmp_path)
    assert calls["ffmpeg_path"] == "ffmpeg.exe"
    assert calls["ffprobe_path"] == "ffprobe.exe"
    assert runtime._store.load() is not None
    assert video.exists() is False
