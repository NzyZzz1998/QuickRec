from __future__ import annotations

import json
import os
import platform
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Any

from recorder.capture_metrics import CaptureGateResult, evaluate_capture_gate


@dataclass(frozen=True)
class DisplayEnvironment:
    monitor_count: int
    width: int
    height: int
    refresh_hz: int


@dataclass(frozen=True)
class EnvironmentFingerprint:
    monitor_count: int
    width: int
    height: int
    refresh_hz: int
    save_drive: str
    processor: str
    graphics: str
    ffmpeg_version: str
    encoder: str


@dataclass(frozen=True)
class CapabilityCache:
    passed: bool
    checked_at: str
    average_fps: float
    minimum_one_second_fps: int
    fingerprint: EnvironmentFingerprint
    failure_stage: str = ""
    failure_reason: str = ""

    def matches(self, fingerprint: EnvironmentFingerprint) -> bool:
        return self.passed and self.fingerprint == fingerprint


@dataclass(frozen=True)
class CapabilityStoreResult:
    ok: bool
    message: str = ""


@dataclass(frozen=True)
class SelfTestMeasurement:
    duration_seconds: float
    completion_times: tuple[float, ...]
    backlog_samples: tuple[tuple[float, float], ...]
    output_path: Path
    probe_ok: bool
    failure_stage: str = ""
    failure_reason: str = ""


@dataclass(frozen=True)
class SelfTestResult:
    status: str
    passed: bool
    average_fps: float = 0.0
    minimum_one_second_fps: int = 0
    maximum_backlog_ms: float = 0.0
    failure_stage: str = ""
    failure_reason: str = ""


@dataclass(frozen=True)
class CaptureReadiness:
    ready: bool
    reason: str = ""


def display_supports_120(environment: DisplayEnvironment) -> tuple[bool, str]:
    if environment.monitor_count != 1:
        return False, "仅支持单显示器 120 FPS 检测"
    if environment.refresh_hz < 119:
        return False, "当前显示刷新率低于 119Hz"
    return True, ""


def query_display_environment() -> DisplayEnvironment:
    if os.name != "nt":
        return DisplayEnvironment(0, 0, 0, 0)
    import ctypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    monitor_count = int(user32.GetSystemMetrics(80))
    width = int(user32.GetSystemMetrics(0))
    height = int(user32.GetSystemMetrics(1))
    hdc = user32.GetDC(0)
    try:
        refresh_hz = int(gdi32.GetDeviceCaps(hdc, 116)) if hdc else 0
    finally:
        if hdc:
            user32.ReleaseDC(0, hdc)
    return DisplayEnvironment(monitor_count, width, height, refresh_hz)


def read_ffmpeg_version(ffmpeg_path: str) -> str:
    try:
        completed = subprocess.run(
            [ffmpeg_path, "-version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.splitlines()[0].strip() if completed.stdout else ""


def build_environment_fingerprint(
    *,
    display: DisplayEnvironment,
    save_path: str | Path,
    ffmpeg_path: str,
    processor: str | None = None,
    graphics: str | None = None,
) -> EnvironmentFingerprint:
    if graphics is None:
        try:
            import dxcam

            graphics = str(dxcam.device_info()).strip()
        except Exception:
            graphics = ""
    return EnvironmentFingerprint(
        monitor_count=display.monitor_count,
        width=display.width,
        height=display.height,
        refresh_hz=display.refresh_hz,
        save_drive=Path(save_path).drive.upper(),
        processor=(processor if processor is not None else platform.processor()).strip(),
        graphics=graphics.strip(),
        ffmpeg_version=read_ffmpeg_version(ffmpeg_path),
        encoder="libx264-superfast-yuv420p",
    )


class CapabilityCacheStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> CapabilityCache | None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
            fingerprint = EnvironmentFingerprint(**payload["fingerprint"])
            return CapabilityCache(
                passed=bool(payload["passed"]),
                checked_at=str(payload["checked_at"]),
                average_fps=float(payload["average_fps"]),
                minimum_one_second_fps=int(payload["minimum_one_second_fps"]),
                fingerprint=fingerprint,
                failure_stage=str(payload.get("failure_stage", "")),
                failure_reason=str(payload.get("failure_reason", "")),
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def save(self, cache: CapabilityCache) -> CapabilityStoreResult:
        temp_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload: dict[str, Any] = asdict(cache)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temp_path = Path(stream.name)
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
            return CapabilityStoreResult(True)
        except OSError as exc:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            return CapabilityStoreResult(False, str(exc))


class CaptureCapabilityService:
    def __init__(
        self,
        store: CapabilityCacheStore,
        *,
        runner: Callable[[EnvironmentFingerprint, Event], SelfTestMeasurement],
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self._runner = runner
        self._now = now or datetime.now

    def check_readiness(
        self,
        display: DisplayEnvironment,
        fingerprint: EnvironmentFingerprint,
    ) -> CaptureReadiness:
        supported, reason = display_supports_120(display)
        if not supported:
            return CaptureReadiness(False, reason)
        cached = self.store.load()
        if cached is None:
            return CaptureReadiness(False, "尚未完成 120 FPS 能力检测")
        if not cached.matches(fingerprint):
            return CaptureReadiness(False, "录制环境已变化，需要重新检测")
        return CaptureReadiness(True)

    def run(
        self,
        fingerprint: EnvironmentFingerprint,
        cancel_event: Event,
    ) -> SelfTestResult:
        if cancel_event.is_set():
            return SelfTestResult(status="cancelled", passed=False)

        measurement = self._runner(fingerprint, cancel_event)
        try:
            if cancel_event.is_set():
                return SelfTestResult(status="cancelled", passed=False)
            gate = evaluate_capture_gate(
                frame_times=measurement.completion_times,
                backlog_samples=measurement.backlog_samples,
                duration_seconds=measurement.duration_seconds,
            )
            if not measurement.probe_ok:
                return self._failed_result(measurement, gate)
            if not gate.passed:
                return SelfTestResult(
                    status="failed",
                    passed=False,
                    average_fps=gate.average_fps,
                    minimum_one_second_fps=gate.minimum_one_second_fps,
                    maximum_backlog_ms=gate.maximum_backlog_ms,
                    failure_stage="performance",
                    failure_reason=", ".join(gate.reasons),
                )
            cache = CapabilityCache(
                passed=True,
                checked_at=self._now().astimezone().isoformat(timespec="seconds"),
                average_fps=gate.average_fps,
                minimum_one_second_fps=gate.minimum_one_second_fps,
                fingerprint=fingerprint,
            )
            stored = self.store.save(cache)
            if not stored.ok:
                return SelfTestResult(
                    status="failed",
                    passed=False,
                    average_fps=gate.average_fps,
                    minimum_one_second_fps=gate.minimum_one_second_fps,
                    maximum_backlog_ms=gate.maximum_backlog_ms,
                    failure_stage="cache",
                    failure_reason=stored.message,
                )
            return SelfTestResult(
                status="passed",
                passed=True,
                average_fps=gate.average_fps,
                minimum_one_second_fps=gate.minimum_one_second_fps,
                maximum_backlog_ms=gate.maximum_backlog_ms,
            )
        finally:
            measurement.output_path.unlink(missing_ok=True)

    @staticmethod
    def _failed_result(
        measurement: SelfTestMeasurement,
        gate: CaptureGateResult,
    ) -> SelfTestResult:
        return SelfTestResult(
            status="failed",
            passed=False,
            average_fps=gate.average_fps,
            minimum_one_second_fps=gate.minimum_one_second_fps,
            maximum_backlog_ms=gate.maximum_backlog_ms,
            failure_stage=measurement.failure_stage or "ffprobe",
            failure_reason=measurement.failure_reason or "output validation failed",
        )
