"""120 FPS 捕获技术门禁的纯指标计算。"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import floor


@dataclass(frozen=True)
class CaptureGateThresholds:
    target_fps: int = 120
    minimum_average_fps: float = 114.0
    minimum_one_second_fps: int = 108
    backlog_limit_ms: float = 500.0
    backlog_limit_seconds: float = 1.0


@dataclass(frozen=True)
class CaptureGateResult:
    passed: bool
    average_fps: float
    minimum_one_second_fps: int
    per_second_fps: tuple[int, ...]
    maximum_backlog_ms: float
    maximum_sustained_backlog_seconds: float
    encoded_frames: int
    expected_frames: int
    dropped_frames: int
    reasons: tuple[str, ...]


def normalize_completion_times(
    completion_times: Sequence[float],
    *,
    target_fps: int,
) -> tuple[float, ...]:
    """将编码完成时间归一到第一帧应完成的时间点。"""
    if not completion_times:
        return ()
    if target_fps <= 0:
        raise ValueError("target_fps must be positive")
    offset = completion_times[0] - (1 / target_fps)
    return tuple(max(value - offset, 0.0) for value in completion_times)


def _count_complete_second_buckets(
    frame_times: Sequence[float],
    duration_seconds: float,
) -> tuple[int, ...]:
    bucket_count = floor(duration_seconds)
    if bucket_count <= 0:
        return (len(frame_times),)
    return tuple(
        sum(second <= timestamp < second + 1.0 for timestamp in frame_times)
        for second in range(bucket_count)
    )


def _maximum_sustained_backlog(
    backlog_samples: Iterable[tuple[float, float]],
    limit_ms: float,
) -> tuple[float, float]:
    ordered = sorted(backlog_samples, key=lambda sample: sample[0])
    maximum_backlog = max((value for _, value in ordered), default=0.0)
    start: float | None = None
    last_above: float | None = None
    maximum_duration = 0.0

    for timestamp, value in ordered:
        if value > limit_ms:
            if start is None:
                start = timestamp
            last_above = timestamp
            continue
        if start is not None and last_above is not None:
            maximum_duration = max(maximum_duration, last_above - start)
        start = None
        last_above = None

    if start is not None and last_above is not None:
        maximum_duration = max(maximum_duration, last_above - start)
    return maximum_backlog, maximum_duration


def evaluate_capture_gate(
    *,
    frame_times: Sequence[float],
    backlog_samples: Iterable[tuple[float, float]],
    duration_seconds: float,
    thresholds: CaptureGateThresholds | None = None,
) -> CaptureGateResult:
    """按 PRD 13.4.3 评估帧率和编码待处理时延。"""
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    thresholds = thresholds or CaptureGateThresholds()
    encoded_frames = len(frame_times)
    expected_frames = round(thresholds.target_fps * duration_seconds)
    average_fps = encoded_frames / duration_seconds
    per_second_fps = _count_complete_second_buckets(frame_times, duration_seconds)
    minimum_one_second_fps = min(per_second_fps, default=0)
    maximum_backlog_ms, maximum_sustained_backlog_seconds = _maximum_sustained_backlog(
        backlog_samples,
        thresholds.backlog_limit_ms,
    )

    reasons: list[str] = []
    if average_fps < thresholds.minimum_average_fps:
        reasons.append("average_fps_below_114")
    if minimum_one_second_fps < thresholds.minimum_one_second_fps:
        reasons.append("one_second_fps_below_108")
    if maximum_sustained_backlog_seconds >= thresholds.backlog_limit_seconds:
        reasons.append("backlog_above_500ms_for_one_second")

    return CaptureGateResult(
        passed=not reasons,
        average_fps=round(average_fps, 3),
        minimum_one_second_fps=minimum_one_second_fps,
        per_second_fps=per_second_fps,
        maximum_backlog_ms=round(maximum_backlog_ms, 3),
        maximum_sustained_backlog_seconds=round(maximum_sustained_backlog_seconds, 3),
        encoded_frames=encoded_frames,
        expected_frames=expected_frames,
        dropped_frames=max(expected_frames - encoded_frames, 0),
        reasons=tuple(reasons),
    )
