from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from services.project_editing_profile import (  # noqa: E402
    EDITING_EXTENSION_KEY,
)
from services.project_library import (
    ProjectLibraryService,  # noqa: E402
    ProjectOperationResult,  # noqa: E402
)
from services.recording_library import RecordingLibraryService  # noqa: E402
from services.timeline_commands import TimelineCommandService  # noqa: E402
from ui.project_dialogs import MaterialPickerDialog  # noqa: E402
from ui.project_page import ProjectPage  # noqa: E402
from utils.project_store import (  # noqa: E402
    ProjectFile,
    ProjectMaterialRef,  # noqa: E402
    load_project,
    save_project,
)
from utils.recording_library_store import MaterialItem  # noqa: E402

APP = QApplication.instance() or QApplication([])


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
        audio_source="none",
        created_at="2026-07-26T10:30:00+08:00",
        duration_sec=3.5,
        width=1920,
        height=1080,
        fps=60.0,
        file_size_bytes=video.stat().st_size,
    )


def test_empty_project_page_exposes_clear_first_action():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        page = ProjectPage(ProjectLibraryService(base / "projects.json"))

        assert page._project_list.count() == 0
        assert page._status_label.text() == "暂无项目"
        assert page._btn_create.isEnabled()
        assert not page._btn_rename.isEnabled()


def test_project_selection_loads_details_and_preserves_selection_on_reload():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        first = service.create_project(name="第一个项目", project_id="project-1")
        second = service.create_project(name="第二个项目", project_id="project-2")
        assert first.ok and second.ok
        page = ProjectPage(service)

        page._select_project("project-1")
        assert page.selected_project_id == "project-1"
        assert page._detail_name.text() == "第一个项目"
        assert page._detail_path.text() == str(first.path)

        page.reload()

        assert page.selected_project_id == "project-1"
        assert page._detail_name.text() == "第一个项目"


def test_recent_scope_limits_project_list_to_eight():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        for index in range(10):
            assert service.create_project(
                name=f"项目 {index}",
                project_id=f"project-{index}",
                now=f"2026-07-26T{index:02d}:00:00+08:00",
            ).ok
        page = ProjectPage(service)

        page._scope_combo.setCurrentIndex(
            page._scope_combo.findData("recent")
        )

        assert page._project_list.count() == 8


def test_archived_project_is_read_only_and_can_be_restored():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        assert service.create_project(name="归档项目", project_id="project-1").ok
        assert service.archive_project("project-1").ok
        page = ProjectPage(service)
        page._scope_combo.setCurrentIndex(page._scope_combo.findData("archived"))
        page._select_project("project-1")

        assert not page._btn_rename.isEnabled()
        assert not page._btn_add_material.isEnabled()
        assert not page._btn_record_fullscreen.isEnabled()
        assert page._btn_archive.text() == "恢复项目"


def test_read_only_project_disables_mutating_actions():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        assert service.create_project(name="只读项目", project_id="project-1").ok

        with patch("ui.project_page.os.access", return_value=False):
            page = ProjectPage(service)
            page._select_project("project-1")

        assert page._detail_status.text() == "只读"
        assert not page._btn_rename.isEnabled()
        assert not page._btn_record_fullscreen.isEnabled()
        assert not page._btn_delete.isEnabled()


def test_missing_and_corrupt_projects_show_distinct_read_only_states():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        missing = service.create_project(name="缺失项目", project_id="missing")
        corrupt = service.create_project(name="损坏项目", project_id="corrupt")
        assert missing.ok and corrupt.ok
        missing.path.unlink()
        corrupt.path.write_text("{broken", encoding="utf-8")
        page = ProjectPage(service)

        page._select_project("missing")
        assert page._detail_status.text() == "项目文件缺失"
        assert not page._btn_archive.isEnabled()

        page._select_project("corrupt")
        assert page._detail_status.text() == "项目文件损坏"
        assert not page._btn_record_fullscreen.isEnabled()


def test_long_chinese_name_and_path_remain_available_at_minimum_content_size():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir) / ("中文 空格路径" * 4)
        service = ProjectLibraryService(
            Path(temp_dir) / "projects.json",
            default_root=base,
        )
        name = "很长的中文项目名称" * 8
        created = service.create_project(name=name, project_id="project-long")
        assert created.ok
        page = ProjectPage(service)

        page.resize(776, 600)
        page.show()
        QApplication.processEvents()
        page._select_project("project-long")

        assert page._detail_name.text() == name
        assert page._detail_path.text() == str(created.path)
        assert page._splitter.orientation() == Qt.Vertical
        assert page._btn_record_fullscreen.isVisible()


def test_create_project_action_uses_one_time_location_without_changing_default():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        default = base / "default"
        custom = base / "custom"
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=default,
        )
        page = ProjectPage(service)

        with patch(
            "ui.project_page.ProjectCreateDialog.exec_",
            return_value=QDialog.Accepted,
        ), patch(
            "ui.project_page.ProjectCreateDialog.values",
            return_value=("自定义项目", "说明", str(custom)),
        ):
            page._on_create_project()

        assert service.default_root == default
        assert service.list_entries()[0].name == "自定义项目"
        assert Path(service.list_entries()[0].file_path).parent == custom / service.list_entries()[0].project_id


def test_create_project_action_inherits_current_recording_fps_once():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        page = ProjectPage(service, editing_fps_provider=lambda: 120)

        with patch(
            "ui.project_page.ProjectCreateDialog.exec_",
            return_value=QDialog.Accepted,
        ), patch(
            "ui.project_page.ProjectCreateDialog.values",
            return_value=("高帧项目", "", str(base / "projects")),
        ):
            page._on_create_project()
        entry = service.list_entries()[0]
        loaded = load_project(entry.file_path)

        assert loaded.ok and loaded.project is not None
        assert loaded.project.extensions[EDITING_EXTENSION_KEY][
            "editing_fps"
        ] == 120


def test_open_external_project_registers_original_file_in_place():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "default",
        )
        external = base / "外部 项目" / "project.qrproj"
        assert save_project(
            external,
            ProjectFile(
                project_id="external",
                name="外部项目",
                description="",
                created_at="2026-07-26T10:00:00+08:00",
                updated_at="2026-07-26T10:00:00+08:00",
            ),
        ).ok
        page = ProjectPage(service)

        with patch(
            "ui.project_page.QFileDialog.getOpenFileName",
            return_value=(str(external), ""),
        ):
            page._on_open_project()

        assert service.list_entries()[0].file_path == str(external)
        assert page.selected_project_id == "external"


def test_edit_archive_and_restore_actions_persist_project_state():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        assert service.create_project(name="原名称", project_id="project-1").ok
        page = ProjectPage(service)
        page._select_project("project-1")

        with patch(
            "ui.project_page.ProjectCreateDialog.exec_",
            return_value=QDialog.Accepted,
        ), patch(
            "ui.project_page.ProjectCreateDialog.values",
            return_value=("新名称", "新说明", str(base / "unused")),
        ):
            page._on_rename_project()

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.Yes,
        ):
            page._on_archive_or_restore()
            page._scope_combo.setCurrentIndex(
                page._scope_combo.findData("archived")
            )
            page._select_project("project-1")
            page._on_archive_or_restore()

        loaded = service.get_project("project-1").project
        assert loaded.name == "新名称"
        assert loaded.description == "新说明"
        assert loaded.archived_at is None


def test_recording_mode_buttons_emit_selected_project_context():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        assert service.create_project(name="录制项目", project_id="project-1").ok
        page = ProjectPage(service)
        page._select_project("project-1")
        emitted: list[tuple[str, str]] = []
        page.start_recording_requested.connect(
            lambda project_id, mode: emitted.append((project_id, mode))
        )

        page._btn_record_fullscreen.click()
        page._btn_record_region.click()
        page._btn_record_window.click()

        assert emitted == [
            ("project-1", "fullscreen"),
            ("project-1", "region"),
            ("project-1", "window"),
        ]


def test_enter_timeline_emits_selected_non_empty_project_context():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(
            name="剪辑项目",
            project_id="project-1",
        )
        assert created.ok
        project = service.get_project("project-1").project
        assert project is not None
        project.materials.append(
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=str(base / "素材.mp4"),
                file_name="素材.mp4",
                added_at="2026-07-28T10:00:00+08:00",
                metadata_snapshot={"duration_sec": 3.0},
            )
        )
        assert service.commit_project_candidate("project-1", project).ok
        page = ProjectPage(service)
        page._select_project("project-1")
        emitted: list[str] = []
        page.open_timeline_requested.connect(emitted.append)

        page._btn_enter_timeline.click()

        assert emitted == ["project-1"]


def test_enter_timeline_is_disabled_for_empty_or_unavailable_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        assert service.create_project(
            name="空项目",
            project_id="project-1",
        ).ok
        page = ProjectPage(service)
        page._select_project("project-1")

        assert not page._btn_enter_timeline.isEnabled()


def test_add_and_remove_material_reference_does_not_touch_video():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        project_service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        material_service = RecordingLibraryService(base / "recordings.json")
        assert project_service.create_project(
            name="素材项目",
            project_id="project-1",
        ).ok
        material = _material(base)
        assert material_service.add(material).ok
        page = ProjectPage(project_service, material_service)
        page._select_project("project-1")

        result = page.add_material_to_project(material, project_id="project-1")
        page._material_table.selectRow(0)
        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.Yes,
        ):
            page._on_remove_material()

        assert result
        assert material.file_path
        assert Path(material.file_path).is_file()
        assert project_service.get_project("project-1").project.materials == []


def test_add_material_emits_content_change_only_for_new_reference():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        project_service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        material_service = RecordingLibraryService(base / "recordings.json")
        assert project_service.create_project(
            name="素材同步项目",
            project_id="project-1",
        ).ok
        material = _material(base)
        assert material_service.add(material).ok
        page = ProjectPage(project_service, material_service)
        page._select_project("project-1")
        changed: list[str] = []
        page.project_content_changed.connect(changed.append)

        assert page.add_material_to_project(material, project_id="project-1")
        assert page.add_material_to_project(material, project_id="project-1")

        assert changed == ["project-1"]


def test_remove_timeline_referenced_material_requires_explicit_group_confirmation():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        project_service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        material_service = RecordingLibraryService(base / "recordings.json")
        assert project_service.create_project(
            name="时间线项目",
            project_id="project-1",
        ).ok
        material = _material(base)
        assert material_service.add(material).ok
        command_service = TimelineCommandService(
            project_service,
            "project-1",
        )
        page = ProjectPage(
            project_service,
            material_service,
            timeline_command_provider=lambda _project_id: command_service,
        )
        page._select_project("project-1")
        assert page.add_material_to_project(material, project_id="project-1")
        command_service.reload()
        added = command_service.add_material(material.id, has_audio=False)
        assert added.ok
        page.reload()
        page._select_project("project-1")
        page._material_table.selectRow(0)
        changed: list[str] = []
        page.project_content_changed.connect(changed.append)

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.Yes,
        ) as question:
            page._on_remove_material()

        assert "1 个时间线片段" in question.call_args.args[2]
        assert command_service.timeline.clips == []
        assert command_service.project.materials == []
        assert changed == ["project-1"]
        assert Path(material.file_path).is_file()
        assert any(
            item.id == material.id
            for item in material_service.list_items()
        )


def test_add_material_to_archived_project_is_rejected_without_mutation():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        assert service.create_project(name="归档项目", project_id="project-1").ok
        assert service.archive_project("project-1").ok
        page = ProjectPage(service)
        material = _material(base)

        added = page.add_material_to_project(material, project_id="project-1")

        assert not added
        assert service.get_project("project-1").project.materials == []


def test_one_material_can_be_added_to_multiple_writable_projects():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        for project_id in ("project-1", "project-2"):
            assert service.create_project(
                name=project_id,
                project_id=project_id,
            ).ok
        material = _material(base)
        page = ProjectPage(service)

        results = page.add_material_to_projects(
            material,
            ["project-1", "project-2"],
        )

        assert results == {"project-1": True, "project-2": True}
        assert len(service.get_project("project-1").project.materials) == 1
        assert len(service.get_project("project-2").project.materials) == 1


def test_writable_project_targets_exclude_archived_and_missing_projects():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        active = service.create_project(name="活跃", project_id="active")
        archived = service.create_project(name="归档", project_id="archived")
        missing = service.create_project(name="缺失", project_id="missing")
        assert active.ok and archived.ok and missing.ok
        assert service.archive_project("archived").ok
        missing.path.unlink()
        page = ProjectPage(service)

        targets = page.writable_project_entries()

        assert [entry.project_id for entry in targets] == ["active"]


def test_batch_add_reports_partial_success_per_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        assert service.create_project(name="活跃", project_id="active").ok
        assert service.create_project(name="归档", project_id="archived").ok
        assert service.archive_project("archived").ok
        page = ProjectPage(service)
        material = _material(base)

        results = page.add_material_to_projects(
            material,
            ["active", "archived"],
        )

        assert results == {"active": True, "archived": False}
        assert len(service.get_project("active").project.materials) == 1
        assert service.get_project("archived").project.materials == []


def test_failed_project_write_keeps_page_and_project_materials_unchanged():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="失败回滚", project_id="project-1")
        assert created.ok
        page = ProjectPage(service)
        page._select_project("project-1")
        material = _material(base)
        failure = ProjectOperationResult(
            False,
            "project",
            created.path,
            error="write denied",
        )

        with patch.object(service, "add_material", return_value=failure):
            added = page.add_material_to_project(
                material,
                project_id="project-1",
            )

        assert not added
        assert page._material_table.rowCount() == 0
        assert service.get_project("project-1").project.materials == []


def test_project_material_uses_global_library_path_after_relink():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        project_service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        material_service = RecordingLibraryService(base / "recordings.json")
        assert project_service.create_project(
            name="重定位项目",
            project_id="project-1",
        ).ok
        original = _material(base)
        assert project_service.add_material(
            "project-1",
            ProjectMaterialRef(
                material_id=original.id,
                last_known_path=r"E:\old\missing.mp4",
                file_name="missing.mp4",
                added_at="2026-07-26T10:30:00+08:00",
            ),
        ).ok
        assert material_service.add(original).ok

        page = ProjectPage(project_service, material_service)
        page._select_project("project-1")

        assert page._material_table.item(0, 3).text() == original.file_path
        assert page._material_table.item(0, 1).text() == "可用"


def test_project_material_without_global_record_keeps_snapshot_as_pending_link():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        project_service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        material_service = RecordingLibraryService(base / "recordings.json")
        assert project_service.create_project(
            name="待关联项目",
            project_id="project-1",
        ).ok
        ref = ProjectMaterialRef(
            material_id="missing-material",
            last_known_path=r"E:\旧路径\素材.mp4",
            file_name="素材.mp4",
            added_at="2026-07-26T10:30:00+08:00",
        )
        assert project_service.add_material("project-1", ref).ok

        page = ProjectPage(project_service, material_service)
        page._select_project("project-1")

        assert page._material_table.item(0, 1).text() == "待关联"
        assert page._material_table.item(0, 3).text() == ref.last_known_path
        assert material_service.load().items == []


def test_material_picker_disables_existing_and_missing_materials():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        available = _material(base, "available")
        missing = _material(base, "missing")
        Path(missing.file_path).unlink()
        missing.with_refreshed_status()

        picker = MaterialPickerDialog(
            [available, missing],
            existing_ids={"available"},
        )

        assert not bool(picker.list_widget.item(0).flags() & Qt.ItemIsEnabled)
        assert not bool(picker.list_widget.item(1).flags() & Qt.ItemIsEnabled)


def test_project_page_picker_adds_selected_material_and_reports_result():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        project_service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        material_service = RecordingLibraryService(base / "recordings.json")
        assert project_service.create_project(
            name="选择素材",
            project_id="project-1",
        ).ok
        material = _material(base)
        assert material_service.add(material).ok
        page = ProjectPage(project_service, material_service)
        page._select_project("project-1")

        with patch(
            "ui.project_page.MaterialPickerDialog.exec_",
            return_value=QDialog.Accepted,
        ), patch(
            "ui.project_page.MaterialPickerDialog.selected_materials",
            return_value=[material],
        ):
            page._on_add_material()

        assert len(project_service.get_project("project-1").project.materials) == 1
        assert page._status_label.text() == "已加入 1 项素材"


def test_material_detail_target_picker_can_add_to_multiple_projects():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        for project_id in ("project-1", "project-2"):
            assert service.create_project(
                name=project_id,
                project_id=project_id,
            ).ok
        page = ProjectPage(service)
        material = _material(base)

        with patch(
            "ui.project_page.ProjectTargetPickerDialog.exec_",
            return_value=QDialog.Accepted,
        ), patch(
            "ui.project_page.ProjectTargetPickerDialog.selected_project_ids",
            return_value=["project-1", "project-2"],
        ):
            page.prompt_add_material(material)

        assert len(service.get_project("project-1").project.materials) == 1
        assert len(service.get_project("project-2").project.materials) == 1
        assert page._status_label.text() == "已加入 2 个项目"


def test_project_recording_result_reports_three_independent_stages():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        assert service.create_project(name="录制结果", project_id="project-1").ok
        page = ProjectPage(service)

        page.show_recording_result(
            "project-1",
            video_saved=True,
            material_indexed=True,
            project_linked=False,
            message="可从素材库手动加入",
        )

        assert page._status_label.text() == (
            "视频已保存；素材已入库；项目未关联；可从素材库手动加入"
        )


def test_missing_project_exposes_relink_and_remove_index_actions():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="缺失", project_id="project-1")
        assert created.ok
        created.path.unlink()
        page = ProjectPage(service)
        page._select_project("project-1")

        assert not page._btn_relocate.isHidden()
        assert page._btn_relocate.isEnabled()
        assert not page._btn_remove_index.isHidden()
        assert not page._btn_open_diagnostics.isHidden()
        assert page._btn_delete.isEnabled() is False


def test_relink_rejects_wrong_project_and_accepts_matching_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="缺失", project_id="project-1")
        assert created.ok
        created.path.unlink()
        wrong = base / "wrong" / "project.qrproj"
        matching = base / "matching" / "project.qrproj"
        assert save_project(
            wrong,
            ProjectFile(
                project_id="other",
                name="其他",
                description="",
                created_at="2026-07-26T10:00:00+08:00",
                updated_at="2026-07-26T10:00:00+08:00",
            ),
        ).ok
        assert save_project(
            matching,
            ProjectFile(
                project_id="project-1",
                name="已找回",
                description="",
                created_at="2026-07-26T10:00:00+08:00",
                updated_at="2026-07-26T10:00:00+08:00",
            ),
        ).ok
        page = ProjectPage(service)
        page._select_project("project-1")

        with patch(
            "ui.project_page.QFileDialog.getOpenFileName",
            return_value=(str(wrong), ""),
        ), patch.object(QMessageBox, "warning"):
            page._on_relocate_project()
        assert service.list_entries()[0].file_path == str(created.path)

        with patch(
            "ui.project_page.QFileDialog.getOpenFileName",
            return_value=(str(matching), ""),
        ):
            page._on_relocate_project()

        assert service.list_entries()[0].file_path == str(matching)
        assert page._detail_name.text() == "已找回"


def test_corrupt_project_recovery_requires_confirmation_and_preserves_corrupt_copy():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="原始", project_id="project-1")
        assert created.ok
        assert service.rename_project("project-1", "当前").ok
        created.path.write_text("{broken", encoding="utf-8")
        page = ProjectPage(service)
        page._select_project("project-1")

        assert not page._btn_recover.isHidden()
        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.Yes,
        ):
            page._on_recover_project()

        assert service.get_project("project-1").ok
        assert list(created.path.parent.glob("project.corrupt-*.qrproj"))
        assert "已从备份恢复" in page._status_label.text()


def test_remove_missing_project_from_list_does_not_touch_candidate_files():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="缺失", project_id="project-1")
        assert created.ok
        backup = created.path.with_name("manual-copy.qrproj")
        backup.write_bytes(created.path.read_bytes())
        created.path.unlink()
        page = ProjectPage(service)
        page._select_project("project-1")

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.Yes,
        ):
            page._on_remove_project_entry()

        assert service.list_entries() == []
        assert backup.is_file()


def test_external_conflict_cancel_keeps_pending_edit_values_for_next_attempt():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        created = service.create_project(name="原名称", project_id="project-1")
        assert created.ok
        page = ProjectPage(service)
        page._select_project("project-1")
        external = service.get_project("project-1").project
        external.name = "外部名称"
        assert save_project(created.path, external).ok

        with patch(
            "ui.project_page.ProjectCreateDialog.exec_",
            return_value=QDialog.Accepted,
        ), patch(
            "ui.project_page.ProjectCreateDialog.values",
            return_value=("未保存名称", "未保存说明", str(base)),
        ), patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.No,
        ):
            page._on_rename_project()

        assert page._pending_edit_values["project-1"] == (
            "未保存名称",
            "未保存说明",
        )
        assert service.get_project("project-1").project.name == "外部名称"


def test_slow_project_recycle_runs_off_ui_thread():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        project_service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "projects",
        )
        material_service = RecordingLibraryService(base / "recordings.json")
        assert project_service.create_project(
            name="后台删除",
            project_id="project-1",
        ).ok
        page = ProjectPage(project_service, material_service)
        page._select_project("project-1")

        def slow_execute(*_args, **_kwargs):
            time.sleep(0.2)
            return SimpleNamespace(
                ok=True,
                stage="complete",
                item_results=(),
                error="",
            )

        with patch(
            "ui.project_page.ProjectDeleteDialog.exec_",
            return_value=QDialog.Accepted,
        ), patch(
            "ui.project_page.ProjectDeleteDialog.selected_material_ids",
            return_value=[],
        ), patch.object(
            page._deletion,
            "execute",
            side_effect=slow_execute,
        ):
            started = time.perf_counter()
            page._on_delete_project()
            elapsed = time.perf_counter() - started

            assert elapsed < 0.1
            assert page._status_label.text() == "正在移入回收站，请稍候..."
            assert page._delete_thread is not None
            page._delete_thread.join(timeout=1)
            APP.processEvents()

        assert page._status_label.text() == "项目已移入回收站"
