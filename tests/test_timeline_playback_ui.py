from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication  # noqa: E402

from services.playback_backend import (  # noqa: E402
    BackendCapabilities,
    BackendFrame,
)
from services.playback_runtime import (  # noqa: E402
    PlaybackRuntime,
    PlaybackState,
)
from services.project_library import ProjectLibraryService  # noqa: E402
from services.project_materials import (  # noqa: E402
    PreviewState,
    ProjectMaterialDescriptor,
)
from services.timeline_session import TimelineSession  # noqa: E402
from ui.timeline_editor_window import TimelineEditorWindow  # noqa: E402
from utils.project_store import ProjectMaterialRef  # noqa: E402

APP = QApplication.instance() or QApplication([])


class FakeClock:
    def __init__(self) -> None:
        self.value_us = 0

    def __call__(self) -> int:
        return self.value_us

    def advance(self, value_us: int) -> None:
        self.value_us += int(value_us)


class FakePlaybackBackend:
    capabilities = BackendCapabilities("fake", "1.0")

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.next_prepare = BackendFrame()
        self.next_render = BackendFrame(
            video_frame=np.full((90, 160, 3), 120, dtype=np.uint8),
            video_status="ready",
        )
        self.muted = False
        self.release_count = 0

    def prepare(self, _plan):
        self.calls.append("prepare")
        return self.next_prepare

    def play(self):
        self.calls.append("play")
        return BackendFrame()

    def pause(self):
        self.calls.append("pause")
        return BackendFrame()

    def seek(self, _plan):
        self.calls.append("seek")
        return BackendFrame()

    def render(self, _plan):
        self.calls.append("render")
        return self.next_render

    def stop_audio(self):
        self.calls.append("stop_audio")

    def set_muted(self, muted):
        self.muted = bool(muted)
        self.calls.append("set_muted")

    def release(self):
        self.release_count += 1
        self.calls.append("release")


def _session(
    base: Path,
    *,
    has_audio: bool = False,
    duration_sec: float = 3.0,
) -> TimelineSession:
    service = ProjectLibraryService(
        base / "projects.json",
        default_root=base / "projects",
    )
    assert service.create_project(
        name="播放项目",
        project_id="project-1",
    ).ok
    project = service.get_project("project-1").project
    assert project is not None
    source = base / "中文 播放素材.mp4"
    source.write_bytes(b"media")
    project.materials.append(
        ProjectMaterialRef(
            "material-1",
            str(source),
            source.name,
            "2026-07-28T10:00:00+08:00",
            {
                "duration_sec": duration_sec,
                "audio_source": "both" if has_audio else "none",
            },
        )
    )
    assert service.commit_project_candidate("project-1", project).ok
    session = TimelineSession(service, "project-1")
    assert session.commands.add_material(
        "material-1",
        has_audio=has_audio,
    ).ok
    return session


def test_play_pause_button_uses_matching_icons(monkeypatch) -> None:
    import ui.timeline_editor_window as editor_module

    icon_calls = []
    original_set_button_icon = editor_module.set_button_icon

    def record_icon(button, name, **kwargs):
        icon_calls.append((button, name))
        return original_set_button_icon(button, name, **kwargs)

    monkeypatch.setattr(editor_module, "set_button_icon", record_icon)

    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        backend = FakePlaybackBackend()
        window = TimelineEditorWindow(
            playback_runtime_factory=lambda project, timeline: PlaybackRuntime(
                project,
                timeline,
                backend,
            )
        )
        window.set_session(session)

        def play_icon_names() -> list[str]:
            return [
                name
                for button, name in icon_calls
                if button is window._btn_play
            ]

        assert play_icon_names()[-1] == "play"

        window._btn_play.click()
        assert window._btn_play.text() == "暂停"
        assert play_icon_names()[-1] == "pause"

        window._btn_play.click()
        assert window._btn_play.text() == "播放"
        assert play_icon_names()[-1] == "play"
        window.shutdown()


def test_single_material_playback_ends_at_its_clip_boundary() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir), duration_sec=2.0)
        backend = FakePlaybackBackend()
        clock = FakeClock()
        window = TimelineEditorWindow(
            playback_runtime_factory=lambda project, timeline: PlaybackRuntime(
                project,
                timeline,
                backend,
                clock_us=clock,
            )
        )
        window.set_session(session)

        window._btn_play.click()
        clock.advance(2_500_000)
        window._on_playback_tick()

        runtime = window._playback_runtime
        assert runtime is not None
        snapshot = runtime.snapshot()
        assert snapshot.state == PlaybackState.ENDED
        assert snapshot.position_us == 2_000_000
        assert snapshot.duration_us == 2_000_000
        assert window._time_label.text() == "00:02.000 / 00:02.000"
        assert window._btn_play.text() == "播放"
        assert window._preview_status.text() == "播放结束"
        assert not window._playback_timer.isActive()
        window.shutdown()


def test_editor_play_pause_updates_surface_playhead_and_releases_runtime() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        backend = FakePlaybackBackend()
        clock = FakeClock()
        window = TimelineEditorWindow(
            playback_runtime_factory=lambda project, timeline: PlaybackRuntime(
                project,
                timeline,
                backend,
                clock_us=clock,
            )
        )
        window.set_session(session)

        assert window._btn_play.isEnabled()
        window._btn_play.click()
        clock.advance(100_000)
        window._on_playback_tick()

        assert window._btn_play.text() == "暂停"
        assert window._playback_timer.isActive()
        assert window._timeline_canvas._playhead_us == 100_000
        assert not window._preview_surface.pixmap().isNull()
        assert "00:00.100" in window._time_label.text()

        window._btn_play.click()
        assert window._btn_play.text() == "播放"
        assert not window._playback_timer.isActive()

        window.shutdown()
        assert backend.release_count == 1


def test_audio_unavailable_can_continue_muted_without_reprompt() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir), has_audio=True)
        backend = FakePlaybackBackend()
        backend.next_prepare = BackendFrame(
            ok=False,
            audio_unavailable=True,
            error_kind="audio_device_unavailable",
            error="no output device",
        )
        window = TimelineEditorWindow(
            playback_runtime_factory=lambda project, timeline: PlaybackRuntime(
                project,
                timeline,
                backend,
            ),
            audio_decision_provider=lambda: "mute",
        )
        window.set_session(session)

        window._btn_play.click()

        assert backend.muted
        assert backend.calls.count("prepare") == 1
        assert backend.calls.count("play") == 1
        assert window._btn_play.text() == "暂停"
        assert "无声" in window._preview_status.text()
        window.shutdown()


def test_playback_uses_relocated_central_path_without_mutating_project(
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        session = _session(base)
        original_project = session.project
        old_path = original_project.materials[0].last_known_path
        original_clip_id = session.timeline.clips[0].clip_id
        relocated = base / "重新定位 后的素材.mp4"
        relocated.write_bytes(b"media")
        captured_projects = []
        backend = FakePlaybackBackend()

        descriptor = ProjectMaterialDescriptor(
            project_id="project-1",
            material_id="material-1",
            file_path=str(relocated),
            file_name=relocated.name,
            file_exists=True,
            business_status="available",
            duration_sec=3.0,
            width=1920,
            height=1080,
            fps=60.0,
            mode="fullscreen",
            audio_source="none",
            file_size_bytes=relocated.stat().st_size,
            preview_path=None,
            preview_state=PreviewState.NOT_GENERATED,
        )

        def runtime_factory(project, timeline):
            captured_projects.append(project)
            return PlaybackRuntime(project, timeline, backend)

        window = TimelineEditorWindow(
            material_provider=lambda _project: [descriptor],
            playback_runtime_factory=runtime_factory,
        )
        window.set_session(session)

        assert captured_projects[0].materials[0].last_known_path == str(
            relocated
        )
        assert session.project.materials[0].last_known_path == old_path
        assert captured_projects[0].materials[0].material_id == "material-1"
        assert session.timeline.clips[0].clip_id == original_clip_id
        window.shutdown()


def test_audio_device_loss_during_tick_can_continue_muted() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir), has_audio=True)
        backend = FakePlaybackBackend()
        clock = FakeClock()
        window = TimelineEditorWindow(
            playback_runtime_factory=lambda project, timeline: PlaybackRuntime(
                project,
                timeline,
                backend,
                clock_us=clock,
            ),
            audio_decision_provider=lambda: "mute",
        )
        window.set_session(session)
        window._btn_play.click()
        backend.next_render = BackendFrame(
            ok=False,
            video_status="ready",
            audio_status="unavailable",
            audio_unavailable=True,
            error_kind="audio_device_unavailable",
            error="output disappeared",
        )
        clock.advance(100_000)

        window._on_playback_tick()

        assert backend.muted
        assert window._btn_play.text() == "暂停"
        assert "无声" in window._preview_status.text()
        window.shutdown()


def test_fatal_playback_error_exposes_retry_and_diagnostics_actions() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        backend = FakePlaybackBackend()
        backend.next_prepare = BackendFrame(
            ok=False,
            fatal=True,
            error_kind="decoder_open_failed",
            error="decoder unavailable",
        )
        diagnostics_projects: list[str] = []
        window = TimelineEditorWindow(
            playback_runtime_factory=lambda project, timeline: PlaybackRuntime(
                project,
                timeline,
                backend,
            )
        )
        window.open_diagnostics_requested.connect(
            diagnostics_projects.append
        )
        window.set_session(session)

        window._btn_play.click()

        assert not window._btn_retry_playback.isHidden()
        assert window._btn_retry_playback.isEnabled()
        assert window._btn_open_diagnostics.isEnabled()
        window._btn_open_diagnostics.click()
        assert diagnostics_projects == ["project-1"]

        backend.next_prepare = BackendFrame()
        window._btn_retry_playback.click()

        assert window._btn_retry_playback.isHidden()
        assert window._btn_play.text() == "暂停"
        assert backend.calls.count("prepare") == 2
        window.shutdown()
