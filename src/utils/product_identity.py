"""QuickRec Lite 的运行身份与默认路径。"""

from __future__ import annotations

from pathlib import Path

PRODUCT_ID = "QuickRec.Lite"
DISPLAY_NAME = "QuickRec Lite"
EXECUTABLE_NAME = "QuickRec-Lite.exe"
PACKAGE_DIR_NAME = "QuickRec-Lite"
CONFIG_DIR_NAME = "QuickRec-Lite"
TEMP_DIR_NAME = "QuickRec-Lite"
AUTOSTART_NAME = "QuickRec Lite"
NOTIFICATION_APP_ID = "QuickRec.Lite"


def lite_appdata_dir(appdata_root: Path) -> Path:
    """返回 Lite 独立配置目录。"""
    return Path(appdata_root) / CONFIG_DIR_NAME


def lite_temp_dir(temp_root: Path) -> Path:
    """返回 Lite 独立临时目录。"""
    return Path(temp_root) / TEMP_DIR_NAME


def default_save_path(home: Path) -> Path:
    """返回首次安装时的默认视频保存目录。"""
    return Path(home) / "Videos" / DISPLAY_NAME
