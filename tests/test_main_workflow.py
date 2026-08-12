import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import main


class FakeQApplication:
    def __init__(self, argv):
        self.argv = argv
        self.quit_called = False

    def setQuitOnLastWindowClosed(self, value):
        self.quit_on_last_window_closed = value

    def setStyle(self, value):
        self.style = value

    def exec_(self):
        return 0

    def quit(self):
        self.quit_called = True


class FakeConfig:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        if key in self.values:
            return self.values[key]
        return default


class FakeRecorder:
    def __init__(self, config, on_saved=None, on_event=None):
        self.config = config
        self.on_saved = on_saved
        self.on_event = on_event
        self.event_handler = None

    def set_event_handler(self, callback):
        self.event_handler = callback


class FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, callback):
        self.connected.append(callback)

    def emit(self, *args):
        for callback in self.connected:
            callback(*args)


class FakeHotkey:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.registered = []

    def register(self, *args):
        self.registered.append(args)
        return True

    def start_listening(self):
        self.started = True

    def stop_listening(self):
        self.stopped = True


class FakeTray:
    def __init__(self, config, callbacks):
        self.config = config
        self.callbacks = callbacks
        self.recording_states = []
        self.notifications = []

    def set_recording_state(self, *args, **kwargs):
        self.recording_states.append((args, kwargs))

    def show_notification(self, *args):
        self.notifications.append(args)

    def hide(self):
        self.hidden = True


class FakeWorkflow:
    def __init__(self, manager):
        self.manager = manager
        self.events = []
        self.calls = []
        self.state = main.RecorderState.IDLE
        self.wait_until_idle_result = True
        self.start_fullscreen_called = False
        self.start_fullscreen_result = True

    def handle_event(self, event):
        self.events.append(event)

    def start_fullscreen(self):
        self.start_fullscreen_called = True
        self.calls.append(("start_fullscreen",))
        return self.start_fullscreen_result

    def pause(self):
        self.calls.append(("pause",))
        self.state = main.RecorderState.PAUSED
        return True

    def resume(self):
        self.calls.append(("resume",))
        self.state = main.RecorderState.RECORDING
        return True

    def stop(self, cancel=False):
        self.calls.append(("stop", cancel))
        self.state = main.RecorderState.SAVING
        return ""

    def get_state(self):
        return self.state

    def wait_until_idle(self, timeout=60):
        self.calls.append(("wait_until_idle", timeout))
        if self.wait_until_idle_result:
            self.state = main.RecorderState.IDLE
        return self.wait_until_idle_result


class FakeToolbar:
    def __init__(self):
        self.timer_started = False
        self.closed = False
        self.saving_shown = False
        self.paused_states = []

    def start_recording_timer(self):
        self.timer_started = True

    def stop_recording_timer(self):
        pass

    def close(self):
        self.closed = True

    def show_saving(self):
        self.saving_shown = True

    def set_paused(self, value):
        self.paused_states.append(value)


class TestQuickRecAppWorkflow(unittest.TestCase):
    def test_init_wires_workflow_to_recorder_and_event_callback(self):
        with patch("main.QApplication", FakeQApplication), \
                patch("main.ConfigManager", FakeConfig), \
                patch("main.RecorderManager", FakeRecorder), \
                patch("main.RecordingWorkflow", FakeWorkflow), \
                patch("main.HotkeyManager", FakeHotkey), \
                patch("main.TrayIcon", FakeTray):
            app = main.QuickRecApp()

        self.assertIs(app._workflow.manager, app._recorder)
        self.assertIs(app._recorder.event_handler.__self__, app._workflow)
        self.assertIs(app._recorder.event_handler.__func__, app._workflow.handle_event.__func__)
        self.assertTrue(app._hotkey.started)
        self.assertEqual(len(app._hotkey.registered), 3)
        self.assertEqual(
            [item[0] for item in app._hotkey.registered],
            ["Ctrl+Alt+R", "Ctrl+Alt+S", "Ctrl+Alt+P"],
        )
        self.assertNotIn("start_region", app._tray.callbacks)
        self.assertNotIn("start_window", app._tray.callbacks)

    def test_do_start_fullscreen_uses_workflow(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._hotkey = FakeHotkey()
        app._workflow = FakeWorkflow(manager=None)
        app._toolbar = FakeToolbar()
        app._tray = FakeTray(config=None, callbacks={})

        app._do_start_fullscreen()

        self.assertTrue(app._workflow.start_fullscreen_called)
        self.assertTrue(app._toolbar.timer_started)
        self.assertEqual(app._tray.recording_states, [((True,), {})])

    def test_do_start_fullscreen_hides_toolbar_when_workflow_fails(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._hotkey = FakeHotkey()
        app._workflow = FakeWorkflow(manager=None)
        app._workflow.start_fullscreen_result = False
        app._toolbar = FakeToolbar()
        app._tray = FakeTray(config=None, callbacks={})

        app._do_start_fullscreen()

        self.assertTrue(app._workflow.start_fullscreen_called)
        self.assertIsNone(app._toolbar)
        self.assertEqual(app._tray.notifications, [("录制启动失败，请检查 FFmpeg 或录制环境",)])

    def test_stop_pause_resume_and_cancel_use_workflow(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._workflow = FakeWorkflow(manager=None)
        app._toolbar = FakeToolbar()
        app._tray = FakeTray(config=None, callbacks={})
        toolbar = app._toolbar

        app._workflow.state = main.RecorderState.RECORDING
        app._on_pause_resume()
        app._on_stop_recording()
        app._workflow.state = main.RecorderState.RECORDING
        app._on_cancel_recording()

        self.assertEqual(
            app._workflow.calls,
            [("pause",), ("stop", False), ("stop", True)],
        )
        self.assertEqual(toolbar.paused_states, [True])
        self.assertTrue(toolbar.saving_shown)

    def test_exit_uses_workflow_stop_and_wait(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._workflow = FakeWorkflow(manager=None)
        app._workflow.state = main.RecorderState.RECORDING
        app._toolbar = FakeToolbar()
        app._hotkey = FakeHotkey()
        app._tray = FakeTray(config=None, callbacks={})
        app._app = FakeQApplication([])

        with patch("PyQt5.QtCore.QCoreApplication.processEvents"):
            app._on_exit()

        self.assertEqual(
            app._workflow.calls,
            [("stop", False), ("wait_until_idle", 60)],
        )
        self.assertTrue(app._hotkey.stopped)
        self.assertTrue(app._app.quit_called)

    def test_main_sets_dpi_attributes_and_exits_with_app_result(self):
        attributes = []

        class EntryApplication:
            @staticmethod
            def setAttribute(attribute, enabled):
                attributes.append((attribute, enabled))

        with patch.object(main, "QApplication", EntryApplication), patch.object(
            main,
            "_enable_dpi_awareness",
        ), patch.object(main, "run_lite_app", return_value=0):
            with self.assertRaises(SystemExit) as exit_info:
                main.main()

        self.assertEqual(exit_info.exception.code, 0)
        self.assertEqual(len(attributes), 2)
        self.assertTrue(all(enabled for _, enabled in attributes))


if __name__ == "__main__":
    unittest.main()
