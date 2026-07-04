from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging


SPEC_TEXT = Path("build_std.spec").read_text(encoding="utf-8")


def test_pyinstaller_spec_includes_ffmpeg_binary():
    assert "('ffmpeg/ffmpeg.exe', 'ffmpeg')" in SPEC_TEXT


def test_pyinstaller_spec_includes_runtime_hiddenimports():
    required_hiddenimports = [
        "recorder.recorder_manager",
        "recorder.video_encoder",
        "recorder.audio_capturer",
        "recorder.cursor_overlay",
        "recorder.events",
        "recorder.frame_resize",
        "recorder.state_machine",
        "recorder.timer_resolution",
        "recorder.workflow",
        "ui.tray_icon",
        "ui.toolbar",
        "hotkey.hotkey_manager",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "soundcard.mediafoundation",
        "pyaudio",
        "winotify",
        "cv2",
    ]

    for module_name in required_hiddenimports:
        assert f"'{module_name}'" in SPEC_TEXT


def test_pyinstaller_spec_keeps_size_exclusion_filters():
    required_filters = [
        "_QT_EXCLUDE_DLLS",
        "_ANGLE_DLLS",
        "_PIL_EXCLUDE",
        "_CV2_EXCLUDE",
        "_QT_PLUGIN_EXCLUDE",
        "_should_exclude",
        "Qt5WebEngine",
        "libGLESv2",
        "opencv_videoio_ffmpeg",
        "_webp.",
        "qwebp",
    ]

    for filter_name in required_filters:
        assert filter_name in SPEC_TEXT


def test_pyinstaller_spec_keeps_cv2_but_excludes_opencv_videoio_ffmpeg():
    assert "'cv2'" in SPEC_TEXT
    assert "_CV2_EXCLUDE" in SPEC_TEXT
    assert "opencv_videoio_ffmpeg" in SPEC_TEXT


def test_pyinstaller_spec_builds_quickrec_onedir_app():
    assert "name='QuickRec'" in SPEC_TEXT
    assert "COLLECT(" in SPEC_TEXT
    assert "console=True" in SPEC_TEXT
    assert "upx=True" in SPEC_TEXT
