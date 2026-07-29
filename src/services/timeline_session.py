"""QuickRec Full 时间线会话与同进程瞬时界面状态。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, cast

from services.project_library import ProjectLibraryService
from services.recording_guard import RecordingGuard
from services.timeline_commands import TimelineCommandResult, TimelineCommandService
from services.timeline_media_runtime import (
    TimelineMediaRuntime,
    TimelinePlaybackRuntime,
)
from utils.project_store import ProjectFile
from utils.timeline_model import Timeline
from utils.timeline_view import normalize_timeline_zoom


@dataclass(frozen=True)
class TimelineViewState:
    """不写入项目文件的剪辑工作台瞬时状态。"""

    selected_track_id: str | None = None
    selected_clip_id: str | None = None
    zoom: float = 1.0
    horizontal_scroll_us: int = 0
    vertical_scroll: int = 0
    playhead_us: int = 0
    splitter_ratio: float = 0.68
    materials_collapsed: bool = False
    preview_maximized: bool = False
    timeline_focused: bool = False

    def normalized(self) -> TimelineViewState:
        preview_maximized = bool(self.preview_maximized)
        return replace(
            self,
            zoom=normalize_timeline_zoom(self.zoom),
            horizontal_scroll_us=max(0, int(self.horizontal_scroll_us)),
            vertical_scroll=max(0, int(self.vertical_scroll)),
            playhead_us=max(0, int(self.playhead_us)),
            splitter_ratio=min(0.8, max(0.2, float(self.splitter_ratio))),
            preview_maximized=preview_maximized,
            timeline_focused=(
                False if preview_maximized else bool(self.timeline_focused)
            ),
        )


class TimelineSession:
    """绑定单个项目的命令服务、瞬时界面状态和媒体资源。"""

    def __init__(
        self,
        project_service: ProjectLibraryService,
        project_id: str,
        *,
        command_service: TimelineCommandService | None = None,
        view_state: TimelineViewState | None = None,
        recording_guard: RecordingGuard | None = None,
        media_runtime: TimelineMediaRuntime | None = None,
    ) -> None:
        self.project_id = str(project_id)
        self.commands = command_service or TimelineCommandService(
            project_service,
            self.project_id,
        )
        self._view_state = (view_state or TimelineViewState()).normalized()
        self._recording_guard = recording_guard or RecordingGuard()
        self._media_runtime = media_runtime or TimelineMediaRuntime()
        guard_state = self._recording_guard.state
        self.commands.set_runtime_read_only(
            guard_state.active,
            reason=guard_state.reason,
        )

    @property
    def ready(self) -> bool:
        return self.commands.ready

    @property
    def status(self) -> str:
        return self.commands.status

    @property
    def error(self) -> str:
        return self.commands.error

    @property
    def read_only(self) -> bool:
        return self.commands.read_only

    @property
    def project(self) -> ProjectFile:
        return self.commands.project

    @property
    def timeline(self) -> Timeline:
        return self.commands.timeline

    @property
    def view_state(self) -> TimelineViewState:
        return self._view_state

    @property
    def recording_active(self) -> bool:
        return self._recording_guard.state.active

    @property
    def recording_guard(self) -> RecordingGuard:
        return self._recording_guard

    @property
    def media_runtime(self) -> TimelineMediaRuntime:
        return self._media_runtime

    @property
    def timeline_backup_available(self) -> bool:
        return self.commands.timeline_backup_available

    def update_view_state(self, **changes: object) -> TimelineViewState:
        unknown = set(changes) - set(TimelineViewState.__dataclass_fields__)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown timeline view state fields: {names}")
        current = self._view_state
        selected_track = changes.get(
            "selected_track_id",
            current.selected_track_id,
        )
        selected_clip = changes.get(
            "selected_clip_id",
            current.selected_clip_id,
        )
        self._view_state = TimelineViewState(
            selected_track_id=(
                None if selected_track is None else str(selected_track)
            ),
            selected_clip_id=(
                None if selected_clip is None else str(selected_clip)
            ),
            zoom=float(cast(Any, changes.get("zoom", current.zoom))),
            horizontal_scroll_us=int(
                cast(
                    Any,
                    changes.get(
                        "horizontal_scroll_us",
                        current.horizontal_scroll_us,
                    ),
                )
            ),
            vertical_scroll=int(
                cast(
                    Any,
                    changes.get("vertical_scroll", current.vertical_scroll),
                )
            ),
            playhead_us=int(
                cast(
                    Any,
                    changes.get("playhead_us", current.playhead_us),
                )
            ),
            splitter_ratio=float(
                cast(
                    Any,
                    changes.get("splitter_ratio", current.splitter_ratio),
                )
            ),
            materials_collapsed=bool(
                changes.get(
                    "materials_collapsed",
                    current.materials_collapsed,
                )
            ),
            preview_maximized=bool(
                changes.get(
                    "preview_maximized",
                    current.preview_maximized,
                )
            ),
            timeline_focused=bool(
                changes.get(
                    "timeline_focused",
                    current.timeline_focused,
                )
            ),
        ).normalized()
        return self._view_state

    def set_recording_active(self, active: bool) -> None:
        if active:
            self._recording_guard.activate(
                "recording is active; timeline editing is disabled"
            )
        else:
            self._recording_guard.release()
        guard_state = self._recording_guard.state
        self.commands.set_runtime_read_only(
            guard_state.active,
            reason=guard_state.reason,
        )

    def recover_timeline_from_backup(self):
        return self.commands.recover_timeline_from_backup()

    def rebuild_empty_timeline(self):
        return self.commands.rebuild_empty_timeline()

    def refresh_project_snapshot(self) -> TimelineCommandResult:
        return self.commands.refresh_project_snapshot()

    def attach_media(self, media: TimelinePlaybackRuntime) -> None:
        self._media_runtime.attach(media)

    def pause_media(self) -> None:
        self._media_runtime.pause()

    def release_media(self) -> None:
        self._media_runtime.release()


class TimelineSessionRegistry:
    """按项目缓存会话，并保证切换前释放旧项目媒体资源。"""

    def __init__(
        self,
        factory: Callable[[str], TimelineSession],
    ) -> None:
        self._factory = factory
        self._sessions: dict[str, TimelineSession] = {}
        self._current_project_id: str | None = None
        self._recording_active = False

    @property
    def current_session(self) -> TimelineSession | None:
        if self._current_project_id is None:
            return None
        return self._sessions.get(self._current_project_id)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def open(self, project_id: str) -> TimelineSession:
        target_id = str(project_id)
        current = self.current_session
        if current is not None and current.project_id != target_id:
            current.release_media()
        session = self._sessions.get(target_id)
        if session is None:
            session = self.get(target_id)
        else:
            refreshed = session.refresh_project_snapshot()
            if not refreshed.ok and not session.commands.has_pending_save:
                session.commands.reload()
        self._current_project_id = target_id
        return session

    def get(self, project_id: str) -> TimelineSession:
        """取得或创建项目会话，但不改变当前激活项目。"""
        target_id = str(project_id)
        session = self._sessions.get(target_id)
        if session is None:
            session = self._factory(target_id)
            session.set_recording_active(self._recording_active)
            self._sessions[target_id] = session
        return session

    def close_current(self) -> None:
        current = self.current_session
        if current is not None:
            current.release_media()
        self._current_project_id = None

    def set_recording_active(self, active: bool) -> None:
        self._recording_active = bool(active)
        for session in self._sessions.values():
            session.set_recording_active(self._recording_active)

    def shutdown(self) -> None:
        for session in self._sessions.values():
            session.release_media()
        self._sessions.clear()
        self._current_project_id = None
