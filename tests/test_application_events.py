from __future__ import annotations

from dataclasses import dataclass

from services.application_events import ApplicationEventHub


@dataclass(frozen=True)
class _Saved:
    recording_id: str


@dataclass(frozen=True)
class _Other:
    value: str


def test_publish_delivers_only_matching_typed_event() -> None:
    hub = ApplicationEventHub()
    saved: list[_Saved] = []
    other: list[_Other] = []
    hub.subscribe(_Saved, saved.append)
    hub.subscribe(_Other, other.append)

    event = _Saved("recording-1")
    hub.publish(event)

    assert saved == [event]
    assert other == []


def test_subscription_close_is_idempotent_and_stops_delivery() -> None:
    hub = ApplicationEventHub()
    received: list[_Saved] = []
    subscription = hub.subscribe(_Saved, received.append)
    subscription.close()
    subscription.close()

    hub.publish(_Saved("recording-1"))

    assert received == []
    assert not subscription.active


def test_handler_failure_does_not_block_later_handlers(caplog) -> None:
    hub = ApplicationEventHub()
    received: list[_Saved] = []

    def fail(_event: _Saved) -> None:
        raise RuntimeError("boom")

    hub.subscribe(_Saved, fail)
    hub.subscribe(_Saved, received.append)
    event = _Saved("recording-1")

    hub.publish(event)

    assert received == [event]
    assert "event_type=_Saved" in caplog.text
    assert "recording-1" not in caplog.text


def test_unsubscribe_during_publish_uses_stable_handler_snapshot() -> None:
    hub = ApplicationEventHub()
    received: list[str] = []
    later = hub.subscribe(
        _Saved,
        lambda _event: received.append("later"),
    )

    def close_later(_event: _Saved) -> None:
        received.append("first")
        later.close()

    first = hub.subscribe(_Saved, close_later)

    hub.publish(_Saved("recording-1"))
    hub.publish(_Saved("recording-2"))

    assert received == ["later", "first", "first"]
    first.close()
