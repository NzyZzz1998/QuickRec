from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PyQt5.QtCore import QLocale, QRect
from PyQt5.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from exporting.models import OverwriteMode  # noqa: E402
from ui.export_dialogs import ExportConfigDialog, ExportDialogContext  # noqa: E402

APP = QApplication.instance() or QApplication([])


class FakeBuilder:
    def __init__(self) -> None:
        self.requests = []
        self.result = SimpleNamespace(
            ok=True,
            plan=SimpleNamespace(
                plan_id="plan-1",
                project=SimpleNamespace(project_id="project-1"),
                timeline=SimpleNamespace(
                    duration_us=30_000_000,
                    clips=(1, 2, 3),
                    tracks=(
                        SimpleNamespace(kind="video"),
                        SimpleNamespace(kind="audio"),
                    ),
                ),
                output=SimpleNamespace(
                    estimated_size_bytes=80 * 1024 * 1024,
                    target_path=Path(r"E:\Exports\demo.mp4"),
                ),
                materials=(1, 2),
            ),
            errors=(),
            warnings=(),
            suggested_filename=None,
        )

    def build(self, request):
        self.requests.append(request)
        return self.result


class FakeQueue:
    def __init__(self, *, paused=False) -> None:
        self.state = SimpleNamespace(paused=paused, jobs=())
        self.read_only = False
        self.enqueued = []
        self.worker_started = 0

    def enqueue(self, plan):
        self.enqueued.append(plan)
        return SimpleNamespace(
            ok=True,
            message="",
            job=SimpleNamespace(job_id="job-1"),
        )

    def start_worker(self):
        self.worker_started += 1
        return SimpleNamespace(ok=True, message="")


def _context(tmp_path: Path) -> ExportDialogContext:
    return ExportDialogContext(
        project_id="project-1",
        project_name="录屏教程",
        project_path=str(tmp_path / "录屏 教程.qrproj"),
        output_directory=str(tmp_path / "导出 结果"),
        project_saved=True,
        save_pending=False,
        external_conflict=False,
        incomplete_job_count=0,
    )


def test_export_config_preflight_builds_controlled_request(tmp_path: Path) -> None:
    builder = FakeBuilder()
    queue = FakeQueue()
    dialog = ExportConfigDialog(
        _context(tmp_path),
        plan_builder=builder,
        queue_service=queue,
    )
    dialog._width.setValue(1920)
    dialog._height.setValue(1080)
    dialog._fps.setCurrentText("60")
    dialog._filename.setText("演示 导出.mp4")

    dialog.run_preflight()

    request = builder.requests[-1]
    assert request.project_path.endswith("录屏 教程.qrproj")
    assert request.width == 1920
    assert request.height == 1080
    assert request.fps == 60
    assert request.filename == "演示 导出.mp4"
    assert request.overwrite_mode == OverwriteMode.DENY
    assert request.accept_safe_suffix is True
    assert dialog._btn_enqueue.isEnabled()
    assert "预检通过" in dialog._preflight_title.text()


def test_export_dimensions_always_use_ascii_digits(tmp_path: Path) -> None:
    dialog = ExportConfigDialog(
        _context(tmp_path),
        plan_builder=FakeBuilder(),
        queue_service=FakeQueue(),
        defaults={"width": 1920, "height": 1080},
    )

    assert dialog._width.locale().language() == QLocale.C
    assert dialog._height.locale().language() == QLocale.C
    assert dialog._width.text() == "1920"
    assert dialog._height.text() == "1080"


def test_export_config_rejects_120_fps_above_1080p_without_builder(
    tmp_path: Path,
) -> None:
    builder = FakeBuilder()
    dialog = ExportConfigDialog(
        _context(tmp_path),
        plan_builder=builder,
        queue_service=FakeQueue(),
    )
    dialog._width.setValue(2560)
    dialog._height.setValue(1440)
    dialog._fps.setCurrentText("120")

    dialog.run_preflight()

    assert builder.requests == []
    assert "120 FPS" in dialog._preflight_title.text()
    assert not dialog._btn_enqueue.isEnabled()


def test_overwrite_is_only_available_for_existing_target(tmp_path: Path) -> None:
    context = _context(tmp_path)
    output_dir = Path(context.output_directory)
    output_dir.mkdir(parents=True)
    dialog = ExportConfigDialog(
        context,
        plan_builder=FakeBuilder(),
        queue_service=FakeQueue(),
    )
    dialog._filename.setText("demo.mp4")
    dialog.refresh_target_state()
    assert not dialog._overwrite.isEnabled()

    (output_dir / "demo.mp4").write_bytes(b"existing")
    dialog.refresh_target_state()

    assert dialog._overwrite.isEnabled()
    assert not dialog._overwrite.isChecked()


def test_explicit_overwrite_requires_second_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context = _context(tmp_path)
    output_dir = Path(context.output_directory)
    output_dir.mkdir(parents=True)
    (output_dir / "demo.mp4").write_bytes(b"existing")
    builder = FakeBuilder()
    queue = FakeQueue()
    dialog = ExportConfigDialog(
        context,
        plan_builder=builder,
        queue_service=queue,
    )
    dialog._filename.setText("demo.mp4")
    dialog.refresh_target_state()
    dialog._overwrite.setChecked(True)
    dialog.run_preflight()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.No,
    )
    dialog.enqueue_plan()
    assert queue.enqueued == []

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.Yes,
    )
    dialog.enqueue_plan()
    assert len(queue.enqueued) == 1


def test_enqueue_starts_worker_only_when_queue_is_enabled(tmp_path: Path) -> None:
    builder = FakeBuilder()
    queue = FakeQueue(paused=False)
    dialog = ExportConfigDialog(
        _context(tmp_path),
        plan_builder=builder,
        queue_service=queue,
    )
    dialog.run_preflight()
    dialog.enqueue_plan()

    assert len(queue.enqueued) == 1
    assert queue.worker_started == 1
    assert dialog.queued_job_id == "job-1"


def test_export_dialog_fits_footer_inside_small_available_geometry(
    tmp_path: Path,
) -> None:
    dialog = ExportConfigDialog(
        _context(tmp_path),
        plan_builder=FakeBuilder(),
        queue_service=FakeQueue(),
    )

    dialog.fit_to_available_geometry(QRect(0, 0, 900, 640))
    dialog.show()
    APP.processEvents()

    assert dialog.width() <= 852
    assert dialog.height() <= 592
    assert dialog.minimumHeight() <= 560
    footer_bottom = dialog._btn_enqueue.mapTo(dialog, dialog._btn_enqueue.rect().bottomRight()).y()
    assert footer_bottom <= dialog.contentsRect().bottom()
    dialog.close()
