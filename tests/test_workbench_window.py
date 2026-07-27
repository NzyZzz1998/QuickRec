from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtWidgets import QApplication, QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ui.workbench_window import (  # noqa: E402, I001
    clamp_workbench_geometry,
    WorkbenchCoordinator,
    WorkbenchPage,
    WorkbenchWindow,
)
import main  # noqa: E402
from config import ConfigManager  # noqa: E402
from services.material_ingestion import MaterialIngestionCoordinator  # noqa: E402
from services.pending_recordings import PendingRecordingService  # noqa: E402
from services.project_library import ProjectLibraryService  # noqa: E402
from services.recording_library import RecordingLibraryService  # noqa: E402
from ui.material_library_dialog import MaterialLibraryDialog  # noqa: E402
from ui.project_page import ProjectPage  # noqa: E402
from ui.settings_dialog import SettingsDialog  # noqa: E402
from ui.workbench_pages import DiagnosticPage, RecordingPage  # noqa: E402


APP = QApplication.instance() or QApplication([])


class FakeWorkbenchWindow:
    def __init__(self) -> None:
        self.current_page = WorkbenchPage.RECORDING
        self.show_count = 0
        self.raise_count = 0
        self.activate_count = 0
        self.hide_count = 0
        self.pages: list[WorkbenchPage] = []

    def set_current_page(self, page: WorkbenchPage) -> None:
        self.current_page = page
        self.pages.append(page)

    def show(self) -> None:
        self.show_count += 1

    def raise_(self) -> None:
        self.raise_count += 1

    def activateWindow(self) -> None:
        self.activate_count += 1

    def hide(self) -> None:
        self.hide_count += 1


def test_coordinator_creates_one_global_window_and_reactivates_it():
    created: list[FakeWorkbenchWindow] = []

    def factory() -> FakeWorkbenchWindow:
        window = FakeWorkbenchWindow()
        created.append(window)
        return window

    coordinator = WorkbenchCoordinator(factory)

    first = coordinator.open(WorkbenchPage.MATERIALS)
    second = coordinator.open(WorkbenchPage.SETTINGS)

    assert first is second
    assert len(created) == 1
    assert first.pages == [WorkbenchPage.MATERIALS, WorkbenchPage.SETTINGS]
    assert first.show_count == 2
    assert first.raise_count == 2
    assert first.activate_count == 2


def test_coordinator_restores_last_page_only_within_same_process():
    first_window = FakeWorkbenchWindow()
    coordinator = WorkbenchCoordinator(lambda: first_window)
    coordinator.open(WorkbenchPage.DIAGNOSTICS)
    coordinator.hide()

    coordinator.open()

    assert first_window.current_page == WorkbenchPage.DIAGNOSTICS
    assert first_window.hide_count == 1

    new_window = FakeWorkbenchWindow()
    new_process_coordinator = WorkbenchCoordinator(lambda: new_window)
    new_process_coordinator.open()

    assert new_window.current_page == WorkbenchPage.RECORDING


def test_coordinator_restores_live_window_page_after_window_hides_itself():
    window = FakeWorkbenchWindow()
    coordinator = WorkbenchCoordinator(lambda: window)
    coordinator.open()
    window.set_current_page(WorkbenchPage.MATERIALS)
    window.hide()

    coordinator.open()

    assert window.current_page == WorkbenchPage.MATERIALS


def test_workbench_has_expected_default_and_minimum_size():
    window = WorkbenchWindow()

    assert window.size().width() == 1200
    assert window.size().height() == 760
    assert window.minimumWidth() == 960
    assert window.minimumHeight() == 640
    assert window.current_page == WorkbenchPage.RECORDING
    assert set(window.page_widgets) == set(WorkbenchPage)
    assert all(
        button.property("role") == "nav"
        for button in window._nav_buttons.values()
    )
    assert all(
        not button.icon().isNull()
        for button in window._nav_buttons.values()
    )

    window.close()


def test_workbench_page_order_includes_projects_between_materials_and_settings():
    assert list(WorkbenchPage) == [
        WorkbenchPage.RECORDING,
        WorkbenchPage.MATERIALS,
        WorkbenchPage.PROJECTS,
        WorkbenchPage.SETTINGS,
        WorkbenchPage.DIAGNOSTICS,
    ]


def test_workbench_sidebar_status_tracks_recording_lifecycle():
    window = WorkbenchWindow()

    window.set_runtime_status("recording")
    assert "录制中" in window._sidebar_status.text()

    window.set_runtime_status("paused")
    assert "已暂停" in window._sidebar_status.text()

    window.set_runtime_status("saving")
    assert "正在保存" in window._sidebar_status.text()

    window.set_runtime_status("idle")
    assert window._sidebar_status.text() == "空闲\n托盘持续运行"
    window.close()


def test_workbench_close_hides_without_destroying_window():
    window = WorkbenchWindow()
    window.show()

    window.close()

    assert window.isHidden()
    assert window.testAttribute(Qt.WA_DeleteOnClose) is False


def test_clamp_workbench_geometry_moves_offscreen_window_into_visible_area():
    saved = {
        "x": 8000,
        "y": -5000,
        "width": 1200,
        "height": 760,
        "maximized": False,
    }

    clamped = clamp_workbench_geometry(
        saved,
        [QRect(0, 0, 1920, 1080)],
        minimum_size=(960, 640),
    )

    assert clamped["x"] == 720
    assert clamped["y"] == 0
    assert clamped["width"] == 1200
    assert clamped["height"] == 760


def test_page_navigation_stays_on_current_page_when_dirty_guard_cancels():
    class GuardedPage(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.allow_navigation = False
            self.confirm_count = 0

        def confirm_navigation(self) -> bool:
            self.confirm_count += 1
            return self.allow_navigation

    guarded = GuardedPage()
    pages = {WorkbenchPage.RECORDING: guarded}
    window = WorkbenchWindow(pages=pages)

    changed = window.set_current_page(WorkbenchPage.SETTINGS)

    assert changed is False
    assert guarded.confirm_count == 1
    assert window.current_page == WorkbenchPage.RECORDING

    guarded.allow_navigation = True
    changed = window.set_current_page(WorkbenchPage.SETTINGS)

    assert changed is True
    assert window.current_page == WorkbenchPage.SETTINGS
    window.close()


def test_application_factory_embeds_all_real_pages_and_preserves_material_query():
    class IdleWorkflow:
        @staticmethod
        def get_state():
            return main.RecorderState.IDLE

    class Recorder:
        @staticmethod
        def get_mode():
            return main.RecordMode.FULLSCREEN

    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        config = ConfigManager.__new__(ConfigManager)
        config.config_path = base / "config.json"
        config._config = ConfigManager.defaults.copy()
        config._config["save_path"] = str(base / "videos")

        app = main.QuickRecApp.__new__(main.QuickRecApp)
        app._config = config
        app._library_service = RecordingLibraryService(base / "recordings.json")
        app._project_service = ProjectLibraryService(
            base / "projects.json",
            default_root=base / "project-files",
        )
        app._pending_service = PendingRecordingService(base / "pending.json")
        app._ingestion_coordinator = MaterialIngestionCoordinator(
            app._library_service,
            app._pending_service,
        )
        app._initial_migration_result = None
        app._workflow = IdleWorkflow()
        app._recorder = Recorder()
        app._recording_page = None
        app._material_library_dialog = None
        app._project_page = None
        app._settings_page = None
        app._diagnostic_page = None

        with patch("ui.settings_dialog.is_autostart_enabled", return_value=False):
            window = app._create_workbench_window()

        assert isinstance(
            window.page_widgets[WorkbenchPage.RECORDING],
            RecordingPage,
        )
        assert isinstance(
            window.page_widgets[WorkbenchPage.MATERIALS],
            MaterialLibraryDialog,
        )
        assert isinstance(
            window.page_widgets[WorkbenchPage.PROJECTS],
            ProjectPage,
        )
        assert isinstance(
            window.page_widgets[WorkbenchPage.SETTINGS],
            SettingsDialog,
        )
        assert isinstance(
            window.page_widgets[WorkbenchPage.DIAGNOSTICS],
            DiagnosticPage,
        )
        assert app._material_library_dialog._close_button.isHidden()

        app._material_library_dialog._query_session.visible_count = 100
        window.set_current_page(WorkbenchPage.MATERIALS)
        window.set_current_page(WorkbenchPage.SETTINGS)
        window.set_current_page(WorkbenchPage.MATERIALS)

        assert app._material_library_dialog._query_session.visible_count == 100
        window.close()
