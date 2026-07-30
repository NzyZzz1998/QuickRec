from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from exporting.executor import ExportExecutor
from exporting.filter_graph import ExportFilterGraphBuilder
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
from exporting.verifier import ExportVerifier
from utils.media_metadata import (
    resolve_ffmpeg_path,
    resolve_ffprobe_path,
)

pytestmark = pytest.mark.packaging


def _run(arguments: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _generate_source(
    ffmpeg: str,
    path: Path,
    *,
    color: str,
    frequency: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = _run(
        [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x180:r=30:d=3",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=48000:duration=3",
            "-shortest",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(path),
        ]
    )
    assert completed.returncode == 0, completed.stderr.decode(
        "utf-8",
        errors="replace",
    )


def _material(path: Path, material_id: str) -> ExportMaterialSnapshot:
    stat = path.stat()
    return ExportMaterialSnapshot(
        material_id=material_id,
        path=str(path),
        normalized_path=str(path).casefold(),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        container="mov,mp4,m4a,3gp,3g2,mj2",
        video_codec="h264",
        width=320,
        height=180,
        fps=30.0,
        duration_us=3_000_000,
        audio_codec="aac",
        audio_sample_rate=48_000,
        audio_channels=1,
        audio_duration_us=3_000_000,
    )


def _plan(tmp_path: Path, first: Path, second: Path) -> ExportPlan:
    return ExportPlan.create(
        plan_id="packaging-graph",
        created_at="2026-07-29T12:00:00+00:00",
        project=ExportProjectSnapshot(
            "project-1",
            "真实媒体图",
            str(tmp_path / "project.qrproj"),
            1,
            2,
        ),
        timeline=ExportTimelineSnapshot(
            "timeline-1",
            3_000_000,
            (
                ExportTrack("video-top", "video", 0),
                ExportTrack("video-bottom", "video", 1),
                ExportTrack("audio-1", "audio", 0),
                ExportTrack("audio-2", "audio", 1),
            ),
            (
                ExportClip(
                    "video-bottom-clip-1",
                    "material-1",
                    "video-bottom",
                    None,
                    0,
                    1_500_000,
                    0,
                    1_500_000,
                ),
                ExportClip(
                    "video-bottom-clip-2",
                    "material-1",
                    "video-bottom",
                    None,
                    1_500_000,
                    1_500_000,
                    1_500_000,
                    1_500_000,
                ),
                ExportClip(
                    "video-top-clip",
                    "material-2",
                    "video-top",
                    None,
                    1_000_000,
                    1_000_000,
                    0,
                    1_000_000,
                ),
                ExportClip(
                    "audio-1-clip",
                    "material-1",
                    "audio-1",
                    None,
                    0,
                    3_000_000,
                    0,
                    3_000_000,
                ),
                ExportClip(
                    "audio-2-clip",
                    "material-2",
                    "audio-2",
                    None,
                    1_000_000,
                    1_000_000,
                    0,
                    1_000_000,
                ),
            ),
        ),
        materials=(
            _material(first, "material-1"),
            _material(second, "material-2"),
        ),
        render_policy=RenderPolicy(),
        output=ExportOutputSpec(
            320,
            180,
            30,
            str(tmp_path / "输出 目录"),
            "合成 结果.mp4",
        ),
    )


def _frame_rgb(ffmpeg: str, output: Path, position: str) -> bytes:
    completed = _run(
        [
            ffmpeg,
            "-hide_banner",
            "-v",
            "error",
            "-ss",
            position,
            "-i",
            str(output),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ]
    )
    assert completed.returncode == 0
    assert len(completed.stdout) == 320 * 180 * 3
    return completed.stdout


def test_production_filter_graph_runs_with_bundled_ffmpeg(
    tmp_path: Path,
) -> None:
    ffmpeg = resolve_ffmpeg_path()
    ffprobe = resolve_ffprobe_path()
    assert Path(ffmpeg).is_file()
    assert Path(ffprobe).is_file()
    media_dir = tmp_path / "中文 空格"
    first = media_dir / "红色 源's[1],;=.mp4"
    second = media_dir / "蓝色 源.mp4"
    _generate_source(ffmpeg, first, color="red", frequency=440)
    _generate_source(ffmpeg, second, color="blue", frequency=880)
    plan = _plan(tmp_path, first, second)
    graph = ExportFilterGraphBuilder().build(plan)
    graph_path = tmp_path / "过滤 图" / "filter graph.txt"
    output = tmp_path / "输出 目录" / "合成 结果.part.mp4"
    output.parent.mkdir(parents=True)
    graph.write_utf8(graph_path)

    completed = _run(
        graph.ffmpeg_arguments(
            executable=ffmpeg,
            graph_path=graph_path,
            output_path=output,
            plan=plan,
        ),
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr.decode(
        "utf-8",
        errors="replace",
    )
    assert output.is_file() and output.stat().st_size > 0
    probed = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(output),
        ]
    )
    assert probed.returncode == 0
    payload = json.loads(probed.stdout.decode("utf-8"))
    video = next(
        stream
        for stream in payload["streams"]
        if stream["codec_type"] == "video"
    )
    audio = next(
        stream
        for stream in payload["streams"]
        if stream["codec_type"] == "audio"
    )
    assert (video["width"], video["height"]) == (320, 180)
    assert video["avg_frame_rate"] == "30/1"
    assert audio["codec_name"] == "aac"
    assert audio["sample_rate"] == "48000"
    assert audio["channels"] == 2
    assert abs(float(payload["format"]["duration"]) - 3.0) <= 0.05
    verified = ExportVerifier(
        ffprobe_resolver=lambda: ffprobe,
    ).verify_output(plan, output)
    assert verified.ok

    verifier = ExportVerifier(ffprobe_resolver=lambda: ffprobe)
    execution = ExportExecutor(
        ffmpeg_resolver=lambda: ffmpeg,
        material_verifier=verifier.verify_materials,
    ).execute(plan, attempt_id="packaging-real")
    assert execution.ok
    assert execution.temp_output_path is not None
    assert verifier.verify_output(plan, execution.temp_output_path).ok
    execution.temp_output_path.unlink()

    bottom_frame = _frame_rgb(ffmpeg, output, "0.5")
    top_frame = _frame_rgb(ffmpeg, output, "1.5")
    center = (90 * 320 + 160) * 3
    assert bottom_frame[center] > bottom_frame[center + 2]
    assert top_frame[center + 2] > top_frame[center]
