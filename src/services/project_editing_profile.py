"""Project-level editing FPS profile and legacy inference."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, TypeGuard

from utils.project_store import ProjectFile
from utils.timeline_model import Timeline

EDITING_EXTENSION_KEY = "quickrec.editing"
EDITING_SCHEMA_VERSION = 1
SUPPORTED_EDITING_FPS = (30, 60, 120)


@dataclass(frozen=True)
class ProjectEditingProfile:
    editing_fps: int
    fps_locked: bool = False
    schema_version: int = EDITING_SCHEMA_VERSION
    unknown_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = copy.deepcopy(self.unknown_fields)
        payload.update(
            {
                "schema_version": self.schema_version,
                "editing_fps": self.editing_fps,
                "fps_locked": self.fps_locked,
            }
        )
        return payload


@dataclass(frozen=True)
class ProjectEditingProfileResolution:
    profile: ProjectEditingProfile
    persisted: bool
    read_only: bool = False
    status: str = "ready"
    error: str = ""


def editing_profile_for_new_project(
    recording_fps: object,
) -> ProjectEditingProfile:
    fps = (
        recording_fps
        if _is_supported_fps(recording_fps)
        else SUPPORTED_EDITING_FPS[0]
    )
    return ProjectEditingProfile(fps)


def is_supported_editing_fps(value: object) -> bool:
    return _is_supported_fps(value)


def resolve_project_editing_profile(
    project: ProjectFile,
    timeline: Timeline,
) -> ProjectEditingProfileResolution:
    raw = project.extensions.get(EDITING_EXTENSION_KEY)
    if raw is None:
        return ProjectEditingProfileResolution(
            _infer_profile(project, timeline),
            persisted=False,
            status="inferred",
        )
    if not isinstance(raw, dict):
        return _invalid_resolution(
            timeline,
            "quickrec.editing must be an object",
        )
    schema_version = raw.get("schema_version")
    if (
        isinstance(schema_version, int)
        and not isinstance(schema_version, bool)
        and schema_version > EDITING_SCHEMA_VERSION
    ):
        return ProjectEditingProfileResolution(
            ProjectEditingProfile(
                SUPPORTED_EDITING_FPS[0],
                fps_locked=bool(timeline.clips),
            ),
            persisted=True,
            read_only=True,
            status="unsupported",
            error=(
                "quickrec.editing schema is newer than this QuickRec version"
            ),
        )
    if schema_version != EDITING_SCHEMA_VERSION or isinstance(
        schema_version,
        bool,
    ):
        return _invalid_resolution(
            timeline,
            "quickrec.editing schema_version must be 1",
        )
    editing_fps = raw.get("editing_fps")
    if not _is_supported_fps(editing_fps):
        return _invalid_resolution(
            timeline,
            "quickrec.editing editing_fps must be 30, 60, or 120",
        )
    raw_locked = raw.get("fps_locked", bool(timeline.clips))
    if not isinstance(raw_locked, bool):
        return _invalid_resolution(
            timeline,
            "quickrec.editing fps_locked must be a boolean",
        )
    unknown = {
        key: copy.deepcopy(value)
        for key, value in raw.items()
        if key not in {"schema_version", "editing_fps", "fps_locked"}
    }
    return ProjectEditingProfileResolution(
        ProjectEditingProfile(
            editing_fps,
            fps_locked=raw_locked or bool(timeline.clips),
            unknown_fields=unknown,
        ),
        persisted=True,
    )


def with_project_editing_profile(
    project: ProjectFile,
    profile: ProjectEditingProfile,
) -> ProjectFile:
    candidate = copy.deepcopy(project)
    candidate.extensions[EDITING_EXTENSION_KEY] = profile.to_dict()
    return candidate


def _infer_profile(
    project: ProjectFile,
    timeline: Timeline,
) -> ProjectEditingProfile:
    tracks = {
        track.track_id: track
        for track in timeline.tracks
        if track.kind == "video"
    }
    materials = {
        material.material_id: material
        for material in project.materials
    }
    clips = sorted(
        (
            clip
            for clip in timeline.clips
            if clip.track_id in tracks
        ),
        key=lambda clip: (
            clip.timeline_start_us,
            tracks[clip.track_id].order,
            clip.clip_id,
        ),
    )
    for clip in clips:
        material = materials.get(clip.material_id)
        if material is None:
            continue
        source_fps = _positive_number(
            material.metadata_snapshot.get("fps")
        )
        if source_fps is None:
            continue
        editing_fps = min(
            SUPPORTED_EDITING_FPS,
            key=lambda candidate: (
                abs(float(candidate) - source_fps),
                candidate,
            ),
        )
        return ProjectEditingProfile(
            editing_fps,
            fps_locked=bool(timeline.clips),
        )
    return ProjectEditingProfile(
        SUPPORTED_EDITING_FPS[0],
        fps_locked=bool(timeline.clips),
    )


def _invalid_resolution(
    timeline: Timeline,
    error: str,
) -> ProjectEditingProfileResolution:
    return ProjectEditingProfileResolution(
        ProjectEditingProfile(
            SUPPORTED_EDITING_FPS[0],
            fps_locked=bool(timeline.clips),
        ),
        persisted=True,
        read_only=True,
        status="invalid",
        error=error,
    )


def _is_supported_fps(value: object) -> TypeGuard[int]:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value in SUPPORTED_EDITING_FPS
    )


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if number > 0 and math.isfinite(number) else None
