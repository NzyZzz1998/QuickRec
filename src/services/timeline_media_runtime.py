from __future__ import annotations

from typing import Protocol

from utils.project_store import ProjectFile
from utils.timeline_model import Timeline


class TimelinePlaybackRuntime(Protocol):
    def pause(self) -> object: ...

    def release(self) -> object: ...

    def replace_timeline(
        self,
        project: ProjectFile,
        timeline: Timeline,
    ) -> object: ...

    def diagnostic_summary(self) -> dict[str, object]: ...


class TimelineMediaRuntime:
    def __init__(self) -> None:
        self._current: TimelinePlaybackRuntime | None = None

    @property
    def current(self) -> TimelinePlaybackRuntime | None:
        return self._current

    def attach(self, runtime: TimelinePlaybackRuntime) -> None:
        if runtime is self._current:
            return
        self.release()
        self._current = runtime

    def pause(self) -> object | None:
        runtime = self._current
        if runtime is None:
            return None
        return runtime.pause()

    def replace_timeline(
        self,
        project: ProjectFile,
        timeline: Timeline,
    ) -> object:
        runtime = self._current
        if runtime is None:
            raise RuntimeError("timeline media runtime is not attached")
        return runtime.replace_timeline(project, timeline)

    def diagnostic_summary(self) -> dict[str, object]:
        runtime = self._current
        if runtime is None:
            return {"state": "not_initialized"}
        return dict(runtime.diagnostic_summary())

    def release(self) -> None:
        runtime = self._current
        if runtime is None:
            return
        self._current = None
        try:
            runtime.pause()
        finally:
            runtime.release()
