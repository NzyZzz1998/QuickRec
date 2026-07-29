from __future__ import annotations

import pytest

from services.recording_guard import RecordingActiveError, RecordingGuard


def test_recording_guard_is_writable_by_default() -> None:
    guard = RecordingGuard()

    assert guard.state.active is False
    assert guard.state.reason == ""
    guard.ensure_writable()


def test_recording_guard_activation_is_idempotent_and_one_release_unlocks() -> None:
    guard = RecordingGuard()

    guard.activate("recording is active")
    first_state = guard.state
    guard.activate("recording is active")

    assert guard.state == first_state
    with pytest.raises(RecordingActiveError, match="recording is active"):
        guard.ensure_writable()

    guard.release()
    guard.release()
    guard.ensure_writable()
    assert guard.state.active is False


def test_recording_guard_can_refresh_the_active_reason() -> None:
    guard = RecordingGuard()
    guard.activate("recording started")

    guard.activate("recording is active; timeline editing is disabled")

    assert guard.state.active is True
    assert (
        guard.state.reason
        == "recording is active; timeline editing is disabled"
    )
