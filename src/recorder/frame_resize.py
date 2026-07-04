import numpy as np
from PIL import Image


def resize_bgr_frame(frame: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    rgb = frame[:, :, ::-1]
    image = Image.fromarray(rgb, mode="RGB")
    resized = image.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(resized)[:, :, ::-1].copy()
