from __future__ import annotations

import json
from pathlib import Path

import pytest

from exporting import queue_store as queue_store_module
from exporting.models import (
    ExportClip,
    ExportFailureKind,
    ExportMaterialSnapshot,
    ExportOutputSpec,
    ExportPlan,
    ExportProjectSnapshot,
    ExportStage,
    ExportTimelineSnapshot,
    ExportTrack,
    ExportValidationError,
    RenderPolicy,
)
from exporting.queue_store import (
    AttemptTrigger,
    ExportAttempt,
    ExportJob,
    ExportQueueState,
    ExportQueueStore,
    IngestionStatus,
    QueueLoadStatus,
)
from utils.recording_library_store import normalize_windows_path


def _plan(tmp_path: Path, plan_id: str = "plan-1") -> ExportPlan:
    source = tmp_path / f"{plan_id} 素材.mp4"
    source.write_bytes(b"source")
    stat = source.stat()
    return ExportPlan.create(
        plan_id=plan_id,
        created_at="2026-07-29T12:00:00+00:00",
        project=ExportProjectSnapshot(
            "project-1",
            "队列项目",
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
                    "material-1",
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
                "material-1",
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


def _state(tmp_path: Path) -> ExportQueueState:
    attempt = ExportAttempt(
        attempt_id="attempt-1",
        sequence=1,
        trigger=AttemptTrigger.INITIAL,
        status=ExportStage.FAILED,
        created_at="2026-07-29T12:00:01+00:00",
        started_at="2026-07-29T12:00:02+00:00",
        completed_at="2026-07-29T12:00:03+00:00",
        failure_kind=ExportFailureKind.TOOL_FAILED,
        message="ffmpeg failed",
    )
    job = ExportJob(
        job_id="job-1",
        plan=_plan(tmp_path),
        status=ExportStage.FAILED,
        created_at="2026-07-29T12:00:00+00:00",
        updated_at="2026-07-29T12:00:03+00:00",
        attempts=(attempt,),
        progress_percent=50,
        ingestion_status=IngestionStatus.PENDING,
        failure_kind=ExportFailureKind.TOOL_FAILED,
        message="ffmpeg failed",
    )
    return ExportQueueState(
        schema_version=1,
        paused=True,
        updated_at="2026-07-29T12:00:03+00:00",
        jobs=(job,),
    )


def test_queue_state_round_trip_preserves_plan_attempt_and_ingestion(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)

    restored = ExportQueueState.from_dict(state.to_dict())

    assert restored == state
    assert restored.jobs[0].plan.plan_hash == state.jobs[0].plan.plan_hash
    assert restored.jobs[0].attempts[0].trigger == AttemptTrigger.INITIAL
    assert restored.jobs[0].ingestion_status == IngestionStatus.PENDING


def test_export_job_round_trip_preserves_stalled_and_old_payload_defaults_false(
    tmp_path: Path,
) -> None:
    original = _state(tmp_path).jobs[0]
    stalled = ExportJob.from_dict({**original.to_dict(), "stalled": True})

    assert stalled.stalled is True
    assert ExportJob.from_dict(stalled.to_dict()).stalled is True

    legacy_payload = stalled.to_dict()
    legacy_payload.pop("stalled")
    assert ExportJob.from_dict(legacy_payload).stalled is False


def test_queue_store_saves_atomically_and_keeps_last_valid_backup(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "APPDATA" / "QuickRec" / "Exports" / "queue.json"
    store = ExportQueueStore(queue_path)
    first = _state(tmp_path)
    second = ExportQueueState(
        schema_version=1,
        paused=False,
        updated_at="2026-07-29T12:01:00+00:00",
        jobs=first.jobs,
    )

    assert store.save(first).ok
    assert store.save(second).ok

    backup_path = queue_path.with_name("queue.json.bak")
    assert queue_path.is_file()
    assert backup_path.is_file()
    assert ExportQueueState.from_dict(
        json.loads(queue_path.read_text(encoding="utf-8"))
    ) == second
    assert ExportQueueState.from_dict(
        json.loads(backup_path.read_text(encoding="utf-8"))
    ) == first
    assert not list(queue_path.parent.glob("*.tmp"))


def test_corrupt_main_is_archived_and_restored_from_valid_backup(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    backup_path = tmp_path / "queue.json.bak"
    state = _state(tmp_path)
    queue_path.write_text("{broken", encoding="utf-8")
    backup_path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )

    result = ExportQueueStore(queue_path).load()

    assert result.ok
    assert result.status == QueueLoadStatus.RECOVERED
    assert result.state == state
    assert result.corrupt_path is not None
    assert result.corrupt_path.read_text(encoding="utf-8") == "{broken"
    assert ExportQueueState.from_dict(
        json.loads(queue_path.read_text(encoding="utf-8"))
    ) == state


def test_corrupt_main_and_backup_are_preserved_and_not_treated_as_empty(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    backup_path = tmp_path / "queue.json.bak"
    queue_path.write_text("{broken-main", encoding="utf-8")
    backup_path.write_text("{broken-backup", encoding="utf-8")

    result = ExportQueueStore(queue_path).load()

    assert not result.ok
    assert result.status == QueueLoadStatus.CORRUPT
    assert result.state is None
    assert queue_path.read_text(encoding="utf-8") == "{broken-main"
    assert backup_path.read_text(encoding="utf-8") == "{broken-backup"
    assert not list(tmp_path.glob("*.corrupt-*"))


def test_future_schema_loads_read_only_summary_and_cannot_be_overwritten(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    future = {
        "schema_version": 99,
        "paused": False,
        "updated_at": "2099-01-01T00:00:00+00:00",
        "jobs": [
            {
                "job_id": "future-job",
                "status": "queued",
                "created_at": "2099-01-01T00:00:00+00:00",
                "updated_at": "2099-01-01T00:00:00+00:00",
                "unknown": {"must": "survive"},
            }
        ],
        "future": {"must": "survive"},
    }
    original = json.dumps(future, ensure_ascii=False)
    queue_path.write_text(original, encoding="utf-8")
    store = ExportQueueStore(queue_path)

    loaded = store.load()
    saved = store.save(_state(tmp_path))

    assert loaded.ok
    assert loaded.status == QueueLoadStatus.FUTURE_READ_ONLY
    assert loaded.read_only
    assert loaded.state is None
    assert loaded.summaries[0].job_id == "future-job"
    assert not saved.ok
    assert saved.read_only
    assert queue_path.read_text(encoding="utf-8") == original


def test_missing_queue_returns_paused_empty_state_without_writing(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"

    result = ExportQueueStore(queue_path).load()

    assert result.ok
    assert result.status == QueueLoadStatus.MISSING
    assert result.state is not None
    assert result.state.paused
    assert result.state.jobs == ()
    assert not queue_path.exists()


def test_invalid_queue_state_is_rejected_before_write(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    state = _state(tmp_path)
    invalid = ExportQueueState(
        schema_version=1,
        paused=True,
        updated_at=state.updated_at,
        jobs=(state.jobs[0], state.jobs[0]),
    )

    result = ExportQueueStore(queue_path).save(invalid)

    assert not result.ok
    assert result.stage == "validate"
    assert not queue_path.exists()


def test_corrupt_queue_can_only_be_reset_after_explicit_confirmation(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    backup_path = tmp_path / "queue.json.bak"
    queue_path.write_text("{broken-main", encoding="utf-8")
    backup_path.write_text("{broken-backup", encoding="utf-8")
    store = ExportQueueStore(queue_path)
    assert not store.load().ok

    denied = store.reset_corrupt_queue(confirmed=False)
    accepted = store.reset_corrupt_queue(confirmed=True)

    assert not denied.ok
    assert accepted.ok
    assert ExportQueueState.from_dict(
        json.loads(queue_path.read_text(encoding="utf-8"))
    ).jobs == ()
    abandoned = list(tmp_path.glob("*.abandoned-*"))
    assert len(abandoned) == 2
    assert {path.read_text(encoding="utf-8") for path in abandoned} == {
        "{broken-main",
        "{broken-backup",
    }


def test_attempt_payload_rejects_invalid_enum_and_sequence(tmp_path: Path) -> None:
    payload = _state(tmp_path).jobs[0].attempts[0].to_dict()

    with pytest.raises(ExportValidationError, match="invalid export attempt state"):
        ExportAttempt.from_dict({**payload, "status": "not-a-stage"})
    with pytest.raises(ExportValidationError, match="sequence must be positive"):
        ExportAttempt.from_dict({**payload, "sequence": 0})


def test_job_payload_rejects_invalid_shape_state_and_metrics(
    tmp_path: Path,
) -> None:
    payload = _state(tmp_path).jobs[0].to_dict()
    with pytest.raises(ExportValidationError, match="invalid export job payload"):
        ExportJob.from_dict({**payload, "plan": []})
    with pytest.raises(ExportValidationError, match="invalid export job state"):
        ExportJob.from_dict({**payload, "ingestion_status": "unknown"})
    with pytest.raises(ExportValidationError, match="duplicate export attempt"):
        ExportJob.from_dict(
            {
                **payload,
                "attempts": [payload["attempts"][0], payload["attempts"][0]],
            }
        )
    with pytest.raises(ExportValidationError, match="progress"):
        ExportJob.from_dict({**payload, "progress_percent": 101})
    with pytest.raises(ExportValidationError, match="ETA"):
        ExportJob.from_dict({**payload, "eta_seconds": -1})


def test_queue_state_payload_rejects_schema_jobs_and_duplicate_identity(
    tmp_path: Path,
) -> None:
    payload = _state(tmp_path).to_dict()
    with pytest.raises(ExportValidationError, match="unsupported"):
        ExportQueueState.from_dict({**payload, "schema_version": 2})
    with pytest.raises(ExportValidationError, match="jobs must be an array"):
        ExportQueueState.from_dict({**payload, "jobs": {}})
    with pytest.raises(ExportValidationError, match="duplicate export job"):
        ExportQueueState.from_dict(
            {**payload, "jobs": [payload["jobs"][0], payload["jobs"][0]]}
        )


def test_queue_store_loads_valid_state_and_recovers_semantic_corruption(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    store = ExportQueueStore(queue_path)
    state = _state(tmp_path)
    assert store.save(state).ok

    loaded = store.load()

    assert loaded.ok
    assert loaded.status == QueueLoadStatus.LOADED
    assert loaded.state == state

    backup = queue_path.with_name("queue.json.bak")
    backup.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    invalid = state.to_dict()
    invalid["jobs"] = {}
    queue_path.write_text(
        json.dumps(invalid, ensure_ascii=False),
        encoding="utf-8",
    )

    recovered = store.load()

    assert recovered.ok
    assert recovered.status == QueueLoadStatus.RECOVERED


def test_queue_store_reports_write_reset_and_recovery_io_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue_path = tmp_path / "queue.json"
    store = ExportQueueStore(queue_path)
    state = _state(tmp_path)

    monkeypatch.setattr(
        queue_store_module,
        "_atomic_write_json",
        lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
    )
    written = store.save(state)
    assert not written.ok
    assert written.stage == "write"

    queue_path.write_text("{broken", encoding="utf-8")
    backup = queue_path.with_name("queue.json.bak")
    backup.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        queue_store_module,
        "_archive_corrupt_file",
        lambda *_args: (_ for _ in ()).throw(OSError("archive denied")),
    )
    recovered = store.load()
    assert not recovered.ok
    assert recovered.status == QueueLoadStatus.CORRUPT

    monkeypatch.setattr(
        queue_store_module.os,
        "replace",
        lambda *_args: (_ for _ in ()).throw(OSError("replace denied")),
    )
    reset = store.reset_corrupt_queue(confirmed=True)
    assert not reset.ok
    assert reset.stage == "reset"
    assert reset.read_only


def test_queue_store_low_level_payload_and_future_summary_guards(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "queue.json"
    queue_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="root must be an object"):
        queue_store_module._read_json_object(queue_path)

    with pytest.raises(ValueError, match="schema version"):
        queue_store_module._schema_version({"schema_version": True})
    assert not queue_store_module._path_has_future_schema(queue_path)
    assert queue_store_module._future_summaries({"jobs": {}}) == ()
    summaries = queue_store_module._future_summaries(
        {
            "jobs": [
                "invalid",
                {},
                {
                    "job_id": "future",
                    "status": "queued",
                    "created_at": "created",
                    "updated_at": "updated",
                },
            ]
        }
    )
    assert [item.job_id for item in summaries] == ["future"]


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: queue_store_module._required_text({}, "name"), "required"),
        (
            lambda: queue_store_module._required_int({"value": True}, "value"),
            "integer",
        ),
        (
            lambda: queue_store_module._required_int({"value": "bad"}, "value"),
            "integer",
        ),
        (
            lambda: queue_store_module._optional_int(True, default=0),
            "integer",
        ),
        (
            lambda: queue_store_module._optional_int("bad", default=0),
            "integer",
        ),
        (lambda: queue_store_module._optional_float(True), "number"),
        (lambda: queue_store_module._optional_float("bad"), "number"),
        (lambda: queue_store_module._object([], "item"), "object"),
    ],
)
def test_queue_store_scalar_parser_guards(call, message: str) -> None:
    with pytest.raises(ExportValidationError, match=message):
        call()


def test_queue_store_scalar_parser_defaults() -> None:
    assert queue_store_module._optional_int(None, default=7) == 7
    assert queue_store_module._optional_float(None) is None
    assert queue_store_module._optional_text(None) is None
    assert queue_store_module._optional_text("  ") is None
