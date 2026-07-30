from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from cli.commands import CliCommandContext
from cli.contracts import CliExitCode, CliFailure
from cli.export_commands import run_export_smoke, run_export_validate
from cli.isolation import CliIsolation
from exporting.models import (
    ExportClip,
    ExportFailureKind,
    ExportMaterialSnapshot,
    ExportOutputSpec,
    ExportPlan,
    ExportPlanBuildResult,
    ExportPlanIssue,
    ExportProjectSnapshot,
    ExportStage,
    ExportTimelineSnapshot,
    ExportTrack,
    RenderPolicy,
)
from exporting.queue_service import ExportAttemptResult
from utils.recording_library_store import normalize_windows_path


def _plan(request, source: Path) -> ExportPlan:
    stat = source.stat()
    return ExportPlan.create(
        plan_id="cli-plan",
        created_at="2026-07-29T18:00:00+08:00",
        project=ExportProjectSnapshot(
            "project-cli-export",
            "CLI 导出项目",
            request.project_path,
            1,
            2,
        ),
        timeline=ExportTimelineSnapshot(
            "timeline-cli-export",
            1_000_000,
            (ExportTrack("video-1", "video", 0),),
            (
                ExportClip(
                    "clip-1",
                    "material-1",
                    "video-1",
                    None,
                    0,
                    1_000_000,
                    0,
                    1_000_000,
                ),
            ),
        ),
        materials=(
            ExportMaterialSnapshot(
                "material-1",
                str(source),
                normalize_windows_path(source),
                stat.st_size,
                stat.st_mtime_ns,
                "mov,mp4,m4a,3gp,3g2,mj2",
                "h264",
                640,
                360,
                30.0,
                1_000_000,
                None,
                None,
                None,
                None,
            ),
        ),
        render_policy=RenderPolicy(),
        output=ExportOutputSpec(
            request.width,
            request.height,
            request.fps,
            request.output_directory,
            request.filename,
            estimated_size_bytes=1024,
        ),
    )


class _Builder:
    def __init__(self, source: Path, *, fail: bool = False) -> None:
        self.source = source
        self.fail = fail
        self.requests = []

    def build(self, request):
        self.requests.append(request)
        if self.fail:
            return ExportPlanBuildResult(
                False,
                errors=(
                    ExportPlanIssue(
                        "MATERIAL_MISSING",
                        "素材文件已移动或删除",
                    ),
                ),
            )
        return ExportPlanBuildResult(
            True,
            plan=_plan(request, self.source),
            warnings=(
                ExportPlanIssue(
                    "DISK_SPACE_WARNING",
                    "可用空间低于保守估算值的 1.5 倍",
                ),
            ),
        )


class _Runner:
    def __init__(self) -> None:
        self.calls = []

    def run(
        self,
        plan,
        *,
        attempt_id,
        cancel_token,
        on_progress,
        on_stage,
    ):
        self.calls.append((plan, attempt_id, cancel_token))
        on_stage(ExportStage.RUNNING)
        target = plan.output.target_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"controlled-export")
        return ExportAttemptResult(
            ExportStage.SUCCEEDED,
            target_path=target,
        )


def test_export_validate_is_read_only_and_reports_stable_plan_summary(
    tmp_path: Path,
) -> None:
    project = tmp_path / "项目 空格.qrproj"
    project.write_text('{"project":"unchanged"}', encoding="utf-8")
    source = tmp_path / "中文 素材.mp4"
    source.write_bytes(b"source")
    before = project.read_bytes()
    builder = _Builder(source)

    outcome = run_export_validate(
        CliCommandContext(timeout=30),
        project,
        plan_builder=builder,
        identity_provider=lambda: {"frozen": False},
    )

    assert project.read_bytes() == before
    assert outcome.result["contract_schema"] == 1
    assert outcome.result["plan"]["plan_hash"]
    assert outcome.result["plan"]["timeline_schema"] == 2
    assert outcome.result["plan"]["clip_count"] == 1
    assert outcome.result["warnings"] == ["DISK_SPACE_WARNING"]
    assert str(tmp_path) not in json.dumps(outcome.result, ensure_ascii=False)


def test_export_validate_maps_preflight_failure_without_writing_output(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project.qrproj"
    project.write_text("unchanged", encoding="utf-8")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")

    with pytest.raises(CliFailure) as raised:
        run_export_validate(
            CliCommandContext(timeout=30),
            project,
            plan_builder=_Builder(source, fail=True),
        )

    assert raised.value.exit_code == CliExitCode.VALIDATION_FAILED
    assert raised.value.category == "export_preflight_failed"
    assert raised.value.context["issues"] == ["MATERIAL_MISSING"]


def test_export_smoke_uses_isolation_and_writes_machine_readable_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project.qrproj"
    project.write_text("unchanged", encoding="utf-8")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    before = project.read_bytes()
    output = tmp_path / "输出 空格"
    evidence = tmp_path / "证据 空格"
    isolation = CliIsolation.prepare_export(output, evidence)
    builder = _Builder(source)
    runner = _Runner()
    monkeypatch.setenv("APPDATA", str(tmp_path / "real-appdata"))

    outcome = run_export_smoke(
        CliCommandContext(timeout=30),
        isolation,
        project,
        width=640,
        height=360,
        fps=30,
        plan_builder=builder,
        attempt_runner=runner,
        identity_provider=lambda: {"frozen": False},
    )

    assert project.read_bytes() == before
    assert os.environ.get("APPDATA") == str(tmp_path / "real-appdata")
    assert outcome.result["stage"] == "succeeded"
    assert outcome.result["output"]["file_name"] == "QuickRec-export-smoke.mp4"
    assert len(outcome.result["output"]["sha256"]) == 64
    assert outcome.evidence == ["export-smoke.json"]
    assert (evidence / "export-smoke.json").is_file()
    assert (output / "QuickRec-export-smoke.mp4").read_bytes() == b"controlled-export"
    assert str(tmp_path) not in json.dumps(outcome.result, ensure_ascii=False)
    assert len(runner.calls) == 1


def test_export_smoke_timeout_cancels_attempt(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project.qrproj"
    project.write_text("unchanged", encoding="utf-8")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    isolation = CliIsolation.prepare_export(
        tmp_path / "output",
        tmp_path / "evidence",
    )

    class BlockingRunner:
        cancelled = False

        def run(
            self,
            _plan,
            *,
            attempt_id,
            cancel_token,
            on_progress,
            on_stage,
        ):
            del attempt_id, on_progress
            on_stage(ExportStage.RUNNING)
            while not cancel_token.is_cancelled:
                time.sleep(0.001)
            self.cancelled = True
            return ExportAttemptResult(
                ExportStage.CANCELLED,
                failure_kind=ExportFailureKind.CANCELLED,
                message="cancelled",
            )

    runner = BlockingRunner()
    with pytest.raises(CliFailure) as raised:
        run_export_smoke(
            CliCommandContext(timeout=0.5),
            isolation,
            project,
            width=640,
            height=360,
            fps=30,
            plan_builder=_Builder(source),
            attempt_runner=runner,
        )

    assert raised.value.exit_code == CliExitCode.TIMEOUT
    assert raised.value.category == "export_timeout"
    assert runner.cancelled


@pytest.mark.parametrize(
    ("status", "failure_kind", "expected_exit"),
    [
        (
            ExportStage.FAILED,
            ExportFailureKind.TOOL_MISSING,
            CliExitCode.DEPENDENCY_MISSING,
        ),
        (
            ExportStage.FAILED,
            ExportFailureKind.TOOL_TIMEOUT,
            CliExitCode.TIMEOUT,
        ),
        (
            ExportStage.FAILED,
            ExportFailureKind.STALLED,
            CliExitCode.TIMEOUT,
        ),
        (
            ExportStage.CANCELLED,
            ExportFailureKind.CANCELLED,
            CliExitCode.CANCELLED,
        ),
        (
            ExportStage.FAILED,
            ExportFailureKind.TOOL_FAILED,
            CliExitCode.VALIDATION_FAILED,
        ),
    ],
)
def test_export_smoke_maps_attempt_failures_to_stable_exit_codes(
    tmp_path: Path,
    status: ExportStage,
    failure_kind: ExportFailureKind,
    expected_exit: CliExitCode,
) -> None:
    project = tmp_path / "project.qrproj"
    project.write_text("unchanged", encoding="utf-8")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    isolation = CliIsolation.prepare_export(
        tmp_path / "output",
        tmp_path / "evidence",
    )

    class FailedRunner:
        def run(
            self,
            _plan,
            *,
            attempt_id,
            cancel_token,
            on_progress,
            on_stage,
        ):
            del attempt_id, cancel_token, on_progress
            on_stage(status)
            return ExportAttemptResult(
                status,
                failure_kind=failure_kind,
                message="controlled",
            )

    with pytest.raises(CliFailure) as raised:
        run_export_smoke(
            CliCommandContext(timeout=30),
            isolation,
            project,
            plan_builder=_Builder(source),
            attempt_runner=FailedRunner(),
            identity_provider=lambda: {"frozen": False},
        )

    assert raised.value.exit_code == expected_exit
    assert raised.value.category == "export_failed"


def test_export_smoke_failure_includes_sanitized_tool_diagnostics(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project.qrproj"
    project.write_text("unchanged", encoding="utf-8")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    isolation = CliIsolation.prepare_export(
        tmp_path / "output",
        tmp_path / "evidence",
    )

    class FailedRunner:
        def run(
            self,
            _plan,
            *,
            attempt_id,
            cancel_token,
            on_progress,
            on_stage,
        ):
            del attempt_id, cancel_token, on_progress
            on_stage(ExportStage.FAILED)
            return ExportAttemptResult(
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.TOOL_FAILED,
                message="FFmpeg returned nonzero",
                exit_code=22,
                stderr_tail=f"decode failed for {source}",
            )

    with pytest.raises(CliFailure) as raised:
        run_export_smoke(
            CliCommandContext(timeout=30),
            isolation,
            project,
            plan_builder=_Builder(source),
            attempt_runner=FailedRunner(),
        )

    context = raised.value.context
    assert context["message"] == "FFmpeg returned nonzero"
    assert context["tool_exit_code"] == 22
    assert "<path:redacted>" in str(context["stderr_tail"])
    assert str(source) not in str(context["stderr_tail"])


def test_export_smoke_maps_runner_exception_and_missing_output(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project.qrproj"
    project.write_text("unchanged", encoding="utf-8")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")

    class RaisingRunner:
        def run(self, *_args, **_kwargs):
            raise RuntimeError("controlled")

    with pytest.raises(CliFailure) as raised:
        run_export_smoke(
            CliCommandContext(timeout=30),
            CliIsolation.prepare_export(
                tmp_path / "raise-output",
                tmp_path / "raise-evidence",
            ),
            project,
            plan_builder=_Builder(source),
            attempt_runner=RaisingRunner(),
            identity_provider=lambda: {"frozen": False},
        )
    assert raised.value.exit_code == CliExitCode.INTERNAL_ERROR
    assert raised.value.category == "export_internal_error"

    class MissingOutputRunner:
        def run(
            self,
            _plan,
            *,
            attempt_id,
            cancel_token,
            on_progress,
            on_stage,
        ):
            del attempt_id, cancel_token, on_progress
            on_stage(ExportStage.SUCCEEDED)
            return ExportAttemptResult(
                ExportStage.SUCCEEDED,
                target_path=tmp_path / "missing.mp4",
            )

    with pytest.raises(CliFailure) as missing:
        run_export_smoke(
            CliCommandContext(timeout=30),
            CliIsolation.prepare_export(
                tmp_path / "missing-output",
                tmp_path / "missing-evidence",
            ),
            project,
            plan_builder=_Builder(source),
            attempt_runner=MissingOutputRunner(),
            identity_provider=lambda: {"frozen": False},
        )
    assert missing.value.exit_code == CliExitCode.VALIDATION_FAILED
    assert missing.value.category == "export_output_missing"
