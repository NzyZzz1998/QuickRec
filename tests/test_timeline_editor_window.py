from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication  # noqa: E402

from ui.timeline_editor_window import (  # noqa: E402
    TimelineEditorCoordinator,
    TimelineEditorWindow,
)

APP = QApplication.instance() or QApplication([])


@dataclass
class _Project:
    project_id: str
    name: str
    archived_at: str | None = None
    materials: list[object] | None = None


class _Session:
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.project = _Project(
            project_id,
            f"项目 {project_id}",
            materials=[],
        )
        self.ready = True
        self.read_only = False
        self.status = "available"
        self.error = ""
        self.refresh_count = 0

    def refresh_project_snapshot(self):
        self.refresh_count += 1
        return type("RefreshResult", (), {"ok": True})()


class _Registry:
    def __init__(self) -> None:
        self.sessions: dict[str, _Session] = {}
        self.current_session = None
        self.closed = 0
        self.shutdown_count = 0

    def open(self, project_id: str) -> _Session:
        session = self.sessions.setdefault(project_id, _Session(project_id))
        self.current_session = session
        return session

    def get(self, project_id: str) -> _Session:
        return self.sessions.setdefault(project_id, _Session(project_id))

    def close_current(self) -> None:
        self.closed += 1
        self.current_session = None

    def shutdown(self) -> None:
        self.shutdown_count += 1
        self.current_session = None


class _Window:
    def __init__(self) -> None:
        self.sessions: list[_Session] = []
        self.maximized = 0
        self.shown = 0
        self.raised = 0
        self.activated = 0
        self.hidden = 0
        self.shutdown_count = 0

    def set_session(self, session: _Session) -> None:
        self.sessions.append(session)

    def showMaximized(self) -> None:
        self.maximized += 1

    def show(self) -> None:
        self.shown += 1

    def raise_(self) -> None:
        self.raised += 1

    def activateWindow(self) -> None:
        self.activated += 1

    def hide(self) -> None:
        self.hidden += 1

    def shutdown(self) -> None:
        self.shutdown_count += 1


def test_editor_window_has_expected_size_and_top_level_lifecycle():
    window = TimelineEditorWindow()

    assert window.minimumWidth() == 960
    assert window.minimumHeight() == 640
    assert window.windowTitle() == "QuickRec 剪辑工作台"
    assert window.parent() is None
    assert window._main_splitter.orientation() != window._workspace_splitter.orientation()

    window.shutdown()


def test_coordinator_creates_one_window_defaults_to_maximized_and_reactivates():
    registry = _Registry()
    created: list[_Window] = []

    def factory() -> _Window:
        window = _Window()
        created.append(window)
        return window

    coordinator = TimelineEditorCoordinator(factory, registry)
    first = coordinator.open("project-1")
    second = coordinator.open("project-1")

    assert first is second
    assert len(created) == 1
    assert first.maximized == 1
    assert first.shown == 1
    assert first.raised == 2
    assert first.activated == 2
    assert [item.project_id for item in first.sessions] == [
        "project-1",
        "project-1",
    ]


def test_coordinator_switches_project_and_shutdown_closes_both_layers():
    registry = _Registry()
    window = _Window()
    coordinator = TimelineEditorCoordinator(lambda: window, registry)

    coordinator.open("project-1")
    coordinator.open("project-2")
    coordinator.hide()
    coordinator.shutdown()

    assert [item.project_id for item in window.sessions] == [
        "project-1",
        "project-2",
    ]
    assert window.hidden == 1
    assert registry.closed == 1
    assert window.shutdown_count == 1
    assert registry.shutdown_count == 1


def test_coordinator_suspend_hides_window_without_releasing_project_session():
    registry = _Registry()
    window = _Window()
    coordinator = TimelineEditorCoordinator(lambda: window, registry)
    coordinator.open("project-1")

    coordinator.suspend()

    assert window.hidden == 1
    assert registry.closed == 0
    assert registry.current_session is not None


def test_coordinator_refreshes_visible_matching_project_without_reopening():
    registry = _Registry()
    window = _Window()
    coordinator = TimelineEditorCoordinator(lambda: window, registry)
    coordinator.open("project-1")

    refreshed = coordinator.refresh_project("project-1")
    ignored = coordinator.refresh_project("project-2")

    assert refreshed
    assert not ignored
    assert [item.project_id for item in window.sessions] == [
        "project-1",
        "project-1",
    ]
    assert registry.current_session.refresh_count == 1


def test_corrupt_timeline_keeps_project_material_surface_and_recovery_actions():
    project = _Project(
        "project-corrupt",
        "损坏项目",
        materials=[],
    )
    commands = type(
        "Commands",
        (),
        {"timeline_backup_available": True, "has_pending_save": False},
    )()
    session = type(
        "CorruptSession",
        (),
        {
            "project_id": "project-corrupt",
            "project": project,
            "ready": False,
            "read_only": True,
            "status": "corrupt",
            "error": "timeline extension is corrupt",
            "recording_active": False,
            "commands": commands,
        },
    )()
    window = TimelineEditorWindow()

    window.set_session(session)

    assert window._project_name.text() == "损坏项目"
    assert window._material_list.isEnabled()
    assert window._timeline_canvas.clip_count == 0
    assert not window._btn_restore_timeline.isHidden()
    assert not window._btn_rebuild_timeline.isHidden()
    assert "损坏" in window._save_status.text()
    window.shutdown()
