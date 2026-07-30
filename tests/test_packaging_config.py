from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging


SPEC_TEXT = Path("build_std.spec").read_text(encoding="utf-8")
CI_TEXT = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")


def test_pyinstaller_spec_includes_ffmpeg_binary():
    assert "('ffmpeg/ffmpeg.exe', 'ffmpeg')" in SPEC_TEXT


def test_pyinstaller_spec_includes_ffprobe_binary():
    assert "('ffmpeg/ffprobe.exe', 'ffmpeg')" in SPEC_TEXT


def test_pyinstaller_spec_includes_runtime_hiddenimports():
    required_hiddenimports = [
        "recorder.recorder_manager",
        "recorder.video_encoder",
        "recorder.audio_capturer",
        "recorder.events",
        "recorder.frame_resize",
        "recorder.state_machine",
        "recorder.timer_resolution",
        "recorder.workflow",
        "ui.tray_icon",
        "ui.toolbar",
        "ui.design_system",
        "ui.material_library_dialog",
        "ui.project_dialogs",
        "ui.project_page",
        "ui.qt_localization",
        "ui.workbench_pages",
        "ui.workbench_window",
        "ui.timeline_canvas",
        "ui.timeline_edit_dialogs",
        "ui.timeline_editor_window",
        "ui.timeline_trim_interaction",
        "ui.clip_inspector_widget",
        "hotkey.hotkey_manager",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "soundcard.mediafoundation",
        "pyaudio",
        "winotify",
        "cv2",
        "services.application_events",
        "services.recording_library",
        "services.recording_guard",
        "services.single_instance",
        "services.pending_recordings",
        "services.material_ingestion",
        "services.material_query",
        "services.material_query_session",
        "services.project_deletion",
        "services.project_library",
        "services.project_query",
        "services.project_recording",
        "services.project_save_coordinator",
        "services.timeline_commands",
        "services.timeline_edit_service",
        "services.timeline_health",
        "services.timeline_history",
        "services.timeline_media_runtime",
        "services.timeline_query",
        "services.timeline_session",
        "services.playback_backend",
        "services.playback_runtime",
        "services.pyav_playback_backend",
        "utils.timeline_model",
        "utils.recording_library_store",
        "utils.pending_recording_store",
        "utils.schema_migrations",
        "utils.media_metadata",
        "utils.project_store",
        "utils.recycle_bin",
        "send2trash",
        "av",
        "exporting.plan_builder",
        "exporting.executor",
        "exporting.verifier",
        "exporting.committer",
        "cli.export_commands",
    ]

    for module_name in required_hiddenimports:
        assert f"'{module_name}'" in SPEC_TEXT


def test_pyinstaller_spec_does_not_include_removed_runtime_modules():
    removed_modules = [
        "recorder.cursor_overlay",
        "ui.recent_recordings_dialog",
        "utils.recording_history",
    ]

    for module_name in removed_modules:
        assert f"'{module_name}'" not in SPEC_TEXT


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


def test_pyinstaller_spec_builds_independent_cli_in_same_onedir_app():
    assert "['src/cli_entry.py']" in SPEC_TEXT
    assert "name='QuickRecCLI'" in SPEC_TEXT
    assert "cli_exe" in SPEC_TEXT
    assert "cli_analysis.binaries" in SPEC_TEXT
    assert SPEC_TEXT.count("COLLECT(") == 1


def test_ci_stages_real_ffmpeg_tools_before_pyinstaller_build():
    stage_marker = "- name: Stage FFmpeg tools"
    build_marker = "- name: Build onedir package"

    assert stage_marker in CI_TEXT
    assert build_marker in CI_TEXT
    assert CI_TEXT.index(stage_marker) < CI_TEXT.index(build_marker)
    assert "choco install ffmpeg" in CI_TEXT
    assert "ffmpeg\\ffmpeg.exe" in CI_TEXT
    assert "ffmpeg\\ffprobe.exe" in CI_TEXT
    assert "Get-Item -LiteralPath $path" in CI_TEXT
    assert "& \"ffmpeg\\ffmpeg.exe\" -version" in CI_TEXT
    assert "& \"ffmpeg\\ffprobe.exe\" -version" in CI_TEXT


def test_ci_stages_real_ffmpeg_tools_before_baseline_pytest():
    test_job = CI_TEXT.split("\n  packaging:", 1)[0]
    stage_marker = "- name: Stage FFmpeg tools"
    pytest_marker = "- name: Pytest with coverage"

    assert stage_marker in test_job
    assert pytest_marker in test_job
    assert test_job.index(stage_marker) < test_job.index(pytest_marker)


def test_ci_verifies_pyav_runtime_files_in_package():
    assert "ci-dist\\QuickRec\\_internal\\av\\_core.pyd" in CI_TEXT
    assert "ci-dist\\QuickRec\\_internal\\av.libs" in CI_TEXT
    assert "avcodec-*.dll" in CI_TEXT


def test_ci_verifies_frozen_cli_contract_and_editing_smoke():
    assert "ci-dist\\QuickRec\\QuickRecCLI.exe" in CI_TEXT
    assert '$cli = "ci-dist\\QuickRec\\QuickRecCLI.exe"' in CI_TEXT
    assert "& $cli doctor --json" in CI_TEXT
    assert "& $cli smoke --suite editing" in CI_TEXT
    assert "& $cli probe" in CI_TEXT
    assert "& $cli timeline validate" in CI_TEXT
    assert "& $cli export validate" in CI_TEXT
    assert "& $cli export smoke" in CI_TEXT
    assert "export-smoke.json" in CI_TEXT
