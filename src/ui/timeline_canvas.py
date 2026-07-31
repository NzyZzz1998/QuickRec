"""多轨时间线的坐标换算、吸附、绘制与拖动候选。"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, replace

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QWidget

from services.project_editing_profile import is_supported_editing_fps
from services.timeline_drag_transaction import TimelineDragCandidate
from services.timeline_edit_service import TimelineEditCandidate
from services.timeline_frame_time import (
    format_frame_time,
    frame_to_microseconds,
)
from ui.timeline_drag_interaction import TimelineDragInteraction
from ui.timeline_trim_interaction import TimelineTrimInteraction, TrimEdge
from utils.timeline_model import Timeline, TimelineClip, TimelineTrack
from utils.timeline_view import (
    DEFAULT_TIMELINE_PIXELS_PER_SECOND,
    normalize_timeline_zoom,
)


@dataclass(frozen=True)
class TimelineScale:
    pixels_per_second: float = DEFAULT_TIMELINE_PIXELS_PER_SECOND
    origin_us: int = 0
    track_header_width: int = 148

    def normalized(self) -> TimelineScale:
        return replace(
            self,
            pixels_per_second=(
                DEFAULT_TIMELINE_PIXELS_PER_SECOND
                * normalize_timeline_zoom(
                    float(self.pixels_per_second)
                    / DEFAULT_TIMELINE_PIXELS_PER_SECOND
                )
            ),
            origin_us=max(0, int(self.origin_us)),
            track_header_width=max(96, int(self.track_header_width)),
        )

    def time_to_x(self, time_us: int) -> float:
        return self.track_header_width + (
            (int(time_us) - self.origin_us)
            / 1_000_000
            * self.pixels_per_second
        )

    def x_to_time(self, x: float) -> int:
        return max(
            0,
            round(
                self.origin_us
                + (float(x) - self.track_header_width)
                / self.pixels_per_second
                * 1_000_000
            ),
        )

    def zoom_at(self, x: float, factor: float) -> TimelineScale:
        anchor_us = self.x_to_time(x)
        new_pixels = (
            DEFAULT_TIMELINE_PIXELS_PER_SECOND
            * normalize_timeline_zoom(
                self.pixels_per_second
                * float(factor)
                / DEFAULT_TIMELINE_PIXELS_PER_SECOND
            )
        )
        origin = round(
            anchor_us
            - (float(x) - self.track_header_width)
            / new_pixels
            * 1_000_000
        )
        return TimelineScale(
            new_pixels,
            max(0, origin),
            self.track_header_width,
        )


def snap_time_us(
    value_us: int,
    *,
    candidates: list[int] | tuple[int, ...],
    grid_us: int,
    tolerance_us: int,
    enabled: bool = True,
) -> int:
    value = max(0, int(value_us))
    if not enabled:
        return value
    options = [max(0, int(item)) for item in candidates]
    if grid_us > 0:
        options.append(round(value / grid_us) * grid_us)
    nearest = min(options, key=lambda item: abs(item - value), default=value)
    return nearest if abs(nearest - value) <= max(0, tolerance_us) else value


class TimelineCanvas(QWidget):
    """轻量自绘轨道画布；拖动期间不修改业务模型。"""

    MATERIAL_MIME_TYPE = "application/x-quickrec-timeline-material"

    clip_selected = pyqtSignal(str, str)
    track_selected = pyqtSignal(str)
    playhead_requested = pyqtSignal(int)
    clip_move_requested = pyqtSignal(str, int, str)
    clip_trim_preview_requested = pyqtSignal(str, int, int)
    clip_trim_commit_requested = pyqtSignal(object)
    clip_context_requested = pyqtSignal(str, object)
    track_lock_requested = pyqtSignal(str, bool)
    material_drop_requested = pyqtSignal(str, bool, int, str)
    material_drop_commit_requested = pyqtSignal(object)
    invalid_drop = pyqtSignal(str)
    zoom_changed = pyqtSignal(float, int)

    ruler_height = 32
    track_height = 54
    track_header_width = 148

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("timelineCanvas")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)
        self._timeline = Timeline("empty", [])
        self._editing_fps = 30
        self._scale = TimelineScale(
            track_header_width=self.track_header_width
        )
        self._playhead_us = 0
        self._selected_clip_id: str | None = None
        self._selected_track_id: str | None = None
        self._drag_clip_id: str | None = None
        self._drag_offset_us = 0
        self._drag_candidate: tuple[int, str, bool, str] | None = None
        self._legacy_material_drop_candidate: tuple[
            int,
            str,
            bool,
            str,
        ] | None = None
        self._material_drop_candidate: TimelineDragCandidate | None = None
        self._material_drop_planner: (
            Callable[
                [
                    dict[str, object],
                    int,
                    str | None,
                    bool,
                    str,
                ],
                TimelineDragCandidate,
            ]
            | None
        ) = None
        self._material_drop_interaction = TimelineDragInteraction()
        self._trim_interaction = TimelineTrimInteraction()
        self._editing_enabled = True
        self._clip_statuses: dict[str, str] = {}
        self._refresh_size()

    @property
    def track_count(self) -> int:
        return len(self._timeline.tracks)

    @property
    def clip_count(self) -> int:
        return len(self._timeline.clips)

    @property
    def scale(self) -> TimelineScale:
        return self._scale

    @property
    def editing_fps(self) -> int:
        return self._editing_fps

    @property
    def trim_active(self) -> bool:
        return self._trim_interaction.active

    @property
    def material_drop_candidate(self) -> TimelineDragCandidate | None:
        return self._material_drop_candidate

    def set_material_drop_planner(
        self,
        planner: Callable[
            [dict[str, object], int, str | None, bool, str],
            TimelineDragCandidate,
        ]
        | None,
    ) -> None:
        self.cancel_material_drop()
        self._material_drop_planner = planner

    def begin_material_drop(self, payload: dict[str, object]) -> bool:
        material_id = str(payload.get("material_id", "")).strip()
        if not material_id:
            return False
        self._material_drop_interaction.begin(
            material_id=material_id,
            has_video=bool(payload.get("has_video", True)),
            has_audio=bool(payload.get("has_audio", False)),
            origin="project_materials",
        )
        self._material_drop_candidate = None
        self._legacy_material_drop_candidate = None
        self.update()
        return True

    def preview_material_drop(
        self,
        payload: dict[str, object],
        *,
        x: float,
        y: float,
        snap_enabled: bool,
    ) -> TimelineDragCandidate | None:
        planner = self._material_drop_planner
        if planner is None:
            return None
        material_id = str(payload.get("material_id", "")).strip()
        context = self._material_drop_interaction.context
        if (
            context is None
            or context.material_id != material_id
            or context.has_video != bool(payload.get("has_video", True))
            or context.has_audio != bool(payload.get("has_audio", False))
        ):
            if not self.begin_material_drop(payload):
                return None
            context = self._material_drop_interaction.context
        assert context is not None
        raw_start_us = self._scale.x_to_time(x)
        track = self._track_at(y)
        if float(x) < self.track_header_width:
            candidate = TimelineDragCandidate.invalid(
                transaction_id=context.transaction_id,
                material_id=context.material_id,
                raw_start_us=raw_start_us,
                start_us=raw_start_us,
                conflict_code="outside_timeline",
                conflict_reason="请把素材拖到时间线内容区域",
                has_video=context.has_video,
                has_audio=context.has_audio,
            )
        else:
            candidate = planner(
                payload,
                raw_start_us,
                track.track_id if track is not None else None,
                bool(snap_enabled),
                context.transaction_id,
            )
        if not self._material_drop_interaction.update(candidate):
            return None
        self._material_drop_candidate = candidate
        self.update()
        return candidate

    def commit_material_drop_preview(self) -> bool:
        candidate = self._material_drop_interaction.finish()
        self._material_drop_candidate = None
        self._legacy_material_drop_candidate = None
        self.update()
        if candidate is None:
            return False
        if not candidate.valid:
            self.invalid_drop.emit(_drop_conflict_message(candidate))
            return False
        self.material_drop_commit_requested.emit(candidate)
        return True

    def cancel_material_drop(self) -> bool:
        active = self._material_drop_interaction.cancel()
        had_candidate = (
            self._material_drop_candidate is not None
            or self._legacy_material_drop_candidate is not None
        )
        self._material_drop_candidate = None
        self._legacy_material_drop_candidate = None
        if active or had_candidate:
            self.update()
        return active or had_candidate

    def material_drop_summary(self) -> str:
        candidate = self._material_drop_candidate
        if candidate is None:
            return ""
        if not candidate.valid:
            return _drop_conflict_message(candidate)
        targets: list[str] = []
        if candidate.video_track_id:
            track = self._track_by_id(candidate.video_track_id)
            targets.append(track.name if track is not None else "新视频轨")
        if candidate.audio_track_id:
            track = self._track_by_id(candidate.audio_track_id)
            targets.append(track.name if track is not None else "新音频轨")
        details = [
            format_frame_time(candidate.start_us, self._editing_fps),
            " + ".join(targets) or "自动选择兼容轨道",
        ]
        if candidate.has_video and candidate.has_audio:
            details.append("关联音视频")
        details.extend(
            f"自动新建{'视频轨' if kind == 'video' else '音频轨'}"
            for kind in candidate.auto_track_kinds
        )
        snap_label = {
            "playhead": "吸附播放头",
            "clip_start": "吸附片段起点",
            "clip_end": "吸附片段终点",
            "frame": "吸附帧边界",
        }.get(candidate.snap_source)
        if snap_label:
            details.append(snap_label)
        return " · ".join(details)

    def set_timeline(self, timeline: Timeline) -> None:
        self.cancel_trim()
        self.cancel_material_drop()
        self._timeline = copy.deepcopy(timeline)
        valid_clip_ids = {item.clip_id for item in timeline.clips}
        self._clip_statuses = {
            clip_id: status
            for clip_id, status in self._clip_statuses.items()
            if clip_id in valid_clip_ids
        }
        valid_track_ids = {item.track_id for item in timeline.tracks}
        if self._selected_clip_id not in valid_clip_ids:
            self._selected_clip_id = None
        if self._selected_track_id not in valid_track_ids:
            self._selected_track_id = (
                self._ordered_tracks()[0].track_id
                if timeline.tracks
                else None
            )
        self._refresh_size()
        self.update()

    def set_clip_statuses(self, statuses: dict[str, str]) -> None:
        valid_ids = {item.clip_id for item in self._timeline.clips}
        self._clip_statuses = {
            str(clip_id): str(status)
            for clip_id, status in statuses.items()
            if clip_id in valid_ids and status != "available"
        }
        if (
            self._trim_interaction.clip_id is not None
            and self._clip_statuses.get(self._trim_interaction.clip_id)
            in {"missing", "link_error"}
        ):
            self.cancel_trim()
        self.update()

    def clip_status(self, clip_id: str) -> str:
        return self._clip_statuses.get(str(clip_id), "available")

    def set_playhead(self, value_us: int) -> None:
        self._playhead_us = max(0, int(value_us))
        self.update()

    def set_editing_fps(self, editing_fps: int) -> None:
        if not is_supported_editing_fps(editing_fps):
            raise ValueError("editing_fps must be 30, 60, or 120")
        self._editing_fps = editing_fps
        self.update()

    def ruler_tick_spec(self) -> tuple[int, int]:
        pixels_per_frame = (
            self._scale.pixels_per_second / self._editing_fps
        )
        minor = _nice_frame_step(max(1, _ceil_ratio(2.0, pixels_per_frame)))
        major = _nice_frame_step(
            max(minor, _ceil_ratio(96.0, pixels_per_frame))
        )
        if major % minor:
            major = ((major + minor - 1) // minor) * minor
        return minor, major

    def set_editing_enabled(self, enabled: bool) -> None:
        self._editing_enabled = bool(enabled)
        if not self._editing_enabled:
            self._drag_clip_id = None
            self._drag_candidate = None
            self.cancel_material_drop()
            self.cancel_trim()
        self.update()

    def set_trim_candidate(
        self,
        candidate: TimelineEditCandidate | None,
    ) -> None:
        self._trim_interaction.set_candidate(candidate)
        self.update()

    def cancel_trim(self) -> None:
        if (
            not self._trim_interaction.active
            and self._trim_interaction.candidate is None
        ):
            return
        self._trim_interaction.cancel()
        self.unsetCursor()
        self.update()

    def set_zoom(self, zoom: float, *, anchor_x: float | None = None) -> None:
        target = normalize_timeline_zoom(zoom)
        current = (
            self._scale.pixels_per_second
            / DEFAULT_TIMELINE_PIXELS_PER_SECOND
        )
        if current <= 0:
            current = 1.0
        x = (
            float(anchor_x)
            if anchor_x is not None
            else self.track_header_width + max(0, self.width() - self.track_header_width) / 2
        )
        self._scale = self._scale.zoom_at(x, target / current)
        self._refresh_size()
        self.zoom_changed.emit(target, self._scale.origin_us)
        self.update()

    def set_origin(self, origin_us: int) -> None:
        self._scale = replace(
            self._scale,
            origin_us=max(0, int(origin_us)),
        )
        self.update()

    def select_clip(self, clip_id: str | None) -> None:
        self._selected_clip_id = clip_id
        clip = self._clip_by_id(clip_id)
        if clip is not None:
            self._selected_track_id = clip.track_id
        self.update()

    def select_track(self, track_id: str | None) -> None:
        self._selected_track_id = track_id
        self.update()

    def selected_track_id(self) -> str | None:
        return self._selected_track_id

    def selected_clip_id(self) -> str | None:
        return self._selected_clip_id

    def clip_rects(self) -> dict[str, QRectF]:
        return self._clip_rects_for(self._timeline)

    def trim_handle_rects(self) -> dict[str, tuple[QRectF, QRectF]]:
        if self._selected_clip_id is None:
            return {}
        if self.clip_status(self._selected_clip_id) in {
            "missing",
            "link_error",
        }:
            return {}
        rect = self.clip_rects().get(self._selected_clip_id)
        if rect is None:
            return {}
        width = 8.0
        return {
            self._selected_clip_id: (
                QRectF(rect.left() - width / 2, rect.top(), width, rect.height()),
                QRectF(rect.right() - width / 2, rect.top(), width, rect.height()),
            )
        }

    def track_lock_rects(self) -> dict[str, QRectF]:
        return {
            track.track_id: QRectF(
                self.track_header_width - 32,
                self.ruler_height + row * self.track_height + 11,
                22,
                22,
            )
            for row, track in enumerate(self._ordered_tracks())
        }

    def _clip_rects_for(self, timeline: Timeline) -> dict[str, QRectF]:
        tracks = {
            track.track_id: index
            for index, track in enumerate(self._ordered_tracks_for(timeline))
        }
        rects: dict[str, QRectF] = {}
        for clip in timeline.clips:
            row = tracks.get(clip.track_id)
            if row is None:
                continue
            x = self._scale.time_to_x(clip.timeline_start_us)
            width = max(
                8.0,
                clip.timeline_duration_us
                / 1_000_000
                * self._scale.pixels_per_second,
            )
            rects[clip.clip_id] = QRectF(
                x,
                self.ruler_height + row * self.track_height + 7,
                width,
                self.track_height - 14,
            )
        return rects

    def fit_timeline(self, viewport_width: int) -> float:
        end_us = max(
            (clip.timeline_end_us for clip in self._timeline.clips),
            default=10_000_000,
        )
        available = max(100, int(viewport_width) - self.track_header_width - 24)
        zoom = normalize_timeline_zoom(
            available
            / (end_us / 1_000_000)
            / DEFAULT_TIMELINE_PIXELS_PER_SECOND
        )
        pixels = zoom * DEFAULT_TIMELINE_PIXELS_PER_SECOND
        self._scale = TimelineScale(
            pixels,
            0,
            self.track_header_width,
        )
        self._refresh_size()
        self.zoom_changed.emit(zoom, 0)
        self.update()
        return zoom

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#F8FAFC"))
        self._draw_ruler(painter)
        self._draw_tracks(painter)
        self._draw_clips(painter)
        self._draw_trim_candidate(painter)
        self._draw_trim_handles(painter)
        self._draw_material_drop_candidate(painter)
        self._draw_playhead(painter)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        point = event.localPos()
        track_lock = self._track_lock_at(point)
        if track_lock is not None:
            if self._editing_enabled:
                self.track_lock_requested.emit(
                    track_lock.track_id,
                    not track_lock.locked,
                )
            event.accept()
            return
        trim_hit = self._trim_handle_at(point)
        if trim_hit is not None and self._editing_enabled:
            clip, edge = trim_hit
            track = self._track_by_id(clip.track_id)
            if track is not None and not track.locked:
                self._drag_clip_id = None
                self._drag_candidate = None
                self._trim_interaction.begin(clip, edge=edge)
                self.setCursor(Qt.SizeHorCursor)
                event.accept()
                return
        clip = self._clip_at(point)
        if clip is not None:
            self._selected_clip_id = clip.clip_id
            self._selected_track_id = clip.track_id
            track = self._track_by_id(clip.track_id)
            if (
                self._editing_enabled
                and track is not None
                and not track.locked
                and self.clip_status(clip.clip_id) != "link_error"
            ):
                self._drag_clip_id = clip.clip_id
                self._drag_offset_us = max(
                    0,
                    self._scale.x_to_time(point.x()) - clip.timeline_start_us,
                )
            self.clip_selected.emit(clip.clip_id, clip.track_id)
            self.update()
            event.accept()
            return
        track = self._track_at(point.y())
        if track is not None:
            self._selected_track_id = track.track_id
            self.track_selected.emit(track.track_id)
        if point.x() >= self.track_header_width:
            requested = self._scale.x_to_time(point.x())
            self._playhead_us = requested
            self.playhead_requested.emit(requested)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._trim_interaction.active:
            try:
                source_start_us, source_end_us = (
                    self._trim_interaction.requested_source_range(
                        self._scale.x_to_time(event.localPos().x())
                    )
                )
            except RuntimeError:
                self.cancel_trim()
                return
            clip_id = self._trim_interaction.clip_id
            if clip_id is not None:
                self.clip_trim_preview_requested.emit(
                    clip_id,
                    source_start_us,
                    source_end_us,
                )
            self.setCursor(Qt.SizeHorCursor)
            self.update()
            event.accept()
            return
        if self._drag_clip_id is None:
            if self._trim_handle_at(event.localPos()) is not None:
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.unsetCursor()
            super().mouseMoveEvent(event)
            return
        clip = self._clip_by_id(self._drag_clip_id)
        target_track = self._track_at(event.localPos().y())
        if clip is None or target_track is None:
            self._drag_candidate = None
            self.update()
            return
        source_track = self._track_by_id(clip.track_id)
        if (
            source_track is None
            or source_track.kind != target_track.kind
            or source_track.locked
            or target_track.locked
        ):
            self._drag_candidate = (
                clip.timeline_start_us,
                target_track.track_id,
                False,
                (
                    "锁定轨道禁止移动片段"
                    if source_track is not None
                    and (source_track.locked or target_track.locked)
                    else "视频片段和音频片段只能在同类轨道之间移动"
                ),
            )
            self.update()
            return
        raw_start = max(
            0,
            self._scale.x_to_time(event.localPos().x()) - self._drag_offset_us,
        )
        candidates = [self._playhead_us]
        for other in self._timeline.clips:
            if other.clip_id == clip.clip_id:
                continue
            candidates.extend(
                [other.timeline_start_us, other.timeline_end_us]
            )
        grid = self._grid_us()
        tolerance = round(8 / self._scale.pixels_per_second * 1_000_000)
        start = snap_time_us(
            raw_start,
            candidates=candidates,
            grid_us=grid,
            tolerance_us=tolerance,
            enabled=not bool(event.modifiers() & Qt.AltModifier),
        )
        valid = not self._would_overlap(
            clip,
            target_track.track_id,
            start,
        )
        self._drag_candidate = (
            start,
            target_track.track_id,
            valid,
            "" if valid else "目标位置与同轨道现有片段重叠",
        )
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._trim_interaction.active:
            candidate = self._trim_interaction.finish()
            self.unsetCursor()
            if candidate is not None:
                self.clip_trim_commit_requested.emit(candidate)
            self.update()
            event.accept()
            return
        if event.button() != Qt.LeftButton or self._drag_clip_id is None:
            super().mouseReleaseEvent(event)
            return
        clip_id = self._drag_clip_id
        candidate = self._drag_candidate
        self._drag_clip_id = None
        self._drag_candidate = None
        if candidate is None:
            self.update()
            return
        start, track_id, valid, reason = candidate
        if valid:
            self.clip_move_requested.emit(clip_id, start, track_id)
        else:
            self.invalid_drop.emit(reason)
        self.update()
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            cancelled = self.cancel_material_drop()
            if self._trim_interaction.active:
                self.cancel_trim()
                cancelled = True
            if cancelled:
                event.accept()
                return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        self.cancel_trim()
        super().focusOutEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._trim_interaction.active:
            self.unsetCursor()
        super().leaveEvent(event)

    def contextMenuEvent(self, event) -> None:
        clip = self._clip_at(QPointF(event.pos()))
        if clip is None:
            super().contextMenuEvent(event)
            return
        self._selected_clip_id = clip.clip_id
        self._selected_track_id = clip.track_id
        self.clip_selected.emit(clip.clip_id, clip.track_id)
        self.clip_context_requested.emit(clip.clip_id, event.globalPos())
        self.update()
        event.accept()

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            current_zoom = (
                self._scale.pixels_per_second
                / DEFAULT_TIMELINE_PIXELS_PER_SECOND
            )
            self.set_zoom(
                current_zoom * factor,
                anchor_x=event.pos().x(),
            )
            event.accept()
            return
        super().wheelEvent(event)

    def material_drop_target(
        self,
        x: float,
        y: float,
        *,
        has_audio: bool,
    ) -> tuple[int, str, bool, str]:
        """计算素材拖入候选，不修改模型。"""
        track = self._track_at(y)
        start_us = self._scale.x_to_time(x)
        if not self._editing_enabled:
            return start_us, "", False, "当前项目为只读状态"
        if track is None or x < self.track_header_width:
            return start_us, "", False, "请把素材拖到视频轨或兼容音频轨"
        if track.locked:
            return start_us, track.track_id, False, "目标轨道已锁定"
        if track.kind == "audio" and not has_audio:
            return (
                start_us,
                track.track_id,
                False,
                "该素材没有可加入音频轨的音频流",
            )
        return start_us, track.track_id, True, ""

    def dragEnterEvent(self, event) -> None:
        payload = self._decode_material_payload(event.mimeData())
        if payload is not None:
            self.begin_material_drop(payload)
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        payload = self._decode_material_payload(event.mimeData())
        if payload is None:
            event.ignore()
            return
        if self._material_drop_planner is not None:
            candidate = self.preview_material_drop(
                payload,
                x=event.pos().x(),
                y=event.pos().y(),
                snap_enabled=not bool(
                    event.keyboardModifiers() & Qt.AltModifier
                ),
            )
            if candidate is not None:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            self._legacy_material_drop_candidate = self.material_drop_target(
                event.pos().x(),
                event.pos().y(),
                has_audio=bool(payload.get("has_audio", False)),
            )
            if self._legacy_material_drop_candidate[2]:
                event.acceptProposedAction()
            else:
                event.ignore()
        self.update()

    def dragLeaveEvent(self, event) -> None:
        self.cancel_material_drop()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        payload = self._decode_material_payload(event.mimeData())
        if payload is None:
            self.cancel_material_drop()
            event.ignore()
            return
        if self._material_drop_planner is not None:
            if self.commit_material_drop_preview():
                event.acceptProposedAction()
            else:
                event.ignore()
            return
        candidate = self._legacy_material_drop_candidate
        self._legacy_material_drop_candidate = None
        self._material_drop_interaction.cancel()
        if candidate is None:
            event.ignore()
            self.update()
            return
        start_us, track_id, valid, reason = candidate
        if not valid:
            self.invalid_drop.emit(reason)
            event.ignore()
            self.update()
            return
        self.material_drop_requested.emit(
            str(payload["material_id"]),
            bool(payload.get("has_audio", False)),
            start_us,
            track_id,
        )
        event.acceptProposedAction()
        self.update()

    def _draw_ruler(self, painter: QPainter) -> None:
        painter.fillRect(
            QRectF(0, 0, self.width(), self.ruler_height),
            QColor("#EEF2F7"),
        )
        painter.setPen(QPen(QColor("#C7D0DE"), 1))
        painter.drawLine(
            QPointF(0, self.ruler_height - 1),
            QPointF(self.width(), self.ruler_height - 1),
        )
        minor_frames, major_frames = self.ruler_tick_spec()
        start_frame = (
            self._scale.origin_us * self._editing_fps // 1_000_000
        )
        end_us = self._scale.x_to_time(self.width())
        end_frame = (
            end_us * self._editing_fps + 999_999
        ) // 1_000_000
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        current_frame = (
            start_frame // minor_frames
        ) * minor_frames
        while current_frame <= end_frame + minor_frames:
            current_us = frame_to_microseconds(
                current_frame,
                self._editing_fps,
            )
            x = self._scale.time_to_x(current_us)
            major = current_frame % major_frames == 0
            painter.drawLine(
                QPointF(
                    x,
                    self.ruler_height - (10 if major else 5),
                ),
                QPointF(x, self.ruler_height),
            )
            if major:
                painter.drawText(
                    QRectF(x + 3, 2, 96, self.ruler_height - 6),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    format_frame_time(current_us, self._editing_fps),
                )
            current_frame += minor_frames

    def _draw_tracks(self, painter: QPainter) -> None:
        for row, track in enumerate(self._ordered_tracks()):
            y = self.ruler_height + row * self.track_height
            selected = track.track_id == self._selected_track_id
            painter.fillRect(
                QRectF(0, y, self.width(), self.track_height),
                QColor(
                    "#E9EDF3"
                    if track.locked
                    else ("#F7FAFF" if selected else "#FFFFFF")
                ),
            )
            painter.fillRect(
                QRectF(0, y, self.track_header_width, self.track_height),
                QColor(
                    "#DDE3EA"
                    if track.locked
                    else ("#EAF1FC" if selected else "#F1F4F8")
                ),
            )
            painter.setPen(QPen(QColor("#D8DEE8"), 1))
            painter.drawLine(
                QPointF(0, y + self.track_height - 1),
                QPointF(self.width(), y + self.track_height - 1),
            )
            painter.drawLine(
                QPointF(self.track_header_width, y),
                QPointF(self.track_header_width, y + self.track_height),
            )
            painter.setPen(QColor("#172033"))
            kind = "视频" if track.kind == "video" else "音频"
            painter.drawText(
                QRectF(12, y + 5, self.track_header_width - 52, 22),
                Qt.AlignLeft | Qt.AlignVCenter,
                track.name,
            )
            painter.setPen(QColor("#7B8799"))
            painter.drawText(
                QRectF(12, y + 27, self.track_header_width - 52, 18),
                Qt.AlignLeft | Qt.AlignVCenter,
                f"{kind} · {'已锁定' if track.locked else '可编辑'}",
            )
            lock_rect = self.track_lock_rects()[track.track_id]
            self._draw_lock_icon(painter, lock_rect, locked=track.locked)

    def _draw_clips(self, painter: QPainter) -> None:
        candidate_clip = self._clip_by_id(self._drag_clip_id)
        for clip in self._timeline.clips:
            rect = self.clip_rects().get(clip.clip_id)
            if rect is None:
                continue
            track = self._track_by_id(clip.track_id)
            base = "#DCE8FF" if track and track.kind == "video" else "#DDF4E8"
            border = "#2563EB" if track and track.kind == "video" else "#168653"
            status = self.clip_status(clip.clip_id)
            if status == "missing":
                base = "#FFF4D6"
                border = "#B7791F"
            elif status == "link_error":
                base = "#FDE8E7"
                border = "#C73A35"
            if clip.clip_id == self._selected_clip_id:
                painter.setPen(QPen(QColor("#1457D9"), 2))
            else:
                painter.setPen(QPen(QColor(border), 1))
            painter.setBrush(QColor(base))
            painter.drawRoundedRect(rect, 5, 5)
            painter.setPen(QColor("#172033"))
            painter.drawText(
                rect.adjusted(8, 4, -6, -4),
                Qt.AlignLeft | Qt.AlignVCenter,
                clip.material_id,
            )
            if status in {"missing", "link_error"}:
                painter.setPen(
                    QColor("#9A6700" if status == "missing" else "#B42318")
                )
                painter.drawText(
                    rect.adjusted(8, 20, -6, -2),
                    Qt.AlignLeft | Qt.AlignBottom,
                    "素材缺失" if status == "missing" else "关联异常",
                )
            elif clip.link_group_id:
                painter.setPen(QColor("#526077"))
                painter.drawText(
                    rect.adjusted(8, 20, -6, -2),
                    Qt.AlignLeft | Qt.AlignBottom,
                    "已关联",
                )
            else:
                painter.setPen(QColor("#7B8799"))
                painter.drawText(
                    rect.adjusted(8, 20, -6, -2),
                    Qt.AlignLeft | Qt.AlignBottom,
                    "未关联",
                )
        if candidate_clip is not None and self._drag_candidate is not None:
            start, track_id, valid, _reason = self._drag_candidate
            track_rows = {
                track.track_id: index
                for index, track in enumerate(self._ordered_tracks())
            }
            row = track_rows.get(track_id)
            if row is not None:
                rect = QRectF(
                    self._scale.time_to_x(start),
                    self.ruler_height + row * self.track_height + 7,
                    max(
                        8.0,
                        candidate_clip.timeline_duration_us
                        / 1_000_000
                        * self._scale.pixels_per_second,
                    ),
                    self.track_height - 14,
                )
                painter.setPen(
                    QPen(QColor("#168653" if valid else "#C73A35"), 2, Qt.DashLine)
                )
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect, 5, 5)

    def _draw_playhead(self, painter: QPainter) -> None:
        x = self._scale.time_to_x(self._playhead_us)
        painter.setPen(QPen(QColor("#E13B32"), 2))
        painter.drawLine(
            QPointF(x, self.ruler_height - 6),
            QPointF(x, self.height()),
        )

    def _draw_material_drop_candidate(self, painter: QPainter) -> None:
        candidate = self._material_drop_candidate
        if candidate is None:
            return
        rows = {
            track.track_id: index
            for index, track in enumerate(self._ordered_tracks())
        }
        x = self._scale.time_to_x(candidate.start_us)
        color = QColor("#168653" if candidate.valid else "#C73A35")
        color.setAlpha(55)
        painter.setBrush(color)
        painter.setPen(
            QPen(
                QColor("#168653" if candidate.valid else "#C73A35"),
                2,
                Qt.DashLine,
            )
        )
        width = max(
            90.0,
            candidate.duration_us
            / 1_000_000
            * self._scale.pixels_per_second,
        )
        target_ids = tuple(
            track_id
            for track_id in (
                candidate.video_track_id,
                candidate.audio_track_id,
            )
            if track_id
        )
        for track_id in target_ids:
            row = rows.get(track_id)
            if row is None:
                continue
            track_rect = QRectF(
                self.track_header_width + 1,
                self.ruler_height + row * self.track_height + 1,
                max(0, self.width() - self.track_header_width - 2),
                self.track_height - 2,
            )
            painter.drawRect(track_rect)
            painter.drawRoundedRect(
                QRectF(
                    x,
                    self.ruler_height + row * self.track_height + 5,
                    width,
                    self.track_height - 10,
                ),
                5,
                5,
            )

        for offset, kind in enumerate(candidate.auto_track_kinds):
            label = "将自动新建视频轨" if kind == "video" else "将自动新建音频轨"
            y = (
                self.ruler_height + 2 + offset * 18
                if kind == "video"
                else max(
                    self.ruler_height + 2,
                    self.height() - 20 - offset * 18,
                )
            )
            painter.setPen(
                QPen(
                    QColor("#168653" if candidate.valid else "#C73A35"),
                    1,
                    Qt.DashLine,
                )
            )
            painter.drawRect(
                QRectF(self.track_header_width + 4, y, 150, 16)
            )
            painter.drawText(
                QRectF(self.track_header_width + 9, y, 140, 16),
                Qt.AlignLeft | Qt.AlignVCenter,
                label,
            )

        if candidate.snap_source != "none":
            painter.setPen(QPen(QColor("#2563EB"), 1, Qt.DashLine))
            painter.drawLine(
                QPointF(x, self.ruler_height),
                QPointF(x, self.height()),
            )
        painter.setFont(QFont(painter.font().family(), 8))
        painter.setPen(
            QColor("#168653" if candidate.valid else "#C73A35")
        )
        painter.drawText(
            QRectF(
                max(self.track_header_width + 4, x + 4),
                2,
                max(120, self.width() - x - 8),
                self.ruler_height - 4,
            ),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.material_drop_summary(),
        )

    def _draw_trim_handles(self, painter: QPainter) -> None:
        for left, right in self.trim_handle_rects().values():
            for rect in (left, right):
                painter.setPen(QPen(QColor("#FFFFFF"), 1))
                painter.setBrush(QColor("#1457D9"))
                painter.drawRoundedRect(rect, 2, 2)

    def _draw_trim_candidate(self, painter: QPainter) -> None:
        candidate = self._trim_interaction.candidate
        if candidate is None:
            return
        if candidate.timeline is None:
            rect = self.clip_rects().get(
                self._trim_interaction.clip_id or ""
            )
            if rect is not None:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor("#C73A35"), 2, Qt.DashLine))
                painter.drawRoundedRect(rect, 5, 5)
            return
        rects = self._clip_rects_for(candidate.timeline)
        affected = set(candidate.impact.affected_clip_ids)
        for clip_id in affected:
            rect = rects.get(clip_id)
            if rect is None:
                continue
            painter.setBrush(Qt.NoBrush)
            painter.setPen(
                QPen(
                    QColor("#168653" if candidate.valid else "#C73A35"),
                    2,
                    Qt.DashLine,
                )
            )
            painter.drawRoundedRect(rect, 5, 5)

    def _draw_lock_icon(
        self,
        painter: QPainter,
        rect: QRectF,
        *,
        locked: bool,
    ) -> None:
        color = QColor("#A66309" if locked else "#526077")
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(QColor("#FFF3D6") if locked else Qt.NoBrush)
        body = QRectF(rect.left() + 5, rect.top() + 9, 12, 10)
        painter.drawRoundedRect(body, 2, 2)
        shackle = QRectF(rect.left() + 7, rect.top() + 3, 8, 10)
        painter.drawArc(shackle, 0, 180 * 16)

    def _refresh_size(self) -> None:
        total_end = max(
            (clip.timeline_end_us for clip in self._timeline.clips),
            default=30_000_000,
        )
        width = round(
            self.track_header_width
            + total_end / 1_000_000 * self._scale.pixels_per_second
            + 120
        )
        height = self.ruler_height + len(self._timeline.tracks) * self.track_height
        self.setMinimumSize(max(640, width), max(120, height))

    def _ordered_tracks(self) -> list[TimelineTrack]:
        return self._ordered_tracks_for(self._timeline)

    @staticmethod
    def _ordered_tracks_for(timeline: Timeline) -> list[TimelineTrack]:
        videos = sorted(
            (track for track in timeline.tracks if track.kind == "video"),
            key=lambda item: item.order,
        )
        audios = sorted(
            (track for track in timeline.tracks if track.kind == "audio"),
            key=lambda item: item.order,
        )
        return [*videos, *audios]

    def _track_at(self, y: float) -> TimelineTrack | None:
        row = int((float(y) - self.ruler_height) // self.track_height)
        tracks = self._ordered_tracks()
        return tracks[row] if 0 <= row < len(tracks) else None

    def _clip_at(self, point: QPointF) -> TimelineClip | None:
        rects = self.clip_rects()
        for clip in reversed(self._timeline.clips):
            rect = rects.get(clip.clip_id)
            if rect is not None and rect.contains(point):
                return clip
        return None

    def _trim_handle_at(
        self,
        point: QPointF,
    ) -> tuple[TimelineClip, TrimEdge] | None:
        for clip_id, (left, right) in self.trim_handle_rects().items():
            clip = self._clip_by_id(clip_id)
            if clip is None:
                continue
            if left.contains(point):
                return clip, "left"
            if right.contains(point):
                return clip, "right"
        return None

    def _track_lock_at(self, point: QPointF) -> TimelineTrack | None:
        for track_id, rect in self.track_lock_rects().items():
            if rect.contains(point):
                return self._track_by_id(track_id)
        return None

    def _clip_by_id(self, clip_id: str | None) -> TimelineClip | None:
        return next(
            (
                clip
                for clip in self._timeline.clips
                if clip.clip_id == clip_id
            ),
            None,
        )

    @classmethod
    def _decode_material_payload(cls, mime_data) -> dict[str, object] | None:
        if not mime_data.hasFormat(cls.MATERIAL_MIME_TYPE):
            return None
        try:
            payload = json.loads(
                bytes(mime_data.data(cls.MATERIAL_MIME_TYPE)).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return None
        if not isinstance(payload, dict) or not str(
            payload.get("material_id", "")
        ).strip():
            return None
        return payload

    def _track_by_id(self, track_id: str) -> TimelineTrack | None:
        return next(
            (
                track
                for track in self._timeline.tracks
                if track.track_id == track_id
            ),
            None,
        )

    def _would_overlap(
        self,
        clip: TimelineClip,
        track_id: str,
        start_us: int,
    ) -> bool:
        end_us = start_us + clip.timeline_duration_us
        for other in self._timeline.clips:
            if other.clip_id == clip.clip_id or other.track_id != track_id:
                continue
            if start_us < other.timeline_end_us and end_us > other.timeline_start_us:
                return True
        return False

    def _grid_us(self) -> int:
        pixels = self._scale.pixels_per_second
        if pixels >= 400:
            return 250_000
        if pixels >= 160:
            return 500_000
        if pixels >= 70:
            return 1_000_000
        return 5_000_000


def _format_ruler_time(value_us: int) -> str:
    total_seconds = max(0, int(value_us)) // 1_000_000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _drop_conflict_message(candidate: TimelineDragCandidate) -> str:
    return {
        "outside_timeline": "请把素材拖到时间线内容区域",
        "read_only": "当前项目为只读状态，不能拖入素材",
        "save_pending": "存在待处理保存，请先解决后再拖入素材",
        "timeline_unavailable": "当前项目时间线不可用",
        "invalid_material": "素材缺失、损坏或没有可用媒体流",
        "missing_track": "目标轨道已经不存在，请重新选择落点",
        "locked_track": "目标轨道已锁定",
        "incompatible_track": "素材类型与目标轨道不兼容",
        "track_limit": "兼容轨道已满，且同类型轨道达到 8 条上限",
        "candidate_invalid": "当前落点无法生成有效片段",
    }.get(
        candidate.conflict_code,
        candidate.conflict_reason or "当前落点不可用",
    )


def _ceil_ratio(numerator: float, denominator: float) -> int:
    return max(1, int((numerator + denominator - 1e-9) // denominator))


def _nice_frame_step(minimum: int) -> int:
    target = max(1, int(minimum))
    scale = 1
    while True:
        for multiplier in (1, 2, 5):
            candidate = multiplier * scale
            if candidate >= target:
                return candidate
        scale *= 10
