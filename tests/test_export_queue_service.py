from __future__ import annotations

import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from exporting.committer import (
    CommitRecoveryResult,
    CommitRecoveryStatus,
)
from exporting.executor import (
    CancellationToken,
    ExportExecutionResult,
    ExportProgressSnapshot,
)
from exporting.models import (
    ExportClip,
    ExportFailureKind,
    ExportMaterialSnapshot,
    ExportOutputSpec,
    ExportPlan,
    ExportProjectSnapshot,
    ExportStage,
    ExportTimelineSnapshot,
    ExportTrack,
    RenderPolicy,
)
from exporting.queue_service import (
    ExportAttemptResult,
    ExportAttemptRunner,
    ExportQueueService,
)
from exporting.queue_store import (
    AttemptTrigger,
    ExportAttempt,
    ExportJob,
    ExportQueueState,
    ExportQueueStore,
    IngestionStatus,
)
from exporting.verifier import ExportVerificationResult
from services.media_operation_guard import MediaOperation, MediaOperationGuard
from utils.recording_library_store import normalize_windows_path


def _plan(tmp_path: Path, plan_id: str) -> ExportPlan:
    source = tmp_path / f"{plan_id} 素材.mp4"
    source.write_bytes(b"source")
    stat = source.stat()
    return ExportPlan.create(
        plan_id=plan_id,
        created_at="2026-07-29T12:00:00+00:00",
        project=ExportProjectSnapshot(
            "project-1",
            "队列项目",
            str(tmp_path / "project.qrproj"),
            1,
            2,
        ),
        timeline=ExportTimelineSnapshot(
            "timeline-1",
            1_000_000,
            (ExportTrack("video-1", "video", 0),),
            (
                ExportClip(
                    "clip-1",
                    "material-1",
                    "video-1",
                    None,
                    0,
                    1_000_000,
                    0,
                    1_000_000,
                ),
            ),
        ),
        materials=(
            ExportMaterialSnapshot(
                "material-1",
                str(source),
                normalize_windows_path(source),
                stat.st_size,
                stat.st_mtime_ns,
                "mov,mp4,m4a,3gp,3g2,mj2",
                "h264",
                320,
                180,
                30.0,
                1_000_000,
                None,
                None,
                None,
                None,
            ),
        ),
        render_policy=RenderPolicy(),
        output=ExportOutputSpec(
            320,
            180,
            30,
            str(tmp_path / "Exports"),
            f"{plan_id}.mp4",
        ),
    )


class _Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"id-{self.value}"


class _Clock:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"2026-07-29T12:00:{self.value:02d}+00:00"


class _Runner:
    def __init__(self, results: list[ExportAttemptResult] | None = None) -> None:
        self.results = list(results or [])
        self.calls: list[tuple[str, str]] = []
        self.active = 0
        self.max_active = 0

    def run(
        self,
        plan: ExportPlan,
        *,
        attempt_id: str,
        cancel_token: CancellationToken,
        on_progress,
        on_stage,
    ) -> ExportAttemptResult:
        self.calls.append((plan.plan_id, attempt_id))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            on_stage(ExportStage.RUNNING)
            on_progress(
                ExportProgressSnapshot(
                    ExportStage.RUNNING,
                    50,
                    500_000,
                    1.0,
                    1.0,
                    1.0,
                )
            )
            if cancel_token.is_cancelled:
                return ExportAttemptResult(
                    ExportStage.CANCELLED,
                    failure_kind=ExportFailureKind.CANCELLED,
                    message="cancelled",
                )
            if self.results:
                return self.results.pop(0)
            return ExportAttemptResult(
                ExportStage.SUCCEEDED,
                target_path=plan.output.target_path,
            )
        finally:
            self.active -= 1


class _BlockingRunner(_Runner):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()
        self.cancel_token: CancellationToken | None = None

    def run(
        self,
        plan: ExportPlan,
        *,
        attempt_id: str,
        cancel_token: CancellationToken,
        on_progress,
        on_stage,
    ) -> ExportAttemptResult:
        self.calls.append((plan.plan_id, attempt_id))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.cancel_token = cancel_token
        self.started.set()
        try:
            on_stage(ExportStage.RUNNING)
            while not self.release.wait(0.01):
                if cancel_token.is_cancelled:
                    return ExportAttemptResult(
                        ExportStage.CANCELLED,
                        failure_kind=ExportFailureKind.CANCELLED,
                        message="cancelled",
                    )
            return ExportAttemptResult(
                ExportStage.SUCCEEDED,
                target_path=plan.output.target_path,
            )
        finally:
            self.active -= 1


def _service(
    tmp_path: Path,
    runner,
    *,
    sleeper=lambda _seconds: None,
    transaction_recoverer=None,
    operation_guard=None,
) -> ExportQueueService:
    return ExportQueueService(
        ExportQueueStore(tmp_path / "queue.json"),
        runner=runner,
        clock=_Clock(),
        id_factory=_Ids(),
        sleeper=sleeper,
        transaction_recoverer=transaction_recoverer,
        operation_guard=operation_guard,
    )


def test_initialize_pauses_queue_and_maps_active_jobs_to_interrupted(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path, "plan-active")
    active = ExportJob(
        job_id="job-active",
        plan=plan,
        status=ExportStage.RUNNING,
        created_at="2026-07-29T11:00:00+00:00",
        updated_at="2026-07-29T11:00:01+00:00",
        attempts=(
            ExportAttempt(
                "attempt-old",
                1,
                AttemptTrigger.INITIAL,
                ExportStage.RUNNING,
                "2026-07-29T11:00:00+00:00",
            ),
        ),
    )
    queued = replace(
        active,
        job_id="job-queued",
        plan=_plan(tmp_path, "plan-queued"),
        status=ExportStage.QUEUED,
        attempts=(),
    )
    store = ExportQueueStore(tmp_path / "queue.json")
    assert store.save(
        ExportQueueState(1, False, "2026-07-29T11:00:02+00:00", (active, queued))
    ).ok
    recovery_calls: list[Path] = []

    def recover(directory: Path):
        recovery_calls.append(directory)
        return ()

    service = _service(
        tmp_path,
        _Runner(),
        transaction_recoverer=recover,
    )

    result = service.initialize()

    assert result.ok
    assert service.state.paused
    assert service.job("job-active").status == ExportStage.INTERRUPTED
    assert service.job("job-queued").status == ExportStage.QUEUED
    assert recovery_calls == [Path(plan.output.directory)]


def test_resume_runs_jobs_fifo_and_persists_attempt_history(tmp_path: Path) -> None:
    runner = _Runner()
    service = _service(tmp_path, runner)
    service.initialize()
    first = service.enqueue(_plan(tmp_path, "plan-first"))
    second = service.enqueue(_plan(tmp_path, "plan-second"))

    assert first.ok and second.ok
    assert service.resume().ok
    assert service.run_next().started
    assert service.run_next().started

    assert [call[0] for call in runner.calls] == ["plan-first", "plan-second"]
    assert service.job(first.job.job_id).status == ExportStage.SUCCEEDED
    assert service.job(second.job.job_id).status == ExportStage.SUCCEEDED
    assert service.job(first.job.job_id).attempts[0].status == ExportStage.SUCCEEDED
    reloaded = ExportQueueStore(tmp_path / "queue.json").load()
    assert reloaded.state == service.state


def test_concurrent_run_next_calls_never_start_two_workers(tmp_path: Path) -> None:
    runner = _BlockingRunner()
    service = _service(tmp_path, runner)
    service.initialize()
    service.enqueue(_plan(tmp_path, "plan-one"))
    service.enqueue(_plan(tmp_path, "plan-two"))
    service.resume()
    first_thread = threading.Thread(target=service.run_next)
    first_thread.start()
    assert runner.started.wait(1)

    second = service.run_next()
    runner.release.set()
    first_thread.join(1)

    assert not second.started
    assert second.message == "another export attempt is active"
    assert runner.max_active == 1
    assert len(runner.calls) == 1


def test_background_worker_drains_fifo_with_one_active_attempt(
    tmp_path: Path,
) -> None:
    runner = _Runner()
    service = _service(tmp_path, runner)
    service.initialize()
    service.enqueue(_plan(tmp_path, "plan-worker-one"))
    service.enqueue(_plan(tmp_path, "plan-worker-two"))
    service.resume()

    started = service.start_worker()

    assert started.ok
    assert service.wait_for_worker(2)
    assert [call[0] for call in runner.calls] == [
        "plan-worker-one",
        "plan-worker-two",
    ]
    assert runner.max_active == 1


def test_queued_job_does_not_block_recording_but_running_export_does(
    tmp_path: Path,
) -> None:
    guard = MediaOperationGuard()
    runner = _BlockingRunner()
    service = _service(tmp_path, runner, operation_guard=guard)
    service.initialize()
    service.enqueue(_plan(tmp_path, "plan-guard"))

    assert guard.try_begin_recording().ok
    guard.release_recording()
    service.resume()
    thread = threading.Thread(target=service.run_next)
    thread.start()
    assert runner.started.wait(1)

    assert guard.state.operation == MediaOperation.EXPORTING
    assert not guard.try_begin_recording().ok
    runner.release.set()
    thread.join(1)
    assert guard.state.operation == MediaOperation.IDLE


def test_recording_blocks_export_without_changing_queued_job(
    tmp_path: Path,
) -> None:
    guard = MediaOperationGuard()
    runner = _Runner()
    service = _service(tmp_path, runner, operation_guard=guard)
    service.initialize()
    created = service.enqueue(_plan(tmp_path, "plan-recording-block"))
    service.resume()
    assert guard.try_begin_recording().ok

    result = service.run_next()

    assert not result.started
    assert "recording is active" in result.message
    assert service.job(created.job.job_id).status == ExportStage.QUEUED
    assert runner.calls == []
    guard.release_recording()


def test_application_exit_interrupt_marks_attempt_interrupted(
    tmp_path: Path,
) -> None:
    runner = _BlockingRunner()
    service = _service(tmp_path, runner)
    service.initialize()
    created = service.enqueue(_plan(tmp_path, "plan-interrupt"))
    service.resume()
    thread = threading.Thread(target=service.run_next)
    thread.start()
    assert runner.started.wait(1)

    interrupted = service.interrupt_active()
    thread.join(1)

    assert interrupted.ok
    assert service.wait_until_idle(0.2)
    assert service.job(created.job.job_id).status == ExportStage.INTERRUPTED
    assert "application exit" in service.job(created.job.job_id).message


def test_cancel_queued_job_does_not_start_runner(tmp_path: Path) -> None:
    runner = _Runner()
    service = _service(tmp_path, runner)
    service.initialize()
    created = service.enqueue(_plan(tmp_path, "plan-cancel"))

    result = service.cancel(created.job.job_id)

    assert result.ok
    assert service.job(created.job.job_id).status == ExportStage.CANCELLED
    assert not service.run_next().started
    assert runner.calls == []


def test_cancel_running_job_reaches_cancelled_and_releases_worker(
    tmp_path: Path,
) -> None:
    runner = _BlockingRunner()
    service = _service(tmp_path, runner)
    service.initialize()
    created = service.enqueue(_plan(tmp_path, "plan-running-cancel"))
    service.resume()
    thread = threading.Thread(target=service.run_next)
    thread.start()
    assert runner.started.wait(1)

    cancelled = service.cancel(created.job.job_id)
    thread.join(1)

    assert cancelled.ok
    assert service.job(created.job.job_id).status == ExportStage.CANCELLED
    assert runner.active == 0


def test_stalled_progress_is_persisted_and_continue_waiting_reaches_runner(
    tmp_path: Path,
) -> None:
    runner = _BlockingRunner()
    service = _service(tmp_path, runner)
    service.initialize()
    created = service.enqueue(_plan(tmp_path, "plan-stalled"))
    service.resume()
    thread = threading.Thread(target=service.run_next)
    thread.start()
    assert runner.started.wait(1)

    service._on_progress(
        created.job.job_id,
        ExportProgressSnapshot(
            ExportStage.RUNNING,
            50,
            500_000,
            121.0,
            None,
            121.0,
            stalled=False,
        ),
    )
    service._on_progress(
        created.job.job_id,
        ExportProgressSnapshot(
            ExportStage.RUNNING,
            50,
            500_000,
            121.0,
            None,
            121.0,
            stalled=True,
        ),
    )

    stalled = service.job(created.job.job_id)
    assert stalled.stalled is True
    persisted = ExportQueueStore(tmp_path / "queue.json").load()
    assert persisted.state is not None
    assert persisted.state.jobs[0].stalled is True

    continued = service.continue_waiting(created.job.job_id)

    assert continued.ok
    assert service.job(created.job.job_id).stalled is False
    assert runner.cancel_token is not None
    assert runner.cancel_token.consume_continue_waiting() is True
    assert runner.cancel_token.consume_continue_waiting() is False

    runner.release.set()
    thread.join(1)
    assert not thread.is_alive()


def test_continue_waiting_rejects_non_stalled_job(tmp_path: Path) -> None:
    service = _service(tmp_path, _Runner())
    service.initialize()
    created = service.enqueue(_plan(tmp_path, "plan-not-stalled"))

    result = service.continue_waiting(created.job.job_id)

    assert not result.ok
    assert result.message == "job is not stalled"


def test_retryable_failure_is_retried_automatically_only_once(
    tmp_path: Path,
) -> None:
    runner = _Runner(
        [
            ExportAttemptResult(
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.TOOL_START_FAILED,
                message="transient",
            ),
            ExportAttemptResult(
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.TOOL_START_FAILED,
                message="still failing",
            ),
        ]
    )
    sleeps: list[float] = []
    service = _service(tmp_path, runner, sleeper=sleeps.append)
    service.initialize()
    created = service.enqueue(_plan(tmp_path, "plan-auto-retry"))
    service.resume()

    service.run_next()

    job = service.job(created.job.job_id)
    assert job.status == ExportStage.FAILED
    assert [item.trigger for item in job.attempts] == [
        AttemptTrigger.INITIAL,
        AttemptTrigger.AUTOMATIC,
    ]
    assert sleeps == [5.0]
    assert len(runner.calls) == 2


def test_terminal_listener_receives_only_final_outcome_after_auto_retry(
    tmp_path: Path,
) -> None:
    runner = _Runner(
        [
            ExportAttemptResult(
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.TOOL_START_FAILED,
                message="transient",
            ),
            ExportAttemptResult(
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.TOOL_START_FAILED,
                message="still failing",
            ),
        ]
    )
    service = _service(tmp_path, runner)
    terminal = []
    service.initialize()
    service.subscribe_terminal(terminal.append)
    service.enqueue(_plan(tmp_path, "plan-terminal"))
    service.resume()

    service.run_next()

    assert [job.status for job in terminal] == [ExportStage.FAILED]
    assert terminal[0].message == "still failing"


def test_non_retryable_failure_stops_after_first_attempt(tmp_path: Path) -> None:
    runner = _Runner(
        [
            ExportAttemptResult(
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.MATERIAL_CHANGED,
                message="material changed",
            )
        ]
    )
    service = _service(tmp_path, runner)
    service.initialize()
    created = service.enqueue(_plan(tmp_path, "plan-no-retry"))
    service.resume()

    service.run_next()

    job = service.job(created.job.job_id)
    assert job.status == ExportStage.FAILED
    assert len(job.attempts) == 1
    assert len(runner.calls) == 1


def test_manual_retry_creates_new_attempt_and_preserves_old_attempt(
    tmp_path: Path,
) -> None:
    runner = _Runner(
        [
            ExportAttemptResult(
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.VERIFICATION_FAILED,
                message="bad output",
            ),
            ExportAttemptResult(
                ExportStage.SUCCEEDED,
                target_path=tmp_path / "Exports" / "plan-manual.mp4",
            ),
        ]
    )
    service = _service(tmp_path, runner)
    service.initialize()
    created = service.enqueue(_plan(tmp_path, "plan-manual"))
    service.resume()
    service.run_next()
    before = service.job(created.job.job_id).attempts[0]

    retried = service.manual_retry(created.job.job_id)
    service.run_next()

    job = service.job(created.job.job_id)
    assert retried.ok
    assert job.status == ExportStage.SUCCEEDED
    assert job.attempts[0] == before
    assert [attempt.trigger for attempt in job.attempts] == [
        AttemptTrigger.INITIAL,
        AttemptTrigger.MANUAL,
    ]


def test_attempt_limit_disables_manual_retry(tmp_path: Path) -> None:
    attempts = tuple(
        ExportAttempt(
            f"attempt-{index}",
            index,
            AttemptTrigger.MANUAL,
            ExportStage.FAILED,
            f"2026-07-29T12:00:{index:02d}+00:00",
        )
        for index in range(1, 6)
    )
    job = ExportJob(
        "job-limit",
        _plan(tmp_path, "plan-limit"),
        ExportStage.FAILED,
        "2026-07-29T12:00:00+00:00",
        "2026-07-29T12:00:05+00:00",
        attempts=attempts,
    )
    store = ExportQueueStore(tmp_path / "queue.json")
    assert store.save(
        ExportQueueState(
            1,
            True,
            "2026-07-29T12:00:05+00:00",
            (job,),
        )
    ).ok
    service = _service(tmp_path, _Runner())
    service.initialize()

    result = service.manual_retry(job.job_id)

    assert not result.ok
    assert result.message == "attempt limit reached"
    assert service.job(job.job_id).attempts == attempts


def test_startup_commit_recovery_maps_finalized_and_ambiguous_jobs(
    tmp_path: Path,
) -> None:
    first_plan = _plan(tmp_path, "plan-final")
    second_plan = _plan(tmp_path, "plan-ambiguous")
    jobs = (
        ExportJob(
            "job-final",
            first_plan,
            ExportStage.COMMITTING,
            "2026-07-29T11:00:00+00:00",
            "2026-07-29T11:00:00+00:00",
        ),
        ExportJob(
            "job-ambiguous",
            second_plan,
            ExportStage.COMMITTING,
            "2026-07-29T11:00:01+00:00",
            "2026-07-29T11:00:01+00:00",
        ),
    )
    store = ExportQueueStore(tmp_path / "queue.json")
    assert store.save(
        ExportQueueState(1, False, "2026-07-29T11:00:02+00:00", jobs)
    ).ok

    def recover(_directory: Path):
        return (
            CommitRecoveryResult(
                CommitRecoveryStatus.FINALIZED_NEW,
                tmp_path / "final.transaction.json",
                first_plan.output.target_path,
            ),
            CommitRecoveryResult(
                CommitRecoveryStatus.AMBIGUOUS,
                tmp_path / "ambiguous.transaction.json",
                second_plan.output.target_path,
            ),
        )

    service = _service(
        tmp_path,
        _Runner(),
        transaction_recoverer=recover,
    )
    service.initialize()

    assert service.job("job-final").status == ExportStage.SUCCEEDED
    assert (
        service.job("job-ambiguous").failure_kind
        == ExportFailureKind.RECOVERY_AMBIGUOUS
    )
    assert service.job("job-ambiguous").status == ExportStage.FAILED


def test_incomplete_job_capacity_is_limited_to_twenty(tmp_path: Path) -> None:
    service = _service(tmp_path, _Runner())
    service.initialize()
    for index in range(20):
        assert service.enqueue(_plan(tmp_path, f"plan-{index}")).ok

    blocked = service.enqueue(_plan(tmp_path, "plan-21"))

    assert not blocked.ok
    assert blocked.message == "incomplete job limit reached"
    assert len(service.state.jobs) == 20


def test_enqueue_rejects_target_reserved_by_another_incomplete_job(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, _Runner())
    service.initialize()
    first = _plan(tmp_path, "plan-first")
    second = ExportPlan.create(
        plan_id="plan-second",
        created_at=first.created_at,
        project=first.project,
        timeline=first.timeline,
        materials=first.materials,
        render_policy=first.render_policy,
        output=first.output,
    )

    assert service.enqueue(first).ok
    blocked = service.enqueue(second)

    assert not blocked.ok
    assert blocked.message == "output target is reserved by another incomplete job"
    assert len(service.state.jobs) == 1


def test_clear_completed_never_deletes_output_or_failed_history(
    tmp_path: Path,
) -> None:
    output = tmp_path / "Exports" / "success.mp4"
    output.parent.mkdir()
    output.write_bytes(b"formal")
    succeeded = ExportJob(
        "job-success",
        _plan(tmp_path, "plan-success"),
        ExportStage.SUCCEEDED,
        "2026-07-29T12:00:00+00:00",
        "2026-07-29T12:01:00+00:00",
        progress_percent=100,
        output_path=str(output),
        ingestion_status=IngestionStatus.SUCCEEDED,
    )
    failed = ExportJob(
        "job-failed",
        _plan(tmp_path, "plan-failed"),
        ExportStage.FAILED,
        "2026-07-29T12:00:00+00:00",
        "2026-07-29T12:01:00+00:00",
        failure_kind=ExportFailureKind.TOOL_FAILED,
    )
    store = ExportQueueStore(tmp_path / "queue.json")
    assert store.save(
        ExportQueueState(
            1,
            True,
            "2026-07-29T12:01:00+00:00",
            (succeeded, failed),
        )
    ).ok
    service = _service(tmp_path, _Runner())
    service.initialize()

    result = service.clear_completed()

    assert result.ok
    assert output.read_bytes() == b"formal"
    assert service.job(failed.job_id).status == ExportStage.FAILED
    assert all(job.job_id != succeeded.job_id for job in service.state.jobs)


def test_prune_history_keeps_latest_hundred_and_all_failed_jobs(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    jobs: list[ExportJob] = []
    for index in range(105):
        updated = now - timedelta(days=index % 80, seconds=index)
        jobs.append(
            ExportJob(
                f"job-success-{index}",
                _plan(tmp_path, f"plan-success-{index}"),
                ExportStage.SUCCEEDED,
                updated.isoformat(),
                updated.isoformat(),
                output_path=str(tmp_path / "formal" / f"{index}.mp4"),
            )
        )
    old = now - timedelta(days=120)
    jobs.append(
        ExportJob(
            "job-old",
            _plan(tmp_path, "plan-old"),
            ExportStage.CANCELLED,
            old.isoformat(),
            old.isoformat(),
        )
    )
    jobs.append(
        ExportJob(
            "job-failed-kept",
            _plan(tmp_path, "plan-failed-kept"),
            ExportStage.FAILED,
            old.isoformat(),
            old.isoformat(),
            failure_kind=ExportFailureKind.TOOL_FAILED,
        )
    )
    store = ExportQueueStore(tmp_path / "queue.json")
    assert store.save(
        ExportQueueState(1, True, now.isoformat(), tuple(jobs))
    ).ok
    service = _service(tmp_path, _Runner())
    service.initialize()

    result = service.prune_history(now=now)

    assert result.ok
    assert len(
        [
            job
            for job in service.state.jobs
            if job.status == ExportStage.SUCCEEDED
        ]
    ) == 100
    assert service.job("job-failed-kept").status == ExportStage.FAILED
    assert all(job.job_id != "job-old" for job in service.state.jobs)


def test_formal_attempt_runner_reuses_executor_verifier_and_committer(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path, "plan-formal-runner")
    candidate = Path(plan.output.directory) / ".candidate.part.mp4"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"candidate")
    target = plan.output.target_path
    calls: list[str] = []

    class Executor:
        def execute(self, received_plan, **kwargs):
            calls.append("execute")
            assert received_plan == plan
            return ExportExecutionResult(
                True,
                ExportStage.VERIFYING,
                temp_output_path=candidate,
            )

    class Verifier:
        def verify_output(self, received_plan, path):
            calls.append(f"verify:{path.name}")
            assert received_plan == plan
            return ExportVerificationResult(True)

        def verify_materials(self, received_plan):
            calls.append("verify-materials")
            assert received_plan == plan
            return ExportVerificationResult(True)

    class Committer:
        def commit(self, received_plan, path, *, attempt_id):
            from exporting.committer import ExportCommitResult

            calls.append("commit")
            assert received_plan == plan
            assert path == candidate
            assert attempt_id == "attempt-formal"
            path.replace(target)
            return ExportCommitResult(True, target)

    stages: list[ExportStage] = []
    result = ExportAttemptRunner(
        executor=Executor(),
        verifier=Verifier(),
        committer=Committer(),
    ).run(
        plan,
        attempt_id="attempt-formal",
        cancel_token=CancellationToken(),
        on_progress=lambda _value: None,
        on_stage=stages.append,
    )

    assert result.status == ExportStage.SUCCEEDED
    assert result.target_path == target
    assert calls == [
        "execute",
        "verify:.candidate.part.mp4",
        "verify-materials",
        "commit",
    ]
    assert stages == [
        ExportStage.VALIDATING,
        ExportStage.VERIFYING,
        ExportStage.COMMITTING,
    ]


def test_formal_attempt_runner_removes_candidate_after_pretransaction_commit_failure(
    tmp_path: Path,
) -> None:
    from exporting.committer import ExportCommitResult

    plan = _plan(tmp_path, "plan-pretransaction-conflict")
    candidate = Path(plan.output.directory) / ".candidate-conflict.part.mp4"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"candidate")

    class Executor:
        def execute(self, _plan, **_kwargs):
            return ExportExecutionResult(
                True,
                ExportStage.VERIFYING,
                temp_output_path=candidate,
            )

    class Verifier:
        def verify_output(self, _plan, _path):
            return ExportVerificationResult(True)

        def verify_materials(self, _plan):
            return ExportVerificationResult(True)

    class Committer:
        def commit(self, received_plan, _path, *, attempt_id):
            assert received_plan == plan
            assert attempt_id == "attempt-pretransaction-conflict"
            return ExportCommitResult(
                False,
                plan.output.target_path,
                failure_kind=ExportFailureKind.TARGET_CONFLICT,
                message="target already exists; use a safe suffix",
            )

    result = ExportAttemptRunner(
        executor=Executor(),
        verifier=Verifier(),
        committer=Committer(),
    ).run(
        plan,
        attempt_id="attempt-pretransaction-conflict",
        cancel_token=CancellationToken(),
        on_progress=lambda _value: None,
        on_stage=lambda _stage: None,
    )

    assert result.status == ExportStage.FAILED
    assert result.failure_kind == ExportFailureKind.TARGET_CONFLICT
    assert not candidate.exists()


def test_formal_attempt_runner_preserves_candidate_for_ambiguous_commit_transaction(
    tmp_path: Path,
) -> None:
    from exporting.committer import ExportCommitResult

    plan = _plan(tmp_path, "plan-ambiguous-commit")
    candidate = Path(plan.output.directory) / ".candidate-ambiguous.part.mp4"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"candidate")
    transaction = Path(plan.output.directory) / ".commit-transaction.json"
    transaction.write_text("{}", encoding="utf-8")

    class Executor:
        def execute(self, _plan, **_kwargs):
            return ExportExecutionResult(
                True,
                ExportStage.VERIFYING,
                temp_output_path=candidate,
            )

    class Verifier:
        def verify_output(self, _plan, _path):
            return ExportVerificationResult(True)

        def verify_materials(self, _plan):
            return ExportVerificationResult(True)

    class Committer:
        def commit(self, received_plan, _path, *, attempt_id):
            assert received_plan == plan
            assert attempt_id == "attempt-ambiguous-commit"
            return ExportCommitResult(
                False,
                plan.output.target_path,
                failure_kind=ExportFailureKind.COMMIT_FAILED,
                message="commit result is ambiguous",
                transaction_path=transaction,
            )

    result = ExportAttemptRunner(
        executor=Executor(),
        verifier=Verifier(),
        committer=Committer(),
    ).run(
        plan,
        attempt_id="attempt-ambiguous-commit",
        cancel_token=CancellationToken(),
        on_progress=lambda _value: None,
        on_stage=lambda _stage: None,
    )

    assert result.status == ExportStage.FAILED
    assert result.failure_kind == ExportFailureKind.COMMIT_FAILED
    assert candidate.read_bytes() == b"candidate"
