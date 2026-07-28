from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "playback_backend_spike.py"
)
SPEC = importlib.util.spec_from_file_location("playback_backend_spike", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
spike = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = spike
SPEC.loader.exec_module(spike)


def test_backend_report_requires_all_checks_and_no_errors() -> None:
    report = spike.BackendReport(backend="candidate", available=True)
    report.add_check("startup", True)
    report.add_check("seek", True)
    assert report.passed is True

    report.add_check("mix", False)
    assert report.passed is False


def test_backend_report_error_blocks_pass() -> None:
    report = spike.BackendReport(backend="candidate", available=True)
    report.add_check("startup", True)
    report.errors.append("backend failed")
    assert report.passed is False


def test_build_inputs_requires_exactly_four_audio_samples(
    tmp_path: Path,
) -> None:
    args = type(
        "Args",
        (),
        {
            "sample": str(tmp_path / "sample.mp4"),
            "silent": str(tmp_path / "silent.mp4"),
            "long_sample": str(tmp_path / "long.mp4"),
            "corrupt": str(tmp_path / "corrupt.mp4"),
            "missing": str(tmp_path / "missing.mp4"),
            "audio_sample": [str(tmp_path / "a.mp4")],
            "libmpv_dir": None,
        },
    )()

    with pytest.raises(ValueError, match="exactly four"):
        spike._build_inputs(args)


def test_validate_inputs_rejects_existing_missing_fixture(
    tmp_path: Path,
) -> None:
    required = [
        tmp_path / "sample.mp4",
        tmp_path / "silent.mp4",
        tmp_path / "long.mp4",
        tmp_path / "corrupt.mp4",
        *(tmp_path / f"audio-{index}.mp4" for index in range(4)),
    ]
    for path in required:
        path.write_bytes(b"fixture")
    missing_path = tmp_path / "should-not-exist.mp4"
    missing_path.write_bytes(b"unexpected")
    inputs = spike.SpikeInputs(
        sample=required[0],
        silent=required[1],
        long_sample=required[2],
        corrupt=required[3],
        missing=missing_path,
        audio_samples=tuple(required[4:]),
        libmpv_dir=None,
    )

    with pytest.raises(ValueError, match="unexpectedly exists"):
        spike._validate_inputs(inputs)
