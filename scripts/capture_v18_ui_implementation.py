"""生成 QuickRec Full v1.8 实际 PyQt 界面截图。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scale", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_SCALE_FACTOR"] = str(args.scale)

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root / "src"))

    from PyQt5.QtCore import QEventLoop, QRect, Qt, QTimer
    from PyQt5.QtWidgets import QApplication, QMessageBox

    from config import ConfigManager
    from services.capture_capability import SelfTestResult
    from services.material_ingestion import MaterialIngestionCoordinator
    from services.pending_recordings import PendingRecordingService
    from services.recording_library import RecordingLibraryService
    from ui.area_selector import AreaSelector
    from ui.capture_self_test_dialog import CaptureSelfTestDialog
    from ui.material_library_dialog import MaterialLibraryDialog
    from ui.qt_localization import install_qt_zh_cn
    from ui.settings_dialog import SettingsDialog
    from ui.toolbar import RecordingToolbar
    from ui.workbench_pages import DiagnosticPage, RecordingPage
    from ui.workbench_window import WorkbenchPage, WorkbenchWindow
    from utils.recording_library_store import MaterialItem

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication.instance() or QApplication([])
    qt_translator = install_qt_zh_cn(app)
    app.setProperty("quickrecQtTranslator", qt_translator)

    def wait_for_animation(milliseconds: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(milliseconds, loop.quit)
        loop.exec_()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_dir = output_dir / "示例 素材"
    sample_dir.mkdir(parents=True, exist_ok=True)

    config = ConfigManager.__new__(ConfigManager)
    config.config_path = output_dir / "config.json"
    config._config = ConfigManager.defaults.copy()
    config._config.update(
        {
            "save_path": str(sample_dir),
            "quality": "high",
            "fps": 60,
            "audio_source": "both",
            "show_countdown": True,
        }
    )

    items: list[MaterialItem] = []
    for index, name in enumerate(
        (
            "QuickRec_工作台演示.mp4",
            "QuickRec_窗口录制_长文件名示例.mp4",
            "QuickRec_区域录制.mp4",
        ),
        start=1,
    ):
        path = sample_dir / name
        path.write_bytes(b"QuickRec UI sample")
        items.append(
            MaterialItem(
                id=f"ui-sample-{index}",
                file_path=str(path),
                file_name=path.name,
                directory=str(path.parent),
                mode=("fullscreen", "window", "region")[index - 1],
                audio_source=("both", "system", "none")[index - 1],
                created_at=f"2026-07-24T10:0{index}:00+08:00",
                duration_sec=12.5 + index,
                width=1920 if index != 3 else 1280,
                height=1080 if index != 3 else 720,
                fps=60.0,
                file_size_bytes=18 * 1024 * 1024,
            )
        )

    library = RecordingLibraryService(output_dir / "recordings.json")
    library.replace(items)
    pending = PendingRecordingService(output_dir / "pending-recordings.json")
    ingestion = MaterialIngestionCoordinator(library, pending)

    recording_page = RecordingPage(config)
    material_page = MaterialLibraryDialog(
        library,
        pending_service=pending,
        ingestion_coordinator=ingestion,
        current_save_dir=sample_dir,
        embedded=True,
    )
    settings_page = SettingsDialog(config, embedded=True)
    diagnostic_page = DiagnosticPage(config)
    window = WorkbenchWindow(
        pages={
            WorkbenchPage.RECORDING: recording_page,
            WorkbenchPage.MATERIALS: material_page,
            WorkbenchPage.SETTINGS: settings_page,
            WorkbenchPage.DIAGNOSTICS: diagnostic_page,
        }
    )
    window.resize(1200, 760)
    window.show()
    app.processEvents()

    suffix = f"{int(round(args.scale * 100))}"
    for page in WorkbenchPage:
        window.set_current_page(page)
        app.processEvents()
        window.grab().save(str(output_dir / f"workbench-{page.value}-{suffix}.png"))

    window.set_current_page(WorkbenchPage.RECORDING)
    recording_page.show_result(
        str(sample_dir / "QuickRec_工作台演示.mp4"),
        "18.0 MB",
        index_ok=True,
    )
    app.processEvents()
    window.grab().save(
        str(output_dir / f"workbench-recording-result-{suffix}.png")
    )
    recording_page.show_failure("编码器未能启动，请打开诊断页查看详细原因。")
    app.processEvents()
    window.grab().save(
        str(output_dir / f"workbench-recording-failure-{suffix}.png")
    )
    recording_page.show_result(
        str(sample_dir / "QuickRec_工作台演示.mp4"),
        "18.0 MB",
        index_ok=True,
        performance_text=(
            "目标 120 FPS · 平均 110.0 FPS · 最低每秒 101 FPS · "
            "未稳定达到 120 FPS，视频已正常保存"
        ),
        performance_stable=False,
    )
    app.processEvents()
    window.grab().save(
        str(output_dir / f"workbench-recording-performance-warning-{suffix}.png")
    )
    recording_page.clear_result()

    library.replace([])
    material_page.reload()
    window.set_current_page(WorkbenchPage.MATERIALS)
    app.processEvents()
    window.grab().save(str(output_dir / f"workbench-materials-empty-{suffix}.png"))

    library.replace(items)
    missing_path = Path(items[1].file_path)
    missing_path.unlink()
    material_page.reload()
    material_page._table.selectRow(1)
    app.processEvents()
    window.grab().save(
        str(output_dir / f"workbench-materials-missing-{suffix}.png")
    )
    missing_path.write_bytes(b"QuickRec UI sample")
    library.replace(items)
    material_page.reload()

    window.resize(960, 640)
    window.set_current_page(WorkbenchPage.SETTINGS)
    app.processEvents()
    window.grab().save(str(output_dir / f"workbench-settings-min-{suffix}.png"))
    window.close()

    toolbar = RecordingToolbar()
    toolbar.show()
    toolbar.start_recording_timer()
    app.processEvents()
    toolbar.grab().save(str(output_dir / f"toolbar-recording-{suffix}.png"))
    toolbar.set_paused(True)
    wait_for_animation(220)
    toolbar.grab().save(str(output_dir / f"toolbar-paused-{suffix}.png"))
    toolbar.show_result(str(sample_dir / "QuickRec_工作台演示.mp4"), "18.0 MB")
    wait_for_animation(220)
    toolbar.grab().save(str(output_dir / f"toolbar-result-{suffix}.png"))
    toolbar.close()

    countdown_toolbar = RecordingToolbar()
    countdown_toolbar.show()
    countdown_toolbar.start_countdown(3)
    wait_for_animation(220)
    countdown_toolbar.grab().save(
        str(output_dir / f"toolbar-countdown-{suffix}.png")
    )
    countdown_toolbar.cancel_countdown()

    saving_toolbar = RecordingToolbar()
    saving_toolbar.show()
    saving_toolbar.show_saving()
    wait_for_animation(220)
    saving_toolbar.grab().save(str(output_dir / f"toolbar-saving-{suffix}.png"))
    saving_toolbar.close()

    import ui.window_selector as selector_module

    selector_module._enum_visible_windows = lambda: [
        (101, "演示窗口 - QuickRec UI", False),
        (202, "素材管理 - 中文与空格", False),
        (303, "设置窗口（最小化）", True),
    ]
    selector = selector_module.WindowSelector()
    selector._list.setCurrentRow(0)
    selector.show()
    app.processEvents()
    selector.grab().save(str(output_dir / f"window-selector-{suffix}.png"))
    selector.close()

    area = AreaSelector()
    area.resize(1280, 720)
    area._selected_rect = QRect(220, 130, 840, 480)
    area._show_confirm_dialog(area._selected_rect)
    area.show()
    app.processEvents()
    area.grab().save(str(output_dir / f"area-selector-{suffix}.png"))
    area.close()

    class _UnusedRuntime:
        def run(self, _cancel_event, *, progress):
            progress("capture", 42)
            raise AssertionError("视觉取证不应运行硬件自检")

    self_test = CaptureSelfTestDialog(
        _UnusedRuntime(),
        open_diagnostics=lambda: None,
    )
    self_test.show()
    self_test._on_progress("capture", 42)
    app.processEvents()
    self_test.grab().save(
        str(output_dir / f"self-test-running-{suffix}.png")
    )
    self_test._on_finished(
        SelfTestResult(
            status="passed",
            passed=True,
            average_fps=119.7,
            minimum_one_second_fps=117,
        )
    )
    app.processEvents()
    self_test.grab().save(
        str(output_dir / f"self-test-passed-{suffix}.png")
    )
    self_test._on_finished(
        SelfTestResult(
            status="failed",
            passed=False,
            average_fps=109.4,
            minimum_one_second_fps=101,
            failure_reason="最低每秒帧率未达到 108 FPS",
        )
    )
    app.processEvents()
    self_test.grab().save(
        str(output_dir / f"self-test-failed-{suffix}.png")
    )
    self_test.close()

    def capture_message_box(
        name: str,
        title: str,
        text: str,
        buttons: tuple[tuple[int, str], ...],
    ) -> None:
        box = QMessageBox()
        box.setWindowTitle(title)
        box.setText(text)
        standard_buttons = QMessageBox.NoButton
        for standard_button, _label in buttons:
            standard_buttons |= standard_button
        box.setStandardButtons(standard_buttons)
        for standard_button, label in buttons:
            button = box.button(standard_button)
            if button is not None:
                button.setText(label)
        box.show()
        app.processEvents()
        box.grab().save(str(output_dir / f"{name}-{suffix}.png"))
        box.close()

    capture_message_box(
        "dialog-unsaved-settings",
        "设置尚未保存",
        "保存设置更改后再继续吗？",
        (
            (QMessageBox.Save, "保存"),
            (QMessageBox.Discard, "放弃"),
            (QMessageBox.Cancel, "取消"),
        ),
    )
    capture_message_box(
        "dialog-recycle-bin",
        "移入回收站",
        "将此视频移入 Windows 回收站？\n不会删除诊断日志或其他文件。",
        (
            (QMessageBox.Yes, "是"),
            (QMessageBox.No, "否"),
        ),
    )

    readiness_box = QMessageBox()
    readiness_box.setWindowTitle("需要重新检测 120 FPS")
    readiness_box.setText("录制环境已变化，需要重新检测")
    readiness_box.setInformativeText(
        "可以重新运行约 5 秒能力检测，或仅将本次全屏录制改用 60 FPS。"
    )
    readiness_box.addButton("重新检测", QMessageBox.AcceptRole)
    readiness_box.addButton("本次改用 60 FPS", QMessageBox.ActionRole)
    readiness_box.addButton(QMessageBox.Cancel)
    readiness_box.show()
    app.processEvents()
    readiness_box.grab().save(
        str(output_dir / f"dialog-120-readiness-{suffix}.png")
    )
    readiness_box.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
