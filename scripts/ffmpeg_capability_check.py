from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CapabilityResult:
    ok: bool
    message: str


def _run_ffmpeg(ffmpeg_path: str, args: list[str], timeout: int = 30) -> CapabilityResult:
    try:
        result = subprocess.run(
            [ffmpeg_path, *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:
        return CapabilityResult(False, f"ffmpeg command failed: {exc}")
    if result.returncode != 0:
        return CapabilityResult(False, result.stdout[-2000:])
    return CapabilityResult(True, "ok")


def check_encoders(ffmpeg_path: str) -> CapabilityResult:
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        return CapabilityResult(False, f"encoder probe failed: {exc}")
    output = result.stdout
    missing = []
    if "libx264" not in output:
        missing.append("libx264")
    if " aac" not in output and "\naac" not in output:
        missing.append("aac")
    if missing:
        return CapabilityResult(False, f"missing encoders: {', '.join(missing)}")
    return CapabilityResult(True, "required encoders ok")


def check_mixed_output(ffmpeg_path: str, mixed_path: str) -> CapabilityResult:
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-i", mixed_path],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        return CapabilityResult(False, f"mixed output probe failed: {exc}")
    output = result.stdout
    if "Video:" not in output:
        return CapabilityResult(False, "mixed output missing Video stream")
    if "Audio: aac" not in output:
        return CapabilityResult(False, "mixed output missing Audio: aac stream")
    return CapabilityResult(True, "mixed output ok")


def run_capability_check(ffmpeg_path: str, output_dir: str | None = None) -> CapabilityResult:
    if not os.path.isfile(ffmpeg_path):
        return CapabilityResult(False, f"ffmpeg missing: {ffmpeg_path}")
    work_dir = Path(output_dir or tempfile.mkdtemp(prefix="quickrec-ffmpeg-capability-"))
    work_dir.mkdir(parents=True, exist_ok=True)

    encoder_result = check_encoders(ffmpeg_path)
    if not encoder_result.ok:
        return encoder_result

    video = work_dir / "video.mp4"
    sys_audio = work_dir / "audio_sys.wav"
    mic_audio = work_dir / "audio_mic.wav"
    mixed = work_dir / "mixed.mp4"

    steps = [
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=15:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        ["-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-ac", "1", str(sys_audio)],
        ["-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=2", "-ac", "1", str(mic_audio)],
        [
            "-y",
            "-i",
            str(video),
            "-i",
            str(sys_audio),
            "-i",
            str(mic_audio),
            "-filter_complex",
            "[1:a][2:a]amerge=inputs=2[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(mixed),
        ],
    ]
    for args in steps:
        result = _run_ffmpeg(ffmpeg_path, args)
        if not result.ok:
            return result
    return check_mixed_output(ffmpeg_path, str(mixed))


def find_default_ffmpeg() -> str:
    project_ffmpeg = Path("ffmpeg") / "ffmpeg.exe"
    if project_ffmpeg.exists():
        return str(project_ffmpeg)
    return shutil.which("ffmpeg") or ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate FFmpeg capabilities required by QuickRec.")
    parser.add_argument("--ffmpeg", default=find_default_ffmpeg(), help="Path to ffmpeg.exe.")
    parser.add_argument("--output-dir", default="", help="Directory for generated probe files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_capability_check(args.ffmpeg, args.output_dir or None)
    if result.ok:
        print(f"OK: {result.message}")
        return 0
    print(f"FAILED: {result.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
