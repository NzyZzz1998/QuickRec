from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from services.project_library import (
    ProjectLibraryService,
    ProjectOperationResult,
)
from utils.project_store import ProjectFile

logger = logging.getLogger("QuickRec")


class ProjectSaveState(StrEnum):
    CLEAN = "clean"
    DIRTY = "dirty"
    SAVING = "saving"
    FAILED = "failed"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class ProjectSaveSnapshot:
    state: ProjectSaveState = ProjectSaveState.CLEAN
    revision: int = 0
    persisted_revision: int = 0
    operation: str = ""
    failure_stage: str = ""
    error: str = ""
    elapsed_ms: float = 0.0

    @property
    def dirty(self) -> bool:
        return self.state != ProjectSaveState.CLEAN


class ProjectSaveCoordinator:
    """Track one project's synchronous, ordered save lifecycle."""

    def __init__(
        self,
        project_service: ProjectLibraryService,
        project_id: str,
        *,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._project_service = project_service
        self._project_id = str(project_id)
        self._monotonic_ns = monotonic_ns
        self._revision = 0
        self._persisted_revision = 0
        self._active_revision: int | None = None
        self._snapshot = ProjectSaveSnapshot()

    @property
    def snapshot(self) -> ProjectSaveSnapshot:
        return self._snapshot

    def begin_change(self, operation: str) -> int:
        if self._active_revision is not None:
            raise RuntimeError(
                "resolve the pending save before starting another change"
            )
        self._revision += 1
        self._active_revision = self._revision
        self._snapshot = ProjectSaveSnapshot(
            state=ProjectSaveState.DIRTY,
            revision=self._revision,
            persisted_revision=self._persisted_revision,
            operation=str(operation),
        )
        return self._revision

    def save(
        self,
        revision: int,
        candidate: ProjectFile,
        *,
        expected_modified_ns: int | None = None,
    ) -> ProjectOperationResult:
        self._require_active_revision(revision)
        operation = self._snapshot.operation
        self._snapshot = ProjectSaveSnapshot(
            state=ProjectSaveState.SAVING,
            revision=revision,
            persisted_revision=self._persisted_revision,
            operation=operation,
        )
        started_ns = self._monotonic_ns()
        try:
            result = self._project_service.commit_project_candidate(
                self._project_id,
                candidate,
                expected_modified_ns=expected_modified_ns,
            )
        except Exception as exc:
            elapsed_ms = self._elapsed_ms(started_ns)
            self._snapshot = ProjectSaveSnapshot(
                state=ProjectSaveState.FAILED,
                revision=revision,
                persisted_revision=self._persisted_revision,
                operation=operation,
                failure_stage="exception",
                error=str(exc),
                elapsed_ms=elapsed_ms,
            )
            logger.exception(
                "project save raised: project_id=%s operation=%s "
                "revision=%d elapsed_ms=%.3f",
                self._project_id,
                operation,
                revision,
                elapsed_ms,
            )
            raise

        elapsed_ms = self._elapsed_ms(started_ns)
        if result.ok:
            self._persisted_revision = revision
            self._active_revision = None
            state = ProjectSaveState.CLEAN
            failure_stage = ""
            error = ""
        else:
            state = (
                ProjectSaveState.CONFLICT
                if result.stage == "external_conflict"
                else ProjectSaveState.FAILED
            )
            failure_stage = result.stage
            error = result.error
        self._snapshot = ProjectSaveSnapshot(
            state=state,
            revision=revision,
            persisted_revision=self._persisted_revision,
            operation=operation,
            failure_stage=failure_stage,
            error=error,
            elapsed_ms=elapsed_ms,
        )
        logger.info(
            "project save coordinated: project_id=%s operation=%s "
            "revision=%d state=%s stage=%s elapsed_ms=%.3f",
            self._project_id,
            operation,
            revision,
            state.value,
            result.stage,
            elapsed_ms,
        )
        return result

    def discard(self, revision: int) -> None:
        self._require_active_revision(revision)
        self._active_revision = None
        self._snapshot = ProjectSaveSnapshot(
            state=ProjectSaveState.CLEAN,
            revision=self._revision,
            persisted_revision=self._persisted_revision,
            operation=self._snapshot.operation,
        )

    def reset(self) -> None:
        self._active_revision = None
        self._persisted_revision = self._revision
        self._snapshot = ProjectSaveSnapshot(
            state=ProjectSaveState.CLEAN,
            revision=self._revision,
            persisted_revision=self._persisted_revision,
        )

    def _require_active_revision(self, revision: int) -> None:
        if revision != self._active_revision:
            raise RuntimeError(
                f"save revision mismatch: expected "
                f"{self._active_revision}, received {revision}"
            )

    def _elapsed_ms(self, started_ns: int) -> float:
        return (self._monotonic_ns() - started_ns) / 1_000_000
