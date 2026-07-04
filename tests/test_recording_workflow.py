import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recorder.events import RecordingEvent, RecordingEventType
from recorder.state_machine import RecordingState
from recorder.workflow import RecordingWorkflow


class FakeManager:
    def __init__(self):
        self.calls = []
        self.state = RecordingState.IDLE
        self.wait_until_idle_result = True

    def start_fullscreen(self):
        self.calls.append(("start_fullscreen",))
        self.state = RecordingState.RECORDING
        return True

    def start_region(self, region):
        self.calls.append(("start_region", region))
        self.state = RecordingState.RECORDING
        return True

    def start_window(self, hwnd):
        self.calls.append(("start_window", hwnd))
        self.state = RecordingState.RECORDING
        return True

    def pause(self):
        self.calls.append(("pause",))
        self.state = RecordingState.PAUSED
        return True

    def resume(self):
        self.calls.append(("resume",))
        self.state = RecordingState.RECORDING
        return True

    def stop(self, cancel=False):
        self.calls.append(("stop", cancel))
        self.state = RecordingState.STOPPING
        return ""

    def get_state(self):
        return self.state

    def wait_until_idle(self, timeout=60.0):
        self.calls.append(("wait_until_idle", timeout))
        if self.wait_until_idle_result:
            self.state = RecordingState.IDLE
        return self.wait_until_idle_result


class TestRecordingWorkflow(unittest.TestCase):
    def test_start_routes_to_manager_by_mode(self):
        manager = FakeManager()
        workflow = RecordingWorkflow(manager)

        self.assertTrue(workflow.start_fullscreen())
        self.assertTrue(workflow.start_region((1, 2, 300, 200)))
        self.assertTrue(workflow.start_window(12345))

        self.assertEqual(
            manager.calls,
            [
                ("start_fullscreen",),
                ("start_region", (1, 2, 300, 200)),
                ("start_window", 12345),
            ],
        )

    def test_pause_resume_and_stop_delegate_to_manager(self):
        manager = FakeManager()
        workflow = RecordingWorkflow(manager)

        self.assertTrue(workflow.pause())
        self.assertTrue(workflow.resume())
        self.assertEqual(workflow.stop(cancel=True), "")

        self.assertEqual(manager.calls, [("pause",), ("resume",), ("stop", True)])

    def test_state_reads_from_manager(self):
        manager = FakeManager()
        workflow = RecordingWorkflow(manager)
        manager.state = RecordingState.PAUSED

        self.assertEqual(workflow.get_state(), RecordingState.PAUSED)

    def test_event_subscribers_receive_forwarded_events(self):
        manager = FakeManager()
        workflow = RecordingWorkflow(manager)
        events = []
        workflow.subscribe(events.append)

        workflow.handle_event(RecordingEvent.saved("D:/Videos/out.mp4"))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, RecordingEventType.SAVED)
        self.assertEqual(events[0].output_path, "D:/Videos/out.mp4")

    def test_unsubscribe_prevents_future_event_delivery(self):
        manager = FakeManager()
        workflow = RecordingWorkflow(manager)
        events = []
        workflow.subscribe(events.append)
        workflow.unsubscribe(events.append)

        workflow.handle_event(RecordingEvent.failed("boom"))

        self.assertEqual(events, [])

    def test_wait_until_idle_delegates_timeout(self):
        manager = FakeManager()
        workflow = RecordingWorkflow(manager)

        self.assertTrue(workflow.wait_until_idle(timeout=3.5))

        self.assertEqual(manager.calls, [("wait_until_idle", 3.5)])
        self.assertEqual(manager.state, RecordingState.IDLE)

    def test_wait_until_idle_returns_timeout_result(self):
        manager = FakeManager()
        manager.wait_until_idle_result = False
        workflow = RecordingWorkflow(manager)

        self.assertFalse(workflow.wait_until_idle(timeout=0.1))
        self.assertEqual(manager.calls, [("wait_until_idle", 0.1)])


if __name__ == "__main__":
    unittest.main()
