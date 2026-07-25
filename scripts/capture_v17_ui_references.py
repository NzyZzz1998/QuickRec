"""生成 v1.8 原型所需的 v1.7 当前界面参考截图。"""

# ruff: noqa: E402

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QMenu

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import ConfigManager
from services.pending_recordings import PendingRecordingService
from services.recording_library import RecordingLibraryService
from ui.area_selector import AreaSelector
from ui.material_library_dialog import MaterialLibraryDialog
from ui.settings_dialog import SettingsDialog
from ui.toolbar import RecordingToolbar
from ui.window_selector import WindowSelector
from utils.pending_recording_store import PendingRecordingItem, save_pending

OUTPUT_DIR = ROOT / "doc" / "releases" / "v1.8" / "prototype" / "reference"


def _capture(
    widget,
    name: str,
    app: QApplication,
    *,
    controlled_background: QPixmap | None = None,
) -> None:
    widget.show()
    app.processEvents()
    widget.raise_()
    app.processEvents()
    if controlled_background is None:
        screen = widget.screen() or app.primaryScreen()
        pixmap = screen.grabWindow(int(widget.winId())) if screen else widget.grab()
        if pixmap.isNull():
            pixmap = widget.grab()
    else:
        pixmap = controlled_background.copy()
        painter = QPainter(pixmap)
        painter.drawPixmap(0, 0, widget.grab())
        painter.end()
    path = OUTPUT_DIR / f"{name}.png"
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"截图保存失败：{path}")
    widget.close()
    app.processEvents()


def _config(path: Path) -> ConfigManager:
    config = ConfigManager.__new__(ConfigManager)
    config.config_path = path
    config._config = ConfigManager.defaults.copy()
    config._config.update(
        {
            "save_path": r"E:\Videos\QuickRec",
            "quality": "high",
            "fps": 60,
            "audio_source": "both",
            "show_countdown": True,
            "countdown_seconds": 3,
        }
    )
    return config


def _capture_settings(app: QApplication, root: Path) -> None:
    dialog = SettingsDialog(_config(root / "config.json"))
    _capture(dialog, "settings-current", app)


def _capture_library(app: QApplication, root: Path) -> None:
    service = RecordingLibraryService(root / "recordings.json")
    samples = [
        ("QuickRec_20260723_214512.mp4", "fullscreen", "both", 52.4, 1920, 1080, 60.0),
        ("中文 演示_20260723_210804.mp4", "region", "none", 18.7, 1280, 720, 30.0),
        ("窗口问题复现_20260722_225210.mp4", "window", "system", 41.2, 1600, 900, 60.0),
    ]
    for index, (name, mode, audio, duration, width, height, fps) in enumerate(samples):
        path = root / name
        path.write_bytes(b"QuickRec reference")
        service.add_recording(
            path,
            item_id=f"reference-{index}",
            diagnostic_dir=str(root / "QuickRecDiagnostics"),
            metadata={
                "mode": mode,
                "audio_source": audio,
                "duration_sec": duration,
                "width": width,
                "height": height,
                "fps": fps,
            },
        )
    dialog = MaterialLibraryDialog(service)
    dialog._table.selectRow(0)
    dialog._update_detail()
    _capture(dialog, "material-library-current", app)

    empty = MaterialLibraryDialog(RecordingLibraryService(root / "empty-recordings.json"))
    _capture(empty, "material-library-empty-current", app)

    missing_service = RecordingLibraryService(root / "missing-recordings.json")
    missing_path = root / "已移动 示例.mp4"
    missing_path.write_bytes(b"QuickRec reference")
    missing_service.add_recording(
        missing_path,
        item_id="reference-missing",
        diagnostic_dir=str(root / "QuickRecDiagnostics"),
        metadata={
            "mode": "fullscreen",
            "audio_source": "none",
            "duration_sec": 12.0,
            "width": 1920,
            "height": 1080,
            "fps": 60.0,
        },
    )
    missing_path.unlink()
    missing = MaterialLibraryDialog(missing_service)
    missing._table.selectRow(0)
    missing._update_detail()
    _capture(missing, "material-library-missing-current", app)

    pending_video = root / "待入库 示例.mp4"
    pending_video.write_bytes(b"QuickRec pending reference")
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    pending_item = PendingRecordingItem(
        pending_id="reference-pending",
        material_id="reference-pending-material",
        file_path=str(pending_video),
        file_name=pending_video.name,
        created_at=now,
        queued_at=now,
        updated_at=now,
        status="retry_failed",
        attempt_count=2,
        capture_mode="fullscreen",
        audio_source="both",
        last_attempt_at=now,
        last_error_code="LIBRARY_WRITE_FAILED",
        last_error_summary="素材索引暂时不可写",
        duration_seconds=23.6,
        width=1920,
        height=1080,
        fps=60.0,
        file_size_bytes=pending_video.stat().st_size,
    )
    pending_path = root / "pending-recordings.json"
    save_pending(pending_path, [pending_item])
    pending = MaterialLibraryDialog(
        RecordingLibraryService(root / "pending-library.json"),
        pending_service=PendingRecordingService(pending_path),
        current_save_dir=root,
    )
    pending._table.selectRow(0)
    pending._update_detail()
    _capture(pending, "material-library-pending-current", app)

    failed_path = root / "failed-recordings.json"
    failed_path.write_text("{ invalid json", encoding="utf-8")
    failed = MaterialLibraryDialog(RecordingLibraryService(failed_path))
    _capture(failed, "material-library-error-current", app)


def _capture_window_selector(app: QApplication) -> None:
    dialog = WindowSelector()
    _capture(dialog, "window-selector-current", app)


def _controlled_desktop_background(width: int, height: int) -> QPixmap:
    """生成不包含用户桌面隐私的受控背景，用于表达透明区域选择器。"""
    background = QPixmap(width, height)
    background.fill(QColor("#eef2f7"))
    painter = QPainter(background)
    painter.fillRect(0, 0, width, 64, QColor("#ffffff"))
    painter.fillRect(32, 92, width - 64, height - 132, QColor("#ffffff"))
    painter.fillRect(58, 128, 220, height - 204, QColor("#dbe5f3"))
    painter.fillRect(310, 128, width - 400, 84, QColor("#e7edf5"))
    painter.fillRect(310, 236, width - 400, 250, QColor("#f4f7fb"))
    painter.setPen(QColor("#182230"))
    title_font = QFont("Microsoft YaHei UI", 16)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.drawText(52, 42, "受控测试桌面 · QuickRec 区域选择参考")
    painter.setFont(QFont("Microsoft YaHei UI", 11))
    painter.drawText(330, 178, "拖拽选区后，透明区域保留原桌面内容")
    painter.drawText(330, 286, "区域外显示半透明遮罩；选区显示尺寸和确认操作")
    painter.end()
    return background


def _capture_area_selector(app: QApplication) -> None:
    selector = AreaSelector()
    selector.setGeometry(QRect(0, 0, 1280, 720))
    selector._start_point = QPoint(150, 110)
    selector._end_point = QPoint(1060, 610)
    selector._is_drawing = True
    selector._selected_rect = selector._get_selection_rect()
    selector._show_confirm_dialog(selector._selected_rect)
    background = _controlled_desktop_background(1280, 720)
    _capture(
        selector,
        "area-selector-current",
        app,
        controlled_background=background,
    )


def _capture_toolbar_states(app: QApplication, root: Path) -> None:
    toolbar = RecordingToolbar()
    toolbar.start_countdown(3)
    toolbar._countdown_timer.stop()
    _capture(toolbar, "toolbar-countdown-current", app)

    toolbar = RecordingToolbar()
    toolbar.start_recording_timer()
    toolbar._timer.stop()
    toolbar._elapsed_seconds = 42
    toolbar._update_timer()
    _capture(toolbar, "toolbar-recording-current", app)

    toolbar = RecordingToolbar()
    toolbar.start_recording_timer()
    toolbar._timer.stop()
    toolbar._elapsed_seconds = 42
    toolbar._update_timer()
    toolbar.set_paused(True)
    _capture(toolbar, "toolbar-paused-current", app)

    toolbar = RecordingToolbar()
    toolbar.show_saving()
    _capture(toolbar, "toolbar-saving-current", app)

    toolbar = RecordingToolbar()
    toolbar.show_result(str(root / "QuickRec_reference.mp4"), "84.6 MB")
    toolbar._auto_close_timer.stop()
    _capture(toolbar, "toolbar-result-current", app)


def _capture_tray_menu_reference(app: QApplication) -> None:
    menu = QMenu()
    for text in (
        "▶ 全屏录制",
        "▢ 区域录制",
        "🖥 窗口录制",
        "⚙ 设置",
        "素材库",
        "📁 打开保存文件夹",
    ):
        menu.addAction(text)
    menu.addSeparator()
    for text in ("复制诊断信息", "打开日志目录", "导出诊断文件"):
        menu.addAction(text)
    menu.addSeparator()
    menu.addAction("✕ 退出")
    menu.adjustSize()
    _capture(menu, "tray-menu-structure-reference", app)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QT_SCALE_FACTOR", "1")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix="quickrec-v17-reference-") as temp_dir:
        root = Path(temp_dir)
        _capture_settings(app, root)
        _capture_library(app, root)
        _capture_window_selector(app)
        _capture_area_selector(app)
        _capture_toolbar_states(app, root)
        _capture_tray_menu_reference(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
