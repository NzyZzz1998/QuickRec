"""时间线播放查询与动态等增益音频混合。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.timeline_model import Timeline, TimelineClip, TimelineTrack


@dataclass(frozen=True)
class MediaSource:
    material_id: str
    path: Path
    file_exists: bool
    metadata: dict[str, object]


@dataclass(frozen=True)
class ActiveClip:
    clip: TimelineClip
    track: TimelineTrack
    source: MediaSource
    source_position_us: int


@dataclass(frozen=True)
class PlaybackPlan:
    position_us: int
    duration_us: int
    video: ActiveClip | None
    audio: tuple[ActiveClip, ...]


def timeline_duration_us(timeline: Timeline) -> int:
    """返回最后一个片段结束时间；空时间线为零。"""
    return max((clip.timeline_end_us for clip in timeline.clips), default=0)


def build_playback_plan(
    project: ProjectFile,
    timeline: Timeline,
    position_us: int,
) -> PlaybackPlan:
    """按固定轨道规则生成指定时刻的播放计划。"""
    duration_us = timeline_duration_us(timeline)
    position = max(0, min(int(position_us), duration_us))
    tracks = {track.track_id: track for track in timeline.tracks}
    materials = {
        material.material_id: material for material in project.materials
    }

    active_video: list[ActiveClip] = []
    active_audio: list[ActiveClip] = []
    for clip in timeline.clips:
        if not _is_active(clip, position):
            continue
        track = tracks.get(clip.track_id)
        material = materials.get(clip.material_id)
        if track is None or material is None:
            continue
        active = _active_clip(clip, track, material, position)
        if track.kind == "video":
            active_video.append(active)
        elif track.kind == "audio":
            active_audio.append(active)

    # order=0 是画布上最靠上的轨道；顶层失败时也不透出下层画面。
    active_video.sort(key=lambda item: (item.track.order, item.clip.clip_id))
    active_audio.sort(key=lambda item: (item.track.order, item.clip.clip_id))
    return PlaybackPlan(
        position,
        duration_us,
        active_video[0] if active_video else None,
        tuple(active_audio),
    )


def mix_audio_blocks(
    blocks: list[NDArray[np.floating[object]]],
) -> NDArray[np.float32]:
    """按成功解码源数量使用 1/N 增益，并做有限值与安全限幅。"""
    if not blocks:
        return np.zeros((0, 0), dtype=np.float32)

    shape = blocks[0].shape
    if any(block.shape != shape for block in blocks):
        raise ValueError("audio blocks must share the same shape")

    mixed = np.zeros(shape, dtype=np.float32)
    gain = 1.0 / len(blocks)
    for block in blocks:
        safe_block = np.nan_to_num(
            np.asarray(block, dtype=np.float32),
            nan=0.0,
            posinf=1.0,
            neginf=-1.0,
        )
        mixed += safe_block * gain
    return np.clip(mixed, -1.0, 1.0).astype(np.float32, copy=False)


def _is_active(clip: TimelineClip, position_us: int) -> bool:
    return clip.timeline_start_us <= position_us < clip.timeline_end_us


def _active_clip(
    clip: TimelineClip,
    track: TimelineTrack,
    material: ProjectMaterialRef,
    position_us: int,
) -> ActiveClip:
    path = Path(material.last_known_path)
    source_position_us = clip.source_start_us + (
        position_us - clip.timeline_start_us
    )
    return ActiveClip(
        clip,
        track,
        MediaSource(
            material.material_id,
            path,
            path.is_file(),
            dict(material.metadata_snapshot),
        ),
        source_position_us,
    )
