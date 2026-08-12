from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from scripts.release_manifest import build_manifest, write_manifest
from scripts.stage_ffmpeg import (
    FFMPEG_ARCHIVE_SHA256,
    FFMPEG_ARCHIVE_URL,
    FFMPEG_EXECUTABLE_SHA256,
    FFMPEG_VERSION_LINE,
    extract_locked_ffmpeg,
    sha256_file,
)

RUNTIME_PINS = {
    "pynput==1.8.2",
    "dxcam==0.3.0",
    "comtypes==1.4.16",
    "numpy==2.4.6",
    "opencv-python==4.13.0.92",
    "Pillow==12.2.0",
    "pyinstaller==6.20.0",
    "pyinstaller-hooks-contrib==2026.6",
    "PyQt5==5.15.11",
    "PyQt5-Qt5==5.15.2",
    "PyQt5_sip==12.18.0",
    "pystray==0.19.5",
    "six==1.17.0",
    "pyaudio==0.2.14",
    "soundcard==0.4.6",
    "winotify==1.1.0",
}

DEV_PINS = {
    "pytest==9.0.3",
    "pytest-cov==7.1.0",
    "ruff==0.15.20",
    "mypy==2.1.0",
}


def _requirement_lines(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "-r"))
    }


def test_direct_dependencies_are_exactly_pinned():
    assert _requirement_lines(Path("requirements.txt")) == RUNTIME_PINS
    assert _requirement_lines(Path("requirements-dev.txt")) == DEV_PINS


def test_ffmpeg_distribution_identity_is_fixed():
    assert FFMPEG_ARCHIVE_URL == (
        "https://github.com/GyanD/codexffmpeg/releases/download/8.0.1/"
        "ffmpeg-8.0.1-essentials_build.zip"
    )
    assert FFMPEG_ARCHIVE_SHA256 == "E2AAEAA0FDBC397D4794828086424D4AAA2102CEF1FB6874F6FFD29C0B88B673"
    assert FFMPEG_EXECUTABLE_SHA256 == "5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D"
    assert FFMPEG_VERSION_LINE == "ffmpeg version 8.0.1-essentials_build-www.gyan.dev Copyright (c) 2000-2025 the FFmpeg developers"


def test_extract_locked_ffmpeg_uses_bin_member_and_hash(tmp_path: Path):
    payload = b"locked-ffmpeg"
    archive = tmp_path / "ffmpeg.zip"
    output = tmp_path / "stage" / "ffmpeg.exe"
    expected_hash = hashlib.sha256(payload).hexdigest().upper()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("ffmpeg-locked/bin/ffmpeg.exe", payload)
        bundle.writestr("ffmpeg-locked/bin/ffprobe.exe", b"not-selected")

    extract_locked_ffmpeg(archive, output, expected_hash=expected_hash)

    assert output.read_bytes() == payload
    assert sha256_file(output) == expected_hash


def test_extract_locked_ffmpeg_rejects_hash_mismatch(tmp_path: Path):
    archive = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("ffmpeg-locked/bin/ffmpeg.exe", b"unexpected")

    with pytest.raises(ValueError, match="SHA256"):
        extract_locked_ffmpeg(archive, tmp_path / "ffmpeg.exe", expected_hash="0" * 64)


def test_release_manifest_contains_reproducible_artifact_identity(tmp_path: Path):
    package = tmp_path / "QuickRec-Lite"
    executable = package / "QuickRec-Lite.exe"
    ffmpeg = package / "_internal" / "ffmpeg" / "ffmpeg.exe"
    release_zip = tmp_path / "QuickRec-Lite-v0.1-win-x64.zip"
    executable.parent.mkdir(parents=True)
    ffmpeg.parent.mkdir(parents=True)
    executable.write_bytes(b"lite-exe")
    ffmpeg.write_bytes(b"ffmpeg")
    release_zip.write_bytes(b"zip")

    manifest = build_manifest(
        package_dir=package,
        release_zip=release_zip,
        version="v0.1",
        git_commit="abc123",
        built_at_utc="2026-08-11T00:00:00Z",
        python_version="3.12.10",
        dependencies=["dxcam==0.3.0", "pytest==9.0.3"],
        ffmpeg_version=FFMPEG_VERSION_LINE,
    )

    assert manifest["schema_version"] == 1
    assert manifest["product_id"] == "QuickRec.Lite"
    assert manifest["version"] == "v0.1"
    assert manifest["git_commit"] == "abc123"
    assert manifest["package"]["size_bytes"] == 14
    assert manifest["artifacts"]["executable"]["sha256"] == sha256_file(executable)
    assert manifest["artifacts"]["ffmpeg"]["sha256"] == sha256_file(ffmpeg)
    assert manifest["artifacts"]["zip"]["sha256"] == sha256_file(release_zip)
    assert manifest["dependencies"] == ["dxcam==0.3.0", "pytest==9.0.3"]

    output = tmp_path / "release-manifest.json"
    write_manifest(output, manifest)
    assert json.loads(output.read_text(encoding="utf-8")) == manifest
