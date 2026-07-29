from __future__ import annotations

from pathlib import Path

import pytest

from services.project_library import ProjectOperationResult
from services.project_save_coordinator import (
    ProjectSaveCoordinator,
    ProjectSaveState,
)
from utils.project_store import ProjectFile


class FakeProjectService:
    def __init__(self) -> None:
        self.results: list[ProjectOperationResult] = []
        self.commits: list[tuple[str, ProjectFile, int | None]] = []

    def commit_project_candidate(
        self,
        project_id: str,
        candidate: ProjectFile,
        *,
        expected_modified_ns: int | None = None,
    ) -> ProjectOperationResult:
        self.commits.append(
            (project_id, candidate, expected_modified_ns)
        )
        if self.results:
            return self.results.pop(0)
        return _result(True, candidate=candidate)


def _project() -> ProjectFile:
    return ProjectFile(
        project_id="project-1",
        name="Project",
        description="",
        created_at="2026-07-28T10:00:00+08:00",
        updated_at="2026-07-28T10:00:00+08:00",
    )


def _result(
    ok: bool,
    *,
    stage: str = "complete",
    candidate: ProjectFile | None = None,
    error: str = "",
) -> ProjectOperationResult:
    return ProjectOperationResult(
        ok=ok,
        stage=stage,
        path=Path("project.qrproj"),
        project=candidate,
        error=error,
    )


def test_immediate_save_moves_dirty_revision_to_clean_persisted_revision() -> None:
    service = FakeProjectService()
    coordinator = ProjectSaveCoordinator(service, "project-1")
    project = _project()

    revision = coordinator.begin_change("add_track")
    dirty = coordinator.snapshot
    result = coordinator.save(
        revision,
        project,
        expected_modified_ns=42,
    )

    assert result.ok
    assert service.commits == [("project-1", project, 42)]
    assert dirty.state == ProjectSaveState.DIRTY
    assert dirty.dirty is True
    assert coordinator.snapshot.state == ProjectSaveState.CLEAN
    assert coordinator.snapshot.dirty is False
    assert coordinator.snapshot.revision == revision
    assert coordinator.snapshot.persisted_revision == revision
    assert coordinator.snapshot.operation == "add_track"


def test_failed_save_stays_dirty_and_retry_reuses_same_revision() -> None:
    service = FakeProjectService()
    service.results = [
        _result(False, stage="index", error="index denied"),
        _result(True, candidate=_project()),
    ]
    coordinator = ProjectSaveCoordinator(service, "project-1")
    project = _project()

    revision = coordinator.begin_change("move_clip")
    failed = coordinator.save(revision, project)

    assert not failed.ok
    assert coordinator.snapshot.state == ProjectSaveState.FAILED
    assert coordinator.snapshot.dirty is True
    assert coordinator.snapshot.failure_stage == "index"
    assert coordinator.snapshot.error == "index denied"

    retried = coordinator.save(revision, project)
    assert retried.ok
    assert coordinator.snapshot.state == ProjectSaveState.CLEAN
    assert coordinator.snapshot.revision == revision
    assert coordinator.snapshot.persisted_revision == revision


def test_external_conflict_has_distinct_state() -> None:
    service = FakeProjectService()
    service.results = [
        _result(
            False,
            stage="external_conflict",
            error="project changed",
        )
    ]
    coordinator = ProjectSaveCoordinator(service, "project-1")

    revision = coordinator.begin_change("rename_track")
    result = coordinator.save(revision, _project())

    assert not result.ok
    assert coordinator.snapshot.state == ProjectSaveState.CONFLICT
    assert coordinator.snapshot.dirty is True


def test_failed_change_must_be_retried_or_discarded_before_new_change() -> None:
    service = FakeProjectService()
    service.results = [_result(False, stage="project", error="denied")]
    coordinator = ProjectSaveCoordinator(service, "project-1")
    revision = coordinator.begin_change("delete_clip")
    coordinator.save(revision, _project())

    with pytest.raises(RuntimeError, match="pending save"):
        coordinator.begin_change("add_track")

    coordinator.discard(revision)
    next_revision = coordinator.begin_change("add_track")

    assert next_revision == revision + 1
    assert coordinator.snapshot.state == ProjectSaveState.DIRTY


def test_stale_revision_is_rejected_without_calling_storage() -> None:
    service = FakeProjectService()
    coordinator = ProjectSaveCoordinator(service, "project-1")
    revision = coordinator.begin_change("add_track")

    with pytest.raises(RuntimeError, match="revision"):
        coordinator.save(revision + 1, _project())

    assert service.commits == []
    assert coordinator.snapshot.state == ProjectSaveState.DIRTY
