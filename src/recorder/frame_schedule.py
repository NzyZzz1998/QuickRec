from __future__ import annotations

import math


def due_frame_count(
    *,
    elapsed_seconds: float,
    target_fps: int,
    submitted_frames: int,
) -> int:
    """返回当前时刻应补交的帧数，避免轮询速度造成过量编码。"""
    if elapsed_seconds < 0:
        raise ValueError("elapsed_seconds must not be negative")
    if target_fps <= 0:
        raise ValueError("target_fps must be positive")
    expected_frames = math.floor(elapsed_seconds * target_fps) + 1
    return max(expected_frames - submitted_frames, 0)
