from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import platform
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
STIMULUS_SCRIPT = PROJECT_ROOT / "scripts" / "capture_120fps_stimulus.py"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from recorder.capture_metrics import evaluate_capture_gate  # noqa: E402


class SpikeCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class ProbeValidation:
    ok: bool
    actual_fps: float
    width: int
    height: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FrameEncodeItem:
    frame: Any
    sequence_index: int


class AsyncFrameEncoder:
    """Keep capture event collection independent from conversion and pipe writes."""

    def __init__(
        self,
        *,
        stdin: Any,
        width: int,
        height: int,
        fps: int,
        capture_started: float,
        prepare_frame: Callable[[Any, int, int], Any] | None = None,
        queue_size: int = 6,
    ) -> None:
        self._stdin = stdin
        self._width = width
        self._height = height
        self._fps = fps
        self._capture_started = capture_started
        self._prepare_frame = prepare_frame or _prepare_frame
        self._queue: queue.Queue[FrameEncodeItem | None] = queue.Queue(
            maxsize=queue_size
        )
        self._thread = threading.Thread(
            target=self._run,
            name="QuickRec-120FPS-EncoderFeed",
            daemon=True,
        )
        self._exception: BaseException | None = None
        self._started = False
        self._aborting = threading.Event()
        self.encoded_frame_times: list[float] = []
        self.backlog_samples: list[tuple[float, float]] = []
        self.write_latencies_ms: list[float] = []

    def start(self) -> None:
        self._thread.start()
        self._started = True

    def submit(self, frame: Any, *, sequence_index: int) -> None:
        if not self._started:
            raise RuntimeError("encoder worker has not started")
        while not self._aborting.is_set():
            self._raise_worker_error()
            try:
                self._queue.put(
                    FrameEncodeItem(frame=frame, sequence_index=sequence_index),
                    timeout=0.05,
                )
                return
            except queue.Full:
                continue
        raise RuntimeError("encoder worker was aborted")

    def finish(self) -> None:
        if not self._started:
            return
        self._queue.put(None)
        self._thread.join()
        self._raise_worker_error()
        self._started = False

    def abort(self) -> None:
        if not self._started:
            return
        self._aborting.set()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        self._thread.join(timeout=5.0)
        self._started = False

    def _raise_worker_error(self) -> None:
        if self._exception is not None:
            raise RuntimeError("encoder feed failed") from self._exception

    def _run(self) -> None:
        try:
            while not self._aborting.is_set():
                item = self._queue.get()
                if item is None:
                    return
                prepared = self._prepare_frame(
                    item.frame,
                    self._width,
                    self._height,
                )
                write_started = time.perf_counter()
                self._stdin.write(memoryview(prepared).cast("B"))
                write_completed = time.perf_counter()
                completion_elapsed = write_completed - self._capture_started
                self.encoded_frame_times.append(completion_elapsed)
                self.write_latencies_ms.append(
                    (write_completed - write_started) * 1000.0
                )
                ideal_elapsed = item.sequence_index / self._fps
                self.backlog_samples.append(
                    (
                        completion_elapsed,
                        max(0.0, (completion_elapsed - ideal_elapsed) * 1000.0),
                    )
                )
        except BaseException as exc:
            self._exception = exc


def build_ffmpeg_command(
    *,
    ffmpeg_path: Path,
    output_path: Path,
    width: int,
    height: int,
    fps: int,
) -> list[str]:
    return [
        str(ffmpeg_path),
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-pix_fmt",
        "yuv420p",
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-crf",
        "23",
        "-preset",
        "superfast",
        "-tune",
        "zerolatency",
        "-threads",
        "1",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def build_stimulus_command(
    *,
    python_executable: Path,
    ready_path: Path,
) -> list[str]:
    return [
        str(python_executable),
        str(STIMULUS_SCRIPT),
        "--ready-file",
        str(ready_path),
    ]


def _start_stimulus(evidence_dir: Path) -> tuple[subprocess.Popen[bytes], dict[str, Any]]:
    ready_path = evidence_dir / "stimulus-ready.json"
    command = build_stimulus_command(
        python_executable=Path(sys.executable),
        ready_path=ready_path,
    )
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.perf_counter() + 5.0
    while time.perf_counter() < deadline:
        if ready_path.is_file():
            return process, {
                "enabled": True,
                "command": command,
                "ready_file": str(ready_path),
            }
        if process.poll() is not None:
            raise RuntimeError(f"stimulus exited before ready: {process.returncode}")
        time.sleep(0.05)
    process.terminate()
    process.wait(timeout=5)
    raise RuntimeError("stimulus did not become ready within 5 seconds")


def _stop_stimulus(process: subprocess.Popen[bytes] | None) -> bool:
    if process is None:
        return True
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    return process.poll() is not None


def _fraction_to_float(value: str) -> float:
    numerator, denominator = value.split("/", 1)
    denominator_value = float(denominator)
    if denominator_value == 0:
        raise ValueError("zero denominator")
    return float(numerator) / denominator_value


def validate_probe_result(
    payload: dict[str, Any],
    *,
    width: int,
    height: int,
    fps: int,
) -> ProbeValidation:
    streams = [
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type", "video") == "video"
    ]
    if not streams:
        return ProbeValidation(False, 0.0, 0, 0, ("video_stream_missing",))

    stream = streams[0]
    actual_width = int(stream.get("width") or 0)
    actual_height = int(stream.get("height") or 0)
    reasons: list[str] = []
    try:
        actual_fps = _fraction_to_float(
            str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/0")
        )
    except (TypeError, ValueError, ZeroDivisionError):
        actual_fps = 0.0
        reasons.append("invalid_frame_rate")

    if actual_width != width or actual_height != height:
        reasons.append("unexpected_resolution")
    if actual_fps and abs(actual_fps - fps) > 0.5:
        reasons.append("unexpected_frame_rate")
    return ProbeValidation(
        ok=not reasons,
        actual_fps=round(actual_fps, 3),
        width=actual_width,
        height=actual_height,
        reasons=tuple(reasons),
    )


def cleanup_temporary_video(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return False
    return not path.exists()


def _find_project_binary(name: str) -> Path | None:
    path = PROJECT_ROOT / "ffmpeg" / f"{name}.exe"
    return path if path.is_file() else None


def _binary_version(path: Path | None) -> str:
    if path is None:
        return ""
    result = subprocess.run(
        [str(path), "-version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    return result.stdout.splitlines()[0] if result.stdout else ""


def _display_environment() -> dict[str, Any]:
    if os.name != "nt":
        return {"monitor_count": 0, "width": 0, "height": 0, "refresh_hz": 0}

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    try:
        user32.SetProcessDPIAware()
    except OSError:
        pass
    monitor_count = int(user32.GetSystemMetrics(80))
    width = int(user32.GetSystemMetrics(0))
    height = int(user32.GetSystemMetrics(1))
    hdc = user32.GetDC(0)
    try:
        refresh_hz = int(gdi32.GetDeviceCaps(hdc, 116)) if hdc else 0
    finally:
        if hdc:
            user32.ReleaseDC(0, hdc)
    return {
        "monitor_count": monitor_count,
        "width": width,
        "height": height,
        "refresh_hz": refresh_hz,
    }


def _probe_video(ffprobe_path: Path, video_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    command = [
        str(ffprobe_path),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_type,width,height,avg_frame_rate,r_frame_rate,nb_frames,duration",
        "-show_entries",
        "format=duration,size",
        "-of",
        "json",
        str(video_path),
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    metadata = {
        "command": command,
        "returncode": result.returncode,
        "stderr": result.stderr.strip(),
    }
    if result.returncode != 0:
        return {}, metadata
    try:
        return json.loads(result.stdout), metadata
    except json.JSONDecodeError as exc:
        metadata["json_error"] = str(exc)
        return {}, metadata


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _close_process(process: subprocess.Popen[bytes] | None, timeout: float = 30.0) -> int | None:
    if process is None:
        return None
    if process.stdin and not process.stdin.closed:
        try:
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        return process.returncode


def _prepare_frame(frame: Any, width: int, height: int) -> Any:
    import cv2
    import numpy as np

    if frame.shape[1] != width or frame.shape[0] != height:
        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2YUV_I420)
    return np.ascontiguousarray(frame)


def _next_capture_frame(
    camera: Any,
    *,
    copy: bool = False,
) -> tuple[Any, float] | None:
    sample = camera.get_latest_frame(copy=copy, with_timestamp=True)
    if sample is None:
        return None
    frame, timestamp = sample
    return frame, float(timestamp)


def _is_source_update(previous_timestamp: float | None, timestamp: float) -> bool:
    return previous_timestamp is None or timestamp != previous_timestamp


def partition_cpu_affinity(available_cores: list[int]) -> tuple[list[int], list[int]]:
    cores = sorted(set(available_cores))
    if not cores:
        raise ValueError("at least one CPU core is required")
    if len(cores) == 1:
        return cores, cores
    capture_count = min(8, max(1, len(cores) // 2))
    return cores[:capture_count], cores[capture_count:]


def capture_sampling_fps(output_fps: int) -> int:
    return output_fps * 2 if output_fps == 120 else output_fps


def capture_video_mode(output_fps: int) -> bool:
    return output_fps != 120


def delivery_schedule(
    *,
    sample_elapsed: float,
    next_delivery_elapsed: float,
    delivery_interval: float,
) -> tuple[int, float]:
    if sample_elapsed < next_delivery_elapsed:
        return 0, next_delivery_elapsed
    due = math.floor(
        (sample_elapsed - next_delivery_elapsed) / delivery_interval
    ) + 1
    return due, next_delivery_elapsed + due * delivery_interval


def run_single_spike(
    *,
    run_index: int,
    evidence_dir: Path,
    ffmpeg_path: Path,
    ffprobe_path: Path,
    duration: float,
    width: int,
    height: int,
    fps: int,
    keep_video: bool,
    cancel_after: float,
) -> dict[str, Any]:
    import cv2
    import dxcam
    import psutil

    run_dir = evidence_dir / f"run-{run_index:02d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    video_path = run_dir / f"技术门禁 run {run_index:02d}.mp4"
    stderr_path = run_dir / "ffmpeg.stderr.log"
    result_path = run_dir / "run-result.json"
    ffprobe_path_json = run_dir / "ffprobe.json"

    command = build_ffmpeg_command(
        ffmpeg_path=ffmpeg_path,
        output_path=video_path,
        width=width,
        height=height,
        fps=fps,
    )
    run_result: dict[str, Any] = {
        "run_index": run_index,
        "status": "failed",
        "passed": False,
        "video_path": str(video_path),
        "ffmpeg_command": command,
        "capture_backend": "dxcam",
        "encoder": "libx264",
        "preset": "superfast",
        "target": {"width": width, "height": height, "fps": fps, "duration": duration},
    }
    camera = None
    process: subprocess.Popen[bytes] | None = None
    encoder_worker: AsyncFrameEncoder | None = None
    stderr_file = None
    capture_started = 0.0
    capture_elapsed = 0.0
    encoded_frame_times: list[float] = []
    source_update_times: list[float] = []
    backlog_samples: list[tuple[float, float]] = []
    write_latencies_ms: list[float] = []
    captured_frames = 0
    capture_events = 0
    last_source_timestamp: float | None = None
    ffmpeg_returncode: int | None = None
    probe_payload: dict[str, Any] = {}
    probe_meta: dict[str, Any] = {}
    probe_validation = ProbeValidation(False, 0.0, 0, 0, ("not_probed",))
    cleanup_ok = False
    runtime_process = psutil.Process()
    original_priority = runtime_process.nice()
    original_affinity = runtime_process.cpu_affinity()
    original_cv2_threads = cv2.getNumThreads()
    capture_cores, encoder_cores = partition_cpu_affinity(original_affinity)

    try:
        runtime_process.nice(psutil.HIGH_PRIORITY_CLASS)
        runtime_process.cpu_affinity(capture_cores)
        cv2.setNumThreads(len(capture_cores))
        run_result["scheduling"] = {
            "process_priority": "high",
            "capture_cores": capture_cores,
            "encoder_cores": encoder_cores,
            "opencv_threads": len(capture_cores),
        }
        camera = dxcam.create(
            output_idx=0,
            output_color="BGRA",
            max_buffer_len=8,
            processor_backend="cv2",
        )
        run_result["dxcam_device"] = dxcam.device_info().strip()
        run_result["dxcam_output"] = dxcam.output_info().strip()
        sampling_fps = capture_sampling_fps(fps)
        video_mode = capture_video_mode(fps)
        camera.start(target_fps=sampling_fps, video_mode=video_mode)
        run_result["capture_sampling_fps"] = sampling_fps
        run_result["capture_video_mode"] = video_mode

        warmup_deadline = time.perf_counter() + 2.0
        first_frame = None
        while time.perf_counter() < warmup_deadline:
            first_frame = _next_capture_frame(camera)
            if first_frame is not None:
                break
            time.sleep(0.001)
        if first_frame is None:
            raise RuntimeError("dxcam warmup did not produce a frame")
        last_source_timestamp = first_frame[1]

        stderr_file = stderr_path.open("wb")
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
        )
        psutil.Process(process.pid).cpu_affinity(encoder_cores)
        if process.stdin is None:
            raise RuntimeError("ffmpeg stdin is unavailable")

        psutil.cpu_percent(interval=None)
        capture_started = time.perf_counter()
        encoder_worker = AsyncFrameEncoder(
            stdin=process.stdin,
            width=width,
            height=height,
            fps=fps,
            capture_started=capture_started,
        )
        encoder_worker.start()
        delivery_interval = 1.0 / fps
        next_delivery_elapsed = 0.0
        while True:
            now = time.perf_counter()
            elapsed = now - capture_started
            if cancel_after > 0 and elapsed >= cancel_after:
                raise SpikeCancelled(f"cancelled after {cancel_after:.2f}s")
            if elapsed >= duration:
                break

            sample = _next_capture_frame(camera)
            if sample is None:
                time.sleep(0.0005)
                continue
            frame, source_timestamp = sample
            sample_elapsed = time.perf_counter() - capture_started
            if sample_elapsed >= duration:
                break
            capture_events += 1
            if _is_source_update(last_source_timestamp, source_timestamp):
                source_update_times.append(sample_elapsed)
            last_source_timestamp = source_timestamp
            due_deliveries, next_delivery_elapsed = delivery_schedule(
                sample_elapsed=sample_elapsed,
                next_delivery_elapsed=next_delivery_elapsed,
                delivery_interval=delivery_interval,
            )
            if due_deliveries == 0:
                continue
            owned_frame = frame.copy()
            for _ in range(due_deliveries):
                captured_frames += 1
                encoder_worker.submit(
                    owned_frame,
                    sequence_index=captured_frames,
                )

        capture_elapsed = time.perf_counter() - capture_started
        encoder_worker.finish()
        encoded_frame_times = encoder_worker.encoded_frame_times
        backlog_samples = encoder_worker.backlog_samples
        write_latencies_ms = encoder_worker.write_latencies_ms
        encoder_worker = None
        ffmpeg_returncode = _close_process(process)
        process = None
        if stderr_file:
            stderr_file.close()
            stderr_file = None

        probe_payload, probe_meta = _probe_video(ffprobe_path, video_path)
        _write_json(ffprobe_path_json, {"metadata": probe_meta, "payload": probe_payload})
        probe_validation = validate_probe_result(
            probe_payload,
            width=width,
            height=height,
            fps=fps,
        )
        delivery_gate = evaluate_capture_gate(
            frame_times=encoded_frame_times,
            backlog_samples=backlog_samples,
            duration_seconds=capture_elapsed,
        )
        effective_capture_gate = evaluate_capture_gate(
            frame_times=source_update_times,
            backlog_samples=[],
            duration_seconds=capture_elapsed,
        )

        failure_reasons = list(effective_capture_gate.reasons)
        failure_reasons.extend(
            f"delivery_{reason}" for reason in delivery_gate.reasons
        )
        if ffmpeg_returncode != 0:
            failure_reasons.append("ffmpeg_nonzero_exit")
        if not probe_validation.ok:
            failure_reasons.extend(probe_validation.reasons)

        run_result.update(
            {
                "status": "passed" if not failure_reasons else "failed",
                "passed": not failure_reasons,
                "capture_elapsed_seconds": round(capture_elapsed, 3),
                "capture_events": capture_events,
                "captured_frames": captured_frames,
                "encoded_frames": len(encoded_frame_times),
                "source_updates": len(source_update_times),
                "source_update_fps": round(
                    len(source_update_times) / capture_elapsed,
                    3,
                )
                if capture_elapsed
                else 0.0,
                "effective_capture_gate": asdict(effective_capture_gate),
                "delivery_gate": asdict(delivery_gate),
                "ffmpeg_returncode": ffmpeg_returncode,
                "ffprobe": asdict(probe_validation),
                "ffprobe_evidence": str(ffprobe_path_json),
                "write_latency_ms": {
                    "average": round(sum(write_latencies_ms) / len(write_latencies_ms), 3)
                    if write_latencies_ms
                    else 0.0,
                    "maximum": round(max(write_latencies_ms), 3)
                    if write_latencies_ms
                    else 0.0,
                },
                "cpu_percent": psutil.cpu_percent(interval=None),
                "failure_reasons": failure_reasons,
            }
        )
    except SpikeCancelled as exc:
        run_result.update(
            {
                "status": "cancelled",
                "error": str(exc),
                "captured_frames": captured_frames,
                "encoded_frames": len(encoded_frame_times),
            }
        )
    except Exception as exc:
        run_result.update(
            {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "captured_frames": captured_frames,
                "encoded_frames": len(encoded_frame_times),
            }
        )
    finally:
        if encoder_worker is not None:
            encoder_worker.abort()
        if camera is not None:
            try:
                camera.stop()
            except Exception:
                pass
            try:
                camera.release()
            except Exception:
                pass
        if process is not None:
            ffmpeg_returncode = _close_process(process, timeout=5.0)
            run_result.setdefault("ffmpeg_returncode", ffmpeg_returncode)
        if stderr_file is not None:
            stderr_file.close()
        try:
            cv2.setNumThreads(original_cv2_threads)
            runtime_process.cpu_affinity(original_affinity)
            runtime_process.nice(original_priority)
        except (OSError, psutil.Error):
            run_result.setdefault("failure_reasons", []).append(
                "capture_scheduling_restore_failed"
            )
            run_result["passed"] = False
            run_result["status"] = "failed"
        if keep_video:
            cleanup_ok = True
        else:
            cleanup_ok = cleanup_temporary_video(video_path)
        run_result["cleanup_ok"] = cleanup_ok
        run_result["video_retained"] = keep_video and video_path.exists()
        if not cleanup_ok:
            run_result["passed"] = False
            run_result["status"] = "failed"
            run_result.setdefault("failure_reasons", []).append("temporary_video_cleanup_failed")
        _write_json(result_path, run_result)
    return run_result


def _preflight(
    *,
    output_dir: Path,
    ffmpeg_path: Path | None,
    ffprobe_path: Path | None,
    width: int,
    height: int,
) -> tuple[dict[str, Any], list[str]]:
    display = _display_environment()
    reasons: list[str] = []
    if display["monitor_count"] != 1:
        reasons.append("active_monitor_count_is_not_one")
    if display["refresh_hz"] < 119:
        reasons.append("display_refresh_below_119hz")
    if display["width"] < width or display["height"] < height:
        reasons.append("display_resolution_below_target")
    if ffmpeg_path is None:
        reasons.append("project_ffmpeg_missing")
    if ffprobe_path is None:
        reasons.append("project_ffprobe_missing")

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_probe = output_dir / ".quickrec-write-test"
        write_probe.write_bytes(b"ok")
        write_probe.unlink()
    except OSError:
        reasons.append("output_directory_not_writable")
    return display, reasons


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QuickRec v1.8 real 1080p120 capture gate.")
    parser.add_argument("--output-dir", required=True, help="Evidence root directory.")
    parser.add_argument("--duration", type=float, default=5.0, help="Capture duration per run.")
    parser.add_argument("--runs", type=int, default=3, help="Number of real capture runs.")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=120)
    parser.add_argument("--keep-video", action="store_true", help="Retain temporary MP4 files.")
    parser.add_argument(
        "--with-stimulus",
        action="store_true",
        help="Show a controlled dynamic desktop stimulus during the engineering gate.",
    )
    parser.add_argument(
        "--cancel-after",
        type=float,
        default=0.0,
        help="Controlled cancellation delay for cleanup verification.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.duration <= 0 or args.runs <= 0:
        print("duration and runs must be positive", file=sys.stderr)
        return 2
    if args.width <= 0 or args.height <= 0 or args.width % 2 or args.height % 2:
        print("width and height must be positive even values", file=sys.stderr)
        return 2

    ffmpeg_path = _find_project_binary("ffmpeg")
    ffprobe_path = _find_project_binary("ffprobe")
    evidence_root = Path(args.output_dir).expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence_dir = evidence_root / f"evidence-{timestamp}"
    evidence_dir.mkdir(parents=True, exist_ok=False)

    display, preflight_reasons = _preflight(
        output_dir=evidence_dir,
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        width=args.width,
        height=args.height,
    )
    stimulus_process: subprocess.Popen[bytes] | None = None
    stimulus_meta: dict[str, Any] = {"enabled": False}
    if args.with_stimulus and not preflight_reasons:
        try:
            stimulus_process, stimulus_meta = _start_stimulus(evidence_dir)
        except Exception as exc:
            preflight_reasons.append(f"stimulus_start_failed:{type(exc).__name__}")
            stimulus_meta = {
                "enabled": True,
                "error": f"{type(exc).__name__}: {exc}",
            }
    environment: dict[str, Any] = {
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "branch_head": _git_identity(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": os.getenv("PROCESSOR_IDENTIFIER", ""),
        "display": display,
        "target": {
            "width": args.width,
            "height": args.height,
            "fps": args.fps,
            "duration": args.duration,
            "runs": args.runs,
        },
        "ffmpeg_path": str(ffmpeg_path) if ffmpeg_path else "",
        "ffmpeg_version": _binary_version(ffmpeg_path),
        "ffprobe_path": str(ffprobe_path) if ffprobe_path else "",
        "ffprobe_version": _binary_version(ffprobe_path),
        "stimulus": stimulus_meta,
        "preflight_reasons": preflight_reasons,
    }
    _write_json(evidence_dir / "environment.json", environment)

    if preflight_reasons:
        _stop_stimulus(stimulus_process)
        summary = {
            "status": "preflight_failed",
            "passed": False,
            "environment": environment,
            "runs": [],
        }
        _write_json(evidence_dir / "summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    assert ffmpeg_path is not None
    assert ffprobe_path is not None
    run_results: list[dict[str, Any]] = []
    stimulus_stopped = False
    try:
        for run_index in range(1, args.runs + 1):
            print(f"run {run_index}/{args.runs}: capture {args.width}x{args.height}@{args.fps}")
            run_results.append(
                run_single_spike(
                    run_index=run_index,
                    evidence_dir=evidence_dir,
                    ffmpeg_path=ffmpeg_path,
                    ffprobe_path=ffprobe_path,
                    duration=args.duration,
                    width=args.width,
                    height=args.height,
                    fps=args.fps,
                    keep_video=args.keep_video,
                    cancel_after=args.cancel_after,
                )
            )
            if run_results[-1]["status"] == "cancelled":
                break
    finally:
        stimulus_stopped = _stop_stimulus(stimulus_process)

    overall_passed = len(run_results) == args.runs and all(
        result.get("passed") for result in run_results
    ) and stimulus_stopped
    status = "passed" if overall_passed else "failed"
    if any(result.get("status") == "cancelled" for result in run_results):
        status = "cancelled"
    summary = {
        "status": status,
        "passed": overall_passed,
        "environment": environment,
        "runs": run_results,
        "stimulus_stopped": stimulus_stopped,
        "evidence_dir": str(evidence_dir),
    }
    _write_json(evidence_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if status == "cancelled":
        return 130
    return 0 if overall_passed else 2


def _git_identity() -> dict[str, str]:
    def run_git(*arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return result.stdout.strip()

    return {
        "branch": run_git("branch", "--show-current"),
        "head": run_git("rev-parse", "HEAD"),
        "status": run_git("status", "--short", "--branch"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
