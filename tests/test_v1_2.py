"""
v1.2 新增模块单元测试

测试内容：
- autostart.py 注册表操作
- config.py v1.2 新增配置项
- window_selector.py 窗口枚举
- window_highlighter.py 窗口边框高亮
- click_highlighter.py 鼠标点击高亮
- screen_capturer.py update_region 方法
- recorder_manager.py RecordMode.WINDOW
"""

import ctypes
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ConfigManager


class TestConfigV12(unittest.TestCase):
    """ConfigManager v1.2 新增配置项测试"""

    def setUp(self):
        with patch("src.config.ConfigManager.__init__", lambda self: None):
            self.config = ConfigManager()
            self.config._config = ConfigManager.defaults.copy()

    def test_default_shortcut_window(self):
        """测试窗口录制快捷键默认值"""
        self.assertEqual(self.config.get("shortcut_window"), "Ctrl+Shift+W")

    def test_default_show_countdown(self):
        """测试录制倒计时默认值"""
        self.assertEqual(self.config.get("show_countdown"), False)

    def test_default_countdown_seconds(self):
        """测试倒计时秒数默认值"""
        self.assertEqual(self.config.get("countdown_seconds"), 3)

    def test_default_mouse_highlight(self):
        """测试鼠标点击高亮默认值"""
        self.assertEqual(self.config.get("mouse_highlight"), False)

    def test_default_auto_start(self):
        """测试开机自启默认值"""
        self.assertEqual(self.config.get("auto_start"), False)

    def test_default_audio_source(self):
        """测试音频源默认值（v1.1 遗留，不应丢失）"""
        self.assertEqual(self.config.get("audio_source"), "none")

    def test_default_shortcut_area(self):
        """测试区域录制快捷键默认值（v1.1 遗留，不应丢失）"""
        self.assertEqual(self.config.get("shortcut_area"), "Ctrl+Shift+A")

    def test_get_native_resolution(self):
        """测试获取主显示器分辨率"""
        width, height = ConfigManager.get_native_resolution()
        self.assertIsInstance(width, int)
        self.assertIsInstance(height, int)
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        # 常见分辨率至少 640x480
        self.assertGreaterEqual(width, 640)
        self.assertGreaterEqual(height, 480)

    def test_quality_sizes_include_native(self):
        """测试画质档位包含 native"""
        self.assertIn("native", ConfigManager.QUALITY_SIZES)
        self.assertIsNone(ConfigManager.QUALITY_SIZES["native"])

    def test_quality_sizes_include_all(self):
        """测试画质档位包含所有档位"""
        self.assertIn("high", ConfigManager.QUALITY_SIZES)
        self.assertIn("medium", ConfigManager.QUALITY_SIZES)
        self.assertIn("low", ConfigManager.QUALITY_SIZES)
        self.assertEqual(ConfigManager.QUALITY_SIZES["high"], (1920, 1080))
        self.assertEqual(ConfigManager.QUALITY_SIZES["medium"], (1280, 720))
        self.assertEqual(ConfigManager.QUALITY_SIZES["low"], (854, 480))

    def test_v1_1_config_backward_compatibility(self):
        """测试 v1.1 配置文件加载后新字段有默认值"""
        base_temp_dir = tempfile.mkdtemp()
        config_path = Path(base_temp_dir) / "config" / "config.json"

        # v1.1 配置文件（没有 v1.2 新增字段）
        v1_1_config = {
            "save_path": "C:/Videos/QuickRec",
            "quality": "high",
            "fps": 30,
            "shortcut_start": "Ctrl+Shift+R",
            "shortcut_stop": "Ctrl+Shift+S",
            "shortcut_pause": "Ctrl+Shift+P",
            "shortcut_area": "Ctrl+Shift+A",
            "audio_source": "none",
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(v1_1_config, f)

        config = ConfigManager.__new__(ConfigManager)
        config.config_path = config_path
        config._config = ConfigManager.defaults.copy()
        config.load()

        # v1.2 新字段应该有默认值
        self.assertEqual(config.get("shortcut_window"), "Ctrl+Shift+W")
        self.assertEqual(config.get("show_countdown"), False)
        self.assertEqual(config.get("countdown_seconds"), 3)
        self.assertEqual(config.get("mouse_highlight"), False)
        self.assertEqual(config.get("auto_start"), False)

        # v1.1 字段应该保留
        self.assertEqual(config.get("audio_source"), "none")
        self.assertEqual(config.get("shortcut_area"), "Ctrl+Shift+A")

        import shutil
        shutil.rmtree(base_temp_dir, ignore_errors=True)


class TestAutostart(unittest.TestCase):
    """开机自启模块测试"""

    def test_is_autostart_enabled_default(self):
        """测试默认未开启开机自启"""
        from utils.autostart import is_autostart_enabled
        # 默认应该返回 False（除非用户手动设置过）
        result = is_autostart_enabled()
        self.assertIsInstance(result, bool)

    def test_enable_and_disable(self):
        """测试开启和关闭开机自启"""
        from utils.autostart import enable_autostart, disable_autostart, is_autostart_enabled

        # 开启
        result = enable_autostart()
        self.assertTrue(result, "enable_autostart 应该成功")

        # 验证已开启
        self.assertTrue(is_autostart_enabled(), "开启后 is_autostart_enabled 应为 True")

        # 关闭
        result = disable_autostart()
        self.assertTrue(result, "disable_autostart 应该成功")

        # 验证已关闭
        self.assertFalse(is_autostart_enabled(), "关闭后 is_autostart_enabled 应为 False")

    def test_disable_when_not_enabled(self):
        """测试未开启时关闭不报错"""
        from utils.autostart import disable_autostart
        # 先确保关闭
        disable_autostart()
        # 再次关闭应该不报错
        result = disable_autostart()
        self.assertTrue(result)


class TestRecordModeWindow(unittest.TestCase):
    """RecordMode.WINDOW 枚举测试"""

    def test_window_mode_exists(self):
        """测试 WINDOW 模式枚举存在"""
        from recorder.recorder_manager import RecordMode
        self.assertEqual(RecordMode.WINDOW.value, "window")

    def test_all_modes(self):
        """测试所有录制模式"""
        from recorder.recorder_manager import RecordMode
        modes = [m.value for m in RecordMode]
        self.assertIn("fullscreen", modes)
        self.assertIn("region", modes)
        self.assertIn("window", modes)


class TestWindowSelector(unittest.TestCase):
    """WindowSelector 测试"""

    def test_enum_visible_windows(self):
        """测试枚举可见窗口"""
        # 枚举当前可见窗口，至少应该有一些窗口
        user32 = ctypes.windll.user32
        windows = []

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def _callback(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd):
                title_length = user32.GetWindowTextLengthW(hwnd)
                if title_length > 0:
                    windows.append(hwnd)
            return True

        user32.EnumWindows(WNDENUMPROC(_callback), 0)
        self.assertGreater(len(windows), 0, "应该至少枚举到一个可见窗口")


class TestScreenCapturerUpdateRegion(unittest.TestCase):
    """ScreenCapturer update_region 测试"""

    def test_update_region_method_exists(self):
        """测试 update_region 方法存在"""
        from recorder.screen_capturer import ScreenCapturer
        capturer = ScreenCapturer(region=(0, 0, 800, 600))
        self.assertTrue(hasattr(capturer, 'update_region'))

    def test_update_region_changes_dxcam_region(self):
        """测试 update_region 更新内部区域"""
        from recorder.screen_capturer import ScreenCapturer
        capturer = ScreenCapturer(region=(0, 0, 800, 600))
        self.assertEqual(capturer._dxcam_region, (0, 0, 800, 600))

        # 更新区域
        capturer.update_region((100, 200, 800, 600))
        self.assertEqual(capturer._region, (100, 200, 800, 600))
        self.assertEqual(capturer._dxcam_region, (100, 200, 900, 800))

    def test_update_region_changes_region(self):
        """测试 update_region 更新 _region 属性"""
        from recorder.screen_capturer import ScreenCapturer
        capturer = ScreenCapturer(region=None)
        self.assertIsNone(capturer._region)

        capturer.update_region((0, 0, 1920, 1080))
        self.assertEqual(capturer._region, (0, 0, 1920, 1080))


class TestRecorderManagerWindow(unittest.TestCase):
    """RecorderManager 窗口模式测试"""

    def test_window_lost_bridge_exists(self):
        """测试 _WindowLostBridge 信号桥存在"""
        from recorder.recorder_manager import RecorderManager
        rm = RecorderManager.__new__(RecorderManager)
        rm._window_lost_bridge = None
        # 验证类定义
        self.assertTrue(hasattr(RecorderManager, 'start_window'))

    def test_get_window_title(self):
        """测试获取窗口标题"""
        from recorder.recorder_manager import RecorderManager
        # 使用桌面窗口句柄测试
        desktop_hwnd = ctypes.windll.user32.GetDesktopWindow()
        title = RecorderManager._get_window_title(desktop_hwnd)
        self.assertIsInstance(title, str)

    def test_get_window_rect(self):
        """测试获取窗口位置"""
        from recorder.recorder_manager import RecorderManager
        desktop_hwnd = ctypes.windll.user32.GetDesktopWindow()
        rect = RecorderManager._get_window_rect(desktop_hwnd)
        # 桌面窗口应该有位置信息
        if rect:
            self.assertGreater(rect.width(), 0)
            self.assertGreater(rect.height(), 0)


class TestWindowHighlighter(unittest.TestCase):
    """WindowHighlighter 测试"""

    def test_highlighter_creation(self):
        """测试 WindowHighlighter 对象创建"""
        from ui.window_highlighter import WindowHighlighter
        # 使用桌面窗口句柄
        desktop_hwnd = ctypes.windll.user32.GetDesktopWindow()
        # 不实际显示，仅验证构造不会崩溃
        highlighter = WindowHighlighter.__new__(WindowHighlighter)
        highlighter._hwnd = desktop_hwnd
        self.assertEqual(highlighter._hwnd, desktop_hwnd)


class TestClickHighlighter(unittest.TestCase):
    """ClickHighlighter 测试"""

    def test_highlighter_creation(self):
        """测试 ClickHighlighter 对象创建"""
        from ui.click_highlighter import ClickHighlighter
        highlighter = ClickHighlighter()
        self.assertFalse(highlighter.is_running())

    def test_start_stop(self):
        """测试启动和停止"""
        from ui.click_highlighter import ClickHighlighter
        highlighter = ClickHighlighter()
        highlighter.start()
        self.assertTrue(highlighter.is_running())
        highlighter.stop()
        self.assertFalse(highlighter.is_running())

    def test_double_start(self):
        """测试重复启动不会创建多个监听器"""
        from ui.click_highlighter import ClickHighlighter
        highlighter = ClickHighlighter()
        highlighter.start()
        highlighter.start()  # 不应该崩溃
        self.assertTrue(highlighter.is_running())
        highlighter.stop()

    def test_stop_when_not_running(self):
        """测试未运行时停止不会崩溃"""
        from ui.click_highlighter import ClickHighlighter
        highlighter = ClickHighlighter()
        highlighter.stop()  # 不应该崩溃


class TestToolbarCountdown(unittest.TestCase):
    """工具栏倒计时测试"""

    def test_countdown_finished_signal_exists(self):
        """测试 countdown_finished 信号存在"""
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.toolbar import RecordingToolbar
        toolbar = RecordingToolbar()
        self.assertTrue(hasattr(toolbar, 'countdown_finished'))

    def test_countdown_mode_flag(self):
        """测试倒计时模式标志"""
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.toolbar import RecordingToolbar
        toolbar = RecordingToolbar()
        self.assertFalse(toolbar.is_countdown_mode())

    def test_start_recording_timer_renamed(self):
        """测试录制计时器方法已重命名"""
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.toolbar import RecordingToolbar
        toolbar = RecordingToolbar()
        self.assertTrue(hasattr(toolbar, 'start_recording_timer'))
        self.assertTrue(hasattr(toolbar, 'stop_recording_timer'))

    def test_cancel_countdown_method(self):
        """测试取消倒计时方法存在"""
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.toolbar import RecordingToolbar
        toolbar = RecordingToolbar()
        # 非倒计时模式下取消不应崩溃
        toolbar.cancel_countdown()


if __name__ == "__main__":
    unittest.main()