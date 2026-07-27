"""QuickRec Full 单实例工作台窗口与路由协调器。"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from typing import Any

from PyQt5.QtCore import QRect, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.design_system import (
    COLORS,
    WORKBENCH_STYLESHEET,
    quickrec_icon,
    set_button_icon,
)


class WorkbenchPage(StrEnum):
    RECORDING = "recording"
    MATERIALS = "materials"
    PROJECTS = "projects"
    SETTINGS = "settings"
    DIAGNOSTICS = "diagnostics"


PAGE_LABELS = {
    WorkbenchPage.RECORDING: "录制",
    WorkbenchPage.MATERIALS: "素材库",
    WorkbenchPage.PROJECTS: "项目",
    WorkbenchPage.SETTINGS: "设置",
    WorkbenchPage.DIAGNOSTICS: "诊断",
}
PAGE_ICONS = {
    WorkbenchPage.RECORDING: "record",
    WorkbenchPage.MATERIALS: "library",
    WorkbenchPage.PROJECTS: "folder",
    WorkbenchPage.SETTINGS: "settings",
    WorkbenchPage.DIAGNOSTICS: "diagnostics",
}


def clamp_workbench_geometry(
    saved: Mapping[str, Any] | None,
    available_rects: Sequence[QRect],
    *,
    minimum_size: tuple[int, int] = (960, 640),
) -> dict[str, int | bool]:
    """把保存的窗口几何夹取到当前任一可见工作区。"""
    minimum_width, minimum_height = minimum_size
    values = saved or {}
    width = max(minimum_width, int(values.get("width", 1200)))
    height = max(minimum_height, int(values.get("height", 760)))
    x = int(values.get("x", 80))
    y = int(values.get("y", 80))

    rects = [QRect(rect) for rect in available_rects if rect.isValid()]
    if not rects:
        return {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "maximized": bool(values.get("maximized", False)),
        }

    requested = QRect(x, y, width, height)
    target = max(
        rects,
        key=lambda rect: rect.intersected(requested).width()
        * rect.intersected(requested).height(),
    )
    width = min(width, target.width())
    height = min(height, target.height())
    x = min(max(x, target.left()), target.right() - width + 1)
    y = min(max(y, target.top()), target.bottom() - height + 1)
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "maximized": bool(values.get("maximized", False)),
    }


class WorkbenchWindow(QMainWindow):
    """统一承接录制、素材库、设置和诊断的工作台壳。"""

    page_changed = pyqtSignal(object)
    geometry_changed = pyqtSignal(object)

    def __init__(
        self,
        *,
        pages: Mapping[WorkbenchPage, QWidget] | None = None,
        saved_geometry: Mapping[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("quickrecWorkbench")
        self.setWindowTitle("QuickRec Full")
        self.setWindowIcon(quickrec_icon("record", COLORS["blue"], 24))
        self.setMinimumSize(960, 640)
        self.resize(1200, 760)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        supplied_pages = dict(pages or {})
        self.page_widgets: dict[WorkbenchPage, QWidget] = {
            page: supplied_pages.get(page) or self._placeholder_page(page)
            for page in WorkbenchPage
        }
        self._page_indexes: dict[WorkbenchPage, int] = {}
        self._nav_buttons: dict[WorkbenchPage, QPushButton] = {}
        self._current_page = WorkbenchPage.RECORDING
        self._init_ui()
        self.setStyleSheet(WORKBENCH_STYLESHEET)
        if saved_geometry:
            self.restore_saved_geometry(saved_geometry)
        self.set_current_page(WorkbenchPage.RECORDING)

    @property
    def current_page(self) -> WorkbenchPage:
        return self._current_page

    def _init_ui(self) -> None:
        central = QWidget(self)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("workbenchSidebar")
        sidebar.setFixedWidth(184)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(9)
        brand_mark = QLabel()
        brand_mark.setPixmap(
            quickrec_icon("record", "#79A2FF", 28).pixmap(28, 28)
        )
        brand_mark.setFixedSize(30, 30)
        brand_row.addWidget(brand_mark)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand = QLabel("QuickRec")
        brand.setObjectName("workbenchBrand")
        brand_text.addWidget(brand)
        subtitle = QLabel("Full 创作者工作台")
        subtitle.setObjectName("workbenchBrandSubtitle")
        brand_text.addWidget(subtitle)
        brand_row.addLayout(brand_text, 1)
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addSpacing(24)

        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)
        for page in WorkbenchPage:
            button = QPushButton(PAGE_LABELS[page])
            button.setObjectName(f"nav_{page.value}")
            button.setAccessibleName(f"打开{PAGE_LABELS[page]}页")
            button.setToolTip(f"切换到{PAGE_LABELS[page]}页")
            button.setProperty("role", "nav")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            set_button_icon(button, PAGE_ICONS[page], color="#CAD4E2", size=18)
            button.clicked.connect(
                lambda _checked=False, target=page: self._navigate_to(target)
            )
            nav_group.addButton(button)
            sidebar_layout.addWidget(button)
            self._nav_buttons[page] = button
        sidebar_layout.addStretch()

        self._sidebar_status = QLabel("空闲\n托盘持续运行")
        self._sidebar_status.setObjectName("workbenchBrandSubtitle")
        self._sidebar_status.setToolTip("关闭工作台不会退出 QuickRec")
        sidebar_layout.addWidget(self._sidebar_status)

        self._stack = QStackedWidget()
        self._stack.setObjectName("workbenchPages")
        for page in WorkbenchPage:
            self._page_indexes[page] = self._stack.addWidget(self.page_widgets[page])

        root.addWidget(sidebar)
        root.addWidget(self._stack, 1)
        self.setCentralWidget(central)

    def _navigate_to(self, page: WorkbenchPage) -> None:
        self.set_current_page(page)

    def set_runtime_status(self, state: str) -> None:
        labels = {
            "idle": "空闲\n托盘持续运行",
            "selecting": "正在选择录制范围\n请在浮动窗口中操作",
            "starting": "正在准备录制\n请稍候",
            "countdown": "录制倒计时\n即将开始",
            "recording": "录制中\n控制请使用浮动工具栏",
            "paused": "录制已暂停\n控制请使用浮动工具栏",
            "saving": "正在保存\n请勿退出 QuickRec",
        }
        self._sidebar_status.setText(labels.get(state, labels["idle"]))

    @staticmethod
    def _placeholder_page(page: WorkbenchPage) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        title = QLabel(PAGE_LABELS[page])
        title.setObjectName(f"pageTitle_{page.value}")
        layout.addWidget(title)
        layout.addStretch()
        return widget

    def set_current_page(self, page: WorkbenchPage | str) -> bool:
        target = page if isinstance(page, WorkbenchPage) else WorkbenchPage(page)
        if target != self._current_page and not self._confirm_current_page():
            self._nav_buttons[self._current_page].setChecked(True)
            return False
        self._stack.setCurrentIndex(self._page_indexes[target])
        self._nav_buttons[target].setChecked(True)
        changed = target != self._current_page
        self._current_page = target
        if changed:
            self.page_changed.emit(target)
        return True

    def _confirm_current_page(self) -> bool:
        page = self.page_widgets[self._current_page]
        confirm = getattr(page, "confirm_navigation", None)
        return bool(confirm()) if callable(confirm) else True

    def restore_saved_geometry(self, saved: Mapping[str, Any] | None) -> None:
        app = QApplication.instance()
        screens = app.screens() if app is not None else []
        rects = [screen.availableGeometry() for screen in screens]
        geometry = clamp_workbench_geometry(saved, rects)
        self.setGeometry(
            int(geometry["x"]),
            int(geometry["y"]),
            int(geometry["width"]),
            int(geometry["height"]),
        )
        if bool(geometry["maximized"]):
            self.showMaximized()

    def geometry_snapshot(self) -> dict[str, int | bool]:
        rect = self.normalGeometry() if self.isMaximized() else self.geometry()
        return {
            "x": rect.x(),
            "y": rect.y(),
            "width": rect.width(),
            "height": rect.height(),
            "maximized": self.isMaximized(),
        }

    def closeEvent(self, event) -> None:
        if not self._confirm_current_page():
            event.ignore()
            return
        self.geometry_changed.emit(self.geometry_snapshot())
        self.hide()
        event.ignore()


class WorkbenchCoordinator:
    """维护工作台全局单实例和同进程页面记忆。"""

    def __init__(self, window_factory: Callable[[], Any]) -> None:
        self._window_factory = window_factory
        self._window: Any = None
        self._last_page = WorkbenchPage.RECORDING

    @property
    def window(self) -> Any:
        return self._window

    def open(self, page: WorkbenchPage | str | None = None) -> Any:
        target = (
            self._window.current_page
            if page is None and self._window is not None
            else self._last_page
            if page is None
            else page
            if isinstance(page, WorkbenchPage)
            else WorkbenchPage(page)
        )
        if self._window is None:
            self._window = self._window_factory()
        changed = self._window.set_current_page(target)
        self._last_page = target if changed is not False else self._window.current_page
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()
        return self._window

    def hide(self) -> None:
        if self._window is not None:
            self._last_page = self._window.current_page
            self._window.hide()
