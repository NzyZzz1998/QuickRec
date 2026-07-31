from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PyQt5.QtGui import QColor, QMouseEvent, QPixmap  # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

from services.project_library import ProjectLibraryService  # noqa: E402
from services.project_materials import (  # noqa: E402
    PreviewState,
    ProjectMaterialDescriptor,
)
from services.timeline_session import TimelineSession  # noqa: E402
from ui.timeline_canvas import (  # noqa: E402
    TimelineCanvas,
    TimelineScale,
    snap_time_us,
)
from ui.timeline_editor_window import TimelineEditorWindow  # noqa: E402
from utils.project_store import ProjectFile, ProjectMaterialRef  # noqa: E402
from utils.timeline_model import (  # noqa: E402
    TIMELINE_EXTENSION_KEY,
    Timeline,
    TimelineClip,
    TimelineTrack,
)

APP = QApplication.instance() or QApplication([])


def _session(
    base: Path,
    *,
    material_count: int = 1,
    editing_fps: int = 30,
) -> TimelineSession:
    service = ProjectLibraryService(
        base / "projects.json",
        default_root=base / "projects",
    )
    assert service.create_project(
        name="中文 项目名称很长但不能挤压按钮",
        project_id="project-1",
        editing_fps=editing_fps,
    ).ok
    project = service.get_project("project-1").project
    assert project is not None
    for index in range(material_count):
        source = base / f"中文 素材 {index}.mp4"
        source.write_bytes(b"video")
        project.materials.append(
            ProjectMaterialRef(
                material_id=f"material-{index}",
                last_known_path=str(source),
                file_name=f"中文 素材 {index}.mp4",
                added_at="2026-07-28T10:00:00+08:00",
                metadata_snapshot={
                    "duration_sec": 3.0 + index,
                    "audio_source": "both",
                },
            )
        )
    assert service.commit_project_candidate("project-1", project).ok
    return TimelineSession(service, "project-1")


def test_timeline_scale_round_trip_and_pointer_center_zoom():
    scale = TimelineScale(
        pixels_per_second=100.0,
        origin_us=2_000_000,
        track_header_width=140,
    )

    x = scale.time_to_x(3_500_000)
    assert x == 290.0
    assert scale.x_to_time(x) == 3_500_000

    zoomed = scale.zoom_at(x, 2.0)
    assert zoomed.x_to_time(x) == 3_500_000
    assert zoomed.pixels_per_second == 200.0


def test_canvas_uses_project_fps_for_frame_level_ruler_ticks():
    canvas = TimelineCanvas()

    canvas.set_editing_fps(120)
    canvas.set_zoom(4.0)

    assert canvas.editing_fps == 120
    minor_frames, major_frames = canvas.ruler_tick_spec()
    assert minor_frames == 1
    assert major_frames >= 1
    assert major_frames % minor_frames == 0


def test_fit_timeline_shows_all_clips_for_thirty_minute_arrangement():
    track = TimelineTrack("video-1", "video", "视频 1", 0)
    clip = TimelineClip(
        "clip-1",
        "material-1",
        track.track_id,
        0,
        1_800_000_000,
        0,
        1_800_000_000,
    )
    canvas = TimelineCanvas()
    canvas.set_timeline(Timeline("timeline-1", [track], [clip]))
    viewport_width = 1_200

    zoom = canvas.fit_timeline(viewport_width)

    assert zoom < 0.25
    assert canvas.clip_rects()[clip.clip_id].right() <= viewport_width


def test_fit_level_zoom_label_keeps_a_nonzero_decimal_percentage():
    window = TimelineEditorWindow()

    window._on_canvas_zoom_changed(0.005, 0)

    assert window._zoom_label.text() == "0.5%"
    window.shutdown()


def test_editor_time_input_supports_120_fps_timecode_and_total_frames():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir), editing_fps=120)
        window = TimelineEditorWindow()
        window.set_session(session)

        assert window._timeline_canvas.editing_fps == 120
        assert window._editing_fps_label.text() == "120 FPS"
        required_width = (
            window._timecode_input.fontMetrics().horizontalAdvance(
                "88:88:88:888"
            )
            + 24
        )
        assert window._timecode_input.minimumWidth() >= required_width

        with (
            patch.object(window, "_timeline_end_us", return_value=2_000_000),
            patch.object(window, "_on_playhead_requested") as requested,
        ):
            window._timecode_input.setText("00:00:01:119")
            window._on_timecode_submitted()
            requested.assert_called_once_with(1_991_667)

            requested.reset_mock()
            window._toggle_time_input_mode()
            window._timecode_input.setText("120")
            window._on_timecode_submitted()
            requested.assert_called_once_with(1_000_000)

        window.shutdown()


def test_invalid_frame_time_input_keeps_original_playhead():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir), editing_fps=120)
        session.update_view_state(playhead_us=500_000)
        window = TimelineEditorWindow()
        window.set_session(session)

        with patch.object(window, "_on_playhead_requested") as requested:
            window._timecode_input.setText("00:00:00:120")
            window._on_timecode_submitted()

        requested.assert_not_called()
        assert "时间码" in window._save_status.text()
        assert window._timecode_input.text() == "00:00:00:060"
        window.shutdown()


def test_snap_uses_grid_playhead_and_clip_edges_or_can_be_disabled():
    candidates = [1_000_000, 2_500_000, 3_000_000]

    assert snap_time_us(
        2_480_000,
        candidates=candidates,
        grid_us=500_000,
        tolerance_us=40_000,
    ) == 2_500_000
    assert snap_time_us(
        2_480_000,
        candidates=candidates,
        grid_us=500_000,
        tolerance_us=40_000,
        enabled=False,
    ) == 2_480_000


def test_canvas_mouse_drag_emits_snapped_move_and_rejects_cross_type():
    video_track = TimelineTrack("video-1", "video", "视频 1", 0)
    audio_track = TimelineTrack("audio-1", "audio", "音频 1", 0)
    moving = TimelineClip(
        "clip-moving",
        "material-1",
        video_track.track_id,
        0,
        1_000_000,
        0,
        1_000_000,
    )
    anchor = TimelineClip(
        "clip-anchor",
        "material-2",
        video_track.track_id,
        2_000_000,
        1_000_000,
        0,
        1_000_000,
    )
    canvas = TimelineCanvas()
    canvas.resize(800, 240)
    canvas.set_timeline(
        Timeline(
            "timeline-1",
            [video_track, audio_track],
            [moving, anchor],
        )
    )
    canvas.show()
    APP.processEvents()
    moved: list[tuple[str, int, str]] = []
    rejected: list[str] = []
    canvas.clip_move_requested.connect(
        lambda clip_id, start_us, track_id: moved.append(
            (clip_id, start_us, track_id)
        )
    )
    canvas.invalid_drop.connect(rejected.append)

    source_center = canvas.clip_rects()[moving.clip_id].center()
    source = QPoint(round(source_center.x()), round(source_center.y()))
    snapped_target = QPoint(
        round(canvas.scale.time_to_x(3_530_000)),
        round(source.y()),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(source),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseMove,
            QPointF(snapped_target),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseButtonRelease,
            QPointF(snapped_target),
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        ),
    )

    assert moved == [(moving.clip_id, 3_000_000, video_track.track_id)]
    assert rejected == []

    moved.clear()
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(source),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseMove,
            QPointF(snapped_target),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.AltModifier,
        ),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseButtonRelease,
            QPointF(snapped_target),
            Qt.LeftButton,
            Qt.NoButton,
            Qt.AltModifier,
        ),
    )

    assert moved == [(moving.clip_id, 3_030_000, video_track.track_id)]
    assert rejected == []

    moved.clear()
    audio_target = QPoint(
        snapped_target.x(),
        round(
            canvas.ruler_height
            + canvas.track_height
            + canvas.track_height / 2
        ),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(source),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseMove,
            QPointF(audio_target),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseButtonRelease,
            QPointF(audio_target),
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        ),
    )

    assert moved == []
    assert rejected == ["视频片段和音频片段只能在同类轨道之间移动"]
    canvas.close()


def test_canvas_renders_sixteen_tracks_and_one_hundred_clips():
    tracks = [
        TimelineTrack(f"video-{index}", "video", f"视频 {index + 1}", index)
        for index in range(8)
    ] + [
        TimelineTrack(f"audio-{index}", "audio", f"音频 {index + 1}", index)
        for index in range(8)
    ]
    clips = [
        TimelineClip(
            f"clip-{index}",
            f"material-{index}",
            tracks[index % len(tracks)].track_id,
            (index // len(tracks)) * 2_000_000,
            1_000_000,
            0,
            1_000_000,
        )
        for index in range(100)
    ]
    canvas = TimelineCanvas()

    canvas.set_timeline(Timeline("timeline-1", tracks, clips))

    assert canvas.track_count == 16
    assert canvas.clip_count == 100
    assert len(canvas.clip_rects()) == 100
    assert canvas.minimumHeight() >= canvas.ruler_height + 16 * canvas.track_height


def test_editor_add_material_persists_timeline_and_updates_canvas():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        window = TimelineEditorWindow()
        window.set_session(session)
        window._material_list.setCurrentRow(0)

        window._btn_add_selected.click()

        assert len(session.timeline.clips) == 2
        assert window._timeline_canvas.clip_count == 2
        assert "自动保存" in window._save_status.text()
        assert window._btn_add_video_track.isEnabled()
        window.shutdown()


def test_repeated_track_reorder_keeps_the_moved_track_selected():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        assert session.commands.add_track("video").ok
        assert session.commands.add_track("video").ok
        video_tracks = sorted(
            (track for track in session.timeline.tracks if track.kind == "video"),
            key=lambda track: track.order,
        )
        moved_track_id = video_tracks[0].track_id
        window = TimelineEditorWindow()
        window.set_session(session)
        window._timeline_canvas.select_track(moved_track_id)
        window._sync_command_controls()

        window._btn_move_track_down.click()
        window._btn_move_track_down.click()

        reordered = sorted(
            (track for track in session.timeline.tracks if track.kind == "video"),
            key=lambda track: track.order,
        )
        assert reordered[-1].track_id == moved_track_id
        assert window._timeline_canvas.selected_track_id() == moved_track_id
        window.shutdown()


def test_save_failure_bar_retries_exact_command_and_restores_editing():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        window = TimelineEditorWindow()
        window.set_session(session)
        before_count = len(session.timeline.tracks)

        with patch(
            "services.project_library.save_project_index",
            side_effect=OSError("index write denied"),
        ):
            window._btn_add_video_track.click()

        assert not window._save_error_bar.isHidden()
        assert window._btn_retry_save.text() == "重试保存"
        assert window._btn_discard_change.text() == "放弃本次修改"
        assert not window._btn_retry_save.isHidden()
        assert not window._btn_error_diagnostics.isHidden()
        assert not window._btn_discard_change.isHidden()
        assert len(session.timeline.tracks) == before_count
        assert not window._btn_add_video_track.isEnabled()

        window._btn_retry_save.click()

        assert window._save_error_bar.isHidden()
        assert len(session.timeline.tracks) == before_count + 1
        assert window._btn_add_video_track.isEnabled()
        assert "自动保存" in window._save_status.text()
        window.shutdown()


def test_save_failure_bar_can_discard_candidate_without_changing_timeline():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        window = TimelineEditorWindow()
        window.set_session(session)
        before = session.timeline

        with patch(
            "services.project_library.save_project",
            side_effect=OSError("project write denied"),
        ):
            window._btn_add_audio_track.click()

        window._btn_discard_change.click()

        assert window._save_error_bar.isHidden()
        assert session.timeline == before
        assert window._btn_add_audio_track.isEnabled()
        assert "已放弃" in window._save_status.text()
        window.shutdown()


def test_external_conflict_bar_offers_reload_recovery_copy_and_cancel():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        session = _session(base)
        window = TimelineEditorWindow()
        window.set_session(session)
        changed = session.commands.project_service.rename_project(
            "project-1",
            "外部修改名称",
        )
        assert changed.ok

        window._btn_add_video_track.click()

        assert not window._save_error_bar.isHidden()
        assert not window._btn_reload_external.isHidden()
        assert not window._btn_save_recovery_copy.isHidden()
        assert not window._btn_cancel_conflict.isHidden()
        assert window._btn_retry_save.isHidden()

        window._btn_save_recovery_copy.click()

        assert window._save_error_bar.isHidden()
        assert session.project.name == "外部修改名称"
        assert "恢复副本" in window._save_status.text()
        recovery_files = list(
            (base / "projects" / "project-1").glob(
                "project.timeline-recovery-*.qrproj"
            )
        )
        assert len(recovery_files) == 1
        window.shutdown()


def test_corrupt_timeline_exposes_backup_and_empty_rebuild_actions():
    project = ProjectFile(
        "project-1",
        "损坏时间线项目",
        "",
        "2026-07-28T10:00:00+08:00",
        "2026-07-28T10:00:00+08:00",
    )
    session = SimpleNamespace(
        project_id="project-1",
        project=project,
        ready=False,
        read_only=True,
        status="corrupt",
        error="timeline payload is corrupt",
        commands=SimpleNamespace(timeline_backup_available=True),
    )
    window = TimelineEditorWindow()

    window.set_session(session)

    assert not window._btn_restore_timeline.isHidden()
    assert window._btn_restore_timeline.isEnabled()
    assert not window._btn_rebuild_timeline.isHidden()
    assert window._btn_rebuild_timeline.isEnabled()
    assert "恢复" in window._save_status.text()
    window.shutdown()


def test_corrupt_timeline_ui_rebuild_preserves_source_and_restores_editing():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        original = _session(base)
        assert original.commands.add_material(
            "material-0",
            has_audio=False,
        ).ok
        entry = original.commands.project_service.get_entry("project-1")
        assert entry is not None
        project_path = Path(entry.file_path)
        payload = json.loads(project_path.read_text(encoding="utf-8"))
        payload["extensions"][TIMELINE_EXTENSION_KEY] = {
            "schema_version": 1,
            "timeline_id": "timeline-corrupt",
            "tracks": [],
            "clips": [],
        }
        project_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        project_path.with_name(f"{project_path.name}.bak").unlink(
            missing_ok=True
        )
        session = TimelineSession(
            original.commands.project_service,
            "project-1",
        )
        window = TimelineEditorWindow()
        window.set_session(session)

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.Yes,
        ):
            window._btn_rebuild_timeline.click()

        assert session.ready
        assert session.timeline.clips == []
        assert len(session.project.materials) == 1
        assert window._btn_add_video_track.isEnabled()
        assert "空时间线已创建" in window._save_status.text()
        assert len(
            list(
                project_path.parent.glob(
                    "project.timeline-corrupt-*.qrproj"
                )
            )
        ) == 1
        window.shutdown()


def test_editor_material_provider_shows_thumbnail_metadata_and_missing_state():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        session = _session(base, material_count=2)
        thumbnail = base / "preview.png"
        image = QPixmap(160, 90)
        image.fill(QColor("#2463EB"))
        assert image.save(str(thumbnail), "PNG")
        descriptors = [
            ProjectMaterialDescriptor(
                project_id="project-1",
                material_id="material-0",
                file_name="中文 超长素材名称 0.mp4",
                file_path=str(base / "中文 素材 0.mp4"),
                file_exists=True,
                business_status="available",
                duration_sec=3.0,
                width=1920,
                height=1080,
                fps=60.0,
                mode="fullscreen",
                audio_source="both",
                file_size_bytes=1024,
                preview_path=thumbnail,
                preview_state=PreviewState.AVAILABLE,
            ),
            ProjectMaterialDescriptor(
                project_id="project-1",
                material_id="material-1",
                file_name="已移动素材.mp4",
                file_path=str(base / "missing.mp4"),
                file_exists=False,
                business_status="missing",
                duration_sec=4.0,
                width=1280,
                height=720,
                fps=30.0,
                mode="region",
                audio_source="none",
                file_size_bytes=None,
                preview_path=None,
                preview_state=PreviewState.MISSING,
            ),
        ]
        window = TimelineEditorWindow(
            material_provider=lambda _project: descriptors
        )

        window.set_session(session)

        available = window._material_list.item(0)
        missing = window._material_list.item(1)
        assert available is not None and missing is not None
        assert not available.icon().isNull()
        assert "1920×1080" in available.text()
        assert "60 FPS" in available.text()
        assert "文件缺失" in missing.text()
        window._material_list.setCurrentRow(1)
        assert not window._btn_add_selected.isEnabled()
        window.shutdown()


def test_editor_track_limit_and_read_only_state_disable_mutations():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        session = _session(base)
        for _ in range(7):
            assert session.commands.add_track("video").ok
        window = TimelineEditorWindow()

        window.set_session(session)

        assert not window._btn_add_video_track.isEnabled()
        assert window._btn_add_audio_track.isEnabled()
        window.shutdown()

        service = session.commands.project_service
        assert service.archive_project("project-1").ok
        archived = TimelineSession(service, "project-1")
        window = TimelineEditorWindow()
        window.set_session(archived)

        assert "归档" in window._save_status.text()
        assert not window._btn_add_video_track.isEnabled()
        assert not window._btn_add_selected.isEnabled()
        window.shutdown()


def test_recording_state_disables_timeline_mutations_and_restores_them():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        session = _session(base)
        added_track = session.commands.add_track("video")
        assert added_track.ok
        first_video_track = next(
            track
            for track in session.timeline.tracks
            if track.kind == "video" and track.order == 0
        )
        window = TimelineEditorWindow()
        window.set_session(session)
        window._timeline_canvas.select_track(first_video_track.track_id)
        window._sync_command_controls()

        assert window._btn_undo.isEnabled()
        assert window._btn_add_selected.isEnabled()
        assert window._btn_rename_track.isEnabled()
        assert window._btn_move_track_down.isEnabled()
        assert window._btn_delete_track.isEnabled()

        window.set_recording_active(True)

        assert session.recording_active
        assert session.read_only
        assert not window._btn_undo.isEnabled()
        assert not window._btn_redo.isEnabled()
        assert not window._btn_add_selected.isEnabled()
        assert not window._btn_add_video_track.isEnabled()
        assert not window._btn_add_audio_track.isEnabled()
        assert not window._btn_rename_track.isEnabled()
        assert not window._btn_move_track_up.isEnabled()
        assert not window._btn_move_track_down.isEnabled()
        assert not window._btn_delete_track.isEnabled()
        assert not window._btn_delete_clip.isEnabled()
        assert "只读" in window._save_status.text()

        window.set_recording_active(False)

        assert not session.recording_active
        assert not session.read_only
        assert window._save_status.text() == "已自动保存"
        assert window._btn_undo.isEnabled()
        assert window._btn_add_selected.isEnabled()
        assert window._btn_rename_track.isEnabled()
        assert window._btn_move_track_down.isEnabled()
        assert window._btn_delete_track.isEnabled()
        window.shutdown()


def test_canvas_material_drop_target_enforces_track_compatibility():
    timeline = Timeline(
        "timeline-1",
        [
            TimelineTrack("video-1", "video", "视频 1", 0),
            TimelineTrack("audio-1", "audio", "音频 1", 0),
        ],
    )
    canvas = TimelineCanvas()
    canvas.set_timeline(timeline)
    x = canvas.track_header_width + 100
    video_y = canvas.ruler_height + canvas.track_height // 2
    audio_y = (
        canvas.ruler_height
        + canvas.track_height
        + canvas.track_height // 2
    )

    video = canvas.material_drop_target(x, video_y, has_audio=False)
    audio_rejected = canvas.material_drop_target(
        x,
        audio_y,
        has_audio=False,
    )
    audio = canvas.material_drop_target(x, audio_y, has_audio=True)

    assert video[:2] == (1_000_000, "video-1")
    assert video[2]
    assert not audio_rejected[2]
    assert audio_rejected[3]
    assert audio[:2] == (1_000_000, "audio-1")
    assert audio[2]


def test_editor_splitter_defaults_near_68_32_and_modes_are_mutually_exclusive():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        window = TimelineEditorWindow()
        window.resize(1200, 760)
        window.set_session(session)
        window.show()
        APP.processEvents()

        sizes = window._main_splitter.sizes()
        ratio = sizes[0] / sum(sizes)
        assert 0.64 <= ratio <= 0.72

        window._btn_maximize_preview.click()
        assert not window._main_splitter.widget(1).isVisible()
        assert not session.view_state.timeline_focused
        assert session.view_state.preview_maximized

        window._btn_maximize_preview.click()
        window._btn_focus_timeline.click()
        assert not window._main_splitter.widget(0).isVisible()
        assert session.view_state.timeline_focused
        assert not session.view_state.preview_maximized
        window.shutdown()


def test_splitter_handle_keyboard_and_double_click_restore_default_ratio():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        window = TimelineEditorWindow()
        window.resize(1200, 760)
        window.set_session(session)
        window.show()
        APP.processEvents()
        handle = window._main_splitter.handle(1)

        window._main_splitter.setSizes([250, 500])
        handle.keyPressEvent(
            type(
                "_Key",
                (),
                {
                    "key": lambda self: Qt.Key_Home,
                    "accept": lambda self: None,
                },
            )()
        )
        home_sizes = window._main_splitter.sizes()
        assert home_sizes[1] >= 200

        handle.mouseDoubleClickEvent(
            type("_Mouse", (), {"accept": lambda self: None})()
        )
        APP.processEvents()
        restored = window._main_splitter.sizes()
        restored_ratio = restored[0] / sum(restored)
        assert 0.64 <= restored_ratio <= 0.72
        window.shutdown()
