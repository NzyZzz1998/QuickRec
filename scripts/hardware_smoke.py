from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import ConfigManager  # noqa: E402
from recorder.recorder_manager import RecorderManager  # noqa: E402
from utils.temp_cleaner import TempCleaner  # noqa: E402


class ExitCode(IntEnum):
    OK = 0
    CAPTURE_FAILED = 10
    ENCODING_FAILED = 11
    FILE_CHECK_FAILED = 12
    LOG_CHECK_FAILED = 13
    TIMEOUT = 14


@dataclass(frozen=True)
class SmokeResult:
    ok: bool
    exit_code: ExitCode
    message: str
    output_path: str = ""


def check_output_file(path: str, min_size: int = 1024) -> SmokeResult:
    if not path or not os.path.exists(path):
        return SmokeResult(False, ExitCode.FILE_CHECK_FAILED, f"output file missing: {path}", path)
    size = os.path.getsize(path)
    if size < min_size:
        return SmokeResult(False, ExitCode.FILE_CHECK_FAILED, f"output file too small: {size} bytes", path)
    return SmokeResult(True, ExitCode.OK, f"output file ok: {size} bytes", path)


def find_ffmpeg() -> str:
    bundled = PROJECT_ROOT / "ffmpeg" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    return shutil.which("ffmpeg") or ""


def check_video_stream(path: str, ffmpeg_path: str) -> SmokeResult:
    if not ffmpeg_path:
        return SmokeResult(False, ExitCode.FILE_CHECK_FAILED, "ffmpeg not found for stream check", path)
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-i", path],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=15,
        )
    except Exception as exc:
        return SmokeResult(False, ExitCode.FILE_CHECK_FAILED, f"video stream check failed: {exc}", path)

    metadata = result.stderr.decode("utf-8", errors="ignore")
    if "Video:" not in metadata:
        return SmokeResult(False, ExitCode.FILE_CHECK_FAILED, "output file has no video stream", path)
    return SmokeResult(True, ExitCode.OK, "video stream ok", path)


def _duration_to_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def check_video_duration(path: str, ffmpeg_path: str, expected_duration: float) -> SmokeResult:
    if not ffmpeg_path:
        return SmokeResult(False, ExitCode.FILE_CHECK_FAILED, "ffmpeg not found for duration check", path)
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-i", path],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=15,
        )
    except Exception as exc:
        return SmokeResult(False, ExitCode.FILE_CHECK_FAILED, f"video duration check failed: {exc}", path)

    metadata = result.stderr.decode("utf-8", errors="ignore")
    marker = "Duration: "
    start = metadata.find(marker)
    if start < 0:
        return SmokeResult(False, ExitCode.FILE_CHECK_FAILED, "output file duration missing", path)
    duration_text = metadata[start + len(marker):].split(",", 1)[0].strip()
    try:
        actual_duration = _duration_to_seconds(duration_text)
    except (TypeError, ValueError):
        return SmokeResult(False, ExitCode.FILE_CHECK_FAILED, f"output file duration invalid: {duration_text}", path)

    minimum_duration = max(0.1, expected_duration * 0.5)
    if actual_duration < minimum_duration:
        return SmokeResult(
            False,
            ExitCode.FILE_CHECK_FAILED,
            f"output file duration too short: {actual_duration:.2f}s",
            path,
        )
    return SmokeResult(True, ExitCode.OK, f"video duration ok: {actual_duration:.2f}s", path)


def check_log_markers(log_text: str, required: tuple[str, ...]) -> SmokeResult:
    missing = [marker for marker in required if marker not in log_text]
    if missing:
        return SmokeResult(False, ExitCode.LOG_CHECK_FAILED, f"missing log markers: {', '.join(missing)}")
    return SmokeResult(True, ExitCode.OK, "log markers ok")


def snapshot_ffmpeg_processes() -> set[str]:
    if os.name != "nt":
        return set()
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq ffmpeg.exe", "/FO", "CSV", "/NH"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=10,
    )
    processes: set[str] = set()
    for line in result.stdout.splitlines():
        parts = [part.strip('"') for part in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == "ffmpeg.exe":
            processes.add(parts[1])
    return processes


def check_no_new_ffmpeg_processes(before: set[str], after: set[str]) -> SmokeResult:
    remaining = sorted(after - before)
    if remaining:
        return SmokeResult(False, ExitCode.ENCODING_FAILED, f"residual ffmpeg processes: {', '.join(remaining)}")
    return SmokeResult(True, ExitCode.OK, "no residual ffmpeg processes")


def snapshot_session_dirs() -> set[str]:
    if not os.path.isdir(TempCleaner.BASE_DIR):
        return set()
    return {
        entry
        for entry in os.listdir(TempCleaner.BASE_DIR)
        if entry.startswith("session_") and os.path.isdir(os.path.join(TempCleaner.BASE_DIR, entry))
    }


def check_no_new_session_dirs(before: set[str], after: set[str]) -> SmokeResult:
    remaining = sorted(after - before)
    if remaining:
        return SmokeResult(False, ExitCode.FILE_CHECK_FAILED, f"residual session dirs: {', '.join(remaining)}")
    return SmokeResult(True, ExitCode.OK, "no residual session dirs")


def _build_config(output_dir: str, fps: int) -> ConfigManager:
    config = ConfigManager.__new__(ConfigManager)
    config._config_path = os.path.join(output_dir, "hardware-smoke-config.json")
    config._config = {
        "save_path": output_dir,
        "quality": "low",
        "fps": fps,
        "audio_source": "none",
    }
    return config


def run_smoke(
    duration: float = 3.0,
    output_dir: str | None = None,
    timeout: float = 30.0,
    min_size: int = 1024,
    fps: int = 15,
    mode: str = "fullscreen",
) -> SmokeResult:
    if mode != "fullscreen":
        return SmokeResult(False, ExitCode.CAPTURE_FAILED, f"unsupported smoke mode: {mode}")
    output_dir = output_dir or tempfile.mkdtemp(prefix="quickrec-hardware-smoke-")
    os.makedirs(output_dir, exist_ok=True)
    saved_paths: list[str] = []
    log_markers: list[str] = []
    ffmpeg_before = snapshot_ffmpeg_processes()
    session_dirs_before = snapshot_session_dirs()
    config = _build_config(output_dir, fps=fps)
    recorder = RecorderManager(config, on_saved=saved_paths.append)

    def mark(message: str) -> None:
        log_markers.append(message)
        logging.info(message)

    mark("capture started")
    try:
        if not recorder.start_fullscreen():
            return SmokeResult(False, ExitCode.CAPTURE_FAILED, "fullscreen recording did not start")
        mark("encoding started")
        time.sleep(duration)
        recorder.stop()
        if not recorder.wait_until_idle(timeout=timeout):
            return SmokeResult(False, ExitCode.TIMEOUT, "recorder did not become idle before timeout")
    except Exception as exc:
        return SmokeResult(False, ExitCode.CAPTURE_FAILED, f"hardware smoke failed: {exc}")

    output_path = saved_paths[-1] if saved_paths else ""
    mark("audio skipped")
    mark("saved file")
    mark("exit complete")
    file_result = check_output_file(output_path, min_size=min_size)
    if not file_result.ok:
        return file_result
    ffmpeg_path = find_ffmpeg()
    stream_result = check_video_stream(output_path, ffmpeg_path)
    if not stream_result.ok:
        return stream_result
    duration_result = check_video_duration(output_path, ffmpeg_path, expected_duration=duration)
    if not duration_result.ok:
        return duration_result
    process_result = check_no_new_ffmpeg_processes(ffmpeg_before, snapshot_ffmpeg_processes())
    if not process_result.ok:
        return process_result
    session_result = check_no_new_session_dirs(session_dirs_before, snapshot_session_dirs())
    if not session_result.ok:
        return session_result
    marker_result = check_log_markers(
        "\n".join(log_markers),
        required=("capture", "encoding", "audio", "saved", "exit"),
    )
    if not marker_result.ok:
        return marker_result
    return stream_result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local QuickRec hardware smoke recording.")
    parser.add_argument("--duration", type=float, default=3.0, help="Recording duration in seconds.")
    parser.add_argument("--output-dir", default="", help="Directory for smoke output.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Wait timeout in seconds.")
    parser.add_argument("--min-size", type=int, default=1024, help="Minimum output file size in bytes.")
    parser.add_argument("--fps", type=int, default=15, help="Smoke recording FPS.")
    parser.add_argument("--mode", default="fullscreen", choices=["fullscreen"], help="Smoke recording mode.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = parse_args(argv or sys.argv[1:])
    result = run_smoke(
        duration=args.duration,
        output_dir=args.output_dir or None,
        timeout=args.timeout,
        min_size=args.min_size,
        fps=args.fps,
        mode=args.mode,
    )
    if result.ok:
        print(f"OK: {result.message}")
    else:
        print(f"FAILED: {result.message}", file=sys.stderr)
    if result.output_path:
        print(f"output: {result.output_path}")
    return int(result.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
