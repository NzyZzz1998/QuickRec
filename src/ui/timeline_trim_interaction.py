"""时间线裁剪手柄的瞬时交互状态。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from services.timeline_edit_service import TimelineEditCandidate
from utils.timeline_model import TimelineClip

TrimEdge = Literal["left", "right"]


@dataclass(frozen=True)
class TrimGesture:
    clip_id: str
    edge: TrimEdge
    timeline_start_us: int
    source_start_us: int
    source_end_us: int


class TimelineTrimInteraction:
    """计算手柄指针对应的源范围，不修改正式时间线。"""

    def __init__(self) -> None:
        self._gesture: TrimGesture | None = None
        self._candidate: TimelineEditCandidate | None = None

    @property
    def active(self) -> bool:
        return self._gesture is not None

    @property
    def clip_id(self) -> str | None:
        return self._gesture.clip_id if self._gesture is not None else None

    @property
    def edge(self) -> TrimEdge | None:
        return self._gesture.edge if self._gesture is not None else None

    @property
    def candidate(self) -> TimelineEditCandidate | None:
        return self._candidate

    def begin(self, clip: TimelineClip, *, edge: TrimEdge) -> None:
        if edge not in {"left", "right"}:
            raise ValueError(f"unsupported trim edge: {edge}")
        self._gesture = TrimGesture(
            clip_id=clip.clip_id,
            edge=edge,
            timeline_start_us=clip.timeline_start_us,
            source_start_us=clip.source_start_us,
            source_end_us=clip.source_start_us + clip.source_duration_us,
        )
        self._candidate = None

    def requested_source_range(self, pointer_time_us: int) -> tuple[int, int]:
        gesture = self._gesture
        if gesture is None:
            raise RuntimeError("trim interaction has not started")
        local_offset_us = int(pointer_time_us) - gesture.timeline_start_us
        if gesture.edge == "left":
            return (
                gesture.source_start_us + local_offset_us,
                gesture.source_end_us,
            )
        return (
            gesture.source_start_us,
            gesture.source_start_us + local_offset_us,
        )

    def set_candidate(self, candidate: TimelineEditCandidate | None) -> None:
        if candidate is not None and candidate.operation != "trim":
            raise ValueError("trim interaction only accepts trim candidates")
        self._candidate = candidate

    def finish(self) -> TimelineEditCandidate | None:
        candidate = self._candidate
        self._gesture = None
        self._candidate = None
        return candidate

    def cancel(self) -> None:
        self._gesture = None
        self._candidate = None
