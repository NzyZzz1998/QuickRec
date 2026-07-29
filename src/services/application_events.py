from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from itertools import count
from typing import TypeVar, cast

logger = logging.getLogger("QuickRec")

EventT = TypeVar("EventT")


class Subscription:
    """可幂等释放的应用事件订阅。"""

    def __init__(self, close_callback: Callable[[], None]) -> None:
        self._close_callback: Callable[[], None] | None = close_callback
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        with self._lock:
            return self._close_callback is not None

    def close(self) -> None:
        with self._lock:
            callback = self._close_callback
            self._close_callback = None
        if callback is not None:
            callback()

    def __enter__(self) -> Subscription:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class ApplicationEventHub:
    """只传播已经发生的类型化事实，不承载业务命令。"""

    def __init__(self) -> None:
        self._handlers: dict[
            type[object],
            dict[int, Callable[[object], None]],
        ] = {}
        self._tokens = count(1)
        self._lock = threading.RLock()

    def subscribe(
        self,
        event_type: type[EventT],
        handler: Callable[[EventT], None],
    ) -> Subscription:
        token = next(self._tokens)
        generic_type = cast(type[object], event_type)
        generic_handler = cast(Callable[[object], None], handler)
        with self._lock:
            self._handlers.setdefault(generic_type, {})[token] = generic_handler

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._handlers.get(generic_type)
                if handlers is None:
                    return
                handlers.pop(token, None)
                if not handlers:
                    self._handlers.pop(generic_type, None)

        return Subscription(unsubscribe)

    def publish(self, event: object) -> None:
        event_type = type(event)
        with self._lock:
            handlers = tuple(self._handlers.get(event_type, {}).values())
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "application event handler failed: event_type=%s",
                    event_type.__name__,
                )
