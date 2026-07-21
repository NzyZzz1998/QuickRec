"""素材查询条件与分页的进程内会话状态。"""

import logging
from dataclasses import dataclass, replace
from datetime import datetime

from services.material_query import (
    DEFAULT_PAGE_SIZE,
    MaterialQueryCriteria,
    MaterialQueryEngine,
    MaterialQueryResult,
)
from utils.pending_recording_store import PendingRecordingItem
from utils.recording_library_store import MaterialItem

logger = logging.getLogger("QuickRec")


@dataclass(frozen=True)
class MaterialQueryOutcome:
    ok: bool
    result: MaterialQueryResult
    error_code: str = ""


class MaterialQuerySession:
    def __init__(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        engine: MaterialQueryEngine | None = None,
    ) -> None:
        self.page_size = max(1, page_size)
        self.visible_count = self.page_size
        self.criteria = MaterialQueryCriteria()
        self.engine = engine or MaterialQueryEngine()
        self._last_successful_result: MaterialQueryResult | None = None

    def update(self, **changes: str) -> None:
        updated = replace(self.criteria, **changes)
        if updated != self.criteria:
            self.criteria = updated
            self.visible_count = self.page_size

    def reset(self) -> None:
        self.criteria = MaterialQueryCriteria()
        self.visible_count = self.page_size

    def load_more(self, formal_matched: int) -> None:
        self.visible_count = min(max(0, formal_matched), self.visible_count + self.page_size)

    def reset_page(self) -> None:
        self.visible_count = self.page_size

    def execute(
        self,
        formal_items: list[MaterialItem],
        pending_items: list[PendingRecordingItem],
        *,
        now: datetime | None = None,
    ) -> MaterialQueryOutcome:
        try:
            result = self.engine.execute(
                formal_items,
                pending_items,
                self.criteria,
                visible_count=self.visible_count,
                now=now,
            )
        except Exception:
            logger.error("Material query failed: code=MATERIAL_QUERY_FAILED")
            fallback = self._last_successful_result or MaterialQueryResult.empty()
            return MaterialQueryOutcome(False, fallback, "MATERIAL_QUERY_FAILED")
        self._last_successful_result = result
        return MaterialQueryOutcome(True, result)
