"""项目引用、中央素材事实与静态预览状态的只读组合查询。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from services.thumbnail_coordinator import (
    ThumbnailTaskPriority,
    ThumbnailTaskSnapshot,
    ThumbnailTaskState,
)
from services.thumbnail_service import ThumbnailGenerationRequest
from utils.project_store import ProjectFile, ProjectMaterialRef
from utils.recording_library_store import MaterialItem
from utils.thumbnail_cache import ThumbnailCacheStore, ThumbnailFingerprint


class PreviewState(StrEnum):
    AVAILABLE = "available"
    NOT_GENERATED = "not_generated"
    QUEUED = "queued"
    GENERATING = "generating"
    FAILED = "failed"
    STALE = "stale"
    MISSING = "missing"
    PENDING = "pending"


class ThumbnailScheduler(Protocol):
    @staticmethod
    def key_for_request(request: ThumbnailGenerationRequest) -> str: ...

    def snapshot(self, key: str) -> ThumbnailTaskSnapshot | None: ...

    def submit(
        self,
        request: ThumbnailGenerationRequest,
        *,
        priority: ThumbnailTaskPriority,
        callback=None,
    ) -> str: ...


@dataclass(frozen=True)
class ProjectMaterialDescriptor:
    project_id: str
    material_id: str
    file_name: str
    file_path: str
    file_exists: bool
    business_status: str
    duration_sec: float | None
    width: int | None
    height: int | None
    fps: float | None
    mode: str
    audio_source: str
    file_size_bytes: int | None
    preview_path: Path | None
    preview_state: PreviewState
    preview_position_sec: float | None = None
    preview_error: str = ""


class ProjectMaterialQueryService:
    def __init__(
        self,
        cache: ThumbnailCacheStore,
        *,
        coordinator: ThumbnailScheduler | None = None,
    ) -> None:
        self.cache = cache
        self.coordinator = coordinator

    def describe(
        self,
        project: ProjectFile,
        library_items: Iterable[MaterialItem],
    ) -> list[ProjectMaterialDescriptor]:
        central = {item.id: item for item in library_items}
        return [
            self._describe_reference(project.project_id, reference, central)
            for reference in project.materials
        ]

    def schedule(
        self,
        descriptors: Iterable[ProjectMaterialDescriptor],
        *,
        visible_ids: set[str] | frozenset[str] | None = None,
        selected_id: str | None = None,
        force_ids: set[str] | frozenset[str] | None = None,
    ) -> dict[str, str]:
        if self.coordinator is None:
            return {}
        visible = set(visible_ids or ())
        forced = set(force_ids or ())
        scheduled: dict[str, str] = {}
        for descriptor in descriptors:
            if (
                descriptor.business_status != "available"
                or not descriptor.file_exists
            ):
                continue
            force = descriptor.material_id in forced
            if (
                not force
                and descriptor.preview_state
                in {
                    PreviewState.AVAILABLE,
                    PreviewState.QUEUED,
                    PreviewState.GENERATING,
                    PreviewState.FAILED,
                }
            ):
                continue
            priority = ThumbnailTaskPriority.BACKGROUND
            if descriptor.material_id == selected_id:
                priority = ThumbnailTaskPriority.SELECTED
            elif descriptor.material_id in visible:
                priority = ThumbnailTaskPriority.VISIBLE
            request = ThumbnailGenerationRequest(
                descriptor.material_id,
                descriptor.file_path,
                force=force,
            )
            scheduled[descriptor.material_id] = self.coordinator.submit(
                request,
                priority=priority,
            )
        return scheduled

    def _describe_reference(
        self,
        project_id: str,
        reference: ProjectMaterialRef,
        central: dict[str, MaterialItem],
    ) -> ProjectMaterialDescriptor:
        material = central.get(reference.material_id)
        file_path = (
            material.file_path
            if material is not None and material.file_path
            else reference.last_known_path
        )
        source = Path(file_path) if file_path else Path()
        file_exists = bool(file_path and source.is_file())
        business_status = self._business_status(material, file_exists)
        snapshot = reference.metadata_snapshot
        duration = (
            material.duration_sec
            if material is not None and material.duration_sec is not None
            else _optional_float(snapshot.get("duration_sec"))
        )
        width = (
            material.width
            if material is not None and material.width is not None
            else _optional_int(snapshot.get("width"))
        )
        height = (
            material.height
            if material is not None and material.height is not None
            else _optional_int(snapshot.get("height"))
        )
        fps = (
            material.fps
            if material is not None and material.fps is not None
            else _optional_float(snapshot.get("fps"))
        )
        mode = (
            material.mode
            if material is not None and material.mode
            else str(snapshot.get("mode") or "unknown")
        )
        audio_source = (
            material.audio_source
            if material is not None and material.audio_source
            else str(snapshot.get("audio_source") or "unknown")
        )
        file_size = (
            material.file_size_bytes
            if material is not None and material.file_size_bytes is not None
            else (source.stat().st_size if file_exists else None)
        )
        preview_path, preview_state, position, error = self._preview_state(
            reference.material_id,
            source,
            business_status,
            file_exists,
        )
        return ProjectMaterialDescriptor(
            project_id=project_id,
            material_id=reference.material_id,
            file_name=(
                material.file_name
                if material is not None and material.file_name
                else reference.file_name
            ),
            file_path=file_path,
            file_exists=file_exists,
            business_status=business_status,
            duration_sec=duration,
            width=width,
            height=height,
            fps=fps,
            mode=mode,
            audio_source=audio_source,
            file_size_bytes=file_size,
            preview_path=preview_path,
            preview_state=preview_state,
            preview_position_sec=position,
            preview_error=error,
        )

    def _preview_state(
        self,
        material_id: str,
        source: Path,
        business_status: str,
        file_exists: bool,
    ) -> tuple[Path | None, PreviewState, float | None, str]:
        latest = self.cache.find_latest_for_material(material_id)
        if business_status == "unindexed":
            return None, PreviewState.PENDING, None, ""
        if not file_exists:
            return (
                latest.path,
                PreviewState.MISSING,
                (
                    latest.entry.source_position_sec
                    if latest.entry is not None
                    else None
                ),
                "",
            )
        try:
            fingerprint = ThumbnailFingerprint.from_file(material_id, source)
        except OSError as exc:
            return latest.path, PreviewState.MISSING, None, str(exc)
        current = self.cache.lookup(fingerprint)
        request = ThumbnailGenerationRequest(material_id, source)
        task = (
            self.coordinator.snapshot(
                self.coordinator.key_for_request(request)
            )
            if self.coordinator is not None
            else None
        )
        if task is not None:
            if task.state == ThumbnailTaskState.QUEUED:
                return latest.path, PreviewState.QUEUED, _position(latest), ""
            if task.state == ThumbnailTaskState.RUNNING:
                return latest.path, PreviewState.GENERATING, _position(latest), ""
            if task.state == ThumbnailTaskState.FAILED:
                return (
                    latest.path,
                    PreviewState.FAILED,
                    _position(latest),
                    task.result.error if task.result is not None else "",
                )
        if current.entry is not None:
            return (
                current.path,
                PreviewState.AVAILABLE,
                current.entry.source_position_sec,
                "",
            )
        if latest.entry is not None:
            return (
                latest.path,
                PreviewState.STALE,
                latest.entry.source_position_sec,
                "",
            )
        return None, PreviewState.NOT_GENERATED, None, ""

    @staticmethod
    def _business_status(
        material: MaterialItem | None,
        file_exists: bool,
    ) -> str:
        if material is None:
            return "unindexed"
        if not file_exists:
            return "missing"
        return "available"


def _position(result) -> float | None:
    return (
        result.entry.source_position_sec
        if result.entry is not None
        else None
    )


def _optional_float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
