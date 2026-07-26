from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication

from ui.window_selector import WindowSelector

APP = QApplication.instance() or QApplication([])


def test_window_selector_has_structured_layout_and_selection_state():
    windows = [
        (101, "演示窗口", False),
        (202, "素材窗口", True),
    ]
    with patch("ui.window_selector._enum_visible_windows", return_value=windows):
        selector = WindowSelector()

    assert selector.minimumWidth() == 480
    assert selector._list.count() == 2
    assert "2 个" in selector._summary.text()
    assert not selector._btn_select.isEnabled()
    assert not selector._btn_refresh.icon().isNull()
    assert not selector._btn_select.icon().isNull()

    selector._list.setCurrentRow(0)
    assert selector._btn_select.isEnabled()


def test_window_selector_cancel_signal_is_emitted_once():
    with patch("ui.window_selector._enum_visible_windows", return_value=[]):
        selector = WindowSelector()
    cancelled: list[bool] = []
    selector.cancelled.connect(lambda: cancelled.append(True))

    selector._cancel()
    selector.close()

    assert cancelled == [True]
