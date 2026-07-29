from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from services.project_library import ProjectLibraryService
from services.timeline_commands import TimelineCommandService
from utils.project_store import (
    ProjectFile,
    ProjectMaterialRef,
    ProjectWriteResult,
    load_project,
)
from utils.timeline_model import (
    TIMELINE_EXTENSION_KEY,
    TIMELINE_SCHEMA_VERSION,
    Timeline,
    TimelineValidationError,
    load_project_timeline,
    serialize_timeline,
    upgrade_timeline_for_v2_edit,
    validate_timeline,
    with_project_timeline,
)

FIXTURES = Path(__file__).parent / "fixtures" / "v1_9_3"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _project(raw_timeline: dict[str, object]) -> ProjectFile:
    return ProjectFile(
        project_id="project-v193",
        name="v1.9.3 schema",
        description="",
        created_at="2026-07-29T00:00:00+08:00",
        updated_at="2026-07-29T00:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=r"E:\QRtest\中文 空格\source.mp4",
                file_name="source.mp4",
                added_at="2026-07-29T00:00:00+08:00",
                metadata_snapshot={"duration_sec": 10.0},
            )
        ],
        extensions={
            TIMELINE_EXTENSION_KEY: copy.deepcopy(raw_timeline),
            "future.project": {"preserve": True},
        },
    )


def _command_session(
    tmp_path: Path,
    raw_timeline: dict[str, object],
) -> tuple[TimelineCommandService, Path]:
    service = ProjectLibraryService(tmp_path / "projects.json")
    created = service.create_project(
        name="v1 schema project",
        root_path=tmp_path / "projects",
        project_id="project-v193",
        now="2026-07-29T00:00:00+08:00",
    )
    assert created.ok
    added = service.add_material(
        "project-v193",
        _project(raw_timeline).materials[0],
        now="2026-07-29T00:00:01+08:00",
    )
    assert added.ok
    loaded = service.get_project("project-v193")
    entry = service.get_entry("project-v193")
    assert loaded.ok and loaded.project is not None and entry is not None
    loaded.project.extensions.update(
        {
            TIMELINE_EXTENSION_KEY: copy.deepcopy(raw_timeline),
            "future.project": {"preserve": True},
        }
    )
    committed = service.commit_project_candidate(
        "project-v193",
        loaded.project,
        expected_modified_ns=entry.file_modified_ns,
    )
    assert committed.ok
    return TimelineCommandService(service, "project-v193"), created.path


def test_v1_load_is_in_memory_only_and_keeps_v1_contract() -> None:
    raw = _fixture("timeline_v1.json")
    project = _project(raw)
    before = copy.deepcopy(project.extensions)

    result = load_project_timeline(project)

    assert result.ok and result.timeline is not None
    assert result.timeline.schema_version == 1
    assert all(not track.locked for track in result.timeline.tracks)
    assert project.extensions == before
    payload = serialize_timeline(result.timeline, project)
    assert payload["schema_version"] == 1
    assert all("locked" not in track for track in payload["tracks"])


def test_v1_upgrade_builds_v2_candidate_without_mutating_source() -> None:
    raw = _fixture("timeline_v1.json")
    project = _project(raw)
    loaded = load_project_timeline(project)
    assert loaded.ok and loaded.timeline is not None
    before = copy.deepcopy(loaded.timeline)

    candidate = upgrade_timeline_for_v2_edit(loaded.timeline, project)

    assert candidate.schema_version == TIMELINE_SCHEMA_VERSION == 2
    assert all(not track.locked for track in candidate.tracks)
    assert loaded.timeline == before
    payload = candidate.to_dict()
    assert payload["future_timeline_field"] == {"preserve": True}
    assert payload["tracks"][0]["future_track_field"] == 7
    assert payload["clips"][0]["future_clip_field"] == 11
    assert payload["tracks"][0]["extensions"] == {
        "track_extension": "保留"
    }


def test_v2_accepts_partial_source_range_and_persists_track_lock() -> None:
    raw = _fixture("timeline_v2.json")
    project = _project(raw)

    result = load_project_timeline(project)

    assert result.ok and result.timeline is not None
    timeline = result.timeline
    assert timeline.schema_version == 2
    assert timeline.tracks[0].locked
    assert timeline.clips[0].source_start_us == 2_000_000
    assert timeline.clips[0].source_duration_us == 4_000_000
    payload = serialize_timeline(timeline, project)
    assert payload["tracks"][0]["locked"] is True
    assert payload["future_timeline_field"] == {"preserve": True}


def test_v1_rejects_partial_source_range() -> None:
    raw = _fixture("timeline_v1.json")
    raw["clips"][0]["source_start_us"] = 1
    project = _project(raw)

    result = load_project_timeline(project)

    assert not result.ok
    assert result.status == "corrupt"
    assert "schema v1" in result.error


def test_v2_rejects_source_range_outside_material() -> None:
    raw = _fixture("timeline_v2_corrupt.json")
    project = _project(raw)

    result = load_project_timeline(project)

    assert not result.ok
    assert result.status == "corrupt"
    assert "source duration range" in result.error


def test_v2_link_group_requires_matching_source_range() -> None:
    raw = _fixture("timeline_v2.json")
    raw["clips"][1]["source_start_us"] = 2_000_001
    project = _project(raw)

    result = load_project_timeline(project)

    assert not result.ok
    assert "matching durations" in result.error


def test_v2_roundtrip_preserves_other_project_extensions() -> None:
    raw = _fixture("timeline_v2.json")
    project = _project(raw)
    loaded = load_project_timeline(project)
    assert loaded.ok and loaded.timeline is not None

    candidate = with_project_timeline(project, loaded.timeline)

    assert candidate.extensions["future.project"] == {"preserve": True}
    assert candidate.extensions[TIMELINE_EXTENSION_KEY][
        "future_timeline_field"
    ] == {"preserve": True}
    assert project.extensions[TIMELINE_EXTENSION_KEY] == raw


def test_future_schema_is_read_only_and_raw_payload_survives() -> None:
    raw = _fixture("timeline_v99.json")
    project = _project(raw)

    result = load_project_timeline(project)

    assert not result.ok
    assert result.status == "unsupported"
    assert result.read_only
    assert result.raw_extension == raw
    assert project.extensions[TIMELINE_EXTENSION_KEY] == raw


def test_v2_parser_rejects_non_boolean_locked_without_mutation() -> None:
    raw = _fixture("timeline_v2.json")
    raw["tracks"][0]["locked"] = "yes"
    project = _project(raw)
    before = copy.deepcopy(project.extensions)

    result = load_project_timeline(project)

    assert not result.ok
    assert "locked" in result.error
    assert project.extensions == before


def test_upgrade_rejects_corrupt_v1_without_mutating_timeline() -> None:
    raw = _fixture("timeline_v1.json")
    project = _project(raw)
    loaded = load_project_timeline(project)
    assert loaded.ok and loaded.timeline is not None
    loaded.timeline.clips[0].timeline_duration_us = 1
    before = copy.deepcopy(loaded.timeline)

    with pytest.raises(TimelineValidationError):
        validate_timeline(loaded.timeline, project)

    assert loaded.timeline == before


def test_v2_serialization_keeps_timeline_duration_equal_to_source() -> None:
    raw = _fixture("timeline_v2.json")
    project = _project(raw)
    timeline = Timeline.from_dict(raw)
    timeline.clips[0].timeline_duration_us += 1

    with pytest.raises(TimelineValidationError, match="timeline duration"):
        serialize_timeline(timeline, project)


def test_v1_compatible_track_rename_stays_on_schema_v1(
    tmp_path: Path,
) -> None:
    session, project_path = _command_session(
        tmp_path,
        _fixture("timeline_v1.json"),
    )

    result = session.rename_track("video-1", "兼容改名")
    loaded = load_project(project_path)
    assert loaded.ok and loaded.project is not None
    persisted = load_project_timeline(loaded.project)

    assert result.ok
    assert persisted.ok and persisted.timeline is not None
    assert persisted.timeline.schema_version == 1
    assert persisted.timeline.tracks[0].name == "兼容改名"
    raw = loaded.project.extensions[TIMELINE_EXTENSION_KEY]
    assert all("locked" not in track for track in raw["tracks"])


def test_first_track_lock_atomically_upgrades_v1_and_keeps_v1_backup(
    tmp_path: Path,
) -> None:
    session, project_path = _command_session(
        tmp_path,
        _fixture("timeline_v1.json"),
    )

    result = session.set_track_locked("video-1", True)
    loaded = load_project(project_path)
    backup = load_project(project_path.with_name(f"{project_path.name}.bak"))

    assert result.ok and result.saved
    assert session.timeline.schema_version == 2
    assert session.timeline.tracks[0].locked
    assert loaded.ok and loaded.project is not None
    current = load_project_timeline(loaded.project)
    assert current.ok and current.timeline is not None
    assert current.timeline.schema_version == 2
    assert current.timeline.tracks[0].locked
    assert loaded.project.extensions["future.project"] == {"preserve": True}
    assert backup.ok and backup.project is not None
    previous = load_project_timeline(backup.project)
    assert previous.ok and previous.timeline is not None
    assert previous.timeline.schema_version == 1


def test_failed_first_v2_edit_keeps_memory_file_and_history_unchanged(
    tmp_path: Path,
) -> None:
    session, project_path = _command_session(
        tmp_path,
        _fixture("timeline_v1.json"),
    )
    before_timeline = session.timeline
    before_bytes = project_path.read_bytes()
    before_undo = session.undo_depth

    with patch(
        "services.project_library.save_project",
        return_value=ProjectWriteResult(
            False,
            project_path,
            stage="write",
            error="injected failure",
        ),
    ):
        result = session.set_track_locked("video-1", True)

    assert not result.ok
    assert session.timeline == before_timeline
    assert session.timeline.schema_version == 1
    assert session.undo_depth == before_undo
    assert project_path.read_bytes() == before_bytes


def test_first_trim_atomically_migrates_v1_and_undo_restores_v1(
    tmp_path: Path,
) -> None:
    session, project_path = _command_session(
        tmp_path,
        _fixture("timeline_v1.json"),
    )
    before = session.timeline
    candidate = session.preview_trim_clip(
        "video-clip-1",
        source_start_us=0,
        source_end_us=9_000_000,
    )

    committed = session.commit_edit_candidate(
        candidate,
        now="2026-07-29T12:10:00+08:00",
    )
    diagnostics = session.diagnostic_summary()

    assert candidate.valid
    assert committed.ok
    assert diagnostics["migration_source_schema"] == 1
    assert diagnostics["migration_target_schema"] == 2
    assert diagnostics["migration_result"] == "complete"
    assert session.timeline.schema_version == 2
    assert session.timeline.clips[0].source_duration_us == 9_000_000
    backup = load_project(project_path.with_name(f"{project_path.name}.bak"))
    assert backup.ok and backup.project is not None
    backup_timeline = load_project_timeline(backup.project)
    assert backup_timeline.ok and backup_timeline.timeline == before

    undone = session.undo(now="2026-07-29T12:10:01+08:00")

    assert undone.ok
    assert session.timeline == before
    assert session.timeline.schema_version == 1

    redone = session.redo(now="2026-07-29T12:10:02+08:00")

    assert redone.ok
    assert session.timeline.schema_version == 2
    assert session.timeline.clips[0].source_duration_us == 9_000_000
