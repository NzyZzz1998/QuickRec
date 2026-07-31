"""Pure frame, clip-edge, and playhead snapping for timeline gestures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from services.timeline_frame_time import (
    frame_to_microseconds,
    microseconds_to_nearest_frame,
)
from utils.timeline_model import TimelineClip


class TimelineSnapSource(StrEnum):
    NONE = "none"
    PLAYHEAD = "playhead"
    CLIP_START = "clip_start"
    CLIP_END = "clip_end"
    FRAME = "frame"


@dataclass(frozen=True)
class TimelineSnapResult:
    raw_time_us: int
    time_us: int
    snapped: bool
    source: TimelineSnapSource
    reference_id: str = ""
    distance_us: int = 0
    tolerance_us: int = 0


@dataclass(frozen=True)
class _SnapTarget:
    time_us: int
    source: TimelineSnapSource
    reference_id: str
    priority: int


def snap_timeline_time(
    raw_time_us: int,
    *,
    editing_fps: int,
    pixels_per_second: float,
    playhead_us: int,
    clips: tuple[TimelineClip, ...] | list[TimelineClip],
    excluded_clip_ids: tuple[str, ...] | list[str] = (),
    enabled: bool = True,
    threshold_pixels: float = 8.0,
) -> TimelineSnapResult:
    raw = max(0, int(raw_time_us))
    pixels = float(pixels_per_second)
    if pixels <= 0:
        raise ValueError("pixels_per_second must be positive")
    threshold = max(0.0, float(threshold_pixels))
    tolerance_us = round(threshold / pixels * 1_000_000)
    if not enabled:
        return TimelineSnapResult(
            raw,
            raw,
            False,
            TimelineSnapSource.NONE,
            tolerance_us=tolerance_us,
        )

    excluded = set(excluded_clip_ids)
    targets = [
        _SnapTarget(
            max(0, int(playhead_us)),
            TimelineSnapSource.PLAYHEAD,
            "playhead",
            0,
        )
    ]
    for clip in clips:
        if clip.clip_id in excluded:
            continue
        targets.extend(
            (
                _SnapTarget(
                    clip.timeline_start_us,
                    TimelineSnapSource.CLIP_START,
                    clip.clip_id,
                    1,
                ),
                _SnapTarget(
                    clip.timeline_end_us,
                    TimelineSnapSource.CLIP_END,
                    clip.clip_id,
                    1,
                ),
            )
        )
    frame_index = microseconds_to_nearest_frame(raw, editing_fps)
    targets.append(
        _SnapTarget(
            frame_to_microseconds(frame_index, editing_fps),
            TimelineSnapSource.FRAME,
            f"frame:{frame_index}",
            2,
        )
    )
    target = min(
        targets,
        key=lambda item: (
            abs(item.time_us - raw),
            item.priority,
            item.time_us,
            item.reference_id,
        ),
    )
    distance = abs(target.time_us - raw)
    if distance > tolerance_us:
        return TimelineSnapResult(
            raw,
            raw,
            False,
            TimelineSnapSource.NONE,
            distance_us=distance,
            tolerance_us=tolerance_us,
        )
    return TimelineSnapResult(
        raw,
        target.time_us,
        True,
        target.source,
        target.reference_id,
        distance,
        tolerance_us,
    )
