"""FFmpeg 子进程生命周期、进度、停滞与取消控制。"""

from __future__ import annotations

import queue
import re
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO, cast

from exporting.diagnostics import sanitize_diagnostic_text
from exporting.filter_graph import ExportFilterGraphBuilder
from exporting.models import (
    ExportFailureKind,
    ExportPlan,
    ExportStage,
)
from exporting.verifier import ExportVerificationResult, ExportVerifier
from utils.media_metadata import resolve_ffmpeg_path

ProgressCallback = Callable[["ExportProgressSnapshot"], None]
MaterialVerifier = Callable[[ExportPlan], ExportVerificationResult]
_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9_.-]+")


class RunningProcess(Protocol):
    stdin: TextIO | None
    stdout: TextIO | None
    stderr: TextIO | None
    returncode: int | None

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


ProcessFactory = Callable[[list[str], Path], RunningProcess]


@dataclass(frozen=True)
class ExportProgressSnapshot:
    stage: ExportStage
    percent: int
    out_time_us: int
    elapsed_seconds: float
    eta_seconds: float | None
    updated_at: float
    stalled: bool = False


@dataclass(frozen=True)
class ExportExecutionResult:
    ok: bool
    stage: ExportStage
    failure_kind: ExportFailureKind | None = None
    message: str = ""
    exit_code: int | None = None
    temp_output_path: Path | None = None
    progress: ExportProgressSnapshot | None = None
    stderr_tail: str = ""


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._continue_lock = threading.Lock()
        self._continue_waiting_requested = False

    def cancel(self) -> None:
        self._event.set()

    def continue_waiting(self) -> None:
        with self._continue_lock:
            self._continue_waiting_requested = True

    def consume_continue_waiting(self) -> bool:
        with self._continue_lock:
            requested = self._continue_waiting_requested
            self._continue_waiting_requested = False
            return requested

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


class ExportExecutor:
    def __init__(
        self,
        *,
        ffmpeg_resolver: Callable[[], str] = resolve_ffmpeg_path,
        graph_builder: ExportFilterGraphBuilder | None = None,
        process_factory: ProcessFactory | None = None,
        material_verifier: MaterialVerifier | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval_seconds: float = 0.05,
        stall_warning_seconds: float = 120,
        stall_timeout_seconds: float = 300,
        cancel_grace_seconds: float = 3,
    ) -> None:
        self._ffmpeg_resolver = ffmpeg_resolver
        self._graph_builder = graph_builder or ExportFilterGraphBuilder()
        self._process_factory: ProcessFactory = (
            process_factory or _start_process
        )
        self._material_verifier = (
            material_verifier or ExportVerifier().verify_materials
        )
        self._monotonic = monotonic
        self._sleep = sleep
        self._poll_interval_seconds = max(0.001, poll_interval_seconds)
        self._stall_warning_seconds = max(0.0, stall_warning_seconds)
        self._stall_timeout_seconds = max(
            self._stall_warning_seconds,
            stall_timeout_seconds,
        )
        self._cancel_grace_seconds = max(0.0, cancel_grace_seconds)

    def execute(
        self,
        plan: ExportPlan,
        *,
        attempt_id: str,
        cancel_token: CancellationToken | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ExportExecutionResult:
        token = cancel_token or CancellationToken()
        material_result = self._material_verifier(plan)
        if not material_result.ok:
            return ExportExecutionResult(
                False,
                ExportStage.FAILED,
                failure_kind=(
                    material_result.failure_kind
                    or ExportFailureKind.MATERIAL_CHANGED
                ),
                message=material_result.message,
            )
        executable = self._ffmpeg_resolver()
        if not executable or not Path(executable).is_file():
            return ExportExecutionResult(
                False,
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.TOOL_MISSING,
                message="FFmpeg executable is missing",
            )
        output_directory = Path(plan.output.directory)
        safe_attempt = _safe_token(attempt_id)
        temp_output = (
            output_directory
            / f".quickrec-export-{safe_attempt}.part.mp4"
        )
        graph_path = (
            output_directory
            / f".quickrec-export-{safe_attempt}.filter.txt"
        )
        try:
            output_directory.mkdir(parents=True, exist_ok=True)
            temp_output.unlink(missing_ok=True)
            graph = self._graph_builder.build(plan)
            graph.write_utf8(graph_path)
        except OSError as exc:
            return ExportExecutionResult(
                False,
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.DISK_ERROR,
                message=f"export workspace failed: {type(exc).__name__}",
            )
        except Exception as exc:
            return ExportExecutionResult(
                False,
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.INTERNAL_ERROR,
                message=f"filter graph failed: {type(exc).__name__}",
            )
        arguments = graph.ffmpeg_arguments(
            executable=executable,
            graph_path=graph_path,
            output_path=temp_output,
            plan=plan,
        )
        try:
            process = self._process_factory(arguments, output_directory)
        except OSError as exc:
            graph_path.unlink(missing_ok=True)
            return ExportExecutionResult(
                False,
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.TOOL_START_FAILED,
                message=f"FFmpeg start failed: {type(exc).__name__}",
            )

        progress_lines: queue.Queue[str] = queue.Queue()
        stderr_buffer = _BoundedText()
        stdout_thread = threading.Thread(
            target=_read_lines,
            args=(process.stdout, progress_lines),
            daemon=True,
            name="QuickRecExportProgress",
        )
        stderr_thread = threading.Thread(
            target=_read_stderr,
            args=(process.stderr, stderr_buffer),
            daemon=True,
            name="QuickRecExportStderr",
        )
        stdout_thread.start()
        stderr_thread.start()
        started_at = self._monotonic()
        last_progress_at = started_at
        latest_out_time_us = 0
        latest = _progress(
            ExportStage.RUNNING,
            latest_out_time_us,
            plan.timeline.duration_us,
            started_at,
            started_at,
        )
        _notify(on_progress, latest)
        stall_notified = False
        cancelled = False
        stalled = False
        try:
            while True:
                drained, parsed_out_time = _drain_progress(
                    progress_lines,
                    latest_out_time_us,
                )
                if drained:
                    latest_out_time_us = parsed_out_time
                    last_progress_at = self._monotonic()
                    latest = _progress(
                        ExportStage.RUNNING,
                        latest_out_time_us,
                        plan.timeline.duration_us,
                        started_at,
                        last_progress_at,
                    )
                    _notify(on_progress, latest)
                    stall_notified = False
                if token.is_cancelled:
                    cancelled = True
                    _request_stop(process, self._cancel_grace_seconds)
                    break
                if token.consume_continue_waiting():
                    last_progress_at = self._monotonic()
                    stall_notified = False
                    latest = _progress(
                        ExportStage.RUNNING,
                        latest_out_time_us,
                        plan.timeline.duration_us,
                        started_at,
                        last_progress_at,
                    )
                    _notify(on_progress, latest)
                now = self._monotonic()
                idle_seconds = now - last_progress_at
                if (
                    not stall_notified
                    and idle_seconds >= self._stall_warning_seconds
                ):
                    stall_notified = True
                    latest = _progress(
                        ExportStage.RUNNING,
                        latest_out_time_us,
                        plan.timeline.duration_us,
                        started_at,
                        now,
                        stalled=True,
                    )
                    _notify(on_progress, latest)
                if idle_seconds >= self._stall_timeout_seconds:
                    stalled = True
                    _request_stop(process, self._cancel_grace_seconds)
                    break
                if process.poll() is not None:
                    break
                self._sleep(self._poll_interval_seconds)
            return_code = process.wait()
        finally:
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            drained, parsed_out_time = _drain_progress(
                progress_lines,
                latest_out_time_us,
            )
            if drained:
                latest_out_time_us = parsed_out_time
            graph_path.unlink(missing_ok=True)

        sensitive_paths = (
            plan.project.project_path,
            *(material.path for material in plan.materials),
            str(temp_output),
            str(plan.output.target_path),
        )
        stderr_tail = sanitize_diagnostic_text(
            stderr_buffer.text,
            sensitive_paths=sensitive_paths,
        )
        if cancelled:
            temp_output.unlink(missing_ok=True)
            return ExportExecutionResult(
                False,
                ExportStage.CANCELLED,
                failure_kind=ExportFailureKind.CANCELLED,
                message="export cancelled",
                exit_code=return_code,
                progress=latest,
                stderr_tail=stderr_tail,
            )
        if stalled:
            temp_output.unlink(missing_ok=True)
            return ExportExecutionResult(
                False,
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.STALLED,
                message="FFmpeg progress stalled",
                exit_code=return_code,
                progress=latest,
                stderr_tail=stderr_tail,
            )
        if return_code != 0:
            temp_output.unlink(missing_ok=True)
            return ExportExecutionResult(
                False,
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.TOOL_FAILED,
                message="FFmpeg returned nonzero",
                exit_code=return_code,
                progress=latest,
                stderr_tail=stderr_tail,
            )
        try:
            if not temp_output.is_file() or temp_output.stat().st_size <= 0:
                raise OSError("candidate output is missing")
        except OSError:
            temp_output.unlink(missing_ok=True)
            return ExportExecutionResult(
                False,
                ExportStage.FAILED,
                failure_kind=ExportFailureKind.DISK_ERROR,
                message="candidate output is missing or empty",
                exit_code=return_code,
                progress=latest,
                stderr_tail=stderr_tail,
            )
        completed_at = self._monotonic()
        verifying = ExportProgressSnapshot(
            ExportStage.VERIFYING,
            96,
            min(latest_out_time_us, plan.timeline.duration_us),
            max(0.0, completed_at - started_at),
            None,
            completed_at,
        )
        _notify(on_progress, verifying)
        return ExportExecutionResult(
            True,
            ExportStage.VERIFYING,
            exit_code=return_code,
            temp_output_path=temp_output,
            progress=verifying,
            stderr_tail=stderr_tail,
        )


def _start_process(
    arguments: list[str],
    cwd: Path,
) -> RunningProcess:
    return cast(
        RunningProcess,
        subprocess.Popen(
            arguments,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ),
    )


def _read_lines(
    stream: TextIO | None,
    destination: queue.Queue[str],
) -> None:
    if stream is None:
        return
    try:
        for line in stream:
            destination.put(line.strip())
    finally:
        stream.close()


def _read_stderr(
    stream: TextIO | None,
    destination: _BoundedText,
) -> None:
    if stream is None:
        return
    try:
        for line in stream:
            destination.append(line)
    finally:
        stream.close()


def _drain_progress(
    lines: queue.Queue[str],
    current_out_time_us: int,
) -> tuple[bool, int]:
    drained = False
    out_time_us = current_out_time_us
    while True:
        try:
            line = lines.get_nowait()
        except queue.Empty:
            break
        if not line:
            continue
        drained = True
        key, separator, value = line.partition("=")
        if not separator:
            continue
        if key in {"out_time_us", "out_time_ms"}:
            try:
                out_time_us = max(out_time_us, int(value))
            except ValueError:
                continue
    return drained, out_time_us


def _progress(
    stage: ExportStage,
    out_time_us: int,
    duration_us: int,
    started_at: float,
    now: float,
    *,
    stalled: bool = False,
) -> ExportProgressSnapshot:
    ratio = (
        max(0.0, min(1.0, out_time_us / duration_us))
        if duration_us > 0
        else 0.0
    )
    percent = min(95, max(5, round(5 + ratio * 90)))
    elapsed = max(0.0, now - started_at)
    eta = elapsed * (1.0 - ratio) / ratio if ratio > 0 else None
    return ExportProgressSnapshot(
        stage,
        percent,
        max(0, out_time_us),
        elapsed,
        eta,
        now,
        stalled=stalled,
    )


def _request_stop(process: RunningProcess, grace_seconds: float) -> None:
    if process.poll() is not None:
        return
    if process.stdin is not None:
        try:
            process.stdin.write("q\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass
    try:
        process.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        process.terminate()
        process.wait(timeout=max(0.1, grace_seconds))
        return
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _safe_token(value: str) -> str:
    safe = _SAFE_TOKEN.sub("_", value).strip("._")
    return safe or "attempt"


def _notify(
    callback: ProgressCallback | None,
    snapshot: ExportProgressSnapshot,
) -> None:
    if callback is None:
        return
    try:
        callback(snapshot)
    except Exception:
        return


class _BoundedText:
    def __init__(self, limit_bytes: int = 64 * 1024) -> None:
        self._chunks: deque[str] = deque()
        self._bytes = 0
        self._limit_bytes = limit_bytes
        self._lock = threading.Lock()

    def append(self, value: str) -> None:
        encoded = value.encode("utf-8", errors="replace")
        with self._lock:
            if len(encoded) >= self._limit_bytes:
                suffix = encoded[-self._limit_bytes :]
                while (
                    suffix
                    and (suffix[0] & 0b1100_0000) == 0b1000_0000
                ):
                    suffix = suffix[1:]
                retained = suffix.decode("utf-8", errors="replace")
                self._chunks.clear()
                self._chunks.append(retained)
                self._bytes = len(
                    retained.encode("utf-8", errors="replace")
                )
                return
            self._chunks.append(value)
            self._bytes += len(encoded)
            while self._chunks and self._bytes > self._limit_bytes:
                removed = self._chunks.popleft()
                self._bytes -= len(
                    removed.encode("utf-8", errors="replace")
                )

    @property
    def text(self) -> str:
        with self._lock:
            return "".join(self._chunks)
