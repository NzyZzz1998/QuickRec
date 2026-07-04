import ctypes

import numpy as np
from PIL import Image, ImageDraw

_CURSOR_POLYGON = [(0, 0), (0, 18), (5, 14), (8, 22), (12, 20), (9, 13), (16, 13)]


def get_cursor_position() -> tuple[int, int] | None:
    try:
        point = ctypes.wintypes.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return None
        return point.x, point.y
    except Exception:
        return None


def draw_cursor(
    frame: np.ndarray,
    capture_region: tuple[int, int, int, int] | None = None,
    cursor_position: tuple[int, int] | None = None,
) -> np.ndarray:
    cursor_position = cursor_position if cursor_position is not None else get_cursor_position()
    if cursor_position is None:
        return frame.copy()

    origin_x, origin_y = (capture_region[0], capture_region[1]) if capture_region else (0, 0)
    x = int(cursor_position[0] - origin_x)
    y = int(cursor_position[1] - origin_y)
    height, width = frame.shape[:2]
    if x < 0 or y < 0 or x >= width or y >= height:
        return frame.copy()

    image = Image.fromarray(frame[:, :, ::-1], mode="RGB")
    draw = ImageDraw.Draw(image)
    points = [(x + px, y + py) for px, py in _CURSOR_POLYGON]
    draw.line(points + [points[0]], fill=(0, 0, 0), width=3)
    draw.polygon(points, fill=(255, 255, 255), outline=(0, 0, 0))
    return np.asarray(image)[:, :, ::-1].copy()
