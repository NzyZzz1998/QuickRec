from __future__ import annotations

import argparse
import ctypes
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QKeyEvent, QPainter
from PyQt5.QtWidgets import QApplication, QWidget


class CaptureStimulus(QWidget):
    def __init__(self, ready_file: Path) -> None:
        super().__init__()
        self._ready_file = ready_file
        self._frame_index = 0
        self._window_width = 320
        self._window_height = 180
        self._screen_x = 0
        self._screen_y = 0
        self._travel_width = 1
        self._travel_height = 1
        self._movement_target_hz = 240
        self._movement_count = 0
        self._stop_event = threading.Event()
        self._movement_thread: threading.Thread | None = None
        self.setWindowTitle("QuickRec 120 FPS Capture Stimulus")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setFixedSize(self._window_width, self._window_height)

    def start(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            geometry = screen.availableGeometry()
            self._screen_x = geometry.x()
            self._screen_y = geometry.y()
            self._travel_width = max(geometry.width() - self.width(), 1)
            self._travel_height = max(geometry.height() - self.height(), 1)
            self.move(self._screen_x, self._screen_y)
        self.show()
        self._movement_thread = threading.Thread(
            target=self._movement_loop,
            name="QuickRecCaptureStimulus",
            daemon=True,
        )
        self._movement_thread.start()
        QTimer.singleShot(250, self._mark_ready)

    def _mark_ready(self) -> None:
        self._ready_file.parent.mkdir(parents=True, exist_ok=True)
        self._ready_file.write_text(
            json.dumps(
                {
                    "ready": True,
                    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "movement_target_hz": self._movement_target_hz,
                    "window_size": [self.width(), self.height()],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _movement_loop(self) -> None:
        user32 = ctypes.windll.user32
        winmm = ctypes.windll.winmm
        hwnd = int(self.winId())
        interval = 1.0 / self._movement_target_hz
        next_tick = time.perf_counter()
        winmm.timeBeginPeriod(1)
        try:
            while not self._stop_event.is_set():
                self._frame_index += 1
                user32.SetWindowPos(
                    hwnd,
                    -1,
                    self._screen_x + (self._frame_index * 5) % self._travel_width,
                    self._screen_y + (self._frame_index * 3) % self._travel_height,
                    0,
                    0,
                    0x0001 | 0x0010 | 0x0040,
                )
                self._movement_count += 1
                next_tick += interval
                remaining = next_tick - time.perf_counter()
                if remaining > 0.001:
                    time.sleep(remaining - 0.0005)
                while time.perf_counter() < next_tick:
                    pass
        finally:
            winmm.timeEndPeriod(1)

    def stop(self) -> None:
        self._stop_event.set()
        if self._movement_thread is not None:
            self._movement_thread.join(timeout=1.0)
            self._movement_thread = None

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        width = max(self.width(), 1)
        height = max(self.height(), 1)
        painter.fillRect(self.rect(), QColor("#101820"))
        painter.fillRect(0, 0, 20, height, QColor("#F0F6FC"))
        painter.fillRect(0, height // 2, width, 12, QColor("#1F6FEB"))
        painter.fillRect(width - 72, height // 3, 64, 64, QColor("#2EA043"))
        painter.end()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is not None and event.key() == Qt.Key_Escape:
            QApplication.quit()
            return
        super().keyPressEvent(event)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dynamic desktop stimulus for 120 FPS capture.")
    parser.add_argument("--ready-file", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    app = QApplication(sys.argv[:1])
    stimulus = CaptureStimulus(Path(args.ready_file).resolve())
    app.aboutToQuit.connect(stimulus.stop)
    stimulus.start()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
