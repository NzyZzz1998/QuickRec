"""
全局快捷键模块

使用 pynput 监听全局键盘快捷键。
pynput 不需要管理员权限即可监听全局按键。
"""

from pynput import keyboard


class HotkeyManager:
    """快捷键管理器（基于 pynput）"""

    def __init__(self):
        self._registered = {}  # {快捷键规范化字符串: 回调函数}
        self._parsed = {}      # {规范化字符串: frozenset(pynput Key/KeyCombo)}
        self._listener = None
        self._current_keys = set()
        self._started = False

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

    def _parse_to_pynput(self, shortcut: str) -> set:
        """将快捷键字符串转为 pynput 键集合"""
        parts = self.parse_shortcut(shortcut)
        key_set = set()
        for part in parts:
            if part == "ctrl":
                key_set.add(keyboard.Key.ctrl_l)
                key_set.add(keyboard.Key.ctrl_r)
            elif part == "shift":
                key_set.add(keyboard.Key.shift_l)
                key_set.add(keyboard.Key.shift_r)
            elif part == "alt":
                key_set.add(keyboard.Key.alt_l)
                key_set.add(keyboard.Key.alt_r)
            elif len(part) == 1:
                key_set.add(keyboard.KeyCode.from_char(part))
            else:
                # 功能键映射
                key_map = {
                    "space": keyboard.Key.space,
                    "enter": keyboard.Key.enter,
                    "tab": keyboard.Key.tab,
                    "esc": keyboard.Key.esc,
                }
                if part in key_map:
                    key_set.add(key_map[part])
        return key_set

    def _match_hotkey(self, key) -> list:
        """检查当前按下的键是否匹配某个快捷键"""
        # 将 pynput key 加入当前按键集合
        self._current_keys.add(key)

        matched = []
        for norm_key, callback in self._registered.items():
            parsed = self._parsed.get(norm_key)
            if parsed is None:
                continue
            # 检查所有解析出的键是否都被按下
            if self._keys_match(parsed):
                matched.append(callback)

        return matched

    def _keys_match(self, parsed_keys: set) -> bool:
        """检查当前按键是否匹配解析的键集合

        对于 ctrl/shift/alt 修饰键，左右键都会加入 parsed_keys，
        只要当前按键集合包含其中之一即可。
        """
        # 将 current_keys 按普通键和修饰键分组
        required_normal = set()
        required_modifiers = {}  # {修饰键类型: {左键, 右键}}

        for k in parsed_keys:
            if k in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                required_modifiers.setdefault("ctrl", set()).add(k)
            elif k in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                required_modifiers.setdefault("shift", set()).add(k)
            elif k in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                required_modifiers.setdefault("alt", set()).add(k)
            else:
                required_normal.add(k)

        # 检查修饰键：当前按键集合中须包含左右之一
        for mod_type, keys in required_modifiers.items():
            if not self._current_keys.intersection(keys):
                return False

        # 检查普通键：须全部在当前按键集合中
        # 需排除修饰键的匹配
        current_without_mods = self._current_keys.copy()
        for keys in required_modifiers.values():
            current_without_mods -= keys

        for k in required_normal:
            if k not in current_without_mods:
                return False

        return True

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

        parsed = self._parse_to_pynput(shortcut)
        self._parsed[key] = parsed
        self._registered[key] = callback

        # 如果监听器已经在运行，需要重启以应用新快捷键
        if self._started:
            self.stop_listening()
            self.start_listening()

        return True

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

        del self._registered[key]
        del self._parsed[key]

        if self._started:
            self.stop_listening()
            self.start_listening()

        return True

    def unregister_all(self):
        """取消所有已注册的快捷键"""
        self._registered.clear()
        self._parsed.clear()
        self.stop_listening()

    def _on_press(self, key):
        """按键按下回调"""
        matched = self._match_hotkey(key)
        for callback in matched:
            try:
                callback()
            except Exception:
                pass

    def _on_release(self, key):
        """按键释放回调"""
        self._current_keys.discard(key)

    def start_listening(self):
        """开始监听全局按键"""
        if self._started:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self._listener.start()
        self._started = True

    def stop_listening(self):
        """停止监听"""
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._started = False
        self._current_keys.clear()