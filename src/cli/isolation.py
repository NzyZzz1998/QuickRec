from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from cli.contracts import CliExitCode, CliFailure

_ISOLATED_ENV_KEYS = ("APPDATA", "LOCALAPPDATA", "TEMP", "TMP")


@dataclass(frozen=True)
class EnvironmentSnapshot:
    values: dict[str, str | None]
    tempfile_dir: str | None


@dataclass(frozen=True)
class CliIsolation:
    workspace: Path
    evidence_dir: Path
    appdata_dir: Path
    local_appdata_dir: Path
    temp_dir: Path
    output_dir: Path

    @classmethod
    def prepare(
        cls,
        workspace: str | Path,
        evidence_dir: str | Path,
    ) -> CliIsolation:
        workspace_path = _resolved(workspace)
        evidence_path = _resolved(evidence_dir)
        real_appdata = _resolved(os.getenv("APPDATA") or Path.home())
        real_quickrec = real_appdata / "QuickRec"

        if _paths_overlap(workspace_path, evidence_path):
            raise CliFailure(
                CliExitCode.ISOLATION_ERROR,
                "overlapping_directories",
                "工作区与证据目录必须彼此独立",
            )
        if _paths_overlap(workspace_path, real_quickrec):
            raise CliFailure(
                CliExitCode.ISOLATION_ERROR,
                "unsafe_workspace",
                "工作区不得指向真实 QuickRec 用户数据目录",
            )
        if _paths_overlap(evidence_path, real_quickrec):
            raise CliFailure(
                CliExitCode.ISOLATION_ERROR,
                "unsafe_evidence_directory",
                "证据目录不得指向真实 QuickRec 用户数据目录",
            )

        try:
            appdata_dir = workspace_path / "appdata"
            local_appdata_dir = workspace_path / "localappdata"
            temp_dir = workspace_path / "temp"
            output_dir = workspace_path / "output"
            for path in (
                workspace_path,
                evidence_path,
                appdata_dir,
                local_appdata_dir,
                temp_dir,
                output_dir,
            ):
                path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CliFailure(
                CliExitCode.ISOLATION_ERROR,
                "directory_prepare_failed",
                "无法创建隔离目录",
                context={"error_type": type(exc).__name__},
            ) from exc

        return cls(
            workspace=workspace_path,
            evidence_dir=evidence_path,
            appdata_dir=appdata_dir,
            local_appdata_dir=local_appdata_dir,
            temp_dir=temp_dir,
            output_dir=output_dir,
        )

    def activate(self) -> EnvironmentSnapshot:
        snapshot = EnvironmentSnapshot(
            values={key: os.environ.get(key) for key in _ISOLATED_ENV_KEYS},
            tempfile_dir=tempfile.tempdir,
        )
        os.environ["APPDATA"] = str(self.appdata_dir)
        os.environ["LOCALAPPDATA"] = str(self.local_appdata_dir)
        os.environ["TEMP"] = str(self.temp_dir)
        os.environ["TMP"] = str(self.temp_dir)
        tempfile.tempdir = str(self.temp_dir)
        return snapshot

    @staticmethod
    def restore(snapshot: EnvironmentSnapshot) -> None:
        for key, value in snapshot.values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        tempfile.tempdir = snapshot.tempfile_dir

    def evidence_reference(self, path: str | Path) -> str:
        candidate = _resolved(path)
        try:
            return candidate.relative_to(self.evidence_dir).as_posix()
        except ValueError as exc:
            raise CliFailure(
                CliExitCode.ISOLATION_ERROR,
                "evidence_outside_directory",
                "证据文件必须位于指定证据目录内",
            ) from exc


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents
