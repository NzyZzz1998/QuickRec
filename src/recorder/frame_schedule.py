from __future__ import annotations

import math


def due_frame_count(
    *,
    elapsed_seconds: float,
    target_fps: int,
    submitted_frames: int,
) -> int:
    """Return the frames currently due on a fixed-rate output timeline."""
    if elapsed_seconds < 0:
        raise ValueError("elapsed_seconds must not be negative")
    if target_fps <= 0:
        raise ValueError("target_fps must be positive")
    expected_frames = math.floor(elapsed_seconds * target_fps) + 1
    return max(expected_frames - submitted_frames, 0)
