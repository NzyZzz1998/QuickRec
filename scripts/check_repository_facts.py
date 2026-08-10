from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

MOJIBAKE_MARKERS = (
    "鍙戝竷",
    "璇存槑",
    "锛",
    "銆",
    "鈥",
    "闁",
    "馃",
    "�",
)
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
APP_VERSION_RE = re.compile(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("release manifest must use schema_version 1")
    return data


def _documentation_files(root: Path) -> tuple[Path, ...]:
    files = set(root.glob("*.md"))
    doc_root = root / "doc"
    if doc_root.is_dir():
        files.update(doc_root.rglob("*.md"))
    return tuple(sorted(files))


def _relative_name(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _local_link_target(source: Path, raw_target: str) -> Path | None:
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(("#", "http://", "https://", "mailto:", "data:")):
        return None
    if re.match(r"^[A-Za-z]:[/\\]", target):
        return None
    target = unquote(target.split("#", 1)[0]).strip()
    if not target:
        return None
    return (source.parent / target).resolve()


def check_document_tree(root: Path) -> list[str]:
    issues: list[str] = []
    for path in _documentation_files(root):
        name = _relative_name(path, root)
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            issues.append(f"{name}: 不是严格 UTF-8（{exc}）")
            continue

        marker = next((item for item in MOJIBAKE_MARKERS if item in text), None)
        if marker is not None:
            issues.append(f"{name}: 检测到疑似乱码标记 {marker!r}")

        for match in MARKDOWN_LINK_RE.finditer(text):
            raw_target = match.group(1)
            target = _local_link_target(path, raw_target)
            if target is not None and not target.exists():
                issues.append(f"{name}: 本地链接不存在：{raw_target}")
    return issues


def _read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def check_release_identity(root: Path, manifest: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    version = str(manifest.get("version", ""))
    release_url = str(manifest.get("release_url", ""))
    tag = str(manifest.get("tag", ""))

    readme = _read_utf8(root / "README.md")
    if version not in readme or release_url not in readme:
        issues.append("README.md: 正式版本或 Release 地址与 release-manifest.json 不一致")

    current = _read_utf8(root / "doc" / "current.md")
    if f"当前公开正式版本：{version}" not in current or f"`{tag}`" not in current:
        issues.append("doc/current.md: 当前正式版本或 tag 与 release-manifest.json 不一致")

    version_text = _read_utf8(root / "src" / "version.py")
    version_match = APP_VERSION_RE.search(version_text)
    if version_match is None or version_match.group(1) != version:
        issues.append("src/version.py: APP_VERSION 与 release-manifest.json 不一致")
    return issues


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def check_media_tools(
    root: Path,
    manifest: dict[str, Any],
    *,
    verify_hashes: bool,
) -> list[str]:
    issues: list[str] = []
    tools = manifest.get("media_tools", {})
    if not isinstance(tools, dict):
        return ["release-manifest.json: media_tools 必须是对象"]

    for filename in ("ffmpeg.exe", "ffprobe.exe"):
        path = root / "ffmpeg" / filename
        if not path.is_file():
            issues.append(f"ffmpeg/{filename}: 文件不存在")
            continue
        if not verify_hashes:
            continue
        entry = tools.get(filename, {})
        expected = entry.get("sha256", "") if isinstance(entry, dict) else ""
        actual = _sha256(path)
        if not expected or actual != str(expected).upper():
            issues.append(f"ffmpeg/{filename}: SHA256 与 release-manifest.json 不一致")
    return issues


def check_repository(root: Path, *, verify_media_hashes: bool) -> list[str]:
    manifest = load_manifest(root / "release-manifest.json")
    issues = check_document_tree(root)
    issues.extend(check_release_identity(root, manifest))
    if verify_media_hashes:
        issues.extend(check_media_tools(root, manifest, verify_hashes=True))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description="校验 QuickRec 文档、版本事实源与可选的媒体工具身份。"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--verify-media-hashes", action="store_true")
    args = parser.parse_args()

    try:
        issues = check_repository(
            args.root.resolve(),
            verify_media_hashes=args.verify_media_hashes,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    for issue in issues:
        print(f"ERROR: {issue}")
    if issues:
        return 1
    print("Repository facts: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
