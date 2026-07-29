from collections.abc import Callable
from typing import Protocol

from recorder.events import RecordingEvent
from recorder.state_machine import RecordingState
from services.application_events import ApplicationEventHub, Subscription


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
    def __init__(
        self,
        manager: RecordingManagerLike,
        *,
        event_hub: ApplicationEventHub | None = None,
    ):
        self._manager = manager
        self._event_hub = event_hub or ApplicationEventHub()
        self._subscriptions: dict[EventSubscriber, Subscription] = {}

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
        if callback in self._subscriptions:
            return
        self._subscriptions[callback] = self._event_hub.subscribe(
            RecordingEvent,
            callback,
        )

    def unsubscribe(self, callback: EventSubscriber) -> None:
        subscription = self._subscriptions.pop(callback, None)
        if subscription is not None:
            subscription.close()

    def handle_event(self, event: RecordingEvent) -> None:
        self._event_hub.publish(event)
