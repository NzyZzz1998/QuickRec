import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recorder.state_machine import RecordingState, RecordingStateMachine


class TestRecordingStateMachine(unittest.TestCase):
    def test_initial_state_is_idle(self):
        machine = RecordingStateMachine()

        self.assertEqual(machine.state, RecordingState.IDLE)

    def test_valid_recording_lifecycle(self):
        machine = RecordingStateMachine()

        self.assertTrue(machine.transition_to(RecordingState.RECORDING))
        self.assertTrue(machine.transition_to(RecordingState.PAUSED))
        self.assertTrue(machine.transition_to(RecordingState.RECORDING))
        self.assertTrue(machine.transition_to(RecordingState.STOPPING))
        self.assertTrue(machine.transition_to(RecordingState.SAVING))
        self.assertTrue(machine.transition_to(RecordingState.IDLE))

        self.assertEqual(machine.state, RecordingState.IDLE)

    def test_invalid_transition_returns_false_without_changing_state(self):
        machine = RecordingStateMachine()

        self.assertFalse(machine.transition_to(RecordingState.SAVING))

        self.assertEqual(machine.state, RecordingState.IDLE)

    def test_reset_forces_idle_from_any_state(self):
        machine = RecordingStateMachine()
        machine.transition_to(RecordingState.RECORDING)

        machine.reset()

        self.assertEqual(machine.state, RecordingState.IDLE)

    def test_can_transition_reports_without_mutating_state(self):
        machine = RecordingStateMachine()

        self.assertTrue(machine.can_transition_to(RecordingState.RECORDING))
        self.assertFalse(machine.can_transition_to(RecordingState.PAUSED))
        self.assertEqual(machine.state, RecordingState.IDLE)


if __name__ == "__main__":
    unittest.main()
