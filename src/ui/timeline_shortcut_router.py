"""Focus-aware semantic shortcut routing for the timeline editor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from PyQt5.QtCore import QEvent, QObject, Qt
from PyQt5.QtWidgets import QApplication, QWidget


class TimelineShortcutCommand(StrEnum):
    TOGGLE_PLAYBACK = "toggle_playback"
    PREVIOUS_FRAME = "previous_frame"
    NEXT_FRAME = "next_frame"
    PREVIOUS_SECOND = "previous_second"
    NEXT_SECOND = "next_second"
    SPLIT_CLIP = "split_clip"
    DELETE_CLIP = "delete_clip"
    RIPPLE_DELETE_CLIP = "ripple_delete_clip"
    TOGGLE_LINK = "toggle_link"
    UNDO = "undo"
    REDO = "redo"
    CANCEL_INTERACTION = "cancel_interaction"


@dataclass(frozen=True)
class ShortcutDispatchResult:
    executed: bool
    reason: str = ""


ShortcutDispatcher = Callable[
    [TimelineShortcutCommand],
    ShortcutDispatchResult,
]

_MODIFIER_MASK = (
    Qt.ShiftModifier
    | Qt.ControlModifier
    | Qt.AltModifier
    | Qt.MetaModifier
)
_SHORTCUTS = {
    (Qt.Key_Space, Qt.NoModifier): TimelineShortcutCommand.TOGGLE_PLAYBACK,
    (Qt.Key_Left, Qt.NoModifier): TimelineShortcutCommand.PREVIOUS_FRAME,
    (Qt.Key_Right, Qt.NoModifier): TimelineShortcutCommand.NEXT_FRAME,
    (
        Qt.Key_Left,
        Qt.ShiftModifier,
    ): TimelineShortcutCommand.PREVIOUS_SECOND,
    (
        Qt.Key_Right,
        Qt.ShiftModifier,
    ): TimelineShortcutCommand.NEXT_SECOND,
    (Qt.Key_B, Qt.ControlModifier): TimelineShortcutCommand.SPLIT_CLIP,
    (Qt.Key_Delete, Qt.NoModifier): TimelineShortcutCommand.DELETE_CLIP,
    (
        Qt.Key_Delete,
        Qt.ShiftModifier,
    ): TimelineShortcutCommand.RIPPLE_DELETE_CLIP,
    (Qt.Key_L, Qt.ControlModifier): TimelineShortcutCommand.TOGGLE_LINK,
    (Qt.Key_Z, Qt.ControlModifier): TimelineShortcutCommand.UNDO,
    (Qt.Key_Y, Qt.ControlModifier): TimelineShortcutCommand.REDO,
    (
        Qt.Key_Escape,
        Qt.NoModifier,
    ): TimelineShortcutCommand.CANCEL_INTERACTION,
}
_REPEATABLE_COMMANDS = {
    TimelineShortcutCommand.PREVIOUS_FRAME,
    TimelineShortcutCommand.NEXT_FRAME,
    TimelineShortcutCommand.PREVIOUS_SECOND,
    TimelineShortcutCommand.NEXT_SECOND,
}


class TimelineShortcutRouter(QObject):
    """Translate editor key events into semantic commands."""

    def __init__(
        self,
        window: QWidget,
        timeline_widget: QWidget,
        *,
        dispatch_command: ShortcutDispatcher,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._timeline_widget = timeline_widget
        self._dispatch_command = dispatch_command
        self._application = QApplication.instance()
        self._attached = False
        self._last_result: ShortcutDispatchResult | None = None
        if self._application is not None:
            self._application.installEventFilter(self)
            self._attached = True

    @property
    def last_result(self) -> ShortcutDispatchResult | None:
        return self._last_result

    def detach(self) -> None:
        if self._attached and self._application is not None:
            self._application.removeEventFilter(self)
        self._attached = False

    def eventFilter(self, watched: QObject | None, event: Any) -> bool:
        if event.type() != QEvent.KeyPress:
            return False
        command = shortcut_command(event.key(), event.modifiers())
        if command is None or not self._can_route():
            return False
        if event.isAutoRepeat() and command not in _REPEATABLE_COMMANDS:
            self._last_result = ShortcutDispatchResult(
                False,
                "该快捷键不支持按住重复触发",
            )
            event.accept()
            return True
        self._last_result = self._dispatch_command(command)
        event.accept()
        return True

    def _can_route(self) -> bool:
        application = self._application
        if application is None:
            return False
        if application.activeModalWidget() is not None:
            return False
        if application.activePopupWidget() is not None:
            return False
        focus = application.focusWidget()
        if focus is None:
            return application.activeWindow() is self._window
        if focus.window() is not self._window:
            return False
        return (
            focus is self._window
            or focus is self._timeline_widget
            or self._timeline_widget.isAncestorOf(focus)
        )


def shortcut_command(
    key: int,
    modifiers: Qt.KeyboardModifiers,
) -> TimelineShortcutCommand | None:
    normalized_modifiers = int(modifiers) & int(_MODIFIER_MASK)
    return _SHORTCUTS.get((int(key), normalized_modifiers))
