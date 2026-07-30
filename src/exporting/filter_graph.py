"""把不可变导出计划转换为确定性的 FFmpeg 滤镜图与参数数组。"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from exporting.models import (
    ExportClip,
    ExportMaterialSnapshot,
    ExportPlan,
)

MAX_ACTIVE_AUDIO_SOURCES = 8
_LABEL_CHARS = re.compile(r"[^A-Za-z0-9_]+")


class ExportFilterGraphError(ValueError):
    """导出计划无法转换为当前固定渲染语义。"""


@dataclass(frozen=True)
class ExportFilterGraph:
    input_paths: tuple[str, ...]
    graph_text: str
    video_label: str
    audio_label: str | None

    def write_utf8(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.graph_text, encoding="utf-8", newline="\n")

    def ffmpeg_arguments(
        self,
        *,
        executable: str,
        graph_path: Path,
        output_path: Path,
        plan: ExportPlan,
    ) -> list[str]:
        arguments = [
            executable,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-xerror",
        ]
        for input_path in self.input_paths:
            arguments.extend(("-i", input_path))
        arguments.extend(
            (
                "-/filter_complex",
                str(graph_path),
                "-map",
                f"[{self.video_label}]",
            )
        )
        if self.audio_label is not None:
            arguments.extend(("-map", f"[{self.audio_label}]"))
        arguments.extend(
            (
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(plan.output.fps),
            )
        )
        if self.audio_label is not None:
            arguments.extend(
                (
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                )
            )
        arguments.extend(
            (
                "-t",
                _seconds(plan.timeline.duration_us),
                "-movflags",
                "+faststart",
                "-progress",
                "pipe:1",
                "-nostats",
                str(output_path),
            )
        )
        return arguments


class ExportFilterGraphBuilder:
    def build(self, plan: ExportPlan) -> ExportFilterGraph:
        material_by_id = {
            material.material_id: material for material in plan.materials
        }
        track_by_id = {
            track.track_id: track for track in plan.timeline.tracks
        }
        video_clips = sorted(
            (
                clip
                for clip in plan.timeline.clips
                if track_by_id[clip.track_id].kind == "video"
            ),
            key=lambda clip: (
                -track_by_id[clip.track_id].order,
                clip.timeline_start_us,
                clip.clip_id,
            ),
        )
        audio_clips = sorted(
            (
                clip
                for clip in plan.timeline.clips
                if track_by_id[clip.track_id].kind == "audio"
            ),
            key=lambda clip: (
                clip.timeline_start_us,
                track_by_id[clip.track_id].order,
                clip.clip_id,
            ),
        )
        self._validate_streams(
            material_by_id,
            video_clips,
            audio_clips,
        )
        audio_segments = _audio_segments(
            audio_clips,
            plan.timeline.duration_us,
        )
        direct_material_ids = _direct_input_material_ids(
            video_clips,
            audio_segments,
        )
        input_materials = tuple(
            material
            for material in plan.materials
            if material.material_id in direct_material_ids
        )
        input_index = {
            material.material_id: index
            for index, material in enumerate(input_materials)
        }

        lines: list[str] = []
        video_sources = _video_source_labels(
            video_clips,
            material_by_id,
            input_index,
            lines,
        )
        audio_sources = _audio_source_labels(
            audio_segments,
            material_by_id,
            input_index,
            lines,
        )

        width = plan.output.width
        height = plan.output.height
        fps = plan.output.fps
        duration = _seconds(plan.timeline.duration_us)
        lines.append(
            f"color=c=black:s={width}x{height}:r={fps}:d={duration},"
            "format=yuv420p[base]"
        )
        current_video = "base"
        for index, clip in enumerate(video_clips):
            clip_label = f"vclip_{index:03d}_{_safe_label(clip.clip_id)}"
            lines.append(
                f"{video_sources[clip.clip_id]}"
                f"trim=start={_seconds(clip.source_start_us)}:"
                f"duration={_seconds(clip.source_duration_us)},"
                f"setpts=PTS-STARTPTS+{_seconds(clip.timeline_start_us)}/TB,"
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fps={fps},format=yuv420p[{clip_label}]"
            )
            overlay_label = (
                "vout" if index == len(video_clips) - 1 else f"voverlay_{index:03d}"
            )
            lines.append(
                f"[{current_video}][{clip_label}]"
                "overlay=eof_action=pass:shortest=0:repeatlast=0:"
                f"enable='between(t,{_seconds(clip.timeline_start_us)},"
                f"{_seconds(clip.timeline_end_us)})'[{overlay_label}]"
            )
            current_video = overlay_label
        if not video_clips:
            lines.append("[base]null[vout]")

        audio_label = self._append_audio_graph(
            lines,
            audio_segments,
            audio_sources,
        )
        return ExportFilterGraph(
            input_paths=tuple(material.path for material in input_materials),
            graph_text=";\n".join(lines),
            video_label="vout",
            audio_label=audio_label,
        )

    @staticmethod
    def _validate_streams(
        materials: dict[str, ExportMaterialSnapshot],
        video_clips: list[ExportClip],
        audio_clips: list[ExportClip],
    ) -> None:
        for clip in video_clips:
            if clip.material_id not in materials:
                raise ExportFilterGraphError("video clip material is missing")
            material = materials[clip.material_id]
            if material.video_codec is None:
                raise ExportFilterGraphError("video clip has no video stream")
        for clip in audio_clips:
            if clip.material_id not in materials:
                raise ExportFilterGraphError("audio clip material is missing")
            material = materials[clip.material_id]
            if material.audio_codec is None:
                raise ExportFilterGraphError("audio clip has no audio stream")

    @staticmethod
    def _append_audio_graph(
        lines: list[str],
        segments: list[tuple[int, int, tuple[ExportClip, ...]]],
        sources: dict[tuple[int, str], str],
    ) -> str | None:
        if not any(active for _, _, active in segments):
            return None
        segment_labels: list[str] = []
        for segment_index, (start_us, end_us, active) in enumerate(segments):
            duration_us = end_us - start_us
            segment_label = f"asegment_{segment_index:03d}"
            segment_labels.append(segment_label)
            if not active:
                lines.append(
                    "anullsrc=r=48000:cl=stereo:"
                    f"d={_seconds(duration_us)}[{segment_label}]"
                )
                continue
            piece_labels: list[str] = []
            for source_index, clip in enumerate(active):
                piece_label = (
                    f"apiece_{segment_index:03d}_{source_index:02d}"
                )
                piece_labels.append(piece_label)
                source_start_us = clip.source_start_us + (
                    start_us - clip.timeline_start_us
                )
                lines.append(
                    f"{sources[(segment_index, clip.clip_id)]}"
                    f"atrim=start={_seconds(source_start_us)}:"
                    f"duration={_seconds(duration_us)},"
                    "asetpts=PTS-STARTPTS,"
                    "aresample=48000,"
                    "aformat=sample_fmts=fltp:sample_rates=48000:"
                    f"channel_layouts=stereo[{piece_label}]"
                )
            if len(piece_labels) == 1:
                lines.append(
                    f"[{piece_labels[0]}]volume=1[{segment_label}]"
                )
            else:
                joined = "".join(f"[{label}]" for label in piece_labels)
                gain = _gain(len(piece_labels))
                lines.append(
                    f"{joined}amix=inputs={len(piece_labels)}:"
                    "duration=longest:dropout_transition=0:normalize=0,"
                    f"volume={gain}[{segment_label}]"
                )
        joined_segments = "".join(f"[{label}]" for label in segment_labels)
        if len(segment_labels) == 1:
            lines.append(
                f"{joined_segments}alimiter=limit=0.95:"
                "level=false:latency=1[aout]"
            )
        else:
            lines.append(
                f"{joined_segments}concat=n={len(segment_labels)}:"
                "v=0:a=1[aconcat]"
            )
            lines.append(
                "[aconcat]alimiter=limit=0.95:"
                "level=false:latency=1[aout]"
            )
        return "aout"


def _video_source_labels(
    clips: list[ExportClip],
    materials: dict[str, ExportMaterialSnapshot],
    input_index: dict[str, int],
    lines: list[str],
) -> dict[str, str]:
    counts = Counter(clip.material_id for clip in clips)
    labels: dict[str, str] = {}
    for source_index, clip in enumerate(clips):
        if counts[clip.material_id] == 1:
            labels[clip.clip_id] = f"[{input_index[clip.material_id]}:v]"
            continue
        material = materials[clip.material_id]
        label = f"vsrc_{source_index:03d}_{_safe_label(clip.clip_id)}"
        lines.append(
            _movie_source(
                material.path,
                seek_point_us=clip.source_start_us,
                stream="dv",
                label=label,
            )
        )
        labels[clip.clip_id] = f"[{label}]"
    return labels


def _audio_segments(
    clips: list[ExportClip],
    duration_us: int,
) -> list[tuple[int, int, tuple[ExportClip, ...]]]:
    if not clips:
        return []
    boundaries = {0, duration_us}
    for clip in clips:
        boundaries.add(max(0, min(duration_us, clip.timeline_start_us)))
        boundaries.add(max(0, min(duration_us, clip.timeline_end_us)))
    ordered = sorted(boundaries)
    segments: list[tuple[int, int, tuple[ExportClip, ...]]] = []
    for start_us, end_us in zip(ordered, ordered[1:]):
        if end_us <= start_us:
            continue
        active = tuple(
            clip
            for clip in clips
            if clip.timeline_start_us <= start_us
            and clip.timeline_end_us >= end_us
        )
        if len(active) > MAX_ACTIVE_AUDIO_SOURCES:
            raise ExportFilterGraphError(
                "active audio source count exceeds 8"
            )
        segments.append((start_us, end_us, active))
    return segments


def _audio_source_labels(
    segments: list[tuple[int, int, tuple[ExportClip, ...]]],
    materials: dict[str, ExportMaterialSnapshot],
    input_index: dict[str, int],
    lines: list[str],
) -> dict[tuple[int, str], str]:
    occurrences = [
        (segment_index, start_us, clip)
        for segment_index, (start_us, _, active) in enumerate(segments)
        for clip in active
    ]
    counts = Counter(clip.material_id for _, _, clip in occurrences)
    sources: dict[tuple[int, str], str] = {}
    for source_index, (segment_index, start_us, clip) in enumerate(occurrences):
        key = (segment_index, clip.clip_id)
        if counts[clip.material_id] == 1:
            sources[key] = f"[{input_index[clip.material_id]}:a]"
            continue
        material = materials[clip.material_id]
        source_start_us = clip.source_start_us + (
            start_us - clip.timeline_start_us
        )
        label = f"asrc_{source_index:03d}_{_safe_label(clip.clip_id)}"
        lines.append(
            _movie_source(
                material.path,
                seek_point_us=source_start_us,
                stream="da",
                label=label,
            )
        )
        sources[key] = f"[{label}]"
    return sources


def _direct_input_material_ids(
    video_clips: list[ExportClip],
    audio_segments: list[tuple[int, int, tuple[ExportClip, ...]]],
) -> set[str]:
    video_counts = Counter(clip.material_id for clip in video_clips)
    audio_counts = Counter(
        clip.material_id
        for _, _, active in audio_segments
        for clip in active
    )
    return {
        material_id
        for material_id in video_counts.keys() | audio_counts.keys()
        if video_counts[material_id] == 1 or audio_counts[material_id] == 1
    }


def _movie_source(
    path: str,
    *,
    seek_point_us: int,
    stream: str,
    label: str,
) -> str:
    escaped_path = _escape_filter_option(path)
    return (
        f"movie=filename={escaped_path}:"
        f"seek_point={_seconds(seek_point_us)}:"
        f"streams={stream}:dec_threads=1[{label}]"
    )


def _escape_filter_option(value: str) -> str:
    normalized = value.replace("\\", "/")
    option_escaped = (
        normalized.replace("\\", r"\\")
        .replace("'", r"\'")
        .replace(":", r"\:")
    )
    graph_escaped = (
        option_escaped.replace("\\", r"\\")
        .replace("'", r"\'")
        .replace("[", r"\[")
        .replace("]", r"\]")
        .replace(",", r"\,")
        .replace(";", r"\;")
    )
    return graph_escaped


def _safe_label(value: str) -> str:
    safe = _LABEL_CHARS.sub("_", value).strip("_")
    return safe or "clip"


def _seconds(microseconds: int) -> str:
    seconds, remainder = divmod(microseconds, 1_000_000)
    if remainder == 0:
        return str(seconds)
    return f"{seconds}.{remainder:06d}".rstrip("0")


def _gain(source_count: int) -> str:
    return f"{1.0 / source_count:.9f}".rstrip("0").rstrip(".")
