from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from services.timeline_query import (
    build_playback_plan,
    mix_audio_blocks,
    timeline_duration_us,
)
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import Timeline, TimelineClip, TimelineTrack


def _project(tmp_path: Path) -> ProjectFile:
    materials: list[ProjectMaterialRef] = []
    for index in range(1, 6):
        source = tmp_path / f"中文 素材 {index}.mp4"
        source.write_bytes(b"media")
        materials.append(
            ProjectMaterialRef(
                f"material-{index}",
                str(source),
                source.name,
                "2026-07-28T10:00:00+08:00",
                {"duration_sec": 10.0},
            )
        )
    return ProjectFile(
        "project-1",
        "播放项目",
        "",
        "2026-07-28T10:00:00+08:00",
        "2026-07-28T10:00:00+08:00",
        materials=materials,
    )


def _timeline() -> Timeline:
    tracks = [
        TimelineTrack("video-top", "video", "视频 2", 0),
        TimelineTrack("video-bottom", "video", "视频 1", 1),
        TimelineTrack("audio-1", "audio", "音频 1", 0),
        TimelineTrack("audio-2", "audio", "音频 2", 1),
        TimelineTrack("audio-3", "audio", "音频 3", 2),
        TimelineTrack("audio-4", "audio", "音频 4", 3),
    ]
    clips = [
        TimelineClip(
            "video-bottom-clip",
            "material-1",
            "video-bottom",
            0,
            8_000_000,
            0,
            8_000_000,
        ),
        TimelineClip(
            "video-top-clip",
            "material-2",
            "video-top",
            1_000_000,
            4_000_000,
            500_000,
            4_000_000,
        ),
        *[
            TimelineClip(
                f"audio-clip-{index}",
                f"material-{index + 1}",
                f"audio-{index + 1}",
                0,
                6_000_000,
                0,
                6_000_000,
            )
            for index in range(4)
        ],
    ]
    return Timeline("timeline-1", tracks, clips)


def test_plan_selects_visual_top_video_and_all_active_audio(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    plan = build_playback_plan(project, _timeline(), 2_000_000)

    assert plan.video is not None
    assert plan.video.clip.clip_id == "video-top-clip"
    assert plan.video.source_position_us == 1_500_000
    assert [item.clip.clip_id for item in plan.audio] == [
        "audio-clip-0",
        "audio-clip-1",
        "audio-clip-2",
        "audio-clip-3",
    ]
    assert all(item.source.file_exists for item in plan.audio)


def test_missing_top_video_remains_selected_instead_of_revealing_lower_track(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    top = next(
        item
        for item in project.materials
        if item.material_id == "material-2"
    )
    Path(top.last_known_path).unlink()

    plan = build_playback_plan(project, _timeline(), 2_000_000)

    assert plan.video is not None
    assert plan.video.clip.clip_id == "video-top-clip"
    assert not plan.video.source.file_exists


def test_blank_position_has_no_video_but_keeps_active_audio(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    timeline = _timeline()
    timeline.clips = [
        clip
        for clip in timeline.clips
        if clip.track_id.startswith("audio")
    ]

    plan = build_playback_plan(project, timeline, 2_000_000)

    assert plan.video is None
    assert len(plan.audio) == 4


def test_timeline_duration_uses_last_clip_end() -> None:
    assert timeline_duration_us(_timeline()) == 8_000_000


@pytest.mark.parametrize("source_count", [1, 4, 8])
def test_audio_mix_uses_dynamic_equal_gain_and_safe_limiter(
    source_count: int,
) -> None:
    blocks = [
        np.full((2, 32), 0.9, dtype=np.float32)
        for _ in range(source_count)
    ]

    mixed = mix_audio_blocks(blocks)

    assert mixed.shape == (2, 32)
    assert np.isfinite(mixed).all()
    assert float(np.max(np.abs(mixed))) <= 1.0
    assert np.allclose(mixed, 0.9)
