import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recorder.cursor_overlay import draw_cursor


class TestCursorOverlay(unittest.TestCase):
    def test_draw_cursor_inside_region_changes_pixels(self):
        frame = np.zeros((80, 100, 3), dtype=np.uint8)

        result = draw_cursor(frame, capture_region=(50, 60, 100, 80), cursor_position=(60, 70))

        self.assertEqual(result.shape, frame.shape)
        self.assertGreater(result.sum(), 0)
        self.assertTrue(np.all(frame == 0))

    def test_draw_cursor_outside_region_returns_unchanged_copy(self):
        frame = np.zeros((80, 100, 3), dtype=np.uint8)

        result = draw_cursor(frame, capture_region=(50, 60, 100, 80), cursor_position=(10, 10))

        self.assertEqual(result.shape, frame.shape)
        self.assertTrue(np.all(result == frame))
        self.assertIsNot(result, frame)


if __name__ == "__main__":
    unittest.main()
