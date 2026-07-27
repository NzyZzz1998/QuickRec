"""QuickRec Full 项目文件与中央项目索引存储。"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.recording_library_store import normalize_windows_path

PROJECT_FILE_NAME = "project.qrproj"
PROJECT_INDEX_FILE_NAME = "projects.json"
PROJECT_SCHEMA_VERSION = 1
PROJECT_INDEX_SCHEMA_VERSION = 1
logger = logging.getLogger("QuickRec")


@dataclass
class ProjectMaterialRef:
    material_id: str
    last_known_path: str
    file_name: str
    added_at: str
    metadata_snapshot: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectMaterialRef:
        material_id = _required_text(data, "material_id")
        added_at = _required_text(data, "added_at")
        return cls(
            material_id=material_id,
            last_known_path=str(data.get("last_known_path") or ""),
            file_name=str(data.get("file_name") or Path(str(data.get("last_known_path") or "")).name),
            added_at=added_at,
            metadata_snapshot=_object(data.get("metadata_snapshot"), "metadata_snapshot"),
            extensions=_object(data.get("extensions"), "extensions"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "last_known_path": self.last_known_path,
            "file_name": self.file_name,
            "added_at": self.added_at,
            "metadata_snapshot": dict(self.metadata_snapshot),
            "extensions": dict(self.extensions),
        }


@dataclass
class ProjectFile:
    project_id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    archived_at: str | None = None
    materials: list[ProjectMaterialRef] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectFile:
        _require_schema(data, PROJECT_SCHEMA_VERSION, "project")
        materials = data.get("materials")
        if not isinstance(materials, list):
            raise ValueError("materials must be an array")
        parsed = [
            ProjectMaterialRef.from_dict(item)
            if isinstance(item, dict)
            else _raise_value("material entry must be an object")
            for item in materials
        ]
        material_ids = [item.material_id for item in parsed]
        if len(set(material_ids)) != len(material_ids):
            raise ValueError("duplicate material_id")
        return cls(
            project_id=_required_text(data, "project_id"),
            name=_required_text(data, "name"),
            description=str(data.get("description") or ""),
            created_at=_required_text(data, "created_at"),
            updated_at=_required_text(data, "updated_at"),
            archived_at=_optional_text(data.get("archived_at")),
            materials=parsed,
            extensions=_object(data.get("extensions"), "extensions"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROJECT_SCHEMA_VERSION,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived_at": self.archived_at,
            "materials": [item.to_dict() for item in self.materials],
            "extensions": dict(self.extensions),
        }


@dataclass
class ProjectIndexEntry:
    project_id: str
    file_path: str
    name: str
    created_at: str
    updated_at: str
    last_opened_at: str | None = None
    archived_at: str | None = None
    file_modified_ns: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectIndexEntry:
        return cls(
            project_id=_required_text(data, "project_id"),
            file_path=_required_text(data, "file_path"),
            name=_required_text(data, "name"),
            created_at=_required_text(data, "created_at"),
            updated_at=_required_text(data, "updated_at"),
            last_opened_at=_optional_text(data.get("last_opened_at")),
            archived_at=_optional_text(data.get("archived_at")),
            file_modified_ns=_optional_int(data.get("file_modified_ns")),
        )

    @classmethod
    def from_project(cls, project: ProjectFile, file_path: str | Path) -> ProjectIndexEntry:
        path = Path(file_path)
        try:
            modified_ns = path.stat().st_mtime_ns
        except OSError:
            modified_ns = 0
        return cls(
            project_id=project.project_id,
            file_path=str(path),
            name=project.name,
            created_at=project.created_at,
            updated_at=project.updated_at,
            last_opened_at=None,
            archived_at=project.archived_at,
            file_modified_ns=modified_ns,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "file_path": self.file_path,
            "normalized_path": normalize_windows_path(self.file_path),
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_opened_at": self.last_opened_at,
            "archived_at": self.archived_at,
            "file_modified_ns": self.file_modified_ns,
        }


@dataclass(frozen=True)
class ProjectLoadResult:
    ok: bool
    path: Path
    project: ProjectFile | None = None
    status: str = "available"
    error: str = ""
    backup_available: bool = False
    recovered: bool = False
    corrupt_path: Path | None = None


@dataclass(frozen=True)
class ProjectWriteResult:
    ok: bool
    path: Path
    project: ProjectFile | None = None
    stage: str = "complete"
    error: str = ""
    corrupt_path: Path | None = None


@dataclass(frozen=True)
class ProjectIndexLoadResult:
    ok: bool
    path: Path
    entries: list[ProjectIndexEntry] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    recovered: bool = False
    corrupt_path: Path | None = None


@dataclass(frozen=True)
class ProjectIndexWriteResult:
    ok: bool
    path: Path
    entries: list[ProjectIndexEntry] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)
    stage: str = "complete"
    error: str = ""


@dataclass(frozen=True)
class ProjectDiscoveryResult:
    projects: list[tuple[Path, ProjectFile]] = field(default_factory=list)
    scanned_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0


@dataclass(frozen=True)
class ProjectIndexRebuildResult:
    ok: bool
    entries: list[ProjectIndexEntry] = field(default_factory=list)
    scanned_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    error: str = ""


def resolve_default_project_root(home_dir: str | Path | None = None) -> Path:
    home = Path(home_dir) if home_dir is not None else Path.home()
    return home / "Videos" / "QuickRec" / "Projects"


def resolve_project_index(appdata_dir: str | Path | None = None) -> Path:
    root = Path(appdata_dir) if appdata_dir is not None else Path(os.getenv("APPDATA") or Path.home())
    return root / "QuickRec" / PROJECT_INDEX_FILE_NAME


def resolve_project_file(project_root: str | Path, project_id: str) -> Path:
    return Path(project_root) / project_id / PROJECT_FILE_NAME


def load_project(path: str | Path) -> ProjectLoadResult:
    target = Path(path)
    backup = target.with_name(f"{target.name}.bak")
    if not target.is_file():
        return ProjectLoadResult(
            False,
            target,
            status="missing",
            error="project file does not exist",
            backup_available=_read_project(backup).ok if backup.is_file() else False,
        )
    loaded = _read_project(target)
    if loaded.ok:
        return loaded
    return ProjectLoadResult(
        False,
        target,
        status=loaded.status,
        error=loaded.error,
        backup_available=_read_project(backup).ok if backup.is_file() else False,
    )


def _read_project(path: Path) -> ProjectLoadResult:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("project root must be an object")
        project = ProjectFile.from_dict(payload)
    except UnsupportedSchemaError as exc:
        return ProjectLoadResult(False, path, status="unsupported", error=str(exc))
    except Exception as exc:
        return ProjectLoadResult(False, path, status="corrupt", error=str(exc))
    return ProjectLoadResult(True, path, project)


def save_project(path: str | Path, project: ProjectFile) -> ProjectWriteResult:
    target = Path(path)
    try:
        validated = ProjectFile.from_dict(project.to_dict())
    except Exception as exc:
        return ProjectWriteResult(False, target, project, stage="validate", error=str(exc))
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return ProjectWriteResult(False, target, project, stage="prepare_directory", error=str(exc))
    try:
        current = _read_project(target) if target.is_file() else None
        if current and current.ok:
            shutil.copy2(target, target.with_name(f"{target.name}.bak"))
        _atomic_write_json(target, validated.to_dict())
    except Exception as exc:
        logger.error("project save failed: stage=write project_id=%s error=%s", project.project_id, exc)
        return ProjectWriteResult(False, target, project, stage="write", error=str(exc))
    return ProjectWriteResult(True, target, validated)


def recover_project_from_backup(path: str | Path) -> ProjectWriteResult:
    target = Path(path)
    backup_path = target.with_name(f"{target.name}.bak")
    backup = _read_project(backup_path) if backup_path.is_file() else ProjectLoadResult(
        False,
        backup_path,
        status="missing",
        error="valid project backup does not exist",
    )
    if not backup.ok or backup.project is None:
        return ProjectWriteResult(False, target, stage="validate_backup", error=backup.error)
    corrupt_path: Path | None = None
    try:
        if target.exists():
            corrupt_path = _archive_corrupt_file(target)
        _atomic_write_json(target, backup.project.to_dict())
    except Exception as exc:
        return ProjectWriteResult(
            False,
            target,
            backup.project,
            stage="restore",
            error=str(exc),
            corrupt_path=corrupt_path,
        )
    logger.info("project restored from backup: project_id=%s", backup.project.project_id)
    return ProjectWriteResult(True, target, backup.project, corrupt_path=corrupt_path)


def load_project_index(path: str | Path) -> ProjectIndexLoadResult:
    target = Path(path)
    if not target.exists():
        return ProjectIndexLoadResult(True, target)
    loaded = _read_project_index(target)
    if loaded.ok:
        return loaded
    corrupt_path = _archive_corrupt_file(target)
    backup_path = target.with_name(f"{target.name}.bak")
    backup = _read_project_index(backup_path) if backup_path.is_file() else None
    if backup and backup.ok:
        shutil.copy2(backup_path, target)
        logger.info("project index restored from backup")
        return ProjectIndexLoadResult(
            True,
            target,
            backup.entries,
            backup.extensions,
            recovered=True,
            corrupt_path=corrupt_path,
        )
    return ProjectIndexLoadResult(False, target, error=loaded.error, corrupt_path=corrupt_path)


def _read_project_index(path: Path) -> ProjectIndexLoadResult:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("project index root must be an object")
        _require_schema(payload, PROJECT_INDEX_SCHEMA_VERSION, "project index")
        raw_entries = payload.get("projects")
        if not isinstance(raw_entries, list):
            raise ValueError("projects must be an array")
        entries = [
            ProjectIndexEntry.from_dict(item)
            if isinstance(item, dict)
            else _raise_value("project index entry must be an object")
            for item in raw_entries
        ]
        _validate_unique_entries(entries)
        extensions = _object(payload.get("extensions"), "extensions")
    except Exception as exc:
        return ProjectIndexLoadResult(False, path, error=str(exc))
    return ProjectIndexLoadResult(True, path, entries, extensions)


def save_project_index(
    path: str | Path,
    entries: list[ProjectIndexEntry],
    *,
    extensions: dict[str, Any] | None = None,
) -> ProjectIndexWriteResult:
    target = Path(path)
    try:
        _validate_unique_entries(entries)
        normalized_entries = sorted(
            entries,
            key=lambda item: (item.last_opened_at or item.updated_at, item.project_id),
            reverse=True,
        )
        payload = {
            "schema_version": PROJECT_INDEX_SCHEMA_VERSION,
            "projects": [entry.to_dict() for entry in normalized_entries],
            "extensions": dict(extensions or {}),
        }
    except Exception as exc:
        return ProjectIndexWriteResult(False, target, entries, dict(extensions or {}), stage="validate", error=str(exc))
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        current = _read_project_index(target) if target.is_file() else None
        if current and current.ok:
            shutil.copy2(target, target.with_name(f"{target.name}.bak"))
        _atomic_write_json(target, payload)
    except Exception as exc:
        logger.error("project index save failed: %s", exc)
        return ProjectIndexWriteResult(
            False,
            target,
            normalized_entries,
            dict(extensions or {}),
            stage="write",
            error=str(exc),
        )
    return ProjectIndexWriteResult(True, target, normalized_entries, dict(extensions or {}))


def discover_project_files(roots: list[str | Path]) -> ProjectDiscoveryResult:
    projects: list[tuple[Path, ProjectFile]] = []
    seen_ids: set[str] = set()
    scanned = 0
    duplicates = 0
    failed = 0
    seen_paths: set[str] = set()
    for root_value in roots:
        root = Path(root_value)
        if not root.is_dir():
            continue
        for path in root.rglob(PROJECT_FILE_NAME):
            normalized_path = normalize_windows_path(path)
            if normalized_path in seen_paths:
                continue
            seen_paths.add(normalized_path)
            scanned += 1
            loaded = load_project(path)
            if not loaded.ok or loaded.project is None:
                failed += 1
                continue
            if loaded.project.project_id in seen_ids:
                duplicates += 1
                continue
            seen_ids.add(loaded.project.project_id)
            projects.append((path, loaded.project))
    return ProjectDiscoveryResult(projects, scanned, duplicates, failed)


def rebuild_project_index(roots: list[str | Path]) -> ProjectIndexRebuildResult:
    discovery = discover_project_files(roots)
    entries = [
        ProjectIndexEntry.from_project(project, path)
        for path, project in discovery.projects
    ]
    return ProjectIndexRebuildResult(
        True,
        entries,
        discovery.scanned_count,
        discovery.duplicate_count,
        discovery.failed_count,
    )


def _validate_unique_entries(entries: list[ProjectIndexEntry]) -> None:
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for entry in entries:
        if entry.project_id in seen_ids:
            raise ValueError(f"duplicate project_id: {entry.project_id}")
        normalized_path = normalize_windows_path(entry.file_path)
        if normalized_path in seen_paths:
            raise ValueError(f"duplicate project path: {entry.file_path}")
        seen_ids.add(entry.project_id)
        seen_paths.add(normalized_path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _archive_corrupt_file(path: Path, max_archives: int = 5) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    corrupt_path = path.with_name(f"{path.stem}.corrupt-{timestamp}{path.suffix}")
    shutil.copy2(path, corrupt_path)
    archives = sorted(
        path.parent.glob(f"{path.stem}.corrupt-*{path.suffix}"),
        key=lambda item: item.name,
    )
    for old_path in archives[:-max_archives]:
        old_path.unlink(missing_ok=True)
    return corrupt_path


class UnsupportedSchemaError(ValueError):
    pass


def _require_schema(data: dict[str, Any], expected: int, label: str) -> None:
    actual = data.get("schema_version")
    if actual != expected:
        raise UnsupportedSchemaError(f"unsupported {label} schema: {actual}")


def _required_text(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("file_modified_ns must be an integer") from exc


def _object(value: Any, key: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return dict(value)


def _raise_value(message: str) -> Any:
    raise ValueError(message)
