from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from utils.project_store import ProjectFile, ProjectMaterialRef, load_project, save_project
from utils.schema_migrations import SchemaMigrationRegistry
from utils.timeline_model import (
    MAX_TRACKS_PER_KIND,
    TIMELINE_EXTENSION_KEY,
    TimelineClip,
    TimelineTrack,
    create_empty_timeline,
    load_project_timeline,
    microseconds_to_display,
    seconds_to_microseconds,
    serialize_timeline,
    validate_timeline,
    with_project_timeline,
)

FIXTURES = Path(__file__).parent / "fixtures" / "v1_9_2"


def _project(*, duration_sec: float = 1.0) -> ProjectFile:
    return ProjectFile(
        project_id="project-1",
        name="项目",
        description="",
        created_at="2026-07-28T10:00:00+08:00",
        updated_at="2026-07-28T10:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=r"E:\QRtest\中文 空格\demo.mp4",
                file_name="demo.mp4",
                added_at="2026-07-28T10:00:01+08:00",
                metadata_snapshot={"duration_sec": duration_sec},
            )
        ],
        extensions={"future.project": {"preserve": True}},
    )


def _clip(
    clip_id: str,
    track_id: str,
    *,
    start_us: int = 0,
    duration_us: int = 1_000_000,
    material_id: str = "material-1",
    link_group_id: str | None = None,
) -> TimelineClip:
    return TimelineClip(
        clip_id=clip_id,
        material_id=material_id,
        track_id=track_id,
        timeline_start_us=start_us,
        timeline_duration_us=duration_us,
        source_start_us=0,
        source_duration_us=duration_us,
        link_group_id=link_group_id,
    )


def test_old_project_gets_deterministic_unpersisted_empty_timeline() -> None:
    loaded = load_project(FIXTURES / "project_timeline_missing.json")
    assert loaded.ok and loaded.project is not None
    project = loaded.project
    before = copy.deepcopy(project.extensions)

    first = load_project_timeline(project)
    second = load_project_timeline(project)

    assert first.ok
    assert first.status == "empty"
    assert not first.persisted
    assert not first.read_only
    assert first.timeline == second.timeline
    assert first.timeline is not None
    assert first.timeline.timeline_id.startswith("timeline-")
    assert [track.kind for track in first.timeline.tracks] == ["video", "audio"]
    assert project.extensions == before


def test_v191_save_roundtrip_preserves_unknown_timeline_extension(
    tmp_path: Path,
) -> None:
    loaded = load_project(FIXTURES / "project_timeline_v99_unknown.json")
    assert loaded.ok and loaded.project is not None
    raw = copy.deepcopy(loaded.project.extensions[TIMELINE_EXTENSION_KEY])
    loaded.project.name = "由旧版本修改名称"
    path = tmp_path / "project.qrproj"

    assert save_project(path, loaded.project).ok
    reloaded = load_project(path)

    assert reloaded.ok and reloaded.project is not None
    assert reloaded.project.name == "由旧版本修改名称"
    assert reloaded.project.extensions[TIMELINE_EXTENSION_KEY] == raw


def test_empty_timeline_uses_stable_unique_ids_and_default_tracks() -> None:
    timeline = create_empty_timeline("project-1")

    assert timeline.timeline_id
    assert len({track.track_id for track in timeline.tracks}) == 2
    assert [(track.kind, track.name, track.order) for track in timeline.tracks] == [
        ("video", "视频 1", 0),
        ("audio", "音频 1", 0),
    ]


def test_valid_fixture_roundtrips_unknown_fields_and_project_extensions() -> None:
    loaded = load_project(FIXTURES / "project_timeline_v1_normal.json")
    assert loaded.ok and loaded.project is not None

    result = load_project_timeline(loaded.project)
    assert result.ok and result.timeline is not None
    payload = serialize_timeline(result.timeline, loaded.project)

    assert payload["future_timeline_field"] == "保留"
    assert payload["tracks"][0]["future_track_field"] == "保留"
    assert payload["clips"][0]["future_clip_field"] == 42
    assert loaded.project.extensions["future.project"] == {"preserve": True}


def test_project_roundtrip_preserves_timeline_and_other_extensions(tmp_path: Path) -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    timeline.clips.append(_clip("clip-1", timeline.tracks[0].track_id))
    candidate = with_project_timeline(project, timeline)
    path = tmp_path / "project.qrproj"

    assert save_project(path, candidate).ok
    loaded = load_project(path)
    assert loaded.ok and loaded.project is not None
    reloaded_timeline = load_project_timeline(loaded.project)

    assert reloaded_timeline.ok
    assert reloaded_timeline.timeline == timeline
    assert loaded.project.extensions["future.project"] == {"preserve": True}


def test_unknown_timeline_version_is_read_only_and_raw_payload_survives() -> None:
    loaded = load_project(FIXTURES / "project_timeline_v99_unknown.json")
    assert loaded.ok and loaded.project is not None
    raw = copy.deepcopy(loaded.project.extensions[TIMELINE_EXTENSION_KEY])

    result = load_project_timeline(loaded.project)

    assert not result.ok
    assert result.status == "unsupported"
    assert result.read_only
    assert result.timeline is None
    assert result.raw_extension == raw
    assert loaded.project.extensions[TIMELINE_EXTENSION_KEY] == raw


def test_registered_timeline_migration_is_in_memory_and_preserves_raw_extension(
    monkeypatch,
) -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    raw = timeline.to_dict()
    raw["schema_version"] = 0
    project.extensions[TIMELINE_EXTENSION_KEY] = copy.deepcopy(raw)
    registry = SchemaMigrationRegistry(
        label="timeline",
        current_version=1,
    )
    registry.register(
        0,
        1,
        lambda payload: {**payload, "schema_version": 1},
    )
    monkeypatch.setattr(
        "utils.timeline_model.TIMELINE_SCHEMA_MIGRATIONS",
        registry,
    )

    result = load_project_timeline(project)

    assert result.ok
    assert result.timeline is not None
    assert result.timeline.schema_version == 1
    assert project.extensions[TIMELINE_EXTENSION_KEY] == raw


def test_corrupt_timeline_is_isolated_from_valid_project_materials() -> None:
    loaded = load_project(FIXTURES / "project_timeline_v1_corrupt.json")
    assert loaded.ok and loaded.project is not None

    result = load_project_timeline(loaded.project)

    assert not result.ok
    assert result.status == "corrupt"
    assert result.read_only
    assert "overlap" in result.error.lower()
    assert loaded.project.materials[0].material_id == "material-a"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (0.0000004, 0),
        (0.0000005, 1),
        ("1.2345675", 1_234_568),
        (3.5, 3_500_000),
    ],
)
def test_seconds_to_microseconds_uses_nearest_half_up(value: object, expected: int) -> None:
    assert seconds_to_microseconds(value) == expected


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "bad"])
def test_seconds_to_microseconds_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError):
        seconds_to_microseconds(value)


def test_microseconds_to_display_uses_fixed_millisecond_shape() -> None:
    assert microseconds_to_display(3_723_456_789) == "01:02:03.457"


@pytest.mark.parametrize("kind", ["video", "audio"])
def test_rejects_more_than_eight_tracks_per_kind(kind: str) -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    other_kind = "audio" if kind == "video" else "video"
    timeline.tracks = [
        TimelineTrack(f"{kind}-{index}", kind, f"{kind} {index + 1}", index)
        for index in range(MAX_TRACKS_PER_KIND + 1)
    ] + [TimelineTrack(f"{other_kind}-0", other_kind, other_kind, 0)]

    with pytest.raises(ValueError, match="at most"):
        validate_timeline(timeline, project)


def test_accepts_eight_video_and_eight_audio_tracks() -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    timeline.tracks = [
        *[
            TimelineTrack(f"video-{index}", "video", f"视频 {index + 1}", index)
            for index in range(MAX_TRACKS_PER_KIND)
        ],
        *[
            TimelineTrack(f"audio-{index}", "audio", f"音频 {index + 1}", index)
            for index in range(MAX_TRACKS_PER_KIND)
        ],
    ]

    validate_timeline(timeline, project)


@pytest.mark.parametrize("kind", ["video", "audio"])
def test_requires_at_least_one_track_per_kind(kind: str) -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    timeline.tracks = [track for track in timeline.tracks if track.kind != kind]

    with pytest.raises(ValueError, match="at least"):
        validate_timeline(timeline, project)


def test_rejects_duplicate_track_and_clip_ids() -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    timeline.tracks[1].track_id = timeline.tracks[0].track_id
    with pytest.raises(ValueError, match="duplicate track_id"):
        validate_timeline(timeline, project)

    timeline = create_empty_timeline(project.project_id)
    track_id = timeline.tracks[0].track_id
    timeline.clips = [_clip("same", track_id), _clip("same", track_id, start_us=1_000_000)]
    with pytest.raises(ValueError, match="duplicate clip_id"):
        validate_timeline(timeline, project)


def test_rejects_non_contiguous_track_order() -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    timeline.tracks[0].order = 2

    with pytest.raises(ValueError, match="continuous"):
        validate_timeline(timeline, project)


@pytest.mark.parametrize(
    "clip",
    [
        _clip("negative", "video", start_us=-1),
        _clip("zero", "video", duration_us=0),
        _clip("missing-material", "video", material_id="not-in-project"),
    ],
)
def test_rejects_invalid_clip_time_or_reference(clip: TimelineClip) -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    clip.track_id = timeline.tracks[0].track_id
    timeline.clips = [clip]

    with pytest.raises(ValueError):
        validate_timeline(timeline, project)


def test_rejects_duration_that_exceeds_material_snapshot() -> None:
    project = _project(duration_sec=1.0)
    timeline = create_empty_timeline(project.project_id)
    timeline.clips = [_clip("too-long", timeline.tracks[0].track_id, duration_us=1_000_001)]

    with pytest.raises(ValueError, match="source duration"):
        validate_timeline(timeline, project)


def test_same_track_overlap_is_rejected_but_cross_track_overlap_is_allowed() -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    video_1 = timeline.tracks[0]
    video_2 = TimelineTrack("video-2", "video", "视频 2", 1)
    timeline.tracks.insert(1, video_2)
    timeline.clips = [
        _clip("clip-1", video_1.track_id),
        _clip("clip-2", video_1.track_id, start_us=500_000),
    ]
    with pytest.raises(ValueError, match="overlap"):
        validate_timeline(timeline, project)

    timeline.clips[1].track_id = video_2.track_id
    validate_timeline(timeline, project)


def test_link_group_requires_one_video_and_one_audio_with_matching_time() -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    video_track, audio_track = timeline.tracks
    timeline.clips = [
        _clip("video-clip", video_track.track_id, link_group_id="link-1"),
        _clip("audio-clip", audio_track.track_id, link_group_id="link-1"),
    ]
    validate_timeline(timeline, project)

    timeline.clips[1].timeline_start_us = 1
    with pytest.raises(ValueError, match="same timeline start"):
        validate_timeline(timeline, project)


def test_link_group_rejects_two_video_members() -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    timeline.tracks.insert(1, TimelineTrack("video-2", "video", "视频 2", 1))
    timeline.clips = [
        _clip("video-a", timeline.tracks[0].track_id, link_group_id="link-1"),
        _clip("video-b", timeline.tracks[1].track_id, link_group_id="link-1"),
    ]

    with pytest.raises(ValueError, match="one video"):
        validate_timeline(timeline, project)


@pytest.mark.parametrize("clip_count", [0, 1, 20, 50, 100])
def test_supported_clip_scales_roundtrip(clip_count: int) -> None:
    project = _project()
    timeline = create_empty_timeline(project.project_id)
    track_id = timeline.tracks[0].track_id
    timeline.clips = [
        _clip(f"clip-{index}", track_id, start_us=index * 1_000_000)
        for index in range(clip_count)
    ]

    payload = serialize_timeline(timeline, project)
    candidate = copy.deepcopy(project)
    candidate.extensions[TIMELINE_EXTENSION_KEY] = json.loads(json.dumps(payload))
    loaded = load_project_timeline(candidate)

    assert loaded.ok
    assert loaded.timeline == timeline
    assert len(loaded.timeline.clips) == clip_count
