from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from exporting.filter_graph import (
    ExportFilterGraphBuilder,
    ExportFilterGraphError,
)
from exporting.models import (
    ExportClip,
    ExportMaterialSnapshot,
    ExportOutputSpec,
    ExportPlan,
    ExportProjectSnapshot,
    ExportTimelineSnapshot,
    ExportTrack,
    RenderPolicy,
)


def _material(tmp_path: Path, index: int) -> ExportMaterialSnapshot:
    path = tmp_path / "中文 空格" / f"源 {index:02d}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"media-{index}".encode())
    stat = path.stat()
    return ExportMaterialSnapshot(
        material_id=f"material-{index}",
        path=str(path),
        normalized_path=str(path).casefold(),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        container="mov,mp4,m4a,3gp,3g2,mj2",
        video_codec="h264",
        width=320,
        height=180,
        fps=30.0,
        duration_us=6_000_000,
        audio_codec="aac",
        audio_sample_rate=48_000,
        audio_channels=2,
        audio_duration_us=6_000_000,
    )


def _plan(
    tmp_path: Path,
    *,
    include_video: bool = True,
    include_audio: bool = True,
) -> ExportPlan:
    materials = tuple(_material(tmp_path, index) for index in range(1, 9))
    tracks: list[ExportTrack] = []
    clips: list[ExportClip] = []
    if include_video:
        tracks.extend(
            [
                ExportTrack("video-top", "video", 0),
                ExportTrack("video-bottom", "video", 1),
            ]
        )
        clips.extend(
            [
                ExportClip(
                    "video-bottom-clip",
                    "material-1",
                    "video-bottom",
                    None,
                    0,
                    4_000_000,
                    0,
                    4_000_000,
                ),
                ExportClip(
                    "video-top-clip",
                    "material-2",
                    "video-top",
                    None,
                    2_000_000,
                    2_000_000,
                    0,
                    2_000_000,
                ),
            ]
        )
    if include_audio:
        tracks.extend(
            ExportTrack(f"audio-{index}", "audio", index - 1)
            for index in range(1, 9)
        )
        for index in range(1, 9):
            start_us = 0 if index == 1 else 2_000_000 if index <= 4 else 4_000_000
            duration_us = 6_000_000 - start_us
            clips.append(
                ExportClip(
                    f"audio-clip-{index}",
                    f"material-{index}",
                    f"audio-{index}",
                    None,
                    start_us,
                    duration_us,
                    start_us,
                    duration_us,
                )
            )
    referenced = {clip.material_id for clip in clips}
    duration_us = max(clip.timeline_end_us for clip in clips)
    return ExportPlan.create(
        plan_id="plan-graph",
        created_at="2026-07-29T12:00:00+00:00",
        project=ExportProjectSnapshot(
            "project-1",
            "图测试",
            str(tmp_path / "project.qrproj"),
            1,
            2,
        ),
        timeline=ExportTimelineSnapshot(
            "timeline-1",
            duration_us,
            tuple(tracks),
            tuple(clips),
        ),
        materials=tuple(
            material
            for material in materials
            if material.material_id in referenced
        ),
        render_policy=RenderPolicy(),
        output=ExportOutputSpec(
            640,
            360,
            30,
            str(tmp_path / "output"),
            "结果.mp4",
        ),
    )


def test_filter_graph_is_deterministic_and_matches_render_policy(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    builder = ExportFilterGraphBuilder()

    first = builder.build(plan)
    second = builder.build(plan)

    assert first == second
    assert len(first.input_paths) == 6
    assert first.video_label == "vout"
    assert first.audio_label == "aout"
    assert (
        "color=c=black:s=640x360:r=30:d=6,format=yuv420p[base]"
        in first.graph_text
    )
    assert "scale=640:360:force_original_aspect_ratio=decrease" in first.graph_text
    assert "fps=30" in first.graph_text
    assert first.graph_text.index("vclip_000_video_bottom_clip") < (
        first.graph_text.index("vclip_001_video_top_clip")
    )
    assert "amix=inputs=4:duration=longest:dropout_transition=0:normalize=0" in (
        first.graph_text
    )
    assert "volume=0.25" in first.graph_text
    assert "amix=inputs=8:duration=longest:dropout_transition=0:normalize=0" in (
        first.graph_text
    )
    assert "volume=0.125" in first.graph_text
    assert "alimiter=limit=0.95:level=false:latency=1[aout]" in first.graph_text
    assert "concat=n=3:v=0:a=1" in first.graph_text
    assert "split=" not in first.graph_text
    assert "asplit=" not in first.graph_text
    assert first.graph_text.count("streams=da") == 9
    assert all(
        material.path not in first.graph_text for material in plan.materials
    )


def test_filter_graph_arguments_use_utf8_file_and_no_shell_string(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    graph = ExportFilterGraphBuilder().build(plan)
    graph_path = tmp_path / "图 文件" / "filter graph.txt"
    graph.write_utf8(graph_path)
    output_path = tmp_path / "输出 目录" / "结果.part.mp4"

    arguments = graph.ffmpeg_arguments(
        executable=str(tmp_path / "ffmpeg.exe"),
        graph_path=graph_path,
        output_path=output_path,
        plan=plan,
    )

    assert graph_path.read_text(encoding="utf-8") == graph.graph_text
    assert arguments[0] == str(tmp_path / "ffmpeg.exe")
    assert "-/filter_complex" in arguments
    assert "-filter_complex" not in arguments
    assert "-filter_complex_script" not in arguments
    assert arguments[arguments.index("-/filter_complex") + 1] == str(graph_path)
    assert "-xerror" in arguments
    assert str(plan.materials[0].path) in arguments
    assert arguments[-1] == str(output_path)


def test_long_unicode_input_path_is_preserved_as_one_argument(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    long_path = (
        tmp_path
        / ("中文 长目录 " * 12)
        / "包含 空格 的素材文件.mp4"
    )
    changed_material = replace(
        plan.materials[0],
        path=str(long_path),
        normalized_path=str(long_path).casefold(),
    )
    changed_plan = ExportPlan.create(
        plan_id=plan.plan_id,
        created_at=plan.created_at,
        project=plan.project,
        timeline=plan.timeline,
        materials=(changed_material, *plan.materials[1:]),
        render_policy=plan.render_policy,
        output=plan.output,
    )
    graph = ExportFilterGraphBuilder().build(changed_plan)

    arguments = graph.ffmpeg_arguments(
        executable="ffmpeg.exe",
        graph_path=tmp_path / "graph.txt",
        output_path=tmp_path / "output.mp4",
        plan=changed_plan,
    )

    assert str(long_path) in arguments
    assert arguments.count(str(long_path)) == 1


def test_repeated_material_clips_use_independent_seekable_sources(
    tmp_path: Path,
) -> None:
    material = _material(tmp_path, 1)
    special_path = (
        tmp_path
        / "中文 空格"
        / "源文件's[1],;=.mp4"
    )
    special_path.write_bytes(b"repeated-media")
    stat = special_path.stat()
    material = replace(
        material,
        path=str(special_path),
        normalized_path=str(special_path).casefold(),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
    )
    video_track = ExportTrack("video-1", "video", 0)
    audio_track = ExportTrack("audio-1", "audio", 0)
    clips: list[ExportClip] = []
    for index in range(3):
        source_start_us = index * 2_000_000
        clips.extend(
            (
                ExportClip(
                    f"video-{index}",
                    material.material_id,
                    video_track.track_id,
                    None,
                    source_start_us,
                    2_000_000,
                    source_start_us,
                    2_000_000,
                ),
                ExportClip(
                    f"audio-{index}",
                    material.material_id,
                    audio_track.track_id,
                    None,
                    source_start_us,
                    2_000_000,
                    source_start_us,
                    2_000_000,
                ),
            )
        )
    plan = ExportPlan.create(
        plan_id="plan-repeated-material",
        created_at="2026-07-29T12:00:00+00:00",
        project=ExportProjectSnapshot(
            "project-repeated",
            "重复素材长时间线",
            str(tmp_path / "project.qrproj"),
            1,
            2,
        ),
        timeline=ExportTimelineSnapshot(
            "timeline-repeated",
            6_000_000,
            (video_track, audio_track),
            tuple(clips),
        ),
        materials=(material,),
        render_policy=RenderPolicy(),
        output=ExportOutputSpec(
            640,
            360,
            30,
            str(tmp_path / "output"),
            "result.mp4",
        ),
    )

    graph = ExportFilterGraphBuilder().build(plan)

    assert graph.input_paths == ()
    assert "split=" not in graph.graph_text
    assert "asplit=" not in graph.graph_text
    assert graph.graph_text.count("streams=dv") == 3
    assert graph.graph_text.count("streams=da") == 3
    assert "seek_point=0" in graph.graph_text
    assert "seek_point=2" in graph.graph_text
    assert "seek_point=4" in graph.graph_text
    assert str(special_path) not in graph.graph_text


def test_audio_only_timeline_keeps_black_video_output(tmp_path: Path) -> None:
    graph = ExportFilterGraphBuilder().build(
        _plan(tmp_path, include_video=False)
    )

    assert graph.video_label == "vout"
    assert graph.audio_label == "aout"
    assert "color=c=black" in graph.graph_text
    assert "null[vout]" in graph.graph_text


def test_silent_timeline_does_not_map_audio(tmp_path: Path) -> None:
    plan = _plan(tmp_path, include_audio=False)
    graph = ExportFilterGraphBuilder().build(plan)
    arguments = graph.ffmpeg_arguments(
        executable="ffmpeg.exe",
        graph_path=tmp_path / "graph.txt",
        output_path=tmp_path / "output.mp4",
        plan=plan,
    )

    assert graph.audio_label is None
    assert "[aout]" not in arguments
    assert "-c:a" not in arguments


def test_more_than_eight_active_audio_sources_is_rejected(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    extra_track = ExportTrack("audio-9", "audio", 8)
    extra_clip = ExportClip(
        "audio-clip-9",
        "material-1",
        "audio-9",
        None,
        4_000_000,
        2_000_000,
        4_000_000,
        2_000_000,
    )
    timeline = replace(
        plan.timeline,
        tracks=(*plan.timeline.tracks, extra_track),
        clips=(*plan.timeline.clips, extra_clip),
    )
    over_limit = ExportPlan.create(
        plan_id=plan.plan_id,
        created_at=plan.created_at,
        project=plan.project,
        timeline=timeline,
        materials=plan.materials,
        render_policy=plan.render_policy,
        output=plan.output,
    )

    with pytest.raises(ExportFilterGraphError, match="8"):
        ExportFilterGraphBuilder().build(over_limit)
