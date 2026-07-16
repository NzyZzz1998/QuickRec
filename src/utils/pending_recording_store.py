"""待入库录制的本地持久化。"""

import json
import logging
import os
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

PENDING_FILE_NAME = "pending-recordings.json"
PENDING_SCHEMA_VERSION = 1
DEFAULT_MAX_PENDING_ITEMS = 200
PENDING_MARKER_DIRECTORY = Path("QuickRecMetadata") / "Pending"
logger = logging.getLogger("QuickRec")


@dataclass
class PendingRecordingItem:
    pending_id: str
    material_id: str
    file_path: str
    file_name: str
    created_at: str
    queued_at: str
    updated_at: str
    status: str
    attempt_count: int
    capture_mode: str
    audio_source: str
    last_attempt_at: str | None = None
    last_error_code: str | None = None
    last_error_summary: str | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    file_size_bytes: int | None = None
    diagnostics_dir: str | None = None
    source: str = "recording_auto_ingest"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PendingRecordingItem":
        required = (
            "pending_id",
            "material_id",
            "file_path",
            "created_at",
            "queued_at",
            "updated_at",
        )
        if any(not payload.get(field_name) for field_name in required):
            raise ValueError("pending item is missing required identity fields")
        path = Path(str(payload["file_path"]))
        return cls(
            pending_id=str(payload["pending_id"]),
            material_id=str(payload["material_id"]),
            file_path=str(path),
            file_name=str(payload.get("file_name") or path.name),
            created_at=str(payload["created_at"]),
            queued_at=str(payload["queued_at"]),
            updated_at=str(payload["updated_at"]),
            status=str(payload.get("status") or "pending"),
            attempt_count=max(0, _optional_int(payload.get("attempt_count")) or 0),
            capture_mode=str(payload.get("capture_mode") or "unknown"),
            audio_source=str(payload.get("audio_source") or "unknown"),
            last_attempt_at=_optional_str(payload.get("last_attempt_at")),
            last_error_code=_optional_str(payload.get("last_error_code")),
            last_error_summary=_optional_str(payload.get("last_error_summary")),
            duration_seconds=_optional_float(payload.get("duration_seconds")),
            width=_optional_int(payload.get("width")),
            height=_optional_int(payload.get("height")),
            fps=_optional_float(payload.get("fps")),
            file_size_bytes=_optional_int(payload.get("file_size_bytes")),
            diagnostics_dir=_optional_str(payload.get("diagnostics_dir")),
            source=str(payload.get("source") or "recording_auto_ingest"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PendingLoadResult:
    ok: bool
    path: Path
    items: list[PendingRecordingItem] = field(default_factory=list)
    error: str = ""
    corrupt_path: Path | None = None
    skipped_items: int = 0


@dataclass(frozen=True)
class PendingWriteResult:
    ok: bool
    path: Path
    items: list[PendingRecordingItem] = field(default_factory=list)
    error: str = ""
    evicted_ids: tuple[str, ...] = ()


def resolve_pending_file(appdata_dir: str | Path | None = None) -> Path:
    root = Path(appdata_dir) if appdata_dir is not None else Path(os.getenv("APPDATA") or Path.home())
    return root / "QuickRec" / PENDING_FILE_NAME


def resolve_fallback_marker(video_path: str | Path, pending_id: str) -> Path:
    return Path(video_path).parent / PENDING_MARKER_DIRECTORY / f"{pending_id}.json"


def load_pending(path: str | Path) -> PendingLoadResult:
    target = Path(path)
    if not target.exists():
        return PendingLoadResult(True, target)
    try:
        payload = json.loads(target.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("pending root must be an object")
        if payload.get("schema_version") != PENDING_SCHEMA_VERSION:
            raise ValueError(f"unsupported pending schema: {payload.get('schema_version')}")
        raw_items = payload.get("items", [])
        if not isinstance(raw_items, list):
            raise ValueError("pending items must be an array")
        items: list[PendingRecordingItem] = []
        skipped = 0
        for raw_item in raw_items:
            try:
                if not isinstance(raw_item, dict):
                    raise ValueError("pending item must be an object")
                items.append(PendingRecordingItem.from_dict(raw_item))
            except (TypeError, ValueError):
                skipped += 1
        return PendingLoadResult(True, target, _sort_pending(items), skipped_items=skipped)
    except Exception as exc:
        corrupt_path = _archive_corrupt_file(target)
        logger.error("pending recording load failed: path=%s error=%s", target, exc)
        return PendingLoadResult(False, target, error=str(exc), corrupt_path=corrupt_path)


def save_pending(
    path: str | Path,
    items: list[PendingRecordingItem],
    *,
    max_items: int = DEFAULT_MAX_PENDING_ITEMS,
) -> PendingWriteResult:
    target = Path(path)
    sorted_items = _sort_pending(items)
    kept_items = sorted_items[:max_items]
    evicted_ids = tuple(item.pending_id for item in sorted_items[max_items:])
    payload = {
        "schema_version": PENDING_SCHEMA_VERSION,
        "max_items": max_items,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "items": [item.to_dict() for item in kept_items],
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(target, payload)
    except Exception as exc:
        logger.error("pending primary save failed: error=%s", exc)
        return PendingWriteResult(False, target, kept_items, str(exc), evicted_ids)
    for pending_id in evicted_ids:
        logger.warning("pending item evicted: pending_id=%s reason=capacity", pending_id)
    return PendingWriteResult(True, target, kept_items, evicted_ids=evicted_ids)


def save_fallback_marker(item: PendingRecordingItem) -> PendingWriteResult:
    target = resolve_fallback_marker(item.file_path, item.pending_id)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(target, item.to_dict())
    except Exception as exc:
        logger.error("pending fallback save failed: pending_id=%s error=%s", item.pending_id, exc)
        return PendingWriteResult(False, target, [item], str(exc))
    logger.info("pending fallback marker saved: pending_id=%s", item.pending_id)
    return PendingWriteResult(True, target, [item])


def load_fallback_markers(directory: str | Path) -> PendingLoadResult:
    marker_dir = Path(directory) / PENDING_MARKER_DIRECTORY
    if not marker_dir.exists():
        return PendingLoadResult(True, marker_dir)
    items: list[PendingRecordingItem] = []
    skipped = 0
    for marker_path in sorted(marker_dir.glob("*.json")):
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict):
                raise ValueError("pending marker must be an object")
            items.append(PendingRecordingItem.from_dict(payload))
        except Exception as exc:
            skipped += 1
            logger.warning("pending marker skipped: path=%s error=%s", marker_path, exc)
    return PendingLoadResult(True, marker_dir, _sort_pending(items), skipped_items=skipped)


def remove_fallback_marker(item: PendingRecordingItem) -> None:
    resolve_fallback_marker(item.file_path, item.pending_id).unlink(missing_ok=True)


def _sort_pending(items: list[PendingRecordingItem]) -> list[PendingRecordingItem]:
    return sorted(items, key=lambda item: (item.queued_at, item.pending_id), reverse=True)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def _archive_corrupt_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    corrupt_path = path.with_name(f"{path.stem}.corrupt-{timestamp}{path.suffix}")
    shutil.copy2(path, corrupt_path)
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
