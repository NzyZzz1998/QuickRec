"""
HotkeyManager 单元测试
"""

import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotkey.hotkey_manager import HotkeyManager


class TestHotkeyManager(unittest.TestCase):
    """HotkeyManager 测试类"""

    def test_parse_shortcut_ctrl_shift_r(self):
        """测试解析 Ctrl+Shift+R"""
        result = HotkeyManager.parse_shortcut("Ctrl+Shift+R")
        self.assertEqual(result, ["ctrl", "shift", "r"])

    def test_parse_shortcut_ctrl_alt_s(self):
        """测试解析 Ctrl+Alt+S"""
        result = HotkeyManager.parse_shortcut("Ctrl+Alt+S")
        self.assertEqual(result, ["ctrl", "alt", "s"])

    def test_parse_shortcut_case_insensitive(self):
        """测试解析不区分大小写"""
        result = HotkeyManager.parse_shortcut("ctrl+shift+p")
        self.assertEqual(result, ["ctrl", "shift", "p"])

    def test_parse_shortcut_with_spaces(self):
        """测试解析带空格"""
        result = HotkeyManager.parse_shortcut("Ctrl + Shift + F5")
        self.assertEqual(result, ["ctrl", "shift", "f5"])

    def test_register_duplicate_returns_false(self):
        """测试重复注册返回 False"""
        manager = HotkeyManager()
        # 模拟已注册
        manager._registered["ctrl+shift+r"] = lambda: None
        result = manager.register("Ctrl+Shift+R", lambda: None)
        self.assertFalse(result)

    def test_unregister_not_registered_returns_false(self):
        """测试取消未注册的快捷键返回 False"""
        manager = HotkeyManager()
        result = manager.unregister("Ctrl+Shift+R")
        self.assertFalse(result)

    def test_initial_state_empty(self):
        """测试初始状态为空"""
        manager = HotkeyManager()
        self.assertEqual(len(manager._registered), 0)


if __name__ == "__main__":
    unittest.main()