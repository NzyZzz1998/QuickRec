from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from services.recording_library import (
    DirectoryScanResult,
    MigrationResult,
    RecordingLibraryService,
)
from utils.media_metadata import MediaMetadataResult
from utils.recording_library_store import MaterialItem


def _material(path: Path, material_id: str) -> MaterialItem:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"video")
    stat = path.stat()
    return MaterialItem(
        id=material_id,
        file_path=str(path),
        file_name=path.name,
        directory=str(path.parent),
        mode="fullscreen",
        audio_source="none",
        created_at="2026-07-27T10:00:00+08:00",
        duration_sec=2,
        width=1920,
        height=1080,
        fps=60,
        file_size_bytes=stat.st_size,
        file_modified_ns=stat.st_mtime_ns,
    )


def test_add_recording_emits_preview_trigger_after_success(tmp_path: Path) -> None:
    service = RecordingLibraryService(tmp_path / "recordings.json")
    events = []
    service.subscribe_changes(events.append)
    video = tmp_path / "QuickRec_20260727_100000.mp4"
    video.write_bytes(b"video")

    result = service.add_recording(
        video,
        metadata={
            "mode": "fullscreen",
            "audio_source": "none",
            "duration_sec": 2,
            "width": 1920,
            "height": 1080,
            "fps": 60,
        },
        diagnostic_dir=None,
        item_id="material-1",
    )

    assert result.ok
    assert len(events) == 1
    assert events[0].reason == "added"
    assert [item.id for item in events[0].items] == ["material-1"]


def test_failed_write_does_not_emit_preview_trigger(tmp_path: Path) -> None:
    service = RecordingLibraryService(tmp_path / "recordings.json")
    events = []
    service.subscribe_changes(events.append)
    material = _material(tmp_path / "video.mp4", "material-1")

    with patch(
        "services.recording_library.save_library",
        side_effect=OSError("denied"),
    ):
        try:
            service.add(material)
        except OSError:
            pass

    assert events == []


def test_relink_emits_changed_material_only_after_validation(tmp_path: Path) -> None:
    service = RecordingLibraryService(tmp_path / "recordings.json")
    original = _material(tmp_path / "old.mp4", "material-1")
    assert service.add(original).ok
    events = []
    service.subscribe_changes(events.append)
    target = tmp_path / "中文 空格" / "new.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"new-video")

    with patch(
        "services.recording_library.probe_media",
        return_value=MediaMetadataResult(
            True,
            duration_sec=3,
            width=1280,
            height=720,
            fps=30,
        ),
    ):
        result = service.relink("material-1", target)

    assert result.ok
    assert len(events) == 1
    assert events[0].reason == "relinked"
    assert events[0].items[0].file_path == str(target)


def test_scan_commit_emits_only_newly_added_items(tmp_path: Path) -> None:
    service = RecordingLibraryService(tmp_path / "recordings.json")
    existing = _material(tmp_path / "existing.mp4", "existing")
    added = _material(tmp_path / "added.mp4", "added")
    assert service.add(existing).ok
    events = []
    service.subscribe_changes(events.append)
    scan = DirectoryScanResult(
        True,
        tmp_path,
        [existing, added],
        scanned_count=2,
    )

    result = service.commit_scan(
        scan,
        imported_at="2026-07-27T11:00:00+08:00",
    )

    assert result.ok
    assert len(events) == 1
    assert events[0].reason == "scan_committed"
    assert [item.id for item in events[0].items] == ["added"]


def test_migration_commit_emits_only_newly_added_items(tmp_path: Path) -> None:
    service = RecordingLibraryService(tmp_path / "recordings.json")
    existing = _material(tmp_path / "existing.mp4", "existing")
    added = _material(tmp_path / "added.mp4", "added")
    assert service.add(existing).ok
    events = []
    service.subscribe_changes(events.append)
    preview = MigrationResult(
        True,
        tmp_path / "legacy.json",
        [added, existing],
        added_count=1,
    )

    result = service.commit_migration(preview)

    assert result.ok
    assert len(events) == 1
    assert events[0].reason == "migration_committed"
    assert [item.id for item in events[0].items] == ["added"]


def test_listener_can_be_removed(tmp_path: Path) -> None:
    service = RecordingLibraryService(tmp_path / "recordings.json")
    events = []
    service.subscribe_changes(events.append)
    service.unsubscribe_changes(events.append)

    result = service.add(_material(tmp_path / "video.mp4", "material-1"))

    assert result.ok
    assert events == []
