"""In-memory lifecycle for one material drag gesture."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from services.timeline_drag_transaction import TimelineDragCandidate


class TimelineDragState(StrEnum):
    IDLE = "idle"
    DRAGGING = "dragging"


@dataclass(frozen=True)
class TimelineDragContext:
    transaction_id: str
    material_id: str
    has_video: bool
    has_audio: bool
    origin: str


class TimelineDragInteraction:
    """Owns transient drag context; it never writes a project."""

    def __init__(
        self,
        *,
        transaction_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._transaction_id_factory = (
            transaction_id_factory
            or (lambda: f"drag-{uuid.uuid4().hex}")
        )
        self._state = TimelineDragState.IDLE
        self._context: TimelineDragContext | None = None
        self._candidate: TimelineDragCandidate | None = None

    @property
    def state(self) -> TimelineDragState:
        return self._state

    @property
    def context(self) -> TimelineDragContext | None:
        return self._context

    @property
    def candidate(self) -> TimelineDragCandidate | None:
        return self._candidate

    def begin(
        self,
        *,
        material_id: str,
        has_video: bool,
        has_audio: bool,
        origin: str,
    ) -> TimelineDragContext:
        self.cancel()
        context = TimelineDragContext(
            transaction_id=self._transaction_id_factory(),
            material_id=str(material_id),
            has_video=bool(has_video),
            has_audio=bool(has_audio),
            origin=str(origin),
        )
        self._state = TimelineDragState.DRAGGING
        self._context = context
        return context

    def update(self, candidate: TimelineDragCandidate) -> bool:
        context = self._context
        if (
            self._state != TimelineDragState.DRAGGING
            or context is None
            or candidate.transaction_id != context.transaction_id
            or candidate.material_id != context.material_id
        ):
            return False
        self._candidate = candidate
        return True

    def finish(self) -> TimelineDragCandidate | None:
        if self._state != TimelineDragState.DRAGGING:
            return None
        candidate = self._candidate
        self._clear()
        return candidate

    def cancel(self) -> bool:
        active = self._state == TimelineDragState.DRAGGING
        self._clear()
        return active

    def _clear(self) -> None:
        self._state = TimelineDragState.IDLE
        self._context = None
        self._candidate = None
