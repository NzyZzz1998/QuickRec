from dataclasses import dataclass
from enum import Enum

from recorder.state_machine import RecordingState


class RecordingEventType(Enum):
    STATE_CHANGED = "state_changed"
    SAVED = "saved"
    FAILED = "failed"


@dataclass(frozen=True)
class RecordingEvent:
    type: RecordingEventType
    state: RecordingState
    previous_state: RecordingState | None = None
    output_path: str = ""
    reason: str = ""

    @classmethod
    def state_changed(cls, previous: RecordingState, current: RecordingState) -> "RecordingEvent":
        return cls(
            type=RecordingEventType.STATE_CHANGED,
            previous_state=previous,
            state=current,
        )

    @classmethod
    def saved(cls, output_path: str) -> "RecordingEvent":
        return cls(
            type=RecordingEventType.SAVED,
            state=RecordingState.IDLE,
            output_path=output_path,
        )

    @classmethod
    def failed(cls, reason: str) -> "RecordingEvent":
        return cls(
            type=RecordingEventType.FAILED,
            state=RecordingState.IDLE,
            reason=reason,
        )
