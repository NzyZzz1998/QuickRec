from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from exporting.ingestion import ExportIngestionCoordinator
from exporting.models import (
    ExportClip,
    ExportMaterialSnapshot,
    ExportOutputSpec,
    ExportPlan,
    ExportProjectSnapshot,
    ExportStage,
    ExportTimelineSnapshot,
    ExportTrack,
    RenderPolicy,
)
from exporting.queue_service import ExportAttemptResult, ExportQueueService
from exporting.queue_store import (
    QUEUE_SCHEMA_VERSION,
    ExportJob,
    ExportQueueState,
    ExportQueueStore,
    IngestionStatus,
)
from services.recording_library import RecordingLibraryService
from utils.recording_library_store import (
    LibraryWriteResult,
    normalize_windows_path,
)


class _SuccessRunner:
    def run(
        self,
        plan,
        *,
        attempt_id,
        cancel_token,
        on_progress,
        on_stage,
    ):
        del attempt_id, cancel_token, on_progress
        on_stage(ExportStage.RUNNING)
        return ExportAttemptResult(
            ExportStage.SUCCEEDED,
            target_path=plan.output.target_path,
        )


def _plan(tmp_path: Path, plan_id: str = "plan-1") -> ExportPlan:
    source = tmp_path / "源 素材.mp4"
    source.write_bytes(b"source")
    stat = source.stat()
    return ExportPlan.create(
        plan_id=plan_id,
        created_at="2026-07-29T12:00:00+00:00",
        project=ExportProjectSnapshot(
            "project-1",
            "导出项目",
            str(tmp_path / "project.qrproj"),
            1,
            2,
        ),
        timeline=ExportTimelineSnapshot(
            "timeline-1",
            1_000_000,
            (ExportTrack("video-1", "video", 0),),
            (
                ExportClip(
                    "clip-1",
                    "source-1",
                    "video-1",
                    None,
                    0,
                    1_000_000,
                    0,
                    1_000_000,
                ),
            ),
        ),
        materials=(
            ExportMaterialSnapshot(
                "source-1",
                str(source),
                normalize_windows_path(source),
                stat.st_size,
                stat.st_mtime_ns,
                "mov,mp4,m4a,3gp,3g2,mj2",
                "h264",
                320,
                180,
                30.0,
                1_000_000,
                None,
                None,
                None,
                None,
            ),
        ),
        render_policy=RenderPolicy(),
        output=ExportOutputSpec(
            320,
            180,
            30,
            str(tmp_path / "Exports"),
            f"{plan_id}.mp4",
        ),
    )


def _services(
    tmp_path: Path,
    *,
    plan_id: str = "plan-1",
) -> tuple[
    ExportQueueService,
    ExportQueueStore,
    RecordingLibraryService,
    ExportIngestionCoordinator,
    Path,
]:
    plan = _plan(tmp_path, plan_id)
    output = plan.output.target_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"exported-video")
    now = "2026-07-29T12:01:00+00:00"
    store = ExportQueueStore(tmp_path / "appdata" / "Exports" / "queue.json")
    assert store.save(
        ExportQueueState(
            QUEUE_SCHEMA_VERSION,
            True,
            now,
            (
                ExportJob(
                    "job-1",
                    plan,
                    ExportStage.SUCCEEDED,
                    now,
                    now,
                    output_path=str(output),
                ),
            ),
        )
    ).ok
    queue = ExportQueueService(store)
    assert queue.initialize().ok
    library = RecordingLibraryService(
        tmp_path / "appdata" / "QuickRec" / "recordings.json"
    )
    coordinator = ExportIngestionCoordinator(queue, library)
    return queue, store, library, coordinator, output


def test_successful_export_is_indexed_and_queue_status_is_separate(
    tmp_path: Path,
) -> None:
    queue, _store, library, coordinator, output = _services(tmp_path)

    result = coordinator.ingest("job-1")

    assert result.ok
    assert result.material_id
    assert result.already_indexed is False
    assert queue.job("job-1").status == ExportStage.SUCCEEDED
    assert queue.job("job-1").ingestion_status == IngestionStatus.SUCCEEDED
    item = library.load().items[0]
    assert Path(item.file_path) == output
    assert item.source_type == "export"
    assert item.mode == "project_export"
    assert item.extensions["quickrec.export"]["job_id"] == "job-1"
    assert item.extensions["quickrec.export"]["idempotency_key"]


def test_queue_success_automatically_triggers_ingestion(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan.output.target_path.parent.mkdir(parents=True, exist_ok=True)
    plan.output.target_path.write_bytes(b"exported-video")
    store = ExportQueueStore(tmp_path / "appdata" / "Exports" / "queue.json")
    queue = ExportQueueService(store, runner=_SuccessRunner())
    assert queue.initialize().ok
    library = RecordingLibraryService(
        tmp_path / "appdata" / "QuickRec" / "recordings.json"
    )
    ExportIngestionCoordinator(queue, library)
    assert queue.enqueue(plan).ok
    assert queue.resume().ok

    result = queue.run_next()

    assert result.status == ExportStage.SUCCEEDED
    assert queue.job(result.job_id or "").ingestion_status == IngestionStatus.SUCCEEDED
    assert len(library.load().items) == 1


def test_startup_recovery_retries_persisted_ingestion_failure(
    tmp_path: Path,
) -> None:
    queue, _store, library, coordinator, _output = _services(tmp_path)

    recovered = coordinator.recover_pending()

    assert len(recovered) == 1
    assert recovered[0].ok
    assert queue.job("job-1").ingestion_status == IngestionStatus.SUCCEEDED
    assert len(library.load().items) == 1


def test_repeated_ingestion_is_idempotent(tmp_path: Path) -> None:
    queue, _store, library, coordinator, _output = _services(tmp_path)

    first = coordinator.ingest("job-1")
    second = coordinator.ingest("job-1")

    assert first.ok
    assert second.ok
    assert second.already_indexed
    assert second.material_id == first.material_id
    assert len(library.load().items) == 1
    assert queue.job("job-1").ingestion_status == IngestionStatus.SUCCEEDED


def test_library_failure_preserves_export_success_and_can_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    queue, _store, library, coordinator, output = _services(tmp_path)
    original = library.upsert
    monkeypatch.setattr(
        library,
        "upsert",
        lambda _item: LibraryWriteResult(
            False,
            library.library_path,
            error="index denied",
        ),
    )

    failed = coordinator.ingest("job-1")

    assert not failed.ok
    assert failed.error == "index denied"
    assert output.is_file()
    assert queue.job("job-1").status == ExportStage.SUCCEEDED
    assert queue.job("job-1").ingestion_status == IngestionStatus.FAILED
    assert queue.job("job-1").ingestion_error == "index denied"

    monkeypatch.setattr(library, "upsert", original)
    retried = coordinator.retry("job-1")

    assert retried.ok
    assert len(library.load().items) == 1
    assert queue.job("job-1").ingestion_status == IngestionStatus.SUCCEEDED


def test_missing_output_marks_only_ingestion_failed(tmp_path: Path) -> None:
    queue, _store, _library, coordinator, output = _services(tmp_path)
    output.unlink()

    result = coordinator.ingest("job-1")

    assert not result.ok
    assert result.error_code == "OUTPUT_MISSING"
    assert queue.job("job-1").status == ExportStage.SUCCEEDED
    assert queue.job("job-1").ingestion_status == IngestionStatus.FAILED


def test_same_output_path_from_new_job_updates_without_duplicate(
    tmp_path: Path,
) -> None:
    queue, store, library, coordinator, output = _services(tmp_path)
    first = coordinator.ingest("job-1")
    assert first.ok
    first_id = first.material_id

    output.write_bytes(b"new-exported-video")
    plan = queue.job("job-1").plan
    now = "2026-07-29T12:02:00+00:00"
    state = queue.state
    second_job = ExportJob(
        "job-2",
        plan,
        ExportStage.SUCCEEDED,
        now,
        now,
        output_path=str(output),
    )
    assert store.save(
        ExportQueueState(
            state.schema_version,
            state.paused,
            now,
            (*state.jobs, second_job),
        )
    ).ok
    assert queue.initialize().ok

    second = coordinator.ingest("job-2")

    assert second.ok
    assert second.material_id == first_id
    items = library.load().items
    assert len(items) == 1
    assert items[0].file_size_bytes == output.stat().st_size
    assert items[0].extensions["quickrec.export"]["job_id"] == "job-2"


@dataclass
class _LinkResult:
    ok: bool
    project_id: str
    material_id: str
    error: str = ""


class _ProjectLinker:
    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[tuple[str, str]] = []

    def link_material(
        self,
        project_id: str,
        material_id: str,
    ) -> _LinkResult:
        self.calls.append((project_id, material_id))
        return _LinkResult(
            self.ok,
            project_id,
            material_id,
            "" if self.ok else "project is read-only",
        )


def test_add_to_project_is_explicit_and_failure_does_not_change_ingestion(
    tmp_path: Path,
) -> None:
    queue, _store, library, coordinator, _output = _services(tmp_path)
    ingested = coordinator.ingest("job-1")
    linker = _ProjectLinker(ok=False)

    linked = coordinator.add_to_project(
        "job-1",
        "project-1",
        linker=linker,
    )

    assert not linked.ok
    assert linker.calls == [("project-1", ingested.material_id)]
    assert len(library.load().items) == 1
    assert queue.job("job-1").ingestion_status == IngestionStatus.SUCCEEDED


def test_non_succeeded_job_cannot_be_marked_as_ingested(tmp_path: Path) -> None:
    queue, store, _library, _coordinator, _output = _services(tmp_path)
    job = queue.job("job-1")
    state = queue.state
    queued = ExportJob(
        job.job_id,
        job.plan,
        ExportStage.QUEUED,
        job.created_at,
        job.updated_at,
    )
    assert store.save(
        ExportQueueState(
            state.schema_version,
            state.paused,
            state.updated_at,
            (queued,),
        )
    ).ok
    assert queue.initialize().ok

    updated = queue.update_ingestion(
        "job-1",
        IngestionStatus.SUCCEEDED,
    )

    assert not updated.ok
    assert queue.job("job-1").ingestion_status == IngestionStatus.PENDING
