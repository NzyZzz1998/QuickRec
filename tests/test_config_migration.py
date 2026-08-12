from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import main
from config import ConfigManager
from utils.config_migration import LiteConfigMigration


def make_config(path: Path) -> ConfigManager:
    config = ConfigManager.__new__(ConfigManager)
    config.config_path = path
    config._config = ConfigManager.defaults.copy()
    config._persisted_config = ConfigManager.defaults.copy()
    return config


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_migration_is_offered_only_when_legacy_exists_and_lite_is_absent(tmp_path: Path) -> None:
    legacy = tmp_path / "QuickRec" / "config.json"
    lite = tmp_path / "QuickRec-Lite" / "config.json"
    legacy.parent.mkdir()
    legacy.write_text("{}", encoding="utf-8")
    migration = LiteConfigMigration(make_config(lite), legacy)

    assert migration.should_offer()
    lite.parent.mkdir()
    lite.write_text("{}", encoding="utf-8")
    assert not migration.should_offer()


def test_import_copies_only_valid_whitelist_fields_without_touching_source(tmp_path: Path) -> None:
    legacy = tmp_path / "QuickRec" / "config.json"
    lite = tmp_path / "QuickRec-Lite" / "config.json"
    legacy.parent.mkdir()
    legacy.write_text(
        json.dumps(
            {
                "save_path": str(tmp_path / "旧 视频"),
                "audio_source": "both",
                "shortcut_start": "Ctrl+Q",
                "auto_start": True,
                "shortcut_area": "Ctrl+A",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source_hash = sha256(legacy)
    config = make_config(lite)

    result = LiteConfigMigration(config, legacy).import_settings()

    assert result.ok
    assert result.warnings == ()
    assert config.get("save_path") == str(tmp_path / "旧 视频")
    assert config.get("audio_source") == "both"
    assert config.get("shortcut_start") == "Ctrl+Alt+R"
    assert config.get("auto_start") is False
    assert "shortcut_area" not in config.snapshot()
    assert sha256(legacy) == source_hash


def test_invalid_fields_fall_back_independently_and_report_warnings(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps({"save_path": "", "audio_source": "mystery"}),
        encoding="utf-8",
    )
    config = make_config(tmp_path / "lite" / "config.json")

    result = LiteConfigMigration(config, legacy).import_settings()

    assert result.ok
    assert len(result.warnings) == 2
    assert config.get("save_path") == ConfigManager.defaults["save_path"]
    assert config.get("audio_source") == "none"


def test_corrupt_legacy_import_fails_without_creating_lite_config(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.json"
    legacy.write_text("{broken", encoding="utf-8")
    config = make_config(tmp_path / "lite" / "config.json")

    result = LiteConfigMigration(config, legacy).import_settings()

    assert not result.ok
    assert result.stage == "read_legacy"
    assert not config.config_path.exists()


def test_use_defaults_does_not_read_or_modify_corrupt_legacy(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.json"
    legacy.write_text("{broken", encoding="utf-8")
    source_hash = sha256(legacy)
    config = make_config(tmp_path / "lite" / "config.json")

    result = LiteConfigMigration(config, legacy).use_defaults()

    assert result.ok
    assert config.config_path.exists()
    assert sha256(legacy) == source_hash


def test_startup_migration_cancel_prevents_application_start(tmp_path: Path) -> None:
    legacy = tmp_path / "QuickRec" / "config.json"
    legacy.parent.mkdir()
    legacy.write_text("{}", encoding="utf-8")
    config = make_config(tmp_path / "QuickRec-Lite" / "config.json")

    class RejectingDialog:
        def __init__(self, _migration) -> None:
            pass

        def exec_(self) -> int:
            return 0

    assert not main.ensure_initial_config(config, dialog_factory=RejectingDialog)
    assert not config.config_path.exists()


def test_startup_skips_migration_when_lite_config_exists(tmp_path: Path) -> None:
    config = make_config(tmp_path / "QuickRec-Lite" / "config.json")
    config.config_path.parent.mkdir()
    config.config_path.write_text("{}", encoding="utf-8")

    assert main.ensure_initial_config(
        config,
        dialog_factory=lambda _migration: (_ for _ in ()).throw(
            AssertionError("dialog must not open")
        ),
    )
