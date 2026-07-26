from __future__ import annotations

from dataclasses import dataclass

from config import ConfigManager


@dataclass(frozen=True)
class EffectiveRecordingProfile:
    configured_fps: int
    effective_fps: int
    output_size: tuple[int, int]
    requires_120_capability: bool
    notice: str = ""


def _fit_size(
    source_size: tuple[int, int],
    target_size: tuple[int, int],
) -> tuple[int, int]:
    source_width, source_height = source_size
    target_width, target_height = target_size
    scale = min(target_width / source_width, target_height / source_height)
    width = max(int(source_width * scale) & ~1, 2)
    height = max(int(source_height * scale) & ~1, 2)
    return width, height


def resolve_recording_profile(
    *,
    configured_fps: int,
    mode: str,
    source_size: tuple[int, int],
    quality: str,
) -> EffectiveRecordingProfile:
    target = ConfigManager.QUALITY_SIZES.get(quality)
    if target is None:
        output_size = source_size
    elif mode == "fullscreen" or (mode == "window" and quality == "high"):
        output_size = target
        if mode == "window":
            output_size = source_size
    else:
        output_size = _fit_size(source_size, target)
    effective_fps = configured_fps
    notice = ""
    requires_capability = configured_fps == 120 and mode == "fullscreen"

    if configured_fps == 120 and mode != "fullscreen":
        effective_fps = 60
        label = "区域" if mode == "region" else "窗口"
        notice = f"{label}录制本次将按 60 FPS 进行"
    elif configured_fps == 120 and (
        output_size[0] > 1920 or output_size[1] > 1080
    ):
        output_size = _fit_size(source_size, (1920, 1080))
        notice = "120 FPS 将以 1920×1080 输出"

    return EffectiveRecordingProfile(
        configured_fps=configured_fps,
        effective_fps=effective_fps,
        output_size=output_size,
        requires_120_capability=requires_capability,
        notice=notice,
    )
