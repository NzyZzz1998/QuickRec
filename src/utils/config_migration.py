"""从拆分前 QuickRec 配置安全导入 Lite 白名单字段。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from config import ConfigManager, ConfigSaveResult

_AUDIO_SOURCES = {"none", "system", "microphone", "both"}


@dataclass(frozen=True)
class MigrationResult:
    ok: bool
    stage: str
    message: str = ""
    warnings: tuple[str, ...] = ()
    save_result: ConfigSaveResult | None = None


class LiteConfigMigration:
    """只读旧配置并原子创建 Lite 独立配置。"""

    def __init__(
        self,
        config: ConfigManager,
        legacy_path: Path | None = None,
    ) -> None:
        self._config = config
        self.legacy_path = legacy_path or (
            config.config_path.parent.parent / "QuickRec" / "config.json"
        )

    def should_offer(self) -> bool:
        return not self._config.config_path.exists() and self.legacy_path.is_file()

    def import_settings(self) -> MigrationResult:
        try:
            loaded = json.loads(self.legacy_path.read_text(encoding="utf-8-sig"))
            if not isinstance(loaded, dict):
                raise ValueError("旧配置根节点必须是对象")
        except Exception as exc:
            return MigrationResult(False, "read_legacy", str(exc))

        candidate = ConfigManager.defaults.copy()
        warnings: list[str] = []

        save_path = loaded.get("save_path")
        if self._valid_save_path(save_path):
            candidate["save_path"] = str(save_path).strip()
        else:
            warnings.append("旧保存路径无效，已使用 Lite 默认目录。")

        audio_source = loaded.get("audio_source")
        if audio_source in _AUDIO_SOURCES:
            candidate["audio_source"] = audio_source
        else:
            warnings.append("旧音频模式无效，已使用无声。")

        return self._save("import", candidate, tuple(warnings))

    def use_defaults(self) -> MigrationResult:
        return self._save("defaults", ConfigManager.defaults.copy(), ())

    def _save(
        self,
        stage: str,
        candidate: dict[str, object],
        warnings: tuple[str, ...],
    ) -> MigrationResult:
        result = self._config.save_candidate(candidate)
        if not result.ok:
            return MigrationResult(
                False,
                result.stage,
                result.message,
                warnings,
                result,
            )
        return MigrationResult(True, stage, warnings=warnings, save_result=result)

    @staticmethod
    def _valid_save_path(value: object) -> bool:
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            return False
        try:
            Path(value).parent
        except (OSError, ValueError):
            return False
        return True
