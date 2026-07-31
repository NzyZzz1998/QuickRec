"""Pure logical-coordinate rules for recording toolbar placement."""

from __future__ import annotations

from collections.abc import Sequence

RectTuple = tuple[int, int, int, int]
SizeTuple = tuple[int, int]


def select_target_screen_index(
    screen_rects: Sequence[RectTuple],
    *,
    mode: str,
    target_rect: RectTuple | None = None,
    output_index: int | None = None,
    primary_index: int = 0,
) -> int:
    if not screen_rects:
        raise ValueError("screen_rects must not be empty")
    fallback = _valid_index(primary_index, len(screen_rects), default=0)
    if mode == "fullscreen":
        return _valid_index(output_index, len(screen_rects), default=fallback)
    if mode not in {"region", "window"} or target_rect is None:
        return fallback

    areas = [_intersection_area(rect, target_rect) for rect in screen_rects]
    largest = max(areas)
    if largest <= 0:
        return fallback
    return areas.index(largest)


def calculate_toolbar_position(
    available_rect: RectTuple,
    toolbar_size: SizeTuple,
    *,
    vertical_ratio: float = 0.10,
    margin: int = 8,
) -> tuple[int, int]:
    left, top, width, height = available_rect
    toolbar_width, toolbar_height = toolbar_size
    safe_margin = max(0, int(margin))

    centered_x = left + (width - toolbar_width) // 2
    preferred_y = top + round(height * vertical_ratio)
    min_x = left + safe_margin
    min_y = top + safe_margin
    max_x = left + width - toolbar_width - safe_margin
    max_y = top + height - toolbar_height - safe_margin
    return (
        _clamp(centered_x, min_x, max_x),
        _clamp(preferred_y, min_y, max_y),
    )


def _intersection_area(first: RectTuple, second: RectTuple) -> int:
    first_left, first_top, first_width, first_height = first
    second_left, second_top, second_width, second_height = second
    left = max(first_left, second_left)
    top = max(first_top, second_top)
    right = min(first_left + first_width, second_left + second_width)
    bottom = min(first_top + first_height, second_top + second_height)
    return max(0, right - left) * max(0, bottom - top)


def _valid_index(value: int | None, length: int, *, default: int) -> int:
    if value is None or value < 0 or value >= length:
        return default
    return value


def _clamp(value: int, minimum: int, maximum: int) -> int:
    if maximum < minimum:
        return minimum
    return max(minimum, min(value, maximum))
