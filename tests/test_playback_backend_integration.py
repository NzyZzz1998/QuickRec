from __future__ import annotations

import subprocess
from pathlib import Path

import av
import numpy as np
import pytest

from services.pyav_playback_backend import PyAVPlaybackBackend
from services.timeline_query import build_playback_plan
from utils.media_metadata import resolve_ffmpeg_path
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import Timeline, TimelineClip, TimelineTrack


class MemoryAudioOutput:
    def __init__(self) -> None:
        self.blocks: list[np.ndarray] = []
        self.released = False

    def start(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def write(self, block: np.ndarray) -> None:
        self.blocks.append(block.copy())

    def release(self) -> None:
        self.released = True


@pytest.fixture
def playable_timeline(
    tmp_path: Path,
) -> tuple[ProjectFile, Timeline, Path]:
    ffmpeg_path = resolve_ffmpeg_path()
    if not ffmpeg_path:
        pytest.skip("bundled ffmpeg is unavailable")
    source = tmp_path / "中文 空格 真实播放.mp4"
    completed = subprocess.run(
        [
            ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=48000",
            "-t",
            "1.2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        pytest.fail(completed.stderr)

    project = ProjectFile(
        "project-integration",
        "真实播放",
        "",
        "2026-07-28T10:00:00+08:00",
        "2026-07-28T10:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                "material-1",
                str(source),
                source.name,
                "2026-07-28T10:00:00+08:00",
                {},
            )
        ],
    )
    timeline = Timeline(
        "timeline-integration",
        [
            TimelineTrack("video-1", "video", "视频 1", 0),
            TimelineTrack("audio-1", "audio", "音频 1", 0),
        ],
        [
            TimelineClip(
                "video-clip",
                "material-1",
                "video-1",
                0,
                1_000_000,
                0,
                1_000_000,
            ),
            TimelineClip(
                "audio-clip",
                "material-1",
                "audio-1",
                0,
                1_000_000,
                0,
                1_000_000,
                "link-1",
            ),
        ],
    )
    return project, timeline, source


def test_pyav_backend_decodes_unicode_h264_aac_and_seeks(
    playable_timeline: tuple[ProjectFile, Timeline, Path],
) -> None:
    project, timeline, _source = playable_timeline
    output = MemoryAudioOutput()
    backend = PyAVPlaybackBackend(audio_output_factory=lambda: output)

    prepared = backend.prepare(build_playback_plan(project, timeline, 0))
    first = backend.render(build_playback_plan(project, timeline, 33_333))
    sought = backend.seek(build_playback_plan(project, timeline, 600_000))
    after_seek = backend.render(
        build_playback_plan(project, timeline, 633_333)
    )
    backend.release()

    assert av.__version__ == "18.0.0"
    assert prepared.ok
    assert first.ok
    assert first.video_frame.shape == (180, 320, 3)
    assert first.audio_status == "ready"
    assert output.blocks
    assert output.blocks[0].shape[0] == 2
    assert np.isfinite(output.blocks[0]).all()
    assert float(np.max(np.abs(output.blocks[0]))) > 0.01
    assert sought.ok
    assert after_seek.ok
    assert after_seek.video_frame.shape == (180, 320, 3)
    assert output.released


def test_pyav_backend_rejects_corrupt_top_video(tmp_path: Path) -> None:
    source = tmp_path / "损坏 素材.mp4"
    source.write_bytes(b"not a media file")
    project = ProjectFile(
        "project-corrupt",
        "损坏素材",
        "",
        "2026-07-28T10:00:00+08:00",
        "2026-07-28T10:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                "material-1",
                str(source),
                source.name,
                "2026-07-28T10:00:00+08:00",
                {},
            )
        ],
    )
    timeline = Timeline(
        "timeline-corrupt",
        [TimelineTrack("video-1", "video", "视频 1", 0)],
        [
            TimelineClip(
                "video-clip",
                "material-1",
                "video-1",
                0,
                1_000_000,
                0,
                1_000_000,
            )
        ],
    )
    backend = PyAVPlaybackBackend(audio_output_factory=MemoryAudioOutput)

    result = backend.prepare(build_playback_plan(project, timeline, 0))
    backend.release()

    assert not result.ok
    assert not result.fatal
    assert result.video_status == "error"
    assert result.error_kind == "video_decode_failed"
