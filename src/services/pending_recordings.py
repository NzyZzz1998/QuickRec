"""待入库录制的发现与恢复服务。"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from utils.media_metadata import probe_media
from utils.pending_recording_store import (
    PendingLoadResult,
    PendingRecordingItem,
    load_fallback_markers,
    load_pending,
    remove_fallback_marker,
    save_fallback_marker,
    save_pending,
)
from utils.recording_library_store import normalize_windows_path

logger = logging.getLogger("QuickRec")


@dataclass(frozen=True)
class PendingActionResult:
    ok: bool
    item: PendingRecordingItem | None = None
    error: str = ""
    error_code: str = ""
    storage: str = ""


class PendingRecordingService:
    def __init__(self, pending_path: str | Path):
        self.pending_path = Path(pending_path)
        self._lock = threading.RLock()

    def load(self, current_save_dir: str | Path | None = None) -> PendingLoadResult:
        primary = load_pending(self.pending_path)
        if not primary.ok:
            return primary
        items = list(primary.items)
        skipped = primary.skipped_items
        marker_path = self.pending_path
        if current_save_dir is not None:
            markers = load_fallback_markers(current_save_dir)
            marker_path = markers.path
            items.extend(markers.items)
            skipped += markers.skipped_items
        merged = self._merge(items)
        for item in merged:
            if not Path(item.file_path).is_file():
                item.status = "missing"
        return PendingLoadResult(True, marker_path, merged, skipped_items=skipped)

    def load_directory(self, directory: str | Path) -> PendingLoadResult:
        markers = load_fallback_markers(directory)
        if not markers.ok:
            return markers
        merged = self._merge(markers.items)
        for item in merged:
            if not Path(item.file_path).is_file():
                item.status = "missing"
        return PendingLoadResult(True, markers.path, merged, skipped_items=markers.skipped_items)

    def discover_directory(self, directory: str | Path) -> PendingActionResult:
        """将用户明确选择目录中的降级标记并入主待入库队列。"""
        with self._lock:
            markers = self.load_directory(directory)
            if not markers.ok:
                return PendingActionResult(
                    False,
                    error=markers.error,
                    error_code="PENDING_MARKER_READ_FAILED",
                )
            if not markers.items:
                return PendingActionResult(True, storage="none")
            primary = load_pending(self.pending_path)
            if not primary.ok:
                return PendingActionResult(
                    False,
                    error=primary.error,
                    error_code="PENDING_PRIMARY_READ_FAILED",
                )
            saved = save_pending(self.pending_path, self._merge([*markers.items, *primary.items]))
            if not saved.ok:
                return PendingActionResult(
                    False,
                    error=saved.error,
                    error_code="PENDING_PRIMARY_WRITE_FAILED",
                )
            logger.info(
                "pending directory discovered: directory=%s marker_count=%s",
                directory,
                len(markers.items),
            )
            return PendingActionResult(True, storage="primary")

    def persist(self, item: PendingRecordingItem):
        with self._lock:
            loaded = load_pending(self.pending_path)
            if not loaded.ok:
                return save_pending(self.pending_path, [item]) if not self.pending_path.exists() else _failed_write(
                    self.pending_path, loaded.error
                )
            merged = self._merge([item, *loaded.items])
            return save_pending(self.pending_path, merged)

    def persist_with_fallback(self, item: PendingRecordingItem) -> PendingActionResult:
        primary = self.persist(item)
        if primary.ok:
            logger.info("pending enqueue succeeded: pending_id=%s storage=primary", item.pending_id)
            return PendingActionResult(True, item, storage="primary")
        logger.warning("pending primary save failed: pending_id=%s error=%s", item.pending_id, primary.error)
        fallback = save_fallback_marker(item)
        if fallback.ok:
            return PendingActionResult(True, item, storage="fallback")
        return PendingActionResult(
            False,
            item,
            error=fallback.error or primary.error,
            error_code="PENDING_FALLBACK_WRITE_FAILED",
        )

    def relink(
        self,
        pending_id: str,
        new_path: str | Path,
        *,
        current_save_dir: str | Path | None = None,
    ) -> PendingActionResult:
        with self._lock:
            loaded = self.load(current_save_dir)
            if not loaded.ok:
                return PendingActionResult(False, error=loaded.error, error_code="PENDING_PRIMARY_READ_FAILED")
            item = next((candidate for candidate in loaded.items if candidate.pending_id == pending_id), None)
            if item is None:
                return PendingActionResult(False, error="pending item not found", error_code="PENDING_NOT_FOUND")
            target = Path(new_path)
            if not target.is_file() or target.suffix.lower() != ".mp4":
                return PendingActionResult(False, item, "selected file does not exist or is not MP4", "VIDEO_INVALID")
            metadata = probe_media(target)
            if not metadata.ok:
                logger.warning("pending relink failed: pending_id=%s error=%s", pending_id, metadata.error)
                return PendingActionResult(False, item, metadata.error, "VIDEO_INVALID")

            updated = PendingRecordingItem.from_dict(item.to_dict())
            stat = target.stat()
            updated.file_path = str(target)
            updated.file_name = target.name
            updated.status = "pending"
            updated.updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
            updated.duration_seconds = metadata.duration_sec
            updated.width = metadata.width
            updated.height = metadata.height
            updated.fps = metadata.fps
            updated.file_size_bytes = stat.st_size
            result = save_pending(
                self.pending_path,
                [updated if candidate.pending_id == pending_id else candidate for candidate in loaded.items],
            )
            if not result.ok:
                return PendingActionResult(False, item, result.error, "PENDING_PRIMARY_WRITE_FAILED")
            remove_fallback_marker(item)
            logger.info("pending relink succeeded: pending_id=%s", pending_id)
            return PendingActionResult(True, updated)

    def remove(
        self,
        pending_id: str,
        *,
        current_save_dir: str | Path | None = None,
    ) -> PendingActionResult:
        with self._lock:
            loaded = self.load(current_save_dir)
            if not loaded.ok:
                return PendingActionResult(False, error=loaded.error, error_code="PENDING_PRIMARY_READ_FAILED")
            item = next((candidate for candidate in loaded.items if candidate.pending_id == pending_id), None)
            if item is None:
                return PendingActionResult(True)
            primary = load_pending(self.pending_path)
            if not primary.ok:
                return PendingActionResult(False, item, primary.error, "PENDING_PRIMARY_READ_FAILED")
            remaining = [candidate for candidate in primary.items if candidate.pending_id != pending_id]
            saved = save_pending(self.pending_path, remaining)
            if not saved.ok:
                return PendingActionResult(False, item, saved.error, "PENDING_PRIMARY_WRITE_FAILED")
            remove_fallback_marker(item)
            logger.info("pending item removed: pending_id=%s", pending_id)
            return PendingActionResult(True, item)

    @staticmethod
    def _merge(items: list[PendingRecordingItem]) -> list[PendingRecordingItem]:
        by_id: dict[str, PendingRecordingItem] = {}
        path_to_id: dict[str, str] = {}
        for item in sorted(items, key=lambda value: (value.updated_at, value.attempt_count)):
            normalized = normalize_windows_path(item.file_path)
            existing_id = item.pending_id if item.pending_id in by_id else path_to_id.get(normalized)
            if existing_id is not None:
                existing = by_id[existing_id]
                if (item.updated_at, item.attempt_count) >= (existing.updated_at, existing.attempt_count):
                    item.material_id = existing.material_id
                    by_id[existing_id] = item
                continue
            by_id[item.pending_id] = item
            path_to_id[normalized] = item.pending_id
        return sorted(by_id.values(), key=lambda value: (value.queued_at, value.pending_id), reverse=True)


def _failed_write(path: Path, error: str):
    from utils.pending_recording_store import PendingWriteResult

    return PendingWriteResult(False, path, error=error)
