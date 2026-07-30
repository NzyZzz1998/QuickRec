"""托盘退出与持久导出队列的明确决策语义。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from exporting.queue_service import QueueOperationResult


class ExportQueueExitPort(Protocol):
    @property
    def active_job_id(self) -> str | None: ...

    @property
    def queued_count(self) -> int: ...

    def interrupt_active(self) -> QueueOperationResult: ...

    def wait_until_idle(self, timeout: float) -> bool: ...


class ExportExitAction(StrEnum):
    CONTINUE_BACKGROUND = "continue_background"
    INTERRUPT_AND_EXIT = "interrupt_and_exit"
    RETURN_TO_APP = "return_to_app"


@dataclass(frozen=True)
class ExportExitResult:
    should_exit: bool
    action: ExportExitAction
    active_job_id: str | None
    queued_count: int
    message: str = ""


class ExportExitCoordinator:
    def __init__(self, queue: ExportQueueExitPort) -> None:
        self._queue = queue

    def request_exit(
        self,
        action: ExportExitAction,
        *,
        timeout: float = 30.0,
    ) -> ExportExitResult:
        active = self._queue.active_job_id
        queued = self._queue.queued_count
        if active is None:
            return ExportExitResult(True, action, None, queued)
        if action in {
            ExportExitAction.CONTINUE_BACKGROUND,
            ExportExitAction.RETURN_TO_APP,
        }:
            return ExportExitResult(
                False,
                action,
                active,
                queued,
                "export continues in the background",
            )
        interrupted = self._queue.interrupt_active()
        if not interrupted.ok:
            return ExportExitResult(
                False,
                action,
                active,
                queued,
                interrupted.message,
            )
        if not self._queue.wait_until_idle(timeout):
            return ExportExitResult(
                False,
                action,
                self._queue.active_job_id,
                queued,
                "export did not stop before the exit timeout",
            )
        return ExportExitResult(True, action, None, queued)
