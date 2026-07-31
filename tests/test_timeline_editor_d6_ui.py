from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtGui import QPixmap  # noqa: E402
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

from services.project_library import ProjectLibraryService  # noqa: E402
from services.timeline_session import TimelineSession  # noqa: E402
from ui.clip_inspector_widget import ClipInspectorWidget  # noqa: E402
from ui.timeline_edit_dialogs import (  # noqa: E402
    TimelineImpactDialog,
    TimelineRelinkDialog,
)
from ui.timeline_editor_window import TimelineEditorWindow  # noqa: E402
from utils.project_store import ProjectMaterialRef  # noqa: E402

APP = QApplication.instance() or QApplication([])


def _session(
    base: Path,
    *,
    has_audio: bool = False,
) -> tuple[TimelineSession, tuple[str, ...]]:
    service = ProjectLibraryService(
        base / "projects.json",
        default_root=base / "projects",
    )
    assert service.create_project(
        name="v1.9.5 D6 界面测试",
        project_id="project-1",
    ).ok
    project = service.get_project("project-1").project
    assert project is not None
    media = base / "中文 空格素材.mp4"
    media.write_bytes(b"video")
    project.materials.append(
        ProjectMaterialRef(
            material_id="material-1",
            last_known_path=str(media),
            file_name=media.name,
            added_at="2026-07-30T15:00:00+08:00",
            metadata_snapshot={
                "duration_sec": 10.0,
                "width": 1920,
                "height": 1080,
                "fps": 30.0,
                "audio_source": "both" if has_audio else "none",
            },
        )
    )
    assert service.commit_project_candidate("project-1", project).ok
    session = TimelineSession(service, "project-1")
    added = session.commands.add_material(
        "material-1",
        has_audio=has_audio,
    )
    assert added.ok
    return session, added.affected_clip_ids


def _select_clip(
    window: TimelineEditorWindow,
    clip_id: str,
) -> None:
    clip = next(
        item for item in window.session.timeline.clips
        if item.clip_id == clip_id
    )
    window._timeline_canvas.select_clip(clip.clip_id)
    window._on_clip_selected(clip.clip_id, clip.track_id)


def test_link_button_unlinks_and_strictly_relinks(tmp_path: Path) -> None:
    session, clip_ids = _session(tmp_path, has_audio=True)
    window = TimelineEditorWindow()
    window.set_session(session)
    _select_clip(window, clip_ids[0])

    assert window._btn_link_clip.isEnabled()
    assert window._btn_link_clip.text() == "解绑音视频"
    assert "Ctrl+L" in window._btn_link_clip.toolTip()
    assert window._load_selected_clip_in_inspector()
    assert "关联组" in window._clip_inspector._link_status.text()

    with patch.object(TimelineImpactDialog, "execute", return_value=True):
        window._btn_link_clip.click()

    assert {
        item.link_group_id
        for item in session.timeline.clips
    } == {None}
    assert window._btn_link_clip.text() == "重新关联"
    assert "未关联" in window._selection_summary.text()

    with patch.object(
        TimelineRelinkDialog,
        "choose",
        return_value=clip_ids[1],
    ):
        window._btn_link_clip.click()

    groups = {
        item.link_group_id
        for item in session.timeline.clips
    }
    assert len(groups) == 1
    assert None not in groups
    assert window._btn_link_clip.text() == "解绑音视频"
    window.shutdown()


def test_relink_without_candidate_keeps_timeline_and_explains_reason(
    tmp_path: Path,
) -> None:
    session, clip_ids = _session(tmp_path)
    window = TimelineEditorWindow()
    window.set_session(session)
    _select_clip(window, clip_ids[0])
    before = session.timeline

    assert window._btn_link_clip.text() == "重新关联"
    window._btn_link_clip.click()

    assert session.timeline == before
    assert "没有兼容" in window._save_status.text()
    window.shutdown()


def test_delete_and_ripple_delete_are_distinct_toolbar_actions(
    tmp_path: Path,
) -> None:
    session, first_ids = _session(tmp_path)
    second = session.commands.add_material(
        "material-1",
        has_audio=False,
        timeline_start_us=12_000_000,
    )
    assert second.ok
    second_id = second.affected_clip_ids[0]
    original_second_start = next(
        item.timeline_start_us
        for item in session.timeline.clips
        if item.clip_id == second_id
    )
    window = TimelineEditorWindow()
    window.set_session(session)
    _select_clip(window, first_ids[0])
    assert "空隙" in window._btn_delete_clip.toolTip()
    assert "Shift+Delete" in window._btn_ripple_delete.toolTip()

    with patch.object(TimelineImpactDialog, "execute", return_value=True):
        window._btn_delete_clip.click()

    assert next(
        item.timeline_start_us
        for item in session.timeline.clips
        if item.clip_id == second_id
    ) == original_second_start
    assert session.commands.undo().ok
    window._refresh_timeline()
    _select_clip(window, first_ids[0])

    with patch.object(TimelineImpactDialog, "execute", return_value=True):
        window._btn_ripple_delete.click()

    assert next(
        item.timeline_start_us
        for item in session.timeline.clips
        if item.clip_id == second_id
    ) == 2_000_000
    window.shutdown()


def test_canvas_drag_preview_commits_one_atomic_candidate(
    tmp_path: Path,
) -> None:
    session, _clip_ids = _session(tmp_path)
    window = TimelineEditorWindow()
    window.set_session(session)
    canvas = window._timeline_canvas
    first_track = next(
        item
        for item in session.timeline.tracks
        if item.kind == "video"
    )
    y = (
        canvas.ruler_height
        + canvas._ordered_tracks().index(first_track) * canvas.track_height
        + canvas.track_height // 2
    )
    x = canvas.scale.time_to_x(11_000_000)
    payload = {
        "material_id": "material-1",
        "has_video": True,
        "has_audio": False,
    }

    canvas.begin_material_drop(payload)
    candidate = canvas.preview_material_drop(
        payload,
        x=x,
        y=y,
        snap_enabled=True,
    )

    assert candidate is not None and candidate.valid
    assert "00:00:11:00" in canvas.material_drop_summary()
    assert "视频" in canvas.material_drop_summary()
    before = len(session.timeline.clips)
    assert canvas.commit_material_drop_preview()
    assert len(session.timeline.clips) == before + 1
    assert "拖入时间线" in window._save_status.text()
    window.shutdown()


def test_drag_preview_shows_linked_auto_track_and_conflict_feedback(
    tmp_path: Path,
) -> None:
    session, _clip_ids = _session(tmp_path, has_audio=True)
    window = TimelineEditorWindow()
    window.set_session(session)
    canvas = window._timeline_canvas
    video_track = next(
        item
        for item in session.timeline.tracks
        if item.kind == "video"
    )
    y = (
        canvas.ruler_height
        + canvas._ordered_tracks().index(video_track) * canvas.track_height
        + canvas.track_height // 2
    )
    x = canvas.scale.time_to_x(1_000_000)
    payload = {
        "material_id": "material-1",
        "has_video": True,
        "has_audio": True,
    }

    canvas.begin_material_drop(payload)
    candidate = canvas.preview_material_drop(
        payload,
        x=x,
        y=y,
        snap_enabled=True,
    )

    assert candidate is not None and candidate.valid
    assert candidate.auto_track_kinds == ("video", "audio")
    assert "自动新建视频轨" in canvas.material_drop_summary()
    assert "自动新建音频轨" in canvas.material_drop_summary()
    assert "关联音视频" in canvas.material_drop_summary()

    assert session.commands.set_track_locked(video_track.track_id, True).ok
    window._refresh_timeline()
    canvas.begin_material_drop(payload)
    locked = canvas.preview_material_drop(
        payload,
        x=x,
        y=y,
        snap_enabled=True,
    )
    assert locked is not None and not locked.valid
    assert "锁定" in canvas.material_drop_summary()
    assert not canvas.commit_material_drop_preview()
    window.shutdown()


def test_drag_candidate_renders_without_mutating_timeline(
    tmp_path: Path,
) -> None:
    session, _clip_ids = _session(tmp_path)
    window = TimelineEditorWindow()
    window.set_session(session)
    canvas = window._timeline_canvas
    canvas.resize(960, 320)
    payload = {
        "material_id": "material-1",
        "has_video": True,
        "has_audio": False,
    }
    canvas.begin_material_drop(payload)
    candidate = canvas.preview_material_drop(
        payload,
        x=canvas.scale.time_to_x(11_000_000),
        y=canvas.ruler_height + canvas.track_height // 2,
        snap_enabled=True,
    )
    before = session.timeline
    pixmap = QPixmap(canvas.size())
    canvas.render(pixmap)

    assert candidate is not None
    assert not pixmap.isNull()
    assert session.timeline == before
    canvas.cancel_material_drop()
    assert canvas.material_drop_candidate is None
    window.shutdown()


def test_d6_controls_are_accessible_and_chinese_text_is_readable(
    tmp_path: Path,
) -> None:
    session, clip_ids = _session(tmp_path, has_audio=True)
    window = TimelineEditorWindow()
    window.set_session(session)
    _select_clip(window, clip_ids[0])
    window.resize(960, 640)
    window.show()
    APP.processEvents()

    for button in (
        window._btn_delete_clip,
        window._btn_ripple_delete,
        window._btn_link_clip,
        window._btn_split_clip,
        window._btn_zoom_in,
        window._btn_zoom_out,
    ):
        assert button.toolTip()
        assert button.accessibleName()
        assert button.isVisible()
        assert button.geometry().right() <= window._timeline_panel.width()

    inspector = ClipInspectorWidget()
    texts = [
        child.text()
        for child in inspector.findChildren((QLabel, QPushButton))
        if hasattr(child, "text")
    ]
    assert any("片段属性" in text for text in texts)
    assert not any(
        marker in text
        for text in texts
        for marker in ("鍙", "鏃", "鐗", "缁", "寮", "彇", "鈥")
    )
    assert window.minimumWidth() == 960
    assert window.minimumHeight() == 640
    assert (
        window._btn_add_video_track.geometry().top()
        > window._btn_link_clip.geometry().top()
    )
    inspector.close()
    window.shutdown()
