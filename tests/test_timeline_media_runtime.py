from __future__ import annotations

import pytest

from services.timeline_media_runtime import TimelineMediaRuntime


class FakePlaybackRuntime:
    def __init__(self, *, pause_error: Exception | None = None) -> None:
        self.pause_count = 0
        self.release_count = 0
        self.replacements: list[tuple[object, object]] = []
        self.pause_error = pause_error

    def pause(self) -> object:
        self.pause_count += 1
        if self.pause_error is not None:
            raise self.pause_error
        return object()

    def release(self) -> object:
        self.release_count += 1
        return object()

    def replace_timeline(self, project: object, timeline: object) -> object:
        self.replacements.append((project, timeline))
        return "replaced"

    def diagnostic_summary(self) -> dict[str, object]:
        return {"state": "paused", "clips": 2}


def test_attach_releases_previous_runtime_but_not_same_runtime() -> None:
    owner = TimelineMediaRuntime()
    first = FakePlaybackRuntime()
    second = FakePlaybackRuntime()

    owner.attach(first)
    owner.attach(first)
    assert first.release_count == 0

    owner.attach(second)
    assert first.pause_count == 1
    assert first.release_count == 1
    assert owner.current is second


def test_release_is_idempotent_and_clears_current_before_cleanup() -> None:
    owner = TimelineMediaRuntime()
    runtime = FakePlaybackRuntime()
    owner.attach(runtime)

    owner.release()
    owner.release()

    assert owner.current is None
    assert runtime.pause_count == 1
    assert runtime.release_count == 1


def test_release_attempts_resource_cleanup_when_pause_fails() -> None:
    owner = TimelineMediaRuntime()
    runtime = FakePlaybackRuntime(pause_error=RuntimeError("pause failed"))
    owner.attach(runtime)

    with pytest.raises(RuntimeError, match="pause failed"):
        owner.release()

    assert owner.current is None
    assert runtime.release_count == 1


def test_replace_and_diagnostics_delegate_to_current_runtime() -> None:
    owner = TimelineMediaRuntime()
    runtime = FakePlaybackRuntime()
    project = object()
    timeline = object()
    owner.attach(runtime)

    assert owner.replace_timeline(project, timeline) == "replaced"
    assert owner.diagnostic_summary() == {"state": "paused", "clips": 2}
    assert runtime.replacements == [(project, timeline)]


def test_empty_runtime_has_stable_diagnostic_and_replace_contract() -> None:
    owner = TimelineMediaRuntime()

    assert owner.diagnostic_summary() == {"state": "not_initialized"}
    with pytest.raises(RuntimeError, match="not attached"):
        owner.replace_timeline(object(), object())
