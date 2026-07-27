from __future__ import annotations

import threading
import time
from pathlib import Path

from services.thumbnail_coordinator import (
    ThumbnailCoordinator,
    ThumbnailTaskPriority,
    ThumbnailTaskState,
)
from services.thumbnail_service import (
    ThumbnailErrorCode,
    ThumbnailGenerationRequest,
    ThumbnailGenerationResult,
)


def _source(tmp_path: Path, index: int) -> Path:
    path = tmp_path / f"source-{index}.mp4"
    path.write_bytes(bytes([index]))
    return path


class BlockingService:
    def __init__(self) -> None:
        self.release = threading.Event()
        self.started = threading.Event()
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.calls: list[str] = []

    def generate(
        self,
        request: ThumbnailGenerationRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> ThumbnailGenerationResult:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.calls.append(request.material_id)
            self.started.set()
        while not self.release.wait(0.01):
            if cancel_event is not None and cancel_event.is_set():
                with self.lock:
                    self.active -= 1
                return ThumbnailGenerationResult(
                    False,
                    request.material_id,
                    error_code=ThumbnailErrorCode.CANCELLED,
                    error="cancelled",
                )
        with self.lock:
            self.active -= 1
        return ThumbnailGenerationResult(True, request.material_id)


class ScriptedService:
    def __init__(self, outcomes: list[ThumbnailGenerationResult]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate(
        self,
        request: ThumbnailGenerationRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> ThumbnailGenerationResult:
        del request, cancel_event
        self.calls += 1
        return self.outcomes.pop(0)


def test_coordinator_limits_parallel_generation_to_two(tmp_path: Path) -> None:
    service = BlockingService()
    coordinator = ThumbnailCoordinator(service, max_workers=2)
    try:
        for index in range(4):
            coordinator.submit(
                ThumbnailGenerationRequest(f"material-{index}", _source(tmp_path, index))
            )
        assert service.started.wait(1)
        time.sleep(0.05)
        assert service.max_active == 2
        service.release.set()
        assert coordinator.wait_for_idle(2)
        assert len(service.calls) == 4
    finally:
        coordinator.shutdown()


def test_duplicate_submission_runs_once_and_notifies_every_callback(tmp_path: Path) -> None:
    service = BlockingService()
    coordinator = ThumbnailCoordinator(service, max_workers=1)
    callbacks: list[ThumbnailGenerationResult] = []
    request = ThumbnailGenerationRequest("material-1", _source(tmp_path, 1))
    try:
        first_key = coordinator.submit(request, callback=callbacks.append)
        assert service.started.wait(1)
        second_key = coordinator.submit(request, callback=callbacks.append)
        service.release.set()

        assert coordinator.wait_for_idle(2)
        assert first_key == second_key
        assert service.calls == ["material-1"]
        assert len(callbacks) == 2
        assert all(item.ok for item in callbacks)
    finally:
        coordinator.shutdown()


def test_retryable_failure_is_retried_once(tmp_path: Path) -> None:
    service = ScriptedService(
        [
            ThumbnailGenerationResult(
                False,
                "material-1",
                error_code=ThumbnailErrorCode.NONZERO_EXIT,
                error="decoder failed",
            ),
            ThumbnailGenerationResult(True, "material-1"),
        ]
    )
    coordinator = ThumbnailCoordinator(service, max_workers=1, max_retries=1)
    results: list[ThumbnailGenerationResult] = []
    try:
        coordinator.submit(
            ThumbnailGenerationRequest("material-1", _source(tmp_path, 1)),
            callback=results.append,
        )
        assert coordinator.wait_for_idle(2)
        assert service.calls == 2
        assert len(results) == 1
        assert results[0].ok
    finally:
        coordinator.shutdown()


def test_non_retryable_failure_is_not_retried(tmp_path: Path) -> None:
    service = ScriptedService(
        [
            ThumbnailGenerationResult(
                False,
                "material-1",
                error_code=ThumbnailErrorCode.FFMPEG_MISSING,
                error="missing",
            )
        ]
    )
    coordinator = ThumbnailCoordinator(service, max_workers=1, max_retries=1)
    try:
        coordinator.submit(
            ThumbnailGenerationRequest("material-1", _source(tmp_path, 1))
        )
        assert coordinator.wait_for_idle(2)
        assert service.calls == 1
    finally:
        coordinator.shutdown()


def test_selected_task_overtakes_background_task_while_worker_is_busy(tmp_path: Path) -> None:
    service = BlockingService()
    coordinator = ThumbnailCoordinator(service, max_workers=1)
    try:
        coordinator.submit(
            ThumbnailGenerationRequest("blocker", _source(tmp_path, 0)),
            priority=ThumbnailTaskPriority.VISIBLE,
        )
        assert service.started.wait(1)
        coordinator.submit(
            ThumbnailGenerationRequest("background", _source(tmp_path, 1)),
            priority=ThumbnailTaskPriority.BACKGROUND,
        )
        coordinator.submit(
            ThumbnailGenerationRequest("selected", _source(tmp_path, 2)),
            priority=ThumbnailTaskPriority.SELECTED,
        )
        service.release.set()

        assert coordinator.wait_for_idle(2)
        assert service.calls == ["blocker", "selected", "background"]
    finally:
        coordinator.shutdown()


def test_priority_upgrade_does_not_duplicate_queued_task(tmp_path: Path) -> None:
    service = BlockingService()
    coordinator = ThumbnailCoordinator(service, max_workers=1)
    request = ThumbnailGenerationRequest("material-1", _source(tmp_path, 1))
    try:
        coordinator.submit(
            ThumbnailGenerationRequest("blocker", _source(tmp_path, 0))
        )
        assert service.started.wait(1)
        coordinator.submit(request, priority=ThumbnailTaskPriority.BACKGROUND)
        coordinator.submit(request, priority=ThumbnailTaskPriority.SELECTED)
        service.release.set()

        assert coordinator.wait_for_idle(2)
        assert service.calls.count("material-1") == 1
    finally:
        coordinator.shutdown()


def test_cancel_pending_task_skips_service_and_reports_cancelled(tmp_path: Path) -> None:
    service = BlockingService()
    coordinator = ThumbnailCoordinator(service, max_workers=1)
    callbacks: list[ThumbnailGenerationResult] = []
    try:
        coordinator.submit(
            ThumbnailGenerationRequest("blocker", _source(tmp_path, 0))
        )
        assert service.started.wait(1)
        key = coordinator.submit(
            ThumbnailGenerationRequest("pending", _source(tmp_path, 1)),
            callback=callbacks.append,
        )

        assert coordinator.cancel(key)
        service.release.set()
        assert coordinator.wait_for_idle(2)
        assert "pending" not in service.calls
        assert len(callbacks) == 1
        assert callbacks[0].error_code == ThumbnailErrorCode.CANCELLED
    finally:
        coordinator.shutdown()


def test_shutdown_cancels_running_task_and_leaves_no_worker(tmp_path: Path) -> None:
    service = BlockingService()
    coordinator = ThumbnailCoordinator(service, max_workers=1)
    coordinator.submit(
        ThumbnailGenerationRequest("running", _source(tmp_path, 0))
    )
    assert service.started.wait(1)

    coordinator.shutdown(cancel_pending=True, wait=True)

    assert coordinator.active_count == 0
    assert coordinator.worker_count == 0


def test_state_listener_observes_queued_running_and_success(tmp_path: Path) -> None:
    service = BlockingService()
    coordinator = ThumbnailCoordinator(service, max_workers=1)
    states: list[ThumbnailTaskState] = []
    coordinator.subscribe(lambda snapshot: states.append(snapshot.state))
    try:
        coordinator.submit(
            ThumbnailGenerationRequest("material-1", _source(tmp_path, 1))
        )
        assert service.started.wait(1)
        service.release.set()
        assert coordinator.wait_for_idle(2)

        assert states[0] == ThumbnailTaskState.QUEUED
        assert ThumbnailTaskState.RUNNING in states
        assert states[-1] == ThumbnailTaskState.SUCCEEDED
    finally:
        coordinator.shutdown()


def test_paused_coordinator_keeps_new_task_queued_until_resumed(
    tmp_path: Path,
) -> None:
    service = BlockingService()
    coordinator = ThumbnailCoordinator(service, max_workers=1)
    try:
        coordinator.set_execution_paused(True, reason="recording")
        coordinator.submit(
            ThumbnailGenerationRequest("material-1", _source(tmp_path, 1))
        )
        time.sleep(0.05)

        assert service.calls == []
        assert coordinator.execution_paused
        assert coordinator.diagnostic_summary()["active_count"] == 1

        coordinator.set_execution_paused(False, reason="idle")
        assert service.started.wait(1)
        service.release.set()
        assert coordinator.wait_for_idle(2)
    finally:
        coordinator.shutdown()


def test_diagnostic_summary_contains_no_source_path(tmp_path: Path) -> None:
    service = BlockingService()
    coordinator = ThumbnailCoordinator(service, max_workers=1)
    source = _source(tmp_path, 1)
    try:
        coordinator.submit(
            ThumbnailGenerationRequest("material-1", source)
        )
        assert service.started.wait(1)
        service.release.set()
        assert coordinator.wait_for_idle(2)

        summary = coordinator.diagnostic_summary()

        assert summary["recent"][0]["material_id"] == "material-1"
        assert str(source) not in str(summary)
    finally:
        coordinator.shutdown()
