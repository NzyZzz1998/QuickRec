from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from services.playback_backend import (
    BackendCapabilities,
    BackendFrame,
)
from services.playback_runtime import PlaybackRuntime, PlaybackState
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import (
    TIMELINE_SCHEMA_VERSION,
    Timeline,
    TimelineClip,
    TimelineTrack,
)


class FakeClock:
    def __init__(self) -> None:
        self.value_us = 0

    def __call__(self) -> int:
        return self.value_us

    def advance(self, value_us: int) -> None:
        self.value_us += int(value_us)


class FakeBackend:
    def __init__(self) -> None:
        self.capabilities = BackendCapabilities("fake", "1.0")
        self.calls: list[tuple[str, int | None]] = []
        self.next_prepare = BackendFrame()
        self.next_play = BackendFrame()
        self.next_pause = BackendFrame()
        self.next_seek = BackendFrame()
        self.next_render = BackendFrame()
        self.release_count = 0
        self.muted = False

    def prepare(self, plan):
        self.calls.append(("prepare", plan.position_us))
        return self.next_prepare

    def play(self):
        self.calls.append(("play", None))
        return self.next_play

    def pause(self):
        self.calls.append(("pause", None))
        return self.next_pause

    def seek(self, plan):
        self.calls.append(("seek", plan.position_us))
        return self.next_seek

    def render(self, plan):
        self.calls.append(("render", plan.position_us))
        return self.next_render

    def stop_audio(self):
        self.calls.append(("stop_audio", None))

    def set_muted(self, muted):
        self.muted = bool(muted)
        self.calls.append(("set_muted", int(bool(muted))))

    def release(self):
        self.release_count += 1
        self.calls.append(("release", None))


def _project_and_timeline(tmp_path: Path) -> tuple[ProjectFile, Timeline]:
    source = tmp_path / "中文 空格.mp4"
    source.write_bytes(b"media")
    project = ProjectFile(
        "project-1",
        "播放项目",
        "",
        "2026-07-28T10:00:00+08:00",
        "2026-07-28T10:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                "material-1",
                str(source),
                source.name,
                "2026-07-28T10:00:00+08:00",
                {"duration_sec": 3.0},
            )
        ],
    )
    timeline = Timeline(
        "timeline-1",
        [
            TimelineTrack("video-1", "video", "视频 1", 0),
            TimelineTrack("audio-1", "audio", "音频 1", 0),
        ],
        [
            TimelineClip(
                "video-clip",
                "material-1",
                "video-1",
                0,
                3_000_000,
                0,
                3_000_000,
            )
        ],
    )
    return project, timeline


def _runtime(tmp_path: Path):
    project, timeline = _project_and_timeline(tmp_path)
    backend = FakeBackend()
    clock = FakeClock()
    runtime = PlaybackRuntime(
        project,
        timeline,
        backend,
        clock_us=clock,
    )
    return runtime, backend, clock, project, timeline


def test_prepare_play_pause_resume_and_end_state(tmp_path: Path) -> None:
    runtime, backend, clock, _project, _timeline = _runtime(tmp_path)

    prepared = runtime.prepare()
    started = runtime.play()
    clock.advance(1_250_000)
    playing = runtime.tick()
    paused = runtime.pause()
    clock.advance(500_000)
    still_paused = runtime.tick()
    resumed = runtime.play()
    clock.advance(2_000_000)
    ended = runtime.tick()

    assert prepared.state == PlaybackState.PAUSED
    assert started.state == PlaybackState.PLAYING
    assert playing.position_us == 1_250_000
    assert paused.state == PlaybackState.PAUSED
    assert still_paused.position_us == 1_250_000
    assert resumed.state == PlaybackState.PLAYING
    assert ended.state == PlaybackState.ENDED
    assert ended.position_us == 3_000_000
    assert ("pause", None) in backend.calls


def test_play_from_end_seeks_to_zero_before_restarting(tmp_path: Path) -> None:
    runtime, backend, clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()
    runtime.play()
    clock.advance(3_100_000)
    assert runtime.tick().state == PlaybackState.ENDED

    restarted = runtime.play()

    assert restarted.state == PlaybackState.PLAYING
    assert restarted.position_us == 0
    assert ("seek", 0) in backend.calls


def test_seek_restores_previous_play_or_pause_state(tmp_path: Path) -> None:
    runtime, backend, _clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()

    paused_seek = runtime.seek(1_000_000)
    runtime.play()
    playing_seek = runtime.seek(2_000_000)

    assert paused_seek.state == PlaybackState.PAUSED
    assert playing_seek.state == PlaybackState.PLAYING
    assert backend.calls.count(("stop_audio", None)) == 2


def test_seek_failure_keeps_last_confirmed_position_and_enters_error(
    tmp_path: Path,
) -> None:
    runtime, backend, _clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()
    runtime.seek(1_000_000)
    backend.next_seek = BackendFrame(
        ok=False,
        fatal=True,
        error_kind="seek_failed",
        error="decode seek failed",
    )

    failed = runtime.seek(2_000_000)

    assert failed.state == PlaybackState.ERROR
    assert failed.position_us == 1_000_000
    assert failed.error_kind == "seek_failed"


def test_nonfatal_top_video_error_keeps_clock_and_error_placeholder(
    tmp_path: Path,
) -> None:
    runtime, backend, clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()
    runtime.play()
    backend.next_render = BackendFrame(
        ok=False,
        fatal=False,
        video_status="error",
        error_kind="decode_failed",
        error="top video failed",
    )
    clock.advance(500_000)

    snapshot = runtime.tick()

    assert snapshot.state == PlaybackState.PLAYING
    assert snapshot.position_us == 500_000
    assert snapshot.frame.video_status == "error"
    assert snapshot.error_kind == "decode_failed"


def test_repeated_degraded_frame_logs_once_until_recovery(
    tmp_path: Path,
    caplog,
) -> None:
    runtime, backend, clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()
    runtime.play()
    degraded = BackendFrame(
        ok=False,
        fatal=False,
        video_status="missing",
        audio_status="error",
        error_kind="audio_decode_failed",
        error="source unavailable",
    )
    backend.next_render = degraded
    caplog.set_level(logging.WARNING, logger="QuickRec")

    for _ in range(3):
        clock.advance(100_000)
        runtime.tick()

    degraded_logs = [
        record
        for record in caplog.records
        if record.getMessage().startswith("timeline playback degraded:")
    ]
    assert len(degraded_logs) == 1

    backend.next_render = BackendFrame()
    clock.advance(100_000)
    runtime.tick()
    backend.next_render = degraded
    clock.advance(100_000)
    runtime.tick()

    degraded_logs = [
        record
        for record in caplog.records
        if record.getMessage().startswith("timeline playback degraded:")
    ]
    assert len(degraded_logs) == 2


def test_audio_unavailable_requires_explicit_mute_or_cancel(
    tmp_path: Path,
) -> None:
    runtime, backend, _clock, _project, _timeline = _runtime(tmp_path)
    backend.next_prepare = BackendFrame(
        ok=False,
        fatal=False,
        audio_unavailable=True,
        error_kind="audio_device_unavailable",
        error="no output device",
    )

    pending = runtime.prepare()
    continued = runtime.continue_without_audio()

    assert pending.state == PlaybackState.PAUSED
    assert pending.needs_audio_decision
    assert continued.muted
    assert not continued.needs_audio_decision
    assert backend.muted


def test_audio_device_loss_when_starting_requires_a_new_decision(
    tmp_path: Path,
) -> None:
    runtime, backend, _clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()
    backend.next_play = BackendFrame(
        ok=False,
        fatal=False,
        audio_unavailable=True,
        error_kind="audio_device_unavailable",
        error="output disappeared",
    )

    pending = runtime.play()

    assert pending.state == PlaybackState.PAUSED
    assert pending.needs_audio_decision
    assert pending.error_kind == "audio_device_unavailable"


def test_audio_device_loss_while_playing_pauses_for_decision(
    tmp_path: Path,
) -> None:
    runtime, backend, clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()
    runtime.play()
    backend.next_render = BackendFrame(
        ok=False,
        fatal=False,
        video_status="ready",
        audio_status="unavailable",
        audio_unavailable=True,
        error_kind="audio_device_unavailable",
        error="output disappeared",
    )
    clock.advance(100_000)

    pending = runtime.tick()

    assert pending.state == PlaybackState.PAUSED
    assert pending.position_us == 100_000
    assert pending.needs_audio_decision


def test_replace_timeline_pauses_and_uses_only_committed_snapshot(
    tmp_path: Path,
) -> None:
    runtime, backend, _clock, project, timeline = _runtime(tmp_path)
    runtime.prepare()
    runtime.play()
    replacement = replace(
        timeline,
        clips=[],
    )

    snapshot = runtime.replace_timeline(project, replacement)

    assert snapshot.state == PlaybackState.PAUSED
    assert snapshot.duration_us == 0
    assert ("pause", None) in backend.calls


def test_release_is_idempotent_and_returns_stopped_state(tmp_path: Path) -> None:
    runtime, backend, _clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()
    runtime.play()

    first = runtime.release()
    second = runtime.release()

    assert first.state == PlaybackState.STOPPED
    assert second.state == PlaybackState.STOPPED
    assert backend.release_count == 1


def test_released_runtime_does_not_reopen_backend(tmp_path: Path) -> None:
    runtime, backend, _clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()
    runtime.release()
    calls_after_release = list(backend.calls)

    snapshot = runtime.play()

    assert snapshot.state == PlaybackState.STOPPED
    assert backend.calls == calls_after_release


def test_empty_timeline_ends_cleanly_with_blank_video(tmp_path: Path) -> None:
    runtime, _backend, _clock, project, timeline = _runtime(tmp_path)
    runtime.replace_timeline(project, replace(timeline, clips=[]))

    runtime.play()
    snapshot = runtime.tick()

    assert snapshot.state == PlaybackState.ENDED
    assert snapshot.position_us == 0
    assert snapshot.frame.video_status == "blank"


def test_prebuffering_over_500_ms_becomes_nonfatal_video_error(
    tmp_path: Path,
) -> None:
    runtime, backend, clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()
    runtime.play()
    backend.next_render = BackendFrame(
        video_status="loading",
        buffering=True,
    )

    loading = runtime.tick()
    clock.advance(500_001)
    timed_out = runtime.tick()

    assert loading.state == PlaybackState.PLAYING
    assert loading.frame.buffering
    assert timed_out.state == PlaybackState.PLAYING
    assert timed_out.frame.video_status == "error"
    assert timed_out.error_kind == "prebuffer_timeout"


def test_diagnostic_summary_has_backend_schema_counts_without_media_path(
    tmp_path: Path,
) -> None:
    runtime, _backend, _clock, _project, _timeline = _runtime(tmp_path)
    runtime.prepare()
    runtime.seek(1_000_000)

    summary = runtime.diagnostic_summary()

    assert summary["backend"] == "fake"
    assert summary["backend_version"] == "1.0"
    assert summary["timeline_schema"] == TIMELINE_SCHEMA_VERSION
    assert summary["video_tracks"] == 1
    assert summary["audio_tracks"] == 1
    assert summary["clips"] == 1
    assert summary["last_seek_target_us"] == 1_000_000
    assert summary["last_seek_source_us"] == 1_000_000
    assert summary["last_seek_result"] == "ok"
    assert summary["resources_released"] is False
    assert str(tmp_path) not in str(summary)

    runtime.release()
    assert runtime.diagnostic_summary()["resources_released"] is True


def test_fatal_prepare_error_can_retry_without_recreating_runtime(
    tmp_path: Path,
) -> None:
    runtime, backend, _clock, _project, _timeline = _runtime(tmp_path)
    backend.next_prepare = BackendFrame(
        ok=False,
        fatal=True,
        error_kind="backend_start_failed",
        error="decoder startup failed",
    )

    failed = runtime.play()
    backend.next_prepare = BackendFrame()
    recovered = runtime.play()

    assert failed.state == PlaybackState.ERROR
    assert recovered.state == PlaybackState.PLAYING
    assert recovered.error_kind == ""
    assert backend.calls.count(("prepare", 0)) == 2
    assert backend.calls.count(("play", None)) == 1


def test_failure_log_keeps_error_kind_but_omits_full_media_path(
    tmp_path: Path,
    caplog,
) -> None:
    runtime, backend, _clock, _project, _timeline = _runtime(tmp_path)
    backend.next_prepare = BackendFrame(
        ok=False,
        fatal=True,
        error_kind="video_decode_failed",
        error=f"cannot decode {tmp_path / '私密目录' / '素材.mp4'}",
    )
    caplog.set_level(logging.INFO, logger="QuickRec")

    runtime.play()

    assert "video_decode_failed" in caplog.text
    assert str(tmp_path) not in caplog.text
