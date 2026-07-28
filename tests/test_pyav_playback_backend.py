from __future__ import annotations

from pathlib import Path

import numpy as np

from services.pyav_playback_backend import PyAVPlaybackBackend
from services.timeline_query import build_playback_plan
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import Timeline, TimelineClip, TimelineTrack


class FakeVideoDecoder:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.calls: list[tuple[int, bool]] = []
        self.release_count = 0

    def frame_at(self, position_us: int, *, force_seek: bool = False):
        self.calls.append((position_us, force_seek))
        return np.full((4, 6, 3), 127, dtype=np.uint8)

    def release(self) -> None:
        self.release_count += 1


class FakeAudioDecoder:
    def __init__(self, path: Path, value: float) -> None:
        self.path = path
        self.value = value
        self.calls: list[tuple[int, int, bool]] = []
        self.release_count = 0

    def samples_at(
        self,
        position_us: int,
        sample_count: int,
        *,
        force_seek: bool = False,
    ):
        self.calls.append((position_us, sample_count, force_seek))
        return np.full((2, sample_count), self.value, dtype=np.float32)

    def release(self) -> None:
        self.release_count += 1


class FailingAudioDecoder(FakeAudioDecoder):
    def samples_at(
        self,
        position_us: int,
        sample_count: int,
        *,
        force_seek: bool = False,
    ):
        self.calls.append((position_us, sample_count, force_seek))
        raise ValueError("corrupt audio stream")


class FakeAudioOutput:
    def __init__(self, *, unavailable: bool = False) -> None:
        if unavailable:
            raise OSError("no output device")
        self.started = 0
        self.paused = 0
        self.writes: list[np.ndarray] = []
        self.release_count = 0

    def start(self) -> None:
        self.started += 1

    def pause(self) -> None:
        self.paused += 1

    def write(self, block: np.ndarray) -> None:
        self.writes.append(block.copy())

    def release(self) -> None:
        self.release_count += 1


def _project_and_timeline(tmp_path: Path) -> tuple[ProjectFile, Timeline]:
    materials: list[ProjectMaterialRef] = []
    for index in range(1, 6):
        path = tmp_path / f"中文 素材 {index}.mp4"
        path.write_bytes(b"media")
        materials.append(
            ProjectMaterialRef(
                f"material-{index}",
                str(path),
                path.name,
                "2026-07-28T10:00:00+08:00",
                {},
            )
        )
    project = ProjectFile(
        "project-1",
        "播放项目",
        "",
        "2026-07-28T10:00:00+08:00",
        "2026-07-28T10:00:00+08:00",
        materials=materials,
    )
    timeline = Timeline(
        "timeline-1",
        [
            TimelineTrack("video-top", "video", "视频 2", 0),
            TimelineTrack("video-bottom", "video", "视频 1", 1),
            *[
                TimelineTrack(
                    f"audio-{index}",
                    "audio",
                    f"音频 {index}",
                    index - 1,
                )
                for index in range(1, 5)
            ],
        ],
        [
            TimelineClip(
                "video-top-clip",
                "material-1",
                "video-top",
                0,
                5_000_000,
                0,
                5_000_000,
            ),
            TimelineClip(
                "video-bottom-clip",
                "material-2",
                "video-bottom",
                0,
                5_000_000,
                0,
                5_000_000,
            ),
            *[
                TimelineClip(
                    f"audio-clip-{index}",
                    f"material-{index + 1}",
                    f"audio-{index}",
                    0,
                    5_000_000,
                    0,
                    5_000_000,
                )
                for index in range(1, 5)
            ],
        ],
    )
    return project, timeline


def test_backend_decodes_only_top_video_and_mixes_four_audio_sources(
    tmp_path: Path,
) -> None:
    project, timeline = _project_and_timeline(tmp_path)
    video_decoders: list[FakeVideoDecoder] = []
    audio_decoders: list[FakeAudioDecoder] = []
    output = FakeAudioOutput()

    def make_video(path: Path) -> FakeVideoDecoder:
        decoder = FakeVideoDecoder(path)
        video_decoders.append(decoder)
        return decoder

    def make_audio(path: Path) -> FakeAudioDecoder:
        decoder = FakeAudioDecoder(path, 0.5)
        audio_decoders.append(decoder)
        return decoder

    backend = PyAVPlaybackBackend(
        video_decoder_factory=make_video,
        audio_decoder_factory=make_audio,
        audio_output_factory=lambda: output,
    )
    plan = build_playback_plan(project, timeline, 1_000_000)

    assert backend.prepare(plan).ok
    assert backend.play().ok
    frame = backend.render(plan)

    assert frame.ok
    assert frame.video_status == "ready"
    assert frame.audio_status == "ready"
    assert frame.video_frame.shape == (4, 6, 3)
    assert len(video_decoders) == 1
    assert video_decoders[0].path.name == "中文 素材 1.mp4"
    assert len(audio_decoders) == 4
    assert len(output.writes) == 1
    assert np.allclose(output.writes[0], 0.5)


def test_seek_forces_all_active_decoders_to_reposition(tmp_path: Path) -> None:
    project, timeline = _project_and_timeline(tmp_path)
    video_decoders: list[FakeVideoDecoder] = []
    audio_decoders: list[FakeAudioDecoder] = []
    backend = PyAVPlaybackBackend(
        video_decoder_factory=lambda path: _append(
            video_decoders,
            FakeVideoDecoder(path),
        ),
        audio_decoder_factory=lambda path: _append(
            audio_decoders,
            FakeAudioDecoder(path, 0.2),
        ),
        audio_output_factory=FakeAudioOutput,
    )
    initial = build_playback_plan(project, timeline, 500_000)
    target = build_playback_plan(project, timeline, 2_000_000)
    backend.prepare(initial)

    result = backend.seek(target)

    assert result.ok
    assert video_decoders[0].calls[-1] == (2_000_000, True)
    assert all(decoder.calls[-1][2] for decoder in audio_decoders)


def test_audio_device_unavailable_is_an_explicit_nonfatal_decision(
    tmp_path: Path,
) -> None:
    project, timeline = _project_and_timeline(tmp_path)
    backend = PyAVPlaybackBackend(
        video_decoder_factory=FakeVideoDecoder,
        audio_decoder_factory=lambda path: FakeAudioDecoder(path, 0.2),
        audio_output_factory=lambda: FakeAudioOutput(unavailable=True),
    )

    result = backend.prepare(build_playback_plan(project, timeline, 0))

    assert not result.ok
    assert not result.fatal
    assert result.audio_unavailable
    assert result.error_kind == "audio_device_unavailable"


def test_muted_mode_skips_audio_device_and_keeps_video(tmp_path: Path) -> None:
    project, timeline = _project_and_timeline(tmp_path)
    backend = PyAVPlaybackBackend(
        video_decoder_factory=FakeVideoDecoder,
        audio_decoder_factory=lambda path: FakeAudioDecoder(path, 0.2),
        audio_output_factory=lambda: FakeAudioOutput(unavailable=True),
    )
    backend.set_muted(True)

    prepared = backend.prepare(build_playback_plan(project, timeline, 0))
    rendered = backend.render(build_playback_plan(project, timeline, 100_000))

    assert prepared.ok
    assert rendered.ok
    assert rendered.video_status == "ready"
    assert rendered.audio_status == "muted"


def test_missing_top_video_is_not_replaced_by_lower_track(tmp_path: Path) -> None:
    project, timeline = _project_and_timeline(tmp_path)
    Path(project.materials[0].last_known_path).unlink()
    created: list[Path] = []
    backend = PyAVPlaybackBackend(
        video_decoder_factory=lambda path: (
            created.append(path) or FakeVideoDecoder(path)
        ),
        audio_decoder_factory=lambda path: FakeAudioDecoder(path, 0.2),
        audio_output_factory=FakeAudioOutput,
    )

    result = backend.prepare(build_playback_plan(project, timeline, 0))

    assert not result.ok
    assert not result.fatal
    assert result.video_status == "missing"
    assert result.error_kind == "missing_media"
    assert created == []


def test_missing_top_video_keeps_active_audio_running(tmp_path: Path) -> None:
    project, timeline = _project_and_timeline(tmp_path)
    Path(project.materials[0].last_known_path).unlink()
    output = FakeAudioOutput()
    backend = PyAVPlaybackBackend(
        video_decoder_factory=FakeVideoDecoder,
        audio_decoder_factory=lambda path: FakeAudioDecoder(path, 0.25),
        audio_output_factory=lambda: output,
    )
    plan = build_playback_plan(project, timeline, 100_000)

    prepared = backend.prepare(plan)
    rendered = backend.render(plan)

    assert not prepared.ok
    assert prepared.video_status == "missing"
    assert prepared.audio_status == "ready"
    assert not rendered.ok
    assert rendered.video_status == "missing"
    assert rendered.audio_status == "ready"
    assert len(output.writes) == 1


def test_release_closes_every_decoder_and_output_once(tmp_path: Path) -> None:
    project, timeline = _project_and_timeline(tmp_path)
    videos: list[FakeVideoDecoder] = []
    audios: list[FakeAudioDecoder] = []
    output = FakeAudioOutput()
    backend = PyAVPlaybackBackend(
        video_decoder_factory=lambda path: _append(
            videos,
            FakeVideoDecoder(path),
        ),
        audio_decoder_factory=lambda path: _append(
            audios,
            FakeAudioDecoder(path, 0.2),
        ),
        audio_output_factory=lambda: output,
    )
    backend.prepare(build_playback_plan(project, timeline, 0))

    backend.release()
    backend.release()

    assert all(item.release_count == 1 for item in videos)
    assert all(item.release_count == 1 for item in audios)
    assert output.release_count == 1


def test_inactive_clip_decoders_are_released_during_playback(
    tmp_path: Path,
) -> None:
    project, _timeline = _project_and_timeline(tmp_path)
    timeline = Timeline(
        "timeline-sequential",
        [
            TimelineTrack("video-1", "video", "视频 1", 0),
            TimelineTrack("audio-1", "audio", "音频 1", 0),
        ],
        [
            TimelineClip(
                "video-clip-1",
                "material-1",
                "video-1",
                0,
                1_000_000,
                0,
                1_000_000,
            ),
            TimelineClip(
                "audio-clip-1",
                "material-1",
                "audio-1",
                0,
                1_000_000,
                0,
                1_000_000,
            ),
            TimelineClip(
                "video-clip-2",
                "material-2",
                "video-1",
                1_000_000,
                1_000_000,
                0,
                1_000_000,
            ),
            TimelineClip(
                "audio-clip-2",
                "material-2",
                "audio-1",
                1_000_000,
                1_000_000,
                0,
                1_000_000,
            ),
        ],
    )
    videos: list[FakeVideoDecoder] = []
    audios: list[FakeAudioDecoder] = []
    backend = PyAVPlaybackBackend(
        video_decoder_factory=lambda path: _append(
            videos,
            FakeVideoDecoder(path),
        ),
        audio_decoder_factory=lambda path: _append(
            audios,
            FakeAudioDecoder(path, 0.2),
        ),
        audio_output_factory=FakeAudioOutput,
    )

    backend.prepare(build_playback_plan(project, timeline, 100_000))
    backend.render(build_playback_plan(project, timeline, 1_100_000))

    assert len(videos) == 2
    assert len(audios) == 2
    assert videos[0].release_count == 1
    assert audios[0].release_count == 1
    assert videos[1].release_count == 0
    assert audios[1].release_count == 0

    backend.render(build_playback_plan(project, timeline, 2_500_000))

    assert videos[1].release_count == 1
    assert audios[1].release_count == 1


def test_decoder_sets_stay_bounded_across_fifty_sequential_clip_pairs(
    tmp_path: Path,
) -> None:
    project, _timeline = _project_and_timeline(tmp_path)
    clips: list[TimelineClip] = []
    for index in range(50):
        material_id = f"material-{index % 5 + 1}"
        start_us = index * 1_000_000
        clips.extend(
            [
                TimelineClip(
                    f"video-clip-{index}",
                    material_id,
                    "video-1",
                    start_us,
                    1_000_000,
                    0,
                    1_000_000,
                ),
                TimelineClip(
                    f"audio-clip-{index}",
                    material_id,
                    "audio-1",
                    start_us,
                    1_000_000,
                    0,
                    1_000_000,
                ),
            ]
        )
    timeline = Timeline(
        "timeline-stress-sequential",
        [
            TimelineTrack("video-1", "video", "视频 1", 0),
            TimelineTrack("audio-1", "audio", "音频 1", 0),
        ],
        clips,
    )
    videos: list[FakeVideoDecoder] = []
    audios: list[FakeAudioDecoder] = []
    backend = PyAVPlaybackBackend(
        video_decoder_factory=lambda path: _append(
            videos,
            FakeVideoDecoder(path),
        ),
        audio_decoder_factory=lambda path: _append(
            audios,
            FakeAudioDecoder(path, 0.2),
        ),
        audio_output_factory=FakeAudioOutput,
    )

    backend.prepare(build_playback_plan(project, timeline, 100_000))
    for index in range(1, 50):
        backend.render(
            build_playback_plan(
                project,
                timeline,
                index * 1_000_000 + 100_000,
            )
        )
        assert len(backend._video_decoders) == 1
        assert len(backend._audio_decoders) == 1

    assert len(videos) == 50
    assert len(audios) == 50
    assert sum(item.release_count for item in videos) == 49
    assert sum(item.release_count for item in audios) == 49

    backend.render(build_playback_plan(project, timeline, 50_500_000))

    assert backend._video_decoders == {}
    assert backend._audio_decoders == {}
    assert all(item.release_count == 1 for item in videos)
    assert all(item.release_count == 1 for item in audios)


def test_one_broken_audio_source_keeps_video_and_other_audio_running(
    tmp_path: Path,
) -> None:
    project, timeline = _project_and_timeline(tmp_path)
    output = FakeAudioOutput()

    def make_audio(path: Path):
        if path.name.endswith("3.mp4"):
            return FailingAudioDecoder(path, 0.0)
        return FakeAudioDecoder(path, 0.2)

    backend = PyAVPlaybackBackend(
        video_decoder_factory=FakeVideoDecoder,
        audio_decoder_factory=make_audio,
        audio_output_factory=lambda: output,
    )
    plan = build_playback_plan(project, timeline, 100_000)

    prepared = backend.prepare(plan)
    rendered = backend.render(plan)

    assert prepared.ok
    assert not rendered.ok
    assert not rendered.fatal
    assert rendered.video_status == "ready"
    assert rendered.audio_status == "degraded"
    assert rendered.error_kind == "audio_decode_failed"
    assert len(output.writes) == 1
    assert np.any(output.writes[0])


def _append(items: list, item):
    items.append(item)
    return item
