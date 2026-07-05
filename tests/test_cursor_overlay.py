import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recorder.cursor_overlay import CursorImage, _get_cursor_base_size, draw_cursor


class TestCursorOverlay(unittest.TestCase):
    def _changed_bounds(self, before, after):
        changed = np.argwhere(after != before)
        self.assertGreater(len(changed), 0)
        min_y, min_x = changed[:, :2].min(axis=0)
        max_y, max_x = changed[:, :2].max(axis=0)
        return min_x, min_y, max_x, max_y

    def test_draw_cursor_inside_region_changes_pixels(self):
        frame = np.zeros((80, 100, 3), dtype=np.uint8)

        with patch("recorder.cursor_overlay.get_system_cursor_image", return_value=None):
            result = draw_cursor(frame, capture_region=(50, 60, 100, 80), cursor_position=(60, 70))

        self.assertEqual(result.shape, frame.shape)
        self.assertGreater(result.sum(), 0)
        self.assertTrue(np.all(frame == 0))

    def test_draw_cursor_outside_region_returns_unchanged_copy(self):
        frame = np.zeros((80, 100, 3), dtype=np.uint8)

        with patch("recorder.cursor_overlay.get_system_cursor_image", return_value=None):
            result = draw_cursor(frame, capture_region=(50, 60, 100, 80), cursor_position=(10, 10))

        self.assertEqual(result.shape, frame.shape)
        self.assertTrue(np.all(result == frame))
        self.assertIsNot(result, frame)

    def test_draw_cursor_scales_position_when_frame_size_differs_from_capture_region(self):
        frame = np.zeros((100, 200, 3), dtype=np.uint8)

        with patch("recorder.cursor_overlay.get_system_cursor_image", return_value=None):
            result = draw_cursor(frame, capture_region=(0, 0, 100, 50), cursor_position=(50, 25))

        min_x, min_y, _, _ = self._changed_bounds(frame, result)
        self.assertGreaterEqual(min_x, 95)
        self.assertGreaterEqual(min_y, 45)

    def test_draw_cursor_scales_shape_down_when_output_frame_is_smaller(self):
        source_size_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        small_output_frame = np.zeros((50, 50, 3), dtype=np.uint8)

        with patch("recorder.cursor_overlay.get_system_cursor_image", return_value=None):
            source_result = draw_cursor(
                source_size_frame,
                capture_region=(0, 0, 100, 100),
                cursor_position=(50, 50),
            )
            small_result = draw_cursor(
                small_output_frame,
                capture_region=(0, 0, 100, 100),
                cursor_position=(50, 50),
            )

        source_min_x, source_min_y, source_max_x, source_max_y = self._changed_bounds(source_size_frame, source_result)
        small_min_x, small_min_y, small_max_x, small_max_y = self._changed_bounds(small_output_frame, small_result)
        source_width = source_max_x - source_min_x + 1
        source_height = source_max_y - source_min_y + 1
        small_width = small_max_x - small_min_x + 1
        small_height = small_max_y - small_min_y + 1

        self.assertLess(small_width, source_width)
        self.assertLess(small_height, source_height)

    def test_draw_cursor_accepts_size_multiplier(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch("recorder.cursor_overlay.get_system_cursor_image", return_value=None):
            normal = draw_cursor(frame, capture_region=(0, 0, 100, 100), cursor_position=(50, 50))
            smaller = draw_cursor(
                frame,
                capture_region=(0, 0, 100, 100),
                cursor_position=(50, 50),
                size_multiplier=0.65,
            )

        normal_min_x, normal_min_y, normal_max_x, normal_max_y = self._changed_bounds(frame, normal)
        small_min_x, small_min_y, small_max_x, small_max_y = self._changed_bounds(frame, smaller)
        normal_width = normal_max_x - normal_min_x + 1
        normal_height = normal_max_y - normal_min_y + 1
        small_width = small_max_x - small_min_x + 1
        small_height = small_max_y - small_min_y + 1

        self.assertLess(small_width, normal_width)
        self.assertLess(small_height, normal_height)

    def test_draw_cursor_prefers_system_cursor_image(self):
        frame = np.zeros((40, 40, 3), dtype=np.uint8)
        cursor_image = Image.new("RGBA", (10, 10), (255, 0, 0, 255))

        with patch(
            "recorder.cursor_overlay.get_system_cursor_image",
            return_value=CursorImage(cursor_image, hotspot=(0, 0)),
        ):
            result = draw_cursor(frame, capture_region=(0, 0, 40, 40), cursor_position=(5, 5))

        self.assertEqual(result[5, 5, 2], 255)
        self.assertEqual(result[5, 5, 1], 0)
        self.assertEqual(result[5, 5, 0], 0)

    def test_cursor_base_size_prefers_color_bitmap_size(self):
        class FakeGdi32:
            def GetObjectW(self, handle, _size, bitmap_ptr):
                bitmap = bitmap_ptr._obj
                bitmap.bmWidth = 48 if handle == 1 else 16
                bitmap.bmHeight = 48 if handle == 1 else 32
                return 1

        icon_info = type("IconInfo", (), {"hbmColor": 1, "hbmMask": 2})()

        self.assertEqual(_get_cursor_base_size(None, FakeGdi32(), icon_info), (48, 48))

    def test_cursor_base_size_halves_monochrome_mask_height(self):
        class FakeGdi32:
            def GetObjectW(self, _handle, _size, bitmap_ptr):
                bitmap = bitmap_ptr._obj
                bitmap.bmWidth = 32
                bitmap.bmHeight = 64
                return 1

        icon_info = type("IconInfo", (), {"hbmColor": 0, "hbmMask": 2})()

        self.assertEqual(_get_cursor_base_size(None, FakeGdi32(), icon_info), (32, 32))

    def test_cursor_base_size_falls_back_to_system_metrics(self):
        class FakeUser32:
            def GetSystemMetrics(self, metric):
                return {13: 24, 14: 28}[metric]

        class FakeGdi32:
            def GetObjectW(self, _handle, _size, _bitmap_ptr):
                return 0

        icon_info = type("IconInfo", (), {"hbmColor": 0, "hbmMask": 0})()

        self.assertEqual(_get_cursor_base_size(FakeUser32(), FakeGdi32(), icon_info), (24, 28))


if __name__ == "__main__":
    unittest.main()
