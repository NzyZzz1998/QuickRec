from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.media_metadata import (  # noqa: E402
    resolve_ffmpeg_path,
    resolve_ffprobe_path,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _video_filter() -> str:
    font = "C\\:/Windows/Fonts/consola.ttf"
    return (
        f"drawtext=fontfile='{font}':"
        "text='FRAME %{n}  TIME %{pts\\:hms}':"
        "x=12:y=12:fontsize=18:fontcolor=white:"
        "box=1:boxcolor=black@0.65"
    )


def _media_command(
    ffmpeg: str,
    output: Path,
    *,
    fps: int,
    duration: int,
    audio: bool,
    long_sample: bool = False,
) -> list[str]:
    size = "320x180" if long_sample else "640x360"
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={size}:rate={fps}:duration={duration}",
    ]
    if audio:
        audio_source = (
            f"sine=frequency=880:sample_rate=48000:duration={duration}"
            if long_sample
            else (
                "aevalsrc="
                f"if(lt(mod(t\\,2)\\,1)\\,-0.5\\,0.5):s=48000:d={duration}"
            )
        )
        command.extend(["-f", "lavfi", "-i", audio_source])
    command.extend(
        [
            "-vf",
            _video_filter(),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "30" if long_sample else "23",
            "-g",
            str(fps * 2),
            "-pix_fmt",
            "yuv420p",
        ]
    )
    if audio:
        command.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
    else:
        command.append("-an")
    command.append(str(output))
    return command


def _run(command: list[str], *, timeout: float) -> None:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(
            f"media generation failed ({completed.returncode}): {detail}"
        )


def _probe(ffprobe: str, path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed for {path.name}: {completed.stderr.strip()}"
        )
    return json.loads(completed.stdout)


def generate_suite(
    output_dir: Path,
    *,
    long_duration: int = 600,
) -> dict[str, Any]:
    ffmpeg = resolve_ffmpeg_path()
    ffprobe = resolve_ffprobe_path()
    if not ffmpeg or not ffprobe:
        raise FileNotFoundError("bundled ffmpeg/ffprobe is unavailable")
    output_dir.mkdir(parents=True, exist_ok=True)
    definitions = {
        "h264_aac_30": (30, 30, True, False),
        "h264_aac_60": (60, 6, True, False),
        "h264_aac_120": (120, 6, True, False),
        "h264_silent_30": (30, 6, False, False),
        "h264_aac_10min": (30, long_duration, True, True),
    }
    files: dict[str, Any] = {}
    commands: dict[str, list[str]] = {}
    for name, (fps, duration, audio, is_long) in definitions.items():
        path = output_dir / f"{name}.mp4"
        command = _media_command(
            ffmpeg,
            path,
            fps=fps,
            duration=duration,
            audio=audio,
            long_sample=is_long,
        )
        _run(command, timeout=max(60.0, duration * 2.0))
        commands[name] = command
        files[name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "probe": _probe(ffprobe, path),
        }

    unicode_dir = output_dir / "中文 空格路径"
    unicode_dir.mkdir(parents=True, exist_ok=True)
    unicode_path = unicode_dir / "剪辑 边界 30fps.mp4"
    shutil.copy2(
        Path(files["h264_aac_30"]["path"]),
        unicode_path,
    )
    files["unicode_space_copy"] = {
        "path": str(unicode_path.resolve()),
        "bytes": unicode_path.stat().st_size,
        "sha256": _sha256(unicode_path),
        "probe": _probe(ffprobe, unicode_path),
    }
    manifest = {
        "schema_version": 1,
        "generated_at_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ffmpeg": str(Path(ffmpeg).resolve()),
        "ffprobe": str(Path(ffprobe).resolve()),
        "long_duration_seconds": long_duration,
        "commands": commands,
        "files": files,
    }
    manifest_path = output_dir / "media-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成 QuickRec v1.9.3 剪辑播放准确性受控媒体"
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--long-duration", type=int, default=600)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = generate_suite(
        Path(args.output_dir).resolve(),
        long_duration=max(30, args.long_duration),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
