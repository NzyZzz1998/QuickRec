from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from services.capture_capability import (
    CapabilityCacheStore,
    CaptureCapabilityService,
    CaptureReadiness,
    DisplayEnvironment,
    EnvironmentFingerprint,
    SelfTestResult,
    build_environment_fingerprint,
    query_display_environment,
)
from services.capture_self_test import ProductionCaptureSelfTestRunner
from utils.media_metadata import resolve_ffprobe_path


@dataclass(frozen=True)
class CapabilityInspection:
    display: DisplayEnvironment
    fingerprint: EnvironmentFingerprint
    readiness: CaptureReadiness


def resolve_capability_file() -> Path:
    appdata = os.getenv("APPDATA")
    root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return root / "QuickRec" / "capture-capabilities.json"


class CaptureCapabilityRuntime:
    def __init__(
        self,
        *,
        save_path: Callable[[], str],
        ffmpeg_path: str,
        store_path: Path | None = None,
        display_provider: Callable[[], DisplayEnvironment] = query_display_environment,
        fingerprint_builder: Callable[..., EnvironmentFingerprint] = build_environment_fingerprint,
    ) -> None:
        self._save_path = save_path
        self._ffmpeg_path = ffmpeg_path
        self._store = CapabilityCacheStore(store_path or resolve_capability_file())
        self._display_provider = display_provider
        self._fingerprint_builder = fingerprint_builder

    def inspect(self) -> CapabilityInspection:
        display = self._display_provider()
        fingerprint = self._fingerprint_builder(
            display=display,
            save_path=self._save_path(),
            ffmpeg_path=self._ffmpeg_path,
        )
        service = CaptureCapabilityService(
            self._store,
            runner=lambda *_args: (_ for _ in ()).throw(
                RuntimeError("self-test runner is not configured")
            ),
        )
        return CapabilityInspection(
            display=display,
            fingerprint=fingerprint,
            readiness=service.check_readiness(display, fingerprint),
        )

    def run(
        self,
        cancel_event: Event,
        *,
        progress: Callable[[str, int], None] | None = None,
    ) -> SelfTestResult:
        inspection = self.inspect()
        runner = ProductionCaptureSelfTestRunner(
            save_dir=self._save_path(),
            ffmpeg_path=self._ffmpeg_path,
            ffprobe_path=resolve_ffprobe_path(),
            progress=progress,
        )
        return CaptureCapabilityService(
            self._store,
            runner=runner,
        ).run(inspection.fingerprint, cancel_event)

    def diagnostic_context(self) -> dict[str, object]:
        inspection = self.inspect()
        cached = self._store.load()
        return {
            "ready": inspection.readiness.ready,
            "reason": inspection.readiness.reason,
            "monitor_count": inspection.display.monitor_count,
            "resolution": f"{inspection.display.width}x{inspection.display.height}",
            "refresh_hz": inspection.display.refresh_hz,
            "checked_at": cached.checked_at if cached else "",
            "average_fps": cached.average_fps if cached else None,
            "minimum_one_second_fps": (
                cached.minimum_one_second_fps if cached else None
            ),
            "save_drive": inspection.fingerprint.save_drive,
            "encoder": inspection.fingerprint.encoder,
        }
