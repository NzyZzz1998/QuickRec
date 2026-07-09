import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ConfigManager
from utils.diagnostics import (
    DiagnosticSnapshot,
    ensure_diagnostic_dir,
    export_diagnostic_file,
    format_snapshot_text,
    initialize_file_logging,
    is_diagnostic_dir_writable,
    open_diagnostic_dir,
    read_recent_log_lines,
    resolve_diagnostic_dir,
)


class TestDiagnostics(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.config = ConfigManager.__new__(ConfigManager)
        self.config.config_path = self.base_path / "config.json"
        self.config._config = ConfigManager.defaults.copy()
        self.config.set("save_path", str(self.base_path / "videos"))

    def tearDown(self):
        for logger_name in (
            "QuickRec.test.file_logging",
            "QuickRec.test.file_logging_fallback",
        ):
            logger = logging.getLogger(logger_name)
            for handler in list(logger.handlers):
                if getattr(handler, "_quickrec_diagnostic_handler", False):
                    logger.removeHandler(handler)
                    handler.close()
        self.temp_dir.cleanup()

    def test_resolve_diagnostic_dir_uses_config_default(self):
        path = resolve_diagnostic_dir(self.config)

        self.assertEqual(path, self.base_path / "videos" / "QuickRecDiagnostics")

    def test_resolve_diagnostic_dir_accepts_override(self):
        override = self.base_path / "override"

        path = resolve_diagnostic_dir(self.config, override)

        self.assertEqual(path, override)

    def test_ensure_diagnostic_dir_creates_directory(self):
        target = self.base_path / "diagnostics"

        result = ensure_diagnostic_dir(target)

        self.assertTrue(result.ok)
        self.assertEqual(result.path, target)
        self.assertTrue(target.is_dir())

    def test_is_diagnostic_dir_writable_returns_true_for_writable_dir(self):
        target = self.base_path / "diagnostics"
        target.mkdir()

        self.assertTrue(is_diagnostic_dir_writable(target))

    def test_format_snapshot_text_uses_unknown_for_missing_fields(self):
        snapshot = DiagnosticSnapshot(
            app={"version": "v1.4.x"},
            config={"save_path": ""},
            recorder={},
            ffmpeg={},
            audio={},
            window={},
            errors=[],
            recent_logs=[],
        )

        text = format_snapshot_text(snapshot)

        self.assertIn("version: v1.4.x", text)
        self.assertIn("save_path: unknown", text)
        self.assertIn("state: unknown", text)

    def test_export_diagnostic_file_writes_utf8_named_file(self):
        target = self.base_path / "diagnostics"

        result = export_diagnostic_file("诊断信息", target)

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.path)
        self.assertRegex(result.path.name, r"diagnostic_\d{8}_\d{6}\.txt")
        self.assertEqual(result.path.read_text(encoding="utf-8"), "诊断信息")

    def test_read_recent_log_lines_returns_tail(self):
        log_path = self.base_path / "quickrec.log"
        log_path.write_text("\n".join(f"line-{i}" for i in range(105)), encoding="utf-8")

        lines = read_recent_log_lines(log_path, max_lines=3)

        self.assertEqual(lines, ["line-102", "line-103", "line-104"])

    def test_open_diagnostic_dir_calls_os_startfile(self):
        target = self.base_path / "diagnostics"
        target.mkdir()

        with patch("utils.diagnostics.os.startfile") as startfile:
            result = open_diagnostic_dir(target)

        self.assertTrue(result.ok)
        startfile.assert_called_once_with(str(target))

    def test_export_diagnostic_file_reports_write_failure(self):
        file_path = self.base_path / "not-a-directory.txt"
        file_path.write_text("x", encoding="utf-8")

        result = export_diagnostic_file("诊断信息", file_path)

        self.assertFalse(result.ok)
        self.assertIsNone(result.path)
        self.assertTrue(result.error)

    def test_initialize_file_logging_creates_quickrec_log_and_keeps_existing_handlers(self):
        logger = logging.getLogger("QuickRec.test.file_logging")
        logger.handlers.clear()
        existing_handler = logging.StreamHandler()
        logger.addHandler(existing_handler)
        logger.setLevel(logging.INFO)

        result = initialize_file_logging(self.config, logger)
        logger.info("diagnostic log line")
        for handler in logger.handlers:
            handler.flush()

        log_path = result.path / "quickrec.log"
        self.assertTrue(result.ok)
        self.assertIn(existing_handler, logger.handlers)
        self.assertTrue(log_path.exists())
        self.assertIn("diagnostic log line", log_path.read_text(encoding="utf-8"))

    def test_initialize_file_logging_falls_back_when_directory_unavailable(self):
        logger = logging.getLogger("QuickRec.test.file_logging_fallback")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        invalid_dir = self.base_path / "not-a-directory.txt"
        invalid_dir.write_text("x", encoding="utf-8")
        fallback_dir = self.base_path / "fallback"

        result = initialize_file_logging(
            self.config,
            logger,
            diagnostic_dir=invalid_dir,
            fallback_dir=fallback_dir,
        )
        logger.info("after fallback")
        for handler in logger.handlers:
            handler.flush()

        log_path = fallback_dir / "quickrec.log"
        self.assertTrue(result.ok)
        self.assertEqual(result.path, fallback_dir)
        self.assertTrue(log_path.exists())
        text = log_path.read_text(encoding="utf-8")
        self.assertIn("diagnostic directory fallback", text)
        self.assertIn("after fallback", text)


if __name__ == "__main__":
    unittest.main()
