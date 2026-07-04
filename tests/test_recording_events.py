import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recorder.events import RecordingEvent, RecordingEventType
from recorder.state_machine import RecordingState


class TestRecordingEvent(unittest.TestCase):
    def test_saved_event_carries_output_path_and_state(self):
        event = RecordingEvent.saved("D:/Videos/out.mp4")

        self.assertEqual(event.type, RecordingEventType.SAVED)
        self.assertEqual(event.state, RecordingState.IDLE)
        self.assertEqual(event.output_path, "D:/Videos/out.mp4")
        self.assertEqual(event.reason, "")

    def test_failed_event_carries_reason(self):
        event = RecordingEvent.failed("ffmpeg failed")

        self.assertEqual(event.type, RecordingEventType.FAILED)
        self.assertEqual(event.state, RecordingState.IDLE)
        self.assertEqual(event.reason, "ffmpeg failed")
        self.assertEqual(event.output_path, "")

    def test_state_changed_event_records_previous_and_current_state(self):
        event = RecordingEvent.state_changed(
            previous=RecordingState.RECORDING,
            current=RecordingState.PAUSED,
        )

        self.assertEqual(event.type, RecordingEventType.STATE_CHANGED)
        self.assertEqual(event.previous_state, RecordingState.RECORDING)
        self.assertEqual(event.state, RecordingState.PAUSED)


if __name__ == "__main__":
    unittest.main()
