import subprocess
from pathlib import Path

import pytest
from scripts.stage_ffmpeg import (
    FFMPEG_EXECUTABLE_SHA256,
    FFMPEG_VERSION_LINE,
    sha256_file,
)

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
        "recorder.state_machine",
        "recorder.timer_resolution",
        "recorder.workflow",
        "ui.tray_icon",
        "ui.toolbar",
        "hotkey.hotkey_manager",
        "pynput.keyboard._win32",
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


def test_pyinstaller_spec_builds_quickrec_lite_onedir_app():
    assert "name='QuickRec-Lite'" in SPEC_TEXT
    assert "name='QuickRec'" not in SPEC_TEXT
    assert "COLLECT(" in SPEC_TEXT
    assert "console=True" in SPEC_TEXT
    assert "upx=True" in SPEC_TEXT


def test_staged_ffmpeg_has_locked_identity():
    ffmpeg = Path("ffmpeg/ffmpeg.exe")

    assert ffmpeg.is_file()
    assert sha256_file(ffmpeg) == FFMPEG_EXECUTABLE_SHA256
    completed = subprocess.run(
        [str(ffmpeg), "-version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    assert completed.returncode == 0
    assert completed.stdout.splitlines()[0] == FFMPEG_VERSION_LINE


def test_ci_stages_locked_ffmpeg_and_verifies_lite_package():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "choco install ffmpeg" not in workflow
    assert "python scripts/stage_ffmpeg.py" in workflow
    assert "ci-dist\\QuickRec-Lite\\QuickRec-Lite.exe" in workflow
    assert "ci-dist\\QuickRec-Lite\\_internal\\ffmpeg\\ffmpeg.exe" in workflow
    assert "scripts/release_manifest.py" in workflow
