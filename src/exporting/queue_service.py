"""单工作执行入口、持久状态机、取消、重试与启动恢复。"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from exporting.committer import (
    CommitRecoveryResult,
    CommitRecoveryStatus,
    ExportCommitter,
    recover_export_transactions,
)
from exporting.executor import (
    CancellationToken,
    ExportExecutor,
    ExportProgressSnapshot,
)
from exporting.models import (
    ExportFailureKind,
    ExportPlan,
    ExportStage,
)
from exporting.queue_store import (
    QUEUE_SCHEMA_VERSION,
    AttemptTrigger,
    ExportAttempt,
    ExportJob,
    ExportQueueState,
    ExportQueueStore,
    IngestionStatus,
    QueueLoadResult,
)
from exporting.temp_cleanup import (
    ExportTempArtifactOwner,
    ExportTempCleanupReport,
    cleanup_export_attempt,
)
from exporting.verifier import ExportVerifier
from services.media_operation_guard import MediaOperationGuard
from utils.recording_library_store import normalize_windows_path

MAX_INCOMPLETE_JOBS = 20
MAX_ATTEMPTS = 5
AUTO_RETRY_DELAY_SECONDS = 5.0
_ACTIVE_STAGES = {
    ExportStage.VALIDATING,
    ExportStage.RUNNING,
    ExportStage.CANCELLING,
    ExportStage.VERIFYING,
    ExportStage.COMMITTING,
}
_CANCELLABLE_ACTIVE_STAGES = {
    ExportStage.VALIDATING,
    ExportStage.RUNNING,
    ExportStage.CANCELLING,
    ExportStage.VERIFYING,
}
_AUTO_RETRYABLE = {
    ExportFailureKind.TOOL_START_FAILED,
    ExportFailureKind.DISK_ERROR,
}

StageCallback = Callable[[ExportStage], None]
ProgressCallback = Callable[[ExportProgressSnapshot], None]
TransactionRecoverer = Callable[[Path], tuple[CommitRecoveryResult, ...]]
SucceededListener = Callable[[ExportJob], None]
TerminalListener = Callable[[ExportJob], None]


@dataclass(frozen=True)
class ExportAttemptResult:
    status: ExportStage
    failure_kind: ExportFailureKind | None = None
    message: str = ""
    target_path: Path | None = None
    exit_code: int | None = None
    stderr_tail: str = ""


class AttemptRunner(Protocol):
    def run(
        self,
        plan: ExportPlan,
        *,
        attempt_id: str,
        cancel_token: CancellationToken,
        on_progress: ProgressCallback,
        on_stage: StageCallback,
    ) -> ExportAttemptResult: ...


@dataclass(frozen=True)
class QueueOperationResult:
    ok: bool
    message: str = ""
    job: ExportJob | None = None
    read_only: bool = False


@dataclass(frozen=True)
class QueueRunResult:
    started: bool
    job_id: str | None = None
    status: ExportStage | None = None
    message: str = ""


class ExportAttemptRunner:
    """将正式执行、验证和提交服务串为一次可追踪尝试。"""

    def __init__(
        self,
        *,
        executor: ExportExecutor | None = None,
        verifier: ExportVerifier | None = None,
        committer: ExportCommitter | None = None,
    ) -> None:
        self._executor = executor or ExportExecutor()
        self._verifier = verifier or ExportVerifier()
        self._committer = committer or ExportCommitter(
            output_verifier=self._verifier.verify_output
        )

    def run(
        self,
        plan: ExportPlan,
        *,
        attempt_id: str,
        cancel_token: CancellationToken,
        on_progress: ProgressCallback,
        on_stage: StageCallback,
    ) -> ExportAttemptResult:
        on_stage(ExportStage.VALIDATING)
        execution = self._executor.execute(
            plan,
            attempt_id=attempt_id,
            cancel_token=cancel_token,
            on_progress=on_progress,
        )
        if not execution.ok or execution.temp_output_path is None:
            return ExportAttemptResult(
                execution.stage,
                failure_kind=execution.failure_kind,
                message=execution.message,
                exit_code=execution.exit_code,
                stderr_tail=execution.stderr_tail,
            )
        candidate = execution.temp_output_path
        if cancel_token.is_cancelled:
            candidate.unlink(missing_ok=True)
            return ExportAttemptResult(
                ExportStage.CANCELLED,
                failure_kind=ExportFailureKind.CANCELLED,
                message="export cancelled before verification",
            )
        on_stage(ExportStage.VERIFYING)
        verification = self._verifier.verify_output(plan, candidate)
        if not verification.ok:
            candidate.unlink(missing_ok=True)
            return ExportAttemptResult(
                ExportStage.FAILED,
                failure_kind=(
                    verification.failure_kind
                    or ExportFailureKind.VERIFICATION_FAILED
                ),
                message=verification.message,
            )
        materials = self._verifier.verify_materials(plan)
        if not materials.ok:
            candidate.unlink(missing_ok=True)
            return ExportAttemptResult(
                ExportStage.FAILED,
                failure_kind=(
                    materials.failure_kind
                    or ExportFailureKind.MATERIAL_CHANGED
                ),
                message=materials.message,
            )
        if cancel_token.is_cancelled:
            candidate.unlink(missing_ok=True)
            return ExportAttemptResult(
                ExportStage.CANCELLED,
                failure_kind=ExportFailureKind.CANCELLED,
                message="export cancelled before commit",
            )
        on_stage(ExportStage.COMMITTING)
        committed = self._committer.commit(
            plan,
            candidate,
            attempt_id=attempt_id,
        )
        if not committed.ok:
            message = committed.message
            if committed.transaction_path is None:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError as exc:
                    cleanup_error = (
                        f"candidate cleanup failed: {type(exc).__name__}"
                    )
                    message = (
                        f"{message}; {cleanup_error}"
                        if message
                        else cleanup_error
                    )
            return ExportAttemptResult(
                ExportStage.FAILED,
                failure_kind=(
                    committed.failure_kind
                    or ExportFailureKind.COMMIT_FAILED
                ),
                message=message,
            )
        return ExportAttemptResult(
            ExportStage.SUCCEEDED,
            target_path=committed.target_path,
        )


class ExportQueueService:
    def __init__(
        self,
        store: ExportQueueStore,
        *,
        runner: AttemptRunner | None = None,
        clock: Callable[[], str] | None = None,
        id_factory: Callable[[], str] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        transaction_recoverer: TransactionRecoverer | None = None,
        operation_guard: MediaOperationGuard | None = None,
    ) -> None:
        self._store = store
        self._runner = runner or ExportAttemptRunner()
        self._clock = clock or _now
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._sleeper = sleeper
        self._transaction_recoverer = (
            transaction_recoverer or recover_export_transactions
        )
        self._operation_guard = operation_guard
        self._state_lock = threading.RLock()
        self._run_lock = threading.Lock()
        self._state = ExportQueueState(
            QUEUE_SCHEMA_VERSION,
            True,
            self._clock(),
            (),
        )
        self._initialized = False
        self._read_only = False
        self._running_job_id: str | None = None
        self._running_token: CancellationToken | None = None
        self._worker_thread: threading.Thread | None = None
        self._succeeded_listeners: list[SucceededListener] = []
        self._terminal_listeners: list[TerminalListener] = []
        self._interrupt_requested_job_id: str | None = None
        self._temp_cleanup_reports: list[ExportTempCleanupReport] = []

    @property
    def state(self) -> ExportQueueState:
        with self._state_lock:
            return self._state

    @property
    def read_only(self) -> bool:
        return self._read_only

    @property
    def active_job_id(self) -> str | None:
        with self._state_lock:
            return self._running_job_id

    @property
    def queued_count(self) -> int:
        with self._state_lock:
            return sum(
                job.status == ExportStage.QUEUED
                for job in self._state.jobs
            )

    @property
    def temp_cleanup_reports(self) -> tuple[ExportTempCleanupReport, ...]:
        return tuple(self._temp_cleanup_reports)

    def initialize(self) -> QueueOperationResult:
        loaded = self._store.load()
        if not loaded.ok:
            self._read_only = True
            self._initialized = True
            return QueueOperationResult(
                False,
                loaded.error or "export queue could not be loaded",
                read_only=True,
            )
        if loaded.read_only or loaded.state is None:
            self._read_only = True
            self._initialized = True
            return QueueOperationResult(
                True,
                loaded.error or "export queue is read-only",
                read_only=True,
            )
        recovered = self._recover_transactions(loaded)
        now = self._clock()
        jobs = tuple(
            self._recover_job(job, recovered, now) for job in loaded.state.jobs
        )
        for job in loaded.state.jobs:
            for attempt in job.attempts:
                if attempt.status in _ACTIVE_STAGES:
                    self._cleanup_attempt_artifacts(
                        job,
                        attempt.attempt_id,
                    )
        state = ExportQueueState(
            QUEUE_SCHEMA_VERSION,
            True,
            now,
            jobs,
        )
        changed = state != loaded.state
        if changed:
            write = self._store.save(state)
            if not write.ok:
                self._read_only = write.read_only
                self._state = loaded.state
                self._initialized = True
                return QueueOperationResult(
                    False,
                    write.error or "export queue recovery could not be saved",
                    read_only=write.read_only,
                )
        self._state = state
        self._read_only = False
        self._initialized = True
        return QueueOperationResult(True)

    def job(self, job_id: str) -> ExportJob:
        with self._state_lock:
            return _find_job(self._state.jobs, job_id)

    def subscribe_succeeded(self, listener: SucceededListener) -> None:
        with self._state_lock:
            if listener not in self._succeeded_listeners:
                self._succeeded_listeners.append(listener)

    def subscribe_terminal(self, listener: TerminalListener) -> None:
        """订阅任务最终结果，不暴露自动重试的中间失败。"""
        with self._state_lock:
            if listener not in self._terminal_listeners:
                self._terminal_listeners.append(listener)

    def enqueue(self, plan: ExportPlan) -> QueueOperationResult:
        with self._state_lock:
            blocked = self._require_writable()
            if blocked is not None:
                return blocked
            incomplete = sum(job.is_incomplete for job in self._state.jobs)
            if incomplete >= MAX_INCOMPLETE_JOBS:
                return QueueOperationResult(
                    False,
                    "incomplete job limit reached",
                )
            target = normalize_windows_path(plan.output.target_path)
            if any(
                job.is_incomplete
                and normalize_windows_path(job.plan.output.target_path) == target
                for job in self._state.jobs
            ):
                return QueueOperationResult(
                    False,
                    "output target is reserved by another incomplete job",
                )
            now = self._clock()
            job = ExportJob(
                job_id=f"job-{self._id_factory()}",
                plan=plan,
                status=ExportStage.QUEUED,
                created_at=now,
                updated_at=now,
            )
            next_state = replace(
                self._state,
                updated_at=now,
                jobs=(*self._state.jobs, job),
            )
            saved = self._persist(next_state)
            return QueueOperationResult(
                saved.ok,
                saved.message,
                job if saved.ok else None,
                saved.read_only,
            )

    def pause(self) -> QueueOperationResult:
        return self._set_paused(True)

    def resume(self) -> QueueOperationResult:
        return self._set_paused(False)

    def cancel(self, job_id: str) -> QueueOperationResult:
        with self._state_lock:
            blocked = self._require_writable()
            if blocked is not None:
                return blocked
            try:
                job = _find_job(self._state.jobs, job_id)
            except KeyError:
                return QueueOperationResult(False, "job not found")
            if job.status == ExportStage.QUEUED:
                updated = _finish_job(
                    job,
                    status=ExportStage.CANCELLED,
                    now=self._clock(),
                    failure_kind=ExportFailureKind.CANCELLED,
                    message="export cancelled before start",
                )
                saved = self._persist(_replace_job(self._state, updated))
                return QueueOperationResult(
                    saved.ok,
                    saved.message,
                    updated if saved.ok else None,
                    saved.read_only,
                )
            if job.status == ExportStage.COMMITTING:
                return QueueOperationResult(
                    False,
                    "commit stage cannot be cancelled",
                )
            if (
                job.status in _CANCELLABLE_ACTIVE_STAGES
                and self._running_job_id == job_id
                and self._running_token is not None
            ):
                updated = _update_job_and_attempt_status(
                    job,
                    ExportStage.CANCELLING,
                    self._clock(),
                )
                saved = self._persist(_replace_job(self._state, updated))
                if not saved.ok:
                    return saved
                self._running_token.cancel()
                return QueueOperationResult(True, job=updated)
            return QueueOperationResult(False, "job cannot be cancelled")

    def continue_waiting(self, job_id: str) -> QueueOperationResult:
        with self._state_lock:
            blocked = self._require_writable()
            if blocked is not None:
                return blocked
            try:
                job = _find_job(self._state.jobs, job_id)
            except KeyError:
                return QueueOperationResult(False, "job not found")
            if not job.stalled:
                return QueueOperationResult(False, "job is not stalled")
            if (
                job.status != ExportStage.RUNNING
                or self._running_job_id != job_id
                or self._running_token is None
            ):
                return QueueOperationResult(
                    False,
                    "stalled attempt is no longer active",
                )
            updated = replace(
                job,
                updated_at=self._clock(),
                stalled=False,
            )
            saved = self._persist(_replace_job(self._state, updated))
            if not saved.ok:
                return saved
            self._running_token.continue_waiting()
            return QueueOperationResult(True, job=updated)

    def interrupt_active(self) -> QueueOperationResult:
        """为应用退出安全中断当前尝试，并保留排队任务。"""
        with self._state_lock:
            blocked = self._require_writable()
            if blocked is not None:
                return blocked
            job_id = self._running_job_id
            token = self._running_token
            if job_id is None or token is None:
                return QueueOperationResult(False, "no active export attempt")
            job = _find_job(self._state.jobs, job_id)
            if job.status == ExportStage.COMMITTING:
                return QueueOperationResult(
                    False,
                    "commit stage must finish before exit",
                )
            updated = _update_job_and_attempt_status(
                job,
                ExportStage.CANCELLING,
                self._clock(),
            )
            saved = self._persist(_replace_job(self._state, updated))
            if not saved.ok:
                return saved
            self._interrupt_requested_job_id = job_id
            token.cancel()
            return QueueOperationResult(True, job=updated)

    def wait_until_idle(self, timeout: float) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            if self.active_job_id is None:
                return True
            time.sleep(0.01)
        return self.active_job_id is None

    def manual_retry(self, job_id: str) -> QueueOperationResult:
        with self._state_lock:
            blocked = self._require_writable()
            if blocked is not None:
                return blocked
            try:
                job = _find_job(self._state.jobs, job_id)
            except KeyError:
                return QueueOperationResult(False, "job not found")
            if job.status not in {
                ExportStage.FAILED,
                ExportStage.INTERRUPTED,
                ExportStage.CANCELLED,
            }:
                return QueueOperationResult(False, "job is not retryable")
            if len(job.attempts) >= MAX_ATTEMPTS:
                return QueueOperationResult(False, "attempt limit reached")
            updated = replace(
                job,
                status=ExportStage.QUEUED,
                updated_at=self._clock(),
                progress_percent=0,
                eta_seconds=None,
                failure_kind=None,
                message="",
                next_attempt_trigger=AttemptTrigger.MANUAL,
                stalled=False,
            )
            saved = self._persist(_replace_job(self._state, updated))
            return QueueOperationResult(
                saved.ok,
                saved.message,
                updated if saved.ok else None,
                saved.read_only,
            )

    def update_ingestion(
        self,
        job_id: str,
        status: IngestionStatus,
        *,
        error: str = "",
    ) -> QueueOperationResult:
        """独立持久化导出结果入库状态，不改写导出成功事实。"""
        with self._state_lock:
            blocked = self._require_writable()
            if blocked is not None:
                return blocked
            try:
                job = _find_job(self._state.jobs, job_id)
            except KeyError:
                return QueueOperationResult(False, "job not found")
            if job.status != ExportStage.SUCCEEDED:
                return QueueOperationResult(
                    False,
                    "only succeeded exports can update ingestion",
                )
            updated = replace(
                job,
                ingestion_status=status,
                ingestion_error=(
                    str(error)
                    if status == IngestionStatus.FAILED
                    else ""
                ),
                updated_at=self._clock(),
            )
            saved = self._persist(_replace_job(self._state, updated))
            return QueueOperationResult(
                saved.ok,
                saved.message,
                updated if saved.ok else None,
                saved.read_only,
            )

    def run_next(self) -> QueueRunResult:
        if not self._run_lock.acquire(blocking=False):
            return QueueRunResult(
                False,
                message="another export attempt is active",
            )
        started_job_id: str | None = None
        guarded_job_id: str | None = None
        try:
            while True:
                with self._state_lock:
                    if (
                        not self._initialized
                        or self._read_only
                        or self._state.paused
                    ):
                        return QueueRunResult(
                            started_job_id is not None,
                            job_id=started_job_id,
                            status=(
                                self.job(started_job_id).status
                                if started_job_id is not None
                                else None
                            ),
                            message=(
                                "queue is paused or unavailable"
                                if started_job_id is None
                                else ""
                            ),
                        )
                    job = next(
                        (
                            item
                            for item in self._state.jobs
                            if item.status == ExportStage.QUEUED
                        ),
                        None,
                    )
                    if job is None:
                        return QueueRunResult(
                            started_job_id is not None,
                            job_id=started_job_id,
                            status=(
                                self.job(started_job_id).status
                                if started_job_id is not None
                                else None
                            ),
                            message=(
                                "no queued export job"
                                if started_job_id is None
                                else ""
                            ),
                        )
                    if (
                        self._operation_guard is not None
                        and guarded_job_id is None
                    ):
                        decision = self._operation_guard.try_begin_export(
                            job.job_id
                        )
                        if not decision.ok:
                            return QueueRunResult(
                                False,
                                job_id=job.job_id,
                                status=job.status,
                                message=decision.message,
                            )
                        guarded_job_id = job.job_id
                    if started_job_id is None:
                        started_job_id = job.job_id
                    attempt = self._start_attempt(job)
                    if attempt is None:
                        return QueueRunResult(
                            started_job_id is not None,
                            job_id=started_job_id,
                            status=job.status,
                            message="queue state could not be saved",
                        )
                    token = CancellationToken()
                    self._running_job_id = job.job_id
                    self._running_token = token
                try:
                    result = self._runner.run(
                        job.plan,
                        attempt_id=attempt.attempt_id,
                        cancel_token=token,
                        on_progress=lambda value: self._on_progress(
                            job.job_id,
                            value,
                        ),
                        on_stage=lambda value: self._on_stage(
                            job.job_id,
                            value,
                        ),
                    )
                except Exception as exc:
                    result = ExportAttemptResult(
                        ExportStage.FAILED,
                        failure_kind=ExportFailureKind.INTERNAL_ERROR,
                        message=f"attempt runner failed: {type(exc).__name__}",
                    )
                finally:
                    with self._state_lock:
                        self._running_job_id = None
                        self._running_token = None
                with self._state_lock:
                    current = _find_job(self._state.jobs, job.job_id)
                    if self._interrupt_requested_job_id == job.job_id:
                        result = ExportAttemptResult(
                            ExportStage.INTERRUPTED,
                            failure_kind=ExportFailureKind.CANCELLED,
                            message="export interrupted by application exit",
                        )
                        self._interrupt_requested_job_id = None
                    if result.status in {
                        ExportStage.SUCCEEDED,
                        ExportStage.CANCELLED,
                    }:
                        cleanup = self._cleanup_attempt_artifacts(
                            current,
                            attempt.attempt_id,
                        )
                        if cleanup.failed:
                            failure_names = ", ".join(
                                kind for _, kind in cleanup.failed
                            )
                            result = replace(
                                result,
                                message=(
                                    f"{result.message}; "
                                    f"temporary cleanup failed: {failure_names}"
                                ).strip("; "),
                            )
                    finished = _finish_attempt(
                        current,
                        result,
                        self._clock(),
                    )
                    saved = self._persist(_replace_job(self._state, finished))
                    if not saved.ok:
                        return QueueRunResult(
                            True,
                            job_id=job.job_id,
                            status=current.status,
                            message=saved.message,
                        )
                    if finished.status == ExportStage.SUCCEEDED:
                        self._notify_succeeded(finished)
                    if not self._should_auto_retry(finished):
                        self._notify_terminal(finished)
                        return QueueRunResult(
                            True,
                            job_id=job.job_id,
                            status=finished.status,
                        )
                    queued = replace(
                        finished,
                        status=ExportStage.QUEUED,
                        updated_at=self._clock(),
                        progress_percent=0,
                        eta_seconds=None,
                        next_attempt_trigger=AttemptTrigger.AUTOMATIC,
                        stalled=False,
                    )
                    saved = self._persist(_replace_job(self._state, queued))
                    if not saved.ok:
                        return QueueRunResult(
                            True,
                            job_id=job.job_id,
                            status=finished.status,
                            message=saved.message,
                        )
                self._sleeper(AUTO_RETRY_DELAY_SECONDS)
        finally:
            if self._operation_guard is not None and guarded_job_id is not None:
                self._operation_guard.release_export(guarded_job_id)
            self._run_lock.release()

    def start_worker(self) -> QueueOperationResult:
        with self._state_lock:
            blocked = self._require_writable()
            if blocked is not None:
                return blocked
            if self._state.paused:
                return QueueOperationResult(False, "queue is paused")
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return QueueOperationResult(False, "queue worker is already active")
            worker = threading.Thread(
                target=self._drain_queue,
                daemon=True,
                name="QuickRecExportWorker",
            )
            self._worker_thread = worker
            worker.start()
            return QueueOperationResult(True)

    def wait_for_worker(self, timeout: float | None = None) -> bool:
        worker = self._worker_thread
        if worker is None:
            return True
        worker.join(timeout)
        return not worker.is_alive()

    def clear_completed(self) -> QueueOperationResult:
        with self._state_lock:
            blocked = self._require_writable()
            if blocked is not None:
                return blocked
            jobs = tuple(
                job
                for job in self._state.jobs
                if job.status
                not in {ExportStage.SUCCEEDED, ExportStage.CANCELLED}
            )
            next_state = replace(
                self._state,
                updated_at=self._clock(),
                jobs=jobs,
            )
            saved = self._persist(next_state)
            return QueueOperationResult(
                saved.ok,
                saved.message,
                read_only=saved.read_only,
            )

    def prune_history(
        self,
        *,
        now: datetime | None = None,
        max_completed: int = 100,
        max_age_days: int = 90,
    ) -> QueueOperationResult:
        with self._state_lock:
            blocked = self._require_writable()
            if blocked is not None:
                return blocked
            current_time = now or datetime.now().astimezone()
            cutoff = current_time - timedelta(days=max_age_days)
            completed = [
                job
                for job in self._state.jobs
                if job.status in {ExportStage.SUCCEEDED, ExportStage.CANCELLED}
                and _timestamp(job.updated_at) >= cutoff
            ]
            retained_completed_ids = {
                job.job_id
                for job in sorted(
                    completed,
                    key=lambda item: _timestamp(item.updated_at),
                    reverse=True,
                )[:max_completed]
            }
            jobs = tuple(
                job
                for job in self._state.jobs
                if job.status
                not in {ExportStage.SUCCEEDED, ExportStage.CANCELLED}
                or job.job_id in retained_completed_ids
            )
            saved = self._persist(
                replace(
                    self._state,
                    updated_at=self._clock(),
                    jobs=jobs,
                )
            )
            return QueueOperationResult(
                saved.ok,
                saved.message,
                read_only=saved.read_only,
            )

    def _start_attempt(self, job: ExportJob) -> ExportAttempt | None:
        if len(job.attempts) >= MAX_ATTEMPTS:
            failed = replace(
                job,
                status=ExportStage.FAILED,
                updated_at=self._clock(),
                failure_kind=ExportFailureKind.INTERNAL_ERROR,
                message="attempt limit reached",
            )
            self._persist(_replace_job(self._state, failed))
            return None
        now = self._clock()
        attempt = ExportAttempt(
            attempt_id=f"attempt-{self._id_factory()}",
            sequence=len(job.attempts) + 1,
            trigger=job.next_attempt_trigger,
            status=ExportStage.VALIDATING,
            created_at=now,
            started_at=now,
        )
        updated = replace(
            job,
            status=ExportStage.VALIDATING,
            updated_at=now,
            attempts=(*job.attempts, attempt),
            progress_percent=0,
            eta_seconds=None,
            failure_kind=None,
            message="",
            next_attempt_trigger=AttemptTrigger.INITIAL,
            stalled=False,
        )
        saved = self._persist(_replace_job(self._state, updated))
        return attempt if saved.ok else None

    def _on_stage(self, job_id: str, stage: ExportStage) -> None:
        with self._state_lock:
            try:
                job = _find_job(self._state.jobs, job_id)
            except KeyError:
                return
            updated = _update_job_and_attempt_status(
                job,
                stage,
                self._clock(),
            )
            self._persist(_replace_job(self._state, updated))

    def _on_progress(
        self,
        job_id: str,
        progress: ExportProgressSnapshot,
    ) -> None:
        with self._state_lock:
            try:
                job = _find_job(self._state.jobs, job_id)
            except KeyError:
                return
            latest = max(job.progress_percent, progress.percent)
            if (
                job.status == progress.stage
                and latest == job.progress_percent
                and job.stalled == progress.stalled
            ):
                return
            updated = replace(
                _update_latest_attempt(job, status=progress.stage),
                status=progress.stage,
                updated_at=self._clock(),
                progress_percent=latest,
                eta_seconds=progress.eta_seconds,
                stalled=progress.stalled,
            )
            self._persist(_replace_job(self._state, updated))

    def _drain_queue(self) -> None:
        while True:
            result = self.run_next()
            if not result.started:
                return

    def _notify_succeeded(self, job: ExportJob) -> None:
        for listener in tuple(self._succeeded_listeners):
            try:
                listener(job)
            except Exception:
                continue

    def _notify_terminal(self, job: ExportJob) -> None:
        for listener in tuple(self._terminal_listeners):
            try:
                listener(job)
            except Exception:
                continue

    def _set_paused(self, paused: bool) -> QueueOperationResult:
        with self._state_lock:
            blocked = self._require_writable()
            if blocked is not None:
                return blocked
            saved = self._persist(
                replace(
                    self._state,
                    paused=paused,
                    updated_at=self._clock(),
                )
            )
            return QueueOperationResult(
                saved.ok,
                saved.message,
                read_only=saved.read_only,
            )

    def _persist(self, state: ExportQueueState) -> QueueOperationResult:
        written = self._store.save(state)
        if not written.ok:
            if written.read_only:
                self._read_only = True
            return QueueOperationResult(
                False,
                written.error or "export queue save failed",
                read_only=written.read_only,
            )
        self._state = state
        return QueueOperationResult(True)

    def _require_writable(self) -> QueueOperationResult | None:
        if not self._initialized:
            return QueueOperationResult(False, "queue is not initialized")
        if self._read_only:
            return QueueOperationResult(
                False,
                "queue is read-only",
                read_only=True,
            )
        return None

    def _should_auto_retry(self, job: ExportJob) -> bool:
        automatic_count = sum(
            attempt.trigger == AttemptTrigger.AUTOMATIC
            for attempt in job.attempts
        )
        return (
            job.status == ExportStage.FAILED
            and job.failure_kind in _AUTO_RETRYABLE
            and automatic_count == 0
            and len(job.attempts) < MAX_ATTEMPTS
        )

    def _cleanup_attempt_artifacts(
        self,
        job: ExportJob,
        attempt_id: str,
    ) -> ExportTempCleanupReport:
        report = cleanup_export_attempt(
            ExportTempArtifactOwner(
                job_id=job.job_id,
                attempt_id=attempt_id,
                output_directory=Path(job.plan.output.directory),
            )
        )
        self._temp_cleanup_reports.append(report)
        return report

    def _recover_transactions(
        self,
        loaded: QueueLoadResult,
    ) -> dict[str, CommitRecoveryResult]:
        assert loaded.state is not None
        directories = sorted(
            {Path(job.plan.output.directory) for job in loaded.state.jobs},
            key=lambda path: normalize_windows_path(path),
        )
        results: dict[str, CommitRecoveryResult] = {}
        for directory in directories:
            for result in self._transaction_recoverer(directory):
                if result.target_path is not None:
                    results[normalize_windows_path(result.target_path)] = result
        return results

    def _recover_job(
        self,
        job: ExportJob,
        recovered: dict[str, CommitRecoveryResult],
        now: str,
    ) -> ExportJob:
        if job.status not in _ACTIVE_STAGES:
            return job
        result = recovered.get(normalize_windows_path(job.plan.output.target_path))
        if result is not None:
            if result.status == CommitRecoveryStatus.FINALIZED_NEW:
                return _finish_job(
                    job,
                    status=ExportStage.SUCCEEDED,
                    now=now,
                    output_path=str(job.plan.output.target_path),
                    progress_percent=100,
                    message="commit recovered and finalized",
                )
            if result.status == CommitRecoveryStatus.AMBIGUOUS:
                return _finish_job(
                    job,
                    status=ExportStage.FAILED,
                    now=now,
                    failure_kind=ExportFailureKind.RECOVERY_AMBIGUOUS,
                    message=result.message or "commit recovery is ambiguous",
                )
            return _finish_job(
                job,
                status=ExportStage.INTERRUPTED,
                now=now,
                message="old target restored after interrupted commit",
            )
        return _finish_job(
            job,
            status=ExportStage.INTERRUPTED,
            now=now,
            message="application exited during export",
        )


def _finish_attempt(
    job: ExportJob,
    result: ExportAttemptResult,
    now: str,
) -> ExportJob:
    output_path = (
        str(result.target_path)
        if result.target_path is not None
        else job.output_path
    )
    return _finish_job(
        job,
        status=result.status,
        now=now,
        failure_kind=result.failure_kind,
        message=result.message,
        output_path=output_path,
        progress_percent=(100 if result.status == ExportStage.SUCCEEDED else None),
    )


def _finish_job(
    job: ExportJob,
    *,
    status: ExportStage,
    now: str,
    failure_kind: ExportFailureKind | None = None,
    message: str = "",
    output_path: str | None = None,
    progress_percent: int | None = None,
) -> ExportJob:
    updated = _update_latest_attempt(
        job,
        status=status,
        completed_at=now,
        failure_kind=failure_kind,
        message=message,
    )
    return replace(
        updated,
        status=status,
        updated_at=now,
        progress_percent=(
            progress_percent
            if progress_percent is not None
            else updated.progress_percent
        ),
        eta_seconds=None,
        output_path=output_path,
        failure_kind=failure_kind,
        message=message,
        stalled=False,
    )


def _update_job_and_attempt_status(
    job: ExportJob,
    status: ExportStage,
    now: str,
) -> ExportJob:
    return replace(
        _update_latest_attempt(job, status=status),
        status=status,
        updated_at=now,
        stalled=(job.stalled if status == ExportStage.RUNNING else False),
    )


def _update_latest_attempt(
    job: ExportJob,
    *,
    status: ExportStage,
    completed_at: str | None = None,
    failure_kind: ExportFailureKind | None = None,
    message: str | None = None,
) -> ExportJob:
    if not job.attempts:
        return job
    latest = job.attempts[-1]
    updated = replace(
        latest,
        status=status,
        completed_at=completed_at,
        failure_kind=failure_kind,
        message=latest.message if message is None else message,
    )
    return replace(job, attempts=(*job.attempts[:-1], updated))


def _replace_job(state: ExportQueueState, updated: ExportJob) -> ExportQueueState:
    jobs = tuple(
        updated if job.job_id == updated.job_id else job
        for job in state.jobs
    )
    if all(job.job_id != updated.job_id for job in state.jobs):
        raise KeyError(updated.job_id)
    return replace(state, updated_at=updated.updated_at, jobs=jobs)


def _find_job(jobs: tuple[ExportJob, ...], job_id: str) -> ExportJob:
    for job in jobs:
        if job.job_id == job_id:
            return job
    raise KeyError(job_id)


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.min.astimezone()
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed
