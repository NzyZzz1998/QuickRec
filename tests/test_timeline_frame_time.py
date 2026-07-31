from __future__ import annotations

import pytest

from services.timeline_frame_time import (
    format_frame_time,
    frame_to_microseconds,
    microseconds_to_nearest_frame,
    navigate_frame_position,
    parse_frame_time,
    parse_total_frame_number,
)


@pytest.mark.parametrize("fps", (30, 60, 120))
def test_frame_and_microsecond_round_trip_has_no_accumulated_drift(
    fps: int,
) -> None:
    frame = fps * 60 * 30 - 1

    for _ in range(100):
        microseconds = frame_to_microseconds(frame, fps)
        frame = microseconds_to_nearest_frame(microseconds, fps)

    assert frame == fps * 60 * 30 - 1


@pytest.mark.parametrize(
    ("fps", "frame", "expected_us"),
    (
        (30, 1, 33_333),
        (60, 1, 16_667),
        (120, 1, 8_333),
        (30, 45, 1_500_000),
        (120, 216_000, 1_800_000_000),
    ),
)
def test_frame_to_microseconds_uses_half_up_rational_rounding(
    fps: int,
    frame: int,
    expected_us: int,
) -> None:
    assert frame_to_microseconds(frame, fps) == expected_us


@pytest.mark.parametrize(
    ("fps", "microseconds", "expected_frame"),
    (
        (30, 16_666, 0),
        (30, 16_667, 1),
        (60, 8_333, 0),
        (60, 8_334, 1),
        (120, 4_166, 0),
        (120, 4_167, 1),
    ),
)
def test_microseconds_to_frame_uses_nearest_half_up(
    fps: int,
    microseconds: int,
    expected_frame: int,
) -> None:
    assert (
        microseconds_to_nearest_frame(microseconds, fps)
        == expected_frame
    )


@pytest.mark.parametrize(
    ("fps", "microseconds", "expected"),
    (
        (30, 3_661_500_000, "01:01:01:15"),
        (60, 3_661_500_000, "01:01:01:30"),
        (120, 3_661_500_000, "01:01:01:060"),
        (120, 25 * 3_600_000_000, "25:00:00:000"),
    ),
)
def test_format_frame_time_uses_stable_frame_width(
    fps: int,
    microseconds: int,
    expected: str,
) -> None:
    assert format_frame_time(microseconds, fps) == expected


@pytest.mark.parametrize("fps", (30, 60, 120))
def test_parse_frame_time_round_trips_formatted_value(fps: int) -> None:
    source = 3_661_500_000
    text = format_frame_time(source, fps)

    parsed = parse_frame_time(text, fps)

    assert parsed == frame_to_microseconds(
        microseconds_to_nearest_frame(source, fps),
        fps,
    )


@pytest.mark.parametrize(
    ("text", "fps"),
    (
        ("00:00:00:30", 30),
        ("00:00:00:60", 60),
        ("00:00:00:120", 120),
        ("00:60:00:00", 30),
        ("00:00:60:00", 30),
        ("-1:00:00:00", 30),
        ("00:00:00:0", 30),
        ("00:00:00:00.5", 30),
    ),
)
def test_parse_frame_time_rejects_invalid_or_out_of_range_values(
    text: str,
    fps: int,
) -> None:
    with pytest.raises(ValueError):
        parse_frame_time(text, fps)


@pytest.mark.parametrize("value", (True, 30.0, "30", 24, 90, 240))
def test_frame_time_rejects_invalid_fps(value: object) -> None:
    with pytest.raises(ValueError):
        frame_to_microseconds(1, value)


def test_navigation_clamps_to_zero_and_last_frame_not_after_timeline_end() -> None:
    end_us = 1_050_000

    assert navigate_frame_position(0, -1, 30, maximum_us=end_us) == 0
    assert (
        navigate_frame_position(
            1_000_000,
            30,
            30,
            maximum_us=end_us,
        )
        == 1_033_333
    )


def test_one_second_navigation_uses_exact_fps_frame_count() -> None:
    current = frame_to_microseconds(17, 120)

    target = navigate_frame_position(
        current,
        120,
        120,
        maximum_us=10_000_000,
    )

    assert microseconds_to_nearest_frame(target, 120) == 137


@pytest.mark.parametrize(
    ("value", "fps", "expected_us"),
    (
        ("0", 30, 0),
        ("30", 30, 1_000_000),
        ("120", 120, 1_000_000),
        ("216000", 120, 1_800_000_000),
    ),
)
def test_parse_total_frame_number_is_strict_and_exact(
    value: str,
    fps: int,
    expected_us: int,
) -> None:
    assert parse_total_frame_number(value, fps) == expected_us


@pytest.mark.parametrize("value", ("", "-1", "+1", "1.0", " 1", "1 "))
def test_parse_total_frame_number_rejects_non_digit_input(value: str) -> None:
    with pytest.raises(ValueError):
        parse_total_frame_number(value, 30)
