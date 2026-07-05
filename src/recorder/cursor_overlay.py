import ctypes
import ctypes.wintypes
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

_CURSOR_POLYGON = [(0, 0), (0, 18), (5, 14), (8, 22), (12, 20), (9, 13), (16, 13)]
_CURSOR_SHOWING = 0x00000001
_DI_NORMAL = 0x0003
_DIB_RGB_COLORS = 0
_SM_CXCURSOR = 13
_SM_CYCURSOR = 14


class _Bitmap(ctypes.Structure):
    _fields_ = [
        ("bmType", ctypes.wintypes.LONG),
        ("bmWidth", ctypes.wintypes.LONG),
        ("bmHeight", ctypes.wintypes.LONG),
        ("bmWidthBytes", ctypes.wintypes.LONG),
        ("bmPlanes", ctypes.wintypes.WORD),
        ("bmBitsPixel", ctypes.wintypes.WORD),
        ("bmBits", ctypes.c_void_p),
    ]


class _CursorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("hCursor", ctypes.wintypes.HANDLE),
        ("ptScreenPos", ctypes.wintypes.POINT),
    ]


class _IconInfo(ctypes.Structure):
    _fields_ = [
        ("fIcon", ctypes.wintypes.BOOL),
        ("xHotspot", ctypes.wintypes.DWORD),
        ("yHotspot", ctypes.wintypes.DWORD),
        ("hbmMask", ctypes.wintypes.HANDLE),
        ("hbmColor", ctypes.wintypes.HANDLE),
    ]


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.wintypes.DWORD),
        ("biWidth", ctypes.wintypes.LONG),
        ("biHeight", ctypes.wintypes.LONG),
        ("biPlanes", ctypes.wintypes.WORD),
        ("biBitCount", ctypes.wintypes.WORD),
        ("biCompression", ctypes.wintypes.DWORD),
        ("biSizeImage", ctypes.wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.wintypes.LONG),
        ("biYPelsPerMeter", ctypes.wintypes.LONG),
        ("biClrUsed", ctypes.wintypes.DWORD),
        ("biClrImportant", ctypes.wintypes.DWORD),
    ]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("bmiHeader", _BitmapInfoHeader), ("bmiColors", ctypes.wintypes.DWORD * 3)]


@dataclass(frozen=True)
class CursorImage:
    image: Image.Image
    hotspot: tuple[int, int]


def get_cursor_position() -> tuple[int, int] | None:
    try:
        point = ctypes.wintypes.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return None
        return point.x, point.y
    except Exception:
        return None


def _get_bitmap_size(gdi32, handle) -> tuple[int, int] | None:
    if not handle:
        return None
    bitmap = _Bitmap()
    if not gdi32.GetObjectW(handle, ctypes.sizeof(_Bitmap), ctypes.byref(bitmap)):
        return None
    if bitmap.bmWidth <= 0 or bitmap.bmHeight <= 0:
        return None
    return int(bitmap.bmWidth), int(bitmap.bmHeight)


def _get_cursor_base_size(user32, gdi32, icon_info: _IconInfo) -> tuple[int, int]:
    color_size = _get_bitmap_size(gdi32, icon_info.hbmColor)
    if color_size is not None:
        return color_size

    mask_size = _get_bitmap_size(gdi32, icon_info.hbmMask)
    if mask_size is not None:
        return mask_size[0], max(1, mask_size[1] // 2)

    return user32.GetSystemMetrics(_SM_CXCURSOR), user32.GetSystemMetrics(_SM_CYCURSOR)


def get_system_cursor_image(size_multiplier: float = 1.0) -> CursorImage | None:
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        cursor_info = _CursorInfo()
        cursor_info.cbSize = ctypes.sizeof(_CursorInfo)
        if not user32.GetCursorInfo(ctypes.byref(cursor_info)):
            return None
        if cursor_info.flags != _CURSOR_SHOWING or not cursor_info.hCursor:
            return None

        icon_info = _IconInfo()
        if not user32.GetIconInfo(cursor_info.hCursor, ctypes.byref(icon_info)):
            return None

        base_width, base_height = _get_cursor_base_size(user32, gdi32, icon_info)
        width = max(1, int(round(base_width * size_multiplier)))
        height = max(1, int(round(base_height * size_multiplier)))
        hotspot = (
            max(0, int(round(icon_info.xHotspot * size_multiplier))),
            max(0, int(round(icon_info.yHotspot * size_multiplier))),
        )

        screen_dc = user32.GetDC(None)
        memory_dc = gdi32.CreateCompatibleDC(screen_dc)
        bits = ctypes.c_void_p()
        bitmap_info = _BitmapInfo()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(_BitmapInfoHeader)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = -height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap = gdi32.CreateDIBSection(
            memory_dc,
            ctypes.byref(bitmap_info),
            _DIB_RGB_COLORS,
            ctypes.byref(bits),
            None,
            0,
        )
        if not bitmap or not bits:
            return None
        old_bitmap = gdi32.SelectObject(memory_dc, bitmap)
        user32.DrawIconEx(memory_dc, 0, 0, cursor_info.hCursor, width, height, 0, None, _DI_NORMAL)
        raw = ctypes.string_at(bits, width * height * 4)
        image = Image.frombuffer("RGBA", (width, height), raw, "raw", "BGRA", 0, 1).copy()
        if image.getchannel("A").getextrema() == (0, 0):
            alpha = image.convert("RGB").point(lambda value: 255 if value else 0).convert("L")
            image.putalpha(alpha)
        return CursorImage(image=image, hotspot=hotspot)
    except Exception:
        return None
    finally:
        try:
            if "old_bitmap" in locals() and old_bitmap:
                gdi32.SelectObject(memory_dc, old_bitmap)
            if "bitmap" in locals() and bitmap:
                gdi32.DeleteObject(bitmap)
            if "memory_dc" in locals() and memory_dc:
                gdi32.DeleteDC(memory_dc)
            if "screen_dc" in locals() and screen_dc:
                user32.ReleaseDC(None, screen_dc)
            if "icon_info" in locals():
                if icon_info.hbmMask:
                    gdi32.DeleteObject(icon_info.hbmMask)
                if icon_info.hbmColor:
                    gdi32.DeleteObject(icon_info.hbmColor)
        except Exception:
            pass


def _paste_cursor_image(image: Image.Image, cursor_image: CursorImage, x: int, y: int) -> Image.Image:
    paste_x = x - cursor_image.hotspot[0]
    paste_y = y - cursor_image.hotspot[1]
    image.paste(cursor_image.image, (paste_x, paste_y), cursor_image.image)
    return image


def draw_cursor(
    frame: np.ndarray,
    capture_region: tuple[int, int, int, int] | None = None,
    cursor_position: tuple[int, int] | None = None,
    size_multiplier: float = 1.0,
) -> np.ndarray:
    cursor_position = cursor_position if cursor_position is not None else get_cursor_position()
    if cursor_position is None:
        return frame.copy()

    height, width = frame.shape[:2]
    origin_x, origin_y = (capture_region[0], capture_region[1]) if capture_region else (0, 0)
    relative_x = cursor_position[0] - origin_x
    relative_y = cursor_position[1] - origin_y
    size_multiplier = max(0.1, min(size_multiplier, 1.0))
    if capture_region and capture_region[2] > 0 and capture_region[3] > 0:
        scale_x = width / capture_region[2]
        scale_y = height / capture_region[3]
        cursor_scale = min(scale_x, scale_y, 1.0) * size_multiplier
        x = int(relative_x * scale_x)
        y = int(relative_y * scale_y)
    else:
        cursor_scale = size_multiplier
        x = int(relative_x)
        y = int(relative_y)
    if x < 0 or y < 0 or x >= width or y >= height:
        return frame.copy()

    image = Image.fromarray(frame[:, :, ::-1], mode="RGB")
    system_cursor = get_system_cursor_image(cursor_scale)
    if system_cursor is not None:
        return np.asarray(_paste_cursor_image(image, system_cursor, x, y))[:, :, ::-1].copy()

    draw = ImageDraw.Draw(image)
    points = [(x + int(round(px * cursor_scale)), y + int(round(py * cursor_scale))) for px, py in _CURSOR_POLYGON]
    line_width = max(1, int(round(3 * cursor_scale)))
    draw.line(points + [points[0]], fill=(0, 0, 0), width=line_width)
    draw.polygon(points, fill=(255, 255, 255), outline=(0, 0, 0))
    return np.asarray(image)[:, :, ::-1].copy()
