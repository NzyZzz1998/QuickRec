from __future__ import annotations

from dataclasses import dataclass

from exporting.exit_coordinator import (
    ExportExitAction,
    ExportExitCoordinator,
)
from exporting.queue_service import QueueOperationResult


@dataclass
class _Queue:
    active_job_id: str | None
    queued_count: int = 0
    interrupt_ok: bool = True
    wait_ok: bool = True

    def __post_init__(self) -> None:
        self.interrupt_calls = 0
        self.wait_calls: list[float] = []

    def interrupt_active(self) -> QueueOperationResult:
        self.interrupt_calls += 1
        if not self.interrupt_ok:
            return QueueOperationResult(False, "commit stage must finish")
        return QueueOperationResult(True)

    def wait_until_idle(self, timeout: float) -> bool:
        self.wait_calls.append(timeout)
        if self.wait_ok:
            self.active_job_id = None
        return self.wait_ok


def test_exit_without_active_attempt_preserves_queue_and_can_exit() -> None:
    queue = _Queue(None, queued_count=3)
    coordinator = ExportExitCoordinator(queue)

    result = coordinator.request_exit(
        ExportExitAction.INTERRUPT_AND_EXIT
    )

    assert result.should_exit
    assert result.queued_count == 3
    assert queue.interrupt_calls == 0


def test_continue_background_and_return_to_app_cancel_exit() -> None:
    queue = _Queue("job-1", queued_count=2)
    coordinator = ExportExitCoordinator(queue)

    background = coordinator.request_exit(
        ExportExitAction.CONTINUE_BACKGROUND
    )
    returned = coordinator.request_exit(
        ExportExitAction.RETURN_TO_APP
    )

    assert not background.should_exit
    assert not returned.should_exit
    assert queue.interrupt_calls == 0


def test_safe_interrupt_waits_for_attempt_before_exit() -> None:
    queue = _Queue("job-1")
    coordinator = ExportExitCoordinator(queue)

    result = coordinator.request_exit(
        ExportExitAction.INTERRUPT_AND_EXIT,
        timeout=12.0,
    )

    assert result.should_exit
    assert queue.interrupt_calls == 1
    assert queue.wait_calls == [12.0]


def test_commit_stage_refusal_keeps_application_running() -> None:
    queue = _Queue("job-1", interrupt_ok=False)
    coordinator = ExportExitCoordinator(queue)

    result = coordinator.request_exit(
        ExportExitAction.INTERRUPT_AND_EXIT
    )

    assert not result.should_exit
    assert "commit stage" in result.message
