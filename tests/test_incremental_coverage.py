from __future__ import annotations

import pytest
from scripts.check_incremental_coverage import (
    CoverageGroup,
    check_report,
    group_statement_coverage,
)


def _report(*, first_covered: int, second_covered: int) -> dict:
    return {
        "files": {
            "src\\first.py": {
                "summary": {
                    "covered_lines": first_covered,
                    "num_statements": 10,
                }
            },
            "src/second.py": {
                "summary": {
                    "covered_lines": second_covered,
                    "num_statements": 10,
                }
            },
        }
    }


def test_group_statement_coverage_normalizes_windows_paths():
    group = CoverageGroup(
        "sample",
        ("src/first.py", "src/second.py"),
        80.0,
    )

    assert group_statement_coverage(
        _report(first_covered=8, second_covered=9),
        group,
    ) == 85.0


def test_check_report_rejects_group_below_threshold():
    group = CoverageGroup(
        "sample",
        ("src/first.py", "src/second.py"),
        80.0,
    )

    failures = check_report(
        _report(first_covered=7, second_covered=8),
        (group,),
    )

    assert len(failures) == 1
    assert "75.00%" in failures[0]


def test_group_statement_coverage_rejects_missing_file():
    group = CoverageGroup(
        "sample",
        ("src/missing.py",),
        80.0,
    )

    with pytest.raises(ValueError, match="missing"):
        group_statement_coverage(
            _report(first_covered=10, second_covered=10),
            group,
        )
