"""项目创建与素材选择对话框。"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from services.project_deletion import ProjectDeletionPlan
from ui.design_system import set_button_icon
from utils.project_store import ProjectIndexEntry
from utils.recording_library_store import STATUS_AVAILABLE, MaterialItem


class ProjectCreateDialog(QDialog):
    """收集项目名称、说明与单次保存位置。"""

    def __init__(self, default_root: str | Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建项目")
        self.setMinimumWidth(520)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        intro = QLabel("项目保存素材引用，不会复制或移动原始视频。")
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：产品演示录制")
        self.name_edit.setMaxLength(120)
        form.addRow("项目名称：", self.name_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("可选，记录项目用途或交付范围")
        self.description_edit.setMaximumHeight(90)
        form.addRow("项目说明：", self.description_edit)

        path_row = QHBoxLayout()
        self.root_edit = QLineEdit(str(default_root))
        self.root_edit.setReadOnly(True)
        path_row.addWidget(self.root_edit, 1)
        browse = QPushButton("浏览...")
        browse.clicked.connect(self._browse_root)
        set_button_icon(browse, "folder")
        path_row.addWidget(browse)
        form.addRow("保存位置：", path_row)
        root.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        _dialog_button(self.buttons, QDialogButtonBox.Ok).setText("创建项目")
        _dialog_button(self.buttons, QDialogButtonBox.Cancel).setText("取消")
        self.buttons.accepted.connect(self._accept_if_valid)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def values(self) -> tuple[str, str, str]:
        return (
            self.name_edit.text().strip(),
            self.description_edit.toPlainText().strip(),
            self.root_edit.text().strip(),
        )

    def _browse_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择项目保存位置",
            self.root_edit.text(),
        )
        if selected:
            self.root_edit.setText(selected)

    def _accept_if_valid(self) -> None:
        name, _description, root = self.values()
        self.name_edit.setProperty("invalid", not bool(name))
        self.root_edit.setProperty("invalid", not bool(root))
        if name and root:
            self.accept()


class MaterialPickerDialog(QDialog):
    """从全局素材库多选可用且尚未加入的素材。"""

    MATERIAL_ROLE = Qt.UserRole

    def __init__(
        self,
        materials: list[MaterialItem],
        *,
        existing_ids: set[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("从素材库添加")
        self.resize(680, 480)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)
        root.addWidget(QLabel("可多选；已加入、文件缺失或不可用素材不会重复添加。"))

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        known = existing_ids or set()
        for material in materials:
            item = QListWidgetItem(
                f"{material.file_name}\n{material.file_path}"
            )
            item.setData(self.MATERIAL_ROLE, material)
            enabled = (
                material.id not in known
                and material.status == STATUS_AVAILABLE
                and Path(material.file_path).is_file()
            )
            if not enabled:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setToolTip("该素材已加入项目或当前不可用")
            self.list_widget.addItem(item)
        root.addWidget(self.list_widget, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        _dialog_button(self.buttons, QDialogButtonBox.Ok).setText("加入项目")
        _dialog_button(self.buttons, QDialogButtonBox.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def selected_materials(self) -> list[MaterialItem]:
        return [
            item.data(self.MATERIAL_ROLE)
            for item in self.list_widget.selectedItems()
            if isinstance(item.data(self.MATERIAL_ROLE), MaterialItem)
        ]


class ProjectTargetPickerDialog(QDialog):
    """为一个素材选择一个或多个活跃、可写项目。"""

    PROJECT_ID_ROLE = Qt.UserRole

    def __init__(
        self,
        projects: list[ProjectIndexEntry],
        *,
        material_name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("加入项目")
        self.resize(520, 420)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)
        label = QLabel(f"选择“{material_name}”要加入的项目，可多选。")
        label.setWordWrap(True)
        root.addWidget(label)
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for project in projects:
            item = QListWidgetItem(f"{project.name}\n{project.file_path}")
            item.setData(self.PROJECT_ID_ROLE, project.project_id)
            self.list_widget.addItem(item)
        root.addWidget(self.list_widget, 1)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        _dialog_button(self.buttons, QDialogButtonBox.Ok).setText("加入所选项目")
        _dialog_button(self.buttons, QDialogButtonBox.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def selected_project_ids(self) -> list[str]:
        return [
            str(item.data(self.PROJECT_ID_ROLE))
            for item in self.list_widget.selectedItems()
        ]


class ProjectDeleteDialog(QDialog):
    """展示引用分类，并默认仅把项目文件移入回收站。"""

    MATERIAL_ID_ROLE = Qt.UserRole

    def __init__(self, plan: ProjectDeletionPlan, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("删除项目")
        self.resize(700, 520)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        warning = QLabel(
            f"将项目“{plan.project_name}”移入 Windows 回收站。\n"
            "默认不会处理任何原始视频；只有独占且存在的素材可以单独选择。"
        )
        warning.setWordWrap(True)
        root.addWidget(warning)
        summary = QLabel(
            f"项目文件：{plan.project_path}\n"
            f"素材共 {len(plan.materials)} 项 · "
            f"独占 {plan.counts.get('exclusive', 0)} · "
            f"共享 {plan.counts.get('shared', 0)} · "
            f"不确定 {plan.counts.get('uncertain', 0)}"
        )
        summary.setWordWrap(True)
        root.addWidget(summary)

        self.material_list = QListWidget()
        for material in plan.materials:
            state_label = {
                "exclusive": "独占，可选择",
                "shared": "共享，禁止删除",
                "uncertain": "缺失或无法确认，禁止删除",
            }.get(material.state, material.state)
            item = QListWidgetItem(
                f"{material.file_name}\n{state_label} · {material.file_path}"
            )
            item.setData(self.MATERIAL_ID_ROLE, material.material_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            if not material.selectable:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.material_list.addItem(item)
        root.addWidget(self.material_list, 1)

        note = QLabel(
            "确认后按顺序处理已选视频、项目文件和中央项目列表。"
            "任一步失败都会停止后续操作并展示真实结果。"
        )
        note.setWordWrap(True)
        root.addWidget(note)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        confirm = _dialog_button(self.buttons, QDialogButtonBox.Ok)
        confirm.setText("移入回收站")
        confirm.setProperty("role", "danger")
        _dialog_button(self.buttons, QDialogButtonBox.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def selected_material_ids(self) -> list[str]:
        selected: list[str] = []
        for row in range(self.material_list.count()):
            item = self.material_list.item(row)
            assert item is not None
            if (
                item.flags() & Qt.ItemIsEnabled
                and item.checkState() == Qt.Checked
            ):
                selected.append(str(item.data(self.MATERIAL_ID_ROLE)))
        return selected


def _dialog_button(
    buttons: QDialogButtonBox,
    standard_button: QDialogButtonBox.StandardButton,
) -> QPushButton:
    button = buttons.button(standard_button)
    assert button is not None
    return button
