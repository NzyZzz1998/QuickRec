"""
HotkeyManager 单元测试
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pynput import keyboard

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

    def test_register_stores_normalized_shortcut_and_parsed_keys(self):
        manager = HotkeyManager()

        self.assertTrue(manager.register(" Ctrl + Shift + R ", lambda: None))

        self.assertIn("ctrl+shift+r", manager._registered)
        self.assertEqual(manager._parsed["ctrl+shift+r"], frozenset({"ctrl", "shift", "r"}))

    def test_unregister_registered_shortcut_removes_callback(self):
        manager = HotkeyManager()
        manager.register("Ctrl+Shift+R", lambda: None)

        self.assertTrue(manager.unregister("ctrl+shift+r"))

        self.assertNotIn("ctrl+shift+r", manager._registered)
        self.assertNotIn("ctrl+shift+r", manager._parsed)

    def test_unregister_all_clears_registered_shortcuts_and_state(self):
        manager = HotkeyManager()
        manager.register("Ctrl+Shift+R", lambda: None)
        manager._current_keys.add("ctrl")
        manager._triggered.add("ctrl+shift+r")

        manager.unregister_all()

        self.assertEqual(manager._registered, {})
        self.assertEqual(manager._parsed, {})
        self.assertEqual(manager._current_keys, set())
        self.assertEqual(manager._triggered, set())

    def test_key_to_id_handles_modifiers_letters_and_special_keys(self):
        manager = HotkeyManager()

        self.assertEqual(manager._key_to_id(keyboard.Key.ctrl_l), "ctrl")
        self.assertEqual(manager._key_to_id(keyboard.Key.shift_r), "shift")
        self.assertEqual(manager._key_to_id(keyboard.Key.alt_l), "alt")
        self.assertEqual(manager._key_to_id(keyboard.KeyCode.from_char("R")), "r")
        self.assertEqual(manager._key_to_id(keyboard.Key.space), "space")
        self.assertEqual(manager._key_to_id(keyboard.Key.enter), "enter")
        self.assertEqual(manager._key_to_id(keyboard.Key.tab), "tab")
        self.assertEqual(manager._key_to_id(keyboard.Key.esc), "esc")

    def test_key_to_id_falls_back_to_virtual_key_map(self):
        manager = HotkeyManager()
        key = keyboard.KeyCode.from_vk(0x41)

        self.assertEqual(manager._key_to_id(key), "a")

    def test_on_press_triggers_exact_shortcut_once_until_release(self):
        manager = HotkeyManager()
        calls = []
        manager.register("Ctrl+Shift+R", lambda: calls.append("record"))

        manager._on_press(keyboard.Key.ctrl_l)
        manager._on_press(keyboard.Key.shift_l)
        manager._on_press(keyboard.KeyCode.from_char("r"))
        manager._on_press(keyboard.KeyCode.from_char("r"))

        self.assertEqual(calls, ["record"])
        self.assertIn("ctrl+shift+r", manager._triggered)

        manager._on_release(keyboard.KeyCode.from_char("r"))
        manager._on_press(keyboard.KeyCode.from_char("r"))

        self.assertEqual(calls, ["record", "record"])

    def test_on_press_ignores_non_exact_shortcut(self):
        manager = HotkeyManager()
        calls = []
        manager.register("Ctrl+Shift+R", lambda: calls.append("record"))

        manager._on_press(keyboard.Key.ctrl_l)
        manager._on_press(keyboard.Key.shift_l)
        manager._on_press(keyboard.Key.alt_l)
        manager._on_press(keyboard.KeyCode.from_char("r"))

        self.assertEqual(calls, [])

    def test_esc_callback_is_called_and_can_be_disabled(self):
        manager = HotkeyManager()
        calls = []
        manager.set_esc_callback(lambda: calls.append("esc"))

        manager._on_press(keyboard.Key.esc)
        manager.set_esc_callback(None)
        manager._on_press(keyboard.Key.esc)

        self.assertEqual(calls, ["esc"])

    def test_start_and_stop_listening_manage_listener_lifecycle(self):
        class FakeListener:
            started = False
            stopped = False

            def __init__(self, on_press, on_release):
                self.on_press = on_press
                self.on_release = on_release

            def start(self):
                self.started = True

            def stop(self):
                self.stopped = True

        manager = HotkeyManager()
        original_listener = keyboard.Listener
        keyboard.Listener = FakeListener
        try:
            manager.start_listening()
            listener = manager._listener
            manager.start_listening()
            manager.stop_listening()
        finally:
            keyboard.Listener = original_listener

        self.assertTrue(listener.started)
        self.assertTrue(listener.stopped)
        self.assertFalse(manager._started)


if __name__ == "__main__":
    unittest.main()
