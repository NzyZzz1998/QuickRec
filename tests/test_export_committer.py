from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from exporting.committer import (
    CommitInterruption,
    CommitPhase,
    CommitRecoveryStatus,
    ExportCommitter,
    build_overwrite_confirmation,
    recover_export_transactions,
    suggest_safe_target,
)
from exporting.models import (
    ExportClip,
    ExportFailureKind,
    ExportMaterialSnapshot,
    ExportOutputSpec,
    ExportPlan,
    ExportProjectSnapshot,
    ExportTimelineSnapshot,
    ExportTrack,
    OverwriteMode,
    RenderPolicy,
    TargetFingerprint,
)
from exporting.verifier import ExportVerificationResult
from utils.recording_library_store import normalize_windows_path


def _plan(
    tmp_path: Path,
    *,
    overwrite_mode: OverwriteMode = OverwriteMode.DENY,
    target_fingerprint: TargetFingerprint | None = None,
) -> ExportPlan:
    source = tmp_path / "素材.mp4"
    source.write_bytes(b"source")
    source_stat = source.stat()
    return ExportPlan.create(
        plan_id="plan-commit",
        created_at="2026-07-29T12:00:00+00:00",
        project=ExportProjectSnapshot(
            "project-1",
            "提交项目",
            str(tmp_path / "project.qrproj"),
            1,
            2,
        ),
        timeline=ExportTimelineSnapshot(
            "timeline-1",
            2_000_000,
            (ExportTrack("video-1", "video", 0),),
            (
                ExportClip(
                    "clip-1",
                    "material-1",
                    "video-1",
                    None,
                    0,
                    2_000_000,
                    0,
                    2_000_000,
                ),
            ),
        ),
        materials=(
            ExportMaterialSnapshot(
                "material-1",
                str(source),
                normalize_windows_path(source),
                source_stat.st_size,
                source_stat.st_mtime_ns,
                "mov,mp4,m4a,3gp,3g2,mj2",
                "h264",
                320,
                180,
                30.0,
                2_000_000,
                None,
                None,
                None,
                None,
            ),
        ),
        render_policy=RenderPolicy(),
        output=ExportOutputSpec(
            320,
            180,
            30,
            str(tmp_path / "输出 目录"),
            "结果.mp4",
            overwrite_mode=overwrite_mode,
            target_fingerprint=target_fingerprint,
        ),
    )


def _target_fingerprint(path: Path) -> TargetFingerprint:
    stat = path.stat()
    return TargetFingerprint(
        normalize_windows_path(path),
        stat.st_size,
        stat.st_mtime_ns,
    )


def _verified(_plan: ExportPlan, path: Path) -> ExportVerificationResult:
    return ExportVerificationResult(path.is_file() and path.read_bytes() == b"new")


def _candidate(plan: ExportPlan, name: str = "attempt-1") -> Path:
    directory = Path(plan.output.directory)
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f".quickrec-export-{name}.part.mp4"
    candidate.write_bytes(b"new")
    return candidate


def _transactions(directory: Path) -> list[Path]:
    return list(directory.glob(".quickrec-export-*.transaction.json"))


def _backups(directory: Path) -> list[Path]:
    return list(directory.glob(".quickrec-export-*.rollback.mp4"))


def test_default_commit_atomically_promotes_verified_candidate(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    candidate = _candidate(plan)

    result = ExportCommitter(output_verifier=_verified).commit(
        plan,
        candidate,
        attempt_id="attempt-1",
    )

    assert result.ok
    assert result.target_path == plan.output.target_path
    assert plan.output.target_path.read_bytes() == b"new"
    assert not candidate.exists()
    assert not _transactions(plan.output.target_path.parent)
    assert not _backups(plan.output.target_path.parent)


def test_default_commit_never_overwrites_target_and_preserves_candidate(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    target = plan.output.target_path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    candidate = _candidate(plan)

    result = ExportCommitter(output_verifier=_verified).commit(
        plan,
        candidate,
        attempt_id="attempt-conflict",
    )

    assert not result.ok
    assert result.failure_kind == ExportFailureKind.TARGET_CONFLICT
    assert target.read_bytes() == b"old"
    assert candidate.read_bytes() == b"new"
    assert not _transactions(target.parent)


def test_safe_suffix_is_deterministic(tmp_path: Path) -> None:
    target = tmp_path / "导出.mp4"
    target.write_bytes(b"0")
    (tmp_path / "导出 (1).mp4").write_bytes(b"1")

    assert suggest_safe_target(target) == tmp_path / "导出 (2).mp4"


def test_commit_rejects_candidate_outside_target_directory(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    candidate = tmp_path / "other" / "candidate.mp4"
    candidate.parent.mkdir()
    candidate.write_bytes(b"new")

    result = ExportCommitter(output_verifier=_verified).commit(
        plan,
        candidate,
        attempt_id="attempt-cross-volume",
    )

    assert not result.ok
    assert result.failure_kind == ExportFailureKind.COMMIT_FAILED
    assert candidate.exists()
    assert not plan.output.target_path.exists()


def test_invalid_candidate_never_enters_commit(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    candidate = _candidate(plan)
    target = plan.output.target_path
    def verifier(_plan: ExportPlan, _path: Path) -> ExportVerificationResult:
        return ExportVerificationResult(False, message="bad")

    result = ExportCommitter(output_verifier=verifier).commit(
        plan,
        candidate,
        attempt_id="attempt-invalid",
    )

    assert not result.ok
    assert result.failure_kind == ExportFailureKind.VERIFICATION_FAILED
    assert not target.exists()
    assert not candidate.exists()
    assert not _transactions(target.parent)


def test_overwrite_confirmation_describes_frozen_target(tmp_path: Path) -> None:
    target = tmp_path / "输出 目录" / "结果.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    fingerprint = _target_fingerprint(target)
    plan = _plan(
        tmp_path,
        overwrite_mode=OverwriteMode.REPLACE,
        target_fingerprint=fingerprint,
    )

    confirmation = build_overwrite_confirmation(plan)

    assert confirmation.filename == target.name
    assert confirmation.size_bytes == len(b"old")
    assert confirmation.mtime_ns == fingerprint.mtime_ns
    assert confirmation.normalized_path == fingerprint.normalized_path


def test_explicit_overwrite_rejects_changed_target(tmp_path: Path) -> None:
    target = tmp_path / "输出 目录" / "结果.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    plan = _plan(
        tmp_path,
        overwrite_mode=OverwriteMode.REPLACE,
        target_fingerprint=_target_fingerprint(target),
    )
    candidate = _candidate(plan)
    target.write_bytes(b"third-party")

    result = ExportCommitter(output_verifier=_verified).commit(
        plan,
        candidate,
        attempt_id="attempt-changed",
    )

    assert not result.ok
    assert result.failure_kind == ExportFailureKind.TARGET_CHANGED
    assert target.read_bytes() == b"third-party"
    assert candidate.read_bytes() == b"new"
    assert not _transactions(target.parent)


def test_explicit_overwrite_success_leaves_only_new_target(tmp_path: Path) -> None:
    target = tmp_path / "输出 目录" / "结果.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    plan = _plan(
        tmp_path,
        overwrite_mode=OverwriteMode.REPLACE,
        target_fingerprint=_target_fingerprint(target),
    )
    candidate = _candidate(plan)

    result = ExportCommitter(output_verifier=_verified).commit(
        plan,
        candidate,
        attempt_id="attempt-replace",
    )

    assert result.ok
    assert target.read_bytes() == b"new"
    assert not candidate.exists()
    assert not _transactions(target.parent)
    assert not _backups(target.parent)


def test_final_verification_failure_restores_old_target(tmp_path: Path) -> None:
    target = tmp_path / "输出 目录" / "结果.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    plan = _plan(
        tmp_path,
        overwrite_mode=OverwriteMode.REPLACE,
        target_fingerprint=_target_fingerprint(target),
    )
    candidate = _candidate(plan)
    calls = 0

    def verifier(_plan: ExportPlan, _path: Path) -> ExportVerificationResult:
        nonlocal calls
        calls += 1
        return ExportVerificationResult(calls == 1, message="final invalid")

    result = ExportCommitter(output_verifier=verifier).commit(
        plan,
        candidate,
        attempt_id="attempt-final-invalid",
    )

    assert not result.ok
    assert result.failure_kind == ExportFailureKind.VERIFICATION_FAILED
    assert target.read_bytes() == b"old"
    assert candidate.read_bytes() == b"new"
    assert not _backups(target.parent)
    assert not _transactions(target.parent)


def test_recovery_restores_old_target_after_backup_phase(tmp_path: Path) -> None:
    target = tmp_path / "输出 目录" / "结果.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    plan = _plan(
        tmp_path,
        overwrite_mode=OverwriteMode.REPLACE,
        target_fingerprint=_target_fingerprint(target),
    )
    candidate = _candidate(plan)

    def interrupt(phase: CommitPhase) -> None:
        if phase == CommitPhase.OLD_BACKED_UP:
            raise CommitInterruption("simulated crash")

    with pytest.raises(CommitInterruption):
        ExportCommitter(
            output_verifier=_verified,
            fault_hook=interrupt,
        ).commit(plan, candidate, attempt_id="attempt-crash-backup")

    assert not target.exists()
    assert _backups(target.parent)
    recovery = recover_export_transactions(
        target.parent,
        output_verifier=_verified,
    )

    assert recovery[0].status == CommitRecoveryStatus.RESTORED_OLD
    assert target.read_bytes() == b"old"
    assert candidate.read_bytes() == b"new"
    assert not _backups(target.parent)
    assert not _transactions(target.parent)


def test_recovery_finalizes_new_target_after_commit_phase(tmp_path: Path) -> None:
    target = tmp_path / "输出 目录" / "结果.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    plan = _plan(
        tmp_path,
        overwrite_mode=OverwriteMode.REPLACE,
        target_fingerprint=_target_fingerprint(target),
    )
    candidate = _candidate(plan)

    def interrupt(phase: CommitPhase) -> None:
        if phase == CommitPhase.NEW_COMMITTED:
            raise CommitInterruption("simulated crash")

    with pytest.raises(CommitInterruption):
        ExportCommitter(
            output_verifier=_verified,
            fault_hook=interrupt,
        ).commit(plan, candidate, attempt_id="attempt-crash-new")

    recovery = recover_export_transactions(
        target.parent,
        output_verifier=_verified,
    )

    assert recovery[0].status == CommitRecoveryStatus.FINALIZED_NEW
    assert target.read_bytes() == b"new"
    assert not candidate.exists()
    assert not _backups(target.parent)
    assert not _transactions(target.parent)


def test_recovery_finishes_default_commit_after_prepared_phase(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    candidate = _candidate(plan)

    def interrupt(phase: CommitPhase) -> None:
        if phase == CommitPhase.PREPARED:
            raise CommitInterruption("simulated crash")

    with pytest.raises(CommitInterruption):
        ExportCommitter(
            output_verifier=_verified,
            fault_hook=interrupt,
        ).commit(plan, candidate, attempt_id="attempt-default-prepared")

    recovery = recover_export_transactions(
        plan.output.target_path.parent,
        output_verifier=_verified,
    )

    assert recovery[0].status == CommitRecoveryStatus.FINALIZED_NEW
    assert plan.output.target_path.read_bytes() == b"new"
    assert not candidate.exists()
    assert not _transactions(plan.output.target_path.parent)


def test_recovery_preserves_everything_when_target_changed_by_third_party(
    tmp_path: Path,
) -> None:
    target = tmp_path / "输出 目录" / "结果.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    plan = _plan(
        tmp_path,
        overwrite_mode=OverwriteMode.REPLACE,
        target_fingerprint=_target_fingerprint(target),
    )
    candidate = _candidate(plan)

    def interrupt(phase: CommitPhase) -> None:
        if phase == CommitPhase.NEW_COMMITTED:
            raise CommitInterruption("simulated crash")

    with pytest.raises(CommitInterruption):
        ExportCommitter(
            output_verifier=_verified,
            fault_hook=interrupt,
        ).commit(plan, candidate, attempt_id="attempt-ambiguous")

    target.write_bytes(b"third-party")
    recovery = recover_export_transactions(
        target.parent,
        output_verifier=_verified,
    )

    assert recovery[0].status == CommitRecoveryStatus.AMBIGUOUS
    assert target.read_bytes() == b"third-party"
    assert _backups(target.parent)[0].read_bytes() == b"old"
    assert _transactions(target.parent)


def test_recovery_handles_backup_move_before_phase_record_is_updated(
    tmp_path: Path,
) -> None:
    target = tmp_path / "输出 目录" / "结果.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    plan = _plan(
        tmp_path,
        overwrite_mode=OverwriteMode.REPLACE,
        target_fingerprint=_target_fingerprint(target),
    )
    candidate = _candidate(plan)

    def interrupt(phase: CommitPhase) -> None:
        if phase == CommitPhase.OLD_BACKED_UP:
            raise CommitInterruption("simulated crash")

    with pytest.raises(CommitInterruption):
        ExportCommitter(
            output_verifier=_verified,
            fault_hook=interrupt,
        ).commit(plan, candidate, attempt_id="attempt-stale-prepared")

    transaction_path = _transactions(target.parent)[0]
    payload = json.loads(transaction_path.read_text(encoding="utf-8"))
    payload["phase"] = CommitPhase.PREPARED.value
    transaction_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    recovery = recover_export_transactions(
        target.parent,
        output_verifier=_verified,
    )

    assert recovery[0].status == CommitRecoveryStatus.RESTORED_OLD
    assert target.read_bytes() == b"old"
    assert candidate.read_bytes() == b"new"
    assert not _backups(target.parent)
    assert not _transactions(target.parent)


def test_recovery_finalizes_verified_target_after_backup_was_deleted(
    tmp_path: Path,
) -> None:
    target = tmp_path / "输出 目录" / "结果.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    plan = _plan(
        tmp_path,
        overwrite_mode=OverwriteMode.REPLACE,
        target_fingerprint=_target_fingerprint(target),
    )
    candidate = _candidate(plan)

    def interrupt(phase: CommitPhase) -> None:
        if phase == CommitPhase.VERIFIED:
            raise CommitInterruption("simulated crash")

    with pytest.raises(CommitInterruption):
        ExportCommitter(
            output_verifier=_verified,
            fault_hook=interrupt,
        ).commit(plan, candidate, attempt_id="attempt-verified")

    _backups(target.parent)[0].unlink()
    recovery = recover_export_transactions(
        target.parent,
        output_verifier=_verified,
    )

    assert recovery[0].status == CommitRecoveryStatus.FINALIZED_NEW
    assert target.read_bytes() == b"new"
    assert not _transactions(target.parent)


def test_missing_candidate_does_not_change_existing_target(tmp_path: Path) -> None:
    target = tmp_path / "输出 目录" / "结果.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    plan = _plan(
        tmp_path,
        overwrite_mode=OverwriteMode.REPLACE,
        target_fingerprint=_target_fingerprint(target),
    )

    result = ExportCommitter(output_verifier=_verified).commit(
        plan,
        target.parent / "missing.part.mp4",
        attempt_id="attempt-missing",
    )

    assert not result.ok
    assert result.failure_kind == ExportFailureKind.COMMIT_FAILED
    assert target.read_bytes() == b"old"
    assert not _transactions(target.parent)


def test_commit_plan_remains_immutable_when_safe_target_is_selected(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    target = plan.output.target_path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"existing")
    safe_target = suggest_safe_target(target)

    safe_output = replace(
        plan.output,
        filename=safe_target.name,
    )

    assert safe_output.target_path == target.parent / "结果 (1).mp4"
    assert plan.output.target_path == target
