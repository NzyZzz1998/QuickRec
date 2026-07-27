"""项目素材预览任务的并发、去重、优先级和生命周期协调。"""

from __future__ import annotations

import hashlib
import itertools
import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Protocol

from services.thumbnail_service import (
    ThumbnailErrorCode,
    ThumbnailGenerationRequest,
    ThumbnailGenerationResult,
)
from utils.thumbnail_cache import (
    ThumbnailFingerprint,
    normalize_thumbnail_source_path,
)

logger = logging.getLogger("QuickRec")


class ThumbnailTaskPriority(IntEnum):
    SELECTED = 0
    VISIBLE = 10
    BACKGROUND = 20


class ThumbnailTaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThumbnailGenerator(Protocol):
    def generate(
        self,
        request: ThumbnailGenerationRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> ThumbnailGenerationResult: ...


@dataclass(frozen=True)
class ThumbnailTaskSnapshot:
    key: str
    request: ThumbnailGenerationRequest
    state: ThumbnailTaskState
    priority: ThumbnailTaskPriority
    attempts: int = 0
    result: ThumbnailGenerationResult | None = None


TaskCallback = Callable[[ThumbnailGenerationResult], None]
StateListener = Callable[[ThumbnailTaskSnapshot], None]


@dataclass
class _TaskRecord:
    key: str
    request: ThumbnailGenerationRequest
    priority: ThumbnailTaskPriority
    version: int = 0
    state: ThumbnailTaskState = ThumbnailTaskState.QUEUED
    attempts: int = 0
    callbacks: list[TaskCallback] = field(default_factory=list)
    cancel_event: threading.Event = field(default_factory=threading.Event)

    def snapshot(
        self,
        *,
        result: ThumbnailGenerationResult | None = None,
    ) -> ThumbnailTaskSnapshot:
        return ThumbnailTaskSnapshot(
            self.key,
            self.request,
            self.state,
            self.priority,
            self.attempts,
            result,
        )


class ThumbnailCoordinator:
    def __init__(
        self,
        service: ThumbnailGenerator,
        *,
        max_workers: int = 2,
        max_retries: int = 1,
    ) -> None:
        self._service = service
        self.max_workers = max(1, int(max_workers))
        self.max_retries = max(0, int(max_retries))
        self._queue: queue.PriorityQueue[tuple[int, int, str, int]] = (
            queue.PriorityQueue()
        )
        self._sequence = itertools.count()
        self._records: dict[str, _TaskRecord] = {}
        self._listeners: list[StateListener] = []
        self._latest: dict[str, ThumbnailTaskSnapshot] = {}
        self._lock = threading.RLock()
        self._idle = threading.Condition(self._lock)
        self._stopping = False
        self._execution_paused = False
        self._workers = [
            threading.Thread(
                target=self._worker,
                name=f"QuickRecThumbnail-{index + 1}",
                daemon=True,
            )
            for index in range(self.max_workers)
        ]
        for worker in self._workers:
            worker.start()

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._records)

    @property
    def worker_count(self) -> int:
        return sum(worker.is_alive() for worker in self._workers)

    @property
    def execution_paused(self) -> bool:
        with self._lock:
            return self._execution_paused

    def snapshot(self, key: str) -> ThumbnailTaskSnapshot | None:
        with self._lock:
            return self._latest.get(key)

    @staticmethod
    def key_for_request(request: ThumbnailGenerationRequest) -> str:
        return _request_key(request)

    def subscribe(self, listener: StateListener) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe(self, listener: StateListener) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def submit(
        self,
        request: ThumbnailGenerationRequest,
        *,
        priority: ThumbnailTaskPriority = ThumbnailTaskPriority.BACKGROUND,
        callback: TaskCallback | None = None,
    ) -> str:
        key = _request_key(request)
        with self._lock:
            if self._stopping:
                raise RuntimeError("thumbnail coordinator is shutting down")
            existing = self._records.get(key)
            if existing is not None:
                if callback is not None:
                    existing.callbacks.append(callback)
                if (
                    existing.state == ThumbnailTaskState.QUEUED
                    and priority < existing.priority
                ):
                    existing.priority = priority
                    existing.version += 1
                    self._enqueue(existing)
                    logger.info(
                        "thumbnail task reprioritized: material_id=%s priority=%s",
                        request.material_id,
                        priority.name.lower(),
                    )
                return key
            record = _TaskRecord(key, request, priority)
            if callback is not None:
                record.callbacks.append(callback)
            self._records[key] = record
            self._enqueue(record)
            snapshot = record.snapshot()
        logger.info(
            "thumbnail task submitted: material_id=%s priority=%s",
            request.material_id,
            priority.name.lower(),
        )
        self._notify(snapshot)
        return key

    def set_execution_paused(self, paused: bool, *, reason: str = "") -> None:
        with self._idle:
            changed = self._execution_paused != bool(paused)
            self._execution_paused = bool(paused)
            self._idle.notify_all()
        if changed:
            logger.info(
                "thumbnail execution %s: reason=%s active=%s",
                "paused" if paused else "resumed",
                reason or "unspecified",
                self.active_count,
            )

    def cancel(self, key: str) -> bool:
        callbacks: list[TaskCallback] = []
        snapshot: ThumbnailTaskSnapshot | None = None
        result: ThumbnailGenerationResult | None = None
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            record.cancel_event.set()
            if record.state == ThumbnailTaskState.QUEUED:
                record.state = ThumbnailTaskState.CANCELLED
                result = _cancelled_result(record.request)
                callbacks = list(record.callbacks)
                snapshot = record.snapshot(result=result)
                self._records.pop(key, None)
                self._idle.notify_all()
        if snapshot is not None and result is not None:
            logger.info(
                "thumbnail task cancelled: material_id=%s source=queue",
                result.material_id,
            )
            self._notify(snapshot)
            self._notify_callbacks(callbacks, result)
        return True

    def cancel_pending(self) -> int:
        with self._lock:
            keys = [
                key
                for key, record in self._records.items()
                if record.state == ThumbnailTaskState.QUEUED
            ]
        for key in keys:
            self.cancel(key)
        return len(keys)

    def wait_for_idle(self, timeout: float | None = None) -> bool:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._idle:
            while self._records:
                remaining = (
                    None
                    if deadline is None
                    else max(0.0, deadline - time.monotonic())
                )
                if remaining == 0:
                    return False
                self._idle.wait(remaining)
            return True

    def shutdown(
        self,
        *,
        cancel_pending: bool = True,
        wait: bool = True,
    ) -> None:
        callbacks: list[tuple[list[TaskCallback], ThumbnailGenerationResult]] = []
        snapshots: list[ThumbnailTaskSnapshot] = []
        with self._lock:
            if not self._stopping:
                self._stopping = True
                logger.info(
                    "thumbnail coordinator shutdown: active=%s",
                    len(self._records),
                )
                for key, record in tuple(self._records.items()):
                    record.cancel_event.set()
                    if cancel_pending and record.state == ThumbnailTaskState.QUEUED:
                        record.state = ThumbnailTaskState.CANCELLED
                        result = _cancelled_result(record.request)
                        callbacks.append((list(record.callbacks), result))
                        snapshots.append(record.snapshot(result=result))
                        self._records.pop(key, None)
                self._idle.notify_all()
                for _worker in self._workers:
                    self._queue.put(
                        (9999, next(self._sequence), "", -1)
                    )
        for snapshot in snapshots:
            self._notify(snapshot)
        for listeners, result in callbacks:
            self._notify_callbacks(listeners, result)
        if wait:
            for worker in self._workers:
                worker.join(timeout=15)
            self._workers = [
                worker for worker in self._workers if worker.is_alive()
            ]

    def _enqueue(self, record: _TaskRecord) -> None:
        self._queue.put(
            (
                int(record.priority),
                next(self._sequence),
                record.key,
                record.version,
            )
        )

    def _worker(self) -> None:
        while True:
            _priority, _sequence, key, version = self._queue.get()
            try:
                if not key:
                    return
                with self._idle:
                    while self._execution_paused and not self._stopping:
                        self._idle.wait()
                with self._lock:
                    record = self._records.get(key)
                    if (
                        record is None
                        or record.version != version
                        or record.state != ThumbnailTaskState.QUEUED
                    ):
                        continue
                    record.state = ThumbnailTaskState.RUNNING
                    running = record.snapshot()
                logger.info(
                    "thumbnail generation started: material_id=%s "
                    "priority=%s attempt=%s",
                    record.request.material_id,
                    record.priority.name.lower(),
                    record.attempts + 1,
                )
                self._notify(running)
                result = self._execute(record)
                with self._lock:
                    current = self._records.get(key)
                    if current is None:
                        continue
                    current.state = (
                        ThumbnailTaskState.SUCCEEDED
                        if result.ok
                        else (
                            ThumbnailTaskState.CANCELLED
                            if result.error_code == ThumbnailErrorCode.CANCELLED
                            else ThumbnailTaskState.FAILED
                        )
                    )
                    callbacks = list(current.callbacks)
                    completed = current.snapshot(result=result)
                    self._records.pop(key, None)
                    self._idle.notify_all()
                self._notify(completed)
                self._notify_callbacks(callbacks, result)
                if result.ok:
                    logger.info(
                        "thumbnail task completed: material_id=%s attempts=%s",
                        result.material_id,
                        result.attempts,
                    )
                else:
                    logger.warning(
                        "thumbnail task failed: material_id=%s code=%s "
                        "attempts=%s",
                        result.material_id,
                        (
                            result.error_code.value
                            if result.error_code is not None
                            else "unknown"
                        ),
                        result.attempts,
                    )
            finally:
                self._queue.task_done()

    def _execute(self, record: _TaskRecord) -> ThumbnailGenerationResult:
        result = _cancelled_result(record.request)
        for attempt in range(self.max_retries + 1):
            if record.cancel_event.is_set():
                return _cancelled_result(record.request)
            record.attempts = attempt + 1
            result = self._service.generate(
                record.request,
                cancel_event=record.cancel_event,
            )
            if result.ok or not result.retryable:
                return result
            logger.info(
                "thumbnail task retrying: material_id=%s code=%s next_attempt=%s",
                record.request.material_id,
                (
                    result.error_code.value
                    if result.error_code is not None
                    else "unknown"
                ),
                attempt + 2,
            )
        return result

    def diagnostic_summary(self, *, limit: int = 10) -> dict[str, object]:
        with self._lock:
            snapshots = list(self._latest.values())[-max(0, int(limit)) :]
            return {
                "paused": self._execution_paused,
                "active_count": len(self._records),
                "worker_count": self.worker_count,
                "recent": [
                    {
                        "material_id": item.request.material_id,
                        "state": item.state.value,
                        "priority": item.priority.name.lower(),
                        "attempts": item.attempts,
                        "error_code": (
                            item.result.error_code.value
                            if item.result is not None
                            and item.result.error_code is not None
                            else ""
                        ),
                    }
                    for item in snapshots
                ],
            }

    def _notify(self, snapshot: ThumbnailTaskSnapshot) -> None:
        with self._lock:
            self._latest[snapshot.key] = snapshot
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(snapshot)
            except Exception:
                continue

    @staticmethod
    def _notify_callbacks(
        callbacks: list[TaskCallback],
        result: ThumbnailGenerationResult,
    ) -> None:
        for callback in callbacks:
            try:
                callback(result)
            except Exception:
                continue


def _request_key(request: ThumbnailGenerationRequest) -> str:
    try:
        return ThumbnailFingerprint.from_file(
            request.material_id,
            request.source_path,
        ).cache_key
    except OSError:
        identity = (
            f"{request.material_id}\0"
            f"{normalize_thumbnail_source_path(Path(request.source_path))}"
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _cancelled_result(
    request: ThumbnailGenerationRequest,
) -> ThumbnailGenerationResult:
    return ThumbnailGenerationResult(
        False,
        request.material_id,
        error_code=ThumbnailErrorCode.CANCELLED,
        error="thumbnail generation cancelled",
    )
