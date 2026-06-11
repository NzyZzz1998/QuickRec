"""
AreaSelector 单元测试
"""

import os
import sys
import unittest

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QPoint, QRect

# 确保 QApplication 实例存在
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from ui.area_selector import AreaSelector


class TestAreaSelector(unittest.TestCase):
    """AreaSelector 测试类"""

    def test_initial_state(self):
        """测试初始状态"""
        selector = AreaSelector()
        self.assertFalse(selector._is_drawing)
        self.assertEqual(selector._selected_rect, QRect())

    def test_min_size_constant(self):
        """测试最小选区尺寸常量"""
        self.assertEqual(AreaSelector.MIN_SIZE, 100)

    def test_get_selection_rect_normalized(self):
        """测试选区矩形规范化（正向拖拽）"""
        selector = AreaSelector()
        selector._start_point = QPoint(10, 20)
        selector._end_point = QPoint(110, 120)
        rect = selector._get_selection_rect()
        self.assertEqual(rect.x(), 10)
        self.assertEqual(rect.y(), 20)
        self.assertEqual(rect.width(), 100)
        self.assertEqual(rect.height(), 100)

    def test_get_selection_rect_reverse_drag(self):
        """测试反向拖拽时矩形规范化"""
        selector = AreaSelector()
        selector._start_point = QPoint(200, 300)
        selector._end_point = QPoint(100, 100)
        rect = selector._get_selection_rect()
        self.assertEqual(rect.x(), 100)
        self.assertEqual(rect.y(), 100)
        self.assertEqual(rect.width(), 100)
        self.assertEqual(rect.height(), 200)

    def test_signals_defined(self):
        """测试信号定义"""
        selector = AreaSelector()
        self.assertTrue(hasattr(selector, 'region_selected'))
        self.assertTrue(hasattr(selector, 'cancelled'))

    def test_window_flags(self):
        """测试窗口标志设置"""
        selector = AreaSelector()
        flags = selector.windowFlags()
        self.assertTrue(bool(flags & Qt.FramelessWindowHint))
        self.assertTrue(bool(flags & Qt.WindowStaysOnTopHint))


if __name__ == "__main__":
    unittest.main()