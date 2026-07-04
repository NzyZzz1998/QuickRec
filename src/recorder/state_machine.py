from enum import Enum


class RecordingState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"
    SAVING = "saving"


_ALLOWED_TRANSITIONS = {
    RecordingState.IDLE: {RecordingState.RECORDING},
    RecordingState.RECORDING: {RecordingState.PAUSED, RecordingState.STOPPING, RecordingState.IDLE},
    RecordingState.PAUSED: {RecordingState.RECORDING, RecordingState.STOPPING, RecordingState.IDLE},
    RecordingState.STOPPING: {RecordingState.SAVING, RecordingState.IDLE},
    RecordingState.SAVING: {RecordingState.IDLE},
}


class RecordingStateMachine:
    def __init__(self, initial: RecordingState = RecordingState.IDLE):
        self._state = initial

    @property
    def state(self) -> RecordingState:
        return self._state

    def can_transition_to(self, state: RecordingState) -> bool:
        return state in _ALLOWED_TRANSITIONS[self._state]

    def transition_to(self, state: RecordingState) -> bool:
        if not self.can_transition_to(state):
            return False
        self._state = state
        return True

    def reset(self) -> None:
        self._state = RecordingState.IDLE
