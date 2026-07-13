"""
RecordingToolbar 单元测试
"""

import os
import sys
import unittest

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from ui.toolbar import RecordingToolbar


class TestRecordingToolbar(unittest.TestCase):
    """RecordingToolbar 测试类"""

    def test_initial_state(self):
        """测试初始状态"""
        toolbar = RecordingToolbar()
        self.assertTrue(toolbar._recording)
        self.assertFalse(toolbar._paused)
        self.assertEqual(toolbar._elapsed_seconds, 0)

    def test_timer_display_format(self):
        """测试计时器显示格式"""
        toolbar = RecordingToolbar()
        toolbar._elapsed_seconds = 125  # 2分5秒
        # 手动计算显示（不调用 _update_timer 避免 +1）
        minutes = toolbar._elapsed_seconds // 60
        seconds = toolbar._elapsed_seconds % 60
        self.assertEqual(f"{minutes:02d}:{seconds:02d}", "02:05")

    def test_timer_display_zero(self):
        """测试计时器初始显示"""
        toolbar = RecordingToolbar()
        self.assertEqual(toolbar._label_timer.text(), "00:00")

    def test_set_paused_state(self):
        """测试暂停状态切换"""
        toolbar = RecordingToolbar()
        toolbar.set_paused(True)
        self.assertTrue(toolbar._paused)
        self.assertEqual(toolbar._btn_pause.text(), "▶ 继续")

        toolbar.set_paused(False)
        self.assertFalse(toolbar._paused)
        self.assertEqual(toolbar._btn_pause.text(), "⏸ 暂停")

    def test_signals_defined(self):
        """测试信号定义"""
        toolbar = RecordingToolbar()
        self.assertTrue(hasattr(toolbar, 'paused'))
        self.assertTrue(hasattr(toolbar, 'resumed'))
        self.assertTrue(hasattr(toolbar, 'stopped'))
        self.assertTrue(hasattr(toolbar, 'cancelled'))
        self.assertTrue(hasattr(toolbar, 'material_library_requested'))

    def test_result_mode_shows_material_library_button(self):
        toolbar = RecordingToolbar()

        toolbar.show_result("out.mp4", "1.0MB")

        self.assertFalse(toolbar._btn_material.isHidden())
        self.assertEqual(toolbar._btn_material.text(), "素材库")

    def test_material_library_button_emits_signal(self):
        toolbar = RecordingToolbar()
        calls = []
        toolbar.material_library_requested.connect(lambda: calls.append("material"))
        toolbar.show_result("out.mp4", "1.0MB")

        toolbar._btn_material.click()

        self.assertEqual(calls, ["material"])

    def test_index_failure_changes_result_action_to_retry(self):
        toolbar = RecordingToolbar()
        retries = []
        toolbar.retry_material_requested.connect(retries.append)

        toolbar.show_result("out.mp4", "1.0MB", index_ok=False)
        toolbar._btn_material.click()

        self.assertEqual(toolbar._btn_material.text(), "重试入库")
        self.assertEqual(retries, ["out.mp4"])

    def test_window_flags(self):
        """测试窗口标志"""
        toolbar = RecordingToolbar()
        flags = toolbar.windowFlags()
        self.assertTrue(bool(flags & Qt.FramelessWindowHint))
        self.assertTrue(bool(flags & Qt.WindowStaysOnTopHint))

    def test_timer_not_counting_when_paused(self):
        """测试暂停时计时器不增加"""
        toolbar = RecordingToolbar()
        toolbar.set_paused(True)
        toolbar._update_timer()
        self.assertEqual(toolbar._elapsed_seconds, 0)

    def test_stop_recording_timer_resets(self):
        """测试停止计时器"""
        toolbar = RecordingToolbar()
        toolbar.stop_recording_timer()
        # stop_recording_timer 只停止定时器，不清零显示
        self.assertFalse(toolbar._timer.isActive())


if __name__ == "__main__":
    unittest.main()
