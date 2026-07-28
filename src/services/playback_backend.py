"""时间线播放后端的稳定契约。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from services.timeline_query import PlaybackPlan


@dataclass(frozen=True)
class BackendCapabilities:
    name: str
    version: str
    max_audio_sources: int = 4
    supports_seek: bool = True


@dataclass(frozen=True)
class BackendFrame:
    ok: bool = True
    video_frame: Any | None = None
    video_status: str = "blank"
    audio_status: str = "silent"
    buffering: bool = False
    fatal: bool = False
    audio_unavailable: bool = False
    error_kind: str = ""
    error: str = ""
    sync_offset_ms: float | None = None


class PlaybackBackend(Protocol):
    capabilities: BackendCapabilities

    def prepare(self, plan: PlaybackPlan) -> BackendFrame: ...

    def play(self) -> BackendFrame: ...

    def pause(self) -> BackendFrame: ...

    def seek(self, plan: PlaybackPlan) -> BackendFrame: ...

    def render(self, plan: PlaybackPlan) -> BackendFrame: ...

    def stop_audio(self) -> None: ...

    def set_muted(self, muted: bool) -> None: ...

    def release(self) -> None: ...
