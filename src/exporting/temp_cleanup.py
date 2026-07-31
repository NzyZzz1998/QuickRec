"""Safe cleanup for export artifacts owned by a queue attempt."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportTempArtifactOwner:
    job_id: str
    attempt_id: str
    output_directory: Path


@dataclass(frozen=True)
class ExportTempCleanupReport:
    job_id: str
    attempt_id: str
    removed: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    failed: tuple[tuple[str, str], ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failed


def cleanup_export_attempt(
    owner: ExportTempArtifactOwner,
    *,
    active_attempt_ids: frozenset[str] = frozenset(),
) -> ExportTempCleanupReport:
    safe_attempt = safe_attempt_token(owner.attempt_id)
    if owner.attempt_id in active_attempt_ids:
        report = ExportTempCleanupReport(
            owner.job_id,
            owner.attempt_id,
            skipped=("active_attempt",),
        )
        _log_report(report)
        return report

    transaction = (
        owner.output_directory
        / f".quickrec-export-{safe_attempt}.transaction.json"
    )
    if transaction.exists() or transaction.is_symlink():
        report = ExportTempCleanupReport(
            owner.job_id,
            owner.attempt_id,
            skipped=("commit_transaction_present",),
        )
        _log_report(report)
        return report

    removed: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    for path in _owned_attempt_paths(owner.output_directory, safe_attempt):
        if not path.exists() and not path.is_symlink():
            continue
        if not path.is_file() and not path.is_symlink():
            skipped.append(f"unexpected_type:{path.name}")
            continue
        try:
            path.unlink()
            removed.append(path.name)
        except OSError as exc:
            failed.append((path.name, type(exc).__name__))

    report = ExportTempCleanupReport(
        owner.job_id,
        owner.attempt_id,
        tuple(removed),
        tuple(skipped),
        tuple(failed),
    )
    _log_report(report)
    return report


def safe_attempt_token(value: str) -> str:
    safe = "".join(
        character
        for character in str(value)
        if character.isalnum() or character in {"-", "_"}
    )
    return safe or "attempt"


def _owned_attempt_paths(
    output_directory: Path,
    safe_attempt: str,
) -> tuple[Path, Path]:
    return (
        output_directory / f".quickrec-export-{safe_attempt}.part.mp4",
        output_directory / f".quickrec-export-{safe_attempt}.filter.txt",
    )


def _log_report(report: ExportTempCleanupReport) -> None:
    log = logger.warning if report.failed else logger.info
    log(
        "export temp cleanup: job=%s attempt=%s removed=%s skipped=%s failed=%s",
        report.job_id,
        report.attempt_id,
        len(report.removed),
        ",".join(report.skipped) or "none",
        ",".join(kind for _, kind in report.failed) or "none",
    )
