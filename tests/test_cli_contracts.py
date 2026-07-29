from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from cli.contracts import (
    CliError,
    CliExitCode,
    CliIdentity,
    CliReport,
    CliStatus,
)


def test_cli_report_uses_stable_json_v1_contract() -> None:
    report = CliReport(
        command="timeline validate",
        status=CliStatus.SUCCESS,
        exit_code=CliExitCode.SUCCESS,
        started_at="2026-07-29T00:00:00+08:00",
        duration_ms=123,
        identity=CliIdentity(
            product="QuickRec Full",
            version="1.9.3",
            frozen=False,
        ),
        result={"timeline_schema": 2},
        errors=[],
        evidence=["reports/timeline.json"],
    )

    assert report.to_dict() == {
        "schema_version": 1,
        "command": "timeline validate",
        "status": "success",
        "exit_code": 0,
        "started_at": "2026-07-29T00:00:00+08:00",
        "duration_ms": 123,
        "identity": {
            "product": "QuickRec Full",
            "version": "1.9.3",
            "frozen": False,
        },
        "result": {"timeline_schema": 2},
        "errors": [],
        "evidence": ["reports/timeline.json"],
    }


def test_cli_report_errors_have_stable_category_message_and_context() -> None:
    error = CliError(
        category="invalid_project",
        message="项目文件不可用",
        context={"status": "corrupt"},
    )

    assert error.to_dict() == {
        "category": "invalid_project",
        "message": "项目文件不可用",
        "context": {"status": "corrupt"},
    }


def test_json_mode_stdout_contains_exactly_one_json_object(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "src/cli_entry.py",
            "doctor",
            "--json",
            "--timeout",
            "30",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )

    payload = json.loads(completed.stdout)
    assert completed.stdout.count("\n") <= 1
    assert payload["schema_version"] == 1
    assert payload["command"] == "doctor"
    assert payload["exit_code"] == completed.returncode
    assert set(payload) == {
        "schema_version",
        "command",
        "status",
        "exit_code",
        "started_at",
        "duration_ms",
        "identity",
        "result",
        "errors",
        "evidence",
    }


def test_cli_entry_import_graph_does_not_import_ui_modules() -> None:
    script = (
        "import sys; import cli_entry; "
        "print(any(name == 'ui' or name.startswith('ui.') for name in sys.modules))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env={
            **dict(__import__("os").environ),
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        },
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert completed.stdout.strip() == "False"


def test_mutating_cli_commands_require_workspace_and_evidence() -> None:
    root = Path(__file__).resolve().parents[1]
    for arguments in (
        [
            "record",
            "--mode",
            "fullscreen",
            "--duration",
            "1",
            "--fps",
            "30",
            "--audio",
            "none",
        ],
        ["smoke", "--suite", "editing"],
    ):
        completed = subprocess.run(
            [sys.executable, "src/cli_entry.py", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        assert completed.returncode == int(CliExitCode.USAGE_ERROR)


def test_json_failure_keeps_stdout_machine_readable_and_utf8(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "src/cli_entry.py",
            "probe",
            str(tmp_path / "不存在.mp4"),
            "--json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == int(CliExitCode.VALIDATION_FAILED)
    assert payload["status"] == "failed"
    assert payload["errors"][0]["category"] == "media_missing"
    assert payload["errors"][0]["context"]["file_name"] == "不存在.mp4"


def test_cli_does_not_expose_destructive_project_or_material_commands() -> None:
    completed = subprocess.run(
        [sys.executable, "src/cli_entry.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    lowered = completed.stdout.lower()
    assert "delete" not in lowered
    assert "remove" not in lowered
    assert "trim" not in lowered
    assert "split" not in lowered
    assert "ripple" not in lowered
