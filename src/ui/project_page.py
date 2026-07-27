"""QuickRec Full 工作台项目页面。"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.project_deletion import ProjectDeletionCoordinator
from services.project_library import ProjectLibraryService
from services.project_query import ProjectQueryCriteria, ProjectQueryEngine
from services.recording_library import RecordingLibraryService
from ui.design_system import set_button_icon
from ui.project_dialogs import (
    MaterialPickerDialog,
    ProjectCreateDialog,
    ProjectDeleteDialog,
    ProjectTargetPickerDialog,
)
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.recording_library_store import STATUS_AVAILABLE, MaterialItem

HEALTH_LABELS = {
    "available": "可用",
    "read_only": "只读",
    "missing": "项目文件缺失",
    "corrupt": "项目文件损坏",
    "unsupported_version": "版本不兼容",
}


class ProjectPage(QWidget):
    """项目列表、项目详情和素材引用的单页工作区。"""

    start_recording_requested = pyqtSignal(str, str)
    open_diagnostics_requested = pyqtSignal()
    delete_finished = pyqtSignal(object)

    PROJECT_ID_ROLE = Qt.UserRole
    MATERIAL_ID_ROLE = Qt.UserRole

    def __init__(
        self,
        project_service: ProjectLibraryService,
        material_service: RecordingLibraryService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("projectPage")
        self._service = project_service
        self._material_service = material_service
        self._query = ProjectQueryEngine()
        self._deletion = (
            ProjectDeletionCoordinator(project_service, material_service)
            if material_service is not None
            else None
        )
        self._current_project: ProjectFile | None = None
        self._current_health = ""
        self._pending_edit_values: dict[str, tuple[str, str]] = {}
        self._delete_thread: threading.Thread | None = None
        self._init_ui()
        self.delete_finished.connect(self._on_delete_finished)
        self.reload()

    @property
    def selected_project_id(self) -> str | None:
        item = self._project_list.currentItem()
        return str(item.data(self.PROJECT_ID_ROLE)) if item is not None else None

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(12)

        title_row = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("项目")
        title.setObjectName("pageTitle")
        title_block.addWidget(title)
        subtitle = QLabel("组织录制素材并从项目上下文继续录制。")
        subtitle.setObjectName("pageSubtitle")
        title_block.addWidget(subtitle)
        title_row.addLayout(title_block, 1)
        self._btn_open = QPushButton("打开项目")
        self._btn_open.clicked.connect(self._on_open_project)
        self._btn_open.setToolTip("打开外部 project.qrproj 并登记到本机项目列表")
        set_button_icon(self._btn_open, "folder")
        title_row.addWidget(self._btn_open)
        self._btn_create = QPushButton("新建项目")
        self._btn_create.setProperty("role", "primary")
        self._btn_create.clicked.connect(self._on_create_project)
        self._btn_create.setToolTip("在默认或临时选择的位置创建本地项目")
        set_button_icon(self._btn_create, "save")
        title_row.addWidget(self._btn_create)
        root.addLayout(title_row)

        query_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索项目名称")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self.reload)
        query_row.addWidget(self._search_input, 1)
        self._scope_combo = QComboBox()
        self._scope_combo.addItem("最近项目", "recent")
        self._scope_combo.addItem("活跃项目", "active")
        self._scope_combo.addItem("归档项目", "archived")
        self._scope_combo.addItem("全部项目", "all")
        self._scope_combo.currentIndexChanged.connect(self.reload)
        query_row.addWidget(self._scope_combo)
        self._btn_refresh = QPushButton("刷新")
        self._btn_refresh.clicked.connect(self.reload)
        set_button_icon(self._btn_refresh, "refresh")
        query_row.addWidget(self._btn_refresh)
        root.addLayout(query_row)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        splitter = QSplitter(Qt.Horizontal)
        self._project_list = QListWidget()
        self._project_list.setAccessibleName("项目列表")
        self._project_list.itemSelectionChanged.connect(self._on_project_selected)
        splitter.addWidget(self._project_list)
        splitter.addWidget(self._create_detail_panel())
        splitter.setSizes([310, 760])
        root.addWidget(splitter, 1)
        self._splitter = splitter

    def _create_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self._detail_name = QLabel("未选择项目")
        self._detail_name.setWordWrap(True)
        self._detail_name.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Preferred,
        )
        self._detail_name.setStyleSheet("font-size: 18px; font-weight: 600;")
        header.addWidget(self._detail_name, 1)
        self._btn_rename = QPushButton("重命名")
        self._btn_rename.clicked.connect(self._on_rename_project)
        header.addWidget(self._btn_rename)
        self._btn_archive = QPushButton("归档项目")
        self._btn_archive.clicked.connect(self._on_archive_or_restore)
        header.addWidget(self._btn_archive)
        self._btn_delete = QPushButton("删除项目")
        self._btn_delete.setProperty("role", "danger")
        self._btn_delete.clicked.connect(self._on_delete_project)
        self._btn_delete.setToolTip("项目和可选独占视频只会移入 Windows 回收站")
        set_button_icon(self._btn_delete, "trash")
        header.addWidget(self._btn_delete)
        layout.addLayout(header)

        form = QFormLayout()
        self._detail_status = QLabel("-")
        self._detail_description = QLabel("-")
        self._detail_description.setWordWrap(True)
        self._detail_description.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Preferred,
        )
        self._detail_path = QLabel("-")
        self._detail_path.setWordWrap(True)
        self._detail_path.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Preferred,
        )
        self._detail_updated = QLabel("-")
        self._detail_count = QLabel("0")
        for label, widget in (
            ("状态", self._detail_status),
            ("说明", self._detail_description),
            ("项目文件", self._detail_path),
            ("更新时间", self._detail_updated),
            ("素材数量", self._detail_count),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)

        recovery_row = QHBoxLayout()
        self._btn_open_project_folder = QPushButton("打开所在目录")
        self._btn_open_project_folder.clicked.connect(
            self._on_open_project_folder
        )
        set_button_icon(self._btn_open_project_folder, "folder")
        recovery_row.addWidget(self._btn_open_project_folder)
        self._btn_relocate = QPushButton("重新定位")
        self._btn_relocate.clicked.connect(self._on_relocate_project)
        set_button_icon(self._btn_relocate, "refresh")
        recovery_row.addWidget(self._btn_relocate)
        self._btn_recover = QPushButton("从备份恢复")
        self._btn_recover.clicked.connect(self._on_recover_project)
        set_button_icon(self._btn_recover, "refresh")
        recovery_row.addWidget(self._btn_recover)
        self._btn_remove_index = QPushButton("从列表移除")
        self._btn_remove_index.clicked.connect(self._on_remove_project_entry)
        recovery_row.addWidget(self._btn_remove_index)
        self._btn_open_diagnostics = QPushButton("查看诊断")
        self._btn_open_diagnostics.clicked.connect(
            self.open_diagnostics_requested.emit
        )
        recovery_row.addWidget(self._btn_open_diagnostics)
        recovery_row.addStretch(1)
        layout.addLayout(recovery_row)
        self._recovery_buttons = (
            self._btn_open_project_folder,
            self._btn_relocate,
            self._btn_recover,
            self._btn_remove_index,
            self._btn_open_diagnostics,
        )

        record_label = QLabel("从项目开始录制")
        record_label.setProperty("role", "sectionTitle")
        layout.addWidget(record_label)
        record_row = QHBoxLayout()
        self._btn_record_fullscreen = self._record_button(
            "全屏录制",
            "monitor",
            "fullscreen",
        )
        self._btn_record_region = self._record_button(
            "区域录制",
            "region",
            "region",
        )
        self._btn_record_window = self._record_button(
            "窗口录制",
            "window",
            "window",
        )
        for button in (
            self._btn_record_fullscreen,
            self._btn_record_region,
            self._btn_record_window,
        ):
            record_row.addWidget(button, 1)
        layout.addLayout(record_row)

        material_header = QHBoxLayout()
        material_title = QLabel("项目素材")
        material_title.setProperty("role", "sectionTitle")
        material_header.addWidget(material_title, 1)
        self._btn_add_material = QPushButton("添加素材")
        self._btn_add_material.clicked.connect(self._on_add_material)
        self._btn_add_material.setToolTip("从全局素材库选择一个或多个可用素材")
        set_button_icon(self._btn_add_material, "library")
        material_header.addWidget(self._btn_add_material)
        self._btn_remove_material = QPushButton("从项目移除")
        self._btn_remove_material.clicked.connect(self._on_remove_material)
        self._btn_remove_material.setToolTip("只移除项目引用，不删除视频和全局素材记录")
        set_button_icon(self._btn_remove_material, "close")
        material_header.addWidget(self._btn_remove_material)
        layout.addLayout(material_header)

        self._material_table = QTableWidget(0, 4)
        self._material_table.setHorizontalHeaderLabels(
            ["文件", "状态", "模式", "路径"]
        )
        self._material_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._material_table.setSelectionMode(QTableWidget.SingleSelection)
        self._material_table.setEditTriggers(QTableWidget.NoEditTriggers)
        horizontal_header = self._material_table.horizontalHeader()
        vertical_header = self._material_table.verticalHeader()
        assert horizontal_header is not None
        assert vertical_header is not None
        horizontal_header.setStretchLastSection(True)
        vertical_header.setVisible(False)
        self._material_table.itemSelectionChanged.connect(self._sync_material_action)
        layout.addWidget(self._material_table, 1)
        self._set_project_actions(False)
        self._set_recovery_actions()
        return panel

    def _record_button(
        self,
        label: str,
        icon: str,
        mode: str,
    ) -> QPushButton:
        button = QPushButton(label)
        button.setMinimumHeight(42)
        button.clicked.connect(lambda _checked=False: self._emit_recording(mode))
        button.setToolTip(f"以当前录制设置开始{label}，完成后自动加入当前项目")
        set_button_icon(button, icon)
        return button

    def reload(self, *_args) -> None:
        selected_id = self.selected_project_id
        criteria = ProjectQueryCriteria(
            keyword=self._search_input.text(),
            scope=str(self._scope_combo.currentData() or "active"),
        )
        if criteria.scope == "recent":
            result = self._query.query(
                self._service.list_entries(),
                ProjectQueryCriteria(
                    keyword=criteria.keyword,
                    scope="all",
                    limit=8,
                ),
            )
        else:
            result = self._query.query(self._service.list_entries(), criteria)
        self._project_list.blockSignals(True)
        self._project_list.clear()
        for query_item in result.items:
            entry = query_item.entry
            status = HEALTH_LABELS.get(query_item.health, query_item.health)
            suffix = " · 已归档" if entry.archived_at else ""
            item = QListWidgetItem(
                f"{entry.name}\n{status}{suffix} · {query_item.material_count or 0} 项素材"
            )
            item.setData(self.PROJECT_ID_ROLE, entry.project_id)
            item.setToolTip(entry.file_path)
            self._project_list.addItem(item)
        self._project_list.blockSignals(False)

        if result.total_count == 0:
            self._status_label.setText(
                "暂无项目" if not criteria.keyword else "没有匹配的项目"
            )
            self._clear_detail()
            return
        self._status_label.setText(f"共 {result.total_count} 个项目")
        if selected_id and self._select_project(selected_id):
            return
        self._project_list.setCurrentRow(0)

    def _select_project(self, project_id: str) -> bool:
        for row in range(self._project_list.count()):
            item = self._project_list.item(row)
            assert item is not None
            if item.data(self.PROJECT_ID_ROLE) == project_id:
                self._project_list.setCurrentRow(row)
                return True
        return False

    def _on_project_selected(self) -> None:
        project_id = self.selected_project_id
        if project_id is None:
            self._clear_detail()
            return
        entry = next(
            (
                item
                for item in self._service.list_entries()
                if item.project_id == project_id
            ),
            None,
        )
        loaded = self._service.get_project(project_id)
        self._current_project = loaded.project
        effective_health = loaded.status
        if (
            loaded.ok
            and loaded.project is not None
            and not os.access(loaded.path, os.W_OK)
        ):
            effective_health = "read_only"
        self._current_health = effective_health
        if entry is None or not loaded.ok or loaded.project is None:
            self._detail_name.setText(entry.name if entry else "项目不可用")
            self._detail_status.setText(
                HEALTH_LABELS.get(loaded.status, loaded.status or "不可用")
            )
            self._detail_path.setText(str(entry.file_path) if entry else "-")
            self._detail_description.setText(loaded.error or "-")
            self._detail_updated.setText(entry.updated_at if entry else "-")
            self._detail_count.setText("-")
            self._material_table.setRowCount(0)
            self._set_project_actions(False)
            self._set_recovery_actions(
                health=loaded.status,
                backup_available=loaded.backup_available,
                has_entry=entry is not None,
            )
            return
        project = loaded.project
        self._detail_name.setText(project.name)
        health = "已归档" if project.archived_at else HEALTH_LABELS.get(
            effective_health,
            "可用",
        )
        self._detail_status.setText(health)
        self._detail_description.setText(project.description or "暂无说明")
        self._detail_path.setText(str(loaded.path))
        self._detail_updated.setText(project.updated_at)
        self._detail_count.setText(str(len(project.materials)))
        self._populate_materials(project)
        writable = not project.archived_at and effective_health == "available"
        self._set_project_actions(writable)
        self._btn_archive.setEnabled(True)
        self._btn_archive.setText("恢复项目" if project.archived_at else "归档项目")
        self._btn_delete.setEnabled(self._deletion is not None)
        self._set_recovery_actions(
            health=effective_health,
            has_entry=True,
        )

    def _populate_materials(self, project: ProjectFile) -> None:
        globals_by_id: dict[str, MaterialItem] = {}
        if self._material_service is not None:
            loaded = self._material_service.load()
            if loaded.ok:
                globals_by_id = {item.id: item for item in loaded.items}
        self._material_table.setRowCount(len(project.materials))
        for row, ref in enumerate(project.materials):
            actual = globals_by_id.get(ref.material_id)
            if actual is None:
                status = "待关联"
                name = ref.file_name
                path = ref.last_known_path
                mode = str(ref.metadata_snapshot.get("mode") or "未知")
            else:
                status = "可用" if actual.status == STATUS_AVAILABLE else "文件缺失"
                name = actual.file_name
                path = actual.file_path
                mode = actual.mode
            name_item = QTableWidgetItem(name)
            name_item.setData(self.MATERIAL_ID_ROLE, ref.material_id)
            self._material_table.setItem(row, 0, name_item)
            self._material_table.setItem(row, 1, QTableWidgetItem(status))
            self._material_table.setItem(row, 2, QTableWidgetItem(mode))
            self._material_table.setItem(row, 3, QTableWidgetItem(path))
        self._material_table.clearSelection()
        self._sync_material_action()

    def _clear_detail(self) -> None:
        self._current_project = None
        self._current_health = ""
        self._detail_name.setText("未选择项目")
        self._detail_status.setText("-")
        self._detail_description.setText("-")
        self._detail_path.setText("-")
        self._detail_updated.setText("-")
        self._detail_count.setText("0")
        self._material_table.setRowCount(0)
        self._set_project_actions(False)
        self._set_recovery_actions()

    def _set_project_actions(self, writable: bool) -> None:
        for button in (
            self._btn_rename,
            self._btn_add_material,
            self._btn_record_fullscreen,
            self._btn_record_region,
            self._btn_record_window,
        ):
            button.setEnabled(writable)
        self._btn_archive.setEnabled(self._current_project is not None)
        self._btn_delete.setEnabled(
            self._current_project is not None
            and self._deletion is not None
            and self._current_health == "available"
        )
        self._sync_material_action()

    def _set_recovery_actions(
        self,
        *,
        health: str = "",
        backup_available: bool = False,
        has_entry: bool = False,
    ) -> None:
        for button in getattr(self, "_recovery_buttons", ()):
            button.setVisible(False)
            button.setEnabled(False)
        if not has_entry:
            return
        self._btn_open_project_folder.setVisible(True)
        self._btn_open_project_folder.setEnabled(True)
        if health in {"missing", "corrupt", "unsupported"}:
            self._btn_relocate.setVisible(True)
            self._btn_relocate.setEnabled(True)
            self._btn_remove_index.setVisible(True)
            self._btn_remove_index.setEnabled(True)
            self._btn_open_diagnostics.setVisible(True)
            self._btn_open_diagnostics.setEnabled(True)
        if health == "corrupt" and backup_available:
            self._btn_recover.setVisible(True)
            self._btn_recover.setEnabled(True)

    def _sync_material_action(self) -> None:
        writable = (
            self._current_project is not None
            and not self._current_project.archived_at
            and self._current_health == "available"
        )
        self._btn_remove_material.setEnabled(
            writable and self._material_table.currentRow() >= 0
        )

    def _on_create_project(self) -> None:
        dialog = ProjectCreateDialog(self._service.default_root, self)
        if dialog.exec_() != dialog.Accepted:
            return
        name, description, root = dialog.values()
        result = self._service.create_project(
            name=name,
            description=description,
            root_path=root,
        )
        if not result.ok:
            if result.project_written:
                self._status_label.setText(
                    "项目文件已创建，但未加入项目列表。"
                    f"请使用“打开项目”重新登记：{result.path}"
                )
                QMessageBox.warning(
                    self,
                    "项目登记失败",
                    "项目文件已安全保留，但中央项目列表写入失败。\n"
                    f"项目文件：{result.path}",
                )
                return
            self._show_error("创建项目失败", result.error)
            return
        self.reload()
        if result.project is not None:
            self._select_project(result.project.project_id)
        self._status_label.setText("项目已创建")

    def _on_open_project(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "打开 QuickRec 项目",
            str(self._service.default_root),
            "QuickRec 项目 (project.qrproj *.qrproj);;所有文件 (*)",
        )
        if not path:
            return
        result = self._service.register_project(path)
        if result.stage == "path_conflict":
            choice = QMessageBox.question(
                self,
                "项目路径已变化",
                "同一项目 ID 已登记在其他位置。是否使用当前选择的位置？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if choice == QMessageBox.Yes:
                result = self._service.register_project(
                    path,
                    update_existing_path=True,
                )
        if not result.ok:
            self._show_error("打开项目失败", result.error)
            return
        self.reload()
        if result.project is not None:
            self._select_project(result.project.project_id)
        self._status_label.setText("项目已打开")

    def _on_rename_project(self) -> None:
        project_id = self.selected_project_id
        if project_id is None or self._current_project is None:
            return
        from ui.project_dialogs import ProjectCreateDialog

        dialog = ProjectCreateDialog(self._service.default_root, self)
        dialog.setWindowTitle("编辑项目")
        pending = self._pending_edit_values.get(project_id)
        dialog.name_edit.setText(
            pending[0] if pending else self._current_project.name
        )
        dialog.description_edit.setPlainText(
            pending[1] if pending else self._current_project.description
        )
        dialog.root_edit.setText(str(Path(self._detail_path.text()).parent.parent))
        dialog.root_edit.setEnabled(False)
        dialog.buttons.button(dialog.buttons.Ok).setText("保存更改")
        if dialog.exec_() != dialog.Accepted:
            return
        name, description, _root = dialog.values()
        result = self._service.update_project_details(
            project_id,
            name=name,
            description=description,
        )
        if result.stage == "external_conflict":
            self._pending_edit_values[project_id] = (name, description)
            reload_external = QMessageBox.question(
                self,
                "项目已在外部修改",
                "QuickRec 已停止写入，未覆盖外部内容。\n"
                "是否重新加载外部版本？选择“否”将保留本次未保存输入。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reload_external == QMessageBox.Yes:
                refreshed = self._service.reload_project(project_id)
                if not refreshed.ok:
                    self._show_error("重新加载失败", refreshed.error)
                    return
                self._pending_edit_values.pop(project_id, None)
                self.reload()
                self._select_project(project_id)
                self._status_label.setText("已重新加载外部版本")
            else:
                self._status_label.setText(
                    "已取消写入；未保存的名称和说明将在下次编辑时恢复"
                )
            return
        if not result.ok:
            self._show_error("重命名失败", result.error)
            return
        self._pending_edit_values.pop(project_id, None)
        self.reload()
        self._select_project(project_id)
        self._status_label.setText("项目名称已更新")

    def _on_archive_or_restore(self) -> None:
        project_id = self.selected_project_id
        if project_id is None or self._current_project is None:
            return
        archived = bool(self._current_project.archived_at)
        action = "恢复" if archived else "归档"
        choice = QMessageBox.question(
            self,
            f"{action}项目",
            f"确认{action}“{self._current_project.name}”？\n"
            "归档不会删除项目文件或原始视频。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if choice != QMessageBox.Yes:
            return
        result = (
            self._service.restore_project(project_id)
            if archived
            else self._service.archive_project(project_id)
        )
        if not result.ok:
            self._show_error(f"{action}失败", result.error)
            return
        self.reload()
        self._status_label.setText(f"项目已{action}")

    def _on_open_project_folder(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        try:
            folder = Path(entry.file_path).parent
            os.startfile(str(folder))
        except OSError as exc:
            self._show_error("打开目录失败", str(exc))

    def _on_relocate_project(self) -> None:
        project_id = self.selected_project_id
        if project_id is None:
            return
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "重新定位 QuickRec 项目",
            str(self._service.default_root),
            "QuickRec 项目 (project.qrproj *.qrproj);;所有文件 (*)",
        )
        if not path:
            return
        result = self._service.relink_project(project_id, path)
        if not result.ok:
            message = (
                "所选文件属于其他项目，原项目路径保持不变。"
                if result.stage == "project_id_mismatch"
                else result.error
            )
            self._show_error("重新定位失败", message)
            return
        self.reload()
        self._select_project(project_id)
        self._status_label.setText("项目已重新定位")

    def _on_recover_project(self) -> None:
        project_id = self.selected_project_id
        if project_id is None:
            return
        if QMessageBox.question(
            self,
            "从备份恢复项目",
            "恢复前会保留损坏主文件；确认使用有效备份恢复吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        result = self._service.recover_project(project_id)
        if not result.ok:
            self._show_error("备份恢复失败", result.error)
            return
        self.reload()
        self._select_project(project_id)
        self._status_label.setText("项目已从备份恢复，损坏文件已保留")

    def _on_remove_project_entry(self) -> None:
        project_id = self.selected_project_id
        if project_id is None:
            return
        if QMessageBox.question(
            self,
            "从项目列表移除",
            "仅移除本机中央项目索引，不删除项目文件或任何视频。继续吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        result = self._service.remove_project_entry(project_id)
        if not result.ok:
            self._show_error("移除失败", result.error)
            return
        self.reload()
        self._status_label.setText("项目已从列表移除，磁盘文件保持不变")

    def _on_delete_project(self) -> None:
        project_id = self.selected_project_id
        if project_id is None or self._deletion is None:
            return
        deletion = self._deletion
        plan = deletion.build_plan(project_id)
        if not plan.ok:
            self._show_error("无法删除项目", plan.error)
            return
        dialog = ProjectDeleteDialog(plan, self)
        if dialog.exec_() != dialog.Accepted:
            return
        selected_material_ids = dialog.selected_material_ids()
        self._set_delete_busy(True)

        def delete_project() -> None:
            result = deletion.execute(
                plan,
                selected_material_ids=selected_material_ids,
            )
            self.delete_finished.emit(result)

        self._delete_thread = threading.Thread(
            target=delete_project,
            name="QuickRecProjectDelete",
            daemon=True,
        )
        self._delete_thread.start()

    def _on_delete_finished(self, result) -> None:
        self._set_delete_busy(False)
        if not result.ok:
            succeeded = sum(item.ok for item in result.item_results)
            self._show_error(
                "删除未完成",
                f"阶段：{result.stage}；已完成 {succeeded} 项。"
                f"{result.error or '项目已保留，请刷新后检查。'}",
            )
            self.reload()
            return
        self.reload()
        self._status_label.setText("项目已移入回收站")

    def _set_delete_busy(self, busy: bool) -> None:
        self._project_list.setEnabled(not busy)
        self._btn_create.setEnabled(not busy)
        self._btn_open.setEnabled(not busy)
        self._btn_delete.setEnabled(
            not busy
            and self._current_project is not None
            and self._deletion is not None
            and self._current_health == "available"
        )
        if busy:
            self._status_label.setText("正在移入回收站，请稍候...")

    def _selected_entry(self):
        project_id = self.selected_project_id
        return next(
            (
                entry
                for entry in self._service.list_entries()
                if entry.project_id == project_id
            ),
            None,
        )

    def _on_add_material(self) -> None:
        project_id = self.selected_project_id
        if (
            project_id is None
            or self._current_project is None
            or self._material_service is None
        ):
            return
        loaded = self._material_service.load()
        if not loaded.ok:
            self._show_error("读取素材库失败", loaded.error)
            return
        picker = MaterialPickerDialog(
            loaded.items,
            existing_ids={item.material_id for item in self._current_project.materials},
            parent=self,
        )
        if picker.exec_() != picker.Accepted:
            return
        successes = 0
        failures: list[str] = []
        for material in picker.selected_materials():
            if self.add_material_to_project(material, project_id=project_id):
                successes += 1
            else:
                failures.append(material.file_name)
        self.reload()
        self._select_project(project_id)
        if failures:
            self._status_label.setText(
                f"已加入 {successes} 项；失败 {len(failures)} 项："
                + "、".join(failures)
            )
        else:
            self._status_label.setText(f"已加入 {successes} 项素材")

    def add_material_to_project(
        self,
        material: MaterialItem,
        *,
        project_id: str | None = None,
    ) -> bool:
        target_id = project_id or self.selected_project_id
        if (
            target_id is None
            or material.status != STATUS_AVAILABLE
            or not Path(material.file_path).is_file()
        ):
            self._status_label.setText("素材当前不可用，未加入项目")
            return False
        ref = ProjectMaterialRef(
            material_id=material.id,
            last_known_path=material.file_path,
            file_name=material.file_name,
            added_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            metadata_snapshot={
                "mode": material.mode,
                "audio_source": material.audio_source,
                "duration_sec": material.duration_sec,
                "width": material.width,
                "height": material.height,
                "fps": material.fps,
                "file_size_bytes": material.file_size_bytes,
            },
        )
        result = self._service.add_material(target_id, ref)
        if not result.ok:
            self._status_label.setText(f"加入项目失败：{result.error}")
            return False
        if self.selected_project_id == target_id:
            self.reload()
            self._select_project(target_id)
        self._status_label.setText(
            "素材已在项目中" if result.duplicate else "素材已加入项目"
        )
        return True

    def add_material_to_projects(
        self,
        material: MaterialItem,
        project_ids: list[str],
    ) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for project_id in dict.fromkeys(project_ids):
            results[project_id] = self.add_material_to_project(
                material,
                project_id=project_id,
            )
        return results

    def writable_project_entries(self, material_id: str | None = None):
        entries = []
        for entry in self._service.list_entries():
            loaded = self._service.get_project(entry.project_id)
            if (
                loaded.ok
                and loaded.project is not None
                and not loaded.project.archived_at
                and loaded.status == "available"
                and Path(entry.file_path).is_file()
                and os.access(entry.file_path, os.W_OK)
                and (
                    material_id is None
                    or all(
                        ref.material_id != material_id
                        for ref in loaded.project.materials
                    )
                )
            ):
                entries.append(entry)
        return entries

    def prompt_add_material(self, material: MaterialItem) -> None:
        candidates = self.writable_project_entries(material.id)
        if not candidates:
            self._show_error("无法加入项目", "当前没有可写的活跃项目")
            return
        dialog = ProjectTargetPickerDialog(
            candidates,
            material_name=material.file_name,
            parent=self,
        )
        if dialog.exec_() != dialog.Accepted:
            return
        project_ids = dialog.selected_project_ids()
        results = self.add_material_to_projects(material, project_ids)
        succeeded = sum(results.values())
        failed = len(results) - succeeded
        if succeeded:
            self.reload()
            if project_ids:
                self._select_project(project_ids[0])
        self._status_label.setText(
            f"已加入 {succeeded} 个项目"
            + (f"；失败 {failed} 个" if failed else "")
        )

    def _on_remove_material(self) -> None:
        project_id = self.selected_project_id
        row = self._material_table.currentRow()
        if project_id is None or row < 0:
            return
        item = self._material_table.item(row, 0)
        assert item is not None
        material_id = str(item.data(self.MATERIAL_ID_ROLE))
        if QMessageBox.question(
            self,
            "从项目移除素材",
            "只移除当前项目中的引用，原视频和全局素材记录都会保留。继续吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        result = self._service.remove_material(project_id, material_id)
        if not result.ok:
            self._show_error("移除失败", result.error)
            return
        self.reload()
        self._select_project(project_id)
        self._status_label.setText("已从项目移除；原视频保持不变")

    def _emit_recording(self, mode: str) -> None:
        project_id = self.selected_project_id
        if project_id is not None:
            self.start_recording_requested.emit(project_id, mode)

    def _show_error(self, title: str, message: str) -> None:
        self._status_label.setText(f"{title}：{message}")
        QMessageBox.warning(self, title, message)

    def show_recording_result(
        self,
        project_id: str,
        *,
        video_saved: bool,
        material_indexed: bool,
        project_linked: bool,
        message: str = "",
    ) -> None:
        if self._select_project(project_id):
            self.reload()
            self._select_project(project_id)
        states = [
            f"视频{'已保存' if video_saved else '未保存'}",
            f"素材{'已入库' if material_indexed else '未入库'}",
            f"项目{'已关联' if project_linked else '未关联'}",
        ]
        self._status_label.setText("；".join(states) + (f"；{message}" if message else ""))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_splitter"):
            self._splitter.setOrientation(
                Qt.Vertical if self.width() < 820 else Qt.Horizontal
            )
