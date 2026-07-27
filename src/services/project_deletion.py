"""项目安全删除的引用分类、预检与回收站协调。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from services.project_library import ProjectLibraryService
from services.recording_library import RecordingLibraryService
from utils.recording_library_store import LibraryWriteResult
from utils.recycle_bin import RecycleResult, recycle_file

logger = logging.getLogger("QuickRec")


@dataclass(frozen=True)
class ProjectDeletionMaterial:
    material_id: str
    file_name: str
    file_path: str
    state: str
    selectable: bool


@dataclass(frozen=True)
class ProjectDeletionPlan:
    ok: bool
    project_id: str
    project_name: str = ""
    project_path: Path = Path()
    materials: tuple[ProjectDeletionMaterial, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)
    selected_ids: tuple[str, ...] = ()
    error: str = ""


@dataclass(frozen=True)
class ProjectDeletionItemResult:
    kind: str
    item_id: str
    path: str
    ok: bool
    error: str = ""


@dataclass(frozen=True)
class ProjectDeletionResult:
    ok: bool
    stage: str
    project_id: str
    project_path: Path
    item_results: tuple[ProjectDeletionItemResult, ...] = ()
    project_recycled: bool = False
    index_removed: bool = False
    error: str = ""


class ProjectDeletionCoordinator:
    """确保视频、项目文件和中央索引按可判断顺序提交。"""

    def __init__(
        self,
        project_service: ProjectLibraryService,
        material_service: RecordingLibraryService,
        *,
        recycle_material: Callable[[str], LibraryWriteResult] | None = None,
        recycle_project: Callable[[Path], RecycleResult] = recycle_file,
    ) -> None:
        self.project_service = project_service
        self.material_service = material_service
        self._recycle_material = recycle_material or material_service.recycle
        self._recycle_project = recycle_project

    def build_plan(self, project_id: str) -> ProjectDeletionPlan:
        entry = next(
            (
                item
                for item in self.project_service.list_entries()
                if item.project_id == project_id
            ),
            None,
        )
        loaded = self.project_service.get_project(project_id)
        if entry is None or not loaded.ok or loaded.project is None:
            return ProjectDeletionPlan(
                False,
                project_id,
                project_name=entry.name if entry else "",
                project_path=Path(entry.file_path) if entry else Path(),
                error=loaded.error or "project is unavailable",
            )
        material_ids = [
            reference.material_id for reference in loaded.project.materials
        ]
        classified = self.project_service.classify_material_references(
            material_ids
        )
        materials: list[ProjectDeletionMaterial] = []
        counts = {"exclusive": 0, "shared": 0, "uncertain": 0}
        for reference in loaded.project.materials:
            material = self.material_service.find_existing(
                item_id=reference.material_id
            )
            state = classified.states.get(reference.material_id, "uncertain")
            file_path = (
                material.file_path
                if material is not None
                else reference.last_known_path
            )
            file_name = (
                material.file_name
                if material is not None
                else reference.file_name
            )
            if (
                state == "exclusive"
                and material is not None
                and Path(material.file_path).is_file()
            ):
                selectable = True
            else:
                selectable = False
                if state == "exclusive":
                    state = "uncertain"
            counts[state] = counts.get(state, 0) + 1
            materials.append(
                ProjectDeletionMaterial(
                    reference.material_id,
                    file_name,
                    file_path,
                    state,
                    selectable,
                )
            )
        return ProjectDeletionPlan(
            True,
            project_id,
            loaded.project.name,
            loaded.path,
            tuple(materials),
            counts,
        )

    def execute(
        self,
        plan: ProjectDeletionPlan,
        *,
        selected_material_ids: list[str],
    ) -> ProjectDeletionResult:
        if not plan.ok:
            return self._failure(
                "validate_plan",
                plan,
                error=plan.error,
            )
        selected = set(selected_material_ids)
        candidates = {
            item.material_id: item
            for item in plan.materials
            if item.selectable
        }
        if selected - candidates.keys():
            return self._failure(
                "validate_selection",
                plan,
                error="only exclusive and available materials can be recycled",
            )
        if not plan.project_path.is_file():
            return self._failure(
                "preflight",
                plan,
                error="project file does not exist",
            )
        for material_id in selected:
            candidate = candidates[material_id]
            if not Path(candidate.file_path).is_file():
                return self._failure(
                    "preflight",
                    plan,
                    error=f"material file does not exist: {candidate.file_name}",
                )

        item_results: list[ProjectDeletionItemResult] = []
        for material_id in selected_material_ids:
            candidate = candidates[material_id]
            result = self._recycle_material(material_id)
            item_results.append(
                ProjectDeletionItemResult(
                    "material",
                    material_id,
                    candidate.file_path,
                    result.ok,
                    result.error,
                )
            )
            if not result.ok:
                logger.warning(
                    "project delete stopped after material recycle failure: "
                    "project_id=%s material_id=%s error=%s",
                    plan.project_id,
                    material_id,
                    result.error,
                )
                return ProjectDeletionResult(
                    False,
                    "material_recycle",
                    plan.project_id,
                    plan.project_path,
                    tuple(item_results),
                    error=result.error,
                )

        project_result = self._recycle_project(plan.project_path)
        item_results.append(
            ProjectDeletionItemResult(
                "project",
                plan.project_id,
                str(plan.project_path),
                project_result.ok,
                project_result.error,
            )
        )
        if not project_result.ok:
            return ProjectDeletionResult(
                False,
                "project_recycle",
                plan.project_id,
                plan.project_path,
                tuple(item_results),
                error=project_result.error,
            )
        removed = self.project_service.remove_project_entry(plan.project_id)
        if not removed.ok:
            logger.error(
                "project recycled but central index removal failed: "
                "project_id=%s error=%s",
                plan.project_id,
                removed.error,
            )
            return ProjectDeletionResult(
                False,
                "index",
                plan.project_id,
                plan.project_path,
                tuple(item_results),
                project_recycled=True,
                error=removed.error,
            )
        logger.info(
            "project moved to recycle bin and index removed: project_id=%s",
            plan.project_id,
        )
        return ProjectDeletionResult(
            True,
            "complete",
            plan.project_id,
            plan.project_path,
            tuple(item_results),
            project_recycled=True,
            index_removed=True,
        )

    @staticmethod
    def _failure(
        stage: str,
        plan: ProjectDeletionPlan,
        *,
        error: str,
    ) -> ProjectDeletionResult:
        return ProjectDeletionResult(
            False,
            stage,
            plan.project_id,
            plan.project_path,
            error=error,
        )
