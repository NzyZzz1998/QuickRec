from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication, QMessageBox

from ui.qt_localization import install_qt_zh_cn

APP = QApplication.instance() or QApplication([])


def test_qt_standard_message_box_buttons_use_chinese_labels():
    translator = install_qt_zh_cn(APP)
    assert translator is not None
    box = QMessageBox()
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

    yes_text = box.button(QMessageBox.Yes).text()
    no_text = box.button(QMessageBox.No).text()

    assert yes_text.startswith("是")
    assert no_text.startswith("否")
    APP.removeTranslator(translator)
