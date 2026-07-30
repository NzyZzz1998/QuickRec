from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from cli import main as cli_main
from cli.contracts import (
    CliCommandOutcome,
    CliExitCode,
    CliFailure,
)


def test_parser_exposes_only_supported_command_tree() -> None:
    parser = cli_main.build_parser()

    doctor = parser.parse_args(["doctor", "--json"])
    project = parser.parse_args(["project", "validate", "project.qrproj"])
    timeline = parser.parse_args(["timeline", "validate", "project.qrproj"])
    export_validate = parser.parse_args(
        ["export", "validate", "project.qrproj", "--json"]
    )
    export_smoke = parser.parse_args(
        [
            "export",
            "smoke",
            "project.qrproj",
            "--output-dir",
            "output",
            "--evidence-dir",
            "evidence",
        ]
    )
    record = parser.parse_args(
        [
            "record",
            "--mode",
            "fullscreen",
            "--duration",
            "3",
            "--workspace",
            "workspace",
            "--evidence-dir",
            "evidence",
        ]
    )

    assert (doctor.command, doctor.timeout, doctor.json) == ("doctor", 30.0, True)
    assert project.project_command == "validate"
    assert timeline.timeline_command == "validate"
    assert export_validate.export_command == "validate"
    assert export_validate.json is True
    assert export_smoke.export_command == "smoke"
    assert export_smoke.width == 1920
    assert export_smoke.height == 1080
    assert export_smoke.fps == 60
    assert record.timeout is None
    assert record.audio == "none"
    assert record.fps == 30


def test_run_writes_one_json_report_for_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_main,
        "_dispatch",
        lambda _args: CliCommandOutcome(
            result={"available": True},
            evidence=["doctor.json"],
        ),
    )

    exit_code = cli_main.run(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == CliExitCode.SUCCESS
    assert payload["status"] == "success"
    assert payload["result"] == {"available": True}
    assert payload["evidence"] == ["doctor.json"]
    assert payload["identity"]["product"] == "QuickRec Full"


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (
            CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "invalid_media",
                "媒体不可用",
                context={"kind": "video"},
            ),
            "failed",
        ),
        (
            CliFailure(CliExitCode.TIMEOUT, "timeout", "命令超时"),
            "timeout",
        ),
        (
            CliFailure(CliExitCode.CANCELLED, "cancelled", "命令取消"),
            "cancelled",
        ),
    ],
)
def test_run_maps_cli_failure_to_json_contract(
    failure: CliFailure,
    expected_status: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_failure(_args: Namespace) -> CliCommandOutcome:
        raise failure

    monkeypatch.setattr(cli_main, "_dispatch", raise_failure)

    exit_code = cli_main.run(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == failure.exit_code
    assert payload["status"] == expected_status
    assert payload["errors"][0]["category"] == failure.category
    assert payload["errors"][0]["context"] == failure.context


def test_run_maps_keyboard_interrupt_to_cancelled_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def cancel(_args: Namespace) -> CliCommandOutcome:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_main, "_dispatch", cancel)

    exit_code = cli_main.run(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == CliExitCode.CANCELLED
    assert payload["status"] == "cancelled"
    assert payload["errors"][0]["category"] == "cancelled"


def test_run_redacts_unhandled_exception_from_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(_args: Namespace) -> CliCommandOutcome:
        raise RuntimeError(r"E:\Private\secret.mp4")

    monkeypatch.setattr(cli_main, "_dispatch", fail)

    exit_code = cli_main.run(["doctor", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == CliExitCode.INTERNAL_ERROR
    assert payload["errors"][0]["category"] == "internal_error"
    assert payload["errors"][0]["context"] == {"error_type": "RuntimeError"}
    assert "secret.mp4" not in captured.out


def test_run_writes_human_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_main,
        "_dispatch",
        lambda _args: CliCommandOutcome(result={"fps": 60}),
    )
    assert cli_main.run(["doctor"]) == CliExitCode.SUCCESS
    success = capsys.readouterr()
    assert "OK: doctor" in success.out
    assert '"fps": 60' in success.out

    def fail(_args: Namespace) -> CliCommandOutcome:
        raise CliFailure(CliExitCode.VALIDATION_FAILED, "invalid", "校验失败")

    monkeypatch.setattr(cli_main, "_dispatch", fail)
    assert cli_main.run(["doctor"]) == CliExitCode.VALIDATION_FAILED
    failure = capsys.readouterr()
    assert "FAILED: doctor" in failure.err
    assert "invalid: 校验失败" in failure.err


def test_dispatches_read_only_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = cli_main.build_parser()
    seen: list[tuple[str, object]] = []

    monkeypatch.setattr(
        cli_main,
        "run_doctor",
        lambda context: _record_dispatch(seen, "doctor", context.timeout),
    )
    monkeypatch.setattr(
        cli_main,
        "run_probe",
        lambda context, path: _record_dispatch(seen, "probe", (context.timeout, path)),
    )
    monkeypatch.setattr(
        cli_main,
        "run_project_validate",
        lambda context, path: _record_dispatch(
            seen,
            "project",
            (context.timeout, path),
        ),
    )
    monkeypatch.setattr(
        cli_main,
        "run_timeline_validate",
        lambda context, path: _record_dispatch(
            seen,
            "timeline",
            (context.timeout, path),
        ),
    )

    cli_main._dispatch(parser.parse_args(["doctor"]))
    cli_main._dispatch(parser.parse_args(["probe", "video.mp4"]))
    cli_main._dispatch(parser.parse_args(["project", "validate", "project.qrproj"]))
    cli_main._dispatch(parser.parse_args(["timeline", "validate", "project.qrproj"]))

    assert seen == [
        ("doctor", 30.0),
        ("probe", (30.0, "video.mp4")),
        ("project", (30.0, "project.qrproj")),
        ("timeline", (30.0, "project.qrproj")),
    ]


def test_dispatches_mutating_commands_with_isolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = cli_main.build_parser()
    seen: list[tuple[str, object]] = []
    record_workspace = tmp_path / "record-workspace"
    record_evidence = tmp_path / "record-evidence"
    smoke_workspace = tmp_path / "smoke-workspace"
    smoke_evidence = tmp_path / "smoke-evidence"

    def record_command(context, isolation, **kwargs):
        seen.append(
            (
                "record",
                (
                    context.timeout,
                    isolation.workspace,
                    isolation.evidence_dir,
                    kwargs,
                ),
            )
        )
        return CliCommandOutcome()

    def smoke_command(context, isolation, *, project_path):
        seen.append(
            (
                "smoke",
                (
                    context.timeout,
                    isolation.workspace,
                    isolation.evidence_dir,
                    project_path,
                ),
            )
        )
        return CliCommandOutcome()

    monkeypatch.setattr(cli_main, "run_record", record_command)
    monkeypatch.setattr(cli_main, "run_editing_smoke", smoke_command)
    monkeypatch.setattr(
        cli_main,
        "run_export_smoke",
        lambda context, isolation, project_path, **kwargs: _record_dispatch(
            seen,
            "export smoke",
            (
                context.timeout,
                isolation.output_dir,
                isolation.evidence_dir,
                project_path,
                kwargs,
            ),
        ),
    )

    record_args = parser.parse_args(
        [
            "record",
            "--mode",
            "fullscreen",
            "--duration",
            "3",
            "--fps",
            "60",
            "--audio",
            "system",
            "--workspace",
            str(record_workspace),
            "--evidence-dir",
            str(record_evidence),
        ]
    )
    smoke_args = parser.parse_args(
        [
            "smoke",
            "--suite",
            "editing",
            "--workspace",
            str(smoke_workspace),
            "--evidence-dir",
            str(smoke_evidence),
            "--project",
            "project.qrproj",
        ]
    )
    export_output = tmp_path / "export-output"
    export_evidence = tmp_path / "export-evidence"
    export_args = parser.parse_args(
        [
            "export",
            "smoke",
            "project.qrproj",
            "--output-dir",
            str(export_output),
            "--evidence-dir",
            str(export_evidence),
            "--width",
            "640",
            "--height",
            "360",
            "--fps",
            "30",
        ]
    )

    cli_main._dispatch(record_args)
    cli_main._dispatch(smoke_args)
    cli_main._dispatch(export_args)

    assert seen[0] == (
        "record",
        (
            63.0,
            record_workspace.resolve(),
            record_evidence.resolve(),
            {
                "mode": "fullscreen",
                "duration": 3.0,
                "fps": 60,
                "audio": "system",
            },
        ),
    )
    assert seen[1] == (
        "smoke",
        (
            900.0,
            smoke_workspace.resolve(),
            smoke_evidence.resolve(),
            "project.qrproj",
        ),
    )
    assert seen[2] == (
        "export smoke",
        (
            900.0,
            export_output.resolve(),
            export_evidence.resolve(),
            "project.qrproj",
            {
                "width": 640,
                "height": 360,
                "fps": 30,
            },
        ),
    )


def test_dispatch_rejects_unsupported_namespace() -> None:
    args = Namespace(command="unsupported", timeout=1.0)

    with pytest.raises(CliFailure) as raised:
        cli_main._dispatch(args)

    assert raised.value.exit_code == CliExitCode.USAGE_ERROR
    assert raised.value.category == "unsupported_command"


def test_command_name_includes_nested_subcommand() -> None:
    assert (
        cli_main._command_name(
            Namespace(
                command="timeline",
                project_command=None,
                timeline_command="validate",
            )
        )
        == "timeline validate"
    )
    assert (
        cli_main._command_name(
            Namespace(
                command="export",
                project_command=None,
                timeline_command=None,
                export_command="smoke",
            )
        )
        == "export smoke"
    )


def _record_dispatch(
    seen: list[tuple[str, object]],
    command: str,
    value: object,
) -> CliCommandOutcome:
    seen.append((command, value))
    return CliCommandOutcome()
