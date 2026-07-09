import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ConfigManager
from recorder.recorder_manager import RecorderManager
from recorder.window_diagnostics import WindowFailureReason, WindowRecordingDiagnostic


class TestWindowDiagnostics(unittest.TestCase):
    def test_diagnostic_records_failure_context(self):
        diagnostic = WindowRecordingDiagnostic(
            reason=WindowFailureReason.RECT_UNAVAILABLE,
            hwnd=123,
            title="Demo Window",
            mode="window",
            stage="get_window_rect",
            rect=None,
            foreground_result="not_attempted",
        )

        self.assertEqual(diagnostic.reason, WindowFailureReason.RECT_UNAVAILABLE)
        self.assertEqual(diagnostic.hwnd, 123)
        self.assertEqual(diagnostic.title, "Demo Window")
        self.assertEqual(diagnostic.mode, "window")
        self.assertEqual(diagnostic.stage, "get_window_rect")
        self.assertIsNone(diagnostic.rect)
        self.assertEqual(diagnostic.foreground_result, "not_attempted")

    def test_recorder_manager_exposes_initial_empty_window_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ConfigManager.__new__(ConfigManager)
            config.config_path = Path(temp_dir) / "config.json"
            config._config = ConfigManager.defaults.copy()
            manager = RecorderManager(config)

            diagnostic = manager.get_last_window_diagnostic()

        self.assertEqual(diagnostic.reason, WindowFailureReason.NONE)
        self.assertEqual(diagnostic.hwnd, 0)
        self.assertEqual(diagnostic.title, "")
        self.assertEqual(diagnostic.mode, "")
        self.assertEqual(diagnostic.stage, "")


if __name__ == "__main__":
    unittest.main()
