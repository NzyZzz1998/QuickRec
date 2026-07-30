"""QuickRec 内部 CLI 的正式导出校验与隔离 smoke。"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from cli.commands import CliCommandContext
from cli.contracts import CliCommandOutcome, CliExitCode, CliFailure
from cli.isolation import CliIsolation
from exporting.diagnostics import sanitize_diagnostic_text
from exporting.executor import CancellationToken
from exporting.models import (
    ExportFailureKind,
    ExportPlan,
    ExportPlanBuildResult,
    ExportPlanRequest,
    ExportStage,
)
from exporting.plan_builder import ExportPlanBuilder
from exporting.queue_service import (
    AttemptRunner,
    ExportAttemptResult,
    ExportAttemptRunner,
)
from utils.media_metadata import resolve_ffmpeg_path, resolve_ffprobe_path

EXPORT_CLI_CONTRACT_SCHEMA = 1
_DEFAULT_FILENAME = "QuickRec-export-smoke.mp4"


class PlanBuilder(Protocol):
    def build(self, request: ExportPlanRequest) -> ExportPlanBuildResult: ...


RuntimeIdentityProvider = Callable[[], dict[str, object]]


def run_export_validate(
    context: CliCommandContext,
    project_path: str | Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 60,
    plan_builder: PlanBuilder | None = None,
    identity_provider: RuntimeIdentityProvider | None = None,
) -> CliCommandOutcome:
    """只读校验项目并构造一次不会被持久化的正式计划。"""
    context.require_positive_timeout()
    started = time.monotonic()
    builder = plan_builder or ExportPlanBuilder()
    with tempfile.TemporaryDirectory(
        prefix="quickrec-export-validate-"
    ) as temporary:
        plan, warnings = _build_plan(
            builder,
            project_path,
            output_directory=Path(temporary),
            width=width,
            height=height,
            fps=fps,
        )
        _require_remaining(started, context.timeout)
        return CliCommandOutcome(
            result={
                "contract_schema": EXPORT_CLI_CONTRACT_SCHEMA,
                "plan": _plan_summary(plan),
                "warnings": warnings,
                "runtime": (identity_provider or _runtime_identity)(),
            }
        )


def run_export_smoke(
    context: CliCommandContext,
    isolation: CliIsolation,
    project_path: str | Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 60,
    plan_builder: PlanBuilder | None = None,
    attempt_runner: AttemptRunner | None = None,
    identity_provider: RuntimeIdentityProvider | None = None,
) -> CliCommandOutcome:
    """在隔离目录执行真实计划、编码、验证和原子提交链路。"""
    context.require_positive_timeout()
    snapshot = isolation.activate()
    started = time.monotonic()
    try:
        plan, warnings = _build_plan(
            plan_builder or ExportPlanBuilder(),
            project_path,
            output_directory=isolation.output_dir,
            width=width,
            height=height,
            fps=fps,
        )
        remaining = _remaining(started, context.timeout)
        if remaining <= 0:
            raise _timeout()
        result, stages = _run_with_timeout(
            attempt_runner or ExportAttemptRunner(),
            plan,
            timeout=remaining,
        )
        if result.status != ExportStage.SUCCEEDED:
            raise _attempt_failure(result)
        target = Path(result.target_path or plan.output.target_path)
        if not target.is_file() or target.stat().st_size <= 0:
            raise CliFailure(
                CliExitCode.VALIDATION_FAILED,
                "export_output_missing",
                "导出执行完成但未生成可用正式文件",
            )
        report = {
            "contract_schema": EXPORT_CLI_CONTRACT_SCHEMA,
            "stage": result.status.value,
            "plan": _plan_summary(plan),
            "warnings": warnings,
            "stages": [stage.value for stage in stages],
            "output": {
                "file_name": target.name,
                "size_bytes": target.stat().st_size,
                "sha256": _sha256(target),
            },
            "runtime": (identity_provider or _runtime_identity)(),
        }
        evidence = isolation.evidence_dir / "export-smoke.json"
        _write_json(evidence, report)
        return CliCommandOutcome(
            result=report,
            evidence=[isolation.evidence_reference(evidence)],
        )
    finally:
        isolation.restore(snapshot)


def _build_plan(
    builder: PlanBuilder,
    project_path: str | Path,
    *,
    output_directory: Path,
    width: int,
    height: int,
    fps: int,
) -> tuple[ExportPlan, list[str]]:
    result = builder.build(
        ExportPlanRequest(
            project_path=str(Path(project_path).expanduser().resolve()),
            width=width,
            height=height,
            fps=fps,
            output_directory=str(output_directory),
            filename=_DEFAULT_FILENAME,
            accept_safe_suffix=True,
        )
    )
    if not result.ok or result.plan is None:
        issues = [issue.code for issue in result.errors]
        raise CliFailure(
            CliExitCode.VALIDATION_FAILED,
            "export_preflight_failed",
            "导出预检未通过",
            context={"issues": issues},
        )
    return result.plan, [issue.code for issue in result.warnings]


def _run_with_timeout(
    runner: AttemptRunner,
    plan: ExportPlan,
    *,
    timeout: float,
) -> tuple[ExportAttemptResult, list[ExportStage]]:
    token = CancellationToken()
    result_box: list[ExportAttemptResult] = []
    error_box: list[BaseException] = []
    stages: list[ExportStage] = []

    def execute() -> None:
        try:
            result_box.append(
                runner.run(
                    plan,
                    attempt_id=f"cli-{uuid.uuid4().hex}",
                    cancel_token=token,
                    on_progress=lambda _progress: None,
                    on_stage=stages.append,
                )
            )
        except BaseException as exc:
            error_box.append(exc)

    worker = threading.Thread(
        target=execute,
        daemon=True,
        name="QuickRecCliExportSmoke",
    )
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        token.cancel()
        worker.join(15.0)
        raise _timeout()
    if error_box:
        raise CliFailure(
            CliExitCode.INTERNAL_ERROR,
            "export_internal_error",
            "导出执行器发生未处理错误",
            context={"error_type": type(error_box[0]).__name__},
        )
    if not result_box:
        raise CliFailure(
            CliExitCode.INTERNAL_ERROR,
            "export_result_missing",
            "导出执行器未返回结果",
        )
    return result_box[0], stages


def _attempt_failure(result: ExportAttemptResult) -> CliFailure:
    failure = result.failure_kind
    if failure == ExportFailureKind.TOOL_MISSING:
        exit_code = CliExitCode.DEPENDENCY_MISSING
    elif failure in {
        ExportFailureKind.TOOL_TIMEOUT,
        ExportFailureKind.STALLED,
    }:
        exit_code = CliExitCode.TIMEOUT
    elif result.status == ExportStage.CANCELLED:
        exit_code = CliExitCode.CANCELLED
    else:
        exit_code = CliExitCode.VALIDATION_FAILED
    context: dict[str, object] = {
        "stage": result.status.value,
        "failure_kind": failure.value if failure is not None else "",
        "message": sanitize_diagnostic_text(result.message),
    }
    if result.exit_code is not None:
        context["tool_exit_code"] = result.exit_code
    if result.stderr_tail:
        context["stderr_tail"] = sanitize_diagnostic_text(
            result.stderr_tail,
        )
    return CliFailure(
        exit_code,
        "export_failed",
        "导出 smoke 未通过",
        context=context,
    )


def _plan_summary(plan: ExportPlan) -> dict[str, object]:
    return {
        "plan_schema": plan.plan_schema_version,
        "plan_hash": plan.plan_hash,
        "project_id": plan.project.project_id,
        "timeline_schema": plan.project.timeline_schema_version,
        "duration_us": plan.timeline.duration_us,
        "track_count": len(plan.timeline.tracks),
        "clip_count": len(plan.timeline.clips),
        "material_count": len(plan.materials),
        "material_fingerprints": [
            {
                "material_id": material.material_id,
                "size_bytes": material.size_bytes,
                "mtime_ns": material.mtime_ns,
                "video_codec": material.video_codec or "",
                "audio_codec": material.audio_codec or "",
            }
            for material in plan.materials
        ],
        "output": {
            "width": plan.output.width,
            "height": plan.output.height,
            "fps": plan.output.fps,
            "file_name": plan.output.filename,
            "estimated_size_bytes": plan.output.estimated_size_bytes,
        },
    }


def _runtime_identity() -> dict[str, object]:
    return {
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": _file_identity(Path(sys.executable)),
        "ffmpeg": _file_identity(Path(resolve_ffmpeg_path())),
        "ffprobe": _file_identity(Path(resolve_ffprobe_path())),
    }


def _file_identity(path: Path) -> dict[str, object]:
    try:
        if not path.is_file():
            return {
                "file_name": path.name,
                "available": False,
                "size_bytes": 0,
                "sha256": "",
            }
        return {
            "file_name": path.name,
            "available": True,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    except OSError:
        return {
            "file_name": path.name,
            "available": False,
            "size_bytes": 0,
            "sha256": "",
        }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise CliFailure(
            CliExitCode.ISOLATION_ERROR,
            "evidence_write_failed",
            "无法写入导出 smoke 证据",
            context={"error_type": type(exc).__name__},
        ) from exc


def _remaining(started: float, timeout: float) -> float:
    return timeout - (time.monotonic() - started)


def _require_remaining(started: float, timeout: float) -> None:
    if _remaining(started, timeout) <= 0:
        raise _timeout()


def _timeout() -> CliFailure:
    return CliFailure(
        CliExitCode.TIMEOUT,
        "export_timeout",
        "导出命令执行超时",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()
