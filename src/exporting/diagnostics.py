"""导出诊断文本的本地隐私清洗与大小限制。"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

MAX_DIAGNOSTIC_TEXT_BYTES = 64 * 1024
_WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?i)(?<![A-Za-z0-9_])[A-Z]:[\\/][^\r\n\"'<>|]*"
)
_ENV_ASSIGNMENT = re.compile(
    r"(?i)\b(?:APPDATA|LOCALAPPDATA|USERPROFILE|TEMP|TMP|PATH)=[^\r\n;]*"
)

_ACTIVE_EXPORT_STAGES = {
    "validating",
    "running",
    "cancelling",
    "verifying",
    "committing",
}


def build_export_diagnostic_summary(
    state: Any,
    *,
    ffmpeg_version: str = "",
    ffprobe_version: str = "",
    transaction_results: Iterable[Mapping[str, Any]] = (),
    limit: int = 10,
) -> dict[str, Any]:
    """生成不含完整本地路径的导出队列诊断摘要。"""
    jobs = tuple(getattr(state, "jobs", ()))
    recent_jobs: list[dict[str, Any]] = []
    for job in sorted(
        jobs,
        key=lambda item: str(getattr(item, "updated_at", "")),
        reverse=True,
    )[: max(0, limit)]:
        attempts = tuple(getattr(job, "attempts", ()))
        latest = attempts[-1] if attempts else None
        plan = getattr(job, "plan", None)
        project = getattr(plan, "project", None)
        output = getattr(plan, "output", None)
        recent_jobs.append(
            {
                "job_id": str(getattr(job, "job_id", "")),
                "plan_id": str(getattr(plan, "plan_id", "")),
                "plan_hash": str(getattr(plan, "plan_hash", "")),
                "project_id": str(getattr(project, "project_id", "")),
                "output_file": Path(
                    str(getattr(output, "filename", ""))
                ).name,
                "stage": _value(getattr(job, "status", "")),
                "progress_percent": int(
                    getattr(job, "progress_percent", 0)
                ),
                "eta_seconds": getattr(job, "eta_seconds", None),
                "failure_kind": _value(
                    getattr(job, "failure_kind", None)
                ),
                "message": sanitize_diagnostic_text(
                    str(getattr(job, "message", ""))
                ),
                "attempt_count": len(attempts),
                "latest_attempt": (
                    {
                        "attempt_id": str(
                            getattr(latest, "attempt_id", "")
                        ),
                        "sequence": int(getattr(latest, "sequence", 0)),
                        "trigger": _value(
                            getattr(latest, "trigger", "")
                        ),
                        "stage": _value(getattr(latest, "status", "")),
                        "failure_kind": _value(
                            getattr(latest, "failure_kind", None)
                        ),
                        "message": sanitize_diagnostic_text(
                            str(getattr(latest, "message", ""))
                        ),
                        "diagnostic_file": Path(
                            str(
                                getattr(
                                    latest,
                                    "diagnostic_path",
                                    "",
                                )
                                or ""
                            )
                        ).name,
                    }
                    if latest is not None
                    else None
                ),
                "ingestion_status": _value(
                    getattr(job, "ingestion_status", "")
                ),
                "ingestion_error": sanitize_diagnostic_text(
                    str(getattr(job, "ingestion_error", ""))
                ),
            }
        )
    transactions = [
        {
            "status": str(item.get("status") or ""),
            "stage": str(item.get("stage") or ""),
            "message": sanitize_diagnostic_text(
                str(item.get("message") or "")
            ),
        }
        for item in tuple(transaction_results)[-max(0, limit) :]
    ]
    return {
        "queue_schema": getattr(state, "schema_version", None),
        "paused": bool(getattr(state, "paused", True)),
        "job_count": len(jobs),
        "active_count": sum(
            _value(getattr(job, "status", "")) in _ACTIVE_EXPORT_STAGES
            for job in jobs
        ),
        "ffmpeg_version": str(ffmpeg_version or "unknown"),
        "ffprobe_version": str(ffprobe_version or "unknown"),
        "recent_jobs": recent_jobs,
        "recent_transactions": transactions,
    }


def sanitize_diagnostic_text(
    value: str | None,
    *,
    sensitive_paths: tuple[str | Path, ...] = (),
    limit_bytes: int = MAX_DIAGNOSTIC_TEXT_BYTES,
) -> str:
    text = str(value or "")
    for raw_path in sensitive_paths:
        path = str(raw_path)
        if not path:
            continue
        replacement = f"<path:{Path(path).name or 'local'}>"
        text = text.replace(path, replacement)
        text = text.replace(path.replace("\\", "/"), replacement)
    text = _ENV_ASSIGNMENT.sub("<environment:redacted>", text)
    text = _WINDOWS_ABSOLUTE_PATH.sub("<path:redacted>", text)
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit_bytes:
        return text
    suffix = encoded[-limit_bytes:]
    while suffix and (suffix[0] & 0b1100_0000) == 0b1000_0000:
        suffix = suffix[1:]
    return suffix.decode("utf-8", errors="replace")


def _value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "")
