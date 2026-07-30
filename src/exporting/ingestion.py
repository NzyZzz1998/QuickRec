"""导出结果中央素材入库、持久重试与显式项目关联。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from exporting.models import ExportPlan, ExportStage
from exporting.queue_service import ExportQueueService
from exporting.queue_store import IngestionStatus
from services.recording_library import RecordingLibraryService
from utils.recording_library_store import MaterialItem, normalize_windows_path

EXPORT_EXTENSION_KEY = "quickrec.export"
EXPORT_EXTENSION_SCHEMA = 1


class ProjectMaterialLinkResult(Protocol):
    ok: bool
    project_id: str
    material_id: str
    error: str


class ProjectMaterialLinker(Protocol):
    def link_material(
        self,
        project_id: str,
        material_id: str,
    ) -> ProjectMaterialLinkResult: ...


@dataclass(frozen=True)
class ExportIngestionResult:
    ok: bool
    job_id: str
    ingestion_status: IngestionStatus
    material_id: str = ""
    already_indexed: bool = False
    error_code: str = ""
    error: str = ""


@dataclass(frozen=True)
class ExportProjectLinkResult:
    ok: bool
    job_id: str
    project_id: str
    material_id: str = ""
    error: str = ""


class ExportIngestionCoordinator:
    """把已提交 MP4 入库；编码成功与入库状态始终独立。"""

    def __init__(
        self,
        queue_service: ExportQueueService,
        library_service: RecordingLibraryService,
    ) -> None:
        self.queue_service = queue_service
        self.library_service = library_service
        self.queue_service.subscribe_succeeded(self._on_export_succeeded)

    def recover_pending(self) -> tuple[ExportIngestionResult, ...]:
        """启动后重试所有已成功但尚未入库的持久任务。"""
        return tuple(
            self.ingest(job.job_id)
            for job in self.queue_service.state.jobs
            if job.status == ExportStage.SUCCEEDED
            and job.ingestion_status != IngestionStatus.SUCCEEDED
        )

    def ingest(self, job_id: str) -> ExportIngestionResult:
        try:
            job = self.queue_service.job(job_id)
        except KeyError:
            return self._result_failed(
                job_id,
                "JOB_NOT_FOUND",
                "export job was not found",
                update_queue=False,
            )
        if job.status != ExportStage.SUCCEEDED:
            return self._result_failed(
                job_id,
                "EXPORT_NOT_SUCCEEDED",
                "only succeeded exports can be ingested",
                update_queue=False,
            )
        output = Path(job.output_path or "")
        try:
            if not output.is_file():
                raise FileNotFoundError("export output is missing")
            stat = output.stat()
        except OSError as exc:
            return self._result_failed(
                job_id,
                "OUTPUT_MISSING",
                str(exc),
            )

        normalized = normalize_windows_path(output)
        idempotency_key = _idempotency_key(
            job_id,
            normalized,
            stat.st_size,
            stat.st_mtime_ns,
        )
        existing = self.library_service.find_existing(file_path=output)
        if (
            existing is not None
            and _export_extension(existing).get("idempotency_key")
            == idempotency_key
        ):
            updated = self.queue_service.update_ingestion(
                job_id,
                IngestionStatus.SUCCEEDED,
            )
            return ExportIngestionResult(
                updated.ok,
                job_id,
                (
                    IngestionStatus.SUCCEEDED
                    if updated.ok
                    else job.ingestion_status
                ),
                existing.id,
                already_indexed=True,
                error_code="" if updated.ok else "QUEUE_WRITE_FAILED",
                error=updated.message,
            )

        material_id = (
            existing.id
            if existing is not None
            else f"export-{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:24]}"
        )
        item = _material_item(
            job_id=job_id,
            material_id=material_id,
            plan=job.plan,
            output=output,
            size_bytes=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            idempotency_key=idempotency_key,
            created_at=job.updated_at,
        )
        written = self.library_service.upsert(item)
        if not written.ok:
            return self._result_failed(
                job_id,
                "LIBRARY_WRITE_FAILED",
                written.error,
            )
        saved = self.queue_service.update_ingestion(
            job_id,
            IngestionStatus.SUCCEEDED,
        )
        actual = self.library_service.find_existing(file_path=output)
        actual_id = actual.id if actual is not None else material_id
        if not saved.ok:
            return ExportIngestionResult(
                False,
                job_id,
                job.ingestion_status,
                actual_id,
                error_code="QUEUE_WRITE_FAILED",
                error=saved.message,
            )
        return ExportIngestionResult(
            True,
            job_id,
            IngestionStatus.SUCCEEDED,
            actual_id,
        )

    def retry(self, job_id: str) -> ExportIngestionResult:
        """持久失败任务直接重试入库，不重新编码。"""
        return self.ingest(job_id)

    def add_to_project(
        self,
        job_id: str,
        project_id: str,
        *,
        linker: ProjectMaterialLinker,
    ) -> ExportProjectLinkResult:
        try:
            job = self.queue_service.job(job_id)
        except KeyError:
            return ExportProjectLinkResult(
                False,
                job_id,
                project_id,
                error="export job was not found",
            )
        if (
            job.status != ExportStage.SUCCEEDED
            or job.ingestion_status != IngestionStatus.SUCCEEDED
            or not job.output_path
        ):
            return ExportProjectLinkResult(
                False,
                job_id,
                project_id,
                error="export result is not available in the central library",
            )
        material = self.library_service.find_existing(
            file_path=job.output_path,
        )
        if material is None:
            return ExportProjectLinkResult(
                False,
                job_id,
                project_id,
                error="export material is missing from the central library",
            )
        linked = linker.link_material(project_id, material.id)
        return ExportProjectLinkResult(
            bool(linked.ok),
            job_id,
            project_id,
            material.id,
            str(linked.error or ""),
        )

    def _result_failed(
        self,
        job_id: str,
        error_code: str,
        error: str,
        *,
        update_queue: bool = True,
    ) -> ExportIngestionResult:
        if update_queue:
            updated = self.queue_service.update_ingestion(
                job_id,
                IngestionStatus.FAILED,
                error=error,
            )
            if not updated.ok:
                error = f"{error}; queue state: {updated.message}"
        return ExportIngestionResult(
            False,
            job_id,
            IngestionStatus.FAILED,
            error_code=error_code,
            error=error,
        )

    def _on_export_succeeded(self, job) -> None:
        self.ingest(job.job_id)


def _material_item(
    *,
    job_id: str,
    material_id: str,
    plan: ExportPlan,
    output: Path,
    size_bytes: int,
    mtime_ns: int,
    idempotency_key: str,
    created_at: str,
) -> MaterialItem:
    has_audio = any(
        track.kind == "audio" for track in plan.timeline.tracks
    )
    return MaterialItem(
        id=material_id,
        file_path=str(output),
        file_name=output.name,
        directory=str(output.parent),
        mode="project_export",
        audio_source="timeline" if has_audio else "none",
        created_at=created_at,
        imported_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        duration_sec=plan.timeline.duration_us / 1_000_000,
        width=plan.output.width,
        height=plan.output.height,
        fps=float(plan.output.fps),
        file_size_bytes=size_bytes,
        file_modified_ns=mtime_ns,
        source_type="export",
        extensions={
            EXPORT_EXTENSION_KEY: {
                "schema_version": EXPORT_EXTENSION_SCHEMA,
                "job_id": job_id,
                "plan_id": plan.plan_id,
                "plan_hash": plan.plan_hash,
                "project_id": plan.project.project_id,
                "normalized_path": normalize_windows_path(output),
                "size_bytes": size_bytes,
                "mtime_ns": mtime_ns,
                "idempotency_key": idempotency_key,
            }
        },
    )


def _export_extension(item: MaterialItem) -> dict[str, object]:
    raw = item.extensions.get(EXPORT_EXTENSION_KEY, {})
    return dict(raw) if isinstance(raw, dict) else {}


def _idempotency_key(
    job_id: str,
    normalized_path: str,
    size_bytes: int,
    mtime_ns: int,
) -> str:
    payload = json.dumps(
        {
            "job_id": job_id,
            "normalized_path": normalized_path,
            "size_bytes": size_bytes,
            "mtime_ns": mtime_ns,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
