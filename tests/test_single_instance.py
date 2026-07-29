from __future__ import annotations

from dataclasses import dataclass

import pytest

from services.single_instance import (
    FULL_PRODUCT_ID,
    LITE_PRODUCT_ID,
    SingleInstanceGuard,
)


@dataclass(frozen=True)
class _Handle:
    kind: str
    name: str
    sequence: int


class FakeInstanceKernel:
    def __init__(self) -> None:
        self._next_sequence = 1
        self._mutex_references: dict[str, int] = {}
        self._event_references: dict[str, int] = {}
        self._activation_counts: dict[str, int] = {}
        self.closed_handles: list[_Handle] = []
        self.fail_event_creation = False

    def create_mutex(self, name: str) -> tuple[_Handle, bool]:
        existed = self._mutex_references.get(name, 0) > 0
        self._mutex_references[name] = self._mutex_references.get(name, 0) + 1
        return self._new_handle("mutex", name), existed

    def create_activation_event(self, name: str) -> _Handle:
        if self.fail_event_creation:
            raise OSError("event creation failed")
        self._event_references[name] = self._event_references.get(name, 0) + 1
        self._activation_counts.setdefault(name, 0)
        return self._new_handle("event", name)

    def signal_activation_event(self, name: str) -> bool:
        if self._event_references.get(name, 0) == 0:
            return False
        self._activation_counts[name] = self._activation_counts.get(name, 0) + 1
        return True

    def consume_activation_event(self, handle: _Handle) -> bool:
        count = self._activation_counts.get(handle.name, 0)
        if count == 0:
            return False
        self._activation_counts[handle.name] = count - 1
        return True

    def close_handle(self, handle: _Handle) -> None:
        self.closed_handles.append(handle)
        references = (
            self._mutex_references
            if handle.kind == "mutex"
            else self._event_references
        )
        remaining = references.get(handle.name, 0) - 1
        if remaining > 0:
            references[handle.name] = remaining
        else:
            references.pop(handle.name, None)

    def mutex_is_owned(self, name: str) -> bool:
        return self._mutex_references.get(name, 0) > 0

    def _new_handle(self, kind: str, name: str) -> _Handle:
        handle = _Handle(kind, name, self._next_sequence)
        self._next_sequence += 1
        return handle


def test_primary_instance_owns_product_scoped_mutex_and_activation_event() -> None:
    kernel = FakeInstanceKernel()
    guard = SingleInstanceGuard(FULL_PRODUCT_ID, kernel=kernel)

    assert guard.acquire() is True
    assert guard.is_primary is True
    assert guard.mutex_name == r"Local\QuickRec.Full.Instance"
    assert guard.activation_event_name == r"Local\QuickRec.Full.Activate"
    assert guard.consume_activation_request() is False

    guard.close()
    assert kernel.mutex_is_owned(guard.mutex_name) is False


def test_secondary_instance_signals_primary_without_owning_instance() -> None:
    kernel = FakeInstanceKernel()
    primary = SingleInstanceGuard(FULL_PRODUCT_ID, kernel=kernel)
    secondary = SingleInstanceGuard(FULL_PRODUCT_ID, kernel=kernel)

    assert primary.acquire() is True
    assert secondary.acquire() is False
    assert secondary.is_primary is False
    assert secondary.activation_signal_sent is True
    assert primary.consume_activation_request() is True
    assert primary.consume_activation_request() is False

    secondary.close()
    assert kernel.mutex_is_owned(primary.mutex_name) is True
    primary.close()


def test_full_and_lite_instances_use_distinct_product_identities() -> None:
    kernel = FakeInstanceKernel()
    full = SingleInstanceGuard(FULL_PRODUCT_ID, kernel=kernel)
    lite = SingleInstanceGuard(LITE_PRODUCT_ID, kernel=kernel)

    assert full.acquire() is True
    assert lite.acquire() is True
    assert full.mutex_name != lite.mutex_name
    assert full.activation_event_name != lite.activation_event_name

    full.close()
    lite.close()


def test_close_is_idempotent_and_allows_a_later_primary() -> None:
    kernel = FakeInstanceKernel()
    first = SingleInstanceGuard(FULL_PRODUCT_ID, kernel=kernel)
    assert first.acquire() is True

    first.close()
    first.close()

    later = SingleInstanceGuard(FULL_PRODUCT_ID, kernel=kernel)
    assert later.acquire() is True
    later.close()


def test_event_creation_failure_releases_mutex() -> None:
    kernel = FakeInstanceKernel()
    kernel.fail_event_creation = True
    guard = SingleInstanceGuard(FULL_PRODUCT_ID, kernel=kernel)

    with pytest.raises(OSError, match="event creation failed"):
        guard.acquire()

    assert kernel.mutex_is_owned(guard.mutex_name) is False
    assert guard.is_primary is False
