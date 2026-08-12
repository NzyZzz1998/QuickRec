from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication, QDialog

from ui.config_migration_dialog import ConfigMigrationDialog
from utils.config_migration import MigrationResult

app = QApplication.instance() or QApplication(sys.argv)


class FakeMigration:
    def __init__(self, import_result: MigrationResult, defaults_result: MigrationResult) -> None:
        self.import_result = import_result
        self.defaults_result = defaults_result
        self.import_calls = 0
        self.default_calls = 0

    def import_settings(self) -> MigrationResult:
        self.import_calls += 1
        return self.import_result

    def use_defaults(self) -> MigrationResult:
        self.default_calls += 1
        return self.defaults_result


def test_import_success_accepts_and_shows_field_fallbacks() -> None:
    service = FakeMigration(
        MigrationResult(True, "import", warnings=("旧音频模式无效，已使用无声。",)),
        MigrationResult(True, "defaults"),
    )
    dialog = ConfigMigrationDialog(service)

    dialog._import_settings()

    assert service.import_calls == 1
    assert dialog.result() == QDialog.Accepted
    assert "旧音频模式无效" in dialog.feedback_text


def test_import_failure_keeps_dialog_open_for_retry() -> None:
    service = FakeMigration(
        MigrationResult(False, "replace", "permission denied"),
        MigrationResult(True, "defaults"),
    )
    dialog = ConfigMigrationDialog(service)

    dialog._import_settings()

    assert dialog.result() == QDialog.Rejected
    assert "permission denied" in dialog.feedback_text
    assert dialog._btn_import.isEnabled()


def test_defaults_success_accepts_without_reading_legacy() -> None:
    service = FakeMigration(
        MigrationResult(False, "read_legacy", "broken"),
        MigrationResult(True, "defaults"),
    )
    dialog = ConfigMigrationDialog(service)

    dialog._use_defaults()

    assert service.import_calls == 0
    assert service.default_calls == 1
    assert dialog.result() == QDialog.Accepted
