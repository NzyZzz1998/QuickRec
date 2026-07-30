from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PyQt5.QtCore import QLocale
from PyQt5.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from exporting.models import ExportStage  # noqa: E402
from exporting.queue_store import IngestionStatus  # noqa: E402
from ui.export_page import ExportPage  # noqa: E402

APP = QApplication.instance() or QApplication([])


class FakeQueue:
    def __init__(self, jobs=(), *, paused=True, read_only=False) -> None:
        self.state = SimpleNamespace(jobs=tuple(jobs), paused=paused)
        self.read_only = read_only
        self.calls: list[tuple[str, str | None]] = []

    def pause(self):
        self.calls.append(("pause", None))
        self.state.paused = True
        return SimpleNamespace(ok=True, message="")

    def resume(self):
        self.calls.append(("resume", None))
        self.state.paused = False
        return SimpleNamespace(ok=True, message="")

    def start_worker(self):
        self.calls.append(("start_worker", None))
        return SimpleNamespace(ok=True, message="")

    def cancel(self, job_id: str):
        self.calls.append(("cancel", job_id))
        return SimpleNamespace(ok=True, message="")

    def manual_retry(self, job_id: str):
        self.calls.append(("retry", job_id))
        return SimpleNamespace(ok=True, message="")

    def continue_waiting(self, job_id: str):
        self.calls.append(("continue_waiting", job_id))
        return SimpleNamespace(ok=True, message="")

    def clear_completed(self):
        self.calls.append(("clear_completed", None))
        return SimpleNamespace(ok=True, message="")


class FakeIngestion:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.library_service = SimpleNamespace(
            find_existing=lambda **_kwargs: SimpleNamespace(id="material-export-1")
        )

    def retry(self, job_id: str):
        self.calls.append(("retry", job_id))
        return SimpleNamespace(ok=True, error="")

    def add_to_project(self, job_id: str, project_id: str, *, linker):
        self.calls.append((job_id, project_id))
        return SimpleNamespace(ok=True, error="")


def _job(
    status: ExportStage,
    *,
    job_id: str = "job-1",
    progress: int = 0,
    ingestion: IngestionStatus = IngestionStatus.PENDING,
    stalled: bool = False,
):
    output = SimpleNamespace(
        width=1920,
        height=1080,
        fps=60,
        filename="中文 导出结果.mp4",
        directory=r"E:\导出 结果",
        target_path=Path(r"E:\导出 结果\中文 导出结果.mp4"),
    )
    plan = SimpleNamespace(
        plan_id="plan-1",
        plan_hash="hash-1",
        project=SimpleNamespace(
            project_id="project-1",
            project_name="录屏教程",
        ),
        timeline=SimpleNamespace(
            duration_us=30_000_000,
            clips=(1, 2, 3),
            tracks=(
                SimpleNamespace(kind="video"),
                SimpleNamespace(kind="audio"),
            ),
        ),
        output=output,
        materials=(1, 2),
    )
    return SimpleNamespace(
        job_id=job_id,
        status=status,
        progress_percent=progress,
        eta_seconds=12.5,
        stalled=stalled,
        output_path=(
            str(output.target_path)
            if status == ExportStage.SUCCEEDED
            else None
        ),
        ingestion_status=ingestion,
        ingestion_error=("中央索引只读" if ingestion == IngestionStatus.FAILED else ""),
        failure_kind=None,
        message=("编码器返回非零" if status == ExportStage.FAILED else ""),
        attempts=(),
        created_at="2026-07-29T10:00:00+08:00",
        updated_at="2026-07-29T10:00:10+08:00",
        plan=plan,
    )


def test_export_page_lists_jobs_and_maps_running_state() -> None:
    queue = FakeQueue([_job(ExportStage.RUNNING, progress=42)], paused=False)
    page = ExportPage(queue)

    page.refresh()

    assert page._job_list.count() == 1
    assert page._detail_title.text() == "录屏教程"
    assert page._status_badge.text() == "正在导出"
    assert page._progress.value() == 42
    assert "预计剩余" in page._progress_meta.text()
    assert page._btn_cancel.isEnabled()
    assert not page._btn_retry.isEnabled()


def test_export_progress_always_uses_ascii_digits() -> None:
    page = ExportPage(FakeQueue())

    assert page._progress.locale().language() == QLocale.C


def test_export_page_exposes_stall_warning_and_continue_waiting_action() -> None:
    job = _job(ExportStage.RUNNING, progress=42, stalled=True)
    queue = FakeQueue([job], paused=False)
    page = ExportPage(queue)

    page.refresh()

    assert page._status_badge.text() == "可能停滞"
    assert "超过 120 秒" in page._stage.text()
    assert page._btn_continue_waiting.isVisibleTo(page)
    assert page._btn_continue_waiting.isEnabled()

    page._btn_continue_waiting.click()

    assert ("continue_waiting", "job-1") in queue.calls
    assert "继续等待" in page._feedback.text()


def test_export_page_maps_success_and_ingestion_failure_independently(
    tmp_path: Path,
) -> None:
    job = _job(
        ExportStage.SUCCEEDED,
        progress=100,
        ingestion=IngestionStatus.FAILED,
    )
    output = tmp_path / "中文 导出结果.mp4"
    output.write_bytes(b"video")
    job.output_path = str(output)
    job.plan.output.target_path = output
    queue = FakeQueue([job], paused=True)
    ingestion = FakeIngestion()
    page = ExportPage(queue, ingestion_coordinator=ingestion)

    page.refresh()

    assert page._status_badge.text() == "导出成功"
    assert "入库失败" in page._ingestion_status.text()
    assert page._btn_open_file.isEnabled()
    assert page._btn_retry_ingestion.isEnabled()
    assert page._btn_add_project.isEnabled() is False

    page._btn_retry_ingestion.click()

    assert ingestion.calls == [("retry", "job-1")]


def test_export_page_pause_resume_and_manual_retry_use_queue_service() -> None:
    failed = _job(ExportStage.FAILED)
    queue = FakeQueue([failed], paused=True)
    page = ExportPage(queue)
    page.refresh()

    assert page._btn_queue.text() == "继续队列"
    page._btn_queue.click()
    assert queue.calls[:2] == [("resume", None), ("start_worker", None)]

    page.refresh()
    assert page._btn_queue.text() == "完成当前任务后暂停"
    page._btn_retry.click()
    assert ("retry", "job-1") in queue.calls
    assert ("start_worker", None) in queue.calls


def test_export_page_read_only_state_disables_mutating_actions() -> None:
    queue = FakeQueue([_job(ExportStage.INTERRUPTED)], read_only=True)
    page = ExportPage(queue)

    page.refresh()

    assert "只读" in page._health_banner.text()
    assert not page._btn_queue.isEnabled()
    assert not page._btn_retry.isEnabled()
    assert not page._btn_cancel.isEnabled()


def test_export_page_filters_finished_and_preserves_selected_job() -> None:
    running = _job(ExportStage.RUNNING, job_id="job-running")
    succeeded = _job(ExportStage.SUCCEEDED, job_id="job-success")
    queue = FakeQueue([running, succeeded])
    page = ExportPage(queue)
    page.refresh()
    page.select_job("job-success")

    page.set_filter("finished")

    assert page._job_list.count() == 1
    assert page._selected_job_id == "job-success"
    assert page._detail_title.text() == "录屏教程"


def test_export_page_exposes_material_navigation_and_export_again(
    tmp_path: Path,
) -> None:
    job = _job(
        ExportStage.SUCCEEDED,
        progress=100,
        ingestion=IngestionStatus.SUCCEEDED,
    )
    output = tmp_path / "中文 导出结果.mp4"
    output.write_bytes(b"video")
    job.output_path = str(output)
    job.plan.output.target_path = output
    queue = FakeQueue([job])
    ingestion = FakeIngestion()
    page = ExportPage(
        queue,
        ingestion_coordinator=ingestion,
        project_linker=object(),
    )
    material_ids: list[str] = []
    project_ids: list[str] = []
    page.show_material_requested.connect(material_ids.append)
    page.new_export_requested.connect(project_ids.append)

    page.refresh()
    page._btn_show_material.click()
    page._btn_export_again.click()

    assert material_ids == ["material-export-1"]
    assert project_ids == ["project-1"]
    assert page._btn_show_material.toolTip()
    assert page._btn_export_again.toolTip()
