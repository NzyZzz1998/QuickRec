"""
配置管理模块

管理 QuickRec 的用户配置，包括读写和持久化。
配置文件存储在 AppData/Roaming/QuickRec/config.json
"""

import ctypes
import json
import os
from pathlib import Path
from typing import Any


class ConfigManager:
    """配置管理器"""

    # 默认配置值
    defaults = {
        "save_path": str(Path.home() / "Videos" / "QuickRec"),
        "quality": "high",  # native / high / medium / low
        "fps": 30,  # 30 / 60
        "shortcut_start": "Ctrl+Shift+R",
        "shortcut_stop": "Ctrl+Shift+S",
        "shortcut_pause": "Ctrl+Shift+P",
        "shortcut_area": "Ctrl+Shift+A",
        "shortcut_window": "Ctrl+Shift+W",
        "show_countdown": False,
        "countdown_seconds": 3,
        "audio_source": "none",  # none / system / microphone / both
        "mouse_highlight": False,
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
        self.config_path = Path(appdata) / "QuickRec" / "config.json"
        self._config = self.defaults.copy()
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

    def save(self) -> None:
        """将配置持久化到 JSON 文件"""
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ConfigManager] 保存配置失败: {e}")

    def load(self) -> None:
        """从 JSON 文件加载配置"""
        if not self.config_path.exists():
            # 文件不存在，使用默认值
            self._config = self.defaults.copy()
            return

        try:
            with open(self.config_path, encoding="utf-8") as f:
                loaded = json.load(f)
                # 合并加载的配置和默认配置
                self._config = {**self.defaults, **loaded}
        except (json.JSONDecodeError, Exception) as e:
            print(f"[ConfigManager] 加载配置失败，使用默认值: {e}")
            self._config = self.defaults.copy()

    def reset(self) -> None:
        """恢复默认配置"""
        self._config = self.defaults.copy()
        self.save()

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
