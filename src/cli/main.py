from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from typing import Any

from cli.commands import (
    CliCommandContext,
    run_doctor,
    run_editing_smoke,
    run_probe,
    run_project_validate,
    run_record,
    run_timeline_validate,
)
from cli.contracts import (
    CliCommandOutcome,
    CliError,
    CliExitCode,
    CliFailure,
    CliIdentity,
    CliReport,
    status_for_exit_code,
)
from cli.export_commands import run_export_smoke, run_export_validate
from cli.isolation import CliIsolation
from version import APP_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="QuickRecCLI",
        description="QuickRec Full 内部自动化 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="检查运行依赖")
    _add_common_options(doctor, default_timeout=30.0)

    probe = subparsers.add_parser("probe", help="读取媒体元数据")
    probe.add_argument("video")
    _add_common_options(probe, default_timeout=30.0)

    project = subparsers.add_parser("project", help="项目文件操作")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    project_validate = project_commands.add_parser("validate", help="只读校验项目")
    project_validate.add_argument("project_file")
    _add_common_options(project_validate, default_timeout=30.0)

    timeline = subparsers.add_parser("timeline", help="时间线操作")
    timeline_commands = timeline.add_subparsers(
        dest="timeline_command",
        required=True,
    )
    timeline_validate = timeline_commands.add_parser(
        "validate",
        help="只读校验时间线",
    )
    timeline_validate.add_argument("project_file")
    _add_common_options(timeline_validate, default_timeout=30.0)

    export = subparsers.add_parser("export", help="导出项目时间线")
    export_commands = export.add_subparsers(
        dest="export_command",
        required=True,
    )
    export_validate = export_commands.add_parser(
        "validate",
        help="只读校验正式导出计划",
    )
    export_validate.add_argument("project_file")
    _add_export_spec_options(export_validate)
    _add_common_options(export_validate, default_timeout=60.0)
    export_smoke = export_commands.add_parser(
        "smoke",
        help="在隔离环境执行正式短样本导出",
    )
    export_smoke.add_argument("project_file")
    export_smoke.add_argument("--output-dir", required=True)
    export_smoke.add_argument("--evidence-dir", required=True)
    _add_export_spec_options(export_smoke)
    _add_common_options(export_smoke, default_timeout=900.0)

    record = subparsers.add_parser("record", help="在隔离环境执行全屏录制")
    record.add_argument("--mode", choices=["fullscreen"], required=True)
    record.add_argument("--duration", type=float, required=True)
    record.add_argument("--fps", type=int, choices=[30, 60, 120], default=30)
    record.add_argument(
        "--audio",
        choices=["none", "system", "mic", "both"],
        default="none",
    )
    record.add_argument("--workspace", required=True)
    record.add_argument("--evidence-dir", required=True)
    _add_common_options(record, default_timeout=None)

    smoke = subparsers.add_parser("smoke", help="在隔离环境执行验证套件")
    smoke.add_argument("--suite", choices=["editing"], required=True)
    smoke.add_argument("--workspace", required=True)
    smoke.add_argument("--evidence-dir", required=True)
    smoke.add_argument("--project", default="")
    _add_common_options(smoke, default_timeout=900.0)
    return parser


def run(argv: list[str] | None = None) -> int:
    _force_utf8_streams()
    args = build_parser().parse_args(argv)
    json_mode = bool(args.json)
    _configure_logging()
    started_perf = time.monotonic()
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    command_name = _command_name(args)
    exit_code = CliExitCode.SUCCESS
    outcome = CliCommandOutcome()
    errors: list[CliError] = []
    try:
        outcome = _dispatch(args)
    except CliFailure as exc:
        exit_code = exc.exit_code
        errors = [exc.to_error()]
    except KeyboardInterrupt:
        exit_code = CliExitCode.CANCELLED
        errors = [CliError("cancelled", "命令已取消")]
    except Exception as exc:
        logging.getLogger("QuickRecCLI").exception("unhandled CLI error")
        exit_code = CliExitCode.INTERNAL_ERROR
        errors = [
            CliError(
                "internal_error",
                "QuickRecCLI 发生未处理错误",
                {"error_type": type(exc).__name__},
            )
        ]

    report = CliReport(
        command=command_name,
        status=status_for_exit_code(exit_code),
        exit_code=exit_code,
        started_at=started_at,
        duration_ms=max(0, round((time.monotonic() - started_perf) * 1000)),
        identity=_identity(),
        result=outcome.result,
        errors=errors,
        evidence=outcome.evidence,
    )
    if json_mode:
        sys.stdout.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")
    else:
        _write_human_report(report.to_dict())
    return int(exit_code)


def _dispatch(args: argparse.Namespace) -> CliCommandOutcome:
    timeout = (
        float(args.timeout)
        if args.timeout is not None
        else float(args.duration) + 60.0
    )
    context = CliCommandContext(timeout=timeout)
    if args.command == "doctor":
        return run_doctor(context)
    if args.command == "probe":
        return run_probe(context, args.video)
    if args.command == "project" and args.project_command == "validate":
        return run_project_validate(context, args.project_file)
    if args.command == "timeline" and args.timeline_command == "validate":
        return run_timeline_validate(context, args.project_file)
    if args.command == "export" and args.export_command == "validate":
        return run_export_validate(
            context,
            args.project_file,
            width=int(args.width),
            height=int(args.height),
            fps=int(args.fps),
        )
    if args.command == "export" and args.export_command == "smoke":
        isolation = CliIsolation.prepare_export(
            args.output_dir,
            args.evidence_dir,
        )
        return run_export_smoke(
            context,
            isolation,
            args.project_file,
            width=int(args.width),
            height=int(args.height),
            fps=int(args.fps),
        )
    if args.command == "record":
        isolation = CliIsolation.prepare(args.workspace, args.evidence_dir)
        return run_record(
            context,
            isolation,
            mode=args.mode,
            duration=float(args.duration),
            fps=int(args.fps),
            audio=args.audio,
        )
    if args.command == "smoke" and args.suite == "editing":
        isolation = CliIsolation.prepare(args.workspace, args.evidence_dir)
        return run_editing_smoke(
            context,
            isolation,
            project_path=args.project or None,
        )
    raise CliFailure(
        CliExitCode.USAGE_ERROR,
        "unsupported_command",
        "不支持的命令",
    )


def _command_name(args: argparse.Namespace) -> str:
    parts = [str(args.command)]
    for attribute in ("project_command", "timeline_command", "export_command"):
        value = getattr(args, attribute, None)
        if value:
            parts.append(str(value))
    return " ".join(parts)


def _identity() -> CliIdentity:
    version = str(APP_VERSION).removeprefix("v")
    return CliIdentity(
        product="QuickRec Full",
        version=version,
        frozen=bool(getattr(sys, "frozen", False)),
    )


def _add_common_options(
    parser: argparse.ArgumentParser,
    *,
    default_timeout: float | None,
) -> None:
    parser.add_argument("--json", action="store_true", help="输出 JSON v1")
    parser.add_argument("--timeout", type=float, default=default_timeout)


def _add_export_spec_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, choices=[30, 60, 120], default=60)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
        force=True,
    )


def _force_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _write_human_report(report: dict[str, Any]) -> None:
    if report["status"] == "success":
        print(f"OK: {report['command']}")
        if report["result"]:
            print(json.dumps(report["result"], ensure_ascii=False, indent=2))
        return
    print(f"FAILED: {report['command']}", file=sys.stderr)
    for error in report["errors"]:
        print(f"- {error['category']}: {error['message']}", file=sys.stderr)


def main() -> int:
    return run()
