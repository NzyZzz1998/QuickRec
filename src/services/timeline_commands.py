"""QuickRec Full 时间线离散命令、撤销重做与项目事务协调。"""

from __future__ import annotations

import copy
import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from services.project_library import ProjectLibraryService
from utils.project_store import ProjectFile, load_project, save_project
from utils.timeline_model import (
    MAX_TRACKS_PER_KIND,
    Timeline,
    TimelineClip,
    TimelineTrack,
    create_empty_timeline,
    load_project_timeline,
    new_clip_id,
    new_link_group_id,
    new_track_id,
    seconds_to_microseconds,
    validate_timeline,
    with_project_timeline,
)

MAX_COMMAND_HISTORY = 50
logger = logging.getLogger("QuickRec")


@dataclass(frozen=True)
class TimelineCommandResult:
    ok: bool
    command: str
    stage: str
    timeline: Timeline | None = None
    error: str = ""
    changed: bool = False
    saved: bool = False
    requires_confirmation: bool = False
    affected_track_ids: tuple[str, ...] = ()
    affected_clip_ids: tuple[str, ...] = ()
    undo_depth: int = 0
    redo_depth: int = 0
    rolled_back: bool = False
    recovery_path: str = ""


@dataclass(frozen=True)
class _Mutation:
    affected_track_ids: tuple[str, ...] = ()
    affected_clip_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class _HistoryEntry:
    command: str
    before: Timeline
    after: Timeline
    before_project: ProjectFile
    after_project: ProjectFile


def _rebase_history_project(
    entry: _HistoryEntry,
    fresh_project: ProjectFile,
) -> _HistoryEntry:
    """让时间线历史继承最新项目素材等非时间线字段。"""
    return replace(
        entry,
        before_project=with_project_timeline(fresh_project, entry.before),
        after_project=with_project_timeline(fresh_project, entry.after),
    )


@dataclass(frozen=True)
class _PendingSave:
    command: str
    before: Timeline
    candidate: Timeline
    before_project: ProjectFile
    candidate_project: ProjectFile
    mutation: _Mutation
    mode: str = "push"
    history_entry: _HistoryEntry | None = None
    failure_stage: str = ""


class TimelineCommandService:
    """单项目时间线会话；成功提交前不会改变可见状态。"""

    def __init__(
        self,
        project_service: ProjectLibraryService,
        project_id: str,
    ) -> None:
        self.project_service = project_service
        self.project_id = project_id
        self.status = "loading"
        self.error = ""
        self._project: ProjectFile | None = None
        self._timeline: Timeline | None = None
        self._expected_modified_ns: int | None = None
        self._read_only = False
        self._runtime_read_only_reason = ""
        self._undo: list[_HistoryEntry] = []
        self._redo: list[_HistoryEntry] = []
        self._pending_save: _PendingSave | None = None
        self.reload()

    @property
    def ready(self) -> bool:
        return self._project is not None and self._timeline is not None

    @property
    def read_only(self) -> bool:
        return self._read_only or bool(self._runtime_read_only_reason)

    def set_runtime_read_only(self, active: bool, *, reason: str = "") -> None:
        """临时阻止命令写入，不覆盖项目自身的只读状态。"""
        self._runtime_read_only_reason = (
            str(reason or "timeline is temporarily read-only")
            if active
            else ""
        )
        logger.info(
            "timeline runtime write lock changed: project_id=%s active=%s",
            self.project_id,
            bool(active),
        )

    def _read_only_error(self) -> str:
        return (
            self._runtime_read_only_reason
            or self.error
            or "timeline is read-only"
        )

    @property
    def timeline(self) -> Timeline:
        if self._timeline is None:
            raise RuntimeError(self.error or "timeline session is not ready")
        return copy.deepcopy(self._timeline)

    @property
    def project(self) -> ProjectFile:
        if self._project is None:
            raise RuntimeError(self.error or "timeline session is not ready")
        return copy.deepcopy(self._project)

    @property
    def undo_depth(self) -> int:
        return len(self._undo)

    @property
    def redo_depth(self) -> int:
        return len(self._redo)

    @property
    def has_pending_save(self) -> bool:
        return self._pending_save is not None

    @property
    def pending_save_stage(self) -> str:
        pending = self._pending_save
        return pending.failure_stage if pending is not None else ""

    @property
    def timeline_backup_available(self) -> bool:
        entry = self.project_service.get_entry(self.project_id)
        if entry is None:
            return False
        project_path = Path(entry.file_path)
        backup_path = project_path.with_name(f"{project_path.name}.bak")
        loaded = load_project(backup_path)
        if (
            not loaded.ok
            or loaded.project is None
            or loaded.project.project_id != self.project_id
        ):
            return False
        timeline = load_project_timeline(loaded.project)
        return timeline.ok and timeline.timeline is not None

    def reload(self) -> None:
        self._pending_save = None
        loaded = self.project_service.get_project(self.project_id)
        entry = self.project_service.get_entry(self.project_id)
        self._undo.clear()
        self._redo.clear()
        if not loaded.ok or loaded.project is None or entry is None:
            self.status = loaded.status
            self.error = loaded.error or "project is not registered"
            self._project = None
            self._timeline = None
            self._expected_modified_ns = None
            self._read_only = True
            logger.warning(
                "timeline load failed: project_id=%s status=%s",
                self.project_id,
                self.status,
            )
            return
        timeline_result = load_project_timeline(loaded.project)
        self.status = timeline_result.status
        self.error = timeline_result.error
        self._project = copy.deepcopy(loaded.project)
        self._timeline = (
            copy.deepcopy(timeline_result.timeline)
            if timeline_result.timeline is not None
            else None
        )
        self._expected_modified_ns = entry.file_modified_ns
        self._read_only = bool(
            loaded.project.archived_at
            or timeline_result.read_only
            or not os.access(loaded.path, os.W_OK)
        )
        logger.info(
            "timeline loaded: project_id=%s schema=%s tracks=%d clips=%d "
            "result=%s read_only=%s",
            self.project_id,
            (
                self._timeline.schema_version
                if self._timeline is not None
                else "unavailable"
            ),
            len(self._timeline.tracks) if self._timeline is not None else 0,
            len(self._timeline.clips) if self._timeline is not None else 0,
            self.status,
            self.read_only,
        )

    def add_material(
        self,
        material_id: str,
        *,
        has_audio: bool,
        timeline_start_us: int | None = None,
        video_track_id: str | None = None,
        audio_track_id: str | None = None,
        now: str | None = None,
    ) -> TimelineCommandResult:
        project = self._require_project()
        if project is None:
            return self._unavailable("add_material")
        material = next(
            (item for item in project.materials if item.material_id == material_id),
            None,
        )
        if material is None:
            return self._failure(
                "add_material",
                "validate",
                f"material is not part of the project: {material_id}",
            )
        try:
            duration_us = seconds_to_microseconds(
                material.metadata_snapshot.get("duration_sec")
            )
        except ValueError as exc:
            return self._failure("add_material", "validate", str(exc))
        if duration_us <= 0:
            return self._failure(
                "add_material",
                "validate",
                "material duration must be positive",
            )

        timeline = self._require_timeline()
        if timeline is None:
            return self._unavailable("add_material")
        try:
            video_track = _resolve_track(
                timeline,
                video_track_id,
                "video",
            )
            audio_track = (
                _resolve_track(timeline, audio_track_id, "audio")
                if has_audio
                else None
            )
            if timeline_start_us is None:
                target_track_ids = [video_track.track_id]
                if audio_track is not None:
                    target_track_ids.append(audio_track.track_id)
                start_us = _first_available_start(
                    timeline,
                    target_track_ids,
                    duration_us,
                )
            else:
                start_us = _non_negative_int(
                    timeline_start_us,
                    "timeline_start_us",
                )
        except ValueError as exc:
            return self._failure("add_material", "validate", str(exc))

        video_clip_id = new_clip_id()
        audio_clip_id = new_clip_id() if audio_track is not None else None
        link_group_id = new_link_group_id() if audio_track is not None else None
        affected_clip_ids = tuple(
            item
            for item in (video_clip_id, audio_clip_id)
            if item is not None
        )
        affected_track_ids = tuple(
            item.track_id
            for item in (video_track, audio_track)
            if item is not None
        )

        def mutate(candidate: Timeline) -> _Mutation:
            candidate.clips.append(
                TimelineClip(
                    video_clip_id,
                    material_id,
                    video_track.track_id,
                    start_us,
                    duration_us,
                    0,
                    duration_us,
                    link_group_id,
                )
            )
            if audio_track is not None and audio_clip_id is not None:
                candidate.clips.append(
                    TimelineClip(
                        audio_clip_id,
                        material_id,
                        audio_track.track_id,
                        start_us,
                        duration_us,
                        0,
                        duration_us,
                        link_group_id,
                    )
                )
            return _Mutation(affected_track_ids, affected_clip_ids)

        return self._execute("add_material", mutate, now=now)

    def delete_clip(
        self,
        clip_id: str,
        *,
        confirmed: bool = False,
        now: str | None = None,
    ) -> TimelineCommandResult:
        timeline = self._require_timeline()
        if timeline is None:
            return self._unavailable("delete_clip")
        clip = _find_clip(timeline, clip_id)
        if clip is None:
            return self._failure(
                "delete_clip",
                "validate",
                f"clip does not exist: {clip_id}",
            )
        affected = _linked_clip_ids(timeline, clip)
        if len(affected) > 1 and not confirmed:
            return self._confirmation(
                "delete_clip",
                affected_clip_ids=affected,
            )

        def mutate(candidate: Timeline) -> _Mutation:
            candidate.clips = [
                item for item in candidate.clips if item.clip_id not in affected
            ]
            return _Mutation(affected_clip_ids=affected)

        return self._execute("delete_clip", mutate, now=now)

    def material_clip_ids(self, material_id: str) -> tuple[str, ...]:
        """返回当前时间线中引用指定项目素材的片段。"""
        timeline = self._require_timeline()
        if timeline is None:
            return ()
        return tuple(
            clip.clip_id
            for clip in timeline.clips
            if clip.material_id == material_id
        )

    def remove_project_material(
        self,
        material_id: str,
        *,
        confirmed: bool = False,
        now: str | None = None,
    ) -> TimelineCommandResult:
        """原子移除项目素材引用及其时间线片段。"""
        if self._pending_save is not None:
            return self._pending_save_block("remove_project_material")
        project = self._require_project()
        timeline = self._require_timeline()
        if project is None or timeline is None:
            return self._unavailable("remove_project_material")
        if not any(
            item.material_id == material_id
            for item in project.materials
        ):
            return self._failure(
                "remove_project_material",
                "validate",
                f"material is not part of the project: {material_id}",
            )
        affected_clip_ids = self.material_clip_ids(material_id)
        if affected_clip_ids and not confirmed:
            return self._confirmation(
                "remove_project_material",
                affected_clip_ids=affected_clip_ids,
            )
        if self.read_only:
            return self._failure(
                "remove_project_material",
                "read_only",
                self._read_only_error(),
            )

        before_timeline = copy.deepcopy(timeline)
        before_project = copy.deepcopy(project)
        candidate_timeline = copy.deepcopy(timeline)
        candidate_timeline.clips = [
            clip
            for clip in candidate_timeline.clips
            if clip.material_id != material_id
        ]
        candidate_project = copy.deepcopy(project)
        candidate_project.materials = [
            item
            for item in candidate_project.materials
            if item.material_id != material_id
        ]
        candidate_project = with_project_timeline(
            candidate_project,
            candidate_timeline,
        )
        try:
            validate_timeline(candidate_timeline, candidate_project)
        except Exception as exc:
            return self._failure(
                "remove_project_material",
                "validate",
                str(exc),
            )

        pending = _PendingSave(
            "remove_project_material",
            before_timeline,
            copy.deepcopy(candidate_timeline),
            before_project,
            copy.deepcopy(candidate_project),
            _Mutation(affected_clip_ids=affected_clip_ids),
        )
        result = self._commit_project_snapshot(
            "remove_project_material",
            candidate_project,
            candidate_timeline,
            now=now,
        )
        if not result.ok:
            return self._remember_pending_failure(pending, result)
        return self._complete_pending_save(pending, result)

    def retry_pending_save(
        self,
        *,
        now: str | None = None,
    ) -> TimelineCommandResult:
        pending = self._pending_save
        if pending is None:
            return self._failure(
                "retry_save",
                "empty",
                "there is no pending timeline save",
            )
        if not self._pending_history_is_valid(pending):
            return self._failure(
                "retry_save",
                "history_changed",
                "timeline history changed after the save failure",
            )
        result = self._commit_project_snapshot(
            pending.command,
            copy.deepcopy(pending.candidate_project),
            copy.deepcopy(pending.candidate),
            now=now,
        )
        if not result.ok:
            return self._remember_pending_failure(pending, result)
        logger.info(
            "timeline pending save retried: project_id=%s command=%s result=ok",
            self.project_id,
            pending.command,
        )
        return self._complete_pending_save(pending, result)

    def discard_pending_save(self) -> TimelineCommandResult:
        pending = self._pending_save
        if pending is None:
            return self._failure(
                "discard_pending_save",
                "empty",
                "there is no pending timeline save",
            )
        self._pending_save = None
        logger.info(
            "timeline pending save discarded: project_id=%s command=%s",
            self.project_id,
            pending.command,
        )
        return TimelineCommandResult(
            True,
            "discard_pending_save",
            "complete",
            copy.deepcopy(self._timeline),
            changed=False,
            saved=False,
            undo_depth=len(self._undo),
            redo_depth=len(self._redo),
        )

    def reload_external_project(self) -> TimelineCommandResult:
        refreshed = self.project_service.reload_project(self.project_id)
        if not refreshed.ok:
            logger.warning(
                "timeline external project reload failed: project_id=%s "
                "stage=%s",
                self.project_id,
                refreshed.stage,
            )
            return self._failure(
                "reload_external_project",
                refreshed.stage,
                refreshed.error,
            )
        self.reload()
        if not self.ready or self._timeline is None:
            return self._unavailable("reload_external_project")
        logger.info(
            "timeline external project reloaded: project_id=%s result=ok",
            self.project_id,
        )
        return TimelineCommandResult(
            True,
            "reload_external_project",
            "complete",
            copy.deepcopy(self._timeline),
            changed=True,
            saved=False,
            undo_depth=0,
            redo_depth=0,
        )

    def refresh_project_snapshot(self) -> TimelineCommandResult:
        """同步项目非时间线字段，并保留当前时间线及其撤销重做历史。"""
        command = "refresh_project_snapshot"
        if self._pending_save is not None:
            return self._pending_save_block(command)
        if not self.ready or self._project is None or self._timeline is None:
            return self._unavailable(command)

        loaded = self.project_service.get_project(self.project_id)
        entry = self.project_service.get_entry(self.project_id)
        if not loaded.ok or loaded.project is None or entry is None:
            return self._failure(
                command,
                loaded.status or "missing",
                loaded.error or "project is not registered",
            )
        timeline_result = load_project_timeline(loaded.project)
        if not timeline_result.ok or timeline_result.timeline is None:
            return self._failure(
                command,
                timeline_result.status,
                timeline_result.error or "project timeline is unavailable",
            )
        if timeline_result.timeline != self._timeline:
            return self._failure(
                command,
                "external_conflict",
                "project timeline changed outside the current editing session",
            )

        fresh_project = copy.deepcopy(loaded.project)
        try:
            rebased_undo = [
                _rebase_history_project(entry_item, fresh_project)
                for entry_item in self._undo
            ]
            rebased_redo = [
                _rebase_history_project(entry_item, fresh_project)
                for entry_item in self._redo
            ]
        except Exception as exc:
            return self._failure(command, "external_conflict", str(exc))

        changed = fresh_project != self._project
        self._project = fresh_project
        self._expected_modified_ns = entry.file_modified_ns
        self._undo = rebased_undo
        self._redo = rebased_redo
        self.status = timeline_result.status
        self.error = timeline_result.error
        self._read_only = bool(
            fresh_project.archived_at
            or timeline_result.read_only
            or not os.access(loaded.path, os.W_OK)
        )
        logger.info(
            "timeline project snapshot refreshed: project_id=%s "
            "materials=%d undo_depth=%d redo_depth=%d changed=%s",
            self.project_id,
            len(fresh_project.materials),
            len(self._undo),
            len(self._redo),
            changed,
        )
        return TimelineCommandResult(
            True,
            command,
            "complete",
            copy.deepcopy(self._timeline),
            changed=changed,
            saved=False,
            undo_depth=len(self._undo),
            redo_depth=len(self._redo),
        )

    def save_pending_recovery_copy(
        self,
        *,
        timestamp: str | None = None,
    ) -> TimelineCommandResult:
        pending = self._pending_save
        if pending is None:
            return self._failure(
                "save_recovery_copy",
                "empty",
                "there is no pending timeline save",
            )
        entry = self.project_service.get_entry(self.project_id)
        if entry is None:
            return self._failure(
                "save_recovery_copy",
                "missing",
                "project is not registered",
            )
        project_path = Path(entry.file_path)
        stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        recovery_path = project_path.with_name(
            f"{project_path.stem}.timeline-recovery-"
            f"{stamp}{project_path.suffix}"
        )
        suffix = 2
        while recovery_path.exists():
            recovery_path = project_path.with_name(
                f"{project_path.stem}.timeline-recovery-"
                f"{stamp}-{suffix}{project_path.suffix}"
            )
            suffix += 1
        candidate = copy.deepcopy(pending.candidate_project)
        written = save_project(recovery_path, candidate)
        if not written.ok:
            return self._failure(
                "save_recovery_copy",
                written.stage,
                written.error,
            )
        logger.info(
            "timeline recovery copy saved: project_id=%s file=%s result=ok",
            self.project_id,
            recovery_path.name,
        )
        self.reload()
        return TimelineCommandResult(
            True,
            "save_recovery_copy",
            "complete",
            copy.deepcopy(self._timeline),
            changed=False,
            saved=True,
            undo_depth=0,
            redo_depth=0,
            recovery_path=str(recovery_path),
        )

    def move_clip(
        self,
        clip_id: str,
        *,
        timeline_start_us: int,
        target_track_id: str | None = None,
        now: str | None = None,
    ) -> TimelineCommandResult:
        timeline = self._require_timeline()
        if timeline is None:
            return self._unavailable("move_clip")
        clip = _find_clip(timeline, clip_id)
        if clip is None:
            return self._failure(
                "move_clip",
                "validate",
                f"clip does not exist: {clip_id}",
            )
        try:
            start_us = _non_negative_int(
                timeline_start_us,
                "timeline_start_us",
            )
            source_track = _find_track(timeline, clip.track_id)
            target_track = (
                _find_track(timeline, target_track_id)
                if target_track_id is not None
                else source_track
            )
            if target_track.kind != source_track.kind:
                raise ValueError("clip can only move to a track of the same kind")
        except ValueError as exc:
            return self._failure("move_clip", "validate", str(exc))
        affected = _linked_clip_ids(timeline, clip)

        def mutate(candidate: Timeline) -> _Mutation:
            for item in candidate.clips:
                if item.clip_id in affected:
                    item.timeline_start_us = start_us
                if item.clip_id == clip_id:
                    item.track_id = target_track.track_id
            return _Mutation(
                affected_track_ids=(target_track.track_id,),
                affected_clip_ids=affected,
            )

        return self._execute("move_clip", mutate, now=now)

    def add_track(
        self,
        kind: str,
        *,
        name: str | None = None,
        now: str | None = None,
    ) -> TimelineCommandResult:
        timeline = self._require_timeline()
        if timeline is None:
            return self._unavailable("add_track")
        if kind not in {"video", "audio"}:
            return self._failure(
                "add_track",
                "validate",
                f"unsupported track kind: {kind}",
            )
        kind_tracks = [track for track in timeline.tracks if track.kind == kind]
        if len(kind_tracks) >= MAX_TRACKS_PER_KIND:
            return self._failure(
                "add_track",
                "validate",
                f"{kind} tracks may contain at most {MAX_TRACKS_PER_KIND} tracks",
            )
        track_id = new_track_id()
        display_name = str(name or "").strip() or _default_track_name(
            kind,
            len(kind_tracks),
        )

        def mutate(candidate: Timeline) -> _Mutation:
            current = [track for track in candidate.tracks if track.kind == kind]
            if kind == "video":
                for track in current:
                    track.order += 1
                order = 0
                insertion = next(
                    (
                        index
                        for index, track in enumerate(candidate.tracks)
                        if track.kind == "video"
                    ),
                    0,
                )
                candidate.tracks.insert(
                    insertion,
                    TimelineTrack(track_id, kind, display_name, order),
                )
            else:
                order = len(current)
                candidate.tracks.append(
                    TimelineTrack(track_id, kind, display_name, order)
                )
            return _Mutation(affected_track_ids=(track_id,))

        return self._execute("add_track", mutate, now=now)

    def rename_track(
        self,
        track_id: str,
        name: str,
        *,
        now: str | None = None,
    ) -> TimelineCommandResult:
        timeline = self._require_timeline()
        if timeline is None:
            return self._unavailable("rename_track")
        try:
            current = _find_track(timeline, track_id)
        except ValueError as exc:
            return self._failure("rename_track", "validate", str(exc))
        display_name = str(name or "").strip() or _default_track_name(
            current.kind,
            current.order,
        )

        def mutate(candidate: Timeline) -> _Mutation:
            _find_track(candidate, track_id).name = display_name
            return _Mutation(affected_track_ids=(track_id,))

        return self._execute("rename_track", mutate, now=now)

    def reorder_track(
        self,
        track_id: str,
        new_order: int,
        *,
        now: str | None = None,
    ) -> TimelineCommandResult:
        timeline = self._require_timeline()
        if timeline is None:
            return self._unavailable("reorder_track")
        try:
            current = _find_track(timeline, track_id)
            order = _non_negative_int(new_order, "new_order")
            peers = sorted(
                (track for track in timeline.tracks if track.kind == current.kind),
                key=lambda item: item.order,
            )
            if order >= len(peers):
                raise ValueError("new_order is outside the track range")
        except ValueError as exc:
            return self._failure("reorder_track", "validate", str(exc))

        def mutate(candidate: Timeline) -> _Mutation:
            candidate_track = _find_track(candidate, track_id)
            candidate_peers = sorted(
                (
                    track
                    for track in candidate.tracks
                    if track.kind == candidate_track.kind
                ),
                key=lambda item: item.order,
            )
            candidate_peers.remove(candidate_track)
            candidate_peers.insert(order, candidate_track)
            for index, track in enumerate(candidate_peers):
                track.order = index
            return _Mutation(
                affected_track_ids=(
                    track_id,
                    *(
                        track.track_id
                        for track in candidate_peers
                        if track.track_id != track_id
                    ),
                )
            )

        return self._execute("reorder_track", mutate, now=now)

    def delete_track(
        self,
        track_id: str,
        *,
        confirmed: bool = False,
        now: str | None = None,
    ) -> TimelineCommandResult:
        timeline = self._require_timeline()
        if timeline is None:
            return self._unavailable("delete_track")
        try:
            track = _find_track(timeline, track_id)
        except ValueError as exc:
            return self._failure("delete_track", "validate", str(exc))
        peers = [item for item in timeline.tracks if item.kind == track.kind]
        if len(peers) <= 1:
            return self._failure(
                "delete_track",
                "validate",
                f"at least one {track.kind} track must remain",
            )
        direct = [
            clip for clip in timeline.clips if clip.track_id == track_id
        ]
        affected_ids: set[str] = {clip.clip_id for clip in direct}
        for clip in direct:
            affected_ids.update(_linked_clip_ids(timeline, clip))
        affected = tuple(
            clip.clip_id
            for clip in timeline.clips
            if clip.clip_id in affected_ids
        )
        if affected and not confirmed:
            return self._confirmation(
                "delete_track",
                affected_track_ids=(track_id,),
                affected_clip_ids=affected,
            )

        def mutate(candidate: Timeline) -> _Mutation:
            candidate.tracks = [
                item for item in candidate.tracks if item.track_id != track_id
            ]
            candidate.clips = [
                item
                for item in candidate.clips
                if item.clip_id not in affected_ids
            ]
            _normalize_track_orders(candidate, track.kind)
            return _Mutation(
                affected_track_ids=(track_id,),
                affected_clip_ids=affected,
            )

        return self._execute("delete_track", mutate, now=now)

    def undo(self, *, now: str | None = None) -> TimelineCommandResult:
        if self._pending_save is not None:
            return self._pending_save_block("undo")
        if not self._undo:
            return self._failure("undo", "empty", "there is nothing to undo")
        entry = self._undo[-1]
        assert self._timeline is not None
        assert self._project is not None
        pending = _PendingSave(
            "undo",
            copy.deepcopy(self._timeline),
            copy.deepcopy(entry.before),
            copy.deepcopy(self._project),
            copy.deepcopy(entry.before_project),
            _Mutation(),
            mode="undo",
            history_entry=entry,
        )
        result = self._commit_project_snapshot(
            "undo",
            copy.deepcopy(entry.before_project),
            copy.deepcopy(entry.before),
            now=now,
        )
        if not result.ok:
            return self._remember_pending_failure(pending, result)
        return self._complete_pending_save(pending, result)

    def redo(self, *, now: str | None = None) -> TimelineCommandResult:
        if self._pending_save is not None:
            return self._pending_save_block("redo")
        if not self._redo:
            return self._failure("redo", "empty", "there is nothing to redo")
        entry = self._redo[-1]
        assert self._timeline is not None
        assert self._project is not None
        pending = _PendingSave(
            "redo",
            copy.deepcopy(self._timeline),
            copy.deepcopy(entry.after),
            copy.deepcopy(self._project),
            copy.deepcopy(entry.after_project),
            _Mutation(),
            mode="redo",
            history_entry=entry,
        )
        result = self._commit_project_snapshot(
            "redo",
            copy.deepcopy(entry.after_project),
            copy.deepcopy(entry.after),
            now=now,
        )
        if not result.ok:
            return self._remember_pending_failure(pending, result)
        return self._complete_pending_save(pending, result)

    def recover_timeline_from_backup(self) -> TimelineCommandResult:
        if self.status != "corrupt":
            return self._failure(
                "recover_timeline",
                "invalid_state",
                "timeline is not corrupt",
            )
        if not self.timeline_backup_available:
            return self._failure(
                "recover_timeline",
                "validate_backup",
                "valid project backup is unavailable",
            )
        recovered = self.project_service.recover_project(self.project_id)
        if not recovered.ok:
            return self._failure(
                "recover_timeline",
                recovered.stage,
                recovered.error,
            )
        self.reload()
        if not self.ready or self._timeline is None:
            return self._failure(
                "recover_timeline",
                self.status,
                self.error or "recovered timeline is unavailable",
            )
        logger.info(
            "timeline recovered: project_id=%s source=project_backup "
            "tracks=%d clips=%d result=ok",
            self.project_id,
            len(self._timeline.tracks),
            len(self._timeline.clips),
        )
        return TimelineCommandResult(
            True,
            "recover_timeline",
            "complete",
            copy.deepcopy(self._timeline),
            changed=True,
            saved=True,
        )

    def rebuild_empty_timeline(
        self,
        *,
        now: str | None = None,
    ) -> TimelineCommandResult:
        if self.status != "corrupt" or self._project is None:
            return self._failure(
                "rebuild_timeline",
                "invalid_state",
                "timeline is not corrupt",
            )
        entry = self.project_service.get_entry(self.project_id)
        if entry is None:
            return self._failure(
                "rebuild_timeline",
                "missing",
                "project is not registered",
            )
        project_path = Path(entry.file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        preserved_path = project_path.with_name(
            f"{project_path.stem}.timeline-corrupt-"
            f"{timestamp}{project_path.suffix}"
        )
        try:
            shutil.copy2(project_path, preserved_path)
        except OSError as exc:
            return self._failure(
                "rebuild_timeline",
                "preserve_corrupt",
                str(exc),
            )
        refreshed = self.project_service.reload_project(self.project_id)
        if not refreshed.ok or refreshed.entry is None:
            return self._failure(
                "rebuild_timeline",
                refreshed.stage,
                refreshed.error,
            )

        timeline = create_empty_timeline(self.project_id)
        candidate = with_project_timeline(self._project, timeline)
        candidate.updated_at = now or _now()
        committed = self.project_service.commit_project_candidate(
            self.project_id,
            candidate,
            expected_modified_ns=refreshed.entry.file_modified_ns,
        )
        if not committed.ok:
            return self._failure(
                "rebuild_timeline",
                committed.stage,
                committed.error,
            )
        self.reload()
        if not self.ready or self._timeline is None:
            return self._failure(
                "rebuild_timeline",
                self.status,
                self.error or "empty timeline could not be loaded",
            )
        logger.info(
            "timeline recovered: project_id=%s source=empty_rebuild "
            "tracks=%d clips=%d result=ok",
            self.project_id,
            len(self._timeline.tracks),
            len(self._timeline.clips),
        )
        return TimelineCommandResult(
            True,
            "rebuild_timeline",
            "complete",
            copy.deepcopy(self._timeline),
            changed=True,
            saved=True,
        )

    def _execute(
        self,
        command: str,
        mutate: Callable[[Timeline], _Mutation],
        *,
        now: str | None,
    ) -> TimelineCommandResult:
        if self._pending_save is not None:
            return self._pending_save_block(command)
        if not self.ready:
            return self._unavailable(command)
        if self.read_only:
            return self._failure(
                command,
                "read_only",
                self._read_only_error(),
            )
        assert self._timeline is not None
        assert self._project is not None
        before = copy.deepcopy(self._timeline)
        before_project = copy.deepcopy(self._project)
        candidate = copy.deepcopy(self._timeline)
        try:
            mutation = mutate(candidate)
            validate_timeline(candidate, self._project)
        except Exception as exc:
            return self._failure(command, "validate", str(exc))
        if candidate == before:
            return TimelineCommandResult(
                True,
                command,
                "noop",
                copy.deepcopy(self._timeline),
                changed=False,
                undo_depth=len(self._undo),
                redo_depth=len(self._redo),
            )
        candidate_project = with_project_timeline(before_project, candidate)
        pending = _PendingSave(
            command,
            before,
            copy.deepcopy(candidate),
            before_project,
            copy.deepcopy(candidate_project),
            mutation,
        )
        result = self._commit_project_snapshot(
            command,
            candidate_project,
            candidate,
            now=now,
        )
        if not result.ok:
            return self._remember_pending_failure(pending, result)
        return self._complete_pending_save(pending, result)

    def _commit_timeline(
        self,
        command: str,
        candidate: Timeline,
        *,
        now: str | None,
    ) -> TimelineCommandResult:
        if not self.ready or self._project is None:
            return self._unavailable(command)
        if self.read_only:
            return self._failure(
                command,
                "read_only",
                self._read_only_error(),
            )
        candidate_project = with_project_timeline(self._project, candidate)
        return self._commit_project_snapshot(
            command,
            candidate_project,
            candidate,
            now=now,
        )

    def _commit_project_snapshot(
        self,
        command: str,
        candidate_project: ProjectFile,
        candidate_timeline: Timeline,
        *,
        now: str | None,
    ) -> TimelineCommandResult:
        if not self.ready:
            return self._unavailable(command)
        if self.read_only:
            return self._failure(
                command,
                "read_only",
                self._read_only_error(),
            )
        candidate_project = with_project_timeline(
            candidate_project,
            candidate_timeline,
        )
        candidate_project.updated_at = now or _now()
        committed = self.project_service.commit_project_candidate(
            self.project_id,
            candidate_project,
            expected_modified_ns=self._expected_modified_ns,
        )
        if not committed.ok:
            logger.warning(
                "timeline save failed: project_id=%s command=%s "
                "stage=%s rolled_back=%s",
                self.project_id,
                command,
                committed.stage,
                committed.rolled_back,
            )
            return TimelineCommandResult(
                False,
                command,
                committed.stage,
                copy.deepcopy(self._timeline),
                committed.error,
                rolled_back=committed.rolled_back,
                undo_depth=len(self._undo),
                redo_depth=len(self._redo),
            )
        if committed.project is None or committed.entry is None:
            return self._failure(
                command,
                "commit",
                "project commit returned no persisted state",
            )
        self._project = copy.deepcopy(committed.project)
        self._timeline = copy.deepcopy(candidate_timeline)
        self._expected_modified_ns = committed.entry.file_modified_ns
        self.status = "ready"
        self.error = ""
        logger.info(
            "timeline command saved: project_id=%s command=%s "
            "tracks=%d clips=%d result=ok",
            self.project_id,
            command,
            len(candidate_timeline.tracks),
            len(candidate_timeline.clips),
        )
        return TimelineCommandResult(
            True,
            command,
            "complete",
            copy.deepcopy(candidate_timeline),
            changed=True,
            saved=True,
            undo_depth=len(self._undo),
            redo_depth=len(self._redo),
        )

    def _push_history(self, entry: _HistoryEntry) -> None:
        self._undo.append(entry)
        if len(self._undo) > MAX_COMMAND_HISTORY:
            del self._undo[: len(self._undo) - MAX_COMMAND_HISTORY]
        self._redo.clear()

    def _remember_pending_failure(
        self,
        pending: _PendingSave,
        result: TimelineCommandResult,
    ) -> TimelineCommandResult:
        self._pending_save = replace(
            pending,
            failure_stage=result.stage,
        )
        return replace(
            result,
            affected_track_ids=pending.mutation.affected_track_ids,
            affected_clip_ids=pending.mutation.affected_clip_ids,
        )

    def _complete_pending_save(
        self,
        pending: _PendingSave,
        result: TimelineCommandResult,
    ) -> TimelineCommandResult:
        assert self._project is not None
        if pending.mode == "push":
            self._push_history(
                _HistoryEntry(
                    pending.command,
                    copy.deepcopy(pending.before),
                    copy.deepcopy(pending.candidate),
                    copy.deepcopy(pending.before_project),
                    copy.deepcopy(self._project),
                )
            )
        elif pending.mode == "undo":
            assert pending.history_entry is not None
            assert self._undo and self._undo[-1] == pending.history_entry
            self._undo.pop()
            self._redo.append(pending.history_entry)
        elif pending.mode == "redo":
            assert pending.history_entry is not None
            assert self._redo and self._redo[-1] == pending.history_entry
            self._redo.pop()
            self._undo.append(pending.history_entry)
        else:
            raise RuntimeError(f"unknown pending save mode: {pending.mode}")
        self._pending_save = None
        logger.info(
            "timeline history changed: project_id=%s command=%s "
            "undo_depth=%d redo_depth=%d result=ok",
            self.project_id,
            pending.command,
            len(self._undo),
            len(self._redo),
        )
        return replace(
            result,
            affected_track_ids=pending.mutation.affected_track_ids,
            affected_clip_ids=pending.mutation.affected_clip_ids,
            undo_depth=len(self._undo),
            redo_depth=len(self._redo),
        )

    def _pending_history_is_valid(self, pending: _PendingSave) -> bool:
        if pending.mode == "undo":
            return bool(
                pending.history_entry is not None
                and self._undo
                and self._undo[-1] == pending.history_entry
            )
        if pending.mode == "redo":
            return bool(
                pending.history_entry is not None
                and self._redo
                and self._redo[-1] == pending.history_entry
            )
        return True

    def _pending_save_block(self, command: str) -> TimelineCommandResult:
        return self._failure(
            command,
            "pending_save",
            "resolve the previous timeline save failure before editing again",
        )

    def _require_project(self) -> ProjectFile | None:
        return self._project

    def _require_timeline(self) -> Timeline | None:
        return self._timeline

    def _unavailable(self, command: str) -> TimelineCommandResult:
        return self._failure(
            command,
            self.status or "unavailable",
            self.error or "timeline session is not ready",
        )

    def _failure(
        self,
        command: str,
        stage: str,
        error: str,
    ) -> TimelineCommandResult:
        logger.warning(
            "timeline command failed: project_id=%s command=%s stage=%s",
            self.project_id,
            command,
            stage,
        )
        return TimelineCommandResult(
            False,
            command,
            stage,
            copy.deepcopy(self._timeline),
            error,
            undo_depth=len(self._undo),
            redo_depth=len(self._redo),
        )

    def _confirmation(
        self,
        command: str,
        *,
        affected_track_ids: tuple[str, ...] = (),
        affected_clip_ids: tuple[str, ...] = (),
    ) -> TimelineCommandResult:
        return TimelineCommandResult(
            False,
            command,
            "confirm",
            copy.deepcopy(self._timeline),
            requires_confirmation=True,
            affected_track_ids=affected_track_ids,
            affected_clip_ids=affected_clip_ids,
            undo_depth=len(self._undo),
            redo_depth=len(self._redo),
        )


def _resolve_track(
    timeline: Timeline,
    track_id: str | None,
    expected_kind: str,
) -> TimelineTrack:
    if track_id is None:
        tracks = sorted(
            (track for track in timeline.tracks if track.kind == expected_kind),
            key=lambda item: item.order,
        )
        if not tracks:
            raise ValueError(f"no {expected_kind} track is available")
        return tracks[0]
    track = _find_track(timeline, track_id)
    if track.kind != expected_kind:
        raise ValueError(
            f"track {track_id} is not a {expected_kind} track"
        )
    return track


def _find_track(timeline: Timeline, track_id: str | None) -> TimelineTrack:
    track = next(
        (item for item in timeline.tracks if item.track_id == track_id),
        None,
    )
    if track is None:
        raise ValueError(f"track does not exist: {track_id}")
    return track


def _find_clip(timeline: Timeline, clip_id: str) -> TimelineClip | None:
    return next(
        (item for item in timeline.clips if item.clip_id == clip_id),
        None,
    )


def _linked_clip_ids(
    timeline: Timeline,
    clip: TimelineClip,
) -> tuple[str, ...]:
    if not clip.link_group_id:
        return (clip.clip_id,)
    return tuple(
        item.clip_id
        for item in timeline.clips
        if item.link_group_id == clip.link_group_id
    )


def _first_available_start(
    timeline: Timeline,
    track_ids: list[str],
    duration_us: int,
) -> int:
    start_us = 0
    while True:
        conflicts = [
            clip
            for clip in timeline.clips
            if clip.track_id in track_ids
            and start_us < clip.timeline_end_us
            and start_us + duration_us > clip.timeline_start_us
        ]
        if not conflicts:
            return start_us
        start_us = max(clip.timeline_end_us for clip in conflicts)


def _normalize_track_orders(timeline: Timeline, kind: str) -> None:
    tracks = sorted(
        (track for track in timeline.tracks if track.kind == kind),
        key=lambda item: item.order,
    )
    for index, track in enumerate(tracks):
        track.order = index


def _default_track_name(kind: str, zero_based_order: int) -> str:
    label = "视频" if kind == "video" else "音频"
    return f"{label} {zero_based_order + 1}"


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
