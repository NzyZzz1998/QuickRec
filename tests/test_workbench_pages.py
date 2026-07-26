from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication

from config import ConfigManager, ConfigSaveResult
from ui.workbench_pages import DiagnosticPage, RecordingPage

APP = QApplication.instance() or QApplication([])


def _config(tmp_path: Path) -> ConfigManager:
    config = ConfigManager.__new__(ConfigManager)
    config.config_path = tmp_path / "config.json"
    config._config = ConfigManager.defaults.copy()
    config._config.update(
        {
            "save_path": str(tmp_path / "视频 目录"),
            "quality": "high",
            "fps": 60,
            "audio_source": "both",
        }
    )
    return config


def test_recording_page_shows_effective_configuration_and_routes_modes(tmp_path):
    page = RecordingPage(_config(tmp_path))
    calls: list[str] = []
    page.start_fullscreen_requested.connect(lambda: calls.append("fullscreen"))
    page.start_region_requested.connect(lambda: calls.append("region"))
    page.start_window_requested.connect(lambda: calls.append("window"))

    page._btn_fullscreen.click()
    page._btn_region.click()
    page._btn_window.click()

    assert calls == ["fullscreen", "region", "window"]
    assert "1080p" in page._quality_value.text()
    assert page._fps_value.text() == "60 FPS"
    assert "系统声音 + 麦克风" in page._audio_value.text()
    assert "视频 目录" in page._path_value.text()


def test_recording_page_exposes_read_only_recording_state_and_result(tmp_path):
    page = RecordingPage(_config(tmp_path))

    page.set_recording_state("recording", mode="window")

    assert "窗口录制中" in page._state_title.text()
    assert not page._btn_fullscreen.isEnabled()
    assert not page._btn_region.isEnabled()
    assert not page._btn_window.isEnabled()

    output = tmp_path / "QuickRec result.mp4"
    page.show_result(str(output), "12.4 MB", index_ok=False)

    assert not page._result_panel.isHidden()
    assert "素材入库失败" in page._result_status.text()
    assert not page._btn_retry_material.isHidden()


def test_recording_page_success_resets_a_previous_failure_state(tmp_path):
    page = RecordingPage(_config(tmp_path))
    output = tmp_path / "QuickRec recovered.mp4"

    page.show_failure("编码器未生成输出")
    page.show_result(str(output), "5.0 MB", index_ok=True)

    assert page._result_title.text() == "录制已保存"
    assert not page._btn_open_file.isHidden()
    assert not page._btn_open_folder.isHidden()
    assert not page._btn_open_material.isHidden()
    assert page._btn_retry_material.isHidden()


def test_recording_page_warns_when_120_fps_is_not_stable(tmp_path):
    page = RecordingPage(_config(tmp_path))
    output = tmp_path / "QuickRec 120.mp4"

    page.show_result(
        str(output),
        "20.0 MB",
        index_ok=True,
        performance_text="目标 120 FPS · 平均 110.0 FPS · 未稳定达到 120 FPS",
        performance_stable=False,
    )

    assert not page._result_performance.isHidden()
    assert "未稳定达到 120 FPS" in page._result_performance.text()
    assert page._result_panel.property("state") == "warning"


def test_diagnostic_page_uses_explicit_save_and_tracks_dirty_state(tmp_path):
    config = _config(tmp_path)
    page = DiagnosticPage(config)
    saved: list[bool] = []
    page.config_saved.connect(lambda: saved.append(True))
    target = tmp_path / "自定义 诊断"

    page._edit_diagnostic_dir.setText(str(target))

    assert page.is_dirty
    assert page.save_changes() is True
    assert not page.is_dirty
    assert saved == [True]
    assert config.get_diagnostic_dir() == str(target)


def test_diagnostic_page_save_failure_keeps_candidate_and_dirty_state(tmp_path):
    config = _config(tmp_path)
    page = DiagnosticPage(config)
    original = config.get_diagnostic_dir()
    target = tmp_path / "无法写入"
    page._edit_diagnostic_dir.setText(str(target))
    failure = ConfigSaveResult(False, "replace", "denied", str(config.config_path))

    with patch.object(config, "save_candidate", return_value=failure):
        result = page.save_changes()

    assert result is False
    assert page.is_dirty
    assert page._edit_diagnostic_dir.text() == str(target)
    assert config.get_diagnostic_dir() == original
    assert "保存失败" in page._status_label.text()
