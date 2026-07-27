from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from utils.thumbnail_cache import (
    MEBIBYTE,
    ThumbnailCacheStore,
    ThumbnailFingerprint,
    normalize_thumbnail_source_path,
    resolve_thumbnail_cache_root,
)


def _write_source(path: Path, payload: bytes = b"video") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _commit(
    store: ThumbnailCacheStore,
    fingerprint: ThumbnailFingerprint,
    payload: bytes,
    *,
    accessed_at: str,
) -> Path:
    temp = store.create_temp_path(fingerprint.cache_key)
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(payload)
    result = store.commit(
        temp,
        fingerprint,
        width=320,
        height=180,
        source_position_sec=1.5,
        accessed_at=accessed_at,
    )
    assert result.ok, result.error
    assert result.entry is not None
    return result.path


def test_resolve_cache_root_uses_local_app_data(tmp_path: Path) -> None:
    root = resolve_thumbnail_cache_root(tmp_path)

    assert root == tmp_path / "QuickRec" / "ThumbnailCache" / "v1"


def test_normalize_source_path_is_stable_for_windows_case_and_separators() -> None:
    left = normalize_thumbnail_source_path(r"E:\Videos\Demo Clip.mp4")
    right = normalize_thumbnail_source_path("e:/videos/demo clip.mp4")

    if os.name == "nt":
        assert left == right
    assert "\\" not in left


def test_fingerprint_is_stable_until_file_facts_change(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "中文 空格" / "demo.mp4", b"abc")
    first = ThumbnailFingerprint.from_file("material-1", source)
    second = ThumbnailFingerprint.from_file("material-1", source)

    assert first == second
    assert first.cache_key == second.cache_key

    source.write_bytes(b"changed-payload")
    os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1_000_000))
    changed = ThumbnailFingerprint.from_file("material-1", source)

    assert changed.cache_key != first.cache_key


def test_temp_file_is_not_visible_until_commit(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "video.mp4")
    store = ThumbnailCacheStore(tmp_path / "cache")
    fingerprint = ThumbnailFingerprint.from_file("material-1", source)
    temp = store.create_temp_path(fingerprint.cache_key)
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(b"jpeg")

    assert store.lookup(fingerprint).entry is None
    assert not store.index_path.exists()


def test_commit_moves_temp_file_and_persists_relative_index(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "video.mp4")
    store = ThumbnailCacheStore(tmp_path / "cache")
    fingerprint = ThumbnailFingerprint.from_file("material-1", source)

    final_path = _commit(store, fingerprint, b"jpeg-bytes", accessed_at="2026-07-27T10:00:00+08:00")
    payload = json.loads(store.index_path.read_text(encoding="utf-8"))

    assert final_path.is_file()
    assert final_path.read_bytes() == b"jpeg-bytes"
    assert payload["schema_version"] == 1
    entry = payload["entries"][fingerprint.cache_key]
    assert entry["relative_path"] == f"images/{fingerprint.cache_key}.jpg"
    assert entry["material_id"] == "material-1"
    assert entry["width"] == 320
    assert entry["height"] == 180
    assert entry["source_position_sec"] == 1.5


def test_lookup_invalidates_entry_when_source_fingerprint_changes(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "video.mp4", b"one")
    store = ThumbnailCacheStore(tmp_path / "cache")
    first = ThumbnailFingerprint.from_file("material-1", source)
    _commit(store, first, b"jpeg-one", accessed_at="2026-07-27T10:00:00+08:00")

    source.write_bytes(b"two-two")
    os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1_000_000))
    changed = ThumbnailFingerprint.from_file("material-1", source)

    assert store.lookup(changed).entry is None
    assert store.lookup(first).entry is not None


def test_missing_cache_file_is_removed_from_index(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "video.mp4")
    store = ThumbnailCacheStore(tmp_path / "cache")
    fingerprint = ThumbnailFingerprint.from_file("material-1", source)
    cached = _commit(store, fingerprint, b"jpeg", accessed_at="2026-07-27T10:00:00+08:00")
    cached.unlink()

    result = store.lookup(fingerprint)
    reloaded = store.load()

    assert result.entry is None
    assert fingerprint.cache_key not in reloaded.entries


def test_corrupt_index_is_preserved_and_rebuilt_empty(tmp_path: Path) -> None:
    store = ThumbnailCacheStore(tmp_path / "cache")
    store.root.mkdir(parents=True)
    store.index_path.write_text("{broken", encoding="utf-8")

    loaded = store.load()

    assert loaded.ok
    assert loaded.recovered
    assert loaded.entries == {}
    assert not store.index_path.exists()
    assert list(store.root.glob("index.corrupt-*.json"))


def test_prune_removes_oldest_unprotected_entries_only(tmp_path: Path) -> None:
    store = ThumbnailCacheStore(tmp_path / "cache", max_bytes=12)
    fingerprints = []
    for index, accessed_at in enumerate(
        (
            "2026-07-27T10:00:00+08:00",
            "2026-07-27T10:01:00+08:00",
            "2026-07-27T10:02:00+08:00",
        )
    ):
        source = _write_source(tmp_path / f"video-{index}.mp4", bytes([index]))
        fingerprint = ThumbnailFingerprint.from_file(f"material-{index}", source)
        _commit(store, fingerprint, b"123456", accessed_at=accessed_at)
        fingerprints.append(fingerprint)

    result = store.prune(protected_keys={fingerprints[0].cache_key})

    assert result.ok
    assert result.removed_keys == (fingerprints[1].cache_key,)
    assert result.remaining_bytes == 12
    assert store.lookup(fingerprints[0]).entry is not None
    assert store.lookup(fingerprints[1]).entry is None
    assert store.lookup(fingerprints[2]).entry is not None


def test_prune_never_deletes_protected_entry_even_if_limit_remains_exceeded(tmp_path: Path) -> None:
    store = ThumbnailCacheStore(tmp_path / "cache", max_bytes=1)
    source = _write_source(tmp_path / "video.mp4")
    fingerprint = ThumbnailFingerprint.from_file("material-1", source)
    _commit(store, fingerprint, b"123456", accessed_at="2026-07-27T10:00:00+08:00")

    result = store.prune(protected_keys={fingerprint.cache_key})

    assert result.ok
    assert result.removed_keys == ()
    assert result.remaining_bytes == 6
    assert store.lookup(fingerprint).entry is not None


def test_prune_continues_after_one_cache_file_cannot_be_deleted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ThumbnailCacheStore(tmp_path / "cache", max_bytes=6)
    fingerprints = []
    for index in range(3):
        source = _write_source(tmp_path / f"video-{index}.mp4", bytes([index]))
        fingerprint = ThumbnailFingerprint.from_file(
            f"material-{index}",
            source,
        )
        _commit(
            store,
            fingerprint,
            b"123456",
            accessed_at=f"2026-07-27T10:0{index}:00+08:00",
        )
        fingerprints.append(fingerprint)
    blocked_name = store.cache_path(fingerprints[0].cache_key).name
    original_unlink = Path.unlink

    def guarded_unlink(path: Path, *args, **kwargs):
        if path.name == blocked_name:
            raise PermissionError("locked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", guarded_unlink)

    result = store.prune()

    assert not result.ok
    assert len(result.removed_keys) == 2
    assert result.remaining_bytes == 6
    assert store.cache_path(fingerprints[0].cache_key).is_file()


def test_store_recovers_after_entire_cache_directory_is_deleted(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "video.mp4")
    store = ThumbnailCacheStore(tmp_path / "cache")
    first = ThumbnailFingerprint.from_file("material-1", source)
    _commit(store, first, b"jpeg", accessed_at="2026-07-27T10:00:00+08:00")

    for child in sorted(store.root.rglob("*"), reverse=True):
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    store.root.rmdir()

    final_path = _commit(store, first, b"rebuilt", accessed_at="2026-07-27T11:00:00+08:00")

    assert final_path.read_bytes() == b"rebuilt"
    assert store.lookup(first).entry is not None


def test_default_limit_is_500_mebibytes(tmp_path: Path) -> None:
    store = ThumbnailCacheStore(tmp_path / "cache")

    assert store.max_bytes == 500 * MEBIBYTE


def test_parallel_commits_preserve_every_cache_entry(tmp_path: Path) -> None:
    store = ThumbnailCacheStore(tmp_path / "cache")
    fingerprints = [
        ThumbnailFingerprint.from_file(
            f"material-{index}",
            _write_source(tmp_path / f"source-{index}.mp4", bytes([index])),
        )
        for index in range(8)
    ]

    def commit_one(fingerprint: ThumbnailFingerprint) -> None:
        _commit(
            store,
            fingerprint,
            fingerprint.material_id.encode("utf-8"),
            accessed_at="2026-07-27T12:00:00+08:00",
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(commit_one, fingerprints))

    loaded = store.load()
    assert loaded.ok
    assert set(loaded.entries) == {item.cache_key for item in fingerprints}


def test_cache_operations_do_not_modify_business_json(tmp_path: Path) -> None:
    project = tmp_path / "project.qrproj"
    projects = tmp_path / "projects.json"
    recordings = tmp_path / "recordings.json"
    for path, content in (
        (project, '{"project_id":"p1"}\n'),
        (projects, '{"entries":[]}\n'),
        (recordings, '{"items":[]}\n'),
    ):
        path.write_text(content, encoding="utf-8")
    before = {path: path.read_bytes() for path in (project, projects, recordings)}

    source = _write_source(tmp_path / "video.mp4")
    store = ThumbnailCacheStore(tmp_path / "cache")
    fingerprint = ThumbnailFingerprint.from_file("material-1", source)
    _commit(store, fingerprint, b"jpeg", accessed_at="2026-07-27T12:00:00+08:00")
    store.lookup(fingerprint, accessed_at="2026-07-27T12:01:00+08:00")
    store.prune()

    assert {path: path.read_bytes() for path in before} == before


def test_latest_material_cache_remains_available_after_source_is_missing(tmp_path: Path) -> None:
    source = _write_source(tmp_path / "video.mp4")
    store = ThumbnailCacheStore(tmp_path / "cache")
    fingerprint = ThumbnailFingerprint.from_file("material-1", source)
    cached = _commit(
        store,
        fingerprint,
        b"historical-preview",
        accessed_at="2026-07-27T12:00:00+08:00",
    )
    source.unlink()

    result = store.find_latest_for_material("material-1")

    assert result.entry is not None
    assert result.path == cached
