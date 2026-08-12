from pathlib import Path

from hotkey.hotkey_manager import HotkeyManager
from recorder.recorder_manager import RecorderManager
from recorder.screen_capturer import ScreenCapturer
from recorder.workflow import RecordingWorkflow
from ui.toolbar import RecordingToolbar

ROOT = Path(__file__).resolve().parents[1]


def test_lite_public_recording_api_is_fullscreen_only():
    assert not hasattr(RecorderManager, "start_region")
    assert not hasattr(RecorderManager, "start_window")
    assert not hasattr(RecordingWorkflow, "start_region")
    assert not hasattr(RecordingWorkflow, "start_window")


def test_lite_screen_capturer_has_no_region_mutation_api():
    assert not hasattr(ScreenCapturer, "update_region")
    assert not hasattr(ScreenCapturer, "get_capture_region")


def test_lite_runtime_has_no_countdown_or_selection_bridges():
    assert not hasattr(RecordingToolbar, "start_countdown")
    assert not hasattr(RecordingToolbar, "is_countdown_mode")
    assert not hasattr(HotkeyManager, "set_esc_callback")

    main_source = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
    tray_source = (ROOT / "src" / "ui" / "tray_icon.py").read_text(encoding="utf-8")
    forbidden = (
        "AreaSelector",
        "WindowSelector",
        "WindowHighlighter",
        "ClickHighlighter",
        "start_region",
        "start_window",
        "countdown",
    )
    for token in forbidden:
        assert token not in main_source
        assert token not in tray_source


def test_lite_package_does_not_collect_dedicated_full_mode_modules():
    spec_source = (ROOT / "build_std.spec").read_text(encoding="utf-8")
    dedicated_modules = (
        "ui.area_selector",
        "ui.window_selector",
        "ui.window_highlighter",
        "ui.click_highlighter",
        "recorder.window_diagnostics",
    )
    for module in dedicated_modules:
        assert module not in spec_source


def test_dedicated_full_mode_files_are_absent_from_lite_tree():
    dedicated_files = (
        "src/ui/area_selector.py",
        "src/ui/window_selector.py",
        "src/ui/window_highlighter.py",
        "src/ui/click_highlighter.py",
        "src/recorder/window_diagnostics.py",
    )
    for relative_path in dedicated_files:
        assert not (ROOT / relative_path).exists()
