from __future__ import annotations

from dataclasses import dataclass


class RecordingActiveError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecordingGuardState:
    active: bool = False
    reason: str = ""


class RecordingGuard:
    def __init__(self) -> None:
        self._state = RecordingGuardState()

    @property
    def state(self) -> RecordingGuardState:
        return self._state

    def activate(
        self,
        reason: str = "recording is active; timeline editing is disabled",
    ) -> RecordingGuardState:
        normalized_reason = str(reason).strip() or (
            "recording is active; timeline editing is disabled"
        )
        candidate = RecordingGuardState(
            active=True,
            reason=normalized_reason,
        )
        if candidate != self._state:
            self._state = candidate
        return self._state

    def release(self) -> RecordingGuardState:
        if self._state.active:
            self._state = RecordingGuardState()
        return self._state

    def ensure_writable(self) -> None:
        if self._state.active:
            raise RecordingActiveError(self._state.reason)
