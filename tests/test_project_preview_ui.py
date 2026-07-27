from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtCore import QPoint  # noqa: E402
from PyQt5.QtGui import QColor, QImage  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

from services.project_library import ProjectLibraryService  # noqa: E402
from services.project_materials import (  # noqa: E402
    PreviewState,
    ProjectMaterialDescriptor,
)
from services.recording_library import RecordingLibraryService  # noqa: E402
from ui.material_library_dialog import MaterialLibraryDialog  # noqa: E402
from ui.project_page import ProjectPage  # noqa: E402
from utils.project_store import ProjectMaterialRef  # noqa: E402
from utils.recording_library_store import MaterialItem  # noqa: E402

APP = QApplication.instance() or QApplication([])


class FakeMaterialQuery:
    def __init__(self, descriptors: list[ProjectMaterialDescriptor]) -> None:
        self.descriptors = descriptors
        self.schedules: list[dict[str, object]] = []

    def describe(self, _project, _library_items):
        return list(self.descriptors)

    def schedule(
        self,
        descriptors,
        *,
        visible_ids=None,
        selected_id=None,
        force_ids=None,
    ):
        descriptors = list(descriptors)
        self.schedules.append(
            {
                "ids": [item.material_id for item in descriptors],
                "visible_ids": set(visible_ids or ()),
                "selected_id": selected_id,
                "force_ids": set(force_ids or ()),
            }
        )
        return {
            item.material_id: f"task-{item.material_id}"
            for item in descriptors
            if item.material_id in set(force_ids or ())
        }


def _material(base: Path, material_id: str = "material-1") -> MaterialItem:
    video = base / "中文 素材" / f"{material_id}.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"video")
    return MaterialItem(
        id=material_id,
        file_path=str(video),
        file_name=video.name,
        directory=str(video.parent),
        mode="fullscreen",
        audio_source="system",
        created_at="2026-07-27T10:00:00+08:00",
        duration_sec=12.5,
        width=1920,
        height=1080,
        fps=60.0,
        file_size_bytes=video.stat().st_size,
    )


def _preview(base: Path) -> Path:
    path = base / "preview.jpg"
    image = QImage(320, 180, QImage.Format_RGB32)
    image.fill(QColor("#2563EB"))
    assert image.save(str(path), "JPG")
    return path


def _descriptor(
    material: MaterialItem,
    *,
    preview_path: Path | None,
    preview_state: PreviewState,
    file_exists: bool = True,
    business_status: str = "available",
    preview_error: str = "",
) -> ProjectMaterialDescriptor:
    return ProjectMaterialDescriptor(
        project_id="project-1",
        material_id=material.id,
        file_name=material.file_name,
        file_path=material.file_path,
        file_exists=file_exists,
        business_status=business_status,
        duration_sec=material.duration_sec,
        width=material.width,
        height=material.height,
        fps=material.fps,
        mode=material.mode,
        audio_source=material.audio_source,
        file_size_bytes=material.file_size_bytes,
        preview_path=preview_path,
        preview_state=preview_state,
        preview_position_sec=1.25,
        preview_error=preview_error,
    )


def _page(
    base: Path,
    descriptor: ProjectMaterialDescriptor,
    *,
    archived: bool = False,
) -> tuple[ProjectPage, FakeMaterialQuery]:
    project_service = ProjectLibraryService(
        base / "projects.json",
        default_root=base / "projects",
    )
    library_service = RecordingLibraryService(base / "recordings.json")
    material = _material(base, descriptor.material_id)
    assert library_service.add(material).ok
    assert project_service.create_project(
        name="预览项目",
        project_id="project-1",
    ).ok
    assert project_service.add_material(
        "project-1",
        ProjectMaterialRef(
            material_id=material.id,
            last_known_path=material.file_path,
            file_name=material.file_name,
            added_at="2026-07-27T10:00:00+08:00",
        ),
    ).ok
    if archived:
        assert project_service.archive_project("project-1").ok
    query = FakeMaterialQuery([descriptor])
    page = ProjectPage(
        project_service,
        library_service,
        material_query=query,
    )
    if archived:
        page._scope_combo.setCurrentIndex(page._scope_combo.findData("archived"))
    page._select_project("project-1")
    page._material_table.selectRow(0)
    APP.processEvents()
    return page, query


def test_project_material_preview_and_actions_follow_selected_descriptor():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        material = _material(base)
        descriptor = _descriptor(
            material,
            preview_path=_preview(base),
            preview_state=PreviewState.AVAILABLE,
        )
        page, query = _page(base, descriptor)
        opened: list[str] = []
        folders: list[str] = []
        library: list[tuple[str, str]] = []
        page.open_material_requested.connect(opened.append)
        page.open_material_folder_requested.connect(folders.append)
        page.show_material_in_library_requested.connect(
            lambda project_id, material_id: library.append(
                (project_id, material_id)
            )
        )

        assert page._material_preview.pixmap() is not None
        assert page._material_detail_name.text() == material.file_name
        assert page._material_detail_status.text() == "预览可用"
        assert "1920 × 1080" in page._material_detail_meta.text()
        assert page._btn_open_material.isEnabled()
        assert page._btn_open_material_folder.isEnabled()
        assert page._btn_show_in_library.isEnabled()
        assert query.schedules[-1]["visible_ids"] == {material.id}

        page._btn_open_material.click()
        page._btn_open_material_folder.click()
        page._btn_show_in_library.click()

        assert opened == [material.file_path]
        assert folders == [material.file_path]
        assert library == [("project-1", material.id)]


def test_material_actions_do_not_overlap_preview_at_minimum_workbench_size():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        material = _material(base)
        descriptor = _descriptor(
            material,
            preview_path=_preview(base),
            preview_state=PreviewState.AVAILABLE,
        )
        page, _query = _page(base, descriptor)
        page.resize(960, 640)
        page.show()
        APP.processEvents()

        scroll_bottom = page._material_detail_scroll.mapTo(
            page,
            QPoint(0, page._material_detail_scroll.height()),
        ).y()
        footer_top = page._material_action_footer.mapTo(page, QPoint()).y()

        assert page._material_action_footer.isVisibleTo(page)
        assert page._btn_open_material.isVisibleTo(page)
        assert page._btn_open_material_folder.isVisibleTo(page)
        assert page._btn_show_in_library.isVisibleTo(page)
        assert page._btn_refresh_preview.isVisibleTo(page)
        assert scroll_bottom <= footer_top
        assert page._material_detail_scroll.verticalScrollBar().maximum() > 0
        page.close()


def test_missing_material_keeps_historical_preview_and_recovery_entry():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        material = _material(base)
        descriptor = _descriptor(
            material,
            preview_path=_preview(base),
            preview_state=PreviewState.MISSING,
            file_exists=False,
            business_status="missing",
        )
        page, _query = _page(base, descriptor)

        assert page._material_preview.pixmap() is not None
        assert page._material_detail_status.text() == "文件已移动或删除"
        assert not page._btn_open_material.isEnabled()
        assert not page._btn_open_material_folder.isEnabled()
        assert page._btn_show_in_library.isEnabled()
        assert not page._btn_refresh_preview.isEnabled()


def test_failed_preview_keeps_file_actions_and_can_retry():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        material = _material(base)
        descriptor = _descriptor(
            material,
            preview_path=None,
            preview_state=PreviewState.FAILED,
            preview_error="ffmpeg failed",
        )
        page, query = _page(base, descriptor)

        assert page._material_detail_status.text() == "预览生成失败"
        assert "ffmpeg failed" in page._material_preview_hint.text()
        assert page._btn_open_material.isEnabled()
        assert page._btn_refresh_preview.isEnabled()

        page._btn_refresh_preview.click()

        assert query.schedules[-1]["force_ids"] == {material.id}
        assert query.schedules[-1]["selected_id"] == material.id


def test_refresh_preview_status_closes_after_task_finishes():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        material = _material(base)
        descriptor = _descriptor(
            material,
            preview_path=_preview(base),
            preview_state=PreviewState.AVAILABLE,
        )
        page, _query = _page(base, descriptor)

        page._btn_refresh_preview.click()
        assert page._status_label.text() == "正在刷新所选素材的首帧预览"

        page._on_thumbnail_state_changed(
            SimpleNamespace(
                key=f"task-{material.id}",
                request=SimpleNamespace(material_id=material.id),
                state="succeeded",
                result=SimpleNamespace(error=""),
            )
        )

        assert page._status_label.text() == "首帧预览已刷新"
        assert material.id not in page._preview_refresh_tasks


def test_refresh_preview_failure_keeps_retry_feedback_visible():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        material = _material(base)
        descriptor = _descriptor(
            material,
            preview_path=_preview(base),
            preview_state=PreviewState.AVAILABLE,
        )
        page, _query = _page(base, descriptor)

        page._btn_refresh_preview.click()
        page._on_thumbnail_state_changed(
            SimpleNamespace(
                key=f"task-{material.id}",
                request=SimpleNamespace(material_id=material.id),
                state="failed",
                result=SimpleNamespace(error="ffmpeg 返回非零"),
            )
        )

        assert page._status_label.text() == "首帧预览刷新失败：ffmpeg 返回非零"
        assert material.id not in page._preview_refresh_tasks


def test_pending_material_disables_file_and_library_navigation():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        material = _material(base)
        descriptor = _descriptor(
            material,
            preview_path=None,
            preview_state=PreviewState.PENDING,
            business_status="unindexed",
        )
        page, _query = _page(base, descriptor)

        assert page._material_detail_status.text() == "待关联素材库"
        assert not page._btn_open_material.isEnabled()
        assert not page._btn_open_material_folder.isEnabled()
        assert not page._btn_show_in_library.isEnabled()
        assert not page._btn_refresh_preview.isEnabled()


def test_archived_project_can_rebuild_preview_but_cannot_remove_material():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        material = _material(base)
        descriptor = _descriptor(
            material,
            preview_path=None,
            preview_state=PreviewState.NOT_GENERATED,
        )
        page, query = _page(base, descriptor, archived=True)

        assert page._btn_rebuild_previews.isEnabled()
        assert not page._btn_remove_material.isEnabled()

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.Yes,
        ):
            page._btn_rebuild_previews.click()

        assert query.schedules[-1]["force_ids"] == {material.id}


def test_material_library_focus_and_return_preserve_project_context():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = RecordingLibraryService(base / "recordings.json")
        material = _material(base)
        assert service.add(material).ok
        dialog = MaterialLibraryDialog(service, embedded=True)
        returned: list[tuple[str, str]] = []
        dialog.return_to_project_requested.connect(
            lambda project_id, material_id: returned.append(
                (project_id, material_id)
            )
        )

        assert dialog.focus_material(
            material.id,
            source_project_id="project-1",
            source_project_name="预览项目",
        )
        assert dialog._project_context_bar.isVisibleTo(dialog)
        assert dialog._selected_item() is not None
        assert dialog._selected_item().id == material.id

        dialog._btn_return_to_project.click()

        assert returned == [("project-1", material.id)]


def test_material_library_focus_closes_pending_query_before_selecting():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = RecordingLibraryService(base / "recordings.json")
        material = _material(base)
        assert service.add(material).ok
        dialog = MaterialLibraryDialog(service, embedded=True)

        dialog._search_input.setText("不会命中的旧条件")
        assert dialog._query_timer.isActive()

        assert dialog.focus_material(
            material.id,
            source_project_id="project-1",
            source_project_name="预览项目",
        )
        QTest.qWait(200)
        APP.processEvents()

        assert dialog._search_input.text() == ""
        assert dialog._selected_item() is not None
        assert dialog._selected_item().id == material.id
        assert dialog._query_result.matched_total == 1
