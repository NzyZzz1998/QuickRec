"""QuickRec v1.9.4 持久导出队列工作台页面。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt5.QtCore import QLocale, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QGuiApplication
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from exporting.models import ExportStage
from exporting.queue_service import ExportQueueService
from exporting.queue_store import IngestionStatus
from ui.design_system import (
    set_button_icon,
)

_STATUS_LABELS = {
    ExportStage.QUEUED: "等待导出",
    ExportStage.VALIDATING: "正在校验",
    ExportStage.RUNNING: "正在导出",
    ExportStage.CANCELLING: "正在取消",
    ExportStage.VERIFYING: "正在验证",
    ExportStage.COMMITTING: "正在安全提交",
    ExportStage.SUCCEEDED: "导出成功",
    ExportStage.FAILED: "导出失败",
    ExportStage.CANCELLED: "已取消",
    ExportStage.INTERRUPTED: "已中断",
}
_ACTIVE_STAGES = {
    ExportStage.VALIDATING,
    ExportStage.RUNNING,
    ExportStage.VERIFYING,
}
_RETRYABLE_STAGES = {
    ExportStage.FAILED,
    ExportStage.CANCELLED,
    ExportStage.INTERRUPTED,
}


class ExportPage(QWidget):
    """展示全局导出任务，并把所有写操作委托给应用服务。"""

    new_export_requested = pyqtSignal(object)
    open_diagnostics_requested = pyqtSignal(str)
    show_material_requested = pyqtSignal(str)
    feedback_changed = pyqtSignal(str)

    JOB_ID_ROLE = Qt.UserRole + 41

    def __init__(
        self,
        queue_service: ExportQueueService,
        *,
        ingestion_coordinator: Any | None = None,
        project_linker: Any | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("exportPage")
        self.queue_service = queue_service
        self.ingestion_coordinator = ingestion_coordinator
        self.project_linker = project_linker
        self._selected_job_id: str | None = None
        self._jobs_by_id: dict[str, Any] = {}
        self._filter = "all"
        self._init_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.refresh)
        self.refresh()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(12)

        title_row = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("导出")
        title.setObjectName("pageTitle")
        title_block.addWidget(title)
        subtitle = QLabel("创建、监控并恢复项目的本地 MP4 导出任务。")
        subtitle.setObjectName("pageSubtitle")
        title_block.addWidget(subtitle)
        title_row.addLayout(title_block, 1)
        self._btn_open_default = QPushButton("打开导出目录")
        self._btn_open_default.setToolTip("打开当前所选任务的输出目录")
        set_button_icon(self._btn_open_default, "folder")
        self._btn_open_default.clicked.connect(self._open_selected_directory)
        title_row.addWidget(self._btn_open_default)
        self._btn_new = QPushButton("新建导出")
        self._btn_new.setProperty("role", "primary")
        self._btn_new.setToolTip("从当前项目或最近项目创建不可变导出计划")
        set_button_icon(self._btn_new, "file", color="#FFFFFF")
        self._btn_new.clicked.connect(
            lambda: self.new_export_requested.emit(None)
        )
        title_row.addWidget(self._btn_new)
        root.addLayout(title_row)

        self._health_banner = QLabel("")
        self._health_banner.setObjectName("exportHealthBanner")
        self._health_banner.setWordWrap(True)
        self._health_banner.hide()
        root.addWidget(self._health_banner)

        summary_row = QHBoxLayout()
        self._queue_summary = QLabel("")
        self._queue_summary.setObjectName("pageSubtitle")
        summary_row.addWidget(self._queue_summary, 1)
        self._btn_queue = QPushButton("继续队列")
        self._btn_queue.setToolTip(
            "继续时按顺序启动排队任务；暂停只阻止启动下一个任务"
        )
        self._btn_queue.clicked.connect(self._toggle_queue)
        summary_row.addWidget(self._btn_queue)
        self._btn_clear = QPushButton("清除已完成")
        self._btn_clear.setToolTip("只清理成功和取消的队列记录，不删除视频")
        self._btn_clear.clicked.connect(self._clear_completed)
        summary_row.addWidget(self._btn_clear)
        root.addLayout(summary_row)

        filters = QHBoxLayout()
        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        for key, label in (
            ("all", "全部"),
            ("unfinished", "进行中"),
            ("failed", "需处理"),
            ("finished", "已完成"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("role", "segment")
            button.setToolTip(f"只显示{label}导出任务")
            button.clicked.connect(
                lambda _checked=False, target=key: self.set_filter(target)
            )
            self._filter_group.addButton(button)
            filters.addWidget(button)
            if key == "all":
                button.setChecked(True)
        filters.addStretch()
        self._btn_refresh = QPushButton()
        self._btn_refresh.setFixedSize(34, 34)
        self._btn_refresh.setAccessibleName("刷新导出队列")
        self._btn_refresh.setToolTip("重新读取当前进程中的导出队列状态")
        set_button_icon(self._btn_refresh, "refresh")
        self._btn_refresh.clicked.connect(self.refresh)
        filters.addWidget(self._btn_refresh)
        root.addLayout(filters)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        self._job_list = QListWidget()
        self._job_list.setObjectName("exportJobList")
        self._job_list.setMinimumWidth(270)
        self._job_list.setMaximumWidth(390)
        self._job_list.setAccessibleName("导出任务列表")
        self._job_list.currentItemChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._job_list)
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([330, 680])
        root.addWidget(splitter, 1)

        self._feedback = QLabel("")
        self._feedback.setObjectName("pageSubtitle")
        self._feedback.setWordWrap(True)
        root.addWidget(self._feedback)

    def _build_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("exportDetailPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        heading = QHBoxLayout()
        title_block = QVBoxLayout()
        self._detail_title = QLabel("选择一个导出任务")
        self._detail_title.setProperty("role", "sectionTitle")
        self._detail_title.setWordWrap(True)
        title_block.addWidget(self._detail_title)
        self._detail_subtitle = QLabel("任务详情、阶段和结果操作会显示在这里。")
        self._detail_subtitle.setObjectName("pageSubtitle")
        self._detail_subtitle.setWordWrap(True)
        title_block.addWidget(self._detail_subtitle)
        heading.addLayout(title_block, 1)
        self._status_badge = QLabel("无任务")
        self._status_badge.setObjectName("exportStatusBadge")
        heading.addWidget(self._status_badge, 0, Qt.AlignTop)
        layout.addLayout(heading)

        self._stage = QLabel("等待任务")
        self._stage.setObjectName("exportStageTitle")
        self._stage.setWordWrap(True)
        layout.addWidget(self._stage)
        self._progress = QProgressBar()
        self._progress.setLocale(QLocale.c())
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setAccessibleName("导出进度")
        layout.addWidget(self._progress)
        self._progress_meta = QLabel("")
        self._progress_meta.setObjectName("pageSubtitle")
        layout.addWidget(self._progress_meta)

        self._plan_summary = QLabel("")
        self._plan_summary.setWordWrap(True)
        self._plan_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._plan_summary)
        self._output_path = QLabel("")
        self._output_path.setObjectName("pageSubtitle")
        self._output_path.setWordWrap(True)
        self._output_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._output_path)
        self._ingestion_status = QLabel("")
        self._ingestion_status.setWordWrap(True)
        layout.addWidget(self._ingestion_status)
        self._failure = QLabel("")
        self._failure.setObjectName("exportFailureText")
        self._failure.setWordWrap(True)
        layout.addWidget(self._failure)
        layout.addStretch()

        actions_1 = QHBoxLayout()
        self._btn_continue_waiting = QPushButton("继续等待")
        self._btn_continue_waiting.setToolTip(
            "重置停滞计时并继续当前导出；不会重新编码或创建新任务"
        )
        set_button_icon(self._btn_continue_waiting, "play")
        self._btn_continue_waiting.clicked.connect(self._continue_waiting)
        self._btn_continue_waiting.hide()
        actions_1.addWidget(self._btn_continue_waiting)
        self._btn_cancel = QPushButton("取消任务")
        self._btn_cancel.setToolTip(
            "排队任务直接取消；运行任务安全终止；提交阶段不可取消"
        )
        self._btn_cancel.clicked.connect(self._cancel_selected)
        actions_1.addWidget(self._btn_cancel)
        self._btn_retry = QPushButton("重试导出")
        self._btn_retry.setToolTip("基于同一不可变计划创建下一次尝试")
        set_button_icon(self._btn_retry, "refresh")
        self._btn_retry.clicked.connect(self._retry_selected)
        actions_1.addWidget(self._btn_retry)
        self._btn_diagnostics = QPushButton("查看诊断")
        self._btn_diagnostics.setToolTip("定位本任务最近尝试的本地诊断上下文")
        self._btn_diagnostics.clicked.connect(self._open_diagnostics)
        actions_1.addWidget(self._btn_diagnostics)
        actions_1.addStretch()
        layout.addLayout(actions_1)

        actions_2 = QHBoxLayout()
        self._btn_open_file = QPushButton("打开文件")
        self._btn_open_file.setToolTip("使用系统默认播放器打开已提交 MP4")
        set_button_icon(self._btn_open_file, "play")
        self._btn_open_file.clicked.connect(self._open_selected_file)
        actions_2.addWidget(self._btn_open_file)
        self._btn_open_folder = QPushButton("打开目录")
        self._btn_open_folder.setToolTip("打开任务输出目录")
        set_button_icon(self._btn_open_folder, "folder")
        self._btn_open_folder.clicked.connect(self._open_selected_directory)
        actions_2.addWidget(self._btn_open_folder)
        self._btn_copy_path = QPushButton("复制路径")
        self._btn_copy_path.setToolTip("复制正式输出的完整本地路径")
        set_button_icon(self._btn_copy_path, "copy")
        self._btn_copy_path.clicked.connect(self._copy_selected_path)
        actions_2.addWidget(self._btn_copy_path)
        actions_2.addStretch()
        layout.addLayout(actions_2)

        actions_3 = QHBoxLayout()
        self._btn_show_material = QPushButton("查看素材")
        self._btn_show_material.setToolTip(
            "打开工作台素材库并定位本次导出结果"
        )
        set_button_icon(self._btn_show_material, "library")
        self._btn_show_material.clicked.connect(self._show_material)
        actions_3.addWidget(self._btn_show_material)
        self._btn_retry_ingestion = QPushButton("重试入库")
        self._btn_retry_ingestion.setToolTip(
            "只重试中央素材索引写入，不重新编码"
        )
        self._btn_retry_ingestion.clicked.connect(self._retry_ingestion)
        actions_3.addWidget(self._btn_retry_ingestion)
        self._btn_add_project = QPushButton("加入当前项目")
        self._btn_add_project.setToolTip(
            "把已入库导出结果显式加入原项目，不修改时间线"
        )
        self._btn_add_project.clicked.connect(self._add_to_project)
        actions_3.addWidget(self._btn_add_project)
        self._btn_export_again = QPushButton("再次导出")
        self._btn_export_again.setToolTip(
            "以原项目的最新已保存时间线重新打开导出配置，不复用旧快照"
        )
        set_button_icon(self._btn_export_again, "refresh")
        self._btn_export_again.clicked.connect(self._export_again)
        actions_3.addWidget(self._btn_export_again)
        actions_3.addStretch()
        layout.addLayout(actions_3)
        return panel

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def set_filter(self, name: str) -> None:
        if name not in {"all", "unfinished", "failed", "finished"}:
            raise ValueError(f"unknown export filter: {name}")
        self._filter = name
        self.refresh()

    def refresh(self) -> None:
        state = self.queue_service.state
        jobs = tuple(state.jobs)
        self._jobs_by_id = {job.job_id: job for job in jobs}
        self._queue_summary.setText(
            f"{len(jobs)} 个任务 · "
            f"{sum(job.status == ExportStage.QUEUED for job in jobs)} 个排队 · "
            f"{sum(job.status in _ACTIVE_STAGES for job in jobs)} 个运行中"
        )
        self._btn_queue.setText(
            "继续队列" if state.paused else "完成当前任务后暂停"
        )
        self._health_banner.setVisible(self.queue_service.read_only)
        self._health_banner.setText(
            "导出队列当前为只读状态。可以查看已有任务，但不能新增、"
            "取消、重试或清理。请查看诊断后再处理。"
            if self.queue_service.read_only
            else ""
        )
        self._btn_queue.setEnabled(not self.queue_service.read_only)
        self._btn_clear.setEnabled(
            not self.queue_service.read_only
            and any(
                job.status in {ExportStage.SUCCEEDED, ExportStage.CANCELLED}
                for job in jobs
            )
        )
        self._btn_new.setEnabled(not self.queue_service.read_only)

        visible_jobs = [job for job in reversed(jobs) if self._matches(job)]
        selected = self._selected_job_id
        self._job_list.blockSignals(True)
        self._job_list.clear()
        for job in visible_jobs:
            item = QListWidgetItem(self._job_text(job))
            item.setData(self.JOB_ID_ROLE, job.job_id)
            item.setToolTip(
                f"{job.plan.output.target_path}\n"
                f"任务 {job.job_id} · 计划 {job.plan.plan_id}"
            )
            self._job_list.addItem(item)
            if job.job_id == selected:
                self._job_list.setCurrentItem(item)
        self._job_list.blockSignals(False)

        if (
            selected is None
            or selected not in self._jobs_by_id
            or not any(job.job_id == selected for job in visible_jobs)
        ):
            selected = visible_jobs[0].job_id if visible_jobs else None
        self._selected_job_id = selected
        if selected is not None:
            self.select_job(selected)
        else:
            self._show_empty_detail()

    def _matches(self, job: Any) -> bool:
        if self._filter == "all":
            return True
        if self._filter == "unfinished":
            return job.status not in {
                ExportStage.SUCCEEDED,
                ExportStage.CANCELLED,
                ExportStage.FAILED,
                ExportStage.INTERRUPTED,
            }
        if self._filter == "failed":
            return job.status in {ExportStage.FAILED, ExportStage.INTERRUPTED}
        return job.status in {ExportStage.SUCCEEDED, ExportStage.CANCELLED}

    def _job_text(self, job: Any) -> str:
        status = (
            "可能停滞"
            if getattr(job, "stalled", False)
            else _STATUS_LABELS.get(job.status, str(job.status))
        )
        progress = (
            f" · {job.progress_percent}%"
            if job.status in _ACTIVE_STAGES
            else ""
        )
        return (
            f"{job.plan.project.project_name}\n"
            f"{job.plan.output.filename} · {status}{progress}"
        )

    def _on_selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        self.select_job(str(current.data(self.JOB_ID_ROLE)))

    def select_job(self, job_id: str) -> None:
        job = self._jobs_by_id.get(job_id)
        if job is None:
            return
        self._selected_job_id = job_id
        for row in range(self._job_list.count()):
            item = self._job_list.item(row)
            if item is not None and str(item.data(self.JOB_ID_ROLE)) == job_id:
                self._job_list.blockSignals(True)
                self._job_list.setCurrentItem(item)
                self._job_list.blockSignals(False)
                break
        self._render_job(job)

    def _render_job(self, job: Any) -> None:
        plan = job.plan
        self._detail_title.setText(plan.project.project_name)
        self._detail_subtitle.setText(
            f"{job.job_id} · 冻结计划 {plan.plan_id}"
        )
        stalled = bool(getattr(job, "stalled", False))
        self._status_badge.setText(
            "可能停滞"
            if stalled
            else _STATUS_LABELS.get(job.status, str(job.status))
        )
        self._status_badge.setProperty(
            "state",
            "stalled" if stalled else job.status.value,
        )
        style = self._status_badge.style()
        if style is not None:
            style.unpolish(self._status_badge)
            style.polish(self._status_badge)
        self._stage.setText(_stage_text(job))
        self._progress.setValue(int(job.progress_percent))
        self._progress.setVisible(
            job.status in _ACTIVE_STAGES
            or job.status in {
                ExportStage.CANCELLING,
                ExportStage.COMMITTING,
                ExportStage.SUCCEEDED,
            }
        )
        self._progress_meta.setText(
            (
                "进度已超过 120 秒未更新，可继续等待或取消任务。"
                if stalled
                else
                f"当前 {job.progress_percent}% · "
                f"预计剩余 {_format_seconds(job.eta_seconds)}"
            )
            if job.status in _ACTIVE_STAGES
            else ""
        )
        audio_tracks = sum(
            getattr(track, "kind", "") == "audio"
            for track in plan.timeline.tracks
        )
        self._plan_summary.setText(
            f"输出 {plan.output.width}×{plan.output.height} · "
            f"{plan.output.fps} FPS · "
            f"{len(plan.timeline.clips)} 个片段 · {audio_tracks} 路音频 · "
            f"时长 {_format_duration(plan.timeline.duration_us)}"
        )
        target = str(job.output_path or plan.output.target_path)
        self._output_path.setText(f"输出：{target}")
        self._ingestion_status.setText(_ingestion_text(job))
        self._failure.setText(job.message if job.message else "")

        writable = not self.queue_service.read_only
        self._btn_continue_waiting.setVisible(stalled)
        self._btn_continue_waiting.setEnabled(
            writable and stalled and job.status == ExportStage.RUNNING
        )
        self._btn_cancel.setEnabled(
            writable
            and (
                job.status == ExportStage.QUEUED
                or job.status in _ACTIVE_STAGES
                or job.status == ExportStage.CANCELLING
            )
            and job.status != ExportStage.COMMITTING
        )
        self._btn_retry.setEnabled(
            writable and job.status in _RETRYABLE_STAGES
        )
        has_output = bool(job.output_path) and Path(job.output_path).is_file()
        self._btn_open_file.setEnabled(has_output)
        self._btn_open_folder.setEnabled(
            bool(job.output_path) or bool(plan.output.directory)
        )
        self._btn_open_default.setEnabled(
            bool(job.output_path) or bool(plan.output.directory)
        )
        self._btn_copy_path.setEnabled(bool(job.output_path))
        self._btn_retry_ingestion.setEnabled(
            writable
            and self.ingestion_coordinator is not None
            and job.status == ExportStage.SUCCEEDED
            and job.ingestion_status == IngestionStatus.FAILED
        )
        self._btn_add_project.setEnabled(
            writable
            and self.ingestion_coordinator is not None
            and self.project_linker is not None
            and job.status == ExportStage.SUCCEEDED
            and job.ingestion_status == IngestionStatus.SUCCEEDED
        )
        self._btn_show_material.setEnabled(
            self._material_id_for_job(job) is not None
        )
        self._btn_export_again.setEnabled(
            writable and bool(plan.project.project_id)
        )
        self._btn_diagnostics.setEnabled(True)

    def _show_empty_detail(self) -> None:
        self._detail_title.setText("还没有导出任务")
        self._detail_subtitle.setText(
            "从项目时间线创建导出任务；关闭工作台不会取消后台队列。"
        )
        self._status_badge.setText("空队列")
        self._stage.setText("等待创建任务")
        self._progress.hide()
        self._progress_meta.clear()
        self._plan_summary.clear()
        self._output_path.clear()
        self._ingestion_status.clear()
        self._failure.clear()
        for button in (
            self._btn_continue_waiting,
            self._btn_cancel,
            self._btn_retry,
            self._btn_diagnostics,
            self._btn_open_file,
            self._btn_open_folder,
            self._btn_copy_path,
            self._btn_retry_ingestion,
            self._btn_add_project,
            self._btn_show_material,
            self._btn_export_again,
        ):
            button.setEnabled(False)
        self._btn_continue_waiting.hide()

    def _selected_job(self) -> Any | None:
        if self._selected_job_id is None:
            return None
        return self._jobs_by_id.get(self._selected_job_id)

    def _toggle_queue(self) -> None:
        if self.queue_service.state.paused:
            result = self.queue_service.resume()
            if result.ok:
                self.queue_service.start_worker()
        else:
            result = self.queue_service.pause()
        self._set_feedback(
            "队列状态已更新"
            if result.ok
            else f"队列操作失败：{result.message}"
        )
        self.refresh()

    def _clear_completed(self) -> None:
        result = self.queue_service.clear_completed()
        self._set_feedback(
            "已清除完成记录；正式视频未删除"
            if result.ok
            else f"清理失败：{result.message}"
        )
        self.refresh()

    def _cancel_selected(self) -> None:
        job = self._selected_job()
        if job is None:
            return
        answer = QMessageBox.question(
            self,
            "确认取消导出",
            "取消不会删除源素材。运行中的任务会先安全终止并清理本次临时文件。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        result = self.queue_service.cancel(job.job_id)
        self._set_feedback(
            "取消请求已提交"
            if result.ok
            else f"无法取消：{result.message}"
        )
        self.refresh()

    def _continue_waiting(self) -> None:
        job = self._selected_job()
        if job is None:
            return
        result = self.queue_service.continue_waiting(job.job_id)
        self._set_feedback(
            "已继续等待；停滞计时已重新开始"
            if result.ok
            else f"无法继续等待：{result.message}"
        )
        self.refresh()

    def _retry_selected(self) -> None:
        job = self._selected_job()
        if job is None:
            return
        result = self.queue_service.manual_retry(job.job_id)
        if result.ok and not self.queue_service.state.paused:
            self.queue_service.start_worker()
        self._set_feedback(
            "任务已重新排队"
            if result.ok
            else f"无法重试：{result.message}"
        )
        self.refresh()

    def _retry_ingestion(self) -> None:
        job = self._selected_job()
        if job is None or self.ingestion_coordinator is None:
            return
        result = self.ingestion_coordinator.retry(job.job_id)
        self._set_feedback(
            "中央素材入库已恢复"
            if result.ok
            else f"入库仍失败：{result.error}"
        )
        self.refresh()

    def _add_to_project(self) -> None:
        job = self._selected_job()
        if (
            job is None
            or self.ingestion_coordinator is None
            or self.project_linker is None
        ):
            return
        result = self.ingestion_coordinator.add_to_project(
            job.job_id,
            job.plan.project.project_id,
            linker=self.project_linker,
        )
        self._set_feedback(
            "导出结果已加入项目"
            if result.ok
            else f"加入项目失败：{result.error}"
        )

    def _material_id_for_job(self, job: Any) -> str | None:
        coordinator = self.ingestion_coordinator
        library = getattr(coordinator, "library_service", None)
        finder = getattr(library, "find_existing", None)
        if (
            job.status != ExportStage.SUCCEEDED
            or job.ingestion_status != IngestionStatus.SUCCEEDED
            or not job.output_path
            or not callable(finder)
        ):
            return None
        material = finder(file_path=job.output_path)
        material_id = str(getattr(material, "id", "") or "")
        return material_id or None

    def _show_material(self) -> None:
        job = self._selected_job()
        if job is None:
            return
        material_id = self._material_id_for_job(job)
        if material_id is None:
            self._set_feedback("导出结果尚未出现在中央素材库")
            return
        self.show_material_requested.emit(material_id)

    def _export_again(self) -> None:
        job = self._selected_job()
        if job is None:
            return
        self.new_export_requested.emit(job.plan.project.project_id)

    def _open_selected_file(self) -> None:
        job = self._selected_job()
        if job is None or not job.output_path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(job.output_path)))

    def _open_selected_directory(self) -> None:
        job = self._selected_job()
        if job is None:
            return
        target = Path(job.output_path or job.plan.output.target_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.parent)))

    def _copy_selected_path(self) -> None:
        job = self._selected_job()
        if job is None or not job.output_path:
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(job.output_path))
            self._set_feedback("完整输出路径已复制")

    def _open_diagnostics(self) -> None:
        job = self._selected_job()
        if job is None:
            return
        path = next(
            (
                attempt.diagnostic_path
                for attempt in reversed(job.attempts)
                if attempt.diagnostic_path
            ),
            None,
        )
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            self.open_diagnostics_requested.emit(job.job_id)

    def _set_feedback(self, message: str) -> None:
        self._feedback.setText(message)
        self.feedback_changed.emit(message)


def _stage_text(job: Any) -> str:
    if getattr(job, "stalled", False):
        return "导出进度已超过 120 秒未更新；请选择继续等待或取消任务"
    mapping = {
        ExportStage.QUEUED: "任务已持久化，等待单工作线程调度",
        ExportStage.VALIDATING: "正在校验素材指纹、工具和输出目标",
        ExportStage.RUNNING: "正在编码视频并混合时间线音频",
        ExportStage.CANCELLING: "正在终止子进程并清理本次临时文件",
        ExportStage.VERIFYING: "FFmpeg 已结束，正在使用 FFprobe 验证正式输出",
        ExportStage.COMMITTING: "正在安全提交输出；当前阶段不可取消",
        ExportStage.SUCCEEDED: "正式 MP4 已完成原子提交",
        ExportStage.FAILED: "本次尝试失败，可查看诊断后重试",
        ExportStage.CANCELLED: "任务已取消，源素材未改变",
        ExportStage.INTERRUPTED: "应用或系统中断了任务，需要显式重试",
    }
    return mapping.get(job.status, str(job.status))


def _ingestion_text(job: Any) -> str:
    if job.status != ExportStage.SUCCEEDED:
        return "中央素材入库将在导出成功后执行。"
    if job.ingestion_status == IngestionStatus.SUCCEEDED:
        return "中央素材库：已入库。可显式加入原项目。"
    if job.ingestion_status == IngestionStatus.FAILED:
        detail = f"（{job.ingestion_error}）" if job.ingestion_error else ""
        return f"中央素材库：入库失败{detail}。导出文件仍然成功。"
    if job.ingestion_status == IngestionStatus.NOT_REQUIRED:
        return "中央素材库：无需入库。"
    return "中央素材库：等待入库。"


def _format_duration(duration_us: int) -> str:
    total = max(0, int(duration_us)) / 1_000_000
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(int(minutes), 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"
    return f"{minutes:02d}:{seconds:05.2f}"


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "计算中"
    seconds = max(0, int(round(value)))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"
