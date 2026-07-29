from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.timeline_health import assess_timeline_clip_health
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import Timeline, TimelineClip, TimelineTrack


def _project(path: Path) -> ProjectFile:
    return ProjectFile(
        project_id="project-1",
        name="健康检查",
        description="",
        created_at="2026-07-29T10:00:00+08:00",
        updated_at="2026-07-29T10:00:00+08:00",
        archived_at=None,
        materials=[
            ProjectMaterialRef(
                material_id="material-1",
                last_known_path=str(path),
                file_name=path.name,
                added_at="2026-07-29T10:00:00+08:00",
                metadata_snapshot={"duration_sec": 10.0},
            )
        ],
    )


def _linked_timeline() -> Timeline:
    return Timeline(
        "timeline-1",
        [
            TimelineTrack("video-1", "video", "视频 1", 0),
            TimelineTrack("audio-1", "audio", "音频 1", 0),
        ],
        [
            TimelineClip(
                "clip-v",
                "material-1",
                "video-1",
                1_000_000,
                3_000_000,
                2_000_000,
                3_000_000,
                "link-1",
            ),
            TimelineClip(
                "clip-a",
                "material-1",
                "audio-1",
                1_000_000,
                3_000_000,
                2_000_000,
                3_000_000,
                "link-1",
            ),
        ],
    )


def test_missing_material_blocks_range_edit_but_keeps_ripple_delete(tmp_path):
    missing = tmp_path / "已移动.mp4"
    health = assess_timeline_clip_health(
        _linked_timeline(),
        _project(missing),
    )

    assert {item.status for item in health.values()} == {"missing"}
    assert all(not item.range_editable for item in health.values())
    assert all(item.move_editable for item in health.values())
    assert all(item.delete_editable for item in health.values())


def test_descriptor_relink_restores_all_clips_without_mutating_identity(tmp_path):
    missing = tmp_path / "原路径.mp4"
    replacement = tmp_path / "中文 新路径.mp4"
    replacement.write_bytes(b"video")
    timeline = _linked_timeline()
    before = [replace(item) for item in timeline.clips]

    class Descriptor:
        material_id = "material-1"
        file_exists = True

    health = assess_timeline_clip_health(
        timeline,
        _project(missing),
        [Descriptor()],
    )

    assert {item.status for item in health.values()} == {"available"}
    assert timeline.clips == before


def test_broken_link_group_is_read_only_without_guessing_repair(tmp_path):
    media = tmp_path / "source.mp4"
    media.write_bytes(b"video")
    timeline = _linked_timeline()
    timeline.clips[1].source_start_us += 1

    health = assess_timeline_clip_health(timeline, _project(media))

    assert {item.status for item in health.values()} == {"link_error"}
    assert all(not item.range_editable for item in health.values())
    assert all(not item.move_editable for item in health.values())
    assert all(not item.delete_editable for item in health.values())
