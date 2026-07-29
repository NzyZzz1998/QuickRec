from __future__ import annotations

import os
from pathlib import Path

import pytest

from cli.contracts import CliExitCode, CliFailure
from cli.isolation import CliIsolation


def test_cli_isolation_creates_separate_runtime_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_appdata = tmp_path / "real-appdata"
    monkeypatch.setenv("APPDATA", str(real_appdata))
    workspace = tmp_path / "workspace"
    evidence = tmp_path / "evidence"

    isolation = CliIsolation.prepare(workspace, evidence)
    previous = isolation.activate()
    try:
        assert Path(os.environ["APPDATA"]) == workspace / "appdata"
        assert Path(os.environ["LOCALAPPDATA"]) == workspace / "localappdata"
        assert Path(os.environ["TEMP"]) == workspace / "temp"
        assert isolation.output_dir.is_dir()
        assert isolation.evidence_dir == evidence.resolve()
        assert not (real_appdata / "QuickRec").exists()
    finally:
        isolation.restore(previous)


def test_cli_isolation_rejects_real_quickrec_appdata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_appdata = tmp_path / "real-appdata"
    monkeypatch.setenv("APPDATA", str(real_appdata))

    with pytest.raises(CliFailure) as raised:
        CliIsolation.prepare(real_appdata / "QuickRec", tmp_path / "evidence")

    assert raised.value.exit_code == CliExitCode.ISOLATION_ERROR
    assert raised.value.category == "unsafe_workspace"


def test_cli_isolation_rejects_overlapping_workspace_and_evidence(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    with pytest.raises(CliFailure) as raised:
        CliIsolation.prepare(workspace, workspace / "evidence")

    assert raised.value.exit_code == CliExitCode.ISOLATION_ERROR
    assert raised.value.category == "overlapping_directories"


def test_evidence_reference_never_exposes_absolute_path(tmp_path: Path) -> None:
    isolation = CliIsolation.prepare(
        tmp_path / "workspace",
        tmp_path / "evidence",
    )
    evidence_file = isolation.evidence_dir / "reports" / "doctor.json"
    evidence_file.parent.mkdir(parents=True)
    evidence_file.write_text("{}", encoding="utf-8")

    assert isolation.evidence_reference(evidence_file) == "reports/doctor.json"
