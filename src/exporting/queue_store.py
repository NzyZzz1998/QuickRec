"""导出队列模型、版本化 JSON、备份与损坏恢复。"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from exporting.models import (
    ExportFailureKind,
    ExportPlan,
    ExportStage,
    ExportValidationError,
)

QUEUE_SCHEMA_VERSION = 1
QUEUE_FILE_NAME = "queue.json"


class AttemptTrigger(StrEnum):
    INITIAL = "initial"
    AUTOMATIC = "automatic"
    MANUAL = "manual"


class IngestionStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NOT_REQUIRED = "not_required"


class QueueLoadStatus(StrEnum):
    MISSING = "missing"
    LOADED = "loaded"
    RECOVERED = "recovered"
    CORRUPT = "corrupt"
    FUTURE_READ_ONLY = "future_read_only"


@dataclass(frozen=True)
class ExportAttempt:
    attempt_id: str
    sequence: int
    trigger: AttemptTrigger
    status: ExportStage
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    failure_kind: ExportFailureKind | None = None
    message: str = ""
    diagnostic_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "sequence": self.sequence,
            "trigger": self.trigger.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "failure_kind": (
                self.failure_kind.value
                if self.failure_kind is not None
                else None
            ),
            "message": self.message,
            "diagnostic_path": self.diagnostic_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportAttempt:
        try:
            trigger = AttemptTrigger(_required_text(data, "trigger"))
            status = ExportStage(_required_text(data, "status"))
            failure_kind = (
                ExportFailureKind(str(data["failure_kind"]))
                if data.get("failure_kind") is not None
                else None
            )
        except ValueError as exc:
            raise ExportValidationError("invalid export attempt state") from exc
        sequence = _required_int(data, "sequence")
        if sequence <= 0:
            raise ExportValidationError("attempt sequence must be positive")
        return cls(
            attempt_id=_required_text(data, "attempt_id"),
            sequence=sequence,
            trigger=trigger,
            status=status,
            created_at=_required_text(data, "created_at"),
            started_at=_optional_text(data.get("started_at")),
            completed_at=_optional_text(data.get("completed_at")),
            failure_kind=failure_kind,
            message=str(data.get("message") or ""),
            diagnostic_path=_optional_text(data.get("diagnostic_path")),
        )


@dataclass(frozen=True)
class ExportJob:
    job_id: str
    plan: ExportPlan
    status: ExportStage
    created_at: str
    updated_at: str
    attempts: tuple[ExportAttempt, ...] = ()
    progress_percent: int = 0
    eta_seconds: float | None = None
    output_path: str | None = None
    ingestion_status: IngestionStatus = IngestionStatus.PENDING
    ingestion_error: str = ""
    failure_kind: ExportFailureKind | None = None
    message: str = ""
    next_attempt_trigger: AttemptTrigger = AttemptTrigger.INITIAL
    stalled: bool = False

    @property
    def is_incomplete(self) -> bool:
        return self.status not in {
            ExportStage.SUCCEEDED,
            ExportStage.CANCELLED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "plan": self.plan.to_dict(),
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "progress_percent": self.progress_percent,
            "eta_seconds": self.eta_seconds,
            "output_path": self.output_path,
            "ingestion_status": self.ingestion_status.value,
            "ingestion_error": self.ingestion_error,
            "failure_kind": (
                self.failure_kind.value
                if self.failure_kind is not None
                else None
            ),
            "message": self.message,
            "next_attempt_trigger": self.next_attempt_trigger.value,
            "stalled": self.stalled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportJob:
        plan_data = data.get("plan")
        raw_attempts = data.get("attempts", [])
        if not isinstance(plan_data, dict) or not isinstance(raw_attempts, list):
            raise ExportValidationError("invalid export job payload")
        try:
            status = ExportStage(_required_text(data, "status"))
            ingestion_status = IngestionStatus(
                str(data.get("ingestion_status") or IngestionStatus.PENDING.value)
            )
            failure_kind = (
                ExportFailureKind(str(data["failure_kind"]))
                if data.get("failure_kind") is not None
                else None
            )
            next_attempt_trigger = AttemptTrigger(
                str(
                    data.get("next_attempt_trigger")
                    or AttemptTrigger.INITIAL.value
                )
            )
        except ValueError as exc:
            raise ExportValidationError("invalid export job state") from exc
        attempts = tuple(
            ExportAttempt.from_dict(_object(item, "attempt"))
            for item in raw_attempts
        )
        attempt_ids = {attempt.attempt_id for attempt in attempts}
        sequences = {attempt.sequence for attempt in attempts}
        if len(attempt_ids) != len(attempts) or len(sequences) != len(attempts):
            raise ExportValidationError("duplicate export attempt identity")
        progress = _optional_int(data.get("progress_percent"), default=0)
        if progress < 0 or progress > 100:
            raise ExportValidationError("job progress must be between 0 and 100")
        eta = _optional_float(data.get("eta_seconds"))
        if eta is not None and eta < 0:
            raise ExportValidationError("job ETA must be non-negative")
        return cls(
            job_id=_required_text(data, "job_id"),
            plan=ExportPlan.from_dict(plan_data),
            status=status,
            created_at=_required_text(data, "created_at"),
            updated_at=_required_text(data, "updated_at"),
            attempts=attempts,
            progress_percent=progress,
            eta_seconds=eta,
            output_path=_optional_text(data.get("output_path")),
            ingestion_status=ingestion_status,
            ingestion_error=str(data.get("ingestion_error") or ""),
            failure_kind=failure_kind,
            message=str(data.get("message") or ""),
            next_attempt_trigger=next_attempt_trigger,
            stalled=bool(data.get("stalled", False)),
        )


@dataclass(frozen=True)
class ExportQueueState:
    schema_version: int
    paused: bool
    updated_at: str
    jobs: tuple[ExportJob, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "paused": self.paused,
            "updated_at": self.updated_at,
            "jobs": [job.to_dict() for job in self.jobs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportQueueState:
        version = _required_int(data, "schema_version")
        if version != QUEUE_SCHEMA_VERSION:
            raise ExportValidationError(
                f"unsupported export queue schema: {version}"
            )
        raw_jobs = data.get("jobs", [])
        if not isinstance(raw_jobs, list):
            raise ExportValidationError("queue jobs must be an array")
        jobs = tuple(
            ExportJob.from_dict(_object(item, "job")) for item in raw_jobs
        )
        job_ids = {job.job_id for job in jobs}
        if len(job_ids) != len(jobs):
            raise ExportValidationError("duplicate export job identity")
        return cls(
            schema_version=version,
            paused=bool(data.get("paused", True)),
            updated_at=_required_text(data, "updated_at"),
            jobs=jobs,
        )


@dataclass(frozen=True)
class QueueJobSummary:
    job_id: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class QueueLoadResult:
    ok: bool
    status: QueueLoadStatus
    path: Path
    state: ExportQueueState | None = None
    read_only: bool = False
    summaries: tuple[QueueJobSummary, ...] = ()
    error: str = ""
    recovered: bool = False
    corrupt_path: Path | None = None


@dataclass(frozen=True)
class QueueWriteResult:
    ok: bool
    path: Path
    stage: str = "complete"
    error: str = ""
    read_only: bool = False


def resolve_export_queue_file(
    appdata_dir: str | Path | None = None,
) -> Path:
    root = (
        Path(appdata_dir)
        if appdata_dir is not None
        else Path(os.getenv("APPDATA") or Path.home())
    )
    return root / "QuickRec" / "Exports" / QUEUE_FILE_NAME


class ExportQueueStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = (
            Path(path) if path is not None else resolve_export_queue_file()
        )
        self._read_only = False

    def load(self) -> QueueLoadResult:
        if not self.path.exists():
            self._read_only = False
            return QueueLoadResult(
                True,
                QueueLoadStatus.MISSING,
                self.path,
                state=_empty_state(),
            )
        try:
            raw = _read_json_object(self.path)
        except (OSError, ValueError, json.JSONDecodeError) as main_error:
            return self._recover_corrupt(main_error)
        version = _schema_version(raw)
        if version > QUEUE_SCHEMA_VERSION:
            self._read_only = True
            return QueueLoadResult(
                True,
                QueueLoadStatus.FUTURE_READ_ONLY,
                self.path,
                read_only=True,
                summaries=_future_summaries(raw),
                error=f"future queue schema {version} is read-only",
            )
        try:
            state = ExportQueueState.from_dict(raw)
        except (TypeError, ValueError, ExportValidationError) as main_error:
            return self._recover_corrupt(main_error)
        self._read_only = False
        return QueueLoadResult(
            True,
            QueueLoadStatus.LOADED,
            self.path,
            state=state,
        )

    def save(self, state: ExportQueueState) -> QueueWriteResult:
        try:
            validated = ExportQueueState.from_dict(state.to_dict())
        except (TypeError, ValueError, ExportValidationError) as exc:
            return QueueWriteResult(
                False,
                self.path,
                stage="validate",
                error=str(exc),
            )
        if self._read_only or _path_has_future_schema(self.path):
            self._read_only = True
            return QueueWriteResult(
                False,
                self.path,
                stage="read_only",
                error="future queue schema is read-only",
                read_only=True,
            )
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.is_file():
                current = _read_queue_state(self.path)
                if current is not None:
                    _atomic_copy(
                        self.path,
                        self.path.with_name(f"{self.path.name}.bak"),
                    )
            _atomic_write_json(self.path, validated.to_dict())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return QueueWriteResult(
                False,
                self.path,
                stage="write",
                error=f"{type(exc).__name__}: {exc}",
            )
        return QueueWriteResult(True, self.path)

    def reset_corrupt_queue(self, *, confirmed: bool) -> QueueWriteResult:
        if not confirmed:
            return QueueWriteResult(
                False,
                self.path,
                stage="confirmation",
                error="explicit confirmation is required",
                read_only=True,
            )
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = self.path.with_name(f"{self.path.name}.bak")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                os.replace(
                    self.path,
                    self.path.with_name(
                        f"{self.path.name}.abandoned-{timestamp}"
                    ),
                )
            if backup.exists():
                os.replace(
                    backup,
                    backup.with_name(
                        f"{backup.name}.abandoned-{timestamp}"
                    ),
                )
            self._read_only = False
            return self.save(_empty_state())
        except OSError as exc:
            self._read_only = True
            return QueueWriteResult(
                False,
                self.path,
                stage="reset",
                error=f"{type(exc).__name__}: {exc}",
                read_only=True,
            )

    def _recover_corrupt(self, main_error: Exception) -> QueueLoadResult:
        backup = self.path.with_name(f"{self.path.name}.bak")
        backup_state = _read_queue_state(backup) if backup.is_file() else None
        if backup_state is None:
            self._read_only = True
            return QueueLoadResult(
                False,
                QueueLoadStatus.CORRUPT,
                self.path,
                read_only=True,
                error=str(main_error),
            )
        try:
            corrupt_path = _archive_corrupt_file(self.path)
            _atomic_copy(backup, self.path)
        except OSError as exc:
            self._read_only = True
            return QueueLoadResult(
                False,
                QueueLoadStatus.CORRUPT,
                self.path,
                read_only=True,
                error=f"queue recovery failed: {type(exc).__name__}",
            )
        self._read_only = False
        return QueueLoadResult(
            True,
            QueueLoadStatus.RECOVERED,
            self.path,
            state=backup_state,
            recovered=True,
            corrupt_path=corrupt_path,
            error=str(main_error),
        )


def _empty_state() -> ExportQueueState:
    return ExportQueueState(
        schema_version=QUEUE_SCHEMA_VERSION,
        paused=True,
        updated_at=datetime.now().astimezone().isoformat(),
        jobs=(),
    )


def _read_queue_state(path: Path) -> ExportQueueState | None:
    try:
        payload = _read_json_object(path)
        if _schema_version(payload) != QUEUE_SCHEMA_VERSION:
            return None
        return ExportQueueState.from_dict(payload)
    except (OSError, ValueError, json.JSONDecodeError, ExportValidationError):
        return None


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("queue root must be an object")
    return payload


def _schema_version(payload: dict[str, Any]) -> int:
    value = payload.get("schema_version")
    if value is None or isinstance(value, bool):
        raise ValueError("queue schema version must be an integer")
    return int(value)


def _path_has_future_schema(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        return _schema_version(_read_json_object(path)) > QUEUE_SCHEMA_VERSION
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _future_summaries(payload: dict[str, Any]) -> tuple[QueueJobSummary, ...]:
    raw_jobs = payload.get("jobs", [])
    if not isinstance(raw_jobs, list):
        return ()
    summaries: list[QueueJobSummary] = []
    for raw in raw_jobs:
        if not isinstance(raw, dict):
            continue
        job_id = str(raw.get("job_id") or "").strip()
        if not job_id:
            continue
        summaries.append(
            QueueJobSummary(
                job_id=job_id,
                status=str(raw.get("status") or "unknown"),
                created_at=str(raw.get("created_at") or ""),
                updated_at=str(raw.get("updated_at") or ""),
            )
        )
    return tuple(summaries)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_copy(source: Path, destination: Path) -> None:
    temporary = destination.with_name(
        f".{destination.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        shutil.copy2(source, temporary)
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _archive_corrupt_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    archive = path.with_name(
        f"{path.stem}.corrupt-{timestamp}{path.suffix}"
    )
    shutil.copy2(path, archive)
    return archive


def _required_text(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ExportValidationError(f"{key} is required")
    return value


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if value is None or isinstance(value, bool):
        raise ExportValidationError(f"{key} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ExportValidationError(f"{key} must be an integer") from exc


def _optional_int(value: Any, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ExportValidationError("value must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ExportValidationError("value must be an integer") from exc


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ExportValidationError("value must be a number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ExportValidationError("value must be a number") from exc


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExportValidationError(f"{name} must be an object")
    return value
