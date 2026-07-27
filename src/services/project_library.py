"""QuickRec Full 项目生命周期与素材引用业务服务。"""

from __future__ import annotations

import copy
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from utils.project_store import (
    ProjectFile,
    ProjectIndexEntry,
    ProjectIndexLoadResult,
    ProjectLoadResult,
    ProjectMaterialRef,
    load_project,
    load_project_index,
    normalize_windows_path,
    recover_project_from_backup,
    resolve_default_project_root,
    resolve_project_file,
    save_project,
    save_project_index,
)


@dataclass(frozen=True)
class ProjectOperationResult:
    ok: bool
    stage: str
    path: Path
    project: ProjectFile | None = None
    entry: ProjectIndexEntry | None = None
    error: str = ""
    conflict_path: Path | None = None
    project_written: bool = False
    index_written: bool = False
    duplicate: bool = False


@dataclass(frozen=True)
class ReferenceClassificationResult:
    states: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    unreadable_project_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class _WritableProject:
    index: ProjectIndexLoadResult
    entry: ProjectIndexEntry
    project: ProjectFile
    path: Path


class ProjectLibraryService:
    def __init__(
        self,
        index_path: str | Path,
        *,
        default_root: str | Path | None = None,
    ) -> None:
        self.index_path = Path(index_path)
        self.default_root = (
            Path(default_root)
            if default_root is not None
            else resolve_default_project_root()
        )
        self._lock = threading.RLock()

    def list_entries(self) -> list[ProjectIndexEntry]:
        loaded = load_project_index(self.index_path)
        return loaded.entries if loaded.ok else []

    def get_project(self, project_id: str) -> ProjectLoadResult:
        entry = self._find_entry(project_id)
        if entry is None:
            return ProjectLoadResult(
                False,
                self.index_path,
                status="missing",
                error="project is not registered",
            )
        return load_project(entry.file_path)

    def create_project(
        self,
        *,
        name: str,
        root_path: str | Path | None = None,
        description: str = "",
        project_id: str | None = None,
        now: str | None = None,
    ) -> ProjectOperationResult:
        with self._lock:
            cleaned_name = str(name or "").strip()
            if not cleaned_name:
                return ProjectOperationResult(False, "validate", self.index_path, error="project name is required")
            timestamp = now or _now()
            stable_id = project_id or uuid.uuid4().hex
            path = resolve_project_file(root_path or self.default_root, stable_id)
            if path.parent.exists():
                return ProjectOperationResult(False, "validate", path, error="project directory already exists")
            project = ProjectFile(
                project_id=stable_id,
                name=cleaned_name,
                description=str(description or ""),
                created_at=timestamp,
                updated_at=timestamp,
            )
            try:
                written = save_project(path, project)
            except Exception as exc:
                return ProjectOperationResult(False, "project", path, project, error=str(exc))
            if not written.ok:
                return ProjectOperationResult(False, "project", path, project, error=written.error)
            entry = ProjectIndexEntry.from_project(project, path)
            index = load_project_index(self.index_path)
            if not index.ok:
                return ProjectOperationResult(
                    False,
                    "index",
                    path,
                    project,
                    entry,
                    index.error,
                    project_written=True,
                )
            try:
                indexed = save_project_index(
                    self.index_path,
                    [entry, *index.entries],
                    extensions=index.extensions,
                )
            except Exception as exc:
                return ProjectOperationResult(
                    False,
                    "index",
                    path,
                    project,
                    entry,
                    str(exc),
                    project_written=True,
                )
            if not indexed.ok:
                return ProjectOperationResult(
                    False,
                    "index",
                    path,
                    project,
                    entry,
                    indexed.error,
                    project_written=True,
                )
            return ProjectOperationResult(
                True,
                "complete",
                path,
                project,
                entry,
                project_written=True,
                index_written=True,
            )

    def register_project(
        self,
        file_path: str | Path,
        *,
        update_existing_path: bool = False,
        opened_at: str | None = None,
    ) -> ProjectOperationResult:
        with self._lock:
            path = Path(file_path)
            loaded = load_project(path)
            if not loaded.ok or loaded.project is None:
                return ProjectOperationResult(False, "validate", path, error=loaded.error)
            index = load_project_index(self.index_path)
            if not index.ok:
                return ProjectOperationResult(False, "index", path, loaded.project, error=index.error)
            existing = next(
                (
                    entry
                    for entry in index.entries
                    if entry.project_id == loaded.project.project_id
                ),
                None,
            )
            if (
                existing is not None
                and normalize_windows_path(existing.file_path)
                != normalize_windows_path(path)
                and not update_existing_path
            ):
                return ProjectOperationResult(
                    False,
                    "path_conflict",
                    path,
                    loaded.project,
                    existing,
                    "project id is already registered at another path",
                    Path(existing.file_path),
                )
            entry = ProjectIndexEntry.from_project(loaded.project, path)
            entry.last_opened_at = opened_at or _now()
            remaining = [
                item
                for item in index.entries
                if item.project_id != loaded.project.project_id
            ]
            written = save_project_index(
                self.index_path,
                [entry, *remaining],
                extensions=index.extensions,
            )
            if not written.ok:
                return ProjectOperationResult(
                    False,
                    "index",
                    path,
                    loaded.project,
                    entry,
                    written.error,
                )
            return ProjectOperationResult(
                True,
                "complete",
                path,
                loaded.project,
                entry,
                index_written=True,
            )

    def rename_project(
        self,
        project_id: str,
        new_name: str,
        *,
        now: str | None = None,
    ) -> ProjectOperationResult:
        loaded = self.get_project(project_id)
        description = (
            loaded.project.description
            if loaded.ok and loaded.project is not None
            else ""
        )
        return self.update_project_details(
            project_id,
            name=new_name,
            description=description,
            now=now,
        )

    def update_project_details(
        self,
        project_id: str,
        *,
        name: str,
        description: str,
        now: str | None = None,
    ) -> ProjectOperationResult:
        cleaned_name = str(name or "").strip()
        if not cleaned_name:
            return ProjectOperationResult(False, "validate", self.index_path, error="project name is required")
        return self._mutate_project(
            project_id,
            lambda project: _update_details(
                project,
                cleaned_name,
                str(description or ""),
                now or _now(),
            ),
        )

    def archive_project(
        self,
        project_id: str,
        *,
        now: str | None = None,
    ) -> ProjectOperationResult:
        return self._mutate_project(
            project_id,
            lambda project: _archive(project, now or _now()),
        )

    def restore_project(
        self,
        project_id: str,
        *,
        now: str | None = None,
    ) -> ProjectOperationResult:
        return self._mutate_project(
            project_id,
            lambda project: _restore(project, now or _now()),
            allow_archived=True,
        )

    def relink_project(
        self,
        project_id: str,
        candidate_path: str | Path,
    ) -> ProjectOperationResult:
        """验证移动后的项目文件，并仅更新匹配项目的中央索引路径。"""
        with self._lock:
            candidate = Path(candidate_path)
            loaded = load_project(candidate)
            if not loaded.ok or loaded.project is None:
                return ProjectOperationResult(
                    False,
                    "validate",
                    candidate,
                    error=loaded.error,
                )
            if loaded.project.project_id != project_id:
                return ProjectOperationResult(
                    False,
                    "project_id_mismatch",
                    candidate,
                    loaded.project,
                    error="candidate project_id does not match",
                )
            index = load_project_index(self.index_path)
            if not index.ok:
                return ProjectOperationResult(
                    False,
                    "index",
                    candidate,
                    loaded.project,
                    error=index.error,
                )
            current = next(
                (item for item in index.entries if item.project_id == project_id),
                None,
            )
            if current is None:
                return ProjectOperationResult(
                    False,
                    "missing",
                    candidate,
                    loaded.project,
                    error="project is not registered",
                )
            entry = ProjectIndexEntry.from_project(loaded.project, candidate)
            entry.last_opened_at = _now()
            remaining = [
                item for item in index.entries if item.project_id != project_id
            ]
            written = save_project_index(
                self.index_path,
                [entry, *remaining],
                extensions=index.extensions,
            )
            if not written.ok:
                return ProjectOperationResult(
                    False,
                    "index",
                    candidate,
                    loaded.project,
                    entry,
                    written.error,
                )
            return ProjectOperationResult(
                True,
                "complete",
                candidate,
                loaded.project,
                entry,
                index_written=True,
            )

    def recover_project(self, project_id: str) -> ProjectOperationResult:
        """经调用方确认后，从同目录有效备份恢复损坏项目。"""
        with self._lock:
            entry = self._find_entry(project_id)
            if entry is None:
                return ProjectOperationResult(
                    False,
                    "missing",
                    self.index_path,
                    error="project is not registered",
                )
            path = Path(entry.file_path)
            backup_path = path.with_name(f"{path.name}.bak")
            backup = load_project(backup_path)
            if not backup.ok or backup.project is None:
                return ProjectOperationResult(
                    False,
                    "validate_backup",
                    path,
                    error=backup.error,
                )
            if backup.project.project_id != project_id:
                return ProjectOperationResult(
                    False,
                    "project_id_mismatch",
                    path,
                    backup.project,
                    error="backup project_id does not match",
                )
            recovered = recover_project_from_backup(path)
            if not recovered.ok or recovered.project is None:
                return ProjectOperationResult(
                    False,
                    recovered.stage,
                    path,
                    recovered.project,
                    error=recovered.error,
                )
            refreshed = self.reload_project(project_id)
            if not refreshed.ok:
                return ProjectOperationResult(
                    False,
                    "index",
                    path,
                    recovered.project,
                    error=refreshed.error,
                    project_written=True,
                )
            return ProjectOperationResult(
                True,
                "complete",
                path,
                recovered.project,
                refreshed.entry,
                project_written=True,
                index_written=True,
            )

    def reload_project(self, project_id: str) -> ProjectOperationResult:
        """接受磁盘上的外部版本，并刷新中央索引指纹。"""
        with self._lock:
            index = load_project_index(self.index_path)
            if not index.ok:
                return ProjectOperationResult(
                    False,
                    "index",
                    self.index_path,
                    error=index.error,
                )
            current = next(
                (item for item in index.entries if item.project_id == project_id),
                None,
            )
            if current is None:
                return ProjectOperationResult(
                    False,
                    "missing",
                    self.index_path,
                    error="project is not registered",
                )
            path = Path(current.file_path)
            loaded = load_project(path)
            if not loaded.ok or loaded.project is None:
                return ProjectOperationResult(
                    False,
                    loaded.status,
                    path,
                    error=loaded.error,
                )
            if loaded.project.project_id != project_id:
                return ProjectOperationResult(
                    False,
                    "project_id_mismatch",
                    path,
                    loaded.project,
                    error="project_id does not match central index",
                )
            entry = ProjectIndexEntry.from_project(loaded.project, path)
            entry.last_opened_at = current.last_opened_at
            remaining = [
                item for item in index.entries if item.project_id != project_id
            ]
            written = save_project_index(
                self.index_path,
                [entry, *remaining],
                extensions=index.extensions,
            )
            if not written.ok:
                return ProjectOperationResult(
                    False,
                    "index",
                    path,
                    loaded.project,
                    entry,
                    written.error,
                )
            return ProjectOperationResult(
                True,
                "complete",
                path,
                loaded.project,
                entry,
                index_written=True,
            )

    def remove_project_entry(self, project_id: str) -> ProjectOperationResult:
        """只移除中央项目索引，不触碰项目文件或任何视频。"""
        with self._lock:
            index = load_project_index(self.index_path)
            if not index.ok:
                return ProjectOperationResult(
                    False,
                    "index",
                    self.index_path,
                    error=index.error,
                )
            current = next(
                (item for item in index.entries if item.project_id == project_id),
                None,
            )
            if current is None:
                return ProjectOperationResult(
                    False,
                    "missing",
                    self.index_path,
                    error="project is not registered",
                )
            remaining = [
                item for item in index.entries if item.project_id != project_id
            ]
            written = save_project_index(
                self.index_path,
                remaining,
                extensions=index.extensions,
            )
            if not written.ok:
                return ProjectOperationResult(
                    False,
                    "index",
                    self.index_path,
                    entry=current,
                    error=written.error,
                )
            return ProjectOperationResult(
                True,
                "complete",
                self.index_path,
                entry=current,
                index_written=True,
            )

    def add_material(
        self,
        project_id: str,
        material: ProjectMaterialRef,
        *,
        now: str | None = None,
    ) -> ProjectOperationResult:
        with self._lock:
            prepared, error = self._prepare_write(project_id)
            if error is not None:
                return error
            assert prepared is not None
            if any(item.material_id == material.material_id for item in prepared.project.materials):
                return ProjectOperationResult(
                    True,
                    "complete",
                    prepared.path,
                    prepared.project,
                    prepared.entry,
                    duplicate=True,
                )
            candidate = copy.deepcopy(prepared.project)
            candidate.materials.append(copy.deepcopy(material))
            candidate.updated_at = now or _now()
            return self._commit(prepared, candidate)

    def remove_material(
        self,
        project_id: str,
        material_id: str,
        *,
        now: str | None = None,
    ) -> ProjectOperationResult:
        with self._lock:
            prepared, error = self._prepare_write(project_id)
            if error is not None:
                return error
            assert prepared is not None
            candidate = copy.deepcopy(prepared.project)
            candidate.materials = [
                item
                for item in candidate.materials
                if item.material_id != material_id
            ]
            candidate.updated_at = now or _now()
            return self._commit(prepared, candidate)

    def classify_material_references(
        self,
        material_ids: list[str] | None = None,
    ) -> ReferenceClassificationResult:
        counts: dict[str, int] = {}
        unreadable: list[str] = []
        for entry in self.list_entries():
            loaded = load_project(entry.file_path)
            if not loaded.ok or loaded.project is None:
                unreadable.append(entry.project_id)
                continue
            for ref in loaded.project.materials:
                counts[ref.material_id] = counts.get(ref.material_id, 0) + 1
        targets = list(dict.fromkeys(material_ids or list(counts)))
        states: dict[str, str] = {}
        for material_id in targets:
            count = counts.get(material_id, 0)
            if count >= 2:
                states[material_id] = "shared"
            elif count == 1 and not unreadable:
                states[material_id] = "exclusive"
            else:
                states[material_id] = "uncertain"
        return ReferenceClassificationResult(
            states,
            counts,
            tuple(sorted(unreadable)),
        )

    def _mutate_project(
        self,
        project_id: str,
        mutate,
        *,
        allow_archived: bool = False,
    ) -> ProjectOperationResult:
        with self._lock:
            prepared, error = self._prepare_write(
                project_id,
                allow_archived=allow_archived,
            )
            if error is not None:
                return error
            assert prepared is not None
            candidate = copy.deepcopy(prepared.project)
            mutate(candidate)
            return self._commit(prepared, candidate)

    def _prepare_write(
        self,
        project_id: str,
        *,
        allow_archived: bool = False,
    ) -> tuple[_WritableProject | None, ProjectOperationResult | None]:
        index = load_project_index(self.index_path)
        if not index.ok:
            return None, ProjectOperationResult(False, "index", self.index_path, error=index.error)
        entry = next(
            (item for item in index.entries if item.project_id == project_id),
            None,
        )
        if entry is None:
            return None, ProjectOperationResult(False, "missing", self.index_path, error="project is not registered")
        path = Path(entry.file_path)
        loaded = load_project(path)
        if not loaded.ok or loaded.project is None:
            return None, ProjectOperationResult(False, loaded.status, path, error=loaded.error)
        if loaded.project.archived_at and not allow_archived:
            return None, ProjectOperationResult(
                False,
                "read_only",
                path,
                loaded.project,
                entry,
                "archived project is read-only",
            )
        try:
            current_modified_ns = path.stat().st_mtime_ns
        except OSError as exc:
            return None, ProjectOperationResult(False, "missing", path, error=str(exc))
        if entry.file_modified_ns and entry.file_modified_ns != current_modified_ns:
            return None, ProjectOperationResult(
                False,
                "external_conflict",
                path,
                loaded.project,
                entry,
                "project file changed outside QuickRec",
            )
        return _WritableProject(index, entry, loaded.project, path), None

    def _commit(
        self,
        prepared: _WritableProject,
        candidate: ProjectFile,
    ) -> ProjectOperationResult:
        try:
            written = save_project(prepared.path, candidate)
        except Exception as exc:
            return ProjectOperationResult(
                False,
                "project",
                prepared.path,
                prepared.project,
                prepared.entry,
                str(exc),
            )
        if not written.ok:
            return ProjectOperationResult(
                False,
                "project",
                prepared.path,
                prepared.project,
                prepared.entry,
                written.error,
            )
        entry = ProjectIndexEntry.from_project(candidate, prepared.path)
        entry.last_opened_at = prepared.entry.last_opened_at
        remaining = [
            item
            for item in prepared.index.entries
            if item.project_id != candidate.project_id
        ]
        indexed = save_project_index(
            self.index_path,
            [entry, *remaining],
            extensions=prepared.index.extensions,
        )
        if not indexed.ok:
            return ProjectOperationResult(
                False,
                "index",
                prepared.path,
                candidate,
                entry,
                indexed.error,
                project_written=True,
            )
        return ProjectOperationResult(
            True,
            "complete",
            prepared.path,
            candidate,
            entry,
            project_written=True,
            index_written=True,
        )

    def _find_entry(self, project_id: str) -> ProjectIndexEntry | None:
        return next(
            (
                entry
                for entry in self.list_entries()
                if entry.project_id == project_id
            ),
            None,
        )


def _update_details(
    project: ProjectFile,
    name: str,
    description: str,
    now: str,
) -> None:
    project.name = name
    project.description = description
    project.updated_at = now


def _archive(project: ProjectFile, now: str) -> None:
    project.archived_at = now
    project.updated_at = now


def _restore(project: ProjectFile, now: str) -> None:
    project.archived_at = None
    project.updated_at = now


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
