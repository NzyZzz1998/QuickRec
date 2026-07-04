import ctypes
import ctypes.wintypes

from PyQt5.QtCore import QRect

MIN_CAPTURE_SIZE = 2
MIN_WINDOW_CAPTURE_SIZE = 10


def normalize_capture_region(
    region: tuple[int, int, int, int],
    min_size: int = MIN_CAPTURE_SIZE,
) -> tuple[int, int, int, int] | None:
    left, top, width, height = (int(value) for value in region)
    if width < min_size or height < min_size:
        return None

    width &= ~1
    height &= ~1
    if width < min_size or height < min_size:
        return None

    return left, top, width, height


def get_window_client_rect(hwnd: int) -> QRect | None:
    user32 = ctypes.windll.user32
    if not user32.IsWindow(hwnd):
        return None
    if not user32.IsWindowVisible(hwnd):
        return None
    if user32.IsIconic(hwnd):
        return None

    client_rect = ctypes.wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(client_rect)):
        return None

    region = normalize_capture_region(
        (0, 0, client_rect.right, client_rect.bottom),
        min_size=MIN_WINDOW_CAPTURE_SIZE,
    )
    if region is None:
        return None

    _, _, width, height = region
    point = ctypes.wintypes.POINT()
    if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
        return None

    return QRect(point.x, point.y, width, height)
