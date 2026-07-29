from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PyQt5.QtGui import QKeyEvent, QMouseEvent  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from services.project_library import ProjectLibraryService  # noqa: E402
from services.project_materials import (  # noqa: E402
    PreviewState,
    ProjectMaterialDescriptor,
)
from services.timeline_edit_service import (  # noqa: E402
    TimelineEditCandidate,
    TimelineEditConflict,
    TimelineEditImpact,
)
from services.timeline_session import TimelineSession  # noqa: E402
from ui.clip_inspector_widget import (  # noqa: E402
    ClipInspectorWidget,
    format_timecode_us,
    parse_timecode_us,
)
from ui.timeline_canvas import TimelineCanvas  # noqa: E402
from ui.timeline_edit_dialogs import TimelineImpactDialog  # noqa: E402
from ui.timeline_editor_window import TimelineEditorWindow  # noqa: E402
from ui.timeline_trim_interaction import TimelineTrimInteraction  # noqa: E402
from utils.project_store import ProjectMaterialRef  # noqa: E402
from utils.timeline_model import Timeline, TimelineClip, TimelineTrack  # noqa: E402

APP = QApplication.instance() or QApplication([])


def _clip(*, link_group_id: str | None = None) -> TimelineClip:
    return TimelineClip(
        "clip-video",
        "material-1",
        "video-1",
        2_000_000,
        4_000_000,
        1_000_000,
        4_000_000,
        link_group_id,
    )


def _valid_trim_candidate(clip: TimelineClip) -> TimelineEditCandidate:
    candidate_clip = TimelineClip(
        clip.clip_id,
        clip.material_id,
        clip.track_id,
        clip.timeline_start_us,
        3_000_000,
        2_000_000,
        3_000_000,
        clip.link_group_id,
    )
    return TimelineEditCandidate(
        "trim",
        True,
        "fingerprint",
        Timeline(
            "timeline-1",
            [TimelineTrack("video-1", "video", "视频 1", 0)],
            [candidate_clip],
        ),
        TimelineEditImpact(
            "trim",
            delta_us=-1_000_000,
            range_start_us=5_000_000,
            range_end_us=6_000_000,
            timeline_duration_before_us=6_000_000,
            timeline_duration_after_us=5_000_000,
            target_clip_ids=(clip.clip_id,),
            affected_track_ids=(clip.track_id,),
            affected_clip_ids=(clip.clip_id,),
        ),
        selected_clip_ids=(clip.clip_id,),
        normalized_source_start_us=2_000_000,
        normalized_source_end_us=5_000_000,
    )


def _session(base: Path) -> TimelineSession:
    service = ProjectLibraryService(
        base / "projects.json",
        default_root=base / "projects",
    )
    assert service.create_project(
        name="v1.9.3 UI 测试",
        project_id="project-1",
    ).ok
    project = service.get_project("project-1").project
    assert project is not None
    media = base / "中文 素材.mp4"
    media.write_bytes(b"video")
    project.materials.append(
        ProjectMaterialRef(
            material_id="material-1",
            last_known_path=str(media),
            file_name=media.name,
            added_at="2026-07-29T10:00:00+08:00",
            metadata_snapshot={
                "duration_sec": 10.0,
                "fps": 30.0,
                "audio_source": "none",
            },
        )
    )
    assert service.commit_project_candidate("project-1", project).ok
    session = TimelineSession(service, "project-1")
    assert session.commands.add_material("material-1", has_audio=False).ok
    return session


def test_timecode_parser_and_formatter_are_strict_and_round_trip():
    assert parse_timecode_us("01:02:03.456") == 3_723_456_000
    assert format_timecode_us(3_723_456_000) == "01:02:03.456"

    for invalid in ("1:02:03.456", "00:60:00.000", "00:00:60.000", "-1"):
        try:
            parse_timecode_us(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid timecode accepted: {invalid}")


def test_trim_interaction_calculates_edges_and_cancel_is_zero_effect():
    clip = _clip()
    interaction = TimelineTrimInteraction()

    interaction.begin(clip, edge="left")
    assert interaction.requested_source_range(3_000_000) == (
        2_000_000,
        5_000_000,
    )
    interaction.set_candidate(_valid_trim_candidate(clip))
    interaction.cancel()

    assert not interaction.active
    assert interaction.candidate is None
    assert clip.source_start_us == 1_000_000
    assert clip.source_duration_us == 4_000_000

    interaction.begin(clip, edge="right")
    assert interaction.requested_source_range(5_000_000) == (
        1_000_000,
        4_000_000,
    )


def test_clip_inspector_validates_timecode_and_exposes_candidate_impact():
    clip = _clip(link_group_id="link-1")
    inspector = ClipInspectorWidget()
    requested: list[tuple[int, int]] = []
    inspector.preview_requested.connect(
        lambda start, end: requested.append((start, end))
    )
    inspector.load_clip(
        clip,
        material_name="中文 素材.mp4",
        track_name="视频 1",
        material_duration_us=10_000_000,
        fps=30.0,
        linked_clip_count=2,
        editable=True,
    )

    inspector._source_in.setText("00:00:02.000")
    inspector._source_out.setText("00:00:05.000")

    assert requested[-1] == (2_000_000, 5_000_000)
    inspector.set_candidate(_valid_trim_candidate(clip))
    assert inspector._btn_apply.isEnabled()
    assert "减少" in inspector._impact_summary.text()
    assert "2" in inspector._link_status.text()

    inspector._source_out.setText("not-a-time")
    assert not inspector._btn_apply.isEnabled()
    assert "格式" in inspector._validation_message.text()
    inspector.close()


def test_clip_inspector_covers_invalid_cancel_apply_and_close_lifecycle():
    clip = _clip()
    inspector = ClipInspectorWidget()
    applied: list[TimelineEditCandidate] = []
    cancelled: list[bool] = []
    closed: list[bool] = []
    inspector.apply_requested.connect(applied.append)
    inspector.cancel_requested.connect(lambda: cancelled.append(True))
    inspector.closed_requested.connect(lambda: closed.append(True))
    inspector.load_clip(
        clip,
        material_name="素材.mp4",
        track_name="视频 1",
        material_duration_us=10_000_000,
        fps=None,
        linked_clip_count=1,
        editable=True,
    )

    inspector.set_candidate(None)
    assert "尚未" in inspector._impact_summary.text()

    invalid = TimelineEditCandidate(
        "trim",
        False,
        "fingerprint",
        None,
        TimelineEditImpact(
            "trim",
            delta_us=1_000_000,
            affected_track_ids=("video-1",),
            affected_clip_ids=(clip.clip_id,),
        ),
        conflicts=(
            TimelineEditConflict(
                "overlap",
                "候选与其他片段重叠",
                track_ids=("video-1",),
                clip_ids=(clip.clip_id,),
            ),
        ),
    )
    inspector.set_candidate(invalid)
    assert "增加" in inspector._impact_summary.text()
    assert "重叠" in inspector._validation_message.text()
    assert not inspector._btn_apply.isEnabled()

    valid = _valid_trim_candidate(clip)
    inspector.set_candidate(valid)
    inspector.set_editable(False)
    assert inspector._source_in.isReadOnly()
    assert not inspector._btn_apply.isEnabled()
    inspector.set_editable(True)
    inspector._btn_apply.click()
    assert applied == [valid]

    inspector._source_in.setText("00:00:05.000")
    inspector._source_out.setText("00:00:04.000")
    assert "必须大于" in inspector._validation_message.text()
    inspector._source_in.setText("00:00:01.000")
    inspector._source_out.setText("00:00:11.000")
    assert "不能超过" in inspector._validation_message.text()
    inspector._source_out.setText("00:00:05.000")
    assert "没有变化" in inspector._validation_message.text()

    inspector.keyPressEvent(None)
    inspector.keyPressEvent(
        QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    )
    assert cancelled == [True]
    assert "已取消" in inspector._validation_message.text()

    inspector.show()
    inspector._btn_close.click()
    assert cancelled == [True, True]
    assert closed == [True]
    assert not inspector.isVisible()
    inspector.close()


def test_impact_dialog_disables_confirm_and_can_locate_conflict():
    clip = _clip()
    conflict = TimelineEditConflict(
        "locked_ripple_track",
        "视频 2 已锁定",
        track_ids=("video-2",),
        clip_ids=("clip-2",),
    )
    candidate = TimelineEditCandidate(
        "trim",
        False,
        "fingerprint",
        None,
        TimelineEditImpact(
            "trim",
            range_start_us=5_000_000,
            range_end_us=6_000_000,
            timeline_duration_before_us=6_000_000,
            timeline_duration_after_us=5_000_000,
            target_clip_ids=(clip.clip_id,),
            affected_track_ids=("video-1", "video-2"),
            affected_clip_ids=(clip.clip_id, "clip-2"),
        ),
        conflicts=(conflict,),
    )
    dialog = TimelineImpactDialog(candidate)
    located: list[tuple[str, str]] = []
    dialog.locate_requested.connect(
        lambda track_id, clip_id: located.append((track_id, clip_id))
    )

    assert not dialog._btn_confirm.isEnabled()
    assert "视频 2 已锁定" in dialog._conflicts.text()
    dialog._btn_locate.click()

    assert located == [("video-2", "clip-2")]
    dialog.close()


def test_canvas_trim_handles_preview_cancel_and_track_lock_signal():
    clip = _clip()
    track = TimelineTrack("video-1", "video", "视频 1", 0)
    canvas = TimelineCanvas()
    canvas.resize(900, 240)
    canvas.set_timeline(Timeline("timeline-1", [track], [clip]))
    canvas.select_clip(clip.clip_id)
    canvas.show()
    APP.processEvents()
    handles = canvas.trim_handle_rects()[clip.clip_id]
    previews: list[tuple[str, int, int]] = []
    commits: list[TimelineEditCandidate] = []
    locks: list[tuple[str, bool]] = []
    canvas.clip_trim_preview_requested.connect(
        lambda clip_id, start, end: previews.append((clip_id, start, end))
    )
    canvas.clip_trim_commit_requested.connect(commits.append)
    canvas.track_lock_requested.connect(
        lambda track_id, locked: locks.append((track_id, locked))
    )

    left = handles[0].center()
    target = QPoint(
        round(canvas.scale.time_to_x(3_000_000)),
        round(left.y()),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseButtonPress,
            left,
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseMove,
            QPointF(target),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
    )
    assert previews[-1] == (clip.clip_id, 2_000_000, 5_000_000)
    canvas.set_trim_candidate(_valid_trim_candidate(clip))
    QApplication.sendEvent(
        canvas,
        QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier),
    )
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseButtonRelease,
            QPointF(target),
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        ),
    )
    assert commits == []
    assert not canvas.trim_active

    lock_rect = canvas.track_lock_rects()[track.track_id]
    QApplication.sendEvent(
        canvas,
        QMouseEvent(
            QEvent.MouseButtonPress,
            lock_rect.center(),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
    )
    assert locks == [(track.track_id, True)]
    canvas.close()


def test_editor_split_lock_and_ripple_delete_use_v193_commands():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        clip = session.timeline.clips[0]
        window = TimelineEditorWindow()
        window.set_session(session)
        window._timeline_canvas.select_clip(clip.clip_id)
        window._on_clip_selected(clip.clip_id, clip.track_id)
        window._on_playhead_requested(
            clip.timeline_start_us + 1_000_000
        )

        window._btn_split_clip.click()

        assert len(session.timeline.clips) == 2
        assert (
            window._timeline_canvas.selected_clip_id()
            in {
                item.clip_id
                for item in session.timeline.clips
                if item.timeline_start_us == clip.timeline_start_us + 1_000_000
            }
        )

        selected = window._timeline_canvas.selected_clip_id()
        assert selected is not None
        selected_clip = next(
            item
            for item in session.timeline.clips
            if item.clip_id == selected
        )
        assert window._selection_summary.text() == (
            f"已选 {selected_clip.clip_id} · 源 "
            f"00:01.000–00:10.000"
        )
        track_id = next(
            item.track_id
            for item in session.timeline.clips
            if item.clip_id == selected
        )
        window._on_track_lock_requested(track_id, True)
        assert next(
            item for item in session.timeline.tracks if item.track_id == track_id
        ).locked
        assert not window._btn_split_clip.isEnabled()

        window._on_track_lock_requested(track_id, False)
        before_materials = len(session.project.materials)
        before_files = {
            Path(item.last_known_path)
            for item in session.project.materials
        }
        with patch.object(
            TimelineImpactDialog,
            "execute",
            return_value=True,
        ):
            window._btn_delete_clip.click()

        assert len(session.project.materials) == before_materials
        assert all(path.exists() for path in before_files)
        assert len(session.timeline.clips) == 1
        assert window._timeline_canvas.selected_clip_id() is None
        assert window._selection_summary.text() == "未选择片段"
        window.shutdown()


def test_editor_d5_controls_fit_supported_window_sizes():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        window = TimelineEditorWindow()
        window.set_session(session)
        window.show()
        for size in ((960, 640), (1216, 760), (1600, 900)):
            window.resize(*size)
            APP.processEvents()
            assert window._btn_split_clip.isVisible()
            assert window._btn_clip_inspector.isVisible()
            assert window._ripple_mode_label.isVisible()
            assert window._timeline_scroll.viewport().width() > 0
            window._open_clip_inspector()
            APP.processEvents()
            assert (
                window._clip_inspector.geometry().bottom()
                <= window._timeline_panel.rect().bottom()
            )
        window.resize(960, 640)
        APP.processEvents()
        assert (
            window._clip_inspector._content_scroll.widget().minimumHeight()
            >= 330
        )
        assert (
            window._clip_inspector._content_scroll.verticalScrollBarPolicy()
            == Qt.ScrollBarAsNeeded
        )
        window.shutdown()


def test_delete_shortcut_does_not_delete_clip_while_editing_timecode():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        window = TimelineEditorWindow()
        window.set_session(session)
        clip = session.timeline.clips[0]
        window._timeline_canvas.select_clip(clip.clip_id)
        window._on_clip_selected(clip.clip_id, clip.track_id)
        assert window._load_selected_clip_in_inspector()
        window._clip_inspector.show()
        window.show()
        window._clip_inspector._source_in.setFocus()
        APP.processEvents()

        with patch.object(window, "_on_delete_clip") as delete_clip:
            window._on_delete_shortcut()
            delete_clip.assert_not_called()

            window._timeline_canvas.setFocus()
            APP.processEvents()
            window._on_delete_shortcut()
            delete_clip.assert_called_once_with()

        window.shutdown()


def test_cancel_without_active_preview_does_not_rebind_canvas_timeline():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        window = TimelineEditorWindow()
        window.set_session(session)

        with patch.object(window._timeline_canvas, "set_timeline") as set_timeline:
            window._cancel_edit_preview()

        set_timeline.assert_not_called()
        window.shutdown()


def test_missing_clip_disables_range_edit_but_keeps_inspection_and_delete():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        clip = session.timeline.clips[0]
        source = Path(session.project.materials[0].last_known_path)
        source.unlink()
        window = TimelineEditorWindow()
        window.set_session(session)
        window._timeline_canvas.select_clip(clip.clip_id)
        window._on_clip_selected(clip.clip_id, clip.track_id)

        assert window._timeline_canvas.clip_status(clip.clip_id) == "missing"
        assert window._timeline_canvas.trim_handle_rects() == {}
        assert not window._btn_split_clip.isEnabled()
        assert window._btn_clip_inspector.isEnabled()
        assert window._btn_delete_clip.isEnabled()
        assert window._load_selected_clip_in_inspector()
        assert not window._clip_inspector._btn_apply.isEnabled()
        assert "缺失" in window._save_status.text()

        window.shutdown()


def test_relinked_descriptor_restores_editing_without_changing_clip_identity():
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        session = _session(base)
        original = session.timeline.clips[0]
        Path(session.project.materials[0].last_known_path).unlink()
        replacement = base / "中文 新路径.mp4"
        replacement.write_bytes(b"video")
        descriptor = ProjectMaterialDescriptor(
            project_id="project-1",
            material_id="material-1",
            file_name=replacement.name,
            file_path=str(replacement),
            file_exists=True,
            business_status="available",
            duration_sec=10.0,
            width=1920,
            height=1080,
            fps=30.0,
            mode="fullscreen",
            audio_source="none",
            file_size_bytes=replacement.stat().st_size,
            preview_path=None,
            preview_state=PreviewState.NOT_GENERATED,
        )
        window = TimelineEditorWindow(
            material_provider=lambda _project: [descriptor],
        )
        window.set_session(session)
        window._timeline_canvas.select_clip(original.clip_id)
        window._on_clip_selected(original.clip_id, original.track_id)

        current = session.timeline.clips[0]
        assert window._timeline_canvas.clip_status(original.clip_id) == "available"
        assert window._timeline_canvas.trim_handle_rects()
        assert window._btn_clip_inspector.isEnabled()
        assert window._load_selected_clip_in_inspector()
        assert window._clip_inspector._source_in.isEnabled()
        assert current.clip_id == original.clip_id
        assert current.link_group_id == original.link_group_id
        assert current.source_start_us == original.source_start_us
        assert current.source_duration_us == original.source_duration_us

        window.shutdown()


def test_link_error_disables_group_edits_but_keeps_properties_visible():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        internal = session.commands._timeline
        assert internal is not None
        video = internal.clips[0]
        video.link_group_id = "broken-link"
        internal.clips.append(
            TimelineClip(
                "clip-audio",
                video.material_id,
                next(
                    track.track_id
                    for track in internal.tracks
                    if track.kind == "audio"
                ),
                video.timeline_start_us,
                video.timeline_duration_us,
                video.source_start_us + 1,
                video.source_duration_us,
                "broken-link",
            )
        )
        window = TimelineEditorWindow()
        window.set_session(session)
        window._timeline_canvas.select_clip(video.clip_id)
        window._on_clip_selected(video.clip_id, video.track_id)

        assert window._timeline_canvas.clip_status(video.clip_id) == "link_error"
        assert window._timeline_canvas.trim_handle_rects() == {}
        assert not window._btn_split_clip.isEnabled()
        assert not window._btn_delete_clip.isEnabled()
        assert window._btn_clip_inspector.isEnabled()
        assert "关联异常" in window._btn_split_clip.toolTip()

        window.shutdown()


def test_read_only_project_keeps_clip_properties_available():
    with tempfile.TemporaryDirectory() as temp_dir:
        session = _session(Path(temp_dir))
        session.commands._read_only = True
        clip = session.timeline.clips[0]
        window = TimelineEditorWindow()
        window.set_session(session)
        window._timeline_canvas.select_clip(clip.clip_id)
        window._on_clip_selected(clip.clip_id, clip.track_id)

        assert window._btn_clip_inspector.isEnabled()
        assert not window._btn_split_clip.isEnabled()
        assert not window._btn_delete_clip.isEnabled()
        assert "只读" in window._btn_delete_clip.toolTip()

        window.shutdown()
