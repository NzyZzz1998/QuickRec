"""中央素材库业务入口。"""

import json
import logging
import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.media_metadata import probe_media
from utils.recording_library_store import (
    STATUS_AVAILABLE,
    STATUS_MISSING,
    LibraryLoadResult,
    LibraryWriteResult,
    MaterialItem,
    load_library,
    normalize_windows_path,
    save_library,
)
from utils.recycle_bin import recycle_file

SCAN_PROBE_TIMEOUT_SEC = 1.5
logger = logging.getLogger("QuickRec")


def _synchronized(method: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(self: "RecordingLibraryService", *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapped


@dataclass(frozen=True)
class MigrationResult:
    ok: bool
    source_path: Path
    items: list[MaterialItem] = field(default_factory=list)
    added_count: int = 0
    duplicate_count: int = 0
    skipped_count: int = 0
    pruned_count: int = 0
    migration_sources: list[dict[str, Any]] = field(default_factory=list)
    library_extensions: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass(frozen=True)
class DirectoryScanResult:
    ok: bool
    directory: Path
    items: list[MaterialItem] = field(default_factory=list)
    scanned_count: int = 0
    duplicate_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    cancelled: bool = False
    error: str = ""


@dataclass(frozen=True)
class RelinkCandidate:
    item_id: str
    old_path: str
    candidate_path: str
    match_reasons: tuple[str, ...]


class RecordingLibraryService:
    def __init__(self, library_path: str | Path):
        self.library_path = Path(library_path)
        self._lock = threading.RLock()

    def load(self) -> LibraryLoadResult:
        return load_library(self.library_path)

    def list_items(self, *, offset: int = 0, limit: int = 50) -> list[MaterialItem]:
        loaded = self.load()
        if not loaded.ok:
            return []
        start = max(0, offset)
        end = start + max(0, limit)
        return loaded.items[start:end]

    @_synchronized
    def add(self, item: MaterialItem) -> LibraryWriteResult:
        loaded = self.load()
        if not loaded.ok:
            return LibraryWriteResult(False, self.library_path, error=loaded.error)
        return save_library(
            self.library_path,
            [item, *loaded.items],
            migration_sources=loaded.migration_sources,
            extensions=loaded.extensions,
        )

    def add_recording(
        self,
        output_path: str | Path,
        *,
        metadata: dict[str, Any],
        diagnostic_dir: str | None,
    ) -> LibraryWriteResult:
        path = Path(output_path)
        try:
            stat = path.stat()
        except OSError as exc:
            return LibraryWriteResult(False, self.library_path, error=str(exc))
        created_at = _created_at_from_quickrec_name(path) or datetime.fromtimestamp(
            stat.st_mtime
        ).astimezone().isoformat(timespec="seconds")
        item = MaterialItem(
            id=uuid.uuid4().hex,
            file_path=str(path),
            file_name=path.name,
            directory=str(path.parent),
            mode=str(metadata.get("mode") or "unknown"),
            audio_source=str(metadata.get("audio_source") or "unknown"),
            created_at=created_at,
            duration_sec=_optional_float(metadata.get("duration_sec")),
            width=_optional_int(metadata.get("width")),
            height=_optional_int(metadata.get("height")),
            fps=_optional_float(metadata.get("fps")),
            file_size_bytes=stat.st_size,
            file_modified_ns=stat.st_mtime_ns,
            diagnostic_dir=diagnostic_dir,
        )
        return self.add(item)

    def has_processed_source(self, source_path: str | Path) -> bool:
        normalized = normalize_windows_path(source_path)
        loaded = self.load()
        return loaded.ok and any(
            normalize_windows_path(str(entry.get("source_path") or "")) == normalized
            and str(entry.get("status") or "") in {"migrated", "declined"}
            for entry in loaded.migration_sources
        )

    def has_source_status(self, source_path: str | Path) -> bool:
        normalized = normalize_windows_path(source_path)
        loaded = self.load()
        return loaded.ok and any(
            normalize_windows_path(str(entry.get("source_path") or "")) == normalized
            for entry in loaded.migration_sources
        )

    @_synchronized
    def mark_source_status(
        self,
        source_path: str | Path,
        *,
        status: str,
        changed_at: str,
    ) -> LibraryWriteResult:
        loaded = self.load()
        if not loaded.ok:
            return LibraryWriteResult(False, self.library_path, error=loaded.error)
        normalized = normalize_windows_path(source_path)
        sources = [
            entry
            for entry in loaded.migration_sources
            if normalize_windows_path(str(entry.get("source_path") or "")) != normalized
        ]
        sources.append(
            {
                "source_path": str(source_path),
                "status": status,
                "changed_at": changed_at,
            }
        )
        return save_library(
            self.library_path,
            loaded.items,
            migration_sources=sources,
            extensions=loaded.extensions,
        )

    @_synchronized
    def replace(self, items: list[MaterialItem]) -> LibraryWriteResult:
        loaded = self.load()
        if not loaded.ok:
            return LibraryWriteResult(False, self.library_path, error=loaded.error)
        return save_library(
            self.library_path,
            items,
            migration_sources=loaded.migration_sources,
            extensions=loaded.extensions,
        )

    @_synchronized
    def remove(self, item_id: str) -> LibraryWriteResult:
        loaded = self.load()
        if not loaded.ok:
            return LibraryWriteResult(False, self.library_path, error=loaded.error)
        remaining = [item for item in loaded.items if item.id != item_id]
        return save_library(
            self.library_path,
            remaining,
            migration_sources=loaded.migration_sources,
            extensions=loaded.extensions,
        )

    @_synchronized
    def relink(self, item_id: str, new_path: str | Path) -> LibraryWriteResult:
        loaded = self.load()
        if not loaded.ok:
            return LibraryWriteResult(False, self.library_path, error=loaded.error)
        target = Path(new_path)
        if not target.is_file() or target.suffix.lower() != ".mp4":
            return LibraryWriteResult(False, self.library_path, loaded.items, "selected file does not exist or is not MP4")
        normalized_target = normalize_windows_path(target)
        if any(
            item.id != item_id and normalize_windows_path(item.file_path) == normalized_target
            for item in loaded.items
        ):
            return LibraryWriteResult(False, self.library_path, loaded.items, "file path is already used by another item")
        item = next((candidate for candidate in loaded.items if candidate.id == item_id), None)
        if item is None:
            return LibraryWriteResult(False, self.library_path, loaded.items, "material item not found")
        metadata = probe_media(target)
        if not metadata.ok:
            logger.warning("material relink validation failed: id=%s error=%s", item_id, metadata.error)
            return LibraryWriteResult(False, self.library_path, loaded.items, metadata.error)
        stat = target.stat()
        item.file_path = str(target)
        item.file_name = target.name
        item.directory = str(target.parent)
        item.file_size_bytes = stat.st_size
        item.file_modified_ns = stat.st_mtime_ns
        item.status = STATUS_AVAILABLE
        item.duration_sec = metadata.duration_sec
        item.width = metadata.width
        item.height = metadata.height
        item.fps = metadata.fps
        result = save_library(
            self.library_path,
            loaded.items,
            migration_sources=loaded.migration_sources,
            extensions=loaded.extensions,
        )
        if result.ok:
            logger.info("material relink completed: id=%s", item_id)
        else:
            logger.warning("material relink failed: id=%s error=%s", item_id, result.error)
        return result

    @_synchronized
    def recycle(self, item_id: str) -> LibraryWriteResult:
        loaded = self.load()
        if not loaded.ok:
            return LibraryWriteResult(False, self.library_path, error=loaded.error)
        item = next((candidate for candidate in loaded.items if candidate.id == item_id), None)
        if item is None:
            return LibraryWriteResult(False, self.library_path, loaded.items, "material item not found")
        recycled = recycle_file(Path(item.file_path))
        if not recycled.ok:
            logger.warning("material recycle failed: id=%s error=%s", item_id, recycled.error)
            return LibraryWriteResult(False, self.library_path, loaded.items, recycled.error)
        remaining = [candidate for candidate in loaded.items if candidate.id != item_id]
        result = save_library(
            self.library_path,
            remaining,
            migration_sources=loaded.migration_sources,
            extensions=loaded.extensions,
        )
        if result.ok:
            logger.info("material recycled and index removed: id=%s", item_id)
        else:
            logger.warning("material recycled but index update failed: id=%s error=%s", item_id, result.error)
        return result

    def preview_v1_history(self, source_path: str | Path, *, imported_at: str) -> MigrationResult:
        source = Path(source_path)
        logger.info("material migration preview started: %s", source)
        loaded = self.load()
        if not loaded.ok:
            return MigrationResult(False, source, error=loaded.error)
        try:
            payload = json.loads(source.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
                raise ValueError("legacy history must contain an items array")
            raw_items = payload.get("items", [])
        except Exception as exc:
            logger.warning("material migration preview failed: %s", exc)
            return MigrationResult(False, source, error=str(exc))

        seen_paths = {normalize_windows_path(item.file_path) for item in loaded.items}
        added: list[MaterialItem] = []
        duplicate_count = 0
        skipped_count = 0
        for raw_item in raw_items:
            if (
                not isinstance(raw_item, dict)
                or not raw_item.get("file_path")
                or not raw_item.get("created_at")
            ):
                skipped_count += 1
                continue
            material_data = dict(raw_item)
            material_data.update(
                imported_at=imported_at,
                source_type="migration",
                source_history_path=str(source),
            )
            item = MaterialItem.from_dict(material_data)
            path = Path(item.file_path)
            if path.exists():
                if not path.is_file() or path.suffix.lower() != ".mp4":
                    skipped_count += 1
                    continue
                metadata = probe_media(path)
                if not metadata.ok:
                    logger.warning("material migration skipped invalid media: path=%s error=%s", path, metadata.error)
                    skipped_count += 1
                    continue
                item.duration_sec = metadata.duration_sec
                item.width = metadata.width
                item.height = metadata.height
                item.fps = metadata.fps
                item.file_size_bytes = path.stat().st_size
                item.status = STATUS_AVAILABLE
            normalized_path = normalize_windows_path(item.file_path)
            if normalized_path in seen_paths:
                duplicate_count += 1
                continue
            seen_paths.add(normalized_path)
            added.append(item)

        normalized_source = normalize_windows_path(source)
        sources = [
            entry
            for entry in loaded.migration_sources
            if normalize_windows_path(str(entry.get("source_path") or "")) != normalized_source
        ]
        sources.append(
            {
                "source_path": str(source),
                "status": "migrated",
                "migrated_at": imported_at,
                "added_count": len(added),
                "duplicate_count": duplicate_count,
                "skipped_count": skipped_count,
            }
        )
        before_count = len(loaded.items) + len(added)
        candidate_items = sorted(
            [*added, *loaded.items],
            key=lambda item: item.created_at,
            reverse=True,
        )[:200]
        result = MigrationResult(
            True,
            source,
            candidate_items,
            added_count=len(added),
            duplicate_count=duplicate_count,
            skipped_count=skipped_count,
            pruned_count=max(0, before_count - len(candidate_items)),
            migration_sources=sources,
            library_extensions=loaded.extensions,
        )
        logger.info(
            "material migration preview completed: added=%s duplicate=%s skipped=%s pruned=%s",
            result.added_count,
            result.duplicate_count,
            result.skipped_count,
            result.pruned_count,
        )
        return result

    @_synchronized
    def commit_migration(self, preview: MigrationResult) -> LibraryWriteResult:
        if not preview.ok:
            return LibraryWriteResult(False, self.library_path, error=preview.error)
        return save_library(
            self.library_path,
            preview.items,
            migration_sources=preview.migration_sources,
            extensions=preview.library_extensions,
        )

    @_synchronized
    def migrate_v1_history(self, source_path: str | Path, *, imported_at: str) -> MigrationResult:
        preview = self.preview_v1_history(source_path, imported_at=imported_at)
        if not preview.ok:
            return preview
        written = self.commit_migration(preview)
        if not written.ok:
            return MigrationResult(False, preview.source_path, error=written.error)
        return MigrationResult(
            True,
            preview.source_path,
            written.items,
            added_count=preview.added_count,
            duplicate_count=preview.duplicate_count,
            skipped_count=preview.skipped_count,
            pruned_count=preview.pruned_count,
            migration_sources=preview.migration_sources,
            library_extensions=preview.library_extensions,
        )

    def preview_directory(
        self,
        directory: str | Path,
        *,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> DirectoryScanResult:
        target = Path(directory)
        logger.info("material directory scan started: %s", target)
        if not target.is_dir():
            return DirectoryScanResult(False, target, error="directory does not exist")
        items: list[MaterialItem] = []
        scanned_count = 0
        duplicate_count = 0
        skipped_count = 0
        failed_count = 0
        loaded = self.load()
        existing_paths = {
            normalize_windows_path(item.file_path)
            for item in loaded.items
        } if loaded.ok else set()
        try:
            for path in target.iterdir():
                if cancel_requested and cancel_requested():
                    logger.info("material directory scan cancelled: %s", target)
                    return DirectoryScanResult(True, target, cancelled=True)
                if not path.is_file() or not path.name.lower().startswith("quickrec_") or path.suffix.lower() != ".mp4":
                    continue
                scanned_count += 1
                if normalize_windows_path(path) in existing_paths:
                    duplicate_count += 1
                    continue
                try:
                    stat = path.stat()
                    metadata = probe_media(path, timeout=SCAN_PROBE_TIMEOUT_SEC)
                    if not metadata.ok:
                        failed_count += 1
                        logger.warning("material directory scan skipped invalid media: path=%s error=%s", path, metadata.error)
                        continue
                    created_at = _created_at_from_quickrec_name(path) or datetime.fromtimestamp(
                        stat.st_mtime
                    ).astimezone().isoformat(timespec="seconds")
                    items.append(
                        MaterialItem(
                            id=uuid.uuid4().hex,
                            file_path=str(path),
                            file_name=path.name,
                            directory=str(path.parent),
                            mode="unknown",
                            audio_source="unknown",
                            created_at=created_at,
                            duration_sec=metadata.duration_sec,
                            width=metadata.width,
                            height=metadata.height,
                            fps=metadata.fps,
                            file_size_bytes=stat.st_size,
                            file_modified_ns=stat.st_mtime_ns,
                            status=STATUS_AVAILABLE,
                            source_type="rebuild",
                        )
                    )
                except OSError:
                    skipped_count += 1
        except OSError as exc:
            return DirectoryScanResult(False, target, error=str(exc))
        items.sort(key=lambda item: item.created_at, reverse=True)
        result = DirectoryScanResult(
            True,
            target,
            items[:200],
            scanned_count=scanned_count,
            duplicate_count=duplicate_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
        )
        logger.info(
            "material directory scan completed: scanned=%s success=%s duplicate=%s skipped=%s failed=%s",
            scanned_count,
            len(result.items),
            duplicate_count,
            skipped_count,
            failed_count,
        )
        return result

    @_synchronized
    def commit_scan(self, scan: DirectoryScanResult, *, imported_at: str) -> LibraryWriteResult:
        if not scan.ok or scan.cancelled:
            return LibraryWriteResult(False, self.library_path, error=scan.error or "scan was cancelled")
        loaded = self.load()
        if not loaded.ok:
            logger.warning(
                "material directory rebuild replacing unreadable index after confirmation: %s",
                loaded.error,
            )
            for item in scan.items:
                item.imported_at = imported_at
            return save_library(self.library_path, scan.items)
        existing_paths = {normalize_windows_path(item.file_path) for item in loaded.items}
        added: list[MaterialItem] = []
        for item in scan.items:
            if normalize_windows_path(item.file_path) in existing_paths:
                continue
            item.imported_at = imported_at
            existing_paths.add(normalize_windows_path(item.file_path))
            added.append(item)
        return save_library(
            self.library_path,
            [*added, *loaded.items],
            migration_sources=loaded.migration_sources,
            extensions=loaded.extensions,
        )

    def find_relink_candidates(self, scanned_items: list[MaterialItem]) -> list[RelinkCandidate]:
        loaded = self.load()
        if not loaded.ok:
            return []
        candidates: list[RelinkCandidate] = []
        used_paths: set[str] = set()
        for missing in (item for item in loaded.items if item.status == STATUS_MISSING):
            best: tuple[int, MaterialItem, tuple[str, ...]] | None = None
            for scanned in scanned_items:
                normalized = normalize_windows_path(scanned.file_path)
                if normalized in used_paths:
                    continue
                reasons: list[str] = []
                if missing.file_name.casefold() == scanned.file_name.casefold():
                    reasons.append("filename")
                if (
                    missing.file_size_bytes is not None
                    and scanned.file_size_bytes == missing.file_size_bytes
                ):
                    reasons.append("size")
                if (
                    missing.file_modified_ns is not None
                    and scanned.file_modified_ns is not None
                    and abs(scanned.file_modified_ns - missing.file_modified_ns) <= 2_000_000_000
                ):
                    reasons.append("modified_time")
                score = (3 if "filename" in reasons else 0) + len(reasons)
                if score and (best is None or score > best[0]):
                    best = (score, scanned, tuple(reasons))
            if best is not None:
                scanned = best[1]
                used_paths.add(normalize_windows_path(scanned.file_path))
                candidates.append(
                    RelinkCandidate(
                        item_id=missing.id,
                        old_path=missing.file_path,
                        candidate_path=scanned.file_path,
                        match_reasons=best[2],
                    )
                )
        return candidates


def _created_at_from_quickrec_name(path: Path) -> str | None:
    match = re.search(r"(\d{8})_(\d{6})", path.stem)
    if not match:
        return None
    try:
        parsed = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return parsed.astimezone().isoformat(timespec="seconds")


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
