"""素材库的纯内存查询能力。"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from utils.pending_recording_store import PendingRecordingItem
from utils.recording_library_store import MaterialItem

logger = logging.getLogger("QuickRec")

QUERY_ALL = "all"
DEFAULT_PAGE_SIZE = 50
SLOW_QUERY_MS = 100.0


@dataclass(frozen=True)
class MaterialQueryCriteria:
    keyword: str = ""
    status: str = QUERY_ALL
    mode: str = QUERY_ALL
    audio: str = QUERY_ALL
    time_range: str = QUERY_ALL
    sort_order: str = "created_desc"

    @property
    def normalized_keyword(self) -> str:
        return self.keyword.strip().casefold()

    @property
    def is_default(self) -> bool:
        return self == MaterialQueryCriteria()


@dataclass(frozen=True)
class MaterialQueryResult:
    pending_items: list[PendingRecordingItem]
    formal_items: list[MaterialItem]
    visible_formal_items: list[MaterialItem]
    pending_total: int
    pending_matched: int
    formal_total: int
    formal_matched: int
    source_total: int
    matched_total: int
    visible_formal_count: int
    has_more: bool
    elapsed_ms: float

    @classmethod
    def empty(cls) -> "MaterialQueryResult":
        return cls([], [], [], 0, 0, 0, 0, 0, 0, 0, False, 0.0)


class MaterialQueryEngine:
    """对完整正式素材与待入库集合执行只读查询。"""

    def execute(
        self,
        formal_items: list[MaterialItem],
        pending_items: list[PendingRecordingItem],
        criteria: MaterialQueryCriteria,
        *,
        visible_count: int = DEFAULT_PAGE_SIZE,
        now: datetime | None = None,
    ) -> MaterialQueryResult:
        started = time.perf_counter()
        local_now = _local_now(now)
        matching_formal = [
            item for item in formal_items if _matches(item, criteria, local_now, pending=False)
        ]
        matching_pending = [
            item for item in pending_items if _matches(item, criteria, local_now, pending=True)
        ]
        matching_formal = _sort_items(matching_formal, criteria.sort_order)
        matching_pending = _sort_items(matching_pending, criteria.sort_order)
        safe_visible_count = max(0, visible_count)
        visible_formal = matching_formal[:safe_visible_count]
        elapsed_ms = (time.perf_counter() - started) * 1000
        result = MaterialQueryResult(
            pending_items=matching_pending,
            formal_items=matching_formal,
            visible_formal_items=visible_formal,
            pending_total=len(pending_items),
            pending_matched=len(matching_pending),
            formal_total=len(formal_items),
            formal_matched=len(matching_formal),
            source_total=len(formal_items) + len(pending_items),
            matched_total=len(matching_formal) + len(matching_pending),
            visible_formal_count=len(visible_formal),
            has_more=len(visible_formal) < len(matching_formal),
            elapsed_ms=elapsed_ms,
        )
        if elapsed_ms > SLOW_QUERY_MS:
            logger.warning(
                "Material query slow: elapsed_ms=%.2f source_count=%d result_count=%d default=%s",
                elapsed_ms,
                result.source_total,
                result.matched_total,
                criteria.is_default,
            )
        return result


def _matches(
    item: MaterialItem | PendingRecordingItem,
    criteria: MaterialQueryCriteria,
    now: datetime,
    *,
    pending: bool,
) -> bool:
    keyword = criteria.normalized_keyword
    if keyword:
        file_name = item.file_name.casefold()
        file_path = item.file_path.casefold()
        if keyword not in file_name and keyword not in file_path:
            return False
    if criteria.status != QUERY_ALL and _status_value(item, pending=pending) != criteria.status:
        return False
    if criteria.mode != QUERY_ALL and _mode_value(item, pending=pending) != criteria.mode:
        return False
    if criteria.audio != QUERY_ALL and _audio_value(item.audio_source) != criteria.audio:
        return False
    return _matches_time(item.created_at, criteria.time_range, now)


def _status_value(item: MaterialItem | PendingRecordingItem, *, pending: bool) -> str:
    if not pending:
        status = str(getattr(item, "status", "") or "").casefold()
        if status in {"available", "missing", "metadata_incomplete"}:
            return status
        return "metadata_incomplete"
    pending_item = item
    status = str(getattr(pending_item, "status", "") or "").casefold()
    if status == "missing":
        return "missing"
    if status == "retry_failed":
        return "retry_failed"
    if _metadata_incomplete(pending_item):
        return "metadata_incomplete"
    return "pending"


def _metadata_incomplete(item: MaterialItem | PendingRecordingItem) -> bool:
    duration = getattr(item, "duration_sec", getattr(item, "duration_seconds", None))
    return any(
        value is None
        for value in (
            duration,
            getattr(item, "width", None),
            getattr(item, "height", None),
            getattr(item, "fps", None),
        )
    )


def _mode_value(item: MaterialItem | PendingRecordingItem, *, pending: bool) -> str:
    raw = getattr(item, "capture_mode", "unknown") if pending else getattr(item, "mode", "unknown")
    value = str(raw or "unknown").casefold()
    if value == "area":
        value = "region"
    return value if value in {"fullscreen", "region", "window"} else "unknown"


def _audio_value(raw: str) -> str:
    value = str(raw or "unknown").casefold()
    if value == "mic":
        value = "microphone"
    return value if value in {"none", "system", "microphone", "both"} else "unknown"


def _matches_time(created_at: str, time_range: str, now: datetime) -> bool:
    if time_range == QUERY_ALL:
        return True
    created = _parse_datetime(created_at, now)
    if created is None:
        return False
    if time_range == "today":
        return created >= now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = {"last_7_days": 7, "last_30_days": 30, "last_90_days": 90}.get(time_range)
    return days is not None and created >= now - timedelta(days=days)


def _local_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now().astimezone()
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value


def _parse_datetime(value: str, now: datetime) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=now.tzinfo)
    return parsed.astimezone(now.tzinfo)


def _sort_items[Material: (MaterialItem, PendingRecordingItem)](
    items: list[Material], sort_order: str
) -> list[Material]:
    return sorted(items, key=lambda item: _sort_key(item, sort_order))


def _sort_key(item: MaterialItem | PendingRecordingItem, sort_order: str) -> tuple[object, ...]:
    created = _parse_sort_time(item.created_at)
    created_missing = created is None
    created_timestamp = created.timestamp() if created is not None else 0.0
    stable_id = getattr(item, "id", getattr(item, "pending_id", ""))
    tie_breaker = (created_missing, -created_timestamp, str(stable_id))
    if sort_order == "created_asc":
        return (created_missing, created_timestamp, str(stable_id))
    if sort_order == "duration_desc":
        return _numeric_sort_key(_duration(item), descending=True) + tie_breaker
    if sort_order == "duration_asc":
        return _numeric_sort_key(_duration(item), descending=False) + tie_breaker
    if sort_order == "size_desc":
        return _numeric_sort_key(item.file_size_bytes, descending=True) + tie_breaker
    if sort_order == "size_asc":
        return _numeric_sort_key(item.file_size_bytes, descending=False) + tie_breaker
    return (created_missing, -created_timestamp, str(stable_id))


def _parse_sort_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def _duration(item: MaterialItem | PendingRecordingItem) -> float | None:
    if isinstance(item, PendingRecordingItem):
        return item.duration_seconds
    return item.duration_sec


def _numeric_sort_key(value: int | float | None, *, descending: bool) -> tuple[bool, float]:
    if value is None:
        return True, 0.0
    number = float(value)
    return False, -number if descending else number
