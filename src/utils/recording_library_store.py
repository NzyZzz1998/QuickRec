"""中央素材索引的本地存储能力。"""

import json
import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

LIBRARY_FILE_NAME = "recordings.json"
SCHEMA_VERSION = 2
DEFAULT_MAX_ITEMS = 200
STATUS_AVAILABLE = "available"
STATUS_MISSING = "missing"
STATUS_METADATA_INCOMPLETE = "metadata_incomplete"
logger = logging.getLogger("QuickRec")


@dataclass
class MaterialItem:
    id: str
    file_path: str
    file_name: str
    directory: str
    mode: str
    audio_source: str
    created_at: str
    imported_at: str | None = None
    duration_sec: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    file_size_bytes: int | None = None
    file_modified_ns: int | None = None
    status: str = STATUS_AVAILABLE
    diagnostic_dir: str | None = None
    source_type: str = "recording"
    source_history_path: str | None = None
    extensions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaterialItem":
        file_path = str(data.get("file_path") or "")
        path = Path(file_path)
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex),
            file_path=file_path,
            file_name=str(data.get("file_name") or path.name),
            directory=str(data.get("directory") or path.parent),
            mode=str(data.get("mode") or "unknown"),
            audio_source=str(data.get("audio_source") or "unknown"),
            created_at=str(data.get("created_at") or ""),
            imported_at=_optional_str(data.get("imported_at")),
            duration_sec=_optional_float(data.get("duration_sec")),
            width=_optional_int(data.get("width")),
            height=_optional_int(data.get("height")),
            fps=_optional_float(data.get("fps")),
            file_size_bytes=_optional_int(data.get("file_size_bytes")),
            file_modified_ns=_optional_int(data.get("file_modified_ns")),
            status=str(data.get("status") or STATUS_AVAILABLE),
            diagnostic_dir=_optional_str(data.get("diagnostic_dir")),
            source_type=str(data.get("source_type") or "recording"),
            source_history_path=_optional_str(data.get("source_history_path")),
            extensions=dict(data.get("extensions") or {}),
        ).with_refreshed_status()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "normalized_path": normalize_windows_path(self.file_path),
            "file_name": self.file_name,
            "directory": self.directory,
            "mode": self.mode,
            "audio_source": self.audio_source,
            "created_at": self.created_at,
            "imported_at": self.imported_at,
            "duration_sec": self.duration_sec,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "file_size_bytes": self.file_size_bytes,
            "file_modified_ns": self.file_modified_ns,
            "status": self.status,
            "diagnostic_dir": self.diagnostic_dir,
            "source_type": self.source_type,
            "source_history_path": self.source_history_path,
            "extensions": self.extensions,
        }

    def with_refreshed_status(self) -> "MaterialItem":
        if not self.file_path or not Path(self.file_path).exists():
            self.status = STATUS_MISSING
        elif self.status == STATUS_MISSING:
            self.status = STATUS_AVAILABLE
        return self


@dataclass(frozen=True)
class LibraryLoadResult:
    ok: bool
    path: Path
    items: list[MaterialItem] = field(default_factory=list)
    migration_sources: list[dict[str, Any]] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    recovered: bool = False
    corrupt_path: Path | None = None
    skipped_items: int = 0


@dataclass(frozen=True)
class LibraryWriteResult:
    ok: bool
    path: Path
    items: list[MaterialItem] = field(default_factory=list)
    error: str = ""


def resolve_library_file(appdata_dir: str | Path | None = None) -> Path:
    """返回 QuickRec Full 中央素材索引路径。"""
    root = Path(appdata_dir) if appdata_dir is not None else Path(os.getenv("APPDATA") or Path.home())
    return root / "QuickRec" / LIBRARY_FILE_NAME


def normalize_windows_path(path: str | Path) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))


def load_library(path: str | Path) -> LibraryLoadResult:
    target = Path(path)
    if not target.exists():
        return LibraryLoadResult(True, target)
    result = _read_library(target)
    if result.ok:
        logger.info("material library loaded: items=%s", len(result.items))
        return result

    corrupt_path = _archive_corrupt_file(target)
    logger.warning("material library corrupt, archived=%s error=%s", corrupt_path, result.error)
    backup_path = target.with_name(f"{target.name}.bak")
    backup = _read_library(backup_path) if backup_path.exists() else None
    if backup and backup.ok:
        shutil.copy2(backup_path, target)
        logger.info("material library restored from backup: %s", backup_path)
        return LibraryLoadResult(
            True,
            target,
            backup.items,
            backup.migration_sources,
            backup.extensions,
            recovered=True,
            corrupt_path=corrupt_path,
            skipped_items=backup.skipped_items,
        )
    logger.error("material library recovery failed: %s", result.error)
    return LibraryLoadResult(False, target, error=result.error, corrupt_path=corrupt_path)


def _read_library(target: Path) -> LibraryLoadResult:
    try:
        payload = json.loads(target.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("library root must be an object")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported library schema: {payload.get('schema_version')}")
        raw_items = payload.get("items", [])
        if not isinstance(raw_items, list):
            raise ValueError("library items must be an array")
        valid_items = [
            item
            for item in raw_items
            if isinstance(item, dict) and item.get("file_path") and item.get("created_at")
        ]
        items = [MaterialItem.from_dict(item) for item in valid_items]
        sources = payload.get("migration_sources", [])
        extensions = payload.get("extensions", {})
        return LibraryLoadResult(
            True,
            target,
            items,
            list(sources) if isinstance(sources, list) else [],
            dict(extensions) if isinstance(extensions, dict) else {},
            skipped_items=len(raw_items) - len(valid_items),
        )
    except Exception as exc:
        return LibraryLoadResult(False, target, error=str(exc))


def save_library(
    path: str | Path,
    items: list[MaterialItem],
    *,
    migration_sources: list[dict[str, Any]] | None = None,
    extensions: dict[str, Any] | None = None,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> LibraryWriteResult:
    target = Path(path)
    normalized_items = _deduplicate_and_sort(items)[:max_items]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "max_items": max_items,
        "items": [item.to_dict() for item in normalized_items],
        "migration_sources": list(migration_sources or []),
        "extensions": dict(extensions or {}),
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and _read_library(target).ok:
            shutil.copy2(target, target.with_name(f"{target.name}.bak"))
        _atomic_write_json(target, payload)
    except Exception as exc:
        logger.error("material library save failed: %s", exc)
        return LibraryWriteResult(False, target, normalized_items, str(exc))
    logger.info("material library saved: items=%s", len(normalized_items))
    return LibraryWriteResult(True, target, normalized_items)


def _deduplicate_and_sort(items: list[MaterialItem]) -> list[MaterialItem]:
    sorted_items = sorted(items, key=lambda item: item.created_at, reverse=True)
    seen_paths: set[str] = set()
    result: list[MaterialItem] = []
    for item in sorted_items:
        normalized_path = normalize_windows_path(item.file_path)
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        result.append(item)
    return result


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def _archive_corrupt_file(path: Path, max_archives: int = 5) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    corrupt_path = path.with_name(f"{path.stem}.corrupt-{timestamp}{path.suffix}")
    shutil.copy2(path, corrupt_path)
    archives = sorted(path.parent.glob(f"{path.stem}.corrupt-*{path.suffix}"), key=lambda item: item.name)
    for old_path in archives[:-max_archives]:
        old_path.unlink(missing_ok=True)
    return corrupt_path


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
