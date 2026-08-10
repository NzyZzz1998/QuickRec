"""工作台打开、页面刷新与运行状态同步的应用层协调。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class WorkbenchNavigationController[WindowT]:
    """集中工作台路由副作用，避免应用装配根理解每个页面细节。"""

    _REFRESH_METHODS = {
        "recording": "refresh_summary",
        "materials": "reload",
        "projects": "reload",
        "exports": "refresh",
    }

    def __init__(
        self,
        *,
        open_window: Callable[[Any], WindowT],
        resolve_page: Callable[[str], object | None],
        sync_runtime: Callable[[], None],
        is_recording_active: Callable[[], bool],
    ) -> None:
        self._open_window = open_window
        self._resolve_page = resolve_page
        self._sync_runtime = sync_runtime
        self._is_recording_active = is_recording_active

    def open(self, page: Any = None) -> WindowT:
        window = self._open_window(page)
        self._sync_runtime()
        page_key = self._page_key(page)
        if page_key and page_key != "recording":
            self._refresh(page_key)
        self._refresh("recording")
        return window

    def page_changed(self, page: object) -> None:
        page_key = self._page_key(page)
        if page_key == "settings":
            settings = self._resolve_page("settings")
            setter = getattr(settings, "set_recording_active", None)
            if callable(setter):
                setter(self._is_recording_active())
            return
        self._refresh(page_key)

    @staticmethod
    def _page_key(page: object | None) -> str:
        if page is None:
            return ""
        return str(getattr(page, "value", page))

    def _refresh(self, page_key: str) -> None:
        method_name = self._REFRESH_METHODS.get(page_key)
        if method_name is None:
            return
        page = self._resolve_page(page_key)
        refresh = getattr(page, method_name, None)
        if callable(refresh):
            refresh()
