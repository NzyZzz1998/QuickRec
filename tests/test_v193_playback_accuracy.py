from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest

from services.pyav_playback_backend import _AvAudioDecoder, _AvVideoDecoder
from services.timeline_query import build_playback_plan
from utils.media_metadata import resolve_ffmpeg_path
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import Timeline, TimelineClip, TimelineTrack


@pytest.fixture(scope="module")
def seek_boundary_media(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    ffmpeg = resolve_ffmpeg_path()
    if ffmpeg is None:
        pytest.skip("bundled ffmpeg is unavailable")
    root = tmp_path_factory.mktemp("v193 中文 seek samples")
    output = root / "非关键帧 AAC 边界.mp4"
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30:duration=4",
            "-f",
            "lavfi",
            "-i",
            r"aevalsrc=if(lt(t\,1)\,-0.5\,0.5):s=48000:d=4",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-g",
            "60",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert output.exists()
    return output


def test_real_video_seek_returns_frame_covering_target(
    seek_boundary_media: Path,
) -> None:
    decoder = _AvVideoDecoder(seek_boundary_media)
    target_us = 1_017_000

    frame = decoder.frame_at(target_us, force_seek=True)

    assert frame.shape == (180, 320, 3)
    assert decoder._last_start_us <= target_us <= decoder._last_end_us
    assert decoder._last_end_us - decoder._last_start_us <= 33_334
    decoder.release()


def test_real_video_seek_at_frame_boundary_does_not_repeat_previous_frame(
    seek_boundary_media: Path,
) -> None:
    decoder = _AvVideoDecoder(seek_boundary_media)

    left = decoder.frame_at(999_999, force_seek=True).copy()
    left_end_us = decoder._last_end_us
    right = decoder.frame_at(1_000_000, force_seek=True).copy()
    right_start_us = decoder._last_start_us

    assert left_end_us == right_start_us
    assert not np.array_equal(left, right)
    decoder.release()


def test_real_aac_seek_discards_samples_before_target(
    seek_boundary_media: Path,
) -> None:
    decoder = _AvAudioDecoder(seek_boundary_media)

    block = decoder.samples_at(1_000_000, 960, force_seek=True)

    assert float(np.mean(block)) > 0.2
    assert float(np.mean(block < 0)) < 0.1
    decoder.release()


def test_playback_plan_adds_non_zero_source_offset(
    seek_boundary_media: Path,
) -> None:
    project = ProjectFile(
        "project-v193-seek",
        "非零源入点",
        "",
        "2026-07-29T00:00:00+08:00",
        "2026-07-29T00:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                "material-v193",
                str(seek_boundary_media),
                seek_boundary_media.name,
                "2026-07-29T00:00:00+08:00",
                {},
            )
        ],
    )
    timeline = Timeline(
        "timeline-v193",
        [TimelineTrack("video-1", "video", "视频 1", 0)],
        [
            TimelineClip(
                "clip-v193",
                "material-v193",
                "video-1",
                2_000_000,
                1_000_000,
                1_000_000,
                1_000_000,
            )
        ],
    )

    plan = build_playback_plan(project, timeline, 2_250_000)

    assert plan.video is not None
    assert plan.video.source_position_us == 1_250_000
