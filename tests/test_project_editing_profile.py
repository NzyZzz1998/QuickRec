from __future__ import annotations

import copy

import pytest

from services.project_editing_profile import (
    EDITING_EXTENSION_KEY,
    ProjectEditingProfile,
    editing_profile_for_new_project,
    resolve_project_editing_profile,
    with_project_editing_profile,
)
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import Timeline, TimelineClip, TimelineTrack


def _project(
    *,
    extensions: dict | None = None,
    materials: list[ProjectMaterialRef] | None = None,
) -> ProjectFile:
    return ProjectFile(
        "project-1",
        "帧率项目",
        "",
        "2026-07-30T10:00:00+08:00",
        "2026-07-30T10:00:00+08:00",
        materials=materials or [],
        extensions=extensions or {},
    )


def _material(material_id: str, fps: object) -> ProjectMaterialRef:
    return ProjectMaterialRef(
        material_id,
        rf"E:\素材\{material_id}.mp4",
        f"{material_id}.mp4",
        "2026-07-30T10:00:00+08:00",
        {"fps": fps},
    )


def _timeline(*clips: TimelineClip) -> Timeline:
    return Timeline(
        "timeline-1",
        [
            TimelineTrack("video-low", "video", "视频 1", 1),
            TimelineTrack("video-high", "video", "视频 2", 0),
            TimelineTrack("audio-1", "audio", "音频 1", 0),
        ],
        list(clips),
    )


def _clip(
    clip_id: str,
    material_id: str,
    *,
    track_id: str = "video-low",
    start_us: int = 0,
) -> TimelineClip:
    return TimelineClip(
        clip_id,
        material_id,
        track_id,
        start_us,
        1_000_000,
        0,
        1_000_000,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    ((30, 30), (60, 60), (120, 120), (None, 30), (90, 30)),
)
def test_new_project_profile_accepts_only_supported_recording_fps(
    value: object,
    expected: int,
) -> None:
    profile = editing_profile_for_new_project(value)

    assert profile.editing_fps == expected
    assert not profile.fps_locked


@pytest.mark.parametrize(
    "value",
    (True, False, 30.0, "30", 24, 90, [], {}),
)
def test_persisted_profile_rejects_non_integer_or_unsupported_fps(
    value: object,
) -> None:
    project = _project(
        extensions={
            EDITING_EXTENSION_KEY: {
                "schema_version": 1,
                "editing_fps": value,
            }
        }
    )

    resolved = resolve_project_editing_profile(project, _timeline())

    assert resolved.read_only
    assert resolved.status == "invalid"
    assert "editing_fps" in resolved.error


def test_profile_preserves_unknown_fields_when_written_back() -> None:
    raw = {
        "schema_version": 1,
        "editing_fps": 60,
        "fps_locked": True,
        "future": {"mode": "keep"},
    }
    project = _project(
        extensions={
            EDITING_EXTENSION_KEY: copy.deepcopy(raw),
            "future.project": {"keep": True},
        }
    )
    resolved = resolve_project_editing_profile(project, _timeline())

    candidate = with_project_editing_profile(project, resolved.profile)

    assert candidate.extensions[EDITING_EXTENSION_KEY] == raw
    assert candidate.extensions["future.project"] == {"keep": True}
    assert project.extensions[EDITING_EXTENSION_KEY] == raw


def test_unknown_profile_schema_is_read_only_and_original_payload_is_untouched() -> None:
    raw = {
        "schema_version": 99,
        "editing_fps": 60,
        "future": "keep",
    }
    project = _project(
        extensions={EDITING_EXTENSION_KEY: copy.deepcopy(raw)}
    )

    resolved = resolve_project_editing_profile(project, _timeline())

    assert resolved.read_only
    assert resolved.status == "unsupported"
    assert resolved.profile.editing_fps == 30
    assert project.extensions[EDITING_EXTENSION_KEY] == raw


def test_missing_profile_uses_first_stable_valid_video_material() -> None:
    project = _project(
        materials=[
            _material("invalid", "bad"),
            _material("high", 59.94),
            _material("later", 120),
        ]
    )
    timeline = _timeline(
        _clip("clip-later", "later", start_us=2_000_000),
        _clip(
            "clip-high",
            "high",
            track_id="video-high",
            start_us=1_000_000,
        ),
        _clip(
            "clip-invalid",
            "invalid",
            track_id="video-high",
            start_us=0,
        ),
    )

    resolved = resolve_project_editing_profile(project, timeline)

    assert resolved.status == "inferred"
    assert not resolved.persisted
    assert resolved.profile.editing_fps == 60
    assert resolved.profile.fps_locked
    assert EDITING_EXTENSION_KEY not in project.extensions


@pytest.mark.parametrize(
    ("source_fps", "expected"),
    ((44.9, 30), (45.0, 30), (45.1, 60), (90.0, 60), (90.1, 120)),
)
def test_inference_uses_nearest_supported_fps_and_lower_tie_break(
    source_fps: float,
    expected: int,
) -> None:
    project = _project(materials=[_material("material-1", source_fps)])

    resolved = resolve_project_editing_profile(
        project,
        _timeline(_clip("clip-1", "material-1")),
    )

    assert resolved.profile.editing_fps == expected


def test_missing_profile_without_valid_video_falls_back_to_unlocked_30() -> None:
    resolved = resolve_project_editing_profile(_project(), _timeline())

    assert resolved.status == "inferred"
    assert resolved.profile == ProjectEditingProfile(30, fps_locked=False)
    assert not resolved.persisted


def test_profile_without_lock_field_locks_when_timeline_has_clips() -> None:
    project = _project(
        extensions={
            EDITING_EXTENSION_KEY: {
                "schema_version": 1,
                "editing_fps": 60,
            }
        }
    )

    resolved = resolve_project_editing_profile(
        project,
        _timeline(_clip("clip-1", "material-1")),
    )

    assert resolved.persisted
    assert resolved.profile.fps_locked
