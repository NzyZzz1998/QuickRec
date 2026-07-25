from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QDialog

from services.capture_capability import SelfTestResult
from ui.capture_self_test_dialog import CaptureSelfTestDialog

APP = QApplication.instance() or QApplication([])


class FakeRuntime:
    def __init__(self, result: SelfTestResult) -> None:
        self.result = result

    def run(self, _cancel, *, progress):
        progress("capture", 42)
        return self.result


class FakeWorker:
    def __init__(self, alive: bool) -> None:
        self.alive = alive

    def is_alive(self) -> bool:
        return self.alive


class FakeCloseEvent:
    def __init__(self) -> None:
        self.ignored = False

    def ignore(self) -> None:
        self.ignored = True


def _result(*, status: str, passed: bool, reason: str = "") -> SelfTestResult:
    return SelfTestResult(
        status=status,
        passed=passed,
        average_fps=119.7,
        minimum_one_second_fps=117,
        failure_reason=reason,
    )


def test_dialog_progress_and_success_state():
    dialog = CaptureSelfTestDialog(FakeRuntime(_result(status="passed", passed=True)))

    dialog._on_progress("capture", 42)
    assert not dialog._progress.isTextVisible()
    dialog._on_finished(_result(status="passed", passed=True))

    assert dialog._progress.value() == 100
    assert dialog._progress.terminal_state == "passed"
    assert not dialog._progress.isTextVisible()
    assert "检测通过" in dialog._status.text()
    assert dialog._start.text() == "使用 120 FPS"
    assert dialog._diagnostics.isHidden()


def test_dialog_failure_keeps_retry_and_exposes_diagnostics():
    opened: list[bool] = []
    dialog = CaptureSelfTestDialog(
        FakeRuntime(_result(status="failed", passed=False)),
        open_diagnostics=lambda: opened.append(True),
    )

    dialog._on_finished(
        _result(status="failed", passed=False, reason="编码积压超过门禁")
    )

    assert dialog._progress.terminal_state == "failed"
    assert "编码积压超过门禁" in dialog._status.text()
    assert dialog._start.text() == "重新检测"
    assert not dialog._diagnostics.isHidden()
    dialog._show_diagnostics()
    assert opened == [True]
    assert dialog.result() == QDialog.Rejected


def test_dialog_cancelled_state_preserves_current_setting():
    dialog = CaptureSelfTestDialog(FakeRuntime(_result(status="cancelled", passed=False)))

    dialog._on_finished(_result(status="cancelled", passed=False))

    assert dialog._progress.terminal_state == "cancelled"
    assert "当前 FPS 设置未改变" in dialog._status.text()
    assert dialog._start.text() == "重新检测"


def test_dialog_cancel_running_worker_sets_event_and_waits_for_cleanup():
    dialog = CaptureSelfTestDialog(FakeRuntime(_result(status="cancelled", passed=False)))
    dialog._worker = FakeWorker(True)

    dialog._cancel_or_close()

    assert dialog._cancel_event.is_set()
    assert not dialog._cancel.isEnabled()
    assert "正在取消" in dialog._status.text()


def test_dialog_close_event_ignores_close_while_worker_is_alive():
    dialog = CaptureSelfTestDialog(FakeRuntime(_result(status="cancelled", passed=False)))
    dialog._worker = FakeWorker(True)
    event = FakeCloseEvent()

    dialog.closeEvent(event)

    assert event.ignored is True
    assert dialog._cancel_event.is_set()


def test_dialog_run_test_forwards_progress_and_result():
    result = _result(status="passed", passed=True)
    dialog = CaptureSelfTestDialog(FakeRuntime(result))
    finished = []
    dialog._bridge.finished.connect(finished.append)

    dialog._run_test()
    APP.processEvents()

    assert finished == [result]
    assert dialog._progress.value() == 100
    assert dialog._progress.terminal_state == "passed"


def test_execute_returns_only_passed_result(monkeypatch):
    passed = _result(status="passed", passed=True)

    def fake_exec(self):
        self._test_result = passed
        return QDialog.Accepted

    monkeypatch.setattr(CaptureSelfTestDialog, "exec_", fake_exec)

    assert CaptureSelfTestDialog.execute(FakeRuntime(passed)) == passed
