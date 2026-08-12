from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotkey.hotkey_manager import HotkeyManager


def test_replace_bindings_commits_complete_valid_set() -> None:
    manager = HotkeyManager()

    def callback() -> None:
        pass

    assert manager.replace_bindings(
        [
            ("Ctrl+Alt+R", callback),
            ("Ctrl+Alt+S", callback),
            ("Ctrl+Alt+P", callback),
        ]
    )
    assert set(manager._registered) == {
        "ctrl+alt+r",
        "ctrl+alt+s",
        "ctrl+alt+p",
    }


def test_replace_bindings_rejects_conflict_without_losing_previous_set() -> None:
    manager = HotkeyManager()

    def first() -> None:
        pass

    def second() -> None:
        pass
    assert manager.replace_bindings([("Ctrl+Alt+R", first)])
    before = manager._registered.copy()

    assert not manager.replace_bindings(
        [("Ctrl+Alt+S", first), ("ctrl+alt+s", second)]
    )
    assert manager._registered == before


def test_replace_bindings_rejects_invalid_shortcut_without_side_effect() -> None:
    manager = HotkeyManager()

    def callback() -> None:
        pass
    assert manager.replace_bindings([("Ctrl+Alt+R", callback)])
    before = manager._registered.copy()

    assert not manager.replace_bindings([("R", callback)])
    assert manager._registered == before
