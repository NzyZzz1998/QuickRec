from __future__ import annotations

import copy
from pathlib import Path

from services.project_materials import (
    PreviewState,
    ProjectMaterialQueryService,
)
from services.thumbnail_coordinator import (
    ThumbnailCoordinator,
    ThumbnailTaskPriority,
    ThumbnailTaskSnapshot,
    ThumbnailTaskState,
)
from services.thumbnail_service import (
    ThumbnailGenerationRequest,
    ThumbnailGenerationResult,
)
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.recording_library_store import MaterialItem
from utils.thumbnail_cache import ThumbnailCacheStore, ThumbnailFingerprint


def _material(tmp_path: Path, material_id: str = "material-1") -> MaterialItem:
    video = tmp_path / "中文 空格" / f"{material_id}.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"video")
    stat = video.stat()
    return MaterialItem(
        id=material_id,
        file_path=str(video),
        file_name=video.name,
        directory=str(video.parent),
        mode="fullscreen",
        audio_source="none",
        created_at="2026-07-27T10:00:00+08:00",
        duration_sec=3.5,
        width=1920,
        height=1080,
        fps=60,
        file_size_bytes=stat.st_size,
        file_modified_ns=stat.st_mtime_ns,
    )


def _project(material: MaterialItem) -> ProjectFile:
    return ProjectFile(
        project_id="project-1",
        name="测试项目",
        description="",
        created_at="2026-07-27T10:00:00+08:00",
        updated_at="2026-07-27T10:00:00+08:00",
        materials=[
            ProjectMaterialRef(
                material_id=material.id,
                last_known_path=material.file_path,
                file_name=material.file_name,
                added_at="2026-07-27T10:00:00+08:00",
                metadata_snapshot={
                    "duration_sec": material.duration_sec,
                    "width": material.width,
                    "height": material.height,
                    "fps": material.fps,
                    "mode": material.mode,
                    "audio_source": material.audio_source,
                },
            )
        ],
    )


def _cache_preview(
    cache: ThumbnailCacheStore,
    material: MaterialItem,
    payload: bytes = b"jpeg",
) -> Path:
    fingerprint = ThumbnailFingerprint.from_file(material.id, material.file_path)
    temp = cache.create_temp_path(fingerprint.cache_key)
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(payload)
    result = cache.commit(
        temp,
        fingerprint,
        width=320,
        height=180,
        source_position_sec=0.35,
        accessed_at="2026-07-27T11:00:00+08:00",
    )
    assert result.ok
    return result.path


class FakeCoordinator:
    def __init__(self) -> None:
        self.snapshots: dict[str, ThumbnailTaskSnapshot] = {}
        self.submitted: list[
            tuple[ThumbnailGenerationRequest, ThumbnailTaskPriority]
        ] = []

    @staticmethod
    def key_for_request(request: ThumbnailGenerationRequest) -> str:
        return ThumbnailCoordinator.key_for_request(request)

    def snapshot(self, key: str) -> ThumbnailTaskSnapshot | None:
        return self.snapshots.get(key)

    def submit(
        self,
        request: ThumbnailGenerationRequest,
        *,
        priority: ThumbnailTaskPriority,
        callback=None,
    ) -> str:
        del callback
        self.submitted.append((request, priority))
        return self.key_for_request(request)


def test_available_material_without_cache_is_not_generated(tmp_path: Path) -> None:
    material = _material(tmp_path)
    service = ProjectMaterialQueryService(ThumbnailCacheStore(tmp_path / "cache"))

    descriptor = service.describe(_project(material), [material])[0]

    assert descriptor.material_id == material.id
    assert descriptor.file_exists
    assert descriptor.business_status == "available"
    assert descriptor.preview_state == PreviewState.NOT_GENERATED
    assert descriptor.preview_path is None
    assert descriptor.width == 1920
    assert descriptor.height == 1080
    assert descriptor.fps == 60


def test_current_cache_is_returned_as_available(tmp_path: Path) -> None:
    material = _material(tmp_path)
    cache = ThumbnailCacheStore(tmp_path / "cache")
    preview = _cache_preview(cache, material)
    service = ProjectMaterialQueryService(cache)

    descriptor = service.describe(_project(material), [material])[0]

    assert descriptor.preview_state == PreviewState.AVAILABLE
    assert descriptor.preview_path == preview
    assert descriptor.preview_position_sec == 0.35


def test_missing_file_keeps_latest_historical_preview(tmp_path: Path) -> None:
    material = _material(tmp_path)
    cache = ThumbnailCacheStore(tmp_path / "cache")
    preview = _cache_preview(cache, material)
    Path(material.file_path).unlink()
    service = ProjectMaterialQueryService(cache)

    descriptor = service.describe(_project(material), [material])[0]

    assert not descriptor.file_exists
    assert descriptor.business_status == "missing"
    assert descriptor.preview_state == PreviewState.MISSING
    assert descriptor.preview_path == preview


def test_project_reference_without_central_material_is_pending(tmp_path: Path) -> None:
    material = _material(tmp_path)
    project = _project(material)
    service = ProjectMaterialQueryService(ThumbnailCacheStore(tmp_path / "cache"))

    descriptor = service.describe(project, [])[0]

    assert descriptor.business_status == "unindexed"
    assert descriptor.preview_state == PreviewState.PENDING
    assert descriptor.preview_path is None


def test_active_task_state_overrides_not_generated_state(tmp_path: Path) -> None:
    material = _material(tmp_path)
    coordinator = FakeCoordinator()
    request = ThumbnailGenerationRequest(material.id, material.file_path)
    key = coordinator.key_for_request(request)
    coordinator.snapshots[key] = ThumbnailTaskSnapshot(
        key,
        request,
        ThumbnailTaskState.RUNNING,
        ThumbnailTaskPriority.SELECTED,
    )
    service = ProjectMaterialQueryService(
        ThumbnailCacheStore(tmp_path / "cache"),
        coordinator=coordinator,
    )

    descriptor = service.describe(_project(material), [material])[0]

    assert descriptor.preview_state == PreviewState.GENERATING


def test_failed_task_exposes_error_without_changing_business_status(tmp_path: Path) -> None:
    material = _material(tmp_path)
    coordinator = FakeCoordinator()
    request = ThumbnailGenerationRequest(material.id, material.file_path)
    key = coordinator.key_for_request(request)
    failure = ThumbnailGenerationResult(
        False,
        material.id,
        error="decoder failed",
    )
    coordinator.snapshots[key] = ThumbnailTaskSnapshot(
        key,
        request,
        ThumbnailTaskState.FAILED,
        ThumbnailTaskPriority.VISIBLE,
        result=failure,
    )
    service = ProjectMaterialQueryService(
        ThumbnailCacheStore(tmp_path / "cache"),
        coordinator=coordinator,
    )

    descriptor = service.describe(_project(material), [material])[0]

    assert descriptor.business_status == "available"
    assert descriptor.preview_state == PreviewState.FAILED
    assert descriptor.preview_error == "decoder failed"


def test_schedule_prioritizes_selected_visible_and_background_materials(
    tmp_path: Path,
) -> None:
    materials = [_material(tmp_path, f"material-{index}") for index in range(3)]
    project = _project(materials[0])
    project.materials.extend(
        [
            ProjectMaterialRef(
                material_id=item.id,
                last_known_path=item.file_path,
                file_name=item.file_name,
                added_at="2026-07-27T10:00:00+08:00",
            )
            for item in materials[1:]
        ]
    )
    coordinator = FakeCoordinator()
    service = ProjectMaterialQueryService(
        ThumbnailCacheStore(tmp_path / "cache"),
        coordinator=coordinator,
    )
    descriptors = service.describe(project, materials)

    service.schedule(
        descriptors,
        visible_ids={materials[0].id, materials[1].id},
        selected_id=materials[1].id,
    )

    priorities = {
        request.material_id: priority
        for request, priority in coordinator.submitted
    }
    assert priorities == {
        materials[0].id: ThumbnailTaskPriority.VISIBLE,
        materials[1].id: ThumbnailTaskPriority.SELECTED,
        materials[2].id: ThumbnailTaskPriority.BACKGROUND,
    }


def test_pending_and_missing_materials_are_not_scheduled(tmp_path: Path) -> None:
    available = _material(tmp_path, "available")
    missing = _material(tmp_path, "missing")
    Path(missing.file_path).unlink()
    project = _project(available)
    project.materials.append(
        ProjectMaterialRef(
            material_id=missing.id,
            last_known_path=missing.file_path,
            file_name=missing.file_name,
            added_at="2026-07-27T10:00:00+08:00",
        )
    )
    project.materials.append(
        ProjectMaterialRef(
            material_id="unindexed",
            last_known_path=str(tmp_path / "unindexed.mp4"),
            file_name="unindexed.mp4",
            added_at="2026-07-27T10:00:00+08:00",
        )
    )
    coordinator = FakeCoordinator()
    service = ProjectMaterialQueryService(
        ThumbnailCacheStore(tmp_path / "cache"),
        coordinator=coordinator,
    )

    service.schedule(service.describe(project, [available, missing]))

    assert [item[0].material_id for item in coordinator.submitted] == ["available"]


def test_describe_and_schedule_do_not_mutate_project_or_material(tmp_path: Path) -> None:
    material = _material(tmp_path)
    project = _project(material)
    project_before = copy.deepcopy(project.to_dict())
    material_before = copy.deepcopy(material.to_dict())
    coordinator = FakeCoordinator()
    service = ProjectMaterialQueryService(
        ThumbnailCacheStore(tmp_path / "cache"),
        coordinator=coordinator,
    )

    descriptors = service.describe(project, [material])
    service.schedule(descriptors)

    assert project.to_dict() == project_before
    assert material.to_dict() == material_before


def test_descriptor_keeps_future_timeline_boundary_read_only(tmp_path: Path) -> None:
    material = _material(tmp_path)
    descriptor = ProjectMaterialQueryService(
        ThumbnailCacheStore(tmp_path / "cache")
    ).describe(_project(material), [material])[0]

    assert descriptor.preview_path is None
    assert not hasattr(descriptor, "track_id")
    assert not hasattr(descriptor, "timeline_position")
    assert not hasattr(descriptor, "in_point")
    assert not hasattr(descriptor, "out_point")
