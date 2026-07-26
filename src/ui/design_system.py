"""QuickRec Full v1.8 视觉令牌、样式和轻量线性图标。"""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QPushButton, QWidget

COLORS = {
    "sidebar": "#171C25",
    "sidebar_hover": "#242C38",
    "sidebar_active": "#293649",
    "background": "#F7F9FC",
    "panel": "#FFFFFF",
    "subtle": "#F1F4F8",
    "text": "#172033",
    "secondary": "#526077",
    "muted": "#7B8799",
    "border": "#D8DEE8",
    "border_strong": "#C2CAD7",
    "blue": "#2563EB",
    "blue_hover": "#1D4ED8",
    "blue_soft": "#E8F0FF",
    "green": "#168653",
    "green_soft": "#E6F5ED",
    "amber": "#A66309",
    "amber_soft": "#FFF3D6",
    "red": "#C73A35",
    "red_soft": "#FDECEA",
}

ICON_NAMES = (
    "record",
    "library",
    "settings",
    "diagnostics",
    "monitor",
    "region",
    "window",
    "folder",
    "file",
    "copy",
    "save",
    "refresh",
    "play",
    "pause",
    "stop",
    "close",
    "check",
    "trash",
    "link",
    "search",
    "more",
)


def _line(painter: QPainter, x1: float, y1: float, x2: float, y2: float) -> None:
    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _draw_icon(name: str, painter: QPainter) -> None:
    if name == "record":
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawEllipse(QRectF(9, 9, 6, 6))
    elif name == "library":
        for x, y in ((4, 4), (13, 4), (4, 13), (13, 13)):
            painter.drawRoundedRect(QRectF(x, y, 7, 7), 1, 1)
    elif name == "settings":
        for y, knob_x in ((6, 9), (12, 15), (18, 7)):
            _line(painter, 4, y, 20, y)
            painter.drawEllipse(QRectF(knob_x - 2, y - 2, 4, 4))
    elif name == "diagnostics":
        painter.drawRoundedRect(QRectF(3, 4, 18, 16), 2, 2)
        path = QPainterPath(QPointF(5, 13))
        path.lineTo(8, 13)
        path.lineTo(10, 8)
        path.lineTo(13, 16)
        path.lineTo(15, 11)
        path.lineTo(19, 11)
        painter.drawPath(path)
    elif name == "monitor":
        painter.drawRoundedRect(QRectF(3, 4, 18, 13), 2, 2)
        _line(painter, 9, 21, 15, 21)
        _line(painter, 12, 17, 12, 21)
    elif name == "region":
        _line(painter, 4, 9, 4, 4)
        _line(painter, 4, 4, 9, 4)
        _line(painter, 15, 4, 20, 4)
        _line(painter, 20, 4, 20, 9)
        _line(painter, 20, 15, 20, 20)
        _line(painter, 20, 20, 15, 20)
        _line(painter, 9, 20, 4, 20)
        _line(painter, 4, 20, 4, 15)
        painter.drawRect(QRectF(8, 8, 8, 8))
    elif name == "window":
        painter.drawRoundedRect(QRectF(3, 5, 18, 15), 2, 2)
        _line(painter, 3, 9, 21, 9)
        painter.drawEllipse(QRectF(6, 6.2, 1.3, 1.3))
        painter.drawEllipse(QRectF(9, 6.2, 1.3, 1.3))
    elif name == "folder":
        path = QPainterPath(QPointF(3, 7))
        path.lineTo(9, 7)
        path.lineTo(11, 9)
        path.lineTo(21, 9)
        path.lineTo(19, 19)
        path.lineTo(3, 19)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "file":
        path = QPainterPath(QPointF(6, 3))
        path.lineTo(14, 3)
        path.lineTo(19, 8)
        path.lineTo(19, 21)
        path.lineTo(6, 21)
        path.closeSubpath()
        painter.drawPath(path)
        _line(painter, 14, 3, 14, 8)
        _line(painter, 14, 8, 19, 8)
    elif name == "copy":
        painter.drawRoundedRect(QRectF(8, 8, 12, 12), 2, 2)
        painter.drawRoundedRect(QRectF(4, 4, 12, 12), 2, 2)
    elif name == "save":
        painter.drawRoundedRect(QRectF(4, 3, 16, 18), 2, 2)
        painter.drawRect(QRectF(7, 3, 9, 6))
        painter.drawRoundedRect(QRectF(7, 14, 10, 7), 1, 1)
    elif name == "refresh":
        painter.drawArc(QRectF(4, 4, 16, 16), 35 * 16, 250 * 16)
        _line(painter, 18, 4, 20, 9)
        _line(painter, 18, 4, 13, 5)
    elif name == "play":
        path = QPainterPath(QPointF(8, 5))
        path.lineTo(19, 12)
        path.lineTo(8, 19)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "pause":
        painter.drawRoundedRect(QRectF(6, 5, 4, 14), 1, 1)
        painter.drawRoundedRect(QRectF(14, 5, 4, 14), 1, 1)
    elif name == "stop":
        painter.drawRoundedRect(QRectF(6, 6, 12, 12), 1, 1)
    elif name == "close":
        _line(painter, 6, 6, 18, 18)
        _line(painter, 18, 6, 6, 18)
    elif name == "check":
        path = QPainterPath(QPointF(4, 12))
        path.lineTo(9, 17)
        path.lineTo(20, 6)
        painter.drawPath(path)
    elif name == "trash":
        painter.drawRoundedRect(QRectF(6, 7, 12, 14), 1, 1)
        _line(painter, 4, 7, 20, 7)
        _line(painter, 9, 4, 15, 4)
        _line(painter, 10, 11, 10, 17)
        _line(painter, 14, 11, 14, 17)
    elif name == "link":
        painter.drawArc(QRectF(3, 8, 11, 8), 35 * 16, 290 * 16)
        painter.drawArc(QRectF(10, 8, 11, 8), 215 * 16, 290 * 16)
        _line(painter, 9, 12, 15, 12)
    elif name == "search":
        painter.drawEllipse(QRectF(4, 4, 12, 12))
        _line(painter, 14.5, 14.5, 20, 20)
    elif name == "more":
        for x in (6, 12, 18):
            painter.drawEllipse(QRectF(x - 1, 11, 2, 2))
    else:
        raise ValueError(f"Unknown QuickRec icon: {name}")


def quickrec_icon(name: str, color: str = "#526077", size: int = 18) -> QIcon:
    """生成不依赖 QtSvg 的确定性线性图标。"""
    if name not in ICON_NAMES:
        raise ValueError(f"Unknown QuickRec icon: {name}")
    logical_size = max(12, int(size))
    pixmap = QPixmap(logical_size, logical_size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    scale = logical_size / 24
    painter.scale(scale, scale)
    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    _draw_icon(name, painter)
    painter.end()
    return QIcon(pixmap)


def set_button_icon(
    button: QPushButton,
    name: str,
    *,
    color: str = "#526077",
    size: int = 18,
) -> None:
    button.setIcon(quickrec_icon(name, color, size))
    button.setIconSize(QSize(size, size))


def refresh_style(widget: QWidget) -> None:
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


WORKBENCH_STYLESHEET = """
QMainWindow#quickrecWorkbench,
QMainWindow#quickrecWorkbench QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI";
}
QMainWindow#quickrecWorkbench {
    background: #F7F9FC;
}
QFrame#workbenchSidebar {
    background: #171C25;
    border: 0;
}
QLabel#workbenchBrand {
    color: #FFFFFF;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 16px;
    font-weight: 700;
}
QLabel#workbenchBrandSubtitle {
    color: #9EABBC;
    font-size: 11px;
}
QPushButton[role="nav"] {
    min-height: 42px;
    padding: 0 12px;
    border: 0;
    border-radius: 6px;
    color: #DCE3ED;
    background: transparent;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}
QPushButton[role="nav"]:hover {
    background: #242C38;
}
QPushButton[role="nav"]:checked {
    color: #FFFFFF;
    background: #293649;
    border-left: 3px solid #6C97FF;
}
QStackedWidget#workbenchPages {
    background: #F7F9FC;
    border: 0;
}
QScrollArea#settingsScrollArea {
    border: 0;
    background: transparent;
}
QScrollArea#settingsScrollArea > QWidget > QWidget {
    background: transparent;
}
QLabel#pageTitle {
    color: #172033;
    font-size: 21px;
    font-weight: 700;
}
QLabel#pageSubtitle {
    color: #526077;
    font-size: 12px;
}
QLabel[role="sectionTitle"] {
    color: #172033;
    font-size: 14px;
    font-weight: 700;
}
QLabel[role="secondary"] {
    color: #526077;
}
QLabel[role="status"][state="available"] {
    color: #168653;
    font-weight: 600;
}
QLabel[role="status"][state="pending"] {
    color: #A66309;
    font-weight: 600;
}
QLabel[role="status"][state="missing"],
QLabel[role="status"][state="error"] {
    color: #C73A35;
    font-weight: 600;
}
QFrame[role="panel"], QFrame#recordingSummary, QFrame#recordingState,
QFrame#recordingResult {
    background: #FFFFFF;
    border: 1px solid #D8DEE8;
    border-radius: 6px;
}
QFrame#recordingState[state="idle"] {
    background: #E8F0FF;
    border-left: 3px solid #2563EB;
}
QFrame#recordingState[state="recording"] {
    background: #FDECEA;
    border-left: 3px solid #C73A35;
}
QFrame#recordingState[state="paused"] {
    background: #FFF3D6;
    border-left: 3px solid #A66309;
}
QFrame#recordingResult {
    background: #E6F5ED;
    border-left: 3px solid #168653;
}
QFrame#recordingResult[state="warning"] {
    background: #FFF3D6;
    border-left: 3px solid #A66309;
}
QFrame#recordingResult[state="error"] {
    background: #FDECEA;
    border-left: 3px solid #C73A35;
}
QPushButton {
    min-height: 32px;
    padding: 0 12px;
    border: 1px solid #C2CAD7;
    border-radius: 4px;
    color: #172033;
    background: #FFFFFF;
    font-size: 12px;
}
QPushButton:hover {
    border-color: #8EA4C6;
    background: #F1F4F8;
}
QPushButton:pressed {
    background: #E8EDF5;
}
QPushButton:disabled {
    color: #9AA5B5;
    border-color: #D8DEE8;
    background: #F1F4F8;
}
QPushButton[role="primary"] {
    color: #FFFFFF;
    border-color: #2563EB;
    background: #2563EB;
    font-weight: 600;
}
QPushButton[role="primary"]:hover {
    border-color: #1D4ED8;
    background: #1D4ED8;
}
QPushButton[role="danger"] {
    color: #C73A35;
    border-color: #E6AAA6;
    background: #FFFFFF;
}
QPushButton[role="danger"]:hover {
    background: #FDECEA;
}
QPushButton[role="mode"] {
    min-height: 112px;
    padding: 14px;
    text-align: left;
    background: #FFFFFF;
}
QFrame[role="modeCard"] {
    background: #FFFFFF;
    border: 1px solid #D8DEE8;
    border-radius: 6px;
}
QFrame[role="modeCard"]:hover {
    border-color: #8FB0F6;
}
QLabel[role="iconBadge"] {
    border: 1px solid #D6E3FF;
    border-radius: 5px;
    background: #E8F0FF;
}
QPushButton[role="mode"]:hover {
    border-color: #6C97FF;
    background: #F8FAFF;
}
QLineEdit, QComboBox {
    min-height: 32px;
    padding: 0 9px;
    border: 1px solid #C2CAD7;
    border-radius: 4px;
    color: #172033;
    background: #FFFFFF;
    selection-background-color: #2563EB;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #2563EB;
}
QCheckBox {
    spacing: 7px;
    color: #172033;
}
QTableWidget, QListWidget {
    border: 1px solid #D8DEE8;
    border-radius: 4px;
    color: #172033;
    background: #FFFFFF;
    alternate-background-color: #F7F9FC;
    gridline-color: #E7EBF1;
    selection-color: #172033;
    selection-background-color: #E8F0FF;
}
QHeaderView::section {
    min-height: 32px;
    padding: 0 8px;
    border: 0;
    border-bottom: 1px solid #D8DEE8;
    color: #526077;
    background: #F1F4F8;
    font-weight: 600;
}
QScrollBar:vertical {
    width: 10px;
    margin: 2px;
    border: 0;
    background: transparent;
}
QScrollBar::handle:vertical {
    min-height: 32px;
    border-radius: 4px;
    background: #C2CAD7;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QToolTip {
    padding: 5px 7px;
    border: 1px solid #59677B;
    color: #FFFFFF;
    background: #202733;
}
"""


FLOATING_STYLESHEET = """
QWidget#recordingToolbar,
QWidget#recordingToolbar QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI";
}
QWidget#recordingToolbar {
    background: #171C25;
    border: 1px solid #364253;
    border-radius: 7px;
}
QWidget#recordingToolbar QLabel {
    color: #F7F9FC;
    background: transparent;
    border: 0;
}
QWidget#recordingToolbar QPushButton {
    min-height: 30px;
    padding: 0 11px;
    border: 1px solid #536075;
    border-radius: 4px;
    color: #E6EBF2;
    background: #232C39;
}
QWidget#recordingToolbar QPushButton:hover {
    border-color: #8190A7;
    background: #303B4A;
}
QWidget#recordingToolbar QPushButton[role="danger"] {
    color: #FFB6B2;
    border-color: #8B4544;
    background: #39282B;
}
QWidget#recordingToolbar QLabel#recordingIndicator[state="recording"] {
    border-radius: 5px;
    background: #D94A45;
}
QWidget#recordingToolbar QLabel#recordingIndicator[state="paused"] {
    border-radius: 5px;
    background: #D68A00;
}
QWidget#recordingToolbar QLabel#recordingIndicator[state="saving"] {
    border-radius: 5px;
    background: #2563EB;
}
QWidget#recordingToolbar QLabel#recordingIndicator[state="saved"] {
    border-radius: 5px;
    background: #168653;
}
"""


SELECTOR_STYLESHEET = """
QDialog#windowSelector,
QDialog#windowSelector QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI";
}
QDialog#windowSelector {
    color: #172033;
    background: #F7F9FC;
}
QDialog#windowSelector QLabel#selectorTitle {
    color: #172033;
    font-size: 17px;
    font-weight: 700;
}
QDialog#windowSelector QLabel#selectorSubtitle {
    color: #526077;
    font-size: 11px;
}
QDialog#windowSelector QListWidget {
    padding: 4px;
    border: 1px solid #D8DEE8;
    border-radius: 5px;
    color: #172033;
    background: #FFFFFF;
    outline: 0;
}
QDialog#windowSelector QListWidget::item {
    min-height: 46px;
    padding: 0 10px;
    border-radius: 4px;
}
QDialog#windowSelector QListWidget::item:hover {
    background: #F1F4F8;
}
QDialog#windowSelector QListWidget::item:selected {
    color: #172033;
    background: #E8F0FF;
    border: 1px solid #8FB0F6;
}
QDialog#windowSelector QPushButton {
    min-height: 32px;
    padding: 0 12px;
    border: 1px solid #C2CAD7;
    border-radius: 4px;
    color: #172033;
    background: #FFFFFF;
}
QDialog#windowSelector QPushButton:hover {
    border-color: #8EA4C6;
    background: #F1F4F8;
}
QDialog#windowSelector QPushButton[role="primary"] {
    color: #FFFFFF;
    border-color: #2563EB;
    background: #2563EB;
    font-weight: 600;
}
QDialog#windowSelector QPushButton:disabled {
    color: #9AA5B5;
    background: #F1F4F8;
}
"""
