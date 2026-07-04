import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recorder.frame_resize import resize_bgr_frame


class TestFrameResize(unittest.TestCase):
    def test_resize_bgr_frame_keeps_bgr_channel_order_without_cv2(self):
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        frame[:, :] = [10, 20, 200]

        with patch.dict(sys.modules, {"cv2": None}):
            resized = resize_bgr_frame(frame, (4, 4))

        self.assertEqual(resized.shape, (4, 4, 3))
        self.assertEqual(resized.dtype, frame.dtype)
        self.assertTrue(np.all(resized[0, 0] == [10, 20, 200]))


if __name__ == "__main__":
    unittest.main()
