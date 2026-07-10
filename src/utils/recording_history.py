import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_MAX_ITEMS = 50
METADATA_DIR_NAME = "QuickRecMetadata"
HISTORY_FILE_NAME = "recordings.json"
STATUS_AVAILABLE = "available"
STATUS_MISSING = "missing"

logger = logging.getLogger("QuickRec")


@dataclass(frozen=True)
class RecordingHistoryItem:
    id: str
    file_path: str
    file_name: str
    directory: str
    mode: str
    audio_source: str
    created_at: str
    duration_sec: float | None = None
    file_size_bytes: int | None = None
    status: str = STATUS_AVAILABLE
    diagnostic_dir: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecordingHistoryItem":
        path = str(data.get("file_path") or "")
        return cls(
            id=str(data.get("id") or _new_item_id(data.get("mode"))),
            file_path=path,
            file_name=str(data.get("file_name") or Path(path).name),
            directory=str(data.get("directory") or str(Path(path).parent)),
            mode=str(data.get("mode") or "unknown"),
            audio_source=str(data.get("audio_source") or "unknown"),
            created_at=str(data.get("created_at") or _now_iso()),
            duration_sec=_optional_float(data.get("duration_sec")),
            file_size_bytes=_optional_int(data.get("file_size_bytes")),
            status=str(data.get("status") or STATUS_AVAILABLE),
            diagnostic_dir=_optional_str(data.get("diagnostic_dir")),
        ).with_refreshed_status()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "directory": self.directory,
            "mode": self.mode,
            "audio_source": self.audio_source,
            "created_at": self.created_at,
            "duration_sec": self.duration_sec,
            "file_size_bytes": self.file_size_bytes,
            "status": self.status,
            "diagnostic_dir": self.diagnostic_dir,
        }

    def with_refreshed_status(self) -> "RecordingHistoryItem":
        status = STATUS_AVAILABLE if self.file_path and Path(self.file_path).exists() else STATUS_MISSING
        if status == STATUS_MISSING and self.status != STATUS_MISSING:
            logger.info(f"recording file missing: {self.file_path}")
        return RecordingHistoryItem(
            id=self.id,
            file_path=self.file_path,
            file_name=self.file_name,
            directory=self.directory,
            mode=self.mode,
            audio_source=self.audio_source,
            created_at=self.created_at,
            duration_sec=self.duration_sec,
            file_size_bytes=self.file_size_bytes,
            status=status,
            diagnostic_dir=self.diagnostic_dir,
        )


@dataclass(frozen=True)
class RecordingHistoryLoadResult:
    ok: bool
    path: Path
    items: list[RecordingHistoryItem] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class RecordingHistoryWriteResult:
    ok: bool
    path: Path
    items: list[RecordingHistoryItem] = field(default_factory=list)
    error: str = ""


def resolve_history_file(config_or_save_path: Any) -> Path:
    save_path = _resolve_save_path(config_or_save_path)
    return save_path / METADATA_DIR_NAME / HISTORY_FILE_NAME


def build_history_item(
    file_path: str | Path,
    mode: str,
    audio_source: str,
    diagnostic_dir: str | Path | None = None,
    duration_sec: float | None = None,
    created_at: datetime | None = None,
) -> RecordingHistoryItem:
    path = Path(file_path)
    created = (created_at or datetime.now().astimezone()).isoformat(timespec="seconds")
    return RecordingHistoryItem(
        id=_new_item_id(mode, created_at=created),
        file_path=str(path),
        file_name=path.name,
        directory=str(path.parent),
        mode=_string_value(mode),
        audio_source=_string_value(audio_source),
        created_at=created,
        duration_sec=duration_sec,
        file_size_bytes=path.stat().st_size if path.exists() else None,
        status=STATUS_AVAILABLE if path.exists() else STATUS_MISSING,
        diagnostic_dir=str(diagnostic_dir) if diagnostic_dir else None,
    )


def load_history(config_or_save_path: Any) -> RecordingHistoryLoadResult:
    path = resolve_history_file(config_or_save_path)
    if not path.exists():
        logger.info(f"recording history loaded: {path} items=0")
        return RecordingHistoryLoadResult(True, path, [])
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        raw_items = payload.get("items", []) if isinstance(payload, dict) else []
        items = [RecordingHistoryItem.from_dict(item) for item in raw_items if isinstance(item, dict)]
        logger.info(f"recording history loaded: {path} items={len(items)}")
        return RecordingHistoryLoadResult(True, path, items)
    except Exception as exc:
        logger.warning(f"recording history load failed: {exc}")
        return RecordingHistoryLoadResult(False, path, [], str(exc))


def save_history(
    config_or_save_path: Any,
    items: list[RecordingHistoryItem],
    max_items: int = DEFAULT_MAX_ITEMS,
) -> RecordingHistoryWriteResult:
    path = resolve_history_file(config_or_save_path)
    normalized = sorted(items, key=lambda item: item.created_at, reverse=True)
    pruned = normalized[:max_items]
    if len(normalized) > len(pruned):
        logger.info(f"recording history pruned: before={len(normalized)} after={len(pruned)}")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "max_items": max_items,
        "items": [item.with_refreshed_status().to_dict() for item in pruned],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(path, payload)
    except Exception as exc:
        logger.warning(f"recording history save failed: {exc}")
        return RecordingHistoryWriteResult(False, path, pruned, str(exc))

    logger.info(f"recording history saved: {path} items={len(pruned)}")
    return RecordingHistoryWriteResult(True, path, pruned)


def add_history_item(
    config_or_save_path: Any,
    item: RecordingHistoryItem,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> RecordingHistoryWriteResult:
    loaded = load_history(config_or_save_path)
    items = [item] + [old_item for old_item in loaded.items if old_item.id != item.id]
    return save_history(config_or_save_path, items, max_items=max_items)


def remove_history_item(config_or_save_path: Any, item_id: str) -> RecordingHistoryWriteResult:
    loaded = load_history(config_or_save_path)
    if not loaded.ok:
        return RecordingHistoryWriteResult(False, loaded.path, [], loaded.error)
    items = [item for item in loaded.items if item.id != item_id]
    result = save_history(config_or_save_path, items)
    if result.ok:
        logger.info(f"recording history item removed: {item_id}")
    return result


def open_recording_file(file_path: str | Path) -> bool:
    try:
        os.startfile(str(file_path))
        return True
    except Exception as exc:
        logger.warning(f"open recording file failed: {exc}")
        return False


def open_recording_directory(file_path: str | Path) -> bool:
    try:
        directory = Path(file_path).parent
        os.startfile(str(directory))
        return True
    except Exception as exc:
        logger.warning(f"open recording directory failed: {exc}")
        return False


def _resolve_save_path(config_or_save_path: Any) -> Path:
    if isinstance(config_or_save_path, Path):
        return config_or_save_path
    if isinstance(config_or_save_path, str):
        return Path(config_or_save_path)
    if hasattr(config_or_save_path, "get"):
        return Path(config_or_save_path.get("save_path"))
    return Path(str(config_or_save_path))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _new_item_id(mode: Any = "recording", created_at: str | None = None) -> str:
    timestamp = (created_at or _now_iso()).replace(":", "").replace("-", "").replace("+", "_").replace("T", "_")
    return f"{timestamp}_{_string_value(mode)}_{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _string_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value or "unknown")


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
