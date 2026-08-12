from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import main
import utils.single_instance as single_instance
from utils.single_instance import SingleInstanceGuard, WindowsInstanceKernel


class FakeWinFunction:
    def __init__(self, result=1) -> None:
        self.result = result
        self.side_effect = None
        self.calls: list[tuple[object, ...]] = []
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        self.calls.append(args)
        if self.side_effect is not None:
            return self.side_effect(*args)
        return self.result


class FakeKernel32:
    def __init__(self) -> None:
        self.last_error = 0
        self.CreateMutexW = FakeWinFunction(101)
        self.CreateEventW = FakeWinFunction(202)
        self.OpenEventW = FakeWinFunction(303)
        self.SetEvent = FakeWinFunction(1)
        self.WaitForSingleObject = FakeWinFunction(0)
        self.CloseHandle = FakeWinFunction(1)


def make_windows_kernel(monkeypatch, **kwargs):
    fake = FakeKernel32()
    monkeypatch.setattr(single_instance.ctypes, "WinDLL", lambda *args, **kw: fake)
    monkeypatch.setattr(single_instance.ctypes, "get_last_error", lambda: fake.last_error)
    monkeypatch.setattr(single_instance.ctypes, "set_last_error", lambda value: setattr(fake, "last_error", value))
    return WindowsInstanceKernel(**kwargs), fake


def test_windows_kernel_rejects_non_windows(monkeypatch) -> None:
    monkeypatch.setattr(single_instance, "os", SimpleNamespace(name="posix"))

    with pytest.raises(OSError, match="requires Windows"):
        WindowsInstanceKernel()


def test_windows_kernel_configures_signatures_and_creates_primary_mutex(monkeypatch) -> None:
    kernel, fake = make_windows_kernel(monkeypatch)

    handle, existed = kernel.create_mutex("Local\\QuickRec.Lite.Instance")

    assert handle == 101
    assert not existed
    assert fake.CreateMutexW.argtypes is not None
    assert fake.CreateMutexW.restype is not None


def test_windows_kernel_detects_existing_mutex(monkeypatch) -> None:
    kernel, fake = make_windows_kernel(monkeypatch)

    def create_mutex(*_args):
        fake.last_error = 183
        return 101

    fake.CreateMutexW.side_effect = create_mutex

    assert kernel.create_mutex("Local\\QuickRec.Lite.Instance") == (101, True)


def test_windows_kernel_raises_when_mutex_or_event_creation_fails(monkeypatch) -> None:
    kernel, fake = make_windows_kernel(monkeypatch)

    def fail(*_args):
        fake.last_error = 5
        return 0

    fake.CreateMutexW.side_effect = fail
    with pytest.raises(OSError, match="CreateMutexW failed"):
        kernel.create_mutex("mutex")

    fake.CreateEventW.side_effect = fail
    with pytest.raises(OSError, match="CreateEventW failed"):
        kernel.create_activation_event("event")


def test_windows_kernel_retries_activation_event_and_closes_handle(monkeypatch) -> None:
    kernel, fake = make_windows_kernel(monkeypatch, signal_attempts=2, signal_retry_seconds=0)
    responses = iter([0, 404])

    def open_event(*_args):
        handle = next(responses)
        fake.last_error = 2 if not handle else 0
        return handle

    fake.OpenEventW.side_effect = open_event

    assert kernel.signal_activation_event("event")
    assert len(fake.OpenEventW.calls) == 2
    assert fake.SetEvent.calls == [(404,)]
    assert fake.CloseHandle.calls == [(404,)]


def test_windows_kernel_activation_stops_on_unexpected_open_error(monkeypatch) -> None:
    kernel, fake = make_windows_kernel(monkeypatch)

    def fail_open(*_args):
        fake.last_error = 5
        return 0

    fake.OpenEventW.side_effect = fail_open

    assert not kernel.signal_activation_event("event")
    assert len(fake.OpenEventW.calls) == 1


def test_windows_kernel_consumes_wait_states(monkeypatch) -> None:
    kernel, fake = make_windows_kernel(monkeypatch)

    fake.WaitForSingleObject.result = 0
    assert kernel.consume_activation_event(202)
    fake.WaitForSingleObject.result = 0x102
    assert not kernel.consume_activation_event(202)
    fake.WaitForSingleObject.result = 123
    with pytest.raises(OSError, match="unexpected wait result"):
        kernel.consume_activation_event(202)


def test_windows_kernel_wait_failure_and_close(monkeypatch) -> None:
    kernel, fake = make_windows_kernel(monkeypatch)

    def fail_wait(*_args):
        fake.last_error = 6
        return 0xFFFFFFFF

    fake.WaitForSingleObject.side_effect = fail_wait
    with pytest.raises(OSError, match="WaitForSingleObject failed"):
        kernel.consume_activation_event(202)

    kernel.close_handle(202)
    assert fake.CloseHandle.calls[-1] == (202,)


class FakeKernel:
    def __init__(self) -> None:
        self.mutexes: set[str] = set()
        self.events: dict[str, bool] = {}
        self.closed: list[object] = []

    def create_mutex(self, name: str) -> tuple[object, bool]:
        existed = name in self.mutexes
        self.mutexes.add(name)
        return ("mutex", name, len(self.closed)), existed

    def create_activation_event(self, name: str) -> object:
        self.events[name] = False
        return ("event", name)

    def signal_activation_event(self, name: str) -> bool:
        if name not in self.events:
            return False
        self.events[name] = True
        return True

    def consume_activation_event(self, handle: object) -> bool:
        name = handle[1]
        signalled = self.events.get(name, False)
        self.events[name] = False
        return signalled

    def close_handle(self, handle: object) -> None:
        self.closed.append(handle)


def test_full_and_lite_guards_do_not_conflict() -> None:
    kernel = FakeKernel()
    full = SingleInstanceGuard("QuickRec.Full", kernel=kernel)
    lite = SingleInstanceGuard("QuickRec.Lite", kernel=kernel)

    assert full.acquire()
    assert lite.acquire()
    assert full.mutex_name != lite.mutex_name


def test_second_lite_instance_signals_primary_and_exits() -> None:
    kernel = FakeKernel()
    primary = SingleInstanceGuard("QuickRec.Lite", kernel=kernel)
    secondary = SingleInstanceGuard("QuickRec.Lite", kernel=kernel)

    assert primary.acquire()
    assert not secondary.acquire()
    assert secondary.activation_signal_sent
    assert primary.consume_activation_request()
    assert not primary.consume_activation_request()


def test_guard_rejects_invalid_product_id() -> None:
    kernel = FakeKernel()

    try:
        SingleInstanceGuard("QuickRec\\Lite", kernel=kernel)
    except ValueError as exc:
        assert "product_id" in str(exc)
    else:
        raise AssertionError("invalid product id should be rejected")


class FakeGuard:
    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired
        self.closed = False

    def acquire(self) -> bool:
        return self.acquired

    def close(self) -> None:
        self.closed = True


class FakeApplication:
    def __init__(self, instance_guard=None) -> None:
        self.instance_guard = instance_guard
        self.run_called = False

    def run(self) -> int:
        self.run_called = True
        return 7


def test_run_lite_app_exits_without_starting_second_instance() -> None:
    guard = FakeGuard(acquired=False)
    created: list[FakeApplication] = []

    result = main.run_lite_app(
        guard=guard,
        app_factory=lambda **kwargs: created.append(FakeApplication(**kwargs)),
    )

    assert result == 0
    assert created == []
    assert guard.closed


def test_run_lite_app_closes_primary_guard_after_event_loop() -> None:
    guard = FakeGuard(acquired=True)
    created: list[FakeApplication] = []

    def create_app(**kwargs):
        app = FakeApplication(**kwargs)
        created.append(app)
        return app

    result = main.run_lite_app(guard=guard, app_factory=create_app)

    assert result == 7
    assert created[0].run_called
    assert created[0].instance_guard is guard
    assert guard.closed
