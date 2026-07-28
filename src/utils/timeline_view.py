"""时间线视图缩放的共享边界。"""

from __future__ import annotations

DEFAULT_TIMELINE_PIXELS_PER_SECOND = 100.0
MIN_TIMELINE_ZOOM = 0.000_001
MAX_TIMELINE_ZOOM = 8.0


def normalize_timeline_zoom(value: float) -> float:
    """限制缩放为可计算的正数，同时允许长时间线完整适配。"""
    return min(MAX_TIMELINE_ZOOM, max(MIN_TIMELINE_ZOOM, float(value)))
