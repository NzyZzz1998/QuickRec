"""
配置管理模块

管理 QuickRec 的用户配置，包括读写和持久化。
配置文件存储在 AppData/Roaming/QuickRec/config.json
"""

import ctypes
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.product_identity import default_save_path, lite_appdata_dir


@dataclass(frozen=True)
class ConfigSaveResult:
    """配置持久化的结构化结果。"""

    ok: bool
    stage: str
    message: str = ""
    path: str = ""


class ConfigManager:
    """配置管理器"""

    # 默认配置值
    defaults = {
        "save_path": str(default_save_path(Path.home())),
        "quality": "native",  # QuickRec Lite v0: fixed native output
        "fps": 60,  # QuickRec Lite v0: fixed 60fps output
        "shortcut_start": "Ctrl+Alt+R",
        "shortcut_stop": "Ctrl+Alt+S",
        "shortcut_pause": "Ctrl+Alt+P",
        "audio_source": "none",  # none / system / microphone / both
        "auto_start": False,
    }

    # 画质档位 → 目标分辨率 (width, height)，"native" 表示原始分辨率
    QUALITY_SIZES = {
        "native": None,
        "high": (1920, 1080),
        "medium": (1280, 720),
        "low": (854, 480),
    }

    # 音频源选项：显示文本 → 配置值
    AUDIO_OPTIONS = [
        ("无", "none"),
        ("系统声音", "system"),
        ("麦克风", "microphone"),
        ("两者都有", "both"),
    ]

    def __init__(self):
        """初始化配置管理器"""
        appdata = os.getenv("APPDATA")
        if not appdata:
            # 回退方案：使用当前目录
            appdata = Path.home()
        self.config_path = lite_appdata_dir(Path(appdata)) / "config.json"
        self._config = self.defaults.copy()
        self._persisted_config = self.defaults.copy()
        self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """
        读取配置项

        Args:
            key: 配置项键名
            default: 如果键不存在时的默认值

        Returns:
            配置项的值
        """
        return self._config.get(key, default if default is not None else self.defaults.get(key))

    def set(self, key: str, value: Any) -> None:
        """
        设置配置项

        Args:
            key: 配置项键名
            value: 配置项的值
        """
        self._config[key] = value

    def snapshot(self) -> dict[str, Any]:
        """返回与当前有效配置隔离的候选副本。"""
        return self._config.copy()

    def save_candidate(self, candidate: Mapping[str, Any]) -> ConfigSaveResult:
        """原子保存候选配置，成功后才更新内存状态。"""
        normalized = {
            key: candidate.get(key, default)
            for key, default in self.defaults.items()
        }
        temp_path: Path | None = None
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return ConfigSaveResult(
                False,
                "prepare_directory",
                str(exc),
                str(self.config_path),
            )

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.config_path.parent,
                prefix=f".{self.config_path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                json.dump(normalized, temp_file, indent=2, ensure_ascii=False)
                temp_file.flush()
                os.fsync(temp_file.fileno())
        except Exception as exc:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            return ConfigSaveResult(
                False,
                "write_temp",
                str(exc),
                str(self.config_path),
            )

        try:
            os.replace(temp_path, self.config_path)
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            return ConfigSaveResult(
                False,
                "replace",
                str(exc),
                str(self.config_path),
            )

        self._config = normalized.copy()
        self._persisted_config = normalized.copy()
        return ConfigSaveResult(True, "complete", path=str(self.config_path))

    def save(self) -> ConfigSaveResult:
        """保存当前候选状态；失败时恢复最后一次持久化状态。"""
        result = self.save_candidate(self._config)
        if not result.ok:
            self._config = getattr(
                self,
                "_persisted_config",
                self.defaults,
            ).copy()
            print(f"[ConfigManager] 保存配置失败 ({result.stage}): {result.message}")
        return result

    def load(self) -> None:
        """从 JSON 文件加载配置"""
        if not self.config_path.exists():
            # 文件不存在，使用默认值
            self._config = self.defaults.copy()
            self._persisted_config = self._config.copy()
            return

        try:
            with open(self.config_path, encoding="utf-8-sig") as f:
                loaded = json.load(f)
                if not isinstance(loaded, dict):
                    raise ValueError("配置根节点必须是对象")
                self._config = {
                    key: loaded.get(key, default)
                    for key, default in self.defaults.items()
                }
                self._persisted_config = self._config.copy()
        except (json.JSONDecodeError, Exception) as e:
            print(f"[ConfigManager] 加载配置失败，使用默认值: {e}")
            self._config = self.defaults.copy()
            self._persisted_config = self._config.copy()

    def reset(self) -> ConfigSaveResult:
        """恢复默认配置"""
        return self.save_candidate(self.defaults.copy())

    @staticmethod
    def get_native_resolution() -> tuple[int, int]:
        """获取主显示器的原生分辨率

        使用 Win32 API GetSystemMetrics 获取主显示器分辨率。

        Returns:
            (width, height) 主显示器分辨率
        """
        user32 = ctypes.windll.user32
        width = user32.GetSystemMetrics(0)   # SM_CXSCREEN
        height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        return (width, height)
