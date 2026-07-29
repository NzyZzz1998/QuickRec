from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from services.pyav_playback_backend import (  # noqa: E402
    PyAVPlaybackBackend,
    _AvAudioDecoder,
    _AvVideoDecoder,
)
from services.timeline_query import ActiveClip, MediaSource, PlaybackPlan  # noqa: E402
from utils.timeline_model import TimelineClip, TimelineTrack  # noqa: E402

VIDEO_FRAME_LIMIT = 1.0
AUDIO_BOUNDARY_LIMIT_MS = 20.0
SYNC_LIMIT_MS = 40.0
DRIFT_LIMIT_MS = 20.0
SEEK_LIMIT_MS = 500.0
RELEASE_LIMIT_MS = 2_000.0


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    value: Any
    limit: Any
    detail: str = ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _process_snapshot() -> dict[str, Any]:
    try:
        import psutil

        process = psutil.Process()
        return {
            "thread_count": process.num_threads(),
            "child_pids": sorted(
                child.pid for child in process.children(recursive=True)
            ),
            "rss_bytes": process.memory_info().rss,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _media_paths(manifest_path: Path) -> dict[str, Path]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = payload.get("files", {})
    required = (
        "h264_aac_30",
        "h264_aac_60",
        "h264_aac_120",
        "h264_silent_30",
        "h264_aac_10min",
        "unicode_space_copy",
    )
    paths: dict[str, Path] = {}
    for key in required:
        path = Path(files[key]["path"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"missing spike media: {path}")
        paths[key] = path
    return paths


def _video_seek_check(path: Path, fps: int) -> tuple[Check, dict[str, Any]]:
    decoder = _AvVideoDecoder(path)
    target_us = 1_000_000 + round(0.51 * 1_000_000 / fps)
    started = time.perf_counter()
    try:
        frame = decoder.frame_at(target_us, force_seek=True)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        start_us = decoder._last_start_us
        end_us = decoder._last_end_us
    finally:
        decoder.release()
    frame_us = 1_000_000 / fps
    start_error_frames = abs(target_us - start_us) / frame_us
    passed = (
        frame.size > 0
        and start_us <= target_us <= end_us
        and start_error_frames <= VIDEO_FRAME_LIMIT
        and elapsed_ms <= SEEK_LIMIT_MS
    )
    metrics = {
        "path": str(path),
        "fps": fps,
        "target_us": target_us,
        "frame_start_us": start_us,
        "frame_end_us": end_us,
        "start_error_frames": start_error_frames,
        "seek_ms": elapsed_ms,
    }
    return (
        Check(
            f"video_seek_{fps}fps",
            passed,
            metrics,
            {"frames": VIDEO_FRAME_LIMIT, "seek_ms": SEEK_LIMIT_MS},
        ),
        metrics,
    )


def _audio_boundary_check(path: Path) -> tuple[Check, dict[str, Any]]:
    decoder = _AvAudioDecoder(path)
    started = time.perf_counter()
    try:
        before = decoder.samples_at(980_000, 960, force_seek=True)
        after = decoder.samples_at(1_000_000, 960, force_seek=True)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
    finally:
        decoder.release()
    unexpected_before = int(np.count_nonzero(before > 0))
    unexpected_after = int(np.count_nonzero(after < 0))
    before_error_ms = unexpected_before / (before.shape[0] * 48_000) * 1000.0
    after_error_ms = unexpected_after / (after.shape[0] * 48_000) * 1000.0
    boundary_error_ms = max(before_error_ms, after_error_ms)
    metrics = {
        "path": str(path),
        "before_mean": float(np.mean(before)),
        "after_mean": float(np.mean(after)),
        "unexpected_before_samples": unexpected_before,
        "unexpected_after_samples": unexpected_after,
        "boundary_error_ms": boundary_error_ms,
        "two_seek_elapsed_ms": elapsed_ms,
    }
    return (
        Check(
            "audio_non_zero_source_boundary",
            boundary_error_ms <= AUDIO_BOUNDARY_LIMIT_MS
            and float(np.mean(before)) < -0.2
            and float(np.mean(after)) > 0.2,
            metrics,
            {"boundary_ms": AUDIO_BOUNDARY_LIMIT_MS},
        ),
        metrics,
    )


def _video_seam_check(path: Path, fps: int) -> tuple[Check, dict[str, Any]]:
    decoder = _AvVideoDecoder(path)
    split_us = 1_000_000
    try:
        left = decoder.frame_at(split_us - 1, force_seek=True)
        left_start_us = decoder._last_start_us
        left_end_us = decoder._last_end_us
        right = decoder.frame_at(split_us, force_seek=True)
        right_start_us = decoder._last_start_us
        right_end_us = decoder._last_end_us
    finally:
        decoder.release()
    frame_us = 1_000_000 / fps
    seam_gap_us = right_start_us - left_end_us
    metrics = {
        "path": str(path),
        "split_us": split_us,
        "left_start_us": left_start_us,
        "left_end_us": left_end_us,
        "right_start_us": right_start_us,
        "right_end_us": right_end_us,
        "seam_gap_us": seam_gap_us,
        "same_frame": bool(np.array_equal(left, right)),
    }
    return (
        Check(
            "continuous_video_seam",
            abs(seam_gap_us) <= frame_us and not np.array_equal(left, right),
            metrics,
            {"absolute_gap_us": frame_us, "same_frame": False},
        ),
        metrics,
    )


class _SpikeAudioOutput:
    def start(self) -> None:
        return

    def pause(self) -> None:
        return

    def write(self, _block: np.ndarray[Any, Any]) -> None:
        return

    def release(self) -> None:
        return


def _active_clip(
    path: Path,
    *,
    clip_id: str,
    track_id: str,
    kind: str,
    source_position_us: int,
) -> ActiveClip:
    clip = TimelineClip(
        clip_id,
        "material-spike",
        track_id,
        0,
        30_000_000,
        0,
        30_000_000,
    )
    track = TimelineTrack(track_id, kind, track_id, 0)
    return ActiveClip(
        clip,
        track,
        MediaSource("material-spike", path, True, {}),
        source_position_us,
    )


def _backend_lifecycle_check(path: Path) -> tuple[Check, dict[str, Any]]:
    video = _active_clip(
        path,
        clip_id="video-spike",
        track_id="video-1",
        kind="video",
        source_position_us=1_017_000,
    )
    audio = _active_clip(
        path,
        clip_id="audio-spike",
        track_id="audio-1",
        kind="audio",
        source_position_us=1_000_000,
    )
    plan = PlaybackPlan(1_017_000, 30_000_000, video, (audio,))
    backend = PyAVPlaybackBackend(
        audio_output_factory=_SpikeAudioOutput,
    )
    before = _process_snapshot()
    prepare_started = time.perf_counter()
    prepared = backend.prepare(plan)
    prepare_ms = (time.perf_counter() - prepare_started) * 1000.0
    seek_started = time.perf_counter()
    sought = backend.seek(plan)
    seek_ms = (time.perf_counter() - seek_started) * 1000.0
    pause_started = time.perf_counter()
    paused = backend.pause()
    pause_ms = (time.perf_counter() - pause_started) * 1000.0
    release_started = time.perf_counter()
    backend.release()
    release_ms = (time.perf_counter() - release_started) * 1000.0
    time.sleep(0.05)
    after = _process_snapshot()
    thread_delta = (
        int(after["thread_count"]) - int(before["thread_count"])
        if "thread_count" in before and "thread_count" in after
        else None
    )
    child_delta = (
        len(after["child_pids"]) - len(before["child_pids"])
        if "child_pids" in before and "child_pids" in after
        else None
    )
    metrics = {
        "prepare_ok": prepared.ok,
        "seek_ok": sought.ok,
        "pause_ok": paused.ok,
        "prepare_ms": prepare_ms,
        "seek_ms": seek_ms,
        "pause_ms": pause_ms,
        "release_ms": release_ms,
        "thread_delta": thread_delta,
        "child_process_delta": child_delta,
    }
    return (
        Check(
            "backend_lifecycle",
            prepared.ok
            and sought.ok
            and paused.ok
            and seek_ms <= SEEK_LIMIT_MS
            and pause_ms <= 200.0
            and release_ms <= RELEASE_LIMIT_MS
            and (thread_delta is None or thread_delta <= 0)
            and (child_delta is None or child_delta <= 0),
            metrics,
            {
                "seek_ms": SEEK_LIMIT_MS,
                "pause_ms": 200.0,
                "release_ms": RELEASE_LIMIT_MS,
                "residual": 0,
            },
        ),
        metrics,
    )


def _stream_sync(path: Path) -> dict[str, Any]:
    import av

    first_video: float | None = None
    end_video: float | None = None
    first_audio: float | None = None
    end_audio: float | None = None
    with av.open(str(path)) as container:
        for frame in container.decode(video=0, audio=0):
            if frame.pts is None or frame.time_base is None:
                continue
            start = float(frame.pts * frame.time_base)
            if isinstance(frame, av.VideoFrame):
                first_video = start if first_video is None else first_video
                duration = (
                    float(frame.duration * frame.time_base)
                    if frame.duration is not None
                    else 0.0
                )
                end_video = start + duration
            elif isinstance(frame, av.AudioFrame):
                first_audio = start if first_audio is None else first_audio
                end_audio = start + frame.samples / frame.sample_rate
    if (
        first_video is None
        or end_video is None
        or first_audio is None
        or end_audio is None
    ):
        raise RuntimeError(f"incomplete A/V timestamps: {path.name}")
    start_offset_ms = abs(first_video - first_audio) * 1000.0
    end_offset_ms = abs(end_video - end_audio) * 1000.0
    return {
        "path": str(path),
        "start_offset_ms": start_offset_ms,
        "end_offset_ms": end_offset_ms,
        "drift_increment_ms": abs(end_offset_ms - start_offset_ms),
    }


def _resource_release_check(path: Path) -> tuple[Check, dict[str, Any]]:
    before = _process_snapshot()
    started = time.perf_counter()
    video = _AvVideoDecoder(path)
    audio = _AvAudioDecoder(path)
    video.frame_at(1_017_000, force_seek=True)
    audio.samples_at(1_000_000, 960, force_seek=True)
    video.release()
    audio.release()
    release_ms = (time.perf_counter() - started) * 1000.0
    time.sleep(0.05)
    after = _process_snapshot()
    thread_delta = (
        int(after["thread_count"]) - int(before["thread_count"])
        if "thread_count" in before and "thread_count" in after
        else None
    )
    child_delta = (
        len(after["child_pids"]) - len(before["child_pids"])
        if "child_pids" in before and "child_pids" in after
        else None
    )
    metrics = {
        "before": before,
        "after": after,
        "release_ms": release_ms,
        "thread_delta": thread_delta,
        "child_process_delta": child_delta,
    }
    passed = (
        release_ms <= RELEASE_LIMIT_MS
        and (thread_delta is None or thread_delta <= 0)
        and (child_delta is None or child_delta <= 0)
    )
    return (
        Check(
            "resource_release",
            passed,
            metrics,
            {"release_ms": RELEASE_LIMIT_MS, "residual": 0},
        ),
        metrics,
    )


def run_spike(manifest_path: Path) -> dict[str, Any]:
    paths = _media_paths(manifest_path)
    checks: list[Check] = []
    metrics: dict[str, Any] = {}
    for key, fps in (
        ("h264_aac_30", 30),
        ("h264_aac_60", 60),
        ("h264_aac_120", 120),
    ):
        check, value = _video_seek_check(paths[key], fps)
        checks.append(check)
        metrics[check.name] = value

    unicode_check, unicode_metrics = _video_seek_check(
        paths["unicode_space_copy"],
        30,
    )
    checks.append(
        Check(
            "unicode_space_path",
            unicode_check.passed,
            unicode_metrics,
            unicode_check.limit,
        )
    )
    metrics["unicode_space_path"] = unicode_metrics

    audio_check, audio_metrics = _audio_boundary_check(paths["h264_aac_30"])
    checks.append(audio_check)
    metrics[audio_check.name] = audio_metrics
    seam_check, seam_metrics = _video_seam_check(paths["h264_aac_30"], 30)
    checks.append(seam_check)
    metrics[seam_check.name] = seam_metrics

    short_sync = _stream_sync(paths["h264_aac_30"])
    long_sync = _stream_sync(paths["h264_aac_10min"])
    checks.extend(
        [
            Check(
                "av_sync_30_seconds",
                short_sync["start_offset_ms"] <= SYNC_LIMIT_MS
                and short_sync["end_offset_ms"] <= SYNC_LIMIT_MS,
                short_sync,
                {"absolute_ms": SYNC_LIMIT_MS},
            ),
            Check(
                "av_sync_10_minutes",
                long_sync["start_offset_ms"] <= SYNC_LIMIT_MS
                and long_sync["end_offset_ms"] <= SYNC_LIMIT_MS
                and long_sync["drift_increment_ms"] <= DRIFT_LIMIT_MS,
                long_sync,
                {
                    "absolute_ms": SYNC_LIMIT_MS,
                    "drift_increment_ms": DRIFT_LIMIT_MS,
                },
            ),
        ]
    )
    metrics["short_sync"] = short_sync
    metrics["long_sync"] = long_sync

    import av

    with av.open(str(paths["h264_silent_30"])) as container:
        audio_streams = [
            stream for stream in container.streams if stream.type == "audio"
        ]
        video_streams = [
            stream for stream in container.streams if stream.type == "video"
        ]
    checks.append(
        Check(
            "silent_h264",
            len(video_streams) == 1 and not audio_streams,
            {
                "video_streams": len(video_streams),
                "audio_streams": len(audio_streams),
            },
            {"video_streams": 1, "audio_streams": 0},
        )
    )

    release_check, release_metrics = _resource_release_check(
        paths["h264_aac_30"]
    )
    checks.append(release_check)
    metrics[release_check.name] = release_metrics
    lifecycle_check, lifecycle_metrics = _backend_lifecycle_check(
        paths["h264_aac_30"]
    )
    checks.append(lifecycle_check)
    metrics[lifecycle_check.name] = lifecycle_metrics
    return {
        "schema_version": 1,
        "generated_at_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "executable": sys.executable,
            "frozen": bool(getattr(sys, "frozen", False)),
            "cwd": str(Path.cwd()),
            "pid": os.getpid(),
            "thread_count": threading.active_count(),
        },
        "manifest": {
            "path": str(manifest_path.resolve()),
            "sha256": _sha256(manifest_path),
        },
        "checks": [asdict(check) for check in checks],
        "metrics": metrics,
        "passed": all(check.passed for check in checks),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="QuickRec v1.9.3 非零源入点播放准确性门禁"
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_spike(Path(args.manifest).resolve())
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
