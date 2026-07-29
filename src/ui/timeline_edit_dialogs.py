"""v1.9.3 时间线影响预览与冲突定位对话框。"""

from __future__ import annotations

from collections.abc import Callable

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.timeline_edit_service import TimelineEditCandidate
from ui.clip_inspector_widget import format_timecode_us


class TimelineImpactDialog(QDialog):
    """只读展示一次剪辑候选的全局影响。"""

    locate_requested = pyqtSignal(str, str)

    def __init__(
        self,
        candidate: TimelineEditCandidate,
        parent: QWidget | None = None,
        *,
        title: str | None = None,
        confirm_text: str = "确认并应用",
    ) -> None:
        super().__init__(parent)
        self._candidate = candidate
        self.setObjectName("timelineImpactDialog")
        self.setWindowTitle(title or "全局波纹影响")
        self.setModal(True)
        self.setMinimumWidth(460)
        self._build_ui(confirm_text)

    @classmethod
    def execute(
        cls,
        parent: QWidget,
        candidate: TimelineEditCandidate,
        *,
        title: str | None = None,
        confirm_text: str = "确认并应用",
        locate_callback: Callable[[str, str], None] | None = None,
    ) -> bool:
        dialog = cls(
            candidate,
            parent,
            title=title,
            confirm_text=confirm_text,
        )
        if locate_callback is not None:
            dialog.locate_requested.connect(locate_callback)
        return dialog.exec_() == QDialog.Accepted

    def _build_ui(self, confirm_text: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        heading = QLabel(_operation_title(self._candidate.operation))
        heading.setProperty("role", "sectionTitle")
        root.addWidget(heading)

        impact = self._candidate.impact
        range_text = (
            f"删除区间 {format_timecode_us(impact.range_start_us)} – "
            f"{format_timecode_us(impact.range_end_us)}"
            if impact.range_start_us is not None
            and impact.range_end_us is not None
            else (
                f"插入点 {format_timecode_us(impact.insert_at_us)}"
                if impact.insert_at_us is not None
                else "不改变时间线区间"
            )
        )
        self._summary = QLabel(
            f"{range_text}\n"
            f"总时长 {format_timecode_us(impact.timeline_duration_before_us)}"
            f" → {format_timecode_us(impact.timeline_duration_after_us)}\n"
            f"影响 {len(impact.affected_track_ids)} 条轨道、"
            f"{len(impact.affected_clip_ids)} 个片段；"
            f"关联目标 {impact.associated_clip_count} 个"
        )
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        conflict_frame = QFrame()
        conflict_frame.setObjectName(
            "timelineImpactConflict"
            if self._candidate.conflicts
            else "timelineImpactSafe"
        )
        conflict_layout = QVBoxLayout(conflict_frame)
        conflict_layout.setContentsMargins(10, 8, 10, 8)
        if self._candidate.conflicts:
            self._conflicts = QLabel(
                "\n".join(
                    f"• {item.message}" for item in self._candidate.conflicts
                )
            )
        else:
            self._conflicts = QLabel(
                "预检通过：没有区间交叉、轨道锁定或数据冲突。"
            )
        self._conflicts.setWordWrap(True)
        conflict_layout.addWidget(self._conflicts)
        root.addWidget(conflict_frame)

        footer = QHBoxLayout()
        self._btn_locate = QPushButton("定位冲突")
        self._btn_locate.setToolTip("关闭对话框并选中首个冲突片段或轨道")
        self._btn_locate.setVisible(bool(self._candidate.conflicts))
        self._btn_locate.clicked.connect(self._locate_first_conflict)
        footer.addWidget(self._btn_locate)
        footer.addStretch(1)
        self._btn_confirm = QPushButton(confirm_text)
        self._btn_confirm.setProperty("role", "primary")
        self._btn_confirm.setEnabled(
            self._candidate.valid and self._candidate.timeline is not None
        )
        self._btn_confirm.clicked.connect(self.accept)
        footer.addWidget(self._btn_confirm)
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setToolTip("关闭影响预览，正式时间线保持不变")
        self._btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self._btn_cancel)
        root.addLayout(footer)

    def _locate_first_conflict(self) -> None:
        if not self._candidate.conflicts:
            return
        conflict = self._candidate.conflicts[0]
        track_id = conflict.track_ids[0] if conflict.track_ids else ""
        clip_id = conflict.clip_ids[0] if conflict.clip_ids else ""
        self.locate_requested.emit(track_id, clip_id)
        self.reject()


def _operation_title(operation: str) -> str:
    return {
        "trim": "确认裁剪与全局波纹影响",
        "ripple_delete": "确认从时间线删除并执行全局波纹",
        "split": "确认在播放头处分割",
    }.get(operation, "确认时间线修改")
