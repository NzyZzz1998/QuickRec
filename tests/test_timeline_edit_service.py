from __future__ import annotations

import copy
from time import perf_counter

from services.timeline_edit_service import TimelineEditService
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import (
    Timeline,
    TimelineClip,
    TimelineTrack,
    validate_timeline,
)


def _project(
    *,
    duration_sec: float = 10.0,
    fps: float | None = 30.0,
) -> ProjectFile:
    metadata: dict[str, object] = {"duration_sec": duration_sec}
    if fps is not None:
        metadata["fps"] = fps
    return ProjectFile(
        project_id="project-edit",
        name="剪辑测试",
        description="",
        created_at="2026-07-29T10:00:00+08:00",
        updated_at="2026-07-29T10:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=r"E:\QRtest\中文 空格\sample.mp4",
                file_name="sample.mp4",
                added_at="2026-07-29T10:00:00+08:00",
                metadata_snapshot=metadata,
            )
        ],
    )


def _tracks() -> list[TimelineTrack]:
    return [
        TimelineTrack("video-1", "video", "视频 1", 0),
        TimelineTrack("video-2", "video", "视频 2", 1),
        TimelineTrack("audio-1", "audio", "音频 1", 0),
        TimelineTrack("audio-2", "audio", "音频 2", 1),
    ]


def _clip(
    clip_id: str,
    track_id: str,
    *,
    start_us: int,
    duration_us: int,
    source_start_us: int = 0,
    link_group_id: str | None = None,
) -> TimelineClip:
    return TimelineClip(
        clip_id=clip_id,
        material_id="material-1",
        track_id=track_id,
        timeline_start_us=start_us,
        timeline_duration_us=duration_us,
        source_start_us=source_start_us,
        source_duration_us=duration_us,
        link_group_id=link_group_id,
    )


def _timeline(*clips: TimelineClip) -> Timeline:
    return Timeline(
        timeline_id="timeline-edit",
        tracks=_tracks(),
        clips=list(clips),
        schema_version=2,
    )


def _linked_group(
    *,
    prefix: str,
    start_us: int,
    duration_us: int,
    source_start_us: int = 0,
    video_track: str = "video-1",
    audio_track: str = "audio-1",
) -> tuple[TimelineClip, TimelineClip]:
    link_id = f"link-{prefix}"
    return (
        _clip(
            f"{prefix}-video",
            video_track,
            start_us=start_us,
            duration_us=duration_us,
            source_start_us=source_start_us,
            link_group_id=link_id,
        ),
        _clip(
            f"{prefix}-audio",
            audio_track,
            start_us=start_us,
            duration_us=duration_us,
            source_start_us=source_start_us,
            link_group_id=link_id,
        ),
    )


def _by_id(timeline: Timeline) -> dict[str, TimelineClip]:
    return {clip.clip_id: clip for clip in timeline.clips}


def test_trim_normalizes_to_video_frames_and_ripples_linked_group() -> None:
    project = _project(fps=30.0)
    target = _linked_group(prefix="target", start_us=0, duration_us=2_000_000)
    later = _linked_group(prefix="later", start_us=2_000_000, duration_us=1_000_000)
    timeline = _timeline(*target, *later)
    before = copy.deepcopy(timeline)

    result = TimelineEditService().trim(
        timeline,
        project,
        "target-video",
        source_start_us=110_000,
        source_end_us=1_910_000,
    )

    assert result.valid
    assert result.timeline is not None
    assert timeline == before
    clips = _by_id(result.timeline)
    assert clips["target-video"].source_start_us == 100_000
    assert clips["target-audio"].source_start_us == 100_000
    assert clips["target-video"].source_duration_us == 1_800_000
    assert clips["target-audio"].source_duration_us == 1_800_000
    assert clips["target-video"].timeline_start_us == 0
    assert clips["later-video"].timeline_start_us == 1_800_000
    assert clips["later-audio"].timeline_start_us == 1_800_000
    assert result.impact.delta_us == -200_000
    assert result.impact.range_start_us == 1_800_000
    assert result.impact.range_end_us == 2_000_000
    assert set(result.impact.affected_track_ids) == {
        "video-1",
        "audio-1",
    }
    assert set(result.impact.affected_link_group_ids) == {
        "link-target",
        "link-later",
    }
    validate_timeline(result.timeline, project)


def test_trim_can_extend_outward_and_ripple_later_clips_right() -> None:
    project = _project(fps=60.0)
    target = _linked_group(
        prefix="target",
        start_us=0,
        duration_us=1_000_000,
        source_start_us=1_000_000,
    )
    later = _linked_group(prefix="later", start_us=1_000_000, duration_us=500_000)
    timeline = _timeline(*target, *later)

    result = TimelineEditService().trim(
        timeline,
        project,
        "target-audio",
        source_start_us=500_000,
        source_end_us=2_000_000,
    )

    assert result.valid
    assert result.timeline is not None
    clips = _by_id(result.timeline)
    assert clips["target-video"].source_start_us == 500_000
    assert clips["target-video"].source_duration_us == 1_500_000
    assert clips["target-audio"].source_duration_us == 1_500_000
    assert clips["later-video"].timeline_start_us == 1_500_000
    assert clips["later-audio"].timeline_start_us == 1_500_000
    assert result.impact.delta_us == 500_000
    assert result.impact.insert_at_us == 1_000_000


def test_trim_without_trustworthy_fps_uses_100ms_video_minimum() -> None:
    project = _project(fps=None)
    timeline = _timeline(
        _clip(
            "video",
            "video-1",
            start_us=0,
            duration_us=1_000_000,
        )
    )

    invalid = TimelineEditService().trim(
        timeline,
        project,
        "video",
        source_start_us=0,
        source_end_us=99_999,
    )
    valid = TimelineEditService().trim(
        timeline,
        project,
        "video",
        source_start_us=0,
        source_end_us=100_000,
    )

    assert not invalid.valid
    assert {conflict.code for conflict in invalid.conflicts} == {
        "minimum_duration",
    }
    assert valid.valid


def test_standalone_audio_uses_20ms_minimum() -> None:
    project = _project()
    timeline = _timeline(
        _clip(
            "audio",
            "audio-1",
            start_us=0,
            duration_us=1_000_000,
        )
    )

    invalid = TimelineEditService().trim(
        timeline,
        project,
        "audio",
        source_start_us=0,
        source_end_us=19_999,
    )
    valid = TimelineEditService().trim(
        timeline,
        project,
        "audio",
        source_start_us=0,
        source_end_us=20_000,
    )

    assert not invalid.valid
    assert invalid.conflicts[0].code == "minimum_duration"
    assert valid.valid


def test_trim_rejects_crossing_insert_point_without_mutating_input() -> None:
    project = _project()
    target = _linked_group(prefix="target", start_us=0, duration_us=1_000_000)
    crossing = _clip(
        "crossing",
        "video-2",
        start_us=500_000,
        duration_us=1_000_000,
    )
    timeline = _timeline(*target, crossing)
    before = copy.deepcopy(timeline)

    result = TimelineEditService().trim(
        timeline,
        project,
        "target-video",
        source_start_us=0,
        source_end_us=1_500_000,
    )

    assert not result.valid
    assert result.timeline is None
    assert any(conflict.code == "crosses_insert_point" for conflict in result.conflicts)
    assert result.conflicts[0].clip_ids
    assert timeline == before


def test_trim_rejects_locked_track_that_would_move() -> None:
    project = _project()
    target = _linked_group(prefix="target", start_us=0, duration_us=1_000_000)
    later = _clip(
        "locked-later",
        "video-2",
        start_us=1_000_000,
        duration_us=500_000,
    )
    timeline = _timeline(*target, later)
    next(track for track in timeline.tracks if track.track_id == "video-2").locked = True

    result = TimelineEditService().trim(
        timeline,
        project,
        "target-video",
        source_start_us=0,
        source_end_us=500_000,
    )

    assert not result.valid
    assert result.timeline is None
    assert any(conflict.code == "locked_ripple_track" for conflict in result.conflicts)


def test_split_linked_group_preserves_left_identity_and_creates_right_identity() -> None:
    project = _project(fps=30.0)
    target = _linked_group(prefix="target", start_us=1_000_000, duration_us=2_000_000)
    timeline = _timeline(*target)
    clip_ids = iter(("right-video", "right-audio"))
    service = TimelineEditService(
        clip_id_factory=lambda: next(clip_ids),
        link_group_id_factory=lambda: "link-right",
    )

    result = service.split(
        timeline,
        project,
        "target-video",
        playhead_us=2_110_000,
    )

    assert result.valid
    assert result.timeline is not None
    clips = _by_id(result.timeline)
    assert set(clips) == {
        "target-video",
        "target-audio",
        "right-video",
        "right-audio",
    }
    assert clips["target-video"].timeline_duration_us == 1_100_000
    assert clips["target-audio"].timeline_duration_us == 1_100_000
    assert clips["right-video"].timeline_start_us == 2_100_000
    assert clips["right-audio"].timeline_start_us == 2_100_000
    assert clips["right-video"].source_start_us == 1_100_000
    assert clips["right-audio"].source_start_us == 1_100_000
    assert clips["target-video"].link_group_id == "link-target"
    assert clips["right-video"].link_group_id == "link-right"
    assert clips["right-audio"].link_group_id == "link-right"
    assert result.selected_clip_ids == ("right-video", "right-audio")
    assert set(result.impact.affected_link_group_ids) == {
        "link-target",
        "link-right",
    }
    assert result.impact.delta_us == 0
    validate_timeline(result.timeline, project)


def test_split_rejects_boundary_that_leaves_less_than_one_frame() -> None:
    project = _project(fps=30.0)
    timeline = _timeline(
        _clip(
            "video",
            "video-1",
            start_us=0,
            duration_us=1_000_000,
        )
    )

    result = TimelineEditService().split(
        timeline,
        project,
        "video",
        playhead_us=10_000,
    )

    assert not result.valid
    assert result.timeline is None
    assert any(conflict.code == "minimum_duration" for conflict in result.conflicts)


def test_split_rejects_direct_edit_on_locked_track() -> None:
    project = _project()
    timeline = _timeline(
        _clip("video", "video-1", start_us=0, duration_us=1_000_000)
    )
    timeline.tracks[0].locked = True

    result = TimelineEditService().split(
        timeline,
        project,
        "video",
        playhead_us=500_000,
    )

    assert not result.valid
    assert any(conflict.code == "locked_target_track" for conflict in result.conflicts)


def test_ripple_delete_removes_linked_group_and_moves_all_later_clips() -> None:
    project = _project()
    target = _linked_group(prefix="target", start_us=1_000_000, duration_us=1_000_000)
    later_video = _clip(
        "later-video",
        "video-2",
        start_us=2_000_000,
        duration_us=500_000,
    )
    later_audio = _clip(
        "later-audio",
        "audio-2",
        start_us=3_000_000,
        duration_us=500_000,
    )
    timeline = _timeline(*target, later_video, later_audio)

    result = TimelineEditService().ripple_delete(
        timeline,
        project,
        "target-audio",
    )

    assert result.valid
    assert result.timeline is not None
    clips = _by_id(result.timeline)
    assert set(clips) == {"later-video", "later-audio"}
    assert clips["later-video"].timeline_start_us == 1_000_000
    assert clips["later-audio"].timeline_start_us == 2_000_000
    assert result.impact.range_start_us == 1_000_000
    assert result.impact.range_end_us == 2_000_000
    assert result.impact.delta_us == -1_000_000
    assert result.impact.associated_clip_count == 2
    validate_timeline(result.timeline, project)


def test_ripple_delete_rejects_clip_crossing_delete_interval() -> None:
    project = _project()
    target = _linked_group(prefix="target", start_us=1_000_000, duration_us=1_000_000)
    crossing = _clip(
        "crossing",
        "video-2",
        start_us=500_000,
        duration_us=1_000_000,
    )
    timeline = _timeline(*target, crossing)
    before = copy.deepcopy(timeline)

    result = TimelineEditService().ripple_delete(
        timeline,
        project,
        "target-video",
    )

    assert not result.valid
    assert result.timeline is None
    assert any(conflict.code == "crosses_delete_range" for conflict in result.conflicts)
    assert timeline == before


def test_invalid_exact_range_does_not_mutate_input() -> None:
    project = _project()
    timeline = _timeline(
        _clip("video", "video-1", start_us=0, duration_us=1_000_000)
    )
    before = copy.deepcopy(timeline)

    result = TimelineEditService().trim(
        timeline,
        project,
        "video",
        source_start_us=2_000_000,
        source_end_us=1_000_000,
    )

    assert not result.valid
    assert result.timeline is None
    assert result.conflicts[0].code == "invalid_source_range"
    assert timeline == before


def test_100_mixed_legal_trims_preserve_timeline_invariants() -> None:
    project = _project(duration_sec=10.0, fps=30.0)
    clips = [
        _clip(
            f"clip-{index}",
            "video-1",
            start_us=index * 1_000_000,
            duration_us=1_000_000,
        )
        for index in range(10)
    ]
    timeline = _timeline(*clips)
    service = TimelineEditService()

    for index in range(100):
        first = _by_id(timeline)["clip-0"]
        source_end = 900_000 if index % 2 == 0 else 1_000_000
        result = service.trim(
            timeline,
            project,
            first.clip_id,
            source_start_us=0,
            source_end_us=source_end,
        )
        assert result.valid and result.timeline is not None
        timeline = result.timeline
        validate_timeline(timeline, project)

    assert len({clip.clip_id for clip in timeline.clips}) == 10
    ordered = sorted(timeline.clips, key=lambda clip: clip.timeline_start_us)
    assert all(
        current.timeline_end_us <= following.timeline_start_us
        for current, following in zip(ordered, ordered[1:], strict=False)
    )


def test_100_clip_ripple_preflight_stays_interactive() -> None:
    project = _project(duration_sec=10.0, fps=30.0)
    clips = [
        _clip(
            f"clip-{index}",
            "video-1",
            start_us=index * 100_000,
            duration_us=100_000,
        )
        for index in range(100)
    ]
    timeline = _timeline(*clips)
    service = TimelineEditService()

    started = perf_counter()
    result = service.trim(
        timeline,
        project,
        "clip-0",
        source_start_us=0,
        source_end_us=66_667,
    )
    elapsed_ms = (perf_counter() - started) * 1000

    assert result.valid
    assert len(result.impact.affected_clip_ids) == 100
    assert elapsed_ms < 250
