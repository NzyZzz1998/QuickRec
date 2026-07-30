from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from exporting.models import (
    ExportClip,
    ExportMaterialSnapshot,
    ExportOutputSpec,
    ExportPlan,
    ExportProjectSnapshot,
    ExportTimelineSnapshot,
    ExportTrack,
    ExportValidationError,
    OverwriteMode,
    RenderPolicy,
)


def _plan(tmp_path: Path, *, plan_id: str, created_at: str) -> ExportPlan:
    media = tmp_path / "中文 素材.mp4"
    if not media.exists():
        media.write_bytes(b"media")
    material = ExportMaterialSnapshot(
        material_id="material-1",
        path=str(media),
        normalized_path=str(media.resolve()).casefold(),
        size_bytes=media.stat().st_size,
        mtime_ns=media.stat().st_mtime_ns,
        container="mov,mp4,m4a,3gp,3g2,mj2",
        video_codec="h264",
        width=1920,
        height=1080,
        fps=60.0,
        duration_us=2_000_000,
        audio_codec="aac",
        audio_sample_rate=48_000,
        audio_channels=2,
        audio_duration_us=2_000_000,
    )
    return ExportPlan.create(
        plan_id=plan_id,
        created_at=created_at,
        project=ExportProjectSnapshot(
            project_id="project-1",
            project_name="演示项目",
            project_path=str(tmp_path / "project.qrproj"),
            project_schema_version=1,
            timeline_schema_version=2,
        ),
        timeline=ExportTimelineSnapshot(
            timeline_id="timeline-1",
            duration_us=2_000_000,
            tracks=(ExportTrack("video-1", "video", 0),),
            clips=(
                ExportClip(
                    clip_id="clip-1",
                    material_id="material-1",
                    track_id="video-1",
                    link_group_id=None,
                    timeline_start_us=0,
                    timeline_duration_us=2_000_000,
                    source_start_us=0,
                    source_duration_us=2_000_000,
                ),
            ),
        ),
        materials=(material,),
        render_policy=RenderPolicy(),
        output=ExportOutputSpec(
            width=1920,
            height=1080,
            fps=60,
            directory=str(tmp_path),
            filename="演示项目.mp4",
            overwrite_mode=OverwriteMode.DENY,
        ),
    )


@pytest.mark.parametrize(
    ("width", "height", "fps"),
    [
        (640, 360, 30),
        (1920, 1080, 60),
        (1920, 1080, 120),
        (3840, 2160, 60),
    ],
)
def test_output_spec_accepts_supported_canvas_and_fps(
    tmp_path: Path,
    width: int,
    height: int,
    fps: int,
) -> None:
    output = ExportOutputSpec(
        width=width,
        height=height,
        fps=fps,
        directory=str(tmp_path),
        filename="output.mp4",
    )

    assert output.width == width
    assert output.height == height
    assert output.fps == fps


@pytest.mark.parametrize(
    ("width", "height", "fps", "message"),
    [
        (0, 1080, 60, "positive even"),
        (1919, 1080, 60, "positive even"),
        (1920, 1079, 60, "positive even"),
        (3842, 2160, 60, "3840x2160"),
        (3840, 2162, 60, "3840x2160"),
        (1920, 1080, 24, "30, 60, or 120"),
        (2560, 1440, 120, "1920x1080"),
    ],
)
def test_output_spec_rejects_unsupported_canvas_or_fps(
    tmp_path: Path,
    width: int,
    height: int,
    fps: int,
    message: str,
) -> None:
    with pytest.raises(ExportValidationError, match=message):
        ExportOutputSpec(
            width=width,
            height=height,
            fps=fps,
            directory=str(tmp_path),
            filename="output.mp4",
        )


def test_plan_hash_is_stable_for_same_render_content(tmp_path: Path) -> None:
    first = _plan(tmp_path, plan_id="plan-a", created_at="2026-07-29T10:00:00+00:00")
    second = _plan(tmp_path, plan_id="plan-b", created_at="2026-07-29T11:00:00+00:00")

    assert first.plan_hash == second.plan_hash
    assert first.to_dict()["plan_hash"] == first.plan_hash
    assert first.to_dict()["plan_id"] == "plan-a"


def test_plan_and_nested_models_are_immutable(tmp_path: Path) -> None:
    plan = _plan(tmp_path, plan_id="plan-a", created_at="2026-07-29T10:00:00+00:00")

    with pytest.raises(FrozenInstanceError):
        plan.plan_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        plan.output.fps = 30  # type: ignore[misc]


def test_unknown_plan_schema_is_rejected(tmp_path: Path) -> None:
    payload = _plan(
        tmp_path,
        plan_id="plan-a",
        created_at="2026-07-29T10:00:00+00:00",
    ).to_dict()
    payload["plan_schema_version"] = 99

    with pytest.raises(ExportValidationError, match="unsupported export plan schema"):
        ExportPlan.from_dict(payload)


def test_plan_roundtrip_preserves_material_fingerprint(tmp_path: Path) -> None:
    plan = _plan(tmp_path, plan_id="plan-a", created_at="2026-07-29T10:00:00+00:00")

    restored = ExportPlan.from_dict(plan.to_dict())

    assert restored == plan
    assert restored.materials[0].fingerprint == plan.materials[0].fingerprint
