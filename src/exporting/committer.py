"""已验证导出文件的原子提交、显式覆盖事务与启动恢复。"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from exporting.models import (
    ExportFailureKind,
    ExportPlan,
    ExportValidationError,
    OverwriteMode,
    TargetFingerprint,
)
from exporting.verifier import ExportVerificationResult, ExportVerifier
from utils.recording_library_store import normalize_windows_path

TRANSACTION_SCHEMA_VERSION = 1
_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9_.-]+")
OutputVerifier = Callable[[ExportPlan, Path], ExportVerificationResult]
FaultHook = Callable[["CommitPhase"], None]


class CommitInterruption(RuntimeError):
    """仅供故障注入模拟进程在原子步骤之间中断。"""


class CommitPhase(StrEnum):
    PREPARED = "prepared"
    OLD_BACKED_UP = "old_backed_up"
    NEW_COMMITTED = "new_committed"
    VERIFIED = "verified"


class CommitRecoveryStatus(StrEnum):
    FINALIZED_NEW = "finalized_new"
    RESTORED_OLD = "restored_old"
    ROLLED_BACK = "rolled_back"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class OverwriteConfirmation:
    normalized_path: str
    filename: str
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True)
class ExportCommitResult:
    ok: bool
    target_path: Path
    failure_kind: ExportFailureKind | None = None
    message: str = ""
    transaction_path: Path | None = None
    backup_path: Path | None = None


@dataclass(frozen=True)
class CommitRecoveryResult:
    status: CommitRecoveryStatus
    transaction_path: Path
    target_path: Path | None
    message: str = ""


@dataclass(frozen=True)
class CommitTransaction:
    schema_version: int
    transaction_id: str
    phase: CommitPhase
    overwrite_mode: OverwriteMode
    target_path: str
    candidate_path: str
    backup_path: str | None
    old_target_fingerprint: TargetFingerprint | None
    new_target_fingerprint: TargetFingerprint
    plan: ExportPlan

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "transaction_id": self.transaction_id,
            "phase": self.phase.value,
            "overwrite_mode": self.overwrite_mode.value,
            "target_path": self.target_path,
            "candidate_path": self.candidate_path,
            "backup_path": self.backup_path,
            "old_target_fingerprint": (
                self.old_target_fingerprint.to_dict()
                if self.old_target_fingerprint is not None
                else None
            ),
            "new_target_fingerprint": self.new_target_fingerprint.to_dict(),
            "plan": self.plan.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommitTransaction:
        if int(data.get("schema_version", 0)) != TRANSACTION_SCHEMA_VERSION:
            raise ExportValidationError("unsupported commit transaction schema")
        old_data = data.get("old_target_fingerprint")
        if old_data is not None and not isinstance(old_data, dict):
            raise ExportValidationError("invalid old target fingerprint")
        new_data = data.get("new_target_fingerprint")
        plan_data = data.get("plan")
        if not isinstance(new_data, dict) or not isinstance(plan_data, dict):
            raise ExportValidationError("invalid commit transaction payload")
        try:
            phase = CommitPhase(str(data["phase"]))
            overwrite_mode = OverwriteMode(str(data["overwrite_mode"]))
        except (KeyError, ValueError) as exc:
            raise ExportValidationError("invalid commit transaction state") from exc
        return cls(
            schema_version=TRANSACTION_SCHEMA_VERSION,
            transaction_id=_required_text(data, "transaction_id"),
            phase=phase,
            overwrite_mode=overwrite_mode,
            target_path=_required_text(data, "target_path"),
            candidate_path=_required_text(data, "candidate_path"),
            backup_path=_optional_text(data.get("backup_path")),
            old_target_fingerprint=(
                TargetFingerprint.from_dict(old_data)
                if isinstance(old_data, dict)
                else None
            ),
            new_target_fingerprint=TargetFingerprint.from_dict(new_data),
            plan=ExportPlan.from_dict(plan_data),
        )


class ExportCommitter:
    def __init__(
        self,
        *,
        output_verifier: OutputVerifier | None = None,
        fault_hook: FaultHook | None = None,
    ) -> None:
        self._output_verifier = (
            output_verifier or ExportVerifier().verify_output
        )
        self._fault_hook = fault_hook

    def commit(
        self,
        plan: ExportPlan,
        candidate_path: Path,
        *,
        attempt_id: str,
    ) -> ExportCommitResult:
        target = plan.output.target_path
        candidate = Path(candidate_path)
        if not _same_directory(candidate, target):
            return _failed_commit(
                target,
                ExportFailureKind.COMMIT_FAILED,
                "candidate and target must use the same directory",
            )
        try:
            if not candidate.is_file() or candidate.stat().st_size <= 0:
                raise OSError("candidate output is missing or empty")
        except OSError:
            return _failed_commit(
                target,
                ExportFailureKind.COMMIT_FAILED,
                "candidate output is missing or empty",
            )

        candidate_verification = self._output_verifier(plan, candidate)
        if not candidate_verification.ok:
            candidate.unlink(missing_ok=True)
            return _failed_commit(
                target,
                candidate_verification.failure_kind
                or ExportFailureKind.VERIFICATION_FAILED,
                candidate_verification.message or "candidate verification failed",
            )

        if plan.output.overwrite_mode == OverwriteMode.DENY:
            if target.exists():
                return _failed_commit(
                    target,
                    ExportFailureKind.TARGET_CONFLICT,
                    "target already exists; use a safe suffix",
                )
            old_fingerprint = None
            backup = None
        else:
            old_fingerprint = plan.output.target_fingerprint
            if old_fingerprint is None or not _matches_fingerprint(
                target,
                old_fingerprint,
            ):
                return _failed_commit(
                    target,
                    ExportFailureKind.TARGET_CHANGED,
                    "overwrite target changed after confirmation",
                )
            safe_attempt = _safe_token(attempt_id)
            backup = (
                target.parent
                / f".quickrec-export-{safe_attempt}.rollback.mp4"
            )
            if backup.exists():
                return _failed_commit(
                    target,
                    ExportFailureKind.COMMIT_FAILED,
                    "task rollback backup already exists",
                )

        transaction_path = _transaction_path(target.parent, attempt_id)
        if transaction_path.exists():
            return _failed_commit(
                target,
                ExportFailureKind.COMMIT_FAILED,
                "task commit transaction already exists",
                transaction_path=transaction_path,
                backup_path=backup,
            )
        transaction = CommitTransaction(
            schema_version=TRANSACTION_SCHEMA_VERSION,
            transaction_id=_safe_token(attempt_id),
            phase=CommitPhase.PREPARED,
            overwrite_mode=plan.output.overwrite_mode,
            target_path=str(target),
            candidate_path=str(candidate),
            backup_path=str(backup) if backup is not None else None,
            old_target_fingerprint=old_fingerprint,
            new_target_fingerprint=_fingerprint_for_target(candidate, target),
            plan=plan,
        )
        try:
            _write_transaction(transaction_path, transaction)
            self._notify_fault(CommitPhase.PREPARED)
            if transaction.overwrite_mode == OverwriteMode.REPLACE:
                if old_fingerprint is None or not _matches_fingerprint(
                    target,
                    old_fingerprint,
                ):
                    transaction_path.unlink(missing_ok=True)
                    return _failed_commit(
                        target,
                        ExportFailureKind.TARGET_CHANGED,
                        "overwrite target changed before commit",
                    )
                assert backup is not None
                os.replace(target, backup)
                transaction = _advance(
                    transaction_path,
                    transaction,
                    CommitPhase.OLD_BACKED_UP,
                )
                self._notify_fault(CommitPhase.OLD_BACKED_UP)
                os.replace(candidate, target)
            else:
                if target.exists():
                    transaction_path.unlink(missing_ok=True)
                    return _failed_commit(
                        target,
                        ExportFailureKind.TARGET_CONFLICT,
                        "target appeared before commit",
                    )
                os.rename(candidate, target)
            transaction = _advance(
                transaction_path,
                transaction,
                CommitPhase.NEW_COMMITTED,
            )
            self._notify_fault(CommitPhase.NEW_COMMITTED)

            final_verification = self._output_verifier(plan, target)
            if not final_verification.ok:
                restored = _restore_previous_target(transaction, transaction_path)
                return _failed_commit(
                    target,
                    final_verification.failure_kind
                    or ExportFailureKind.VERIFICATION_FAILED,
                    final_verification.message or "final target verification failed",
                    transaction_path=(None if restored else transaction_path),
                    backup_path=(None if restored else backup),
                )
            transaction = _advance(
                transaction_path,
                transaction,
                CommitPhase.VERIFIED,
            )
            self._notify_fault(CommitPhase.VERIFIED)
            if backup is not None:
                backup.unlink(missing_ok=True)
            transaction_path.unlink(missing_ok=True)
            return ExportCommitResult(True, target)
        except CommitInterruption:
            raise
        except OSError as exc:
            restored = _restore_previous_target(transaction, transaction_path)
            return _failed_commit(
                target,
                ExportFailureKind.COMMIT_FAILED,
                f"atomic commit failed: {type(exc).__name__}",
                transaction_path=(None if restored else transaction_path),
                backup_path=(None if restored else backup),
            )

    def _notify_fault(self, phase: CommitPhase) -> None:
        if self._fault_hook is not None:
            self._fault_hook(phase)


def build_overwrite_confirmation(plan: ExportPlan) -> OverwriteConfirmation:
    fingerprint = plan.output.target_fingerprint
    if (
        plan.output.overwrite_mode != OverwriteMode.REPLACE
        or fingerprint is None
    ):
        raise ValueError("plan does not contain explicit overwrite authorization")
    return OverwriteConfirmation(
        normalized_path=fingerprint.normalized_path,
        filename=plan.output.filename,
        size_bytes=fingerprint.size_bytes,
        mtime_ns=fingerprint.mtime_ns,
    )


def suggest_safe_target(target: Path) -> Path:
    stem = target.stem
    suffix = target.suffix or ".mp4"
    index = 1
    while True:
        candidate = target.with_name(f"{stem} ({index}){suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def recover_export_transactions(
    directory: Path,
    *,
    output_verifier: OutputVerifier | None = None,
) -> tuple[CommitRecoveryResult, ...]:
    verifier = output_verifier or ExportVerifier().verify_output
    root = Path(directory)
    results: list[CommitRecoveryResult] = []
    for transaction_path in sorted(
        root.glob(".quickrec-export-*.transaction.json")
    ):
        results.append(
            _recover_transaction(
                root,
                transaction_path,
                verifier,
            )
        )
    return tuple(results)


def _recover_transaction(
    directory: Path,
    transaction_path: Path,
    verifier: OutputVerifier,
) -> CommitRecoveryResult:
    try:
        transaction = _read_transaction(transaction_path)
    except (OSError, ValueError, ExportValidationError, json.JSONDecodeError) as exc:
        return CommitRecoveryResult(
            CommitRecoveryStatus.AMBIGUOUS,
            transaction_path,
            None,
            f"transaction unreadable: {type(exc).__name__}",
        )
    target = Path(transaction.target_path)
    candidate = Path(transaction.candidate_path)
    backup = (
        Path(transaction.backup_path)
        if transaction.backup_path is not None
        else None
    )
    if not _transaction_paths_are_safe(
        directory,
        transaction_path,
        target,
        candidate,
        backup,
    ):
        return _ambiguous(transaction_path, target, "transaction paths are unsafe")

    old_matches = (
        transaction.old_target_fingerprint is not None
        and _matches_fingerprint(target, transaction.old_target_fingerprint)
    )
    backup_matches = (
        backup is not None
        and transaction.old_target_fingerprint is not None
        and _matches_file_identity(
            backup,
            transaction.old_target_fingerprint,
        )
    )
    new_matches = _matches_fingerprint(
        target,
        transaction.new_target_fingerprint,
    )
    candidate_matches = _matches_file_identity(
        candidate,
        transaction.new_target_fingerprint,
    )

    if transaction.phase == CommitPhase.PREPARED:
        if transaction.overwrite_mode == OverwriteMode.DENY:
            if new_matches:
                return _finalize_recovered_new(
                    transaction,
                    transaction_path,
                    target,
                    backup,
                    verifier,
                )
            if target.exists() or not candidate_matches:
                return _ambiguous(
                    transaction_path,
                    target,
                    "default commit state changed unexpectedly",
                )
            candidate_result = verifier(transaction.plan, candidate)
            if not candidate_result.ok:
                return _ambiguous(
                    transaction_path,
                    target,
                    "prepared candidate no longer verifies",
                )
            try:
                os.rename(candidate, target)
                transaction = _advance(
                    transaction_path,
                    transaction,
                    CommitPhase.NEW_COMMITTED,
                )
            except OSError as exc:
                return _ambiguous(
                    transaction_path,
                    target,
                    f"default commit recovery failed: {type(exc).__name__}",
                )
            return _finalize_recovered_new(
                transaction,
                transaction_path,
                target,
                backup,
                verifier,
            )
        if new_matches and backup_matches:
            return _finalize_recovered_new(
                transaction,
                transaction_path,
                target,
                backup,
                verifier,
            )
        if not target.exists() and backup_matches and backup is not None:
            try:
                os.replace(backup, target)
                transaction_path.unlink(missing_ok=True)
            except OSError as exc:
                return _ambiguous(
                    transaction_path,
                    target,
                    f"stale prepared recovery failed: {type(exc).__name__}",
                )
            return CommitRecoveryResult(
                CommitRecoveryStatus.RESTORED_OLD,
                transaction_path,
                target,
                "old target restored from a stale prepared transaction",
            )
        if old_matches and candidate_matches and (backup is None or not backup.exists()):
            transaction_path.unlink(missing_ok=True)
            return CommitRecoveryResult(
                CommitRecoveryStatus.RESTORED_OLD,
                transaction_path,
                target,
                "overwrite had not changed the old target",
            )

    if transaction.phase in {
        CommitPhase.OLD_BACKED_UP,
        CommitPhase.NEW_COMMITTED,
        CommitPhase.VERIFIED,
    }:
        if (
            transaction.phase == CommitPhase.VERIFIED
            and new_matches
            and (backup is None or not backup.exists())
        ):
            return _finalize_recovered_new(
                transaction,
                transaction_path,
                target,
                backup,
                verifier,
            )
        if new_matches and (
            transaction.overwrite_mode == OverwriteMode.DENY or backup_matches
        ):
            return _finalize_recovered_new(
                transaction,
                transaction_path,
                target,
                backup,
                verifier,
            )
        if not target.exists() and backup_matches and backup is not None:
            try:
                os.replace(backup, target)
                transaction_path.unlink(missing_ok=True)
            except OSError as exc:
                return _ambiguous(
                    transaction_path,
                    target,
                    f"old target recovery failed: {type(exc).__name__}",
                )
            return CommitRecoveryResult(
                CommitRecoveryStatus.RESTORED_OLD,
                transaction_path,
                target,
                "old target restored from rollback backup",
            )
        if old_matches and (backup is None or not backup.exists()):
            transaction_path.unlink(missing_ok=True)
            return CommitRecoveryResult(
                CommitRecoveryStatus.RESTORED_OLD,
                transaction_path,
                target,
                "old target already restored",
            )
    return _ambiguous(
        transaction_path,
        target,
        "commit state cannot be resolved without risking user data",
    )


def _finalize_recovered_new(
    transaction: CommitTransaction,
    transaction_path: Path,
    target: Path,
    backup: Path | None,
    verifier: OutputVerifier,
) -> CommitRecoveryResult:
    verification = verifier(transaction.plan, target)
    if verification.ok:
        try:
            if backup is not None:
                backup.unlink(missing_ok=True)
            transaction_path.unlink(missing_ok=True)
        except OSError as exc:
            return _ambiguous(
                transaction_path,
                target,
                f"recovery cleanup failed: {type(exc).__name__}",
            )
        return CommitRecoveryResult(
            CommitRecoveryStatus.FINALIZED_NEW,
            transaction_path,
            target,
            "new target verified and finalized",
        )
    if backup is not None and backup.exists():
        if _restore_previous_target(transaction, transaction_path):
            return CommitRecoveryResult(
                CommitRecoveryStatus.RESTORED_OLD,
                transaction_path,
                target,
                "new target verification failed; old target restored",
            )
    return _ambiguous(
        transaction_path,
        target,
        "new target verification failed and automatic rollback was unsafe",
    )


def _restore_previous_target(
    transaction: CommitTransaction,
    transaction_path: Path,
) -> bool:
    target = Path(transaction.target_path)
    candidate = Path(transaction.candidate_path)
    backup = (
        Path(transaction.backup_path)
        if transaction.backup_path is not None
        else None
    )
    try:
        if transaction.overwrite_mode == OverwriteMode.REPLACE:
            if backup is None or not backup.exists():
                return False
            if target.exists():
                if candidate.exists():
                    return False
                os.replace(target, candidate)
            os.replace(backup, target)
        else:
            if target.exists():
                if candidate.exists():
                    return False
                os.replace(target, candidate)
        transaction_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _advance(
    transaction_path: Path,
    transaction: CommitTransaction,
    phase: CommitPhase,
) -> CommitTransaction:
    updated = replace(transaction, phase=phase)
    _write_transaction(transaction_path, updated)
    return updated


def _write_transaction(
    transaction_path: Path,
    transaction: CommitTransaction,
) -> None:
    temporary = transaction_path.with_suffix(
        transaction_path.suffix + ".tmp"
    )
    payload = json.dumps(
        transaction.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, transaction_path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_transaction(transaction_path: Path) -> CommitTransaction:
    data = json.loads(transaction_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ExportValidationError("commit transaction root must be an object")
    return CommitTransaction.from_dict(data)


def _transaction_path(directory: Path, attempt_id: str) -> Path:
    return (
        directory
        / f".quickrec-export-{_safe_token(attempt_id)}.transaction.json"
    )


def _safe_token(value: str) -> str:
    normalized = _SAFE_TOKEN.sub("-", str(value).strip()).strip("-.")
    return normalized or "attempt"


def _fingerprint_for_target(
    candidate: Path,
    target: Path,
) -> TargetFingerprint:
    stat = candidate.stat()
    return TargetFingerprint(
        normalize_windows_path(target),
        stat.st_size,
        stat.st_mtime_ns,
    )


def _matches_fingerprint(path: Path, fingerprint: TargetFingerprint) -> bool:
    if normalize_windows_path(path) != fingerprint.normalized_path:
        return False
    return _matches_file_identity(path, fingerprint)


def _matches_file_identity(
    path: Path,
    fingerprint: TargetFingerprint,
) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    return (
        path.is_file()
        and stat.st_size == fingerprint.size_bytes
        and stat.st_mtime_ns == fingerprint.mtime_ns
    )


def _same_directory(left: Path, right: Path) -> bool:
    try:
        return left.parent.resolve() == right.parent.resolve()
    except OSError:
        return normalize_windows_path(left.parent) == normalize_windows_path(
            right.parent
        )


def _transaction_paths_are_safe(
    directory: Path,
    transaction_path: Path,
    target: Path,
    candidate: Path,
    backup: Path | None,
) -> bool:
    expected = directory.resolve()
    paths = [transaction_path, target, candidate]
    if backup is not None:
        paths.append(backup)
    try:
        return all(path.parent.resolve() == expected for path in paths)
    except OSError:
        return False


def _failed_commit(
    target: Path,
    failure_kind: ExportFailureKind,
    message: str,
    *,
    transaction_path: Path | None = None,
    backup_path: Path | None = None,
) -> ExportCommitResult:
    return ExportCommitResult(
        False,
        target,
        failure_kind=failure_kind,
        message=message,
        transaction_path=transaction_path,
        backup_path=backup_path,
    )


def _ambiguous(
    transaction_path: Path,
    target_path: Path,
    message: str,
) -> CommitRecoveryResult:
    return CommitRecoveryResult(
        CommitRecoveryStatus.AMBIGUOUS,
        transaction_path,
        target_path,
        message,
    )


def _required_text(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ExportValidationError(f"{key} is required")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
