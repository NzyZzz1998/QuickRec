from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.project_library import ProjectLibraryService  # noqa: E402
from services.timeline_session import (  # noqa: E402
    TimelineSession,
    TimelineSessionRegistry,
    TimelineViewState,
)
from utils.project_store import ProjectMaterialRef  # noqa: E402


class _MediaHandle:
    def __init__(self) -> None:
        self.pause_count = 0
        self.release_count = 0

    def pause(self) -> None:
        self.pause_count += 1

    def release(self) -> None:
        self.release_count += 1


def _project_service(base: Path) -> ProjectLibraryService:
    service = ProjectLibraryService(
        base / "projects.json",
        default_root=base / "projects",
    )
    assert service.create_project(
        name="项目一",
        project_id="project-1",
    ).ok
    assert service.create_project(
        name="项目二",
        project_id="project-2",
    ).ok
    return service


def test_view_state_normalizes_ranges_and_mutually_exclusive_layout_modes():
    state = TimelineViewState(
        zoom=99,
        horizontal_scroll_us=-20,
        vertical_scroll=-2,
        playhead_us=-10,
        splitter_ratio=0.99,
        preview_maximized=True,
        timeline_focused=True,
    ).normalized()

    assert state.zoom == 8.0
    assert state.horizontal_scroll_us == 0
    assert state.vertical_scroll == 0
    assert state.playhead_us == 0
    assert state.splitter_ratio == 0.8
    assert state.preview_maximized
    assert not state.timeline_focused


def test_view_state_preserves_zoom_needed_to_fit_long_timeline():
    state = TimelineViewState(zoom=0.005).normalized()

    assert state.zoom == 0.005


def test_session_exposes_project_timeline_and_transient_view_state():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _project_service(Path(temp_dir))
        session = TimelineSession(service, "project-1")

        session.update_view_state(
            selected_track_id="track-video-1",
            playhead_us=2_500_000,
            zoom=2.0,
        )

        assert session.ready
        assert session.project_id == "project-1"
        assert session.project.name == "项目一"
        assert session.timeline.timeline_id
        assert session.view_state.selected_track_id == "track-video-1"
        assert session.view_state.playhead_us == 2_500_000
        assert session.view_state.zoom == 2.0


def test_recording_state_temporarily_blocks_timeline_commands_and_persistence():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _project_service(Path(temp_dir))
        session = TimelineSession(service, "project-1")
        entry = service.get_entry("project-1")
        assert entry is not None
        project_path = Path(entry.file_path)
        before_file = project_path.read_bytes()
        before_timeline = session.timeline

        session.set_recording_active(True)
        blocked = session.commands.add_track("video")

        assert session.recording_active
        assert session.recording_guard.state.active
        assert session.read_only
        assert not blocked.ok
        assert blocked.stage == "read_only"
        assert "recording" in blocked.error
        assert session.timeline == before_timeline
        assert project_path.read_bytes() == before_file

        session.set_recording_active(False)
        resumed = session.commands.add_track("video")

        assert not session.recording_active
        assert not session.recording_guard.state.active
        assert not session.read_only
        assert resumed.ok


def test_registry_reuses_project_state_and_releases_previous_media():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _project_service(Path(temp_dir))
        handles: dict[str, _MediaHandle] = {}

        def factory(project_id: str) -> TimelineSession:
            handle = _MediaHandle()
            handles[project_id] = handle
            session = TimelineSession(service, project_id)
            session.attach_media(handle)
            return session

        registry = TimelineSessionRegistry(factory)
        first = registry.open("project-1")
        first.update_view_state(playhead_us=3_000_000, zoom=1.75)

        second = registry.open("project-2")
        restored = registry.open("project-1")

        assert second.project_id == "project-2"
        assert restored is first
        assert restored.view_state.playhead_us == 3_000_000
        assert restored.view_state.zoom == 1.75
        assert handles["project-1"].pause_count == 1
        assert handles["project-1"].release_count == 1
        assert handles["project-2"].pause_count == 1
        assert handles["project-2"].release_count == 1


def test_registry_get_reuses_session_without_switching_current_project():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _project_service(Path(temp_dir))
        registry = TimelineSessionRegistry(
            lambda project_id: TimelineSession(service, project_id)
        )
        current = registry.open("project-1")

        background = registry.get("project-2")

        assert registry.current_session is current
        assert background.project_id == "project-2"
        assert registry.get("project-2") is background


def test_registry_applies_active_recording_lock_to_sessions_created_later():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _project_service(Path(temp_dir))
        registry = TimelineSessionRegistry(
            lambda project_id: TimelineSession(service, project_id)
        )

        registry.set_recording_active(True)
        session = registry.open("project-1")

        assert session.recording_active
        assert session.read_only
        assert not session.commands.add_track("video").ok


def test_registry_reopen_refreshes_cached_project_snapshot():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _project_service(Path(temp_dir))
        registry = TimelineSessionRegistry(
            lambda project_id: TimelineSession(service, project_id)
        )
        first = registry.open("project-1")
        registry.close_current()
        added = service.add_material(
            "project-1",
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=r"E:\QRtest\中文 空格\demo.mp4",
                file_name="demo.mp4",
                added_at="2026-07-28T11:10:00+08:00",
                metadata_snapshot={"duration_sec": 1.0},
            ),
            now="2026-07-28T11:10:00+08:00",
        )
        assert added.ok

        reopened = registry.open("project-1")

        assert reopened is first
        assert [item.material_id for item in reopened.project.materials] == [
            "material-1"
        ]


def test_registry_shutdown_releases_active_media_and_clears_sessions():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _project_service(Path(temp_dir))
        handle = _MediaHandle()

        def factory(project_id: str) -> TimelineSession:
            session = TimelineSession(service, project_id)
            session.attach_media(handle)
            return session

        registry = TimelineSessionRegistry(factory)
        registry.open("project-1")

        registry.shutdown()

        assert registry.current_session is None
        assert registry.session_count == 0
        assert handle.pause_count == 1
        assert handle.release_count == 1


def test_session_exposes_typed_media_runtime_with_compatible_delegates():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _project_service(Path(temp_dir))
        session = TimelineSession(service, "project-1")
        handle = _MediaHandle()

        session.attach_media(handle)
        assert session.media_runtime.current is handle

        session.pause_media()
        session.release_media()

        assert handle.pause_count == 2
        assert handle.release_count == 1
        assert session.media_runtime.current is None


def test_session_exposes_and_updates_project_editing_profile():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = ProjectLibraryService(
            Path(temp_dir) / "projects.json",
            default_root=Path(temp_dir) / "projects",
        )
        assert service.create_project(
            name="帧率测试项目",
            project_id="project-fps",
            editing_fps=60,
        ).ok
        session = TimelineSession(service, "project-fps")

        assert session.editing_fps == 60
        assert not session.editing_fps_locked
        assert session.editing_profile_persisted
        assert session.editing_profile_status == "ready"
        assert session.editing_profile_error == ""

        changed = session.set_editing_fps(120)

        assert changed.ok
        assert session.editing_fps == 120
