from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.check_repository_facts import (
    check_document_tree,
    check_media_tools,
    check_release_identity,
    load_manifest,
)


def _write_manifest(root: Path, *, tool_hash: str = "") -> Path:
    manifest = {
        "schema_version": 1,
        "product": "QuickRec Full",
        "version": "v1.9.5",
        "tag": "v1.9.5",
        "release_url": "https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.9.5",
        "archive": {
            "name": "QuickRec-v1.9.5-win-x64.zip",
            "sha256": "A" * 64,
        },
        "media_tools": {
            "version": "8.0.1",
            "ffmpeg.exe": {"sha256": tool_hash or "B" * 64},
            "ffprobe.exe": {"sha256": tool_hash or "C" * 64},
        },
    }
    path = root / "release-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_document_tree_rejects_non_utf8_markdown(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_bytes(b"\xff\xfe")

    issues = check_document_tree(tmp_path)

    assert any("UTF-8" in issue for issue in issues)


def test_document_tree_rejects_mojibake(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# 鍙戝竷璇存槑", encoding="utf-8")

    issues = check_document_tree(tmp_path)

    assert any("乱码" in issue for issue in issues)


def test_document_tree_rejects_missing_local_link(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "[当前事实](doc/current.md)",
        encoding="utf-8",
    )

    issues = check_document_tree(tmp_path)

    assert any("doc/current.md" in issue for issue in issues)


def test_release_identity_requires_readme_and_current_to_match_manifest(
    tmp_path: Path,
) -> None:
    manifest = load_manifest(_write_manifest(tmp_path))
    (tmp_path / "README.md").write_text(
        "[Release](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.9.4)",
        encoding="utf-8",
    )
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "current.md").write_text(
        "当前公开正式版本：v1.9.4",
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "version.py").write_text(
        'APP_VERSION = "v1.9.4"',
        encoding="utf-8",
    )

    issues = check_release_identity(tmp_path, manifest)

    assert len(issues) == 3


def test_media_tool_hashes_are_checked_when_requested(tmp_path: Path) -> None:
    ffmpeg_dir = tmp_path / "ffmpeg"
    ffmpeg_dir.mkdir()
    ffmpeg = ffmpeg_dir / "ffmpeg.exe"
    ffprobe = ffmpeg_dir / "ffprobe.exe"
    ffmpeg.write_bytes(b"ffmpeg")
    ffprobe.write_bytes(b"ffprobe")
    expected_hash = hashlib.sha256(b"ffmpeg").hexdigest().upper()
    manifest = load_manifest(_write_manifest(tmp_path, tool_hash=expected_hash))

    issues = check_media_tools(tmp_path, manifest, verify_hashes=True)

    assert not any("ffmpeg.exe" in issue for issue in issues)
    assert any("ffprobe.exe" in issue and "SHA256" in issue for issue in issues)


def test_current_repository_facts_are_consistent() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = load_manifest(root / "release-manifest.json")

    assert check_document_tree(root) == []
    assert check_release_identity(root, manifest) == []
    assert check_media_tools(root, manifest, verify_hashes=True) == []


def test_ci_runs_repository_facts_and_shared_ffmpeg_staging_script() -> None:
    root = Path(__file__).resolve().parents[1]
    ci_text = (root / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "python scripts/check_repository_facts.py" in ci_text
    assert ci_text.count("pwsh -File scripts/stage_ffmpeg.ps1") == 2
    assert "choco install ffmpeg" not in ci_text


def test_ffmpeg_staging_script_pins_version_and_validates_pair() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "stage_ffmpeg.ps1").read_text(encoding="utf-8")

    assert '[string]$Version = "8.0.1"' in script
    assert "--version=$Version" in script
    assert 'Join-Path $candidate.DirectoryName "ffprobe.exe"' in script
    assert '"ffmpeg version $Version"' in script


def test_direct_dependencies_are_exactly_pinned() -> None:
    root = Path(__file__).resolve().parents[1]
    for filename in ("requirements.txt", "requirements-dev.txt"):
        lines = (root / filename).read_text(encoding="utf-8").splitlines()
        direct = [line for line in lines if line and not line.startswith(("#", "-r "))]
        assert direct
        assert all("==" in line for line in direct)
