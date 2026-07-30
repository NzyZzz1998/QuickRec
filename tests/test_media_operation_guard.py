from __future__ import annotations

from services.media_operation_guard import (
    MediaOperation,
    MediaOperationGuard,
)


def test_recording_and_export_are_mutually_exclusive() -> None:
    guard = MediaOperationGuard()

    recording = guard.try_begin_recording()
    export = guard.try_begin_export("job-1")

    assert recording.ok
    assert not export.ok
    assert guard.state.operation == MediaOperation.RECORDING

    guard.release_recording()
    export = guard.try_begin_export("job-1")
    recording = guard.try_begin_recording()

    assert export.ok
    assert not recording.ok
    assert guard.state.operation == MediaOperation.EXPORTING
    assert guard.state.owner_id == "job-1"


def test_repeated_owner_acquisition_and_release_are_idempotent() -> None:
    guard = MediaOperationGuard()

    assert guard.try_begin_export("job-1").ok
    assert guard.try_begin_export("job-1").ok
    assert not guard.release_export("other-job")
    assert guard.state.operation == MediaOperation.EXPORTING
    assert guard.release_export("job-1")
    assert guard.state.operation == MediaOperation.IDLE

    assert guard.try_begin_recording().ok
    assert guard.try_begin_recording().ok
    assert guard.release_recording()
    assert not guard.release_recording()


def test_can_begin_checks_do_not_reserve_runtime() -> None:
    guard = MediaOperationGuard()

    assert guard.can_begin_recording().ok
    assert guard.can_begin_export().ok
    assert guard.state.operation == MediaOperation.IDLE
