"""v1.9.5 时间线影响预览、冲突定位与重新关联对话框。"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.timeline_edit_service import (
    TimelineEditCandidate,
    TimelineRelinkOption,
)
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
        self.setWindowTitle(title or "时间线修改影响")
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
        if (
            impact.range_start_us is not None
            and impact.range_end_us is not None
        ):
            range_text = (
                f"作用区间 {format_timecode_us(impact.range_start_us)} - "
                f"{format_timecode_us(impact.range_end_us)}"
            )
        elif impact.insert_at_us is not None:
            range_text = (
                f"插入点 {format_timecode_us(impact.insert_at_us)}"
            )
        else:
            range_text = "不会移动其他片段的时间位置"
        self._summary = QLabel(
            f"{range_text}\n"
            f"总时长 {format_timecode_us(impact.timeline_duration_before_us)}"
            f" -> {format_timecode_us(impact.timeline_duration_after_us)}\n"
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
                    f"- {item.message}" for item in self._candidate.conflicts
                )
            )
        else:
            self._conflicts = QLabel(
                "预检通过：没有轨道锁定、区间交叉或数据冲突。"
            )
        self._conflicts.setWordWrap(True)
        conflict_layout.addWidget(self._conflicts)
        root.addWidget(conflict_frame)

        footer = QHBoxLayout()
        self._btn_locate = QPushButton("定位冲突")
        self._btn_locate.setAccessibleName("定位首个时间线冲突")
        self._btn_locate.setToolTip(
            "关闭对话框并选中首个冲突片段或轨道"
        )
        self._btn_locate.setVisible(bool(self._candidate.conflicts))
        self._btn_locate.clicked.connect(self._locate_first_conflict)
        footer.addWidget(self._btn_locate)
        footer.addStretch(1)
        self._btn_confirm = QPushButton(confirm_text)
        self._btn_confirm.setAccessibleName(confirm_text)
        self._btn_confirm.setProperty("role", "primary")
        self._btn_confirm.setEnabled(
            self._candidate.valid and self._candidate.timeline is not None
        )
        self._btn_confirm.clicked.connect(self.accept)
        footer.addWidget(self._btn_confirm)
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setAccessibleName("取消时间线修改")
        self._btn_cancel.setToolTip(
            "关闭影响预览，正式时间线保持不变"
        )
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


class TimelineRelinkDialog(QDialog):
    """只列出经过领域服务严格过滤的可重新关联片段。"""

    def __init__(
        self,
        options: Sequence[TimelineRelinkOption],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._options = tuple(options)
        self.setObjectName("timelineRelinkDialog")
        self.setWindowTitle("重新关联音视频")
        self.setModal(True)
        self.setMinimumSize(540, 320)
        self._build_ui()

    @classmethod
    def choose(
        cls,
        parent: QWidget,
        options: Sequence[TimelineRelinkOption],
    ) -> str | None:
        if not options:
            return None
        dialog = cls(options, parent)
        if dialog.exec_() != QDialog.Accepted:
            return None
        return dialog.selected_clip_id()

    def selected_clip_id(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return str(item.data(Qt.UserRole))

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        title = QLabel("选择兼容的音频或视频片段")
        title.setProperty("role", "sectionTitle")
        root.addWidget(title)
        explanation = QLabel(
            "仅显示素材、时间位置、源范围和时长完全一致，"
            "且轨道未锁定的候选。重新关联不会移动或裁剪片段。"
        )
        explanation.setWordWrap(True)
        root.addWidget(explanation)

        self._list = QListWidget()
        self._list.setAccessibleName("重新关联候选列表")
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        for option in self._options:
            source_end_us = (
                option.source_start_us + option.source_duration_us
            )
            item = QListWidgetItem(
                f"{option.track_name} · {option.clip_id}\n"
                f"时间线 {format_timecode_us(option.timeline_start_us)} · "
                f"时长 {format_timecode_us(option.timeline_duration_us)}\n"
                f"源范围 {format_timecode_us(option.source_start_us)} - "
                f"{format_timecode_us(source_end_us)} · "
                f"{option.file_name}"
            )
            item.setData(Qt.UserRole, option.clip_id)
            item.setToolTip(option.file_path)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        self._list.itemDoubleClicked.connect(lambda _item: self.accept())
        root.addWidget(self._list, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self._btn_confirm = QPushButton("确认关联")
        self._btn_confirm.setAccessibleName("确认重新关联音视频")
        self._btn_confirm.setProperty("role", "primary")
        self._btn_confirm.setToolTip(
            "为两个原片段生成新的关联组并原子保存"
        )
        self._btn_confirm.clicked.connect(self.accept)
        footer.addWidget(self._btn_confirm)
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setAccessibleName("取消重新关联")
        self._btn_cancel.setToolTip("关闭候选列表，不修改时间线")
        self._btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self._btn_cancel)
        root.addLayout(footer)


def _operation_title(operation: str) -> str:
    return {
        "trim": "确认裁剪与全局波纹影响",
        "ripple_delete": "确认删除并执行全局波纹",
        "delete": "确认删除并保留时间线空隙",
        "split": "确认在播放头处分割",
        "unlink": "确认解绑音视频",
        "relink": "确认重新关联音视频",
    }.get(operation, "确认时间线修改")
