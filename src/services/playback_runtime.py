"""由单调时钟驱动的时间线播放状态机。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from services.playback_backend import BackendFrame, PlaybackBackend
from services.timeline_query import PlaybackPlan, build_playback_plan
from utils.project_store import ProjectFile
from utils.timeline_model import Timeline

logger = logging.getLogger("QuickRec")


class PlaybackState(StrEnum):
    STOPPED = "stopped"
    PREPARING = "preparing"
    PAUSED = "paused"
    PLAYING = "playing"
    SEEKING = "seeking"
    ENDED = "ended"
    ERROR = "error"
    RELEASING = "releasing"


@dataclass(frozen=True)
class PlaybackSnapshot:
    state: PlaybackState
    position_us: int
    duration_us: int
    plan: PlaybackPlan
    frame: BackendFrame
    error_kind: str = ""
    error: str = ""
    muted: bool = False
    needs_audio_decision: bool = False


class PlaybackRuntime:
    """协调播放时钟、查询计划和后端资源，不承担媒体解码。"""

    def __init__(
        self,
        project: ProjectFile,
        timeline: Timeline,
        backend: PlaybackBackend,
        *,
        clock_us: Callable[[], int] | None = None,
    ) -> None:
        self._project = project
        self._timeline = timeline
        self._backend = backend
        self._clock_us = clock_us or _monotonic_us
        self._state = PlaybackState.STOPPED
        self._position_us = 0
        self._anchor_clock_us = self._clock_us()
        self._anchor_position_us = 0
        self._frame = BackendFrame()
        self._error_kind = ""
        self._error = ""
        self._muted = False
        self._needs_audio_decision = False
        self._buffering_started_us: int | None = None
        self._last_degraded_signature: tuple[str, str, str] | None = None
        self._last_seek_target_us: int | None = None
        self._last_seek_source_us: int | None = None
        self._last_seek_elapsed_ms: float | None = None
        self._last_seek_result = "not_run"
        self._released = False

    def prepare(self) -> PlaybackSnapshot:
        if self._released:
            return self.snapshot()
        self._state = PlaybackState.PREPARING
        self._buffering_started_us = None
        self._clear_error()
        plan = self._plan()
        logger.info(
            "timeline playback prepare: backend=%s version=%s "
            "position_us=%d video=%s audio_sources=%d",
            self._backend.capabilities.name,
            self._backend.capabilities.version,
            plan.position_us,
            plan.video.clip.clip_id if plan.video is not None else "blank",
            len(plan.audio),
        )
        result = self._backend.prepare(plan)
        self._frame = result
        if result.fatal:
            return self._fail(result)
        self._state = PlaybackState.PAUSED
        self._apply_nonfatal_result(result)
        self._needs_audio_decision = result.audio_unavailable
        return self.snapshot()

    def play(self) -> PlaybackSnapshot:
        if self._released:
            return self.snapshot()
        if self._state == PlaybackState.ENDED:
            seek_result = self.seek(0)
            if seek_result.state == PlaybackState.ERROR:
                return seek_result
        elif self._state in {PlaybackState.STOPPED, PlaybackState.ERROR}:
            prepared = self.prepare()
            if prepared.state == PlaybackState.ERROR:
                return prepared
        if self._needs_audio_decision:
            return self.snapshot()

        result = self._backend.play()
        self._frame = result
        if not result.ok and result.fatal:
            return self._fail(result)
        self._apply_nonfatal_result(result)
        if result.audio_unavailable:
            self._needs_audio_decision = True
            self._state = PlaybackState.PAUSED
            return self.snapshot()
        self._anchor_clock_us = self._clock_us()
        self._anchor_position_us = self._position_us
        self._state = PlaybackState.PLAYING
        logger.info(
            "timeline playback started: position_us=%d muted=%s",
            self._position_us,
            self._muted,
        )
        return self.snapshot()

    def pause(self) -> PlaybackSnapshot:
        if self._released:
            return self.snapshot()
        if self._state != PlaybackState.PLAYING:
            return self.snapshot()
        self._update_position_from_clock()
        result = self._backend.pause()
        self._frame = result
        if not result.ok and result.fatal:
            return self._fail(result)
        self._apply_nonfatal_result(result)
        self._buffering_started_us = None
        self._state = PlaybackState.PAUSED
        logger.info(
            "timeline playback paused: position_us=%d",
            self._position_us,
        )
        return self.snapshot()

    def tick(self) -> PlaybackSnapshot:
        if self._released:
            return self.snapshot()
        if self._state != PlaybackState.PLAYING:
            return self.snapshot()
        self._update_position_from_clock()
        if self._position_us >= self._duration_us:
            self._position_us = self._duration_us
            self._backend.pause()
            self._backend.stop_audio()
            self._state = PlaybackState.ENDED
            logger.info(
                "timeline playback ended: position_us=%d",
                self._position_us,
            )
            return self.snapshot()

        result = self._backend.render(self._plan())
        result = self._apply_prebuffer_limit(result)
        self._frame = result
        if not result.ok and result.fatal:
            return self._fail(result)
        self._apply_nonfatal_result(result)
        if result.audio_unavailable:
            self._backend.stop_audio()
            self._needs_audio_decision = True
            self._state = PlaybackState.PAUSED
        return self.snapshot()

    def seek(self, position_us: int) -> PlaybackSnapshot:
        if self._released:
            return self.snapshot()
        previous_state = self._state
        previous_position = self._position_us
        target = max(0, min(int(position_us), self._duration_us))
        started_ns = time.monotonic_ns()
        was_playing = previous_state == PlaybackState.PLAYING
        self._backend.stop_audio()
        self._buffering_started_us = None
        self._state = PlaybackState.SEEKING
        result = self._backend.seek(self._plan(target))
        elapsed_ms = (time.monotonic_ns() - started_ns) / 1_000_000
        self._last_seek_target_us = target
        seek_plan = self._plan(target)
        self._last_seek_source_us = (
            seek_plan.video.source_position_us
            if seek_plan.video is not None
            else None
        )
        self._last_seek_elapsed_ms = round(elapsed_ms, 3)
        self._last_seek_result = "failed" if not result.ok else "ok"
        self._frame = result
        if not result.ok:
            self._position_us = previous_position
            logger.warning(
                "timeline playback seek failed: from_us=%d target_us=%d "
                "elapsed_ms=%.3f kind=%s",
                previous_position,
                target,
                elapsed_ms,
                result.error_kind,
            )
            return self._fail(result)

        self._position_us = target
        self._anchor_position_us = target
        self._anchor_clock_us = self._clock_us()
        self._clear_error()
        self._apply_nonfatal_result(result)
        self._state = (
            PlaybackState.PLAYING if was_playing else PlaybackState.PAUSED
        )
        logger.info(
            "timeline playback seek complete: from_us=%d target_us=%d "
            "elapsed_ms=%.3f state=%s",
            previous_position,
            target,
            elapsed_ms,
            self._state.value,
        )
        return self.snapshot()

    def continue_without_audio(self) -> PlaybackSnapshot:
        if not self._needs_audio_decision:
            return self.snapshot()
        self._backend.set_muted(True)
        self._muted = True
        self._needs_audio_decision = False
        self._error_kind = ""
        self._error = ""
        logger.warning("timeline playback continuing without audio")
        return self.snapshot()

    def cancel_audio_start(self) -> PlaybackSnapshot:
        if self._needs_audio_decision:
            self._backend.stop_audio()
            self._needs_audio_decision = False
            self._state = PlaybackState.STOPPED
        return self.snapshot()

    def replace_timeline(
        self,
        project: ProjectFile,
        timeline: Timeline,
    ) -> PlaybackSnapshot:
        if self._released:
            return self.snapshot()
        if self._state == PlaybackState.PLAYING:
            self.pause()
        self._project = project
        self._timeline = timeline
        self._position_us = min(self._position_us, self._duration_us)
        self._anchor_position_us = self._position_us
        self._anchor_clock_us = self._clock_us()
        self._buffering_started_us = None
        result = self._backend.prepare(self._plan())
        self._frame = result
        if result.fatal:
            return self._fail(result)
        self._clear_error()
        self._apply_nonfatal_result(result)
        self._state = PlaybackState.PAUSED
        return self.snapshot()

    def release(self) -> PlaybackSnapshot:
        if self._released:
            return self.snapshot()
        started_ns = time.monotonic_ns()
        self._state = PlaybackState.RELEASING
        self._backend.stop_audio()
        self._backend.release()
        self._released = True
        self._state = PlaybackState.STOPPED
        logger.info(
            "timeline playback released: backend=%s elapsed_ms=%.3f result=ok",
            self._backend.capabilities.name,
            (time.monotonic_ns() - started_ns) / 1_000_000,
        )
        return self.snapshot()

    def diagnostic_summary(self) -> dict[str, object]:
        """返回不包含素材完整路径的播放诊断摘要。"""
        plan = self._plan()
        return {
            "backend": self._backend.capabilities.name,
            "backend_version": self._backend.capabilities.version,
            "state": self._state.value,
            "timeline_schema": self._timeline.schema_version,
            "video_tracks": sum(
                track.kind == "video" for track in self._timeline.tracks
            ),
            "audio_tracks": sum(
                track.kind == "audio" for track in self._timeline.tracks
            ),
            "clips": len(self._timeline.clips),
            "position_us": self._position_us,
            "duration_us": plan.duration_us,
            "active_video": (
                plan.video.clip.clip_id if plan.video is not None else "none"
            ),
            "active_audio_sources": len(plan.audio),
            "muted": self._muted,
            "sync_offset_ms": self._frame.sync_offset_ms,
            "last_error_kind": self._error_kind,
            "last_seek_target_us": (
                self._last_seek_target_us
                if self._last_seek_target_us is not None
                else "none"
            ),
            "last_seek_source_us": (
                self._last_seek_source_us
                if self._last_seek_source_us is not None
                else "none"
            ),
            "last_seek_elapsed_ms": (
                self._last_seek_elapsed_ms
                if self._last_seek_elapsed_ms is not None
                else "none"
            ),
            "last_seek_result": self._last_seek_result,
            "resources_released": self._released,
        }

    def snapshot(self) -> PlaybackSnapshot:
        return PlaybackSnapshot(
            self._state,
            self._position_us,
            self._duration_us,
            self._plan(),
            self._frame,
            self._error_kind,
            self._error,
            self._muted,
            self._needs_audio_decision,
        )

    @property
    def _duration_us(self) -> int:
        return self._plan().duration_us

    def _plan(self, position_us: int | None = None) -> PlaybackPlan:
        return build_playback_plan(
            self._project,
            self._timeline,
            self._position_us if position_us is None else position_us,
        )

    def _update_position_from_clock(self) -> None:
        elapsed = max(0, self._clock_us() - self._anchor_clock_us)
        self._position_us = min(
            self._duration_us,
            self._anchor_position_us + elapsed,
        )

    def _fail(self, result: BackendFrame) -> PlaybackSnapshot:
        self._state = PlaybackState.ERROR
        self._error_kind = result.error_kind
        self._error = result.error
        logger.error(
            "timeline playback failed: state=%s kind=%s",
            self._state.value,
            self._error_kind,
        )
        return self.snapshot()

    def _apply_nonfatal_result(self, result: BackendFrame) -> None:
        if result.ok:
            self._last_degraded_signature = None
            self._clear_error()
            return
        self._error_kind = result.error_kind
        self._error = result.error
        signature = (
            result.error_kind,
            result.video_status,
            result.audio_status,
        )
        if signature != self._last_degraded_signature:
            logger.warning(
                "timeline playback degraded: kind=%s video=%s audio=%s",
                result.error_kind,
                result.video_status,
                result.audio_status,
            )
            self._last_degraded_signature = signature

    def _apply_prebuffer_limit(self, result: BackendFrame) -> BackendFrame:
        if not result.buffering:
            self._buffering_started_us = None
            return result
        now_us = self._clock_us()
        if self._buffering_started_us is None:
            self._buffering_started_us = now_us
            return result
        if now_us - self._buffering_started_us <= 500_000:
            return result
        self._buffering_started_us = None
        return BackendFrame(
            ok=False,
            video_frame=result.video_frame,
            video_status="error",
            audio_status=result.audio_status,
            fatal=False,
            audio_unavailable=result.audio_unavailable,
            error_kind="prebuffer_timeout",
            error="video prebuffer exceeded 500 ms",
            sync_offset_ms=result.sync_offset_ms,
        )

    def _clear_error(self) -> None:
        self._error_kind = ""
        self._error = ""


def _monotonic_us() -> int:
    return time.monotonic_ns() // 1_000
