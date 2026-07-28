from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CoverageGroup:
    name: str
    files: tuple[str, ...]
    minimum_percent: float


GROUPS = (
    CoverageGroup(
        "timeline-core",
        (
            "src/utils/timeline_model.py",
            "src/services/timeline_commands.py",
            "src/services/timeline_session.py",
        ),
        85.0,
    ),
    CoverageGroup(
        "timeline-playback-coordination",
        (
            "src/ui/timeline_editor_window.py",
            "src/services/playback_runtime.py",
        ),
        80.0,
    ),
)


def _normalized_files(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = report.get("files")
    if not isinstance(files, dict):
        raise ValueError("coverage report has no files mapping")
    return {
        str(path).replace("\\", "/"): details
        for path, details in files.items()
        if isinstance(details, dict)
    }


def group_statement_coverage(
    report: dict[str, Any],
    group: CoverageGroup,
) -> float:
    files = _normalized_files(report)
    covered = 0
    statements = 0
    for path in group.files:
        details = files.get(path)
        if details is None:
            raise ValueError(f"coverage report is missing {path}")
        summary = details.get("summary")
        if not isinstance(summary, dict):
            raise ValueError(f"coverage summary is missing for {path}")
        covered += int(summary.get("covered_lines", 0))
        statements += int(summary.get("num_statements", 0))
    if statements <= 0:
        raise ValueError(f"coverage group {group.name} has no statements")
    return covered * 100.0 / statements


def check_report(
    report: dict[str, Any],
    groups: tuple[CoverageGroup, ...] = GROUPS,
) -> list[str]:
    failures: list[str] = []
    for group in groups:
        percent = group_statement_coverage(report, group)
        print(
            f"{group.name}: {percent:.2f}% "
            f"(required {group.minimum_percent:.2f}%)"
        )
        if percent + 1e-9 < group.minimum_percent:
            failures.append(
                f"{group.name} statement coverage {percent:.2f}% is below "
                f"{group.minimum_percent:.2f}%"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check v1.9.2 incremental statement coverage gates."
    )
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    failures = check_report(report)
    for failure in failures:
        print(f"ERROR: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
