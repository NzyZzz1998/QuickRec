from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.stage_ffmpeg import sha256_file as _sha256_file
from scripts.stage_ffmpeg import verify_ffmpeg as _verify_ffmpeg


def tree_size(path: str | Path) -> int:
    return sum(file.stat().st_size for file in Path(path).rglob("*") if file.is_file())


def read_dependencies(paths: list[str | Path]) -> list[str]:
    dependencies: list[str] = []
    for path in paths:
        for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith(("#", "-r")) and line not in dependencies:
                dependencies.append(line)
    return dependencies


def current_git_commit(repo_dir: str | Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def artifact_identity(path: Path, *, relative_to: Path | None = None) -> dict[str, str | int]:
    display_path = path.name if relative_to is None else path.relative_to(relative_to).as_posix()
    return {
        "path": display_path,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def build_manifest(
    *,
    package_dir: str | Path,
    release_zip: str | Path,
    version: str,
    git_commit: str,
    built_at_utc: str,
    python_version: str,
    dependencies: list[str],
    ffmpeg_version: str,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    zip_path = Path(release_zip)
    executable = package_path / "QuickRec-Lite.exe"
    ffmpeg = package_path / "_internal" / "ffmpeg" / "ffmpeg.exe"
    for required in (package_path, executable, ffmpeg, zip_path):
        if not required.exists():
            raise FileNotFoundError(f"Release artifact missing: {required}")

    return {
        "schema_version": 1,
        "product_id": "QuickRec.Lite",
        "product_name": "QuickRec Lite",
        "version": version,
        "git_commit": git_commit,
        "built_at_utc": built_at_utc,
        "platform": "Windows x64",
        "python_version": python_version,
        "dependencies": dependencies,
        "package": {
            "directory": package_path.name,
            "size_bytes": tree_size(package_path),
        },
        "artifacts": {
            "executable": artifact_identity(executable, relative_to=package_path),
            "ffmpeg": {
                **artifact_identity(ffmpeg, relative_to=package_path),
                "version": ffmpeg_version,
            },
            "zip": artifact_identity(zip_path),
        },
    }


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_name(f".{output.name}.tmp")
    temp_output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_output, output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the QuickRec Lite release manifest.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--zip", dest="release_zip", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--version", default="v0.1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package_dir = Path(args.package_dir)
    ffmpeg = package_dir / "_internal" / "ffmpeg" / "ffmpeg.exe"
    ffmpeg_identity = _verify_ffmpeg(ffmpeg)
    manifest = build_manifest(
        package_dir=package_dir,
        release_zip=args.release_zip,
        version=args.version,
        git_commit=current_git_commit(args.repo_dir),
        built_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        python_version=platform.python_version(),
        dependencies=read_dependencies(["requirements.txt", "requirements-dev.txt"]),
        ffmpeg_version=str(ffmpeg_identity["version"]),
    )
    write_manifest(args.output, manifest)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
