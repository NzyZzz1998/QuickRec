from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import config as config_module
from config import ConfigManager


def make_config(path: Path) -> ConfigManager:
    config = ConfigManager.__new__(ConfigManager)
    config.config_path = path
    config._config = ConfigManager.defaults.copy()
    config._persisted_config = ConfigManager.defaults.copy()
    return config


def test_save_candidate_commits_file_and_memory_atomically(tmp_path: Path) -> None:
    config = make_config(tmp_path / "config.json")
    candidate = config.snapshot()
    candidate["audio_source"] = "system"

    result = config.save_candidate(candidate)

    assert result.ok
    assert result.stage == "complete"
    assert config.get("audio_source") == "system"
    assert json.loads(config.config_path.read_text(encoding="utf-8"))["audio_source"] == "system"
    assert list(tmp_path.glob("*.tmp")) == []


def test_replace_failure_preserves_old_file_and_memory(tmp_path: Path, monkeypatch) -> None:
    config = make_config(tmp_path / "config.json")
    assert config.save_candidate(config.snapshot()).ok
    old_bytes = config.config_path.read_bytes()
    candidate = config.snapshot()
    candidate["audio_source"] = "both"

    def fail_replace(_source, _target):
        raise PermissionError("blocked")

    monkeypatch.setattr(os, "replace", fail_replace)
    result = config.save_candidate(candidate)

    assert not result.ok
    assert result.stage == "replace"
    assert config.get("audio_source") == "none"
    assert config.config_path.read_bytes() == old_bytes
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_failure_restores_last_persisted_memory(tmp_path: Path, monkeypatch) -> None:
    config = make_config(tmp_path / "config.json")
    assert config.save_candidate(config.snapshot()).ok
    config.set("audio_source", "microphone")

    monkeypatch.setattr(os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("fail")))
    result = config.save()

    assert not result.ok
    assert config.get("audio_source") == "none"


def test_load_filters_obsolete_and_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "save_path": str(tmp_path / "videos"),
                "audio_source": "both",
                "shortcut_area": "Ctrl+Shift+A",
                "show_countdown": True,
                "unknown": "ignored",
            }
        ),
        encoding="utf-8",
    )
    config = make_config(path)

    config.load()

    assert config.get("audio_source") == "both"
    assert "shortcut_area" not in config.snapshot()
    assert "show_countdown" not in config.snapshot()
    assert "unknown" not in config.snapshot()


def test_prepare_directory_failure_has_no_memory_or_file_side_effect(tmp_path: Path, monkeypatch) -> None:
    config = make_config(tmp_path / "missing" / "config.json")
    before = config.snapshot()

    def fail_mkdir(*_args, **_kwargs) -> None:
        raise PermissionError("directory blocked")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    result = config.save_candidate({**before, "audio_source": "system"})

    assert not result.ok
    assert result.stage == "prepare_directory"
    assert config.snapshot() == before
    assert not config.config_path.exists()


def test_temporary_file_failure_has_no_memory_side_effect(tmp_path: Path, monkeypatch) -> None:
    config = make_config(tmp_path / "config.json")
    before = config.snapshot()

    def fail_temp_file(*_args, **_kwargs):
        raise OSError("temporary file blocked")

    monkeypatch.setattr(config_module.tempfile, "NamedTemporaryFile", fail_temp_file)
    result = config.save_candidate({**before, "audio_source": "both"})

    assert not result.ok
    assert result.stage == "write_temp"
    assert config.snapshot() == before
    assert list(tmp_path.glob("*.tmp")) == []


def test_load_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")
    config = make_config(path)

    config.load()

    assert config.snapshot() == ConfigManager.defaults


def test_native_resolution_uses_win32_metrics(monkeypatch) -> None:
    user32 = SimpleNamespace(GetSystemMetrics=lambda index: (1920, 1080)[index])
    monkeypatch.setattr(config_module.ctypes, "windll", SimpleNamespace(user32=user32))

    assert ConfigManager.get_native_resolution() == (1920, 1080)
