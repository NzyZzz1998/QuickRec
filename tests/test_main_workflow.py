import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import main
from services.material_ingestion import MaterialIngestionCoordinator
from services.pending_recordings import PendingRecordingService


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

    def get_diagnostic_dir(self):
        return self.values.get("diagnostic_dir", str(Path(self.values.get("save_path", tempfile.gettempdir())) / "QuickRecDiagnostics"))


class FakeRecorder:
    def __init__(self, config, on_saved=None, on_event=None):
        self.config = config
        self.on_saved = on_saved
        self.on_event = on_event
        self.event_handler = None
        self.window_lost_callback = None
        self.window_lost_connected = False

    def set_event_handler(self, callback):
        self.event_handler = callback

    def connect_window_lost(self, callback):
        self.window_lost_callback = callback
        self.window_lost_connected = True

    def get_diagnostic_context(self):
        return {
            "config": {"save_path": self.config.get("save_path"), "audio_source": "none", "quality": "high", "fps": 30},
            "recorder": {"state": "idle", "mode": "fullscreen", "output_path": "", "session_dir": "", "last_result": "", "last_failure_reason": ""},
            "ffmpeg": {"path": "ffmpeg.exe", "exists": True, "frozen": False},
            "audio": {"requested_source": "none", "final_source": "none", "degraded": False, "reason": ""},
            "window": {"hwnd": 0, "title": "", "mode": "", "stage": "", "reason": "none", "rect": None, "foreground_result": ""},
        }

    def get_mode(self):
        return main.RecordMode.FULLSCREEN


class FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, callback):
        self.connected.append(callback)

    def emit(self, *args):
        for callback in self.connected:
            callback(*args)


class FakeWindowLostBridge:
    def __init__(self):
        self.window_lost = FakeSignal()


class FakeHotkey:
    def __init__(self):
        self.started = False
        self.stopped = False

    def register(self, *_args):
        return True

    def start_listening(self):
        self.started = True

    def stop_listening(self):
        self.stopped = True

    def set_esc_callback(self, _callback):
        pass


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

    def show_notification_with_action(self, *args, **kwargs):
        self.notifications.append(("action", args, kwargs))

    def hide(self):
        self.hidden = True


class FakeClickHighlighter:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.running = False

    def start(self):
        self.started = True
        self.running = True

    def stop(self):
        self.stopped = True
        self.running = False

    def is_running(self):
        return self.running


class FakeWindowHighlighter:
    def __init__(self):
        self.hidden = False

    def hide_highlight(self):
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

    def start_region(self, region):
        self.calls.append(("start_region", region))
        return True

    def start_window(self, hwnd):
        self.calls.append(("start_window", hwnd))
        return True

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

    def show_result(self, output_path, file_size, *, index_ok=True):
        self.result = (output_path, file_size, index_ok)

    def mark_material_index_saved(self):
        self.material_index_saved = True


class TestQuickRecAppWorkflow(unittest.TestCase):
    def test_init_wires_workflow_to_recorder_and_event_callback(self):
        with patch("main.QApplication", FakeQApplication), \
                patch("main.ConfigManager", FakeConfig), \
                patch("main.initialize_file_logging"), \
                patch("main.RecorderManager", FakeRecorder), \
                patch("main.RecordingWorkflow", FakeWorkflow), \
                patch("main.HotkeyManager", FakeHotkey), \
                patch("main.ClickHighlighter", FakeClickHighlighter), \
                patch("main.TrayIcon", FakeTray):
            app = main.QuickRecApp()

        self.assertIs(app._workflow.manager, app._recorder)
        self.assertIs(app._recorder.event_handler.__self__, app._workflow)
        self.assertIs(app._recorder.event_handler.__func__, app._workflow.handle_event.__func__)
        self.assertTrue(app._recorder.window_lost_connected)
        self.assertTrue(callable(app._recorder.window_lost_callback))
        self.assertTrue(app._hotkey.started)
        self.assertIn("copy_diagnostic", app._tray.callbacks)
        self.assertIn("open_diagnostic_dir", app._tray.callbacks)
        self.assertIn("export_diagnostic", app._tray.callbacks)
        self.assertIn("material_library", app._tray.callbacks)
        self.assertIsInstance(app._pending_service, PendingRecordingService)
        self.assertIsInstance(app._ingestion_coordinator, MaterialIngestionCoordinator)

    def test_copy_diagnostic_info_writes_clipboard_and_notifies(self):
        class Clipboard:
            text = ""

            def setText(self, value):
                self.text = value

        clipboard = Clipboard()
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        with tempfile.TemporaryDirectory() as temp_dir:
            app._config = FakeConfig({"save_path": temp_dir})
            app._recorder = FakeRecorder(app._config)
            app._tray = FakeTray(config=None, callbacks={})

            with patch("main.QApplication.clipboard", return_value=clipboard):
                app._on_copy_diagnostic_info()

        self.assertIn("QuickRec Diagnostic Report", clipboard.text)
        self.assertEqual(app._tray.notifications, [("诊断信息已复制",)])

    def test_diagnostic_report_uses_current_application_version(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        with tempfile.TemporaryDirectory() as temp_dir:
            app._config = FakeConfig({"save_path": temp_dir})
            app._recorder = FakeRecorder(app._config)

            text = app._build_diagnostic_text()

        self.assertIn("version: v1.6.1", text)
        self.assertNotIn("version: v1.4.x", text)

    def test_export_diagnostic_file_writes_file_and_notifies(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        with tempfile.TemporaryDirectory() as temp_dir:
            diagnostic_dir = Path(temp_dir) / "diagnostics"
            app._config = FakeConfig({"save_path": temp_dir, "diagnostic_dir": str(diagnostic_dir)})
            app._recorder = FakeRecorder(app._config)
            app._tray = FakeTray(config=None, callbacks={})

            app._on_export_diagnostic_file()

            exported = list(diagnostic_dir.glob("diagnostic_*.txt"))
            self.assertEqual(len(exported), 1)
            self.assertIn("QuickRec Diagnostic Report", exported[0].read_text(encoding="utf-8"))
            self.assertEqual(app._tray.notifications, [("诊断文件已导出",)])

    def test_handle_saved_writes_central_material_library_without_toolbar(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "QuickRec_20260710_153000.mp4"
            video.write_bytes(b"video")
            app._config = FakeConfig({"save_path": temp_dir, "audio_source": "both"})
            app._recorder = FakeRecorder(app._config)
            app._tray = FakeTray(config=None, callbacks={})
            app._toolbar = None
            app._window_highlighter = None
            app._click_highlighter = FakeClickHighlighter()
            central_index = Path(temp_dir) / "appdata" / "QuickRec" / "recordings.json"
            app._library_service = main.RecordingLibraryService(central_index)
            app._pending_service = PendingRecordingService(
                Path(temp_dir) / "appdata" / "QuickRec" / "pending-recordings.json"
            )
            app._ingestion_coordinator = MaterialIngestionCoordinator(
                app._library_service,
                app._pending_service,
            )
            app._pending_ids_by_output = {}

            app._handle_saved(str(video))

            self.assertTrue(central_index.exists())
            text = central_index.read_text(encoding="utf-8")
            self.assertIn("QuickRec_20260710_153000.mp4", text)
            self.assertIn("both", text)
            self.assertFalse((Path(temp_dir) / "QuickRecMetadata" / "recordings.json").exists())
            self.assertEqual(app._tray.recording_states, [((False,), {})])

    def test_handle_saved_keeps_recording_success_when_library_write_fails(self):
        class FailingLibrary:
            library_path = Path("denied-recordings.json")

            def find_existing(self, **_kwargs):
                return None

            def add_recording(self, *_args, **_kwargs):
                return type("Result", (), {"ok": False, "error": "denied"})()

        app = main.QuickRecApp.__new__(main.QuickRecApp)
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "QuickRec_20260710_153001.mp4"
            video.write_bytes(b"video")
            app._config = FakeConfig({"save_path": temp_dir, "audio_source": "none"})
            app._recorder = FakeRecorder(app._config)
            app._tray = FakeTray(config=None, callbacks={})
            app._toolbar = None
            app._window_highlighter = None
            app._click_highlighter = FakeClickHighlighter()
            app._library_service = FailingLibrary()
            pending_path = Path(temp_dir) / "appdata" / "QuickRec" / "pending-recordings.json"
            app._pending_service = PendingRecordingService(pending_path)
            app._ingestion_coordinator = MaterialIngestionCoordinator(
                app._library_service,
                app._pending_service,
            )
            app._pending_ids_by_output = {}

            app._handle_saved(str(video))

            pending = app._pending_service.load(temp_dir)

        action_notifications = [entry for entry in app._tray.notifications if entry[0] == "action"]
        self.assertEqual(len(action_notifications), 1)
        self.assertIn(("录制已保存，但素材索引写入失败",), app._tray.notifications)
        self.assertEqual(len(pending.items), 1)
        self.assertEqual(pending.items[0].file_path, str(video))

    def test_retry_material_item_reuses_pending_record_and_cleans_it_after_success(self):
        class ToggleLibrary(main.RecordingLibraryService):
            fail = True

            def add_recording(self, *args, **kwargs):
                if self.fail:
                    return type("Result", (), {"ok": False, "error": "denied"})()
                return super().add_recording(*args, **kwargs)

        app = main.QuickRecApp.__new__(main.QuickRecApp)
        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "QuickRec_20260715_120000.mp4"
            video.write_bytes(b"video")
            app._config = FakeConfig({"save_path": temp_dir, "audio_source": "none"})
            app._recorder = FakeRecorder(app._config)
            app._tray = FakeTray(config=None, callbacks={})
            app._toolbar = FakeToolbar()
            app._window_highlighter = None
            app._click_highlighter = FakeClickHighlighter()
            app._library_service = ToggleLibrary(Path(temp_dir) / "recordings.json")
            app._pending_service = PendingRecordingService(Path(temp_dir) / "pending-recordings.json")
            app._ingestion_coordinator = MaterialIngestionCoordinator(
                app._library_service,
                app._pending_service,
            )
            app._pending_ids_by_output = {}

            app._handle_saved(str(video))
            self.assertEqual(len(app._pending_service.load(temp_dir).items), 1)
            app._library_service.fail = False
            app._retry_material_item(str(video))

            self.assertEqual(app._pending_service.load(temp_dir).items, [])
            self.assertEqual(len(app._library_service.load().items), 1)
            self.assertTrue(app._toolbar.material_index_saved)
            self.assertIn(("素材已加入素材库",), app._tray.notifications)

    def test_startup_pending_retry_runs_once_in_background_and_reports_recovery(self):
        completed = threading.Event()

        class Coordinator:
            calls = []

            def retry_startup(self, save_path):
                self.calls.append(save_path)
                return main.StartupRetrySummary(scanned_count=2, succeeded_count=1, failed_count=1)

        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._config = FakeConfig({"save_path": "E:/QRtest/videos"})
        app._ingestion_coordinator = Coordinator()
        app._pending_retry_thread = None
        app._tray = FakeTray(config=None, callbacks={})
        app._material_library_dialog = None
        app._pending_retry_bridge = type("Bridge", (), {"finished": FakeSignal()})()
        app._pending_retry_bridge.finished.connect(
            lambda summary: (app._on_pending_retry_finished(summary), completed.set())
        )

        app._start_pending_retry()
        self.assertTrue(completed.wait(1))
        app._pending_retry_thread.join(timeout=1)

        self.assertEqual(app._ingestion_coordinator.calls, ["E:/QRtest/videos"])
        self.assertIn(("已恢复 1 条录制",), app._tray.notifications)

    def test_initial_migration_imports_current_save_path_legacy_history_once(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        with tempfile.TemporaryDirectory() as temp_dir:
            save_dir = Path(temp_dir) / "videos"
            legacy_dir = save_dir / "QuickRecMetadata"
            legacy_dir.mkdir(parents=True)
            source = legacy_dir / "recordings.json"
            source.write_text(
                '{"schema_version":1,"items":[{"id":"legacy-1",'
                f'"file_path":"{str(save_dir / "QuickRec_old.mp4").replace(chr(92), chr(92) * 2)}",'
                '"created_at":"2026-07-10T15:00:00+08:00"}]}',
                encoding="utf-8",
            )
            app._config = FakeConfig({"save_path": str(save_dir)})
            app._library_service = main.RecordingLibraryService(
                Path(temp_dir) / "appdata" / "QuickRec" / "recordings.json"
            )

            first = app._run_initial_migration()
            second = app._run_initial_migration()

        self.assertIsNotNone(first)
        self.assertTrue(first.ok)
        self.assertEqual(first.added_count, 1)
        self.assertIsNone(second)

    def test_save_path_change_prompts_for_legacy_history_only_once(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        with tempfile.TemporaryDirectory() as temp_dir:
            save_dir = Path(temp_dir) / "other-videos"
            legacy_dir = save_dir / "QuickRecMetadata"
            legacy_dir.mkdir(parents=True)
            source = legacy_dir / "recordings.json"
            source.write_text('{"schema_version":1,"items":[]}', encoding="utf-8")
            app._library_service = main.RecordingLibraryService(
                Path(temp_dir) / "appdata" / "QuickRec" / "recordings.json"
            )

            first = app._register_save_path_legacy_prompt(save_dir)
            second = app._register_save_path_legacy_prompt(save_dir)

        self.assertEqual(first, source)
        self.assertIsNone(second)

    def test_do_start_fullscreen_uses_workflow(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._hotkey = FakeHotkey()
        app._workflow = FakeWorkflow(manager=None)
        app._toolbar = FakeToolbar()
        app._tray = FakeTray(config=None, callbacks={})
        app._update_highlight_state = lambda: None

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

    def test_region_and_window_start_use_workflow(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._hotkey = FakeHotkey()
        app._workflow = FakeWorkflow(manager=None)
        app._toolbar = FakeToolbar()
        app._tray = FakeTray(config=None, callbacks={})
        app._window_highlighter = None
        app._update_highlight_state = lambda: None

        app._do_start_region(1, 2, 300, 200)
        app._do_start_window(42)

        self.assertEqual(
            app._workflow.calls,
            [("start_region", (1, 2, 300, 200)), ("start_window", 42)],
        )
        self.assertEqual(app._tray.recording_states, [((True,), {}), ((True,), {})])

    def test_window_highlighter_is_hidden_after_window_recording_starts(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._hotkey = FakeHotkey()
        app._workflow = FakeWorkflow(manager=None)
        app._toolbar = FakeToolbar()
        app._tray = FakeTray(config=None, callbacks={})
        highlighter = FakeWindowHighlighter()
        app._window_highlighter = highlighter
        app._update_highlight_state = lambda: None

        app._do_start_window(42)

        self.assertTrue(highlighter.hidden)
        self.assertIsNone(app._window_highlighter)

    def test_window_resume_does_not_recreate_highlighter_during_recording(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._workflow = FakeWorkflow(manager=None)
        app._workflow.state = main.RecorderState.PAUSED
        app._toolbar = FakeToolbar()
        app._tray = FakeTray(config=None, callbacks={})
        app._click_highlighter = FakeClickHighlighter()
        app._window_highlighter = None
        app._recorder = type(
            "RecorderReadModel",
            (),
            {"get_mode": lambda self: main.RecordMode.WINDOW, "get_window_hwnd": lambda self: 42},
        )()

        with patch("main.WindowHighlighter", side_effect=AssertionError("must not recreate highlighter")):
            app._on_pause_resume()

        self.assertIsNone(app._window_highlighter)

    def test_window_recording_disables_click_highlighter_overlay(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._config = FakeConfig({"mouse_highlight": True})
        app._workflow = FakeWorkflow(manager=None)
        app._workflow.state = main.RecorderState.RECORDING
        app._click_highlighter = FakeClickHighlighter()
        app._click_highlighter.running = True
        app._recorder = type(
            "RecorderReadModel",
            (),
            {"get_mode": lambda self: main.RecordMode.WINDOW},
        )()

        app._update_highlight_state()

        self.assertFalse(app._click_highlighter.started)
        self.assertTrue(app._click_highlighter.stopped)
        self.assertFalse(app._click_highlighter.is_running())

    def test_region_recording_can_still_enable_click_highlighter_overlay(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._config = FakeConfig({"mouse_highlight": True})
        app._workflow = FakeWorkflow(manager=None)
        app._workflow.state = main.RecorderState.RECORDING
        app._click_highlighter = FakeClickHighlighter()
        app._recorder = type(
            "RecorderReadModel",
            (),
            {"get_mode": lambda self: main.RecordMode.REGION},
        )()

        app._update_highlight_state()

        self.assertTrue(app._click_highlighter.started)
        self.assertFalse(app._click_highlighter.stopped)
        self.assertTrue(app._click_highlighter.is_running())

    def test_stop_pause_resume_and_cancel_use_workflow(self):
        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._workflow = FakeWorkflow(manager=None)
        app._toolbar = FakeToolbar()
        app._tray = FakeTray(config=None, callbacks={})
        app._click_highlighter = FakeClickHighlighter()
        app._window_highlighter = None
        app._recorder = type(
            "RecorderReadModel",
            (),
            {"get_mode": lambda self: None, "get_window_hwnd": lambda self: None},
        )()
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
        app._window_highlighter = None
        app._click_highlighter = FakeClickHighlighter()
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


if __name__ == "__main__":
    unittest.main()
