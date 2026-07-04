from collections.abc import Callable
from typing import Protocol

from recorder.events import RecordingEvent
from recorder.state_machine import RecordingState


class RecordingManagerLike(Protocol):
    def start_fullscreen(self) -> bool: ...

    def start_region(self, region: tuple[int, int, int, int]) -> bool: ...

    def start_window(self, hwnd: int) -> bool: ...

    def pause(self) -> bool: ...

    def resume(self) -> bool: ...

    def stop(self, cancel: bool = False) -> str: ...

    def get_state(self) -> RecordingState: ...

    def wait_until_idle(self, timeout: float = 60.0) -> bool: ...


EventSubscriber = Callable[[RecordingEvent], None]


class RecordingWorkflow:
    def __init__(self, manager: RecordingManagerLike):
        self._manager = manager
        self._subscribers: list[EventSubscriber] = []

    def start_fullscreen(self) -> bool:
        return self._manager.start_fullscreen()

    def start_region(self, region: tuple[int, int, int, int]) -> bool:
        return self._manager.start_region(region)

    def start_window(self, hwnd: int) -> bool:
        return self._manager.start_window(hwnd)

    def pause(self) -> bool:
        return self._manager.pause()

    def resume(self) -> bool:
        return self._manager.resume()

    def stop(self, cancel: bool = False) -> str:
        return self._manager.stop(cancel=cancel)

    def get_state(self) -> RecordingState:
        return self._manager.get_state()

    def wait_until_idle(self, timeout: float = 60.0) -> bool:
        return self._manager.wait_until_idle(timeout=timeout)

    def subscribe(self, callback: EventSubscriber) -> None:
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: EventSubscriber) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def handle_event(self, event: RecordingEvent) -> None:
        for callback in list(self._subscribers):
            callback(event)
