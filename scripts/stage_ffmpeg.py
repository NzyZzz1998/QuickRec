from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from hashlib import sha256
from pathlib import Path

FFMPEG_ARCHIVE_URL = (
    "https://github.com/GyanD/codexffmpeg/releases/download/8.0.1/"
    "ffmpeg-8.0.1-essentials_build.zip"
)
FFMPEG_ARCHIVE_SHA256 = "E2AAEAA0FDBC397D4794828086424D4AAA2102CEF1FB6874F6FFD29C0B88B673"
FFMPEG_EXECUTABLE_SHA256 = "5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D"
FFMPEG_VERSION_LINE = (
    "ffmpeg version 8.0.1-essentials_build-www.gyan.dev "
    "Copyright (c) 2000-2025 the FFmpeg developers"
)


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _require_hash(path: Path, expected_hash: str, label: str) -> None:
    actual_hash = sha256_file(path)
    if actual_hash != expected_hash.upper():
        raise ValueError(f"{label} SHA256 mismatch: expected {expected_hash}, got {actual_hash}")


def extract_locked_ffmpeg(
    archive: str | Path,
    output: str | Path,
    *,
    expected_hash: str = FFMPEG_EXECUTABLE_SHA256,
) -> Path:
    archive_path = Path(archive)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_name(f".{output_path.name}.tmp")

    with zipfile.ZipFile(archive_path) as bundle:
        members = [
            member
            for member in bundle.infolist()
            if member.filename.replace("\\", "/").lower().endswith("/bin/ffmpeg.exe")
        ]
        if len(members) != 1:
            raise ValueError(f"FFmpeg archive must contain exactly one bin/ffmpeg.exe, found {len(members)}")
        with bundle.open(members[0]) as source, temp_output.open("wb") as destination:
            shutil.copyfileobj(source, destination, length=1024 * 1024)

    try:
        _require_hash(temp_output, expected_hash, "FFmpeg executable")
        os.replace(temp_output, output_path)
    finally:
        temp_output.unlink(missing_ok=True)
    return output_path


def verify_ffmpeg(path: str | Path) -> dict[str, str | int]:
    executable = Path(path)
    if not executable.is_file():
        raise FileNotFoundError(f"FFmpeg executable missing: {executable}")
    _require_hash(executable, FFMPEG_EXECUTABLE_SHA256, "FFmpeg executable")
    completed = subprocess.run(
        [str(executable), "-version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"FFmpeg version check failed with exit code {completed.returncode}")
    first_line = completed.stdout.splitlines()[0] if completed.stdout else ""
    if first_line != FFMPEG_VERSION_LINE:
        raise ValueError(f"FFmpeg version mismatch: {first_line!r}")
    return {
        "path": str(executable),
        "size_bytes": executable.stat().st_size,
        "sha256": sha256_file(executable),
        "version": first_line,
    }


def _download_archive(destination: Path) -> None:
    request = urllib.request.Request(FFMPEG_ARCHIVE_URL, headers={"User-Agent": "QuickRec-Lite-CI/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    _require_hash(destination, FFMPEG_ARCHIVE_SHA256, "FFmpeg archive")


def stage_ffmpeg(output: str | Path, archive: str | Path | None = None) -> dict[str, str | int]:
    if archive is not None:
        archive_path = Path(archive)
        _require_hash(archive_path, FFMPEG_ARCHIVE_SHA256, "FFmpeg archive")
        extract_locked_ffmpeg(archive_path, output)
    else:
        with tempfile.TemporaryDirectory(prefix="quickrec-lite-ffmpeg-") as temp_dir:
            archive_path = Path(temp_dir) / "ffmpeg-8.0.1-essentials_build.zip"
            _download_archive(archive_path)
            extract_locked_ffmpeg(archive_path, output)
    return verify_ffmpeg(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage the locked QuickRec Lite FFmpeg executable.")
    parser.add_argument("--output", default="ffmpeg/ffmpeg.exe", help="Destination ffmpeg.exe path.")
    parser.add_argument("--archive", default="", help="Optional pre-downloaded locked archive.")
    parser.add_argument("--verify-only", action="store_true", help="Only verify an existing executable.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = verify_ffmpeg(args.output) if args.verify_only else stage_ffmpeg(args.output, args.archive or None)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
