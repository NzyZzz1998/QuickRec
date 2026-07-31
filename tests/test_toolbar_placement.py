from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ui.toolbar_placement import (  # noqa: E402
    calculate_toolbar_position,
    select_target_screen_index,
)

SCREENS = (
    (0, 0, 1920, 1080),
    (1920, 0, 2560, 1440),
    (-1280, 0, 1280, 1024),
)


def test_fullscreen_uses_capture_output_screen_index() -> None:
    assert (
        select_target_screen_index(
            SCREENS,
            mode="fullscreen",
            output_index=1,
            primary_index=0,
        )
        == 1
    )


@pytest.mark.parametrize("mode", ("region", "window"))
def test_region_and_window_use_largest_intersection(mode: str) -> None:
    target = (1700, 100, 900, 700)

    assert (
        select_target_screen_index(
            SCREENS,
            mode=mode,
            target_rect=target,
            primary_index=0,
        )
        == 1
    )


@pytest.mark.parametrize(
    ("mode", "target_rect", "output_index"),
    (
        ("fullscreen", None, 99),
        ("region", None, None),
        ("window", (9000, 9000, 100, 100), None),
    ),
)
def test_missing_or_unusable_target_metadata_falls_back_to_primary(
    mode: str,
    target_rect: tuple[int, int, int, int] | None,
    output_index: int | None,
) -> None:
    assert (
        select_target_screen_index(
            SCREENS,
            mode=mode,
            target_rect=target_rect,
            output_index=output_index,
            primary_index=2,
        )
        == 2
    )


def test_toolbar_is_centered_in_top_safe_area_and_clamped() -> None:
    assert calculate_toolbar_position(
        (1920, 0, 2560, 1400),
        (500, 48),
    ) == (2950, 140)

    assert calculate_toolbar_position(
        (0, 0, 320, 120),
        (500, 100),
    ) == (8, 12)


@pytest.mark.parametrize(
    ("available_rect", "toolbar_size"),
    (
        ((0, 0, 1920, 1040), (460, 48)),
        ((0, 0, 1536, 832), (368, 38)),
        ((0, 0, 1280, 693), (307, 32)),
    ),
)
def test_toolbar_placement_uses_logical_coordinates_at_common_dpi_scales(
    available_rect: tuple[int, int, int, int],
    toolbar_size: tuple[int, int],
) -> None:
    x, y = calculate_toolbar_position(available_rect, toolbar_size)
    left, top, width, height = available_rect
    toolbar_width, toolbar_height = toolbar_size

    assert abs((x + toolbar_width / 2) - (left + width / 2)) <= 1
    assert top + round(height * 0.08) <= y
    assert y <= top + round(height * 0.12)
    assert x >= left + 8
    assert x + toolbar_width <= left + width - 8
    assert y + toolbar_height <= top + height - 8
