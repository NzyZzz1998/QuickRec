from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtCore import QEvent, QPoint, Qt  # noqa: E402
from PyQt5.QtGui import QKeyEvent  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.playback_runtime import PlaybackState  # noqa: E402
from services.timeline_health import TimelineClipHealth  # noqa: E402
from ui.timeline_editor_window import TimelineEditorWindow  # noqa: E402
from ui.timeline_shortcut_router import (  # noqa: E402
    ShortcutDispatchResult,
    TimelineShortcutCommand,
    TimelineShortcutRouter,
)

APP = QApplication.instance() or QApplication([])


def _router(dispatch=None):
    window = QWidget()
    layout = QVBoxLayout(window)
    timeline = QWidget(window)
    timeline.setFocusPolicy(Qt.StrongFocus)
    line_edit = QLineEdit(window)
    button = QPushButton("原生按钮", window)
    item_list = QListWidget(window)
    layout.addWidget(timeline)
    layout.addWidget(line_edit)
    layout.addWidget(button)
    layout.addWidget(item_list)
    calls: list[TimelineShortcutCommand] = []

    def default_dispatch(command: TimelineShortcutCommand):
        calls.append(command)
        return ShortcutDispatchResult(True)

    router = TimelineShortcutRouter(
        window,
        timeline,
        dispatch_command=dispatch or default_dispatch,
    )
    window.show()
    APP.processEvents()
    return window, timeline, line_edit, button, item_list, router, calls


@pytest.mark.parametrize(
    ("key", "modifiers", "expected"),
    (
        (Qt.Key_Space, Qt.NoModifier, TimelineShortcutCommand.TOGGLE_PLAYBACK),
        (Qt.Key_Left, Qt.NoModifier, TimelineShortcutCommand.PREVIOUS_FRAME),
        (Qt.Key_Right, Qt.NoModifier, TimelineShortcutCommand.NEXT_FRAME),
        (
            Qt.Key_Left,
            Qt.ShiftModifier,
            TimelineShortcutCommand.PREVIOUS_SECOND,
        ),
        (
            Qt.Key_Right,
            Qt.ShiftModifier,
            TimelineShortcutCommand.NEXT_SECOND,
        ),
        (Qt.Key_B, Qt.ControlModifier, TimelineShortcutCommand.SPLIT_CLIP),
        (Qt.Key_Delete, Qt.NoModifier, TimelineShortcutCommand.DELETE_CLIP),
        (
            Qt.Key_Delete,
            Qt.ShiftModifier,
            TimelineShortcutCommand.RIPPLE_DELETE_CLIP,
        ),
        (Qt.Key_L, Qt.ControlModifier, TimelineShortcutCommand.TOGGLE_LINK),
        (Qt.Key_Z, Qt.ControlModifier, TimelineShortcutCommand.UNDO),
        (Qt.Key_Y, Qt.ControlModifier, TimelineShortcutCommand.REDO),
        (
            Qt.Key_Escape,
            Qt.NoModifier,
            TimelineShortcutCommand.CANCEL_INTERACTION,
        ),
    ),
)
def test_fixed_shortcut_mapping_dispatches_once(
    key: int,
    modifiers: Qt.KeyboardModifiers,
    expected: TimelineShortcutCommand,
) -> None:
    window, timeline, *_, router, calls = _router()
    timeline.setFocus()
    APP.processEvents()

    QTest.keyClick(timeline, key, modifiers)
    APP.processEvents()

    assert calls == [expected]
    router.detach()
    window.close()


def test_text_button_and_list_focus_keep_native_shortcuts() -> None:
    window, timeline, line_edit, button, item_list, router, calls = _router()
    del timeline
    button_calls: list[str] = []
    button.clicked.connect(lambda: button_calls.append("clicked"))

    line_edit.setText("文本")
    line_edit.setFocus()
    QTest.keyClick(line_edit, Qt.Key_Space)
    button.setFocus()
    QTest.keyClick(button, Qt.Key_Space)
    item_list.setFocus()
    QTest.keyClick(item_list, Qt.Key_Delete)
    APP.processEvents()

    assert line_edit.text() == "文本 "
    assert button_calls == ["clicked"]
    assert calls == []
    router.detach()
    window.close()


def test_menu_and_modal_dialog_block_editor_shortcuts() -> None:
    window, timeline, *_, router, calls = _router()
    timeline.setFocus()
    menu = QMenu(window)
    menu.addAction("测试")
    menu.show()
    menu.setFocus()
    APP.processEvents()
    QTest.keyClick(menu, Qt.Key_Space)
    menu.close()

    dialog = QDialog(window)
    dialog.setModal(True)
    dialog.show()
    dialog.setFocus()
    APP.processEvents()
    QTest.keyClick(dialog, Qt.Key_Delete)
    dialog.close()

    assert calls == []
    router.detach()
    window.close()


def test_window_focus_uses_window_level_shortcut_fallback() -> None:
    window, _timeline, *_, router, calls = _router()
    window.setFocus()
    APP.processEvents()

    QTest.keyClick(window, Qt.Key_Space)

    assert calls == [TimelineShortcutCommand.TOGGLE_PLAYBACK]
    router.detach()
    window.close()


def test_dispatch_result_preserves_disabled_reason() -> None:
    def disabled(_command: TimelineShortcutCommand):
        return ShortcutDispatchResult(False, "项目当前只读")

    window, timeline, *_, router, calls = _router(disabled)
    timeline.setFocus()
    APP.processEvents()

    QTest.keyClick(timeline, Qt.Key_B, Qt.ControlModifier)

    assert calls == []
    assert router.last_result == ShortcutDispatchResult(
        False,
        "项目当前只读",
    )
    router.detach()
    window.close()


def test_auto_repeat_is_only_allowed_for_navigation() -> None:
    window, timeline, *_, router, calls = _router()
    timeline.setFocus()
    APP.processEvents()

    QApplication.sendEvent(
        timeline,
        QKeyEvent(
            QEvent.KeyPress,
            Qt.Key_B,
            Qt.ControlModifier,
            "",
            True,
            2,
        ),
    )
    QApplication.sendEvent(
        timeline,
        QKeyEvent(
            QEvent.KeyPress,
            Qt.Key_Right,
            Qt.NoModifier,
            "",
            True,
            2,
        ),
    )

    assert calls == [TimelineShortcutCommand.NEXT_FRAME]
    router.detach()
    window.close()


def _editor_with_state(
    *,
    ready: bool = True,
    read_only: bool = False,
    recording: bool = False,
    pending_save: bool = False,
) -> TimelineEditorWindow:
    window = TimelineEditorWindow()
    window._session = SimpleNamespace(
        ready=ready,
        read_only=read_only,
        recording_active=recording,
        commands=SimpleNamespace(
            has_pending_save=pending_save,
            undo_depth=1,
            redo_depth=1,
        ),
    )
    window._writable = ready and not read_only and not recording
    return window


@pytest.mark.parametrize(
    ("state", "reason"),
    (
        ({"read_only": True}, "只读"),
        ({"recording": True}, "录制中"),
        ({"pending_save": True}, "尚未保存"),
        ({"ready": False}, "不可用"),
    ),
)
def test_structural_shortcuts_report_state_specific_disabled_reason(
    state: dict[str, bool],
    reason: str,
) -> None:
    window = _editor_with_state(**state)

    result = window._shortcut_command_availability(
        TimelineShortcutCommand.SPLIT_CLIP
    )

    assert not result.executed
    assert reason in result.reason
    window.shutdown()


def test_missing_material_blocks_split_but_keeps_safe_delete_available() -> None:
    window = _editor_with_state()
    window._clip_health = {
        "clip-1": TimelineClipHealth(
            "clip-1",
            "missing",
            "素材文件已移动或删除",
        )
    }

    with patch.object(
        window._timeline_canvas,
        "selected_clip_id",
        return_value="clip-1",
    ):
        split_result = window._shortcut_command_availability(
            TimelineShortcutCommand.SPLIT_CLIP
        )
        delete_result = window._shortcut_command_availability(
            TimelineShortcutCommand.DELETE_CLIP
        )

    assert not split_result.executed
    assert "素材文件已移动或删除" in split_result.reason
    assert delete_result.executed
    window.shutdown()


def test_shortcut_buttons_expose_formal_keys_and_accessible_names() -> None:
    window = TimelineEditorWindow()

    assert "Space" in window._btn_play.toolTip()
    assert window._btn_play.accessibleName()
    assert "Ctrl+B" in window._btn_split_clip.toolTip()
    assert window._btn_split_clip.accessibleName()
    assert "Delete" in window._btn_delete_clip.toolTip()
    assert "保留空隙" in window._btn_delete_clip.toolTip()
    assert window._btn_delete_clip.accessibleName()
    assert "Ctrl+Z" in window._btn_undo.toolTip()
    assert "Ctrl+Y" in window._btn_redo.toolTip()
    window.shutdown()


def test_buttons_and_clip_menu_use_the_same_semantic_dispatcher() -> None:
    window = TimelineEditorWindow()
    calls: list[TimelineShortcutCommand] = []

    def dispatch(command: TimelineShortcutCommand) -> ShortcutDispatchResult:
        calls.append(command)
        return ShortcutDispatchResult(True)

    window._dispatch_shortcut_command = dispatch
    for button in (
        window._btn_play,
        window._btn_undo,
        window._btn_redo,
        window._btn_split_clip,
        window._btn_delete_clip,
    ):
        button.setEnabled(True)
        button.click()

    def trigger_semantic_actions(menu: QMenu, _position: QPoint) -> None:
        for action in menu.actions():
            if action.text().startswith(
                ("在播放头处分割", "删除片段并保留空隙", "全局波纹删除")
            ):
                action.trigger()

    with patch(
        "ui.timeline_editor_window.QMenu.exec_",
        new=trigger_semantic_actions,
    ):
        window._on_clip_context_requested("clip-1", QPoint())

    assert calls == [
        TimelineShortcutCommand.TOGGLE_PLAYBACK,
        TimelineShortcutCommand.UNDO,
        TimelineShortcutCommand.REDO,
        TimelineShortcutCommand.SPLIT_CLIP,
        TimelineShortcutCommand.DELETE_CLIP,
        TimelineShortcutCommand.SPLIT_CLIP,
        TimelineShortcutCommand.DELETE_CLIP,
        TimelineShortcutCommand.RIPPLE_DELETE_CLIP,
    ]
    window.shutdown()


def test_frame_navigation_uses_project_fps_and_pauses_active_playback() -> None:
    window = TimelineEditorWindow()
    paused_snapshot = SimpleNamespace(state=PlaybackState.PAUSED)
    runtime = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(state=PlaybackState.PLAYING),
        pause=lambda: paused_snapshot,
        release=lambda: None,
    )
    window._session = SimpleNamespace(
        editing_fps=120,
        view_state=SimpleNamespace(playhead_us=0),
    )
    window._playback_runtime = runtime

    with (
        patch.object(window, "_timeline_end_us", return_value=1_000_000),
        patch.object(window, "_on_playhead_requested") as requested,
        patch.object(window, "_render_playback_snapshot") as render,
    ):
        window._navigate_playhead_frames(1)

    requested.assert_called_once_with(8_333)
    render.assert_called_once_with(paused_snapshot)
    window.shutdown()


def test_second_navigation_dispatches_one_project_second() -> None:
    window = TimelineEditorWindow()
    window._session = SimpleNamespace(editing_fps=120)

    with (
        patch.object(
            window,
            "_shortcut_command_availability",
            return_value=ShortcutDispatchResult(True),
        ),
        patch.object(window, "_navigate_playhead_frames") as navigate,
    ):
        window._dispatch_shortcut_command(
            TimelineShortcutCommand.NEXT_SECOND
        )

    navigate.assert_called_once_with(120)
    window.shutdown()


def test_empty_timeline_keeps_frame_navigation_available() -> None:
    window = _editor_with_state()

    with patch.object(window, "_timeline_end_us", return_value=0):
        result = window._shortcut_command_availability(
            TimelineShortcutCommand.NEXT_FRAME
        )

    assert result.executed
    window.shutdown()
