"""录制完成后的正式入库与失败恢复协调。"""

import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from services.pending_recordings import PendingRecordingService
from services.recording_library import RecordingLibraryService
from utils.pending_recording_store import PendingRecordingItem

logger = logging.getLogger("QuickRec")


@dataclass(frozen=True)
class IngestionResult:
    video_saved: bool
    formal_indexed: bool
    pending_persisted: bool = False
    already_indexed: bool = False
    pending_id: str = ""
    material_id: str = ""
    error_code: str = ""
    error: str = ""


@dataclass(frozen=True)
class StartupRetrySummary:
    scanned_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    missing_count: int = 0
    already_ran: bool = False


class MaterialIngestionCoordinator:
    def __init__(
        self,
        library_service: RecordingLibraryService,
        pending_service: PendingRecordingService,
    ):
        self.library_service = library_service
        self.pending_service = pending_service
        self._lock = threading.RLock()
        self._startup_retry_ran = False
        self._completed: dict[str, str] = {}

    def ingest_saved_recording(
        self,
        output_path: str | Path,
        *,
        metadata: dict[str, Any],
        diagnostic_dir: str | None,
        pending_id: str | None = None,
        material_id: str | None = None,
    ) -> IngestionResult:
        path = Path(output_path)
        pending_key = pending_id or uuid.uuid4().hex
        material_key = material_id or uuid.uuid4().hex
        existing = self.library_service.find_existing(item_id=material_key, file_path=path)
        if existing is not None:
            self._completed[pending_key] = existing.id
            return IngestionResult(True, True, already_indexed=True, pending_id=pending_key, material_id=existing.id)
        try:
            formal = self.library_service.add_recording(
                path,
                metadata=metadata,
                diagnostic_dir=diagnostic_dir,
                item_id=material_key,
            )
        except Exception as exc:
            formal = _failed_library_result(self.library_service, str(exc))
        if formal.ok:
            self._completed[pending_key] = material_key
            return IngestionResult(True, True, pending_id=pending_key, material_id=material_key)

        item = self._create_pending_item(
            path,
            metadata=metadata,
            diagnostic_dir=diagnostic_dir,
            pending_id=pending_key,
            material_id=material_key,
            error=str(formal.error),
        )
        persisted = self.pending_service.persist_with_fallback(item)
        if persisted.ok:
            return IngestionResult(
                True,
                False,
                pending_persisted=True,
                pending_id=pending_key,
                material_id=material_key,
                error_code="FORMAL_INDEX_WRITE_FAILED",
                error=str(formal.error),
            )
        logger.error("pending fallback save failed: pending_id=%s error=%s", pending_key, persisted.error)
        return IngestionResult(
            True,
            False,
            pending_persisted=False,
            pending_id=pending_key,
            material_id=material_key,
            error_code=persisted.error_code or "PENDING_FALLBACK_WRITE_FAILED",
            error=persisted.error or str(formal.error),
        )

    def retry(
        self,
        pending_id: str,
        *,
        current_save_dir: str | Path | None = None,
    ) -> IngestionResult:
        with self._lock:
            if pending_id in self._completed:
                return IngestionResult(
                    True,
                    True,
                    already_indexed=True,
                    pending_id=pending_id,
                    material_id=self._completed[pending_id],
                )
            loaded = self.pending_service.load(current_save_dir)
            if not loaded.ok:
                return IngestionResult(
                    True,
                    False,
                    error_code="PENDING_PRIMARY_READ_FAILED",
                    error=loaded.error,
                    pending_id=pending_id,
                )
            item = next((candidate for candidate in loaded.items if candidate.pending_id == pending_id), None)
            if item is None:
                return IngestionResult(True, False, error_code="PENDING_NOT_FOUND", pending_id=pending_id)
            path = Path(item.file_path)
            if not path.is_file():
                item.status = "missing"
                item.updated_at = _now()
                item.last_error_code = "VIDEO_MISSING"
                item.last_error_summary = "视频文件已移动或删除"
                self.pending_service.persist(item)
                return IngestionResult(
                    True,
                    False,
                    pending_persisted=True,
                    pending_id=item.pending_id,
                    material_id=item.material_id,
                    error_code="VIDEO_MISSING",
                    error=item.last_error_summary,
                )

            existing = self.library_service.find_existing(item_id=item.material_id, file_path=path)
            if existing is not None:
                self.pending_service.remove(item.pending_id, current_save_dir=current_save_dir)
                self._completed[item.pending_id] = existing.id
                return IngestionResult(
                    True,
                    True,
                    already_indexed=True,
                    pending_id=item.pending_id,
                    material_id=existing.id,
                )

            item.attempt_count += 1
            item.last_attempt_at = _now()
            metadata = {
                "mode": item.capture_mode,
                "audio_source": item.audio_source,
                "duration_sec": item.duration_seconds,
                "width": item.width,
                "height": item.height,
                "fps": item.fps,
            }
            try:
                formal = self.library_service.add_recording(
                    path,
                    metadata=metadata,
                    diagnostic_dir=item.diagnostics_dir,
                    item_id=item.material_id,
                )
            except Exception as exc:
                formal = _failed_library_result(self.library_service, str(exc))
            if not formal.ok:
                item.status = "retry_failed"
                item.updated_at = _now()
                item.last_error_code = "FORMAL_INDEX_WRITE_FAILED"
                item.last_error_summary = str(formal.error)
                self.pending_service.persist(item)
                logger.warning("pending manual retry failed: pending_id=%s error=%s", item.pending_id, formal.error)
                return IngestionResult(
                    True,
                    False,
                    pending_persisted=True,
                    pending_id=item.pending_id,
                    material_id=item.material_id,
                    error_code="FORMAL_INDEX_WRITE_FAILED",
                    error=str(formal.error),
                )

            cleanup = self.pending_service.remove(item.pending_id, current_save_dir=current_save_dir)
            self._completed[item.pending_id] = item.material_id
            if not cleanup.ok:
                logger.warning("pending cleanup failed: pending_id=%s error=%s", item.pending_id, cleanup.error)
            else:
                logger.info("pending manual retry succeeded: pending_id=%s", item.pending_id)
            return IngestionResult(
                True,
                True,
                pending_persisted=not cleanup.ok,
                pending_id=item.pending_id,
                material_id=item.material_id,
                error_code="PENDING_CLEANUP_FAILED" if not cleanup.ok else "",
                error=cleanup.error if not cleanup.ok else "",
            )

    def retry_startup(self, current_save_dir: str | Path) -> StartupRetrySummary:
        with self._lock:
            if self._startup_retry_ran:
                return StartupRetrySummary(already_ran=True)
            self._startup_retry_ran = True
        loaded = self.pending_service.load(current_save_dir)
        if not loaded.ok:
            logger.warning("pending startup retry summary: scanned=0 succeeded=0 failed=1 missing=0")
            return StartupRetrySummary(failed_count=1)
        succeeded = 0
        failed = 0
        missing = 0
        for item in loaded.items:
            result = self.retry(item.pending_id, current_save_dir=current_save_dir)
            if result.formal_indexed:
                succeeded += 1
            elif result.error_code == "VIDEO_MISSING":
                missing += 1
            else:
                failed += 1
        logger.info(
            "pending startup retry summary: scanned=%s succeeded=%s failed=%s missing=%s",
            len(loaded.items),
            succeeded,
            failed,
            missing,
        )
        return StartupRetrySummary(len(loaded.items), succeeded, failed, missing)

    @staticmethod
    def _create_pending_item(
        path: Path,
        *,
        metadata: dict[str, Any],
        diagnostic_dir: str | None,
        pending_id: str,
        material_id: str,
        error: str,
    ) -> PendingRecordingItem:
        now = _now()
        stat = path.stat() if path.exists() else None
        created_at = (
            datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds") if stat else now
        )
        return PendingRecordingItem(
            pending_id=pending_id,
            material_id=material_id,
            file_path=str(path),
            file_name=path.name,
            created_at=created_at,
            queued_at=now,
            updated_at=now,
            status="pending",
            attempt_count=1,
            capture_mode=str(metadata.get("mode") or "unknown"),
            audio_source=str(metadata.get("audio_source") or "unknown"),
            last_attempt_at=now,
            last_error_code="FORMAL_INDEX_WRITE_FAILED",
            last_error_summary=error,
            duration_seconds=_optional_float(metadata.get("duration_sec")),
            width=_optional_int(metadata.get("width")),
            height=_optional_int(metadata.get("height")),
            fps=_optional_float(metadata.get("fps")),
            file_size_bytes=stat.st_size if stat else None,
            diagnostics_dir=diagnostic_dir,
        )


def _failed_library_result(service: RecordingLibraryService, error: str):
    from utils.recording_library_store import LibraryWriteResult

    return LibraryWriteResult(False, service.library_path, error=error)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


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
