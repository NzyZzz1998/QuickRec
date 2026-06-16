"""
全局快捷键模块

使用 pynput 监听全局键盘快捷键。
pynput 不需要管理员权限即可监听全局按键。

采用字符串标识符进行键匹配，比直接比较 pynput Key/KeyCode 对象更可靠。
原因：pynput 在修饰键按下时报告的 KeyCode 与解析时创建的不同
（例如 Ctrl+Shift+R 按下时 char 可能为 None 或控制字符），
导致直接使用 KeyCode.__eq__ 比较永远不匹配。
"""

import logging

from pynput import keyboard

logger = logging.getLogger("QuickRec")

# Windows 虚拟键码到字符串标识符的映射
_VK_MAP = {}
for _vk, _ch in zip(range(0x41, 0x5B), 'abcdefghijklmnopqrstuvwxyz'):
    _VK_MAP[_vk] = _ch
for _vk in range(0x30, 0x3A):
    _VK_MAP[_vk] = str(_vk - 0x30)
_VK_MAP[0x20] = 'space'
_VK_MAP[0x0D] = 'enter'
_VK_MAP[0x09] = 'tab'
_VK_MAP[0x1B] = 'esc'


class HotkeyManager:
    """快捷键管理器（基于 pynput）"""

    def __init__(self):
        self._registered = {}  # {快捷键规范化字符串: 回调函数}
        self._parsed = {}      # {规范化字符串: frozenset(键标识符)}
        self._listener = None
        self._current_keys = set()  # 当前按下的键标识符集合
        self._started = False
        self._triggered = set()     # 已触发的快捷键（防按键按住时重复触发）
        self._on_esc = None         # ESC 单键全局回调

    @staticmethod
    def parse_shortcut(shortcut: str) -> list:
        """解析快捷键字符串为标识符列表"""
        parts = shortcut.split("+")
        result = []
        for part in parts:
            p = part.strip().lower()
            if p in ("ctrl", "shift", "alt"):
                result.append(p)
            else:
                result.append(p)
        return result

    @staticmethod
    def _normalize(shortcut: str) -> str:
        """将快捷键字符串统一为小写格式"""
        parts = shortcut.split("+")
        return "+".join(p.strip().lower() for p in parts)

    def _key_to_id(self, key) -> str:
        """将 pynput 键对象转换为标准化字符串标识符

        解决 pynput 在修饰键按下时 KeyCode 与 from_char 创建的对象不一致的问题：
        直接比较 Key/KeyCode 对象在 Ctrl/Shift 等修饰键按下时会失败，
        因为 pynput 报告的 KeyCode.char 可能为 None 或控制字符。
        通过将所有键统一为字符串标识符，用集合交集匹配，彻底避免此问题。
        """
        # 修饰键 → 统一字符串
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return 'ctrl'
        if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            return 'shift'
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            return 'alt'

        # KeyCode 对象
        if isinstance(key, keyboard.KeyCode):
            # 优先用字符属性（字母不区分大小写）
            char = getattr(key, 'char', None)
            if char and len(char) == 1 and char.isalpha():
                return char.lower()
            # 回退到虚拟键码映射
            vk = getattr(key, 'vk', None)
            if vk is not None and vk in _VK_MAP:
                return _VK_MAP[vk]

        # 特殊键
        if key == keyboard.Key.space:
            return 'space'
        if key == keyboard.Key.enter:
            return 'enter'
        if key == keyboard.Key.tab:
            return 'tab'
        if key == keyboard.Key.esc:
            return 'esc'

        # 尝试 vk 映射（兜底）
        vk = getattr(key, 'vk', None)
        if vk is not None and vk in _VK_MAP:
            return _VK_MAP[vk]

        return None

    def register(self, shortcut: str, callback) -> bool:
        """注册快捷键"""
        key = self._normalize(shortcut)
        if key in self._registered:
            logger.debug(f"快捷键 {key} 已注册，跳过重复注册")
            return False
        parsed = frozenset(self.parse_shortcut(shortcut))
        self._parsed[key] = parsed
        self._registered[key] = callback
        return True

    def set_esc_callback(self, callback):
        """设置 ESC 单键全局回调（用于倒计时取消等场景）

        与组合键快捷键不同，ESC 是单键监听，无需修饰键。
        设为 None 可禁用。
        """
        self._on_esc = callback

    def unregister(self, shortcut: str) -> bool:
        """取消注册快捷键"""
        key = self._normalize(shortcut)
        if key not in self._registered:
            return False
        del self._registered[key]
        del self._parsed[key]
        return True

    def unregister_all(self):
        """取消所有已注册的快捷键"""
        self._registered.clear()
        self._parsed.clear()
        self.stop_listening()

    def _on_press(self, key):
        """按键按下回调"""
        key_id = self._key_to_id(key)
        if key_id is None:
            return

        # ESC 单键回调（倒计时取消等）
        if key_id == 'esc' and self._on_esc:
            try:
                self._on_esc()
            except Exception as e:
                logger.error(f"ESC 回调异常: {e}")

        self._current_keys.add(key_id)
        logger.debug(f"按键按下: {key_id}, 当前按键集合: {self._current_keys}")

        # 精确匹配：当前按键集合必须完全等于注册的组合键
        for norm_key, parsed in self._parsed.items():
            if parsed == self._current_keys and norm_key not in self._triggered:
                self._triggered.add(norm_key)
                logger.info(f"快捷键触发: {norm_key}")
                callback = self._registered.get(norm_key)
                if callback:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"快捷键回调异常: {e}")

    def _on_release(self, key):
        """按键释放回调"""
        key_id = self._key_to_id(key)
        if key_id is None:
            return
        self._current_keys.discard(key_id)
        logger.debug(f"按键释放: {key_id}, 当前按键集合: {self._current_keys}")
        # 组合键中任一键释放，清除对应触发标记
        self._triggered = {
            k for k in self._triggered
            if key_id not in self._parsed.get(k, frozenset())
        }

    def start_listening(self):
        """开始监听全局按键"""
        if self._started:
            return
        self._current_keys.clear()
        self._triggered.clear()
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
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
        self._triggered.clear()