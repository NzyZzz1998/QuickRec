"""可测试的片段属性检查器与精确时间输入。"""

from __future__ import annotations

import re

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.timeline_edit_service import TimelineEditCandidate
from utils.timeline_model import TimelineClip

_TIMECODE_PATTERN = re.compile(
    r"^(?P<hours>\d{2,}):(?P<minutes>[0-5]\d):"
    r"(?P<seconds>[0-5]\d)\.(?P<milliseconds>\d{3})$"
)


def parse_timecode_us(value: str) -> int:
    """把严格的 HH:MM:SS.mmm 文本转换为整数微秒。"""
    match = _TIMECODE_PATTERN.fullmatch(str(value).strip())
    if match is None:
        raise ValueError("时间格式必须为 HH:MM:SS.mmm")
    hours = int(match.group("hours"))
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    milliseconds = int(match.group("milliseconds"))
    return (
        ((hours * 60 + minutes) * 60 + seconds) * 1_000_000
        + milliseconds * 1_000
    )


def format_timecode_us(value_us: int) -> str:
    value = max(0, int(value_us))
    total_milliseconds = value // 1_000
    total_seconds, milliseconds = divmod(total_milliseconds, 1_000)
    total_minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


class ClipInspectorWidget(QFrame):
    """只生成并展示精确裁剪候选，由窗口协调正式提交。"""

    preview_requested = pyqtSignal(int, int)
    apply_requested = pyqtSignal(object)
    cancel_requested = pyqtSignal()
    closed_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("clipInspector")
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(300)
        self.setMaximumWidth(380)
        self.setFocusPolicy(Qt.StrongFocus)
        self._candidate: TimelineEditCandidate | None = None
        self._baseline_range = (0, 0)
        self._material_duration_us = 0
        self._editable = False
        self._suppress_preview = False
        self._build_ui()

    @property
    def candidate(self) -> TimelineEditCandidate | None:
        return self._candidate

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(9)

        header = QHBoxLayout()
        title = QLabel("片段属性")
        title.setProperty("role", "sectionTitle")
        header.addWidget(title, 1)
        self._btn_close = QPushButton("关闭")
        self._btn_close.setAccessibleName("关闭片段属性")
        self._btn_close.setToolTip("关闭检查器，并放弃尚未提交的裁剪候选")
        self._btn_close.clicked.connect(self._close_inspector)
        header.addWidget(self._btn_close)
        root.addLayout(header)

        self._content_scroll = QScrollArea()
        self._content_scroll.setObjectName("clipInspectorScroll")
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setFrameShape(QFrame.NoFrame)
        self._content_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        content = QWidget()
        content.setObjectName("clipInspectorContent")
        content.setMinimumHeight(330)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 4, 0)
        content_layout.setSpacing(9)

        self._identity = QLabel("未选择片段")
        self._identity.setWordWrap(True)
        content_layout.addWidget(self._identity)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(7)
        self._timeline_start = QLabel("00:00:00.000")
        form.addRow("时间线起点", self._timeline_start)
        self._source_in = QLineEdit()
        self._source_in.setAccessibleName("片段源入点")
        self._source_in.setPlaceholderText("HH:MM:SS.mmm")
        form.addRow("源入点", self._source_in)
        self._source_out = QLineEdit()
        self._source_out.setAccessibleName("片段源出点")
        self._source_out.setPlaceholderText("HH:MM:SS.mmm")
        form.addRow("源出点", self._source_out)
        self._effective_duration = QLabel("00:00:00.000")
        form.addRow("有效时长", self._effective_duration)
        self._material_duration = QLabel("00:00:00.000")
        form.addRow("素材总时长", self._material_duration)
        self._frame_summary = QLabel("FPS 未知，按 100 毫秒下限校验")
        self._frame_summary.setWordWrap(True)
        form.addRow("帧归一化", self._frame_summary)
        self._link_status = QLabel("未关联，可独立编辑")
        form.addRow("音视频关联", self._link_status)
        content_layout.addLayout(form)

        self._validation_message = QLabel("修改源范围后将生成候选")
        self._validation_message.setObjectName("clipInspectorValidation")
        self._validation_message.setWordWrap(True)
        content_layout.addWidget(self._validation_message)

        impact = QFrame()
        impact.setObjectName("clipInspectorImpact")
        impact_layout = QVBoxLayout(impact)
        impact_layout.setContentsMargins(10, 8, 10, 8)
        impact_layout.setSpacing(2)
        impact_title = QLabel("全局波纹影响")
        impact_title.setProperty("role", "sectionTitle")
        impact_layout.addWidget(impact_title)
        self._impact_summary = QLabel("当前无变化")
        self._impact_summary.setWordWrap(True)
        impact_layout.addWidget(self._impact_summary)
        content_layout.addWidget(impact)
        content_layout.addStretch(1)
        self._content_scroll.setWidget(content)
        root.addWidget(self._content_scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self._btn_apply = QPushButton("应用")
        self._btn_apply.setProperty("role", "primary")
        self._btn_apply.setAccessibleName("应用精确裁剪")
        self._btn_apply.setEnabled(False)
        self._btn_apply.setToolTip(
            "打开全局波纹影响确认，确认后原子保存"
        )
        self._btn_apply.clicked.connect(self._apply)
        footer.addWidget(self._btn_apply)
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setAccessibleName("取消精确裁剪")
        self._btn_cancel.setToolTip("放弃尚未提交的精确裁剪候选")
        self._btn_cancel.clicked.connect(self.cancel)
        footer.addWidget(self._btn_cancel)
        root.addLayout(footer)

        self._source_in.textChanged.connect(self._on_values_changed)
        self._source_out.textChanged.connect(self._on_values_changed)
        self._source_in.returnPressed.connect(self._apply)
        self._source_out.returnPressed.connect(self._apply)

    def load_clip(
        self,
        clip: TimelineClip,
        *,
        material_name: str,
        track_name: str,
        material_duration_us: int,
        fps: float | None,
        linked_clip_count: int,
        editable: bool,
    ) -> None:
        self._candidate = None
        source_end_us = clip.source_start_us + clip.source_duration_us
        self._baseline_range = (clip.source_start_us, source_end_us)
        self._material_duration_us = max(0, int(material_duration_us))
        self._editable = bool(editable)
        self._identity.setText(
            f"{material_name} · {track_name} · {clip.clip_id}"
        )
        self._timeline_start.setText(
            format_timecode_us(clip.timeline_start_us)
        )
        self._material_duration.setText(
            format_timecode_us(self._material_duration_us)
        )
        self._link_status.setText(
            f"关联组，共 {linked_clip_count} 个片段"
            if linked_clip_count > 1
            else "未关联，可独立编辑"
        )
        self._frame_summary.setText(
            f"{float(fps):g} FPS · 候选按帧边界归一化"
            if fps is not None and float(fps) > 0
            else "FPS 未知，按 100 毫秒下限校验"
        )
        self._suppress_preview = True
        self._source_in.setText(format_timecode_us(clip.source_start_us))
        self._source_out.setText(format_timecode_us(source_end_us))
        self._suppress_preview = False
        self._effective_duration.setText(
            format_timecode_us(clip.source_duration_us)
        )
        self._validation_message.setText("修改源范围后将生成候选")
        self._impact_summary.setText("当前无变化")
        self._source_in.setReadOnly(not self._editable)
        self._source_out.setReadOnly(not self._editable)
        self._btn_apply.setEnabled(False)

    def set_candidate(self, candidate: TimelineEditCandidate | None) -> None:
        self._candidate = candidate
        if candidate is None:
            self._btn_apply.setEnabled(False)
            self._impact_summary.setText("尚未生成候选")
            return
        if (
            candidate.normalized_source_start_us is not None
            and candidate.normalized_source_end_us is not None
        ):
            duration_us = (
                candidate.normalized_source_end_us
                - candidate.normalized_source_start_us
            )
            self._effective_duration.setText(format_timecode_us(duration_us))
            self._validation_message.setText(
                "已按媒体帧边界归一化为 "
                f"{format_timecode_us(candidate.normalized_source_start_us)}"
                " - "
                f"{format_timecode_us(candidate.normalized_source_end_us)}"
            )
        impact = candidate.impact
        delta = impact.delta_us
        if delta < 0:
            direction = f"总时长减少 {format_timecode_us(-delta)}"
        elif delta > 0:
            direction = f"总时长增加 {format_timecode_us(delta)}"
        else:
            direction = "总时长不变"
        self._impact_summary.setText(
            f"{direction}；影响 {len(impact.affected_track_ids)} 条轨道、"
            f"{len(impact.affected_clip_ids)} 个片段"
        )
        if candidate.valid:
            self._btn_apply.setEnabled(self._editable)
            return
        self._btn_apply.setEnabled(False)
        detail = "；".join(item.message for item in candidate.conflicts)
        self._validation_message.setText(detail or "候选范围无效")

    def set_editable(self, editable: bool) -> None:
        self._editable = bool(editable)
        self._source_in.setReadOnly(not self._editable)
        self._source_out.setReadOnly(not self._editable)
        self._btn_apply.setEnabled(
            self._editable
            and self._candidate is not None
            and self._candidate.valid
        )

    def cancel(self) -> None:
        start_us, end_us = self._baseline_range
        self._candidate = None
        self._suppress_preview = True
        self._source_in.setText(format_timecode_us(start_us))
        self._source_out.setText(format_timecode_us(end_us))
        self._suppress_preview = False
        self._effective_duration.setText(format_timecode_us(end_us - start_us))
        self._validation_message.setText(
            "已取消，正式时间线没有发生变化"
        )
        self._impact_summary.setText("当前无变化")
        self._btn_apply.setEnabled(False)
        self.cancel_requested.emit()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        if event.key() == Qt.Key_Escape:
            self.cancel()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_values_changed(self) -> None:
        if self._suppress_preview:
            return
        self._candidate = None
        self._btn_apply.setEnabled(False)
        try:
            start_us = parse_timecode_us(self._source_in.text())
            end_us = parse_timecode_us(self._source_out.text())
        except ValueError as exc:
            self._validation_message.setText(str(exc))
            self._impact_summary.setText("输入格式无效，未生成候选")
            return
        if start_us < 0 or end_us <= start_us:
            self._validation_message.setText("源出点必须大于源入点")
            return
        if self._material_duration_us and end_us > self._material_duration_us:
            self._validation_message.setText("源出点不能超过素材总时长")
            return
        self._effective_duration.setText(format_timecode_us(end_us - start_us))
        if (start_us, end_us) == self._baseline_range:
            self._validation_message.setText("源范围没有变化")
            self._impact_summary.setText("当前无变化")
            return
        self._validation_message.setText(
            "正在计算帧归一化和全局波纹影响"
        )
        self.preview_requested.emit(start_us, end_us)

    def _apply(self) -> None:
        candidate = self._candidate
        if (
            not self._btn_apply.isEnabled()
            or candidate is None
            or not candidate.valid
        ):
            return
        self.apply_requested.emit(candidate)

    def _close_inspector(self) -> None:
        self.cancel()
        self.hide()
        self.closed_requested.emit()
