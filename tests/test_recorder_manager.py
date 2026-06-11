"""
RecorderManager 单元测试
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ConfigManager
from recorder.recorder_manager import RecorderManager, RecorderState


class TestRecorderManager(unittest.TestCase):
    """RecorderManager 测试类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigManager.__new__(ConfigManager)
        self.config._config_path = os.path.join(self.temp_dir, "config.json")
        self.config._config = {
            "save_path": self.temp_dir,
            "quality": "low",
            "fps": 30,
        }

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initial_state_is_idle(self):
        """测试初始状态为 IDLE"""
        manager = RecorderManager(self.config)
        self.assertEqual(manager.get_state(), RecorderState.IDLE)

    def test_start_fullscreen_changes_state(self):
        """测试全屏录制启动后状态变为 RECORDING"""
        manager = RecorderManager(self.config)
        try:
            result = manager.start_fullscreen()
            self.assertTrue(result)
            self.assertEqual(manager.get_state(), RecorderState.RECORDING)
        finally:
            if manager.get_state() != RecorderState.IDLE:
                manager.stop()

    def test_pause_resume_state_flow(self):
        """测试暂停/恢复状态流转"""
        manager = RecorderManager(self.config)
        try:
            manager.start_fullscreen()
            # 暂停
            self.assertTrue(manager.pause())
            self.assertEqual(manager.get_state(), RecorderState.PAUSED)
            # 不能重复暂停
            self.assertFalse(manager.pause())
            # 恢复
            self.assertTrue(manager.resume())
            self.assertEqual(manager.get_state(), RecorderState.RECORDING)
            # 不能重复恢复
            self.assertFalse(manager.resume())
        finally:
            manager.stop()

    def test_stop_returns_file_path(self):
        """测试停止后返回有效文件路径"""
        manager = RecorderManager(self.config)
        manager.start_fullscreen()
        time.sleep(0.5)  # 录制短暂时间
        output = manager.stop()
        self.assertTrue(len(output) > 0)
        self.assertTrue(output.endswith(".mp4"))
        self.assertTrue(os.path.exists(output))

    def test_stop_when_idle_returns_empty(self):
        """测试空闲时停止返回空字符串"""
        manager = RecorderManager(self.config)
        result = manager.stop()
        self.assertEqual(result, "")

    def test_elapsed_time_format(self):
        """测试录制时长格式"""
        manager = RecorderManager(self.config)
        self.assertEqual(manager.get_elapsed(), "00:00")
        try:
            manager.start_fullscreen()
            time.sleep(1.0)
            elapsed = manager.get_elapsed()
            # 应该有值，格式为 MM:SS
            self.assertRegex(elapsed, r"\d{2}:\d{2}")
        finally:
            manager.stop()

    def test_consecutive_start_stop(self):
        """测试连续 start-stop 无资源泄漏"""
        manager = RecorderManager(self.config)
        try:
            for _ in range(3):
                self.assertTrue(manager.start_fullscreen())
                time.sleep(0.3)
                output = manager.stop()
                self.assertTrue(output.endswith(".mp4"))
                self.assertEqual(manager.get_state(), RecorderState.IDLE)
        finally:
            if manager.get_state() != RecorderState.IDLE:
                manager.stop()


if __name__ == "__main__":
    unittest.main()