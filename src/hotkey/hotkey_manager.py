"""
全局快捷键模块

注册和监听全局键盘快捷键。
"""

import keyboard


class HotkeyManager:
    """快捷键管理器"""

    def __init__(self):
        self._registered = {}  # {快捷键字符串: 回调函数}

    @staticmethod
    def parse_shortcut(shortcut: str) -> list:
        """
        解析快捷键字符串

        Args:
            shortcut: 格式如 "Ctrl+Shift+R"

        Returns:
            列表形式，如 ['ctrl', 'shift', 'r']
        """
        parts = shortcut.split("+")
        result = []
        for part in parts:
            p = part.strip().lower()
            # 修正修饰键名称
            if p == "ctrl":
                result.append("ctrl")
            elif p == "shift":
                result.append("shift")
            elif p == "alt":
                result.append("alt")
            else:
                result.append(p)
        return result

    @staticmethod
    def _normalize(shortcut: str) -> str:
        """将快捷键字符串统一为小写格式"""
        parts = shortcut.split("+")
        return "+".join(p.strip().lower() for p in parts)

    def register(self, shortcut: str, callback) -> bool:
        """
        注册快捷键

        Args:
            shortcut: 快捷键字符串，如 "Ctrl+Shift+R"
            callback: 回调函数

        Returns:
            True 注册成功, False 注册失败或已存在
        """
        key = self._normalize(shortcut)
        if key in self._registered:
            return False

        try:
            keyboard.add_hotkey(shortcut, callback, suppress=False)
            self._registered[key] = callback
            return True
        except Exception:
            return False

    def unregister(self, shortcut: str) -> bool:
        """
        取消注册快捷键

        Args:
            shortcut: 快捷键字符串

        Returns:
            True 取消成功, False 快捷键未注册
        """
        key = self._normalize(shortcut)
        if key not in self._registered:
            return False

        try:
            keyboard.remove_hotkey(shortcut)
            del self._registered[key]
            return True
        except Exception:
            return False

    def unregister_all(self):
        """取消所有已注册的快捷键"""
        for shortcut in list(self._registered.keys()):
            self.unregister(shortcut)

    def start_listening(self):
        """开始监听（keyboard 库自动监听）"""
        pass

    def stop_listening(self):
        """停止监听，取消所有快捷键"""
        self.unregister_all()