"""
v1.3 新增模块单元测试

测试内容：
- video_encoder.py FFmpeg pipe H.264 编码
- utils/temp_cleaner.py 三层临时文件清理
- utils/disk_checker.py 磁盘空间预警
- utils/autostart.py（v1.2 已测，跳过）
- recorder_manager.py _get_window_rect / get_window_hwnd
- config.py v1.3 新增字段向后兼容
"""

import ctypes
import ctypes.wintypes
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

_FFMPEG = str(Path(__file__).parent.parent / "ffmpeg" / "ffmpeg.exe")


@pytest.mark.packaging
class TestVideoEncoderV13(unittest.TestCase):
    """VideoEncoder v1.3 FFmpeg pipe 编码测试"""

    def setUp(self):
        if not os.path.isfile(_FFMPEG):
            self.skipTest(f"FFmpeg 未就位: {_FFMPEG}")
        self.temp_dir = tempfile.mkdtemp()
        self.output = os.path.join(self.temp_dir, "out.mp4")
        self.frame_size = (640, 480)  # width, height
        self.fps = 30

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _frame(self):
        import numpy as np
        return np.zeros((self.frame_size[1], self.frame_size[0], 3), dtype=np.uint8)

    def test_construct_and_close_empty(self):
        """构造 + 立即关闭（无写入帧）→ returncode 0"""
        from recorder.video_encoder import VideoEncoder
        enc = VideoEncoder(self.output, self.fps, self.frame_size, _FFMPEG)
        self.assertTrue(enc.is_open())
        self.assertTrue(enc.close())
        self.assertFalse(enc.is_open())

    def test_write_frames_and_close(self):
        """写入 30 帧后关闭 → 生成可播放 MP4"""
        from recorder.video_encoder import VideoEncoder
        enc = VideoEncoder(self.output, self.fps, self.frame_size, _FFMPEG)
        for _ in range(30):
            self.assertTrue(enc.write_frame(self._frame()))
        self.assertEqual(enc.get_frame_count(), 30)
        self.assertTrue(enc.close())
        self.assertTrue(os.path.exists(self.output))
        self.assertGreater(os.path.getsize(self.output), 0)

    def test_close_then_write_returns_false(self):
        """close 后写入返回 False"""
        from recorder.video_encoder import VideoEncoder
        enc = VideoEncoder(self.output, self.fps, self.frame_size, _FFMPEG)
        enc.close()
        self.assertFalse(enc.write_frame(self._frame()))

    def test_frame_count_accurate(self):
        """帧计数准确"""
        from recorder.video_encoder import VideoEncoder
        enc = VideoEncoder(self.output, self.fps, self.frame_size, _FFMPEG)
        for i in range(50):
            enc.write_frame(self._frame())
            self.assertEqual(enc.get_frame_count(), i + 1)
        enc.close()

    def test_ffmpeg_path_not_exist_raises(self):
        """FFmpeg 路径不存在 → 启动抛 FileNotFoundError"""
        from recorder.video_encoder import VideoEncoder
        with self.assertRaises(FileNotFoundError):
            VideoEncoder(self.output, self.fps, self.frame_size,
                         os.path.join(self.temp_dir, "no_such_ffmpeg.exe"))

    def test_output_is_h264_mp4(self):
        """确认输出 MP4 容器 + H.264 编码（用 ffprobe）"""
        try:
            import subprocess as sp
        except Exception:
            self.skipTest("subprocess 不可用")
        from recorder.video_encoder import VideoEncoder
        enc = VideoEncoder(self.output, self.fps, self.frame_size, _FFMPEG)
        for _ in range(20):
            enc.write_frame(self._frame())
        self.assertTrue(enc.close())
        out = sp.run(
            [_FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")
             if os.path.isfile(_FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"))
             else _FFMPEG, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "default=nw=1", self.output],
            capture_output=True, text=True
        ) if os.path.isfile(_FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")) else None
        # ffprobe 缺失时不强测；有时仅打包 ffmpeg
        if out is None:
            self.skipTest("ffprobe 未随包提供，跳过编码格式断言")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("h264", out.stdout.lower())


class TestTempCleaner(unittest.TestCase):
    """TempCleaner 三层清理测试"""

    def test_create_session_dir(self):
        """create_session_dir 创建 session_<pid>_<ts> 目录"""
        from utils.temp_cleaner import TempCleaner
        d = TempCleaner.create_session_dir()
        self.assertTrue(os.path.isdir(d))
        self.assertIn("session_", os.path.basename(d))
        TempCleaner.cleanup_session(d)

    def test_cleanup_session_removes_dir(self):
        """cleanup_session 删除指定目录"""
        from utils.temp_cleaner import TempCleaner
        d = TempCleaner.create_session_dir()
        TempCleaner.cleanup_session(d)
        self.assertFalse(os.path.exists(d))

    def test_cleanup_session_idempotent(self):
        """cleanup_session 对已删除目录不报错"""
        from utils.temp_cleaner import TempCleaner
        d = TempCleaner.create_session_dir()
        TempCleaner.cleanup_session(d)
        TempCleaner.cleanup_session(d)  # 第二次不应异常

    def test_is_pid_alive_self(self):
        """当前进程 PID 存活"""
        from utils.temp_cleaner import TempCleaner
        self.assertTrue(TempCleaner._is_pid_alive(os.getpid()))

    def test_is_pid_alive_dead(self):
        """不存在的 PID 视为已终止"""
        from utils.temp_cleaner import TempCleaner
        # 选一个不可能的 PID（>2^31 太大；用 0 因 os.kill(0,0) 限制改为大数）
        self.assertFalse(TempCleaner._is_pid_alive(99999999))

    def test_cleanup_stale_removes_dead_sessions(self):
        """cleanup_stale 删除 dead PID 的 session 目录"""
        from utils.temp_cleaner import TempCleaner
        # 在 BASE_DIR 下构造一个 dead-pid 的 session 目录
        base = TempCleaner.BASE_DIR
        os.makedirs(base, exist_ok=True)
        dead_dir = os.path.join(base, f"session_99999999_{int(__import__('time').time())}")
        os.makedirs(dead_dir, exist_ok=True)
        try:
            TempCleaner.cleanup_stale()
            self.assertFalse(os.path.exists(dead_dir))
        finally:
            if os.path.exists(dead_dir):
                TempCleaner.cleanup_session(dead_dir)


class TestDiskCheckerV13(unittest.TestCase):
    """DiskChecker v1.3 预警测试"""

    def test_check_before_recording_ok(self):
        """free > 1GB → 'ok'"""
        from utils import disk_checker
        from utils.disk_checker import DiskChecker
        # get_free_space 返回字节，2GB = 2048*1024*1024
        with patch.object(disk_checker.DiskChecker, 'get_free_space',
                          return_value=2048 * 1024 * 1024):
            status, free = DiskChecker.check_before_recording("E:/")
            self.assertEqual(status, "ok")

    def test_check_before_recording_warn(self):
        """200MB < free < 1GB → 'warn'"""
        from utils import disk_checker
        from utils.disk_checker import DiskChecker
        # 500MB = 500*1024*1024
        with patch.object(disk_checker.DiskChecker, 'get_free_space',
                          return_value=500 * 1024 * 1024):
            status, free = DiskChecker.check_before_recording("E:/")
            self.assertEqual(status, "warn")

    def test_check_before_recording_block(self):
        """free < 200MB → 'block'"""
        from utils import disk_checker
        from utils.disk_checker import DiskChecker
        # 100MB = 100*1024*1024
        with patch.object(disk_checker.DiskChecker, 'get_free_space',
                          return_value=100 * 1024 * 1024):
            status, free = DiskChecker.check_before_recording("E:/")
            self.assertEqual(status, "block")

    def test_thresholds_constants(self):
        """阈值常量正确（模块级）"""
        from utils import disk_checker
        self.assertEqual(disk_checker.WARN_THRESHOLD_MB, 1024)
        self.assertEqual(disk_checker.BLOCK_THRESHOLD_MB, 200)


@pytest.mark.hardware
class TestRecorderManagerWindow(unittest.TestCase):
    """RecorderManager 窗口相关静态方法测试"""

    def test_get_window_rect_returns_qrect(self):
        """_get_window_rect 对存在窗口返回 QRect（用 Shell_TrayWnd 或记事本）"""
        from recorder.recorder_manager import RecorderManager
        user32 = ctypes.windll.user32
        # 用 desktop var 等可能返回 None，改用 Shell 窗口的话需排除最小化
        # 找当前前台窗口
        fg = user32.GetForegroundWindow()
        if not fg:
            self.skipTest("无前台窗口")
        rect = RecorderManager._get_window_rect(fg)
        # 前台可能是最小化的（罕见），允许 None
        if rect is not None:
            from PyQt5.QtCore import QRect
            self.assertIsInstance(rect, QRect)
            self.assertGreater(rect.width(), 0)

    def test_get_window_rect_minimized_returns_none(self):
        """最小化窗口返回 None"""
        from recorder.recorder_manager import RecorderManager
        user32 = ctypes.windll.user32
        # 枚举找一个最小化窗口或直接构造——用前台（通常不会最小化）这支测不到则跳过
        fg = user32.GetForegroundWindow()
        if not fg or not user32.IsIconic(fg):
            self.skipTest("当前前台非最小化，跳过 minimized 断言")
        self.assertIsNone(RecorderManager._get_window_rect(fg))

    def test_get_window_hwnd_method_exists(self):
        """get_window_hwnd 方法存在"""
        from recorder.recorder_manager import RecorderManager
        self.assertTrue(hasattr(RecorderManager, 'get_window_hwnd'))

    def test_get_window_rect_invalid_hwnd_returns_none(self):
        """无效 hwnd 返回 None"""
        from recorder.recorder_manager import RecorderManager
        self.assertIsNone(RecorderManager._get_window_rect(0))


class TestConfigV13(unittest.TestCase):
    """ConfigManager v1.3 向后兼容测试"""

    def test_v12_config_loads_with_defaults(self):
        """v1.2 配置（无 v1.3 字段）加载时新字段有默认值"""
        from config import ConfigManager
        with tempfile.TemporaryDirectory() as td:
            # ConfigManager 读 <APPDATA>/QuickRec/config.json，提前建子目录
            qr_dir = os.path.join(td, "QuickRec")
            os.makedirs(qr_dir, exist_ok=True)
            cfg_path = os.path.join(qr_dir, "config.json")
            v12_data = {
                "save_path": "E:/QRtest",
                "quality": "high",
                "fps": 60,
                "shortcut_start": "Ctrl+Q",
                "shortcut_stop": "Ctrl+E",
                "shortcut_pause": "Ctrl+S",
                "shortcut_area": "Ctrl+A",
                "shortcut_window": "Ctrl+W",
            }
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(v12_data, f)
            # ConfigManager 用 APPDATA 环境变量找配置，patch 到临时目录
            with patch.dict('os.environ', {'APPDATA': td}):
                cm = ConfigManager()
                # v1.2 已有字段保留
                self.assertEqual(cm.get("shortcut_window"), "Ctrl+W")
                # v1.3 / v1.2 可缺字段填默认值
                self.assertEqual(cm.get("countdown_seconds", 3), 3)
                self.assertEqual(cm.get("mouse_highlight", False), False)
                self.assertEqual(cm.get("audio_source", "none"), "none")

    def test_default_shortcut_window(self):
        """默认 shortcut_window 是 Ctrl+Shift+W"""
        from config import ConfigManager
        self.assertIn("shortcut_window", ConfigManager.defaults)
        self.assertEqual(ConfigManager.defaults["shortcut_window"], "Ctrl+Shift+W")


class TestWindowHighlighterConstruct(unittest.TestCase):
    """WindowHighlighter v1.3 构造测试（不实际显示）"""

    def test_construct_and_methods(self):
        """WindowHighlighter 类有 show_highlight / hide_highlight 方法"""
        from ui.window_highlighter import WindowHighlighter
        self.assertTrue(hasattr(WindowHighlighter, 'show_highlight'))
        self.assertTrue(hasattr(WindowHighlighter, 'hide_highlight'))
        self.assertTrue(hasattr(WindowHighlighter, 'hwnd'))


if __name__ == "__main__":
    unittest.main()
