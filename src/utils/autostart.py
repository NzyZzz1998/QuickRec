"""
开机自启模块

管理 QuickRec 开机自启注册表项，操作 HKEY_CURRENT_USER\\Run。
无需管理员权限。
"""

import logging
import os
import sys
import winreg

logger = logging.getLogger(__name__)

AUTO_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTO_RUN_NAME = "QuickRec"


def is_autostart_enabled() -> bool:
    """检查开机自启是否已开启

    读取 HKCU\\Run 中 QuickReg 项的值，
    与当前可执行文件路径比较（不区分大小写）。

    Returns:
        True 如果已开启且路径匹配
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTO_RUN_KEY, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, AUTO_RUN_NAME)
        winreg.CloseKey(key)
        return os.path.normcase(value) == os.path.normcase(_get_executable_path())
    except FileNotFoundError:
        return False
    except Exception:
        return False


def enable_autostart() -> bool:
    """开启开机自启

    写入 HKEY_CURRENT_USER\\Run 注册表项。
    无需管理员权限。

    Returns:
        True 如果成功写入
    """
    try:
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, AUTO_RUN_KEY, 0, winreg.KEY_SET_VALUE)
        exe_path = _get_executable_path()
        winreg.SetValueEx(key, AUTO_RUN_NAME, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        logger.info(f"开机自启已开启: {exe_path}")
        return True
    except Exception as e:
        logger.error(f"开启开机自启失败: {e}")
        return False


def disable_autostart() -> bool:
    """关闭开机自启

    删除 HKEY_CURRENT_USER\\Run 中的 QuickRec 项。

    Returns:
        True 如果成功删除或项已不存在
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTO_RUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, AUTO_RUN_NAME)
        winreg.CloseKey(key)
        logger.info("开机自启已关闭")
        return True
    except FileNotFoundError:
        return True  # 已经不存在
    except Exception as e:
        logger.error(f"关闭开机自启失败: {e}")
        return False


def _get_executable_path() -> str:
    """获取当前可执行文件路径

    打包后返回 exe 路径，开发环境返回 python 解释器路径。
    开机自启仅在打包后生效。
    """
    return sys.executable
