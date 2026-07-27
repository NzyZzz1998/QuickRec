from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QDialog  # noqa: E402

from services.project_deletion import (  # noqa: E402
    ProjectDeletionMaterial,
    ProjectDeletionPlan,
)
from ui.project_dialogs import (  # noqa: E402
    MaterialPickerDialog,
    ProjectCreateDialog,
    ProjectDeleteDialog,
    ProjectTargetPickerDialog,
)
from utils.project_store import ProjectIndexEntry  # noqa: E402
from utils.recording_library_store import MaterialItem  # noqa: E402

APP = QApplication.instance() or QApplication([])


def _material(path: Path, material_id: str) -> MaterialItem:
    return MaterialItem(
        id=material_id,
        file_path=str(path),
        file_name=path.name,
        directory=str(path.parent),
        mode="fullscreen",
        audio_source="none",
        created_at="2026-07-26T10:00:00+08:00",
    )


def test_project_create_dialog_collects_trimmed_values_and_custom_root():
    with tempfile.TemporaryDirectory() as temp_dir:
        default = Path(temp_dir) / "default"
        custom = Path(temp_dir) / "中文 项目"
        custom.mkdir()
        dialog = ProjectCreateDialog(default)
        dialog.name_edit.setText("  教程项目  ")
        dialog.description_edit.setPlainText("  说明  ")

        with patch(
            "ui.project_dialogs.QFileDialog.getExistingDirectory",
            return_value=str(custom),
        ):
            dialog._browse_root()
        dialog._accept_if_valid()

        assert dialog.values() == ("教程项目", "说明", str(custom))
        assert dialog.result() == QDialog.Accepted


def test_project_create_dialog_rejects_blank_name_without_closing():
    dialog = ProjectCreateDialog(Path("E:/Projects"))
    dialog.name_edit.setText("   ")

    dialog._accept_if_valid()

    assert dialog.result() != QDialog.Accepted
    assert dialog.name_edit.property("invalid") is True


def test_material_picker_returns_only_enabled_selected_materials():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        available_path = base / "available.mp4"
        available_path.write_bytes(b"video")
        missing_path = base / "missing.mp4"
        available = _material(available_path, "available")
        missing = _material(missing_path, "missing").with_refreshed_status()
        picker = MaterialPickerDialog([available, missing])

        picker.list_widget.item(0).setSelected(True)
        picker.list_widget.item(1).setSelected(True)

        assert [item.id for item in picker.selected_materials()] == ["available"]


def test_project_target_picker_returns_multiple_selected_ids():
    entries = [
        ProjectIndexEntry(
            project_id=f"project-{index}",
            file_path=rf"E:\Projects\{index}\project.qrproj",
            name=f"项目 {index}",
            created_at="2026-07-26T10:00:00+08:00",
            updated_at="2026-07-26T10:00:00+08:00",
        )
        for index in range(2)
    ]
    picker = ProjectTargetPickerDialog(entries, material_name="素材.mp4")

    picker.list_widget.item(0).setSelected(True)
    picker.list_widget.item(1).setSelected(True)

    assert picker.selected_project_ids() == ["project-0", "project-1"]


def test_project_delete_dialog_defaults_to_no_video_and_disables_shared_item():
    plan = ProjectDeletionPlan(
        True,
        "project-1",
        "项目",
        Path(r"E:\Projects\project.qrproj"),
        (
            ProjectDeletionMaterial(
                "exclusive",
                "独占.mp4",
                r"E:\Videos\独占.mp4",
                "exclusive",
                True,
            ),
            ProjectDeletionMaterial(
                "shared",
                "共享.mp4",
                r"E:\Videos\共享.mp4",
                "shared",
                False,
            ),
        ),
        {"exclusive": 1, "shared": 1, "uncertain": 0},
    )
    dialog = ProjectDeleteDialog(plan)

    assert dialog.selected_material_ids() == []
    assert not bool(
        dialog.material_list.item(1).flags() & Qt.ItemIsEnabled
    )

    dialog.material_list.item(0).setCheckState(Qt.Checked)

    assert dialog.selected_material_ids() == ["exclusive"]
