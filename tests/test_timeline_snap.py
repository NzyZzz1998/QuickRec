from __future__ import annotations

from time import perf_counter

from services.timeline_snap import (
    TimelineSnapSource,
    snap_timeline_time,
)
from utils.timeline_model import TimelineClip


def _clip(
    clip_id: str,
    start_us: int,
    duration_us: int = 1_000_000,
) -> TimelineClip:
    return TimelineClip(
        clip_id=clip_id,
        material_id="material-1",
        track_id="video-1",
        timeline_start_us=start_us,
        timeline_duration_us=duration_us,
        source_start_us=0,
        source_duration_us=duration_us,
    )


def test_snap_uses_distance_then_stable_source_priority() -> None:
    result = snap_timeline_time(
        1_010_000,
        editing_fps=30,
        pixels_per_second=100,
        playhead_us=1_000_000,
        clips=(_clip("clip-1", 1_000_000),),
    )

    assert result.snapped
    assert result.time_us == 1_000_000
    assert result.source == TimelineSnapSource.PLAYHEAD
    assert result.reference_id == "playhead"


def test_snap_chooses_nearest_before_source_priority() -> None:
    result = snap_timeline_time(
        1_055_000,
        editing_fps=30,
        pixels_per_second=100,
        playhead_us=1_000_000,
        clips=(_clip("clip-1", 1_050_000),),
    )

    assert result.time_us == 1_050_000
    assert result.source == TimelineSnapSource.CLIP_START
    assert result.reference_id == "clip-1"


def test_snap_uses_project_frame_grid_and_pixel_threshold() -> None:
    snapped = snap_timeline_time(
        10_005,
        editing_fps=120,
        pixels_per_second=100,
        playhead_us=2_000_000,
        clips=(),
        threshold_pixels=2,
    )
    outside = snap_timeline_time(
        80_000,
        editing_fps=30,
        pixels_per_second=100,
        playhead_us=0,
        clips=(),
        threshold_pixels=1,
    )

    assert snapped.source == TimelineSnapSource.FRAME
    assert snapped.time_us == 8_333
    assert snapped.tolerance_us == 20_000
    assert not outside.snapped
    assert outside.time_us == 80_000


def test_snap_supports_right_edge_and_stable_edge_tie_break() -> None:
    result = snap_timeline_time(
        2_002_000,
        editing_fps=30,
        pixels_per_second=100,
        playhead_us=5_000_000,
        clips=(
            _clip("clip-b", 1_000_000),
            _clip("clip-a", 2_000_000),
        ),
    )

    assert result.time_us == 2_000_000
    assert result.source == TimelineSnapSource.CLIP_START
    assert result.reference_id == "clip-a"


def test_alt_style_disable_returns_raw_time() -> None:
    result = snap_timeline_time(
        1_001_000,
        editing_fps=60,
        pixels_per_second=100,
        playhead_us=1_000_000,
        clips=(_clip("clip-1", 1_000_000),),
        enabled=False,
    )

    assert not result.snapped
    assert result.time_us == 1_001_000
    assert result.source == TimelineSnapSource.NONE


def test_excluded_clips_do_not_contribute_edges() -> None:
    result = snap_timeline_time(
        1_005_000,
        editing_fps=30,
        pixels_per_second=100,
        playhead_us=3_000_000,
        clips=(_clip("dragged", 1_000_000),),
        excluded_clip_ids=("dragged",),
    )

    assert result.source == TimelineSnapSource.FRAME
    assert result.reference_id == "frame:30"


def test_snap_candidate_performance_with_one_hundred_clips() -> None:
    clips = tuple(
        _clip(f"clip-{index:03d}", index * 2_000_000)
        for index in range(100)
    )
    samples: list[float] = []
    for index in range(200):
        started = perf_counter()
        snap_timeline_time(
            50_000_000 + index * 1_000,
            editing_fps=60,
            pixels_per_second=120,
            playhead_us=50_500_000,
            clips=clips,
        )
        samples.append(perf_counter() - started)
    samples.sort()

    assert samples[int(len(samples) * 0.95)] < 0.033
