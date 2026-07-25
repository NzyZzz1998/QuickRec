from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication

from ui.design_system import ICON_NAMES, WORKBENCH_STYLESHEET, quickrec_icon

APP = QApplication.instance() or QApplication([])


def test_all_product_icons_render_nonblank_pixels():
    for name in ICON_NAMES:
        image = quickrec_icon(name, "#2563EB", 24).pixmap(24, 24).toImage()
        nontransparent = sum(
            image.pixelColor(x, y).alpha() > 0
            for y in range(image.height())
            for x in range(image.width())
        )
        assert nontransparent > 4, name


def test_workbench_stylesheet_contains_confirmed_visual_tokens():
    for token in (
        "#171C25",
        "#F7F9FC",
        "#2563EB",
        "#168653",
        "#A66309",
        "#C73A35",
    ):
        assert token in WORKBENCH_STYLESHEET

    assert "QPushButton[role=\"nav\"]" in WORKBENCH_STYLESHEET
    assert "QPushButton[role=\"primary\"]" in WORKBENCH_STYLESHEET
    assert "QPushButton[role=\"danger\"]" in WORKBENCH_STYLESHEET
