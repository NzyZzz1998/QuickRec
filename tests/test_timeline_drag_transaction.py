from __future__ import annotations

import copy
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import pytest

from services.project_library import ProjectLibraryService
from services.timeline_commands import TimelineCommandService
from services.timeline_drag_transaction import TimelineDragTransactionService
from utils.project_store import (
    ProjectFile,
    ProjectMaterialRef,
    ProjectWriteResult,
)
from utils.timeline_model import (
    MAX_TRACKS_PER_KIND,
    Timeline,
    TimelineClip,
    TimelineTrack,
)


def _project(source: Path, *, duration_sec: float = 2.0) -> ProjectFile:
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    return ProjectFile(
        project_id="project-drag",
        name="拖放测试",
        description="",
        created_at="2026-07-30T12:00:00+08:00",
        updated_at="2026-07-30T12:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=str(source),
                file_name=source.name,
                added_at="2026-07-30T12:00:00+08:00",
                metadata_snapshot={
                    "duration_sec": duration_sec,
                    "fps": 60.0,
                    "audio_source": "both",
                },
            )
        ],
    )


def _timeline(
    *,
    video_tracks: int = 1,
    audio_tracks: int = 1,
    clips: list[TimelineClip] | None = None,
) -> Timeline:
    tracks = [
        TimelineTrack(f"video-{index}", "video", f"视频 {index}", index - 1)
        for index in range(1, video_tracks + 1)
    ]
    tracks.extend(
        TimelineTrack(f"audio-{index}", "audio", f"音频 {index}", index - 1)
        for index in range(1, audio_tracks + 1)
    )
    return Timeline("timeline-drag", tracks, clips or [])


def _blocking_clip(
    clip_id: str,
    track_id: str,
    *,
    start_us: int = 0,
    duration_us: int = 2_000_000,
) -> TimelineClip:
    return TimelineClip(
        clip_id=clip_id,
        material_id="material-1",
        track_id=track_id,
        timeline_start_us=start_us,
        timeline_duration_us=duration_us,
        source_start_us=0,
        source_duration_us=duration_us,
    )


def _preview(
    service: TimelineDragTransactionService,
    timeline: Timeline,
    project: ProjectFile,
    **overrides,
):
    options = {
        "material_id": "material-1",
        "has_video": True,
        "has_audio": True,
        "raw_start_us": 3_000_000,
        "hovered_track_id": "video-1",
        "playhead_us": 8_000_000,
        "editing_fps": 60,
        "pixels_per_second": 100.0,
        "snap_enabled": True,
        "transaction_id": "drag-1",
    }
    options.update(overrides)
    return service.preview(timeline, project, **options)


def _command_session(
    tmp_path: Path,
) -> tuple[TimelineCommandService, Path]:
    source = tmp_path / "中文 空格" / "source.mp4"
    project = _project(source)
    project_service = ProjectLibraryService(
        tmp_path / "projects.json",
        default_root=tmp_path / "projects",
    )
    created = project_service.create_project(
        name=project.name,
        project_id=project.project_id,
    )
    assert created.ok and created.path is not None
    assert project_service.add_material(
        project.project_id,
        project.materials[0],
    ).ok
    return (
        TimelineCommandService(project_service, project.project_id),
        created.path,
    )


def test_preview_is_explainable_and_does_not_mutate_source(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "source.mp4")
    timeline = _timeline()
    before = copy.deepcopy(timeline)

    candidate = _preview(
        TimelineDragTransactionService(),
        timeline,
        project,
    )

    assert candidate.valid
    assert candidate.transaction_id == "drag-1"
    assert candidate.material_id == "material-1"
    assert candidate.video_track_id == "video-1"
    assert candidate.audio_track_id == "audio-1"
    assert candidate.start_us == 3_000_000
    assert candidate.snap_source == "frame"
    assert candidate.auto_track_kinds == ()
    assert candidate.timeline is not None
    assert len(candidate.created_clip_ids) == 2
    assert timeline == before


def test_stream_types_and_explicit_locked_or_incompatible_tracks(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "source.mp4")
    timeline = _timeline()
    timeline.tracks[0].locked = True
    service = TimelineDragTransactionService()

    locked = _preview(service, timeline, project)
    wrong_video = _preview(
        service,
        timeline,
        project,
        has_audio=False,
        hovered_track_id="audio-1",
    )
    timeline.tracks[0].locked = False
    wrong_audio = _preview(
        service,
        timeline,
        project,
        has_video=False,
        has_audio=True,
        hovered_track_id="video-1",
    )

    assert not locked.valid and locked.conflict_code == "locked_track"
    assert not wrong_video.valid
    assert wrong_video.conflict_code == "incompatible_track"
    assert not wrong_audio.valid
    assert wrong_audio.conflict_code == "incompatible_track"


def test_existing_free_tracks_prevent_auto_creation(tmp_path: Path) -> None:
    project = _project(tmp_path / "source.mp4")
    timeline = _timeline(video_tracks=2, audio_tracks=2)
    timeline.clips.extend(
        [
            _blocking_clip("video-block", "video-1"),
            _blocking_clip("audio-block", "audio-1"),
        ]
    )

    candidate = _preview(
        TimelineDragTransactionService(),
        timeline,
        project,
        raw_start_us=500_000,
    )

    assert candidate.valid
    assert candidate.video_track_id == "video-2"
    assert candidate.audio_track_id == "audio-2"
    assert candidate.auto_track_kinds == ()


def test_audio_only_material_creates_one_unlinked_audio_clip(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "audio.mp4")
    timeline = _timeline()

    candidate = _preview(
        TimelineDragTransactionService(
            clip_id_factory=lambda: "audio-clip"
        ),
        timeline,
        project,
        has_video=False,
        has_audio=True,
        hovered_track_id="audio-1",
    )

    assert candidate.valid
    assert candidate.video_track_id is None
    assert candidate.audio_track_id == "audio-1"
    assert candidate.created_clip_ids == ("audio-clip",)
    assert candidate.timeline is not None
    created = next(
        clip
        for clip in candidate.timeline.clips
        if clip.clip_id == "audio-clip"
    )
    assert created.link_group_id is None
    assert created.track_id == "audio-1"


def test_all_locked_tracks_allow_auto_track_only_without_explicit_hover(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "source.mp4")
    timeline = _timeline()
    for track in timeline.tracks:
        track.locked = True

    candidate = _preview(
        TimelineDragTransactionService(),
        timeline,
        project,
        hovered_track_id=None,
    )

    assert candidate.valid
    assert candidate.auto_track_kinds == ("video", "audio")


def test_all_conflicting_tracks_create_atomic_top_video_and_last_audio(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "source.mp4")
    timeline = _timeline(video_tracks=2, audio_tracks=2)
    timeline.clips.extend(
        [
            _blocking_clip("video-1-block", "video-1"),
            _blocking_clip("video-2-block", "video-2"),
            _blocking_clip("audio-1-block", "audio-1"),
            _blocking_clip("audio-2-block", "audio-2"),
        ]
    )

    candidate = _preview(
        TimelineDragTransactionService(
            track_id_factory=iter(("video-new", "audio-new")).__next__,
            clip_id_factory=iter(("clip-video", "clip-audio")).__next__,
            link_group_id_factory=lambda: "link-new",
        ),
        timeline,
        project,
        raw_start_us=500_000,
    )

    assert candidate.valid
    assert candidate.auto_track_kinds == ("video", "audio")
    assert candidate.video_track_id == "video-new"
    assert candidate.audio_track_id == "audio-new"
    assert candidate.created_track_ids == ("video-new", "audio-new")
    assert candidate.timeline is not None
    videos = sorted(
        (
            track.order,
            track.track_id,
        )
        for track in candidate.timeline.tracks
        if track.kind == "video"
    )
    audios = sorted(
        (
            track.order,
            track.track_id,
        )
        for track in candidate.timeline.tracks
        if track.kind == "audio"
    )
    assert videos[0] == (0, "video-new")
    assert audios[-1] == (2, "audio-new")
    created = [
        clip
        for clip in candidate.timeline.clips
        if clip.clip_id in candidate.created_clip_ids
    ]
    assert {clip.link_group_id for clip in created} == {"link-new"}


@pytest.mark.parametrize(
    ("has_video", "has_audio", "expected_kind"),
    (
        (True, False, "video"),
        (False, True, "audio"),
    ),
)
def test_track_limit_rejects_without_partial_candidate(
    tmp_path: Path,
    has_video: bool,
    has_audio: bool,
    expected_kind: str,
) -> None:
    project = _project(tmp_path / "source.mp4")
    timeline = _timeline(
        video_tracks=MAX_TRACKS_PER_KIND,
        audio_tracks=MAX_TRACKS_PER_KIND,
    )
    timeline.clips.extend(
        [
            _blocking_clip(f"v-{index}", f"video-{index}")
            for index in range(1, MAX_TRACKS_PER_KIND + 1)
        ]
    )
    timeline.clips.extend(
        [
            _blocking_clip(f"a-{index}", f"audio-{index}")
            for index in range(1, MAX_TRACKS_PER_KIND + 1)
        ]
    )

    candidate = _preview(
        TimelineDragTransactionService(),
        timeline,
        project,
        raw_start_us=500_000,
        has_video=has_video,
        has_audio=has_audio,
        hovered_track_id=f"{expected_kind}-1",
    )

    assert not candidate.valid
    assert candidate.timeline is None
    assert candidate.conflict_code == "track_limit"
    assert candidate.created_track_ids == ()
    assert candidate.created_clip_ids == ()


def test_command_commit_is_one_save_and_one_undo_for_auto_tracks(
    tmp_path: Path,
) -> None:
    session, _project_path = _command_session(tmp_path)
    first = session.add_material("material-1", has_audio=True)
    assert first.ok
    before = session.timeline
    before_undo = session.undo_depth
    before_revision = session.save_snapshot.revision
    candidate = session.preview_material_drop(
        "material-1",
        has_video=True,
        has_audio=True,
        raw_start_us=500_000,
        hovered_track_id=first.affected_track_ids[0],
        playhead_us=4_000_000,
        pixels_per_second=100,
        transaction_id="drag-command",
    )

    result = session.commit_material_drop(candidate)

    assert candidate.valid
    assert candidate.auto_track_kinds == ("video", "audio")
    assert result.ok and result.saved
    assert session.undo_depth == before_undo + 1
    assert session.save_snapshot.revision == before_revision + 1
    assert session.undo().ok
    assert session.timeline == before
    assert session.redo().ok
    assert session.timeline == candidate.timeline


def test_stale_drop_candidate_is_rejected_without_side_effects(
    tmp_path: Path,
) -> None:
    session, project_path = _command_session(tmp_path)
    candidate = session.preview_material_drop(
        "material-1",
        has_video=True,
        has_audio=False,
        raw_start_us=2_000_000,
        hovered_track_id=session.timeline.tracks[0].track_id,
        playhead_us=4_000_000,
        pixels_per_second=100,
        transaction_id="drag-stale",
    )
    assert candidate.valid
    assert session.rename_track(
        session.timeline.tracks[0].track_id,
        "renamed",
    ).ok
    before = session.timeline
    before_file = project_path.read_bytes()
    before_undo = session.undo_depth

    rejected = session.commit_material_drop(candidate)

    assert not rejected.ok
    assert rejected.stage == "stale_candidate"
    assert session.timeline == before
    assert project_path.read_bytes() == before_file
    assert session.undo_depth == before_undo


def test_auto_track_save_failure_has_zero_side_effects(tmp_path: Path) -> None:
    session, project_path = _command_session(tmp_path)
    first = session.add_material("material-1", has_audio=True)
    assert first.ok
    before = session.timeline
    before_file = project_path.read_bytes()
    before_undo = session.undo_depth
    candidate = session.preview_material_drop(
        "material-1",
        has_video=True,
        has_audio=True,
        raw_start_us=500_000,
        hovered_track_id=first.affected_track_ids[0],
        playhead_us=4_000_000,
        pixels_per_second=100,
        transaction_id="drag-failure",
    )

    with patch(
        "services.project_library.save_project",
        return_value=ProjectWriteResult(
            False,
            project_path,
            stage="write",
            error="injected drag save failure",
        ),
    ):
        failed = session.commit_material_drop(candidate)

    assert not failed.ok
    assert session.timeline == before
    assert session.undo_depth == before_undo
    assert project_path.read_bytes() == before_file
    assert session.discard_pending_save().ok
    assert session.timeline == before


def test_preview_with_one_hundred_clips_stays_below_release_budget(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path / "source.mp4", duration_sec=1.0)
    timeline = _timeline(video_tracks=8, audio_tracks=8)
    for index in range(100):
        kind = "video" if index % 2 == 0 else "audio"
        track_number = index % 8 + 1
        timeline.clips.append(
            _blocking_clip(
                f"clip-{index}",
                f"{kind}-{track_number}",
                start_us=index * 2_000_000,
                duration_us=1_000_000,
            )
        )
    service = TimelineDragTransactionService()
    samples: list[float] = []
    for index in range(50):
        started = perf_counter()
        candidate = _preview(
            service,
            timeline,
            project,
            has_audio=False,
            raw_start_us=250_000_000 + index * 20_000,
            hovered_track_id="video-1",
        )
        samples.append(perf_counter() - started)
        assert candidate.valid
    samples.sort()

    assert samples[int(len(samples) * 0.95)] < 0.2
