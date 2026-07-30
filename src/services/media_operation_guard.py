"""录制与导出共享编码资源的应用级互斥门禁。"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum


class MediaOperation(StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    EXPORTING = "exporting"


@dataclass(frozen=True)
class MediaOperationState:
    operation: MediaOperation = MediaOperation.IDLE
    owner_id: str = ""


@dataclass(frozen=True)
class MediaOperationDecision:
    ok: bool
    operation: MediaOperation
    message: str = ""


class MediaOperationGuard:
    """只在实际录制或导出运行期间占用，不受排队任务影响。"""

    def __init__(self) -> None:
        self._state = MediaOperationState()
        self._lock = threading.RLock()

    @property
    def state(self) -> MediaOperationState:
        with self._lock:
            return self._state

    def can_begin_recording(self) -> MediaOperationDecision:
        with self._lock:
            return self._decision_for(MediaOperation.RECORDING)

    def can_begin_export(self) -> MediaOperationDecision:
        with self._lock:
            return self._decision_for(MediaOperation.EXPORTING)

    def try_begin_recording(self) -> MediaOperationDecision:
        with self._lock:
            decision = self._decision_for(MediaOperation.RECORDING)
            if decision.ok and self._state.operation == MediaOperation.IDLE:
                self._state = MediaOperationState(MediaOperation.RECORDING)
            return decision

    def release_recording(self) -> bool:
        with self._lock:
            if self._state.operation != MediaOperation.RECORDING:
                return False
            self._state = MediaOperationState()
            return True

    def try_begin_export(self, job_id: str) -> MediaOperationDecision:
        owner = str(job_id).strip()
        if not owner:
            return MediaOperationDecision(
                False,
                self.state.operation,
                "export job id is required",
            )
        with self._lock:
            if (
                self._state.operation == MediaOperation.EXPORTING
                and self._state.owner_id == owner
            ):
                return MediaOperationDecision(
                    True,
                    MediaOperation.EXPORTING,
                )
            decision = self._decision_for(MediaOperation.EXPORTING)
            if decision.ok:
                self._state = MediaOperationState(
                    MediaOperation.EXPORTING,
                    owner,
                )
            return decision

    def release_export(self, job_id: str) -> bool:
        with self._lock:
            if (
                self._state.operation != MediaOperation.EXPORTING
                or self._state.owner_id != str(job_id)
            ):
                return False
            self._state = MediaOperationState()
            return True

    def _decision_for(
        self,
        requested: MediaOperation,
    ) -> MediaOperationDecision:
        current = self._state.operation
        if current in {MediaOperation.IDLE, requested}:
            return MediaOperationDecision(True, current)
        if current == MediaOperation.RECORDING:
            return MediaOperationDecision(
                False,
                current,
                "recording is active; wait or stop recording before export",
            )
        return MediaOperationDecision(
            False,
            current,
            "export is active; wait or cancel export before recording",
        )
