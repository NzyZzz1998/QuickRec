from __future__ import annotations

import json
import threading
from pathlib import Path

from services.capture_capability import (
    CapabilityCache,
    CapabilityCacheStore,
    CaptureCapabilityService,
    DisplayEnvironment,
    EnvironmentFingerprint,
    SelfTestMeasurement,
    build_environment_fingerprint,
    display_supports_120,
)


def _fingerprint(**overrides) -> EnvironmentFingerprint:
    values = {
        "monitor_count": 1,
        "width": 1920,
        "height": 1080,
        "refresh_hz": 120,
        "save_drive": "E:",
        "processor": "cpu",
        "graphics": "gpu",
        "ffmpeg_version": "8.0.1",
        "encoder": "libx264-superfast",
    }
    values.update(overrides)
    return EnvironmentFingerprint(**values)


def test_display_accepts_single_monitor_at_119hz_boundary():
    supported, reason = display_supports_120(
        DisplayEnvironment(1, 1920, 1080, 119)
    )

    assert supported is True
    assert reason == ""


def test_display_rejects_multiple_monitors_and_low_refresh():
    assert display_supports_120(DisplayEnvironment(2, 1920, 1080, 120)) == (
        False,
        "仅支持单显示器 120 FPS 检测",
    )
    assert display_supports_120(DisplayEnvironment(1, 1920, 1080, 118)) == (
        False,
        "当前显示刷新率低于 119Hz",
    )


def test_capability_cache_round_trip_and_fingerprint_match(tmp_path: Path):
    store = CapabilityCacheStore(tmp_path / "capture-capabilities.json")
    cache = CapabilityCache(
        passed=True,
        checked_at="2026-07-25T00:42:10+08:00",
        average_fps=120.12,
        minimum_one_second_fps=119,
        fingerprint=_fingerprint(),
    )

    assert store.save(cache).ok is True
    loaded = store.load()

    assert loaded == cache
    assert loaded is not None
    assert loaded.matches(_fingerprint()) is True
    assert loaded.matches(_fingerprint(refresh_hz=144)) is False
    assert loaded.matches(_fingerprint(save_drive="D:")) is False


def test_capability_cache_ignores_corrupt_payload(tmp_path: Path):
    path = tmp_path / "capture-capabilities.json"
    path.write_text("{broken", encoding="utf-8")

    assert CapabilityCacheStore(path).load() is None


def test_capability_cache_does_not_store_full_save_path(tmp_path: Path):
    path = tmp_path / "capture-capabilities.json"
    store = CapabilityCacheStore(path)
    store.save(
        CapabilityCache(
            passed=True,
            checked_at="2026-07-25T00:42:10+08:00",
            average_fps=120.0,
            minimum_one_second_fps=119,
            fingerprint=_fingerprint(save_drive="E:"),
        )
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["fingerprint"]["save_drive"] == "E:"
    assert "QRtest" not in path.read_text(encoding="utf-8")


def test_self_test_passes_all_gates_writes_cache_and_cleans_video(tmp_path: Path):
    video = tmp_path / "self-test.mp4"
    video.write_bytes(b"video")
    measurement = SelfTestMeasurement(
        duration_seconds=5.0,
        completion_times=tuple(index / 120 for index in range(1, 601)),
        backlog_samples=((5.0, 8.0),),
        output_path=video,
        probe_ok=True,
    )
    store = CapabilityCacheStore(tmp_path / "capture-capabilities.json")
    service = CaptureCapabilityService(store, runner=lambda *_args: measurement)

    result = service.run(_fingerprint(), threading.Event())

    assert result.passed is True
    assert result.status == "passed"
    assert store.load() is not None
    assert video.exists() is False


def test_self_test_failure_does_not_replace_valid_cache(tmp_path: Path):
    store = CapabilityCacheStore(tmp_path / "capture-capabilities.json")
    valid = CapabilityCache(
        passed=True,
        checked_at="2026-07-25T00:42:10+08:00",
        average_fps=120.0,
        minimum_one_second_fps=120,
        fingerprint=_fingerprint(),
    )
    assert store.save(valid).ok
    measurement = SelfTestMeasurement(
        duration_seconds=5.0,
        completion_times=tuple(index / 100 for index in range(1, 501)),
        backlog_samples=(),
        output_path=tmp_path / "failed.mp4",
        probe_ok=False,
        failure_stage="ffprobe",
        failure_reason="output is not parseable",
    )
    service = CaptureCapabilityService(store, runner=lambda *_args: measurement)

    result = service.run(_fingerprint(), threading.Event())

    assert result.passed is False
    assert result.status == "failed"
    assert result.failure_stage == "ffprobe"
    assert store.load() == valid


def test_self_test_cancelled_does_not_write_cache(tmp_path: Path):
    cancel = threading.Event()
    cancel.set()
    store = CapabilityCacheStore(tmp_path / "capture-capabilities.json")
    runner_called = False

    def runner(*_args):
        nonlocal runner_called
        runner_called = True
        raise AssertionError("runner should not be called")

    result = CaptureCapabilityService(store, runner=runner).run(
        _fingerprint(),
        cancel,
    )

    assert result.status == "cancelled"
    assert runner_called is False
    assert store.load() is None


def test_readiness_requires_matching_passed_cache(tmp_path: Path):
    store = CapabilityCacheStore(tmp_path / "capture-capabilities.json")
    service = CaptureCapabilityService(
        store,
        runner=lambda *_args: (_ for _ in ()).throw(AssertionError()),
    )
    display = DisplayEnvironment(1, 1920, 1080, 120)

    assert service.check_readiness(display, _fingerprint()).ready is False
    assert store.save(
        CapabilityCache(
            passed=True,
            checked_at="2026-07-25T00:42:10+08:00",
            average_fps=120.0,
            minimum_one_second_fps=119,
            fingerprint=_fingerprint(),
        )
    ).ok
    assert service.check_readiness(display, _fingerprint()).ready is True
    changed = service.check_readiness(display, _fingerprint(graphics="new gpu"))
    assert changed.ready is False
    assert "重新检测" in changed.reason


def test_fingerprint_keeps_drive_but_not_full_save_path(monkeypatch):
    monkeypatch.setattr(
        "services.capture_capability.read_ffmpeg_version",
        lambda _path: "ffmpeg 8.0.1",
    )
    fingerprint = build_environment_fingerprint(
        display=DisplayEnvironment(1, 1920, 1080, 120),
        save_path=r"E:\Private Name\Videos",
        ffmpeg_path="ffmpeg.exe",
        processor="cpu",
        graphics="gpu",
    )

    assert fingerprint.save_drive == "E:"
    assert "Private" not in json.dumps(fingerprint.__dict__)
