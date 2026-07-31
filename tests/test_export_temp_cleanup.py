from __future__ import annotations

from pathlib import Path

from exporting.temp_cleanup import (
    ExportTempArtifactOwner,
    cleanup_export_attempt,
)


def _owner(tmp_path: Path, attempt_id: str = "attempt-1"):
    return ExportTempArtifactOwner(
        job_id="job-1",
        attempt_id=attempt_id,
        output_directory=tmp_path,
    )


def test_cleanup_removes_only_exact_owned_attempt_artifacts(
    tmp_path: Path,
) -> None:
    owned_part = tmp_path / ".quickrec-export-attempt-1.part.mp4"
    owned_graph = tmp_path / ".quickrec-export-attempt-1.filter.txt"
    another_attempt = tmp_path / ".quickrec-export-attempt-2.part.mp4"
    user_file = tmp_path / "用户自建.part.mp4"
    similar_file = tmp_path / ".quickrec-export-attempt-1.notes.txt"
    owned_part.write_bytes(b"partial")
    owned_graph.write_text("graph", encoding="utf-8")
    another_attempt.write_bytes(b"other")
    user_file.write_bytes(b"user")
    similar_file.write_text("keep", encoding="utf-8")

    report = cleanup_export_attempt(_owner(tmp_path))

    assert report.ok
    assert set(report.removed) == {
        ".quickrec-export-attempt-1.part.mp4",
        ".quickrec-export-attempt-1.filter.txt",
    }
    assert not owned_part.exists()
    assert not owned_graph.exists()
    assert another_attempt.exists()
    assert user_file.exists()
    assert similar_file.exists()


def test_cleanup_protects_active_attempt(tmp_path: Path) -> None:
    part = tmp_path / ".quickrec-export-attempt-active.part.mp4"
    part.write_bytes(b"active")

    report = cleanup_export_attempt(
        _owner(tmp_path, "attempt-active"),
        active_attempt_ids=frozenset({"attempt-active"}),
    )

    assert report.ok
    assert report.removed == ()
    assert report.skipped == ("active_attempt",)
    assert part.exists()


def test_cleanup_protects_attempt_with_commit_transaction(
    tmp_path: Path,
) -> None:
    part = tmp_path / ".quickrec-export-attempt-commit.part.mp4"
    transaction = (
        tmp_path / ".quickrec-export-attempt-commit.transaction.json"
    )
    part.write_bytes(b"candidate")
    transaction.write_text("{}", encoding="utf-8")

    report = cleanup_export_attempt(_owner(tmp_path, "attempt-commit"))

    assert report.ok
    assert report.removed == ()
    assert report.skipped == ("commit_transaction_present",)
    assert part.exists()
    assert transaction.exists()


def test_cleanup_failure_is_reported_without_deleting_other_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    part = tmp_path / ".quickrec-export-attempt-1.part.mp4"
    graph = tmp_path / ".quickrec-export-attempt-1.filter.txt"
    unrelated = tmp_path / "keep.txt"
    part.write_bytes(b"partial")
    graph.write_text("graph", encoding="utf-8")
    unrelated.write_text("keep", encoding="utf-8")
    original_unlink = Path.unlink

    def fail_part(path: Path, *args, **kwargs):
        if path == part:
            raise PermissionError("locked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_part)

    report = cleanup_export_attempt(_owner(tmp_path))

    assert not report.ok
    assert report.removed == (graph.name,)
    assert report.failed == ((part.name, "PermissionError"),)
    assert part.exists()
    assert unrelated.exists()
