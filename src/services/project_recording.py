"""项目内录制的最小上下文与素材关联协调。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from services.project_library import ProjectLibraryService
from services.recording_library import RecordingLibraryService
from utils.project_store import ProjectMaterialRef


@dataclass(frozen=True)
class ProjectRecordingContext:
    project_id: str
    mode: str

    def __post_init__(self) -> None:
        if self.mode not in {"fullscreen", "region", "window"}:
            raise ValueError(f"unsupported project recording mode: {self.mode}")


@dataclass(frozen=True)
class ProjectLinkResult:
    ok: bool
    project_id: str
    material_id: str
    stage: str = "complete"
    error: str = ""
    duplicate: bool = False


class ProjectRecordingCoordinator:
    """在全局素材已存在后，把稳定素材 ID 写入目标项目。"""

    def __init__(
        self,
        project_service: ProjectLibraryService,
        library_service: RecordingLibraryService,
    ) -> None:
        self.project_service = project_service
        self.library_service = library_service

    def link_material(
        self,
        project_id: str,
        material_id: str,
        *,
        now: str | None = None,
    ) -> ProjectLinkResult:
        loaded = self.project_service.get_project(project_id)
        if not loaded.ok or loaded.project is None:
            stage = (
                "project_missing"
                if loaded.status == "missing"
                else f"project_{loaded.status}"
            )
            return ProjectLinkResult(
                False,
                project_id,
                material_id,
                stage,
                loaded.error,
            )
        if loaded.project.archived_at or not os.access(loaded.path, os.W_OK):
            return ProjectLinkResult(
                False,
                project_id,
                material_id,
                "project_read_only",
                "project is archived or read-only",
            )
        material = self.library_service.find_existing(item_id=material_id)
        if material is None:
            return ProjectLinkResult(
                False,
                project_id,
                material_id,
                "material_missing",
                "material is not present in the central library",
            )
        ref = ProjectMaterialRef(
            material_id=material.id,
            last_known_path=material.file_path,
            file_name=material.file_name,
            added_at=now or _now(),
            metadata_snapshot={
                "mode": material.mode,
                "audio_source": material.audio_source,
                "duration_sec": material.duration_sec,
                "width": material.width,
                "height": material.height,
                "fps": material.fps,
                "file_size_bytes": material.file_size_bytes,
            },
        )
        result = self.project_service.add_material(project_id, ref, now=now)
        if not result.ok:
            return ProjectLinkResult(
                False,
                project_id,
                material_id,
                result.stage,
                result.error,
            )
        return ProjectLinkResult(
            True,
            project_id,
            material_id,
            duplicate=result.duplicate,
        )


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
