from __future__ import annotations

import json
from types import SimpleNamespace

from exporting.diagnostics import (
    build_export_diagnostic_summary,
    sanitize_diagnostic_text,
)
from exporting.models import ExportFailureKind, ExportStage
from exporting.queue_store import IngestionStatus


def test_diagnostics_redact_paths_and_environment_assignments() -> None:
    sensitive = r"C:\Users\win\Videos\private source.mp4"
    text = (
        f"failed input={sensitive}\n"
        r"APPDATA=C:\Users\win\AppData\Roaming"
        "\n"
        r"fallback D:\秘密 目录\other.mp4"
    )

    sanitized = sanitize_diagnostic_text(
        text,
        sensitive_paths=(sensitive,),
    )

    assert sensitive not in sanitized
    assert r"C:\Users\win\AppData\Roaming" not in sanitized
    assert r"D:\秘密 目录\other.mp4" not in sanitized
    assert "<path:" in sanitized
    assert "<environment:redacted>" in sanitized


def test_diagnostics_keep_utf8_tail_within_byte_limit() -> None:
    text = "前缀" + ("诊断尾部" * 30_000)

    sanitized = sanitize_diagnostic_text(text, limit_bytes=4096)

    assert sanitized
    assert sanitized.endswith("诊断尾部")
    assert len(sanitized.encode("utf-8")) <= 4096


def test_export_diagnostic_summary_covers_plan_attempt_and_ingestion() -> None:
    attempt = SimpleNamespace(
        attempt_id="attempt-1",
        sequence=1,
        trigger=SimpleNamespace(value="initial"),
        status=ExportStage.FAILED,
        failure_kind=ExportFailureKind.TOOL_FAILED,
        message=r"ffmpeg failed at C:\Users\win\private\source.mp4",
        diagnostic_path=r"C:\Users\win\diagnostics\attempt-1.txt",
    )
    job = SimpleNamespace(
        job_id="job-1",
        plan=SimpleNamespace(
            plan_id="plan-1",
            plan_hash="hash-1",
            project=SimpleNamespace(project_id="project-1"),
            output=SimpleNamespace(filename="result.mp4"),
        ),
        status=ExportStage.FAILED,
        progress_percent=42,
        eta_seconds=3.5,
        failure_kind=ExportFailureKind.TOOL_FAILED,
        message=r"PATH=C:\Tools; failed C:\Users\win\private\source.mp4",
        ingestion_status=IngestionStatus.FAILED,
        ingestion_error=r"index denied C:\Users\win\AppData\recordings.json",
        attempts=(attempt,),
        updated_at="2026-07-29T12:00:00+00:00",
    )
    state = SimpleNamespace(
        schema_version=1,
        paused=True,
        jobs=(job,),
    )

    summary = build_export_diagnostic_summary(
        state,
        ffmpeg_version="8.0.1",
        ffprobe_version="8.0.1",
        transaction_results=(
            {
                "status": "ambiguous",
                "stage": "commit",
                "message": r"target C:\Users\win\private\result.mp4 changed",
            },
        ),
    )

    text = json.dumps(summary, ensure_ascii=False)
    assert summary["ffmpeg_version"] == "8.0.1"
    assert summary["ffprobe_version"] == "8.0.1"
    assert summary["recent_jobs"][0]["plan_id"] == "plan-1"
    assert summary["recent_jobs"][0]["stage"] == "failed"
    assert summary["recent_jobs"][0]["attempt_count"] == 1
    assert summary["recent_jobs"][0]["ingestion_status"] == "failed"
    assert summary["recent_transactions"][0]["status"] == "ambiguous"
    assert r"C:\Users\win" not in text
    assert "PATH=" not in text
