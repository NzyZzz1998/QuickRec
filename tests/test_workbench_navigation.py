from __future__ import annotations

from enum import StrEnum

from services.workbench_navigation import WorkbenchNavigationController


class _Page(StrEnum):
    RECORDING = "recording"
    MATERIALS = "materials"
    PROJECTS = "projects"
    EXPORTS = "exports"
    SETTINGS = "settings"
    DIAGNOSTICS = "diagnostics"


class _Refreshable:
    def __init__(self) -> None:
        self.calls = 0

    def reload(self) -> None:
        self.calls += 1


class _RecordingPage:
    def __init__(self) -> None:
        self.calls = 0

    def refresh_summary(self) -> None:
        self.calls += 1


class _SettingsPage:
    def __init__(self) -> None:
        self.states: list[bool] = []

    def set_recording_active(self, active: bool) -> None:
        self.states.append(active)


def _controller(*, active: bool = False):
    opened: list[object | None] = []
    synced: list[str] = []
    pages = {
        "recording": _RecordingPage(),
        "materials": _Refreshable(),
        "projects": _Refreshable(),
        "exports": type("ExportPage", (), {"calls": 0, "refresh": lambda self: setattr(self, "calls", self.calls + 1)})(),
        "settings": _SettingsPage(),
    }
    window = object()
    controller = WorkbenchNavigationController(
        open_window=lambda page: (opened.append(page), window)[1],
        resolve_page=pages.get,
        sync_runtime=lambda: synced.append("sync"),
        is_recording_active=lambda: active,
    )
    return controller, pages, opened, synced, window


def test_open_syncs_runtime_and_refreshes_target_plus_recording_summary() -> None:
    controller, pages, opened, synced, window = _controller()

    result = controller.open(_Page.MATERIALS)

    assert result is window
    assert opened == [_Page.MATERIALS]
    assert synced == ["sync"]
    assert pages["materials"].calls == 1
    assert pages["recording"].calls == 1


def test_open_recording_page_does_not_refresh_summary_twice() -> None:
    controller, pages, _opened, _synced, _window = _controller()

    controller.open(_Page.RECORDING)

    assert pages["recording"].calls == 1


def test_page_changed_refreshes_page_and_injects_recording_state() -> None:
    controller, pages, _opened, _synced, _window = _controller(active=True)

    controller.page_changed(_Page.PROJECTS)
    controller.page_changed(_Page.EXPORTS)
    controller.page_changed(_Page.SETTINGS)

    assert pages["projects"].calls == 1
    assert pages["exports"].calls == 1
    assert pages["settings"].states == [True]


def test_missing_optional_page_is_a_safe_noop() -> None:
    controller, _pages, _opened, _synced, _window = _controller()

    controller.page_changed(_Page.DIAGNOSTICS)
