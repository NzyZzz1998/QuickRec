from __future__ import annotations

import threading
from collections.abc import Callable

from PyQt5.QtCore import QObject, QPointF, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from services.capture_capability import SelfTestResult
from services.capture_capability_runtime import CaptureCapabilityRuntime

_STAGE_LABELS = {
    "prepare": "正在准备捕获与编码环境",
    "capture": "正在执行 1080p120 录制检测",
    "probe": "正在验证临时视频",
    "complete": "检测完成",
}

class _SelfTestBridge(QObject):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(object)


class _SemanticProgressBar(QProgressBar):
    """使用矢量终态符号，避免打包环境缺少符号字体。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._terminal_state: str | None = None
        self.setTextVisible(False)
        self.setStyleSheet(
            """
            QProgressBar {
                min-height: 18px;
                border: 1px solid #C2CAD7;
                border-radius: 4px;
                background: #F1F4F8;
                color: #172033;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 3px;
                background: #2563EB;
            }
            QProgressBar[state="passed"]::chunk { background: #168653; }
            QProgressBar[state="failed"]::chunk { background: #C73A35; }
            QProgressBar[state="cancelled"]::chunk { background: #7B8799; }
            """
        )

    @property
    def terminal_state(self) -> str | None:
        return self._terminal_state

    def set_terminal_state(self, state: str | None) -> None:
        self._terminal_state = state
        self.setProperty("state", state or "running")
        if state is not None:
            self.setValue(100)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self._terminal_state is None:
            self._paint_percentage(painter)
            painter.end()
            return

        center = self.rect().center()
        pen = QPen(QColor("#FFFFFF"), 2.2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        if self._terminal_state == "passed":
            painter.drawLine(
                QPointF(center.x() - 6, center.y()),
                QPointF(center.x() - 2, center.y() + 4),
            )
            painter.drawLine(
                QPointF(center.x() - 2, center.y() + 4),
                QPointF(center.x() + 7, center.y() - 5),
            )
        elif self._terminal_state == "failed":
            painter.drawLine(
                QPointF(center.x() - 5, center.y() - 5),
                QPointF(center.x() + 5, center.y() + 5),
            )
            painter.drawLine(
                QPointF(center.x() + 5, center.y() - 5),
                QPointF(center.x() - 5, center.y() + 5),
            )
        else:
            painter.drawLine(
                QPointF(center.x() - 6, center.y()),
                QPointF(center.x() + 6, center.y()),
            )
        painter.end()

    def _paint_percentage(self, painter: QPainter) -> None:
        minimum = self.minimum()
        maximum = self.maximum()
        ratio = (
            0.0
            if maximum <= minimum
            else (self.value() - minimum) / (maximum - minimum)
        )
        ratio = min(1.0, max(0.0, ratio))
        filled_width = round(self.rect().width() * ratio)
        text = f"{round(ratio * 100)}%"
        font = QFont("Segoe UI", 9)
        font.setWeight(QFont.Normal)
        painter.setFont(font)

        filled = QRect(self.rect())
        filled.setWidth(filled_width)
        painter.save()
        painter.setClipRect(filled)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(self.rect(), Qt.AlignCenter, text)
        painter.restore()

        remaining = QRect(self.rect())
        remaining.setLeft(self.rect().left() + filled_width)
        painter.save()
        painter.setClipRect(remaining)
        painter.setPen(QColor("#172033"))
        painter.drawText(self.rect(), Qt.AlignCenter, text)
        painter.restore()


class CaptureSelfTestDialog(QDialog):
    def __init__(
        self,
        runtime: CaptureCapabilityRuntime,
        parent=None,
        open_diagnostics: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self._open_diagnostics = open_diagnostics
        self._test_result: SelfTestResult | None = None
        self._cancel_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._bridge = _SelfTestBridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.finished.connect(self._on_finished)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("120 FPS 能力检测")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        title = QLabel("检测当前设备能否稳定完成 1080p120 录制")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        self._status = QLabel(
            "检测约需 5 秒，将在当前保存目录生成临时视频，完成后自动删除。"
        )
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._progress = _SemanticProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)
        actions = QHBoxLayout()
        actions.addStretch()
        self._diagnostics = QPushButton("查看诊断")
        self._diagnostics.clicked.connect(self._show_diagnostics)
        self._diagnostics.hide()
        actions.addWidget(self._diagnostics)
        self._cancel = QPushButton("取消")
        self._cancel.clicked.connect(self._cancel_or_close)
        actions.addWidget(self._cancel)
        self._start = QPushButton("开始检测")
        self._start.setProperty("role", "primary")
        self._start.clicked.connect(self._start_test)
        actions.addWidget(self._start)
        layout.addLayout(actions)

    def _start_test(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._test_result = None
        self._cancel_event.clear()
        self._start.setEnabled(False)
        self._cancel.setText("取消检测")
        self._status.setText(_STAGE_LABELS["prepare"])
        self._progress.setValue(0)
        self._progress.set_terminal_state(None)
        self._worker = threading.Thread(target=self._run_test, daemon=True)
        self._worker.start()

    def _run_test(self) -> None:
        result = self.runtime.run(
            self._cancel_event,
            progress=lambda stage, percent: self._bridge.progress.emit(
                stage,
                percent,
            ),
        )
        self._bridge.finished.emit(result)

    def _on_progress(self, stage: str, percent: int) -> None:
        self._status.setText(_STAGE_LABELS.get(stage, stage))
        self._progress.set_terminal_state(None)
        self._progress.setValue(percent)

    def _on_finished(self, result: SelfTestResult) -> None:
        self._test_result = result
        self._cancel.setEnabled(True)
        self._cancel.setText("关闭")
        self._start.setEnabled(True)
        if result.passed:
            self._diagnostics.hide()
            self._progress.set_terminal_state("passed")
            self._status.setText(
                f"检测通过：平均 {result.average_fps:.1f} FPS，"
                f"最低每秒 {result.minimum_one_second_fps} FPS。"
            )
            self._start.setText("使用 120 FPS")
            self._start.clicked.disconnect()
            self._start.clicked.connect(self.accept)
            return
        if result.status == "cancelled":
            self._progress.set_terminal_state("cancelled")
            self._status.setText("检测已取消，当前 FPS 设置未改变。")
        else:
            self._progress.set_terminal_state("failed")
            reason = result.failure_reason or "当前设备未通过稳定性门禁"
            self._status.setText(f"检测未通过：{reason}")
            self._diagnostics.setVisible(self._open_diagnostics is not None)
        self._start.setText("重新检测")

    def _show_diagnostics(self) -> None:
        if self._open_diagnostics is not None:
            self._open_diagnostics()
        self.reject()

    def _cancel_or_close(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            self._cancel_event.set()
            self._cancel.setEnabled(False)
            self._status.setText("正在取消并清理临时文件…")
            return
        self.reject()

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.is_alive():
            self._cancel_event.set()
            event.ignore()
            return
        super().closeEvent(event)

    @classmethod
    def execute(
        cls,
        runtime: CaptureCapabilityRuntime,
        parent=None,
        open_diagnostics: Callable[[], None] | None = None,
    ) -> SelfTestResult | None:
        dialog = cls(runtime, parent, open_diagnostics=open_diagnostics)
        dialog.exec_()
        return (
            dialog._test_result
            if dialog._test_result and dialog._test_result.passed
            else None
        )
