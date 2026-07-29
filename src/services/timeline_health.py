"""时间线片段可用性与关联完整性的只读评估。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from utils.project_store import ProjectFile
from utils.timeline_model import Timeline, TimelineClip


class MaterialAvailability(Protocol):
    material_id: str
    file_exists: bool


@dataclass(frozen=True)
class TimelineClipHealth:
    clip_id: str
    status: str
    reason: str = ""

    @property
    def range_editable(self) -> bool:
        return self.status == "available"

    @property
    def move_editable(self) -> bool:
        return self.status != "link_error"

    @property
    def delete_editable(self) -> bool:
        return self.status != "link_error"


def assess_timeline_clip_health(
    timeline: Timeline,
    project: ProjectFile,
    materials: Iterable[MaterialAvailability] | None = None,
) -> dict[str, TimelineClipHealth]:
    """评估每个片段；不校验或修改时间线，允许诊断损坏关联组。"""
    availability: dict[str, bool] = {}
    for item in materials or ():
        material_id = str(getattr(item, "material_id", "") or "")
        file_exists = getattr(item, "file_exists", None)
        if material_id and file_exists is not None:
            availability[material_id] = bool(file_exists)
    for item in project.materials:
        availability.setdefault(
            item.material_id,
            bool(item.last_known_path and Path(item.last_known_path).is_file()),
        )

    broken_groups = _broken_link_groups(timeline)
    result: dict[str, TimelineClipHealth] = {}
    for clip in timeline.clips:
        if clip.link_group_id in broken_groups:
            result[clip.clip_id] = TimelineClipHealth(
                clip.clip_id,
                "link_error",
                "关联组成员、类型、素材或范围不一致",
            )
        elif not availability.get(clip.material_id, False):
            result[clip.clip_id] = TimelineClipHealth(
                clip.clip_id,
                "missing",
                "素材文件已移动或删除",
            )
        else:
            result[clip.clip_id] = TimelineClipHealth(
                clip.clip_id,
                "available",
            )
    return result


def summarize_timeline_health(
    health: dict[str, TimelineClipHealth],
) -> dict[str, int]:
    counts = {"available": 0, "missing": 0, "link_error": 0}
    for item in health.values():
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def _broken_link_groups(timeline: Timeline) -> set[str]:
    tracks = {item.track_id: item for item in timeline.tracks}
    groups: dict[str, list[TimelineClip]] = {}
    for clip in timeline.clips:
        if clip.link_group_id:
            groups.setdefault(clip.link_group_id, []).append(clip)

    broken: set[str] = set()
    for group_id, members in groups.items():
        kinds = [
            tracks[item.track_id].kind
            for item in members
            if item.track_id in tracks
        ]
        if (
            len(members) != 2
            or len(kinds) != 2
            or kinds.count("video") != 1
            or kinds.count("audio") != 1
        ):
            broken.add(group_id)
            continue
        first, second = members
        if (
            first.material_id != second.material_id
            or first.timeline_start_us != second.timeline_start_us
            or first.timeline_duration_us != second.timeline_duration_us
            or first.source_start_us != second.source_start_us
            or first.source_duration_us != second.source_duration_us
        ):
            broken.add(group_id)
    return broken
