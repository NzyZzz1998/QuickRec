"""Exact project-frame and integer-microsecond conversions."""

from __future__ import annotations

import re

from services.project_editing_profile import SUPPORTED_EDITING_FPS

MICROSECONDS_PER_SECOND = 1_000_000


def frame_to_microseconds(frame_index: int, fps: int) -> int:
    frame = _nonnegative_int(frame_index, "frame_index")
    rate = _editing_fps(fps)
    return _round_half_up(frame * MICROSECONDS_PER_SECOND, rate)


def microseconds_to_nearest_frame(
    microseconds: int,
    fps: int,
) -> int:
    value = _nonnegative_int(microseconds, "microseconds")
    rate = _editing_fps(fps)
    return _round_half_up(value * rate, MICROSECONDS_PER_SECOND)


def format_frame_time(microseconds: int, fps: int) -> str:
    rate = _editing_fps(fps)
    total_frames = microseconds_to_nearest_frame(microseconds, rate)
    total_seconds, frame = divmod(total_frames, rate)
    hours, remainder = divmod(total_seconds, 3_600)
    minutes, seconds = divmod(remainder, 60)
    frame_width = 3 if rate == 120 else 2
    return (
        f"{hours:02d}:{minutes:02d}:{seconds:02d}:"
        f"{frame:0{frame_width}d}"
    )


def parse_frame_time(value: str, fps: int) -> int:
    rate = _editing_fps(fps)
    frame_width = 3 if rate == 120 else 2
    pattern = re.compile(
        rf"^(\d{{2,}}):([0-5]\d):([0-5]\d):(\d{{{frame_width}}})$"
    )
    matched = pattern.fullmatch(str(value))
    if matched is None:
        raise ValueError("timecode must use HH:MM:SS:FF")
    hours, minutes, seconds, frame = (
        int(part) for part in matched.groups()
    )
    if frame >= rate:
        raise ValueError(f"frame field must be lower than {rate}")
    total_frames = (
        ((hours * 60 + minutes) * 60 + seconds) * rate
        + frame
    )
    return frame_to_microseconds(total_frames, rate)


def parse_total_frame_number(value: str, fps: int) -> int:
    rate = _editing_fps(fps)
    text = str(value)
    if not text or not text.isascii() or not text.isdigit():
        raise ValueError("total frame number must contain digits only")
    return frame_to_microseconds(int(text), rate)


def navigate_frame_position(
    current_us: int,
    frame_delta: int,
    fps: int,
    *,
    maximum_us: int,
) -> int:
    rate = _editing_fps(fps)
    current = _nonnegative_int(current_us, "current_us")
    delta = _integer(frame_delta, "frame_delta")
    maximum = _nonnegative_int(maximum_us, "maximum_us")
    current_frame = microseconds_to_nearest_frame(current, rate)
    last_frame = maximum * rate // MICROSECONDS_PER_SECOND
    target_frame = max(0, min(current_frame + delta, last_frame))
    return frame_to_microseconds(target_frame, rate)


def _round_half_up(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    return quotient + int(remainder * 2 >= denominator)


def _editing_fps(value: object) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value not in SUPPORTED_EDITING_FPS
    ):
        raise ValueError("fps must be 30, 60, or 120")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    parsed = _integer(value, label)
    if parsed < 0:
        raise ValueError(f"{label} must not be negative")
    return parsed
