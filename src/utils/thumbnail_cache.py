"""项目素材静态预览的独立可再生缓存。"""

from __future__ import annotations

import hashlib
import json
import logging
import ntpath
import os
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("QuickRec")

MEBIBYTE = 1024 * 1024
DEFAULT_MAX_BYTES = 500 * MEBIBYTE
CACHE_SCHEMA_VERSION = 1


def resolve_thumbnail_cache_root(local_app_data: str | Path | None = None) -> Path:
    base = Path(
        local_app_data
        or os.environ.get("LOCALAPPDATA")
        or (Path.home() / "AppData" / "Local")
    )
    return base / "QuickRec" / "ThumbnailCache" / "v1"


def normalize_thumbnail_source_path(path: str | Path) -> str:
    normalized = ntpath.normcase(ntpath.normpath(str(path)))
    return normalized.replace("\\", "/")


def _now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class ThumbnailFingerprint:
    material_id: str
    normalized_path: str
    file_size: int
    modified_ns: int
    cache_key: str

    @classmethod
    def from_file(
        cls,
        material_id: str,
        file_path: str | Path,
    ) -> ThumbnailFingerprint:
        source = Path(file_path)
        stat = source.stat()
        normalized_path = normalize_thumbnail_source_path(source)
        identity = {
            "material_id": str(material_id),
            "normalized_path": normalized_path,
            "file_size": int(stat.st_size),
            "modified_ns": int(stat.st_mtime_ns),
        }
        digest = hashlib.sha256(
            json.dumps(
                identity,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return cls(
            material_id=str(material_id),
            normalized_path=normalized_path,
            file_size=int(stat.st_size),
            modified_ns=int(stat.st_mtime_ns),
            cache_key=digest,
        )


@dataclass(frozen=True)
class ThumbnailCacheEntry:
    material_id: str
    fingerprint: str
    relative_path: str
    width: int
    height: int
    byte_size: int
    created_at: str
    accessed_at: str
    source_position_sec: float
    extensions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        cache_key: str,
        payload: dict[str, Any],
    ) -> ThumbnailCacheEntry:
        relative_path = str(payload["relative_path"])
        if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
            raise ValueError("cache entry path must be relative")
        return cls(
            material_id=str(payload["material_id"]),
            fingerprint=str(payload.get("fingerprint") or cache_key),
            relative_path=relative_path.replace("\\", "/"),
            width=int(payload["width"]),
            height=int(payload["height"]),
            byte_size=max(0, int(payload["byte_size"])),
            created_at=str(payload["created_at"]),
            accessed_at=str(payload["accessed_at"]),
            source_position_sec=float(payload["source_position_sec"]),
            extensions=dict(payload.get("extensions") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "fingerprint": self.fingerprint,
            "relative_path": self.relative_path,
            "width": self.width,
            "height": self.height,
            "byte_size": self.byte_size,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "source_position_sec": self.source_position_sec,
            "extensions": dict(self.extensions),
        }


@dataclass(frozen=True)
class ThumbnailCacheLoadResult:
    ok: bool
    entries: dict[str, ThumbnailCacheEntry] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)
    recovered: bool = False
    error: str = ""


@dataclass(frozen=True)
class ThumbnailCacheLookupResult:
    entry: ThumbnailCacheEntry | None
    path: Path | None = None


@dataclass(frozen=True)
class ThumbnailCacheWriteResult:
    ok: bool
    path: Path
    entry: ThumbnailCacheEntry | None = None
    error: str = ""


@dataclass(frozen=True)
class ThumbnailCachePruneResult:
    ok: bool
    removed_keys: tuple[str, ...] = ()
    remaining_bytes: int = 0
    error: str = ""


class ThumbnailCacheStore:
    def __init__(
        self,
        root: str | Path | None = None,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        now: Callable[[], str] = _now_iso,
    ) -> None:
        self.root = Path(root) if root is not None else resolve_thumbnail_cache_root()
        self.index_path = self.root / "index.json"
        self.images_dir = self.root / "images"
        self.temp_dir = self.root / "temp"
        self.max_bytes = max(0, int(max_bytes))
        self._now = now
        self._lock = threading.RLock()

    def create_temp_path(self, cache_key: str) -> Path:
        return self.temp_dir / f"{cache_key}-{uuid.uuid4().hex}.tmp.jpg"

    def cache_path(self, cache_key: str) -> Path:
        return self.images_dir / f"{cache_key}.jpg"

    def load(self) -> ThumbnailCacheLoadResult:
        with self._lock:
            return self._load_unlocked()

    def _load_unlocked(self) -> ThumbnailCacheLoadResult:
        if not self.index_path.is_file():
            return ThumbnailCacheLoadResult(True)
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != CACHE_SCHEMA_VERSION:
                raise ValueError(
                    f"unsupported thumbnail cache schema: {payload.get('schema_version')}"
                )
            raw_entries = payload.get("entries", {})
            if not isinstance(raw_entries, dict):
                raise ValueError("thumbnail cache entries must be an object")
            entries: dict[str, ThumbnailCacheEntry] = {}
            for cache_key, value in raw_entries.items():
                if not isinstance(value, dict):
                    continue
                try:
                    entries[str(cache_key)] = ThumbnailCacheEntry.from_dict(
                        str(cache_key),
                        value,
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            extensions = payload.get("extensions", {})
            return ThumbnailCacheLoadResult(
                True,
                entries,
                dict(extensions) if isinstance(extensions, dict) else {},
            )
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            preserved = self._preserve_corrupt_index()
            return ThumbnailCacheLoadResult(
                True,
                recovered=True,
                error=f"{exc}; preserved={preserved}",
            )

    def lookup(
        self,
        fingerprint: ThumbnailFingerprint,
        *,
        accessed_at: str | None = None,
    ) -> ThumbnailCacheLookupResult:
        with self._lock:
            return self._lookup_unlocked(fingerprint, accessed_at=accessed_at)

    def find_latest_for_material(
        self,
        material_id: str,
    ) -> ThumbnailCacheLookupResult:
        with self._lock:
            loaded = self._load_unlocked()
            matches = sorted(
                (
                    entry
                    for entry in loaded.entries.values()
                    if entry.material_id == material_id
                ),
                key=lambda entry: (entry.accessed_at, entry.created_at),
                reverse=True,
            )
            for entry in matches:
                path = self.root / entry.relative_path
                if path.is_file():
                    return ThumbnailCacheLookupResult(entry, path)
            return ThumbnailCacheLookupResult(None)

    def _lookup_unlocked(
        self,
        fingerprint: ThumbnailFingerprint,
        *,
        accessed_at: str | None = None,
    ) -> ThumbnailCacheLookupResult:
        loaded = self.load()
        entry = loaded.entries.get(fingerprint.cache_key)
        if entry is None or entry.fingerprint != fingerprint.cache_key:
            return ThumbnailCacheLookupResult(None)
        path = self.root / entry.relative_path
        if not path.is_file():
            entries = dict(loaded.entries)
            entries.pop(fingerprint.cache_key, None)
            self._save(entries, loaded.extensions)
            return ThumbnailCacheLookupResult(None)
        if accessed_at is not None and accessed_at != entry.accessed_at:
            touched = ThumbnailCacheEntry(
                material_id=entry.material_id,
                fingerprint=entry.fingerprint,
                relative_path=entry.relative_path,
                width=entry.width,
                height=entry.height,
                byte_size=entry.byte_size,
                created_at=entry.created_at,
                accessed_at=accessed_at,
                source_position_sec=entry.source_position_sec,
                extensions=entry.extensions,
            )
            entries = dict(loaded.entries)
            entries[fingerprint.cache_key] = touched
            self._save(entries, loaded.extensions)
            entry = touched
        return ThumbnailCacheLookupResult(entry, path)

    def commit(
        self,
        temp_path: str | Path,
        fingerprint: ThumbnailFingerprint,
        *,
        width: int,
        height: int,
        source_position_sec: float,
        accessed_at: str | None = None,
    ) -> ThumbnailCacheWriteResult:
        with self._lock:
            return self._commit_unlocked(
                temp_path,
                fingerprint,
                width=width,
                height=height,
                source_position_sec=source_position_sec,
                accessed_at=accessed_at,
            )

    def _commit_unlocked(
        self,
        temp_path: str | Path,
        fingerprint: ThumbnailFingerprint,
        *,
        width: int,
        height: int,
        source_position_sec: float,
        accessed_at: str | None = None,
    ) -> ThumbnailCacheWriteResult:
        temp = Path(temp_path)
        final_path = self.cache_path(fingerprint.cache_key)
        if not temp.is_file():
            return ThumbnailCacheWriteResult(False, final_path, error="temporary thumbnail is missing")
        try:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp, final_path)
            timestamp = accessed_at or self._now()
            entry = ThumbnailCacheEntry(
                material_id=fingerprint.material_id,
                fingerprint=fingerprint.cache_key,
                relative_path=final_path.relative_to(self.root).as_posix(),
                width=int(width),
                height=int(height),
                byte_size=final_path.stat().st_size,
                created_at=timestamp,
                accessed_at=timestamp,
                source_position_sec=float(source_position_sec),
            )
            loaded = self.load()
            entries = dict(loaded.entries)
            entries[fingerprint.cache_key] = entry
            self._save(entries, loaded.extensions)
            return ThumbnailCacheWriteResult(True, final_path, entry)
        except OSError as exc:
            return ThumbnailCacheWriteResult(False, final_path, error=str(exc))

    def prune(
        self,
        *,
        protected_keys: set[str] | frozenset[str] | None = None,
    ) -> ThumbnailCachePruneResult:
        with self._lock:
            return self._prune_unlocked(protected_keys=protected_keys)

    def _prune_unlocked(
        self,
        *,
        protected_keys: set[str] | frozenset[str] | None = None,
    ) -> ThumbnailCachePruneResult:
        protected = set(protected_keys or ())
        loaded = self.load()
        entries = dict(loaded.entries)
        total = 0
        for cache_key, entry in tuple(entries.items()):
            path = self.root / entry.relative_path
            if path.is_file():
                total += path.stat().st_size
            else:
                entries.pop(cache_key, None)
        removed: list[str] = []
        candidates = sorted(
            (
                (cache_key, entry)
                for cache_key, entry in entries.items()
                if cache_key not in protected
            ),
            key=lambda item: (item[1].accessed_at, item[0]),
        )
        failures: list[str] = []
        try:
            for cache_key, entry in candidates:
                if total <= self.max_bytes:
                    break
                path = self.root / entry.relative_path
                size = path.stat().st_size if path.is_file() else 0
                try:
                    if path.is_file():
                        path.unlink()
                except OSError:
                    failures.append(cache_key)
                    continue
                total = max(0, total - size)
                entries.pop(cache_key, None)
                removed.append(cache_key)
            self._save(entries, loaded.extensions)
            logger.info(
                "thumbnail cache pruned: removed=%s remaining_bytes=%s "
                "failed=%s",
                len(removed),
                total,
                len(failures),
            )
            return ThumbnailCachePruneResult(
                not failures,
                tuple(removed),
                total,
                (
                    ""
                    if not failures
                    else f"failed to remove {len(failures)} cache files"
                ),
            )
        except OSError as exc:
            logger.warning(
                "thumbnail cache prune failed: removed=%s error=%s",
                len(removed),
                str(exc)[:300],
            )
            return ThumbnailCachePruneResult(
                False,
                tuple(removed),
                total,
                str(exc),
            )

    def _save(
        self,
        entries: dict[str, ThumbnailCacheEntry],
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "entries": {
                key: entries[key].to_dict()
                for key in sorted(entries)
            },
            "extensions": dict(extensions or {}),
        }
        temp = self.root / f"index-{uuid.uuid4().hex}.tmp"
        try:
            temp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temp, self.index_path)
        finally:
            if temp.exists():
                temp.unlink()

    def _preserve_corrupt_index(self) -> str:
        if not self.index_path.exists():
            return ""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.root / f"index.corrupt-{timestamp}-{uuid.uuid4().hex[:8]}.json"
        try:
            os.replace(self.index_path, target)
            logger.warning(
                "thumbnail cache index recovered: preserved=%s",
                target.name,
            )
            return str(target)
        except OSError:
            return ""
