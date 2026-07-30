"""QuickRec v1.9.4 导出配置、预检与安全入队对话框。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PyQt5.QtCore import QLocale, QRect, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from exporting.models import (
    ExportPlan,
    ExportPlanRequest,
    OverwriteMode,
)
from exporting.plan_builder import ExportPlanBuilder
from exporting.queue_service import ExportQueueService
from ui.design_system import (
    COLORS,
    WORKBENCH_STYLESHEET,
    set_button_icon,
)


@dataclass(frozen=True)
class ExportDialogContext:
    project_id: str
    project_name: str
    project_path: str
    output_directory: str
    project_saved: bool = True
    save_pending: bool = False
    external_conflict: bool = False
    incomplete_job_count: int = 0


class ExportConfigDialog(QDialog):
    """把导出表单、不可变计划预检和持久入队保持为三个明确步骤。"""

    queued = pyqtSignal(str)

    def __init__(
        self,
        context: ExportDialogContext,
        *,
        plan_builder: ExportPlanBuilder,
        queue_service: ExportQueueService,
        defaults: dict[str, object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.plan_builder = plan_builder
        self.queue_service = queue_service
        self._plan: ExportPlan | Any | None = None
        self.queued_job_id: str | None = None
        self._initializing = True

        self.setObjectName("quickrecExportConfig")
        self.setWindowTitle("新建导出任务")
        self.setModal(True)
        self.setMinimumSize(640, 540)
        self.resize(760, 700)
        self._init_ui(defaults or {})
        self.setStyleSheet(WORKBENCH_STYLESHEET + _EXPORT_DIALOG_STYLESHEET)
        self._initializing = False
        self.refresh_target_state()
        self._invalidate_preflight()

    def _init_ui(self, defaults: dict[str, object]) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel("新建导出任务")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        subtitle = QLabel(
            f"{self.context.project_name} · 创建后冻结当前已保存的时间线"
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)

        snapshot = QFrame()
        snapshot.setObjectName("exportSummaryPanel")
        snapshot_layout = QVBoxLayout(snapshot)
        snapshot_layout.setContentsMargins(14, 12, 14, 12)
        snapshot_layout.setSpacing(4)
        snapshot_title = QLabel("不可变导出计划")
        snapshot_title.setProperty("role", "sectionTitle")
        snapshot_layout.addWidget(snapshot_title)
        snapshot_text = QLabel(
            "预检会读取已保存项目、时间线和素材指纹；加入队列后，"
            "后续编辑不会改变本次任务。"
        )
        snapshot_text.setWordWrap(True)
        snapshot_text.setObjectName("pageSubtitle")
        snapshot_layout.addWidget(snapshot_text)
        body_layout.addWidget(snapshot)

        output_group = QFrame()
        output_group.setObjectName("exportFormPanel")
        output_layout = QVBoxLayout(output_group)
        output_layout.setContentsMargins(14, 12, 14, 12)
        output_layout.setSpacing(10)
        output_title = QLabel("输出规格")
        output_title.setProperty("role", "sectionTitle")
        output_layout.addWidget(output_title)

        dimensions = QGridLayout()
        dimensions.setHorizontalSpacing(12)
        dimensions.setVerticalSpacing(8)
        self._width = QSpinBox()
        self._width.setRange(320, 3840)
        self._width.setSingleStep(2)
        self._width.setLocale(QLocale.c())
        self._width.setValue(int(cast(Any, defaults.get("width", 1920))))
        self._width.setAccessibleName("导出宽度")
        self._width.setToolTip("最终 MP4 画布宽度，必须为偶数，最大 3840")
        self._height = QSpinBox()
        self._height.setRange(240, 2160)
        self._height.setSingleStep(2)
        self._height.setLocale(QLocale.c())
        self._height.setValue(int(cast(Any, defaults.get("height", 1080))))
        self._height.setAccessibleName("导出高度")
        self._height.setToolTip("最终 MP4 画布高度，必须为偶数，最大 2160")
        self._fps = QComboBox()
        self._fps.addItems(["30", "60", "120"])
        self._fps.setCurrentText(str(defaults.get("fps", 60)))
        self._fps.setAccessibleName("导出帧率")
        self._fps.setToolTip("120 FPS 只允许不超过 1920×1080 的画布")
        dimensions.addWidget(QLabel("宽度"), 0, 0)
        dimensions.addWidget(self._width, 1, 0)
        dimensions.addWidget(QLabel("高度"), 0, 1)
        dimensions.addWidget(self._height, 1, 1)
        dimensions.addWidget(QLabel("FPS"), 0, 2)
        dimensions.addWidget(self._fps, 1, 2)
        output_layout.addLayout(dimensions)
        codec = QLabel("编码：MP4 · H.264 · AAC · 固定全画面覆盖与等增益混音")
        codec.setObjectName("pageSubtitle")
        codec.setWordWrap(True)
        output_layout.addWidget(codec)
        body_layout.addWidget(output_group)

        destination_group = QFrame()
        destination_group.setObjectName("exportFormPanel")
        destination_layout = QVBoxLayout(destination_group)
        destination_layout.setContentsMargins(14, 12, 14, 12)
        destination_layout.setSpacing(10)
        destination_title = QLabel("输出位置")
        destination_title.setProperty("role", "sectionTitle")
        destination_layout.addWidget(destination_title)
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        directory_row = QHBoxLayout()
        self._output_directory = QLineEdit(
            str(defaults.get("directory") or self.context.output_directory)
        )
        self._output_directory.setAccessibleName("导出目录")
        self._output_directory.setToolTip("正式 MP4 和任务临时文件所在目录")
        directory_row.addWidget(self._output_directory, 1)
        self._btn_browse = QPushButton("浏览")
        self._btn_browse.setToolTip("选择本次导出的本地目录")
        set_button_icon(self._btn_browse, "folder")
        self._btn_browse.clicked.connect(self._browse_output_directory)
        directory_row.addWidget(self._btn_browse)
        form.addRow("目录", directory_row)
        self._filename = QLineEdit(f"{self.context.project_name}.mp4")
        self._filename.setAccessibleName("导出文件名")
        self._filename.setToolTip("默认不覆盖；名称冲突时生成安全数字后缀")
        form.addRow("文件名", self._filename)
        destination_layout.addLayout(form)
        self._target_hint = QLabel("")
        self._target_hint.setObjectName("pageSubtitle")
        self._target_hint.setWordWrap(True)
        destination_layout.addWidget(self._target_hint)
        self._overwrite = QCheckBox("覆盖当前同名文件")
        self._overwrite.setToolTip(
            "仅目标已存在时可选；入队前还会要求二次确认并记录目标指纹"
        )
        destination_layout.addWidget(self._overwrite)
        body_layout.addWidget(destination_group)

        self._preflight_panel = QFrame()
        self._preflight_panel.setObjectName("exportPreflightPanel")
        preflight_layout = QVBoxLayout(self._preflight_panel)
        preflight_layout.setContentsMargins(14, 12, 14, 12)
        preflight_layout.setSpacing(5)
        self._preflight_title = QLabel("等待预检")
        self._preflight_title.setProperty("role", "sectionTitle")
        preflight_layout.addWidget(self._preflight_title)
        self._preflight_text = QLabel(
            "预检不会创建队列任务，也不会生成或覆盖视频文件。"
        )
        self._preflight_text.setWordWrap(True)
        preflight_layout.addWidget(self._preflight_text)
        self._preflight_details = QLabel("")
        self._preflight_details.setWordWrap(True)
        self._preflight_details.setObjectName("pageSubtitle")
        preflight_layout.addWidget(self._preflight_details)
        body_layout.addWidget(self._preflight_panel)
        body_layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        self._status = QLabel("只有加入队列后才会持久化任务。")
        self._status.setObjectName("pageSubtitle")
        self._status.setWordWrap(True)
        footer.addWidget(self._status, 1)
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setToolTip("关闭配置，不创建计划或队列任务")
        self._btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self._btn_cancel)
        self._btn_preflight = QPushButton("开始预检")
        self._btn_preflight.setToolTip("校验项目、素材、输出规格、工具和磁盘空间")
        self._btn_preflight.clicked.connect(self.run_preflight)
        footer.addWidget(self._btn_preflight)
        self._btn_enqueue = QPushButton("加入导出队列")
        self._btn_enqueue.setProperty("role", "primary")
        self._btn_enqueue.setToolTip("持久化不可变计划并按当前队列状态调度")
        self._btn_enqueue.clicked.connect(self.enqueue_plan)
        footer.addWidget(self._btn_enqueue)
        root.addLayout(footer)

        for control in (
            self._width,
            self._height,
            self._fps,
            self._output_directory,
            self._filename,
            self._overwrite,
        ):
            signal = (
                control.textChanged
                if isinstance(control, QLineEdit)
                else control.currentTextChanged
                if isinstance(control, QComboBox)
                else control.stateChanged
                if isinstance(control, QCheckBox)
                else control.valueChanged
            )
            signal.connect(self._on_form_changed)

    def _browse_output_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            self._output_directory.text().strip(),
        )
        if selected:
            self._output_directory.setText(selected)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            self.fit_to_available_geometry(screen.availableGeometry())

    def fit_to_available_geometry(self, available: QRect) -> None:
        """让高 DPI 下的表单和固定底栏都保持在可见工作区内。"""
        if not available.isValid():
            return
        margin = 24
        maximum_width = max(480, available.width() - margin * 2)
        maximum_height = max(460, available.height() - margin * 2)
        self.setMinimumSize(
            min(640, maximum_width),
            min(540, maximum_height),
        )
        self.resize(
            min(self.width(), maximum_width),
            min(self.height(), maximum_height),
        )
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _on_form_changed(self, *_args) -> None:
        if self._initializing:
            return
        self.refresh_target_state()
        self._invalidate_preflight()

    def _invalidate_preflight(self) -> None:
        self._plan = None
        self._btn_enqueue.setEnabled(False)
        self._preflight_panel.setProperty("state", "idle")
        style = self._preflight_panel.style()
        if style is not None:
            style.unpolish(self._preflight_panel)
            style.polish(self._preflight_panel)
        if not self.queued_job_id:
            self._preflight_title.setText("等待预检")
            self._preflight_text.setText(
                "预检不会创建队列任务，也不会生成或覆盖视频文件。"
            )
            self._preflight_details.clear()

    @property
    def target_path(self) -> Path:
        return Path(self._output_directory.text().strip()).expanduser() / (
            self._filename.text().strip()
        )

    def refresh_target_state(self) -> None:
        try:
            exists = self.target_path.is_file()
        except OSError:
            exists = False
        self._overwrite.setEnabled(exists)
        if not exists:
            self._overwrite.setChecked(False)
            self._target_hint.setText(
                "目标不存在；任务会创建新文件。若稍后出现冲突，将使用安全后缀。"
            )
        elif self._overwrite.isChecked():
            self._target_hint.setText(
                "目标已存在；预检将记录文件身份，入队前仍需二次确认。"
            )
        else:
            self._target_hint.setText(
                "目标已存在；默认生成安全数字后缀，不覆盖现有文件。"
            )

    def run_preflight(self) -> None:
        self._plan = None
        self._btn_enqueue.setEnabled(False)
        width = self._width.value()
        height = self._height.value()
        fps = int(self._fps.currentText())
        if width % 2 or height % 2:
            self._show_preflight_failure("宽度和高度必须为偶数")
            return
        if fps == 120 and (width > 1920 or height > 1080):
            self._show_preflight_failure(
                "120 FPS 只支持不超过 1920×1080 的画布"
            )
            return
        directory = self._output_directory.text().strip()
        filename = self._filename.text().strip()
        if not directory:
            self._show_preflight_failure("请选择输出目录")
            return
        if not filename:
            self._show_preflight_failure("请输入输出文件名")
            return

        request = ExportPlanRequest(
            project_path=self.context.project_path,
            width=width,
            height=height,
            fps=fps,
            output_directory=directory,
            filename=filename,
            overwrite_mode=(
                OverwriteMode.REPLACE
                if self._overwrite.isChecked()
                else OverwriteMode.DENY
            ),
            accept_safe_suffix=not self._overwrite.isChecked(),
            project_saved=self.context.project_saved,
            save_pending=self.context.save_pending,
            external_conflict=self.context.external_conflict,
            incomplete_job_count=self.context.incomplete_job_count,
            reserved_target_paths=self._reserved_target_paths(),
        )
        result = self.plan_builder.build(request)
        if not result.ok or result.plan is None:
            messages = [
                str(getattr(issue, "message", issue))
                for issue in getattr(result, "errors", ())
            ]
            self._show_preflight_failure(
                "\n".join(messages) or "导出预检未通过"
            )
            suggested = getattr(result, "suggested_filename", None)
            if suggested:
                self._preflight_details.setText(
                    f"建议安全文件名：{suggested}"
                )
            return

        self._plan = result.plan
        warnings = [
            str(getattr(issue, "message", issue))
            for issue in getattr(result, "warnings", ())
        ]
        timeline = result.plan.timeline
        output = result.plan.output
        audio_tracks = sum(
            getattr(track, "kind", "") == "audio"
            for track in timeline.tracks
        )
        estimated = _format_bytes(
            int(getattr(output, "estimated_size_bytes", 0))
        )
        self._preflight_panel.setProperty(
            "state",
            "warning" if warnings else "success",
        )
        self._preflight_title.setText(
            "预检通过，存在提示"
            if warnings
            else "预检通过，可以加入队列"
        )
        self._preflight_text.setText(
            f"时长 {_format_duration(timeline.duration_us)} · "
            f"{len(timeline.clips)} 个片段 · {audio_tracks} 条音频轨 · "
            f"预计 {estimated}"
        )
        self._preflight_details.setText(
            "\n".join(warnings)
            if warnings
            else "项目、素材、工具、输出路径与画布规则均已通过。"
        )
        self._btn_enqueue.setEnabled(not self.queue_service.read_only)
        self._status.setText(
            "ExportPlan 已冻结；加入队列前不会生成正式输出。"
        )
        style = self._preflight_panel.style()
        if style is not None:
            style.unpolish(self._preflight_panel)
            style.polish(self._preflight_panel)

    def _show_preflight_failure(self, message: str) -> None:
        self._preflight_panel.setProperty("state", "error")
        self._preflight_title.setText(message)
        self._preflight_text.setText(
            "请修改导出设置后重新预检；当前没有创建任务。"
        )
        self._preflight_details.clear()
        self._status.setText("预检失败，不会写入队列。")
        style = self._preflight_panel.style()
        if style is not None:
            style.unpolish(self._preflight_panel)
            style.polish(self._preflight_panel)

    def enqueue_plan(self) -> None:
        if self._plan is None:
            self._status.setText("请先完成预检。")
            return
        if self._overwrite.isChecked():
            answer = QMessageBox.question(
                self,
                "确认覆盖已有文件",
                "目标文件已存在。QuickRec 会使用可恢复覆盖事务，"
                "但仍建议确认该文件确实可以被替换。\n\n是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                self._status.setText("已取消覆盖，计划和目标文件均未改变。")
                return
        result = self.queue_service.enqueue(self._plan)
        if not result.ok or result.job is None:
            if (
                result.message
                == "output target is reserved by another incomplete job"
            ):
                self._invalidate_preflight()
                self._status.setText(
                    "输出目标刚被其他任务占用，请重新预检以生成安全后缀。"
                )
            else:
                self._status.setText(
                    f"加入队列失败：{result.message or '队列不可写'}"
                )
            return
        self.queued_job_id = str(result.job.job_id)
        self._status.setText(
            "任务已持久化。关闭此窗口不会取消任务。"
        )
        self._btn_enqueue.setEnabled(False)
        self._btn_preflight.setEnabled(False)
        if not self.queue_service.state.paused:
            self.queue_service.start_worker()
        self.queued.emit(self.queued_job_id)

    def _reserved_target_paths(self) -> tuple[str, ...]:
        state = getattr(self.queue_service, "state", None)
        jobs = getattr(state, "jobs", ())
        return tuple(
            str(job.plan.output.target_path)
            for job in jobs
            if bool(getattr(job, "is_incomplete", False))
        )


def _format_duration(duration_us: int) -> str:
    seconds = max(0, int(duration_us)) / 1_000_000
    minutes, remainder = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remainder:05.2f}"
    return f"{minutes:02d}:{remainder:05.2f}"


def _format_bytes(value: int) -> str:
    amount = max(0, int(value))
    if amount >= 1024**3:
        return f"{amount / 1024**3:.1f} GB"
    if amount >= 1024**2:
        return f"{amount / 1024**2:.1f} MB"
    if amount >= 1024:
        return f"{amount / 1024:.1f} KB"
    return f"{amount} B"


_EXPORT_DIALOG_STYLESHEET = f"""
QDialog#quickrecExportConfig {{
    background: {COLORS["background"]};
}}
QFrame#exportSummaryPanel,
QFrame#exportFormPanel,
QFrame#exportPreflightPanel {{
    background: {COLORS["panel"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
}}
QFrame#exportPreflightPanel[state="success"] {{
    background: {COLORS["green_soft"]};
    border-color: #A7DCC2;
}}
QFrame#exportPreflightPanel[state="warning"] {{
    background: {COLORS["amber_soft"]};
    border-color: #E7C476;
}}
QFrame#exportPreflightPanel[state="error"] {{
    background: {COLORS["red_soft"]};
    border-color: #E8A9A6;
}}
"""
