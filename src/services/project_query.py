"""项目列表、最近项目与文件健康状态查询。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from utils.project_store import ProjectIndexEntry, load_project


@dataclass(frozen=True)
class ProjectQueryCriteria:
    keyword: str = ""
    scope: str = "active"
    limit: int | None = None


@dataclass(frozen=True)
class ProjectQueryItem:
    entry: ProjectIndexEntry
    health: str
    material_count: int | None = None


@dataclass(frozen=True)
class ProjectQueryResult:
    items: list[ProjectQueryItem] = field(default_factory=list)
    total_count: int = 0


class ProjectQueryEngine:
    def query(
        self,
        entries: list[ProjectIndexEntry],
        criteria: ProjectQueryCriteria,
    ) -> ProjectQueryResult:
        keyword = criteria.keyword.strip().casefold()
        selected: list[ProjectIndexEntry] = []
        for entry in entries:
            if criteria.scope == "active" and entry.archived_at:
                continue
            if criteria.scope == "archived" and not entry.archived_at:
                continue
            if criteria.scope not in {"active", "archived", "all"}:
                continue
            if keyword and keyword not in entry.name.casefold():
                loaded = load_project(entry.file_path)
                material_match = (
                    loaded.ok
                    and loaded.project is not None
                    and any(
                        keyword in material.file_name.casefold()
                        for material in loaded.project.materials
                    )
                )
                if not material_match:
                    continue
            selected.append(entry)
        selected.sort(
            key=lambda entry: (
                entry.last_opened_at or entry.updated_at,
                entry.project_id,
            ),
            reverse=True,
        )
        total = len(selected)
        if criteria.limit is not None:
            selected = selected[: max(0, criteria.limit)]
        return ProjectQueryResult(
            [self._item(entry) for entry in selected],
            total,
        )

    def recent(
        self,
        entries: list[ProjectIndexEntry],
        *,
        limit: int = 8,
    ) -> list[ProjectQueryItem]:
        return self.query(
            entries,
            ProjectQueryCriteria(scope="all", limit=limit),
        ).items

    @staticmethod
    def _item(entry: ProjectIndexEntry) -> ProjectQueryItem:
        loaded = load_project(entry.file_path)
        if not loaded.ok or loaded.project is None:
            return ProjectQueryItem(entry, loaded.status)
        path = Path(entry.file_path)
        health = "available" if os.access(path, os.W_OK) else "read_only"
        return ProjectQueryItem(entry, health, len(loaded.project.materials))
