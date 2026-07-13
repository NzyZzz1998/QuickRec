"""使用 ffprobe 读取本地视频基础元数据。"""

import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("QuickRec")


@dataclass(frozen=True)
class MediaMetadataResult:
    ok: bool
    duration_sec: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    error: str = ""


def resolve_ffprobe_path() -> str:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "ffmpeg" / "ffprobe.exe")
        candidates.append(Path(sys.executable).parent / "ffmpeg" / "ffprobe.exe")
    candidates.append(Path(__file__).resolve().parents[2] / "ffmpeg" / "ffprobe.exe")
    for candidate in candidates:
        if candidate.is_file():
            logger.debug("ffprobe resolved: frozen=%s executable=%s", getattr(sys, "frozen", False), candidate)
            return str(candidate)
    return shutil.which("ffprobe") or ""


def probe_media(
    video_path: str | Path,
    *,
    ffprobe_path: str | None = None,
    timeout: float = 30,
) -> MediaMetadataResult:
    executable = ffprobe_path or resolve_ffprobe_path()
    if not executable:
        logger.warning("ffprobe unavailable")
        return MediaMetadataResult(False, error="ffprobe executable not found")
    command = [
        executable,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        logger.warning("ffprobe timeout: path=%s timeout=%s", video_path, timeout)
        return MediaMetadataResult(False, error=f"ffprobe timeout after {timeout:g}s")
    except OSError as exc:
        logger.warning("ffprobe start failed: path=%s error=%s", video_path, exc)
        return MediaMetadataResult(False, error=str(exc))
    if completed.returncode != 0:
        logger.warning(
            "ffprobe returned nonzero: path=%s returncode=%s stderr=%s",
            video_path,
            completed.returncode,
            _short_error(completed.stderr),
        )
        return MediaMetadataResult(False, error=(completed.stderr or "ffprobe failed").strip())
    try:
        payload = json.loads(completed.stdout)
        stream = next(
            item
            for item in payload.get("streams", [])
            if isinstance(item, dict) and item.get("codec_type") == "video"
        )
        format_data = payload.get("format", {})
        duration = _optional_float(format_data.get("duration"))
        width = _optional_int(stream.get("width"))
        height = _optional_int(stream.get("height"))
        fps = _parse_frame_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
        if not duration or not width or not height or not fps:
            raise ValueError("required metadata fields are missing")
        return MediaMetadataResult(
            True,
            duration_sec=duration,
            width=width,
            height=height,
            fps=fps,
        )
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("ffprobe output invalid: path=%s error=%s", video_path, exc)
        return MediaMetadataResult(False, error=f"invalid ffprobe output: {exc}")


def _short_error(value: str | None, limit: int = 300) -> str:
    text = (value or "").strip().replace("\r", " ").replace("\n", " ")
    return text[:limit]


def _parse_frame_rate(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value)
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        denominator_value = float(denominator)
        return float(numerator) / denominator_value if denominator_value else None
    return _optional_float(text)


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
