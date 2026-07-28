from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STARTUP_LIMIT_MS = 1_500.0
SEEK_LIMIT_MS = 500.0
PAUSE_LIMIT_MS = 200.0
SYNC_LIMIT_MS = 40.0
DRIFT_LIMIT_MS = 20.0


@dataclass
class CheckResult:
    name: str
    passed: bool
    value: Any = None
    limit: Any = None
    detail: str = ""


@dataclass
class BackendReport:
    backend: str
    version: str = ""
    available: bool = False
    checks: list[CheckResult] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.available and not self.errors and all(
            check.passed for check in self.checks
        )

    def add_check(
        self,
        name: str,
        passed: bool,
        *,
        value: Any = None,
        limit: Any = None,
        detail: str = "",
    ) -> None:
        self.checks.append(
            CheckResult(
                name=name,
                passed=passed,
                value=value,
                limit=limit,
                detail=detail,
            )
        )


@dataclass(frozen=True)
class SpikeInputs:
    sample: Path
    silent: Path
    long_sample: Path
    corrupt: Path
    missing: Path
    audio_samples: tuple[Path, ...]
    libmpv_dir: Path | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _process_snapshot() -> dict[str, Any]:
    try:
        import psutil

        process = psutil.Process()
        return {
            "rss_bytes": process.memory_info().rss,
            "thread_count": process.num_threads(),
            "child_pids": sorted(child.pid for child in process.children(recursive=True)),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _frame_time_seconds(frame: Any) -> float | None:
    if frame.pts is None or frame.time_base is None:
        return None
    return float(frame.pts * frame.time_base)


def _decode_pyav_timestamps(path: Path) -> dict[str, Any]:
    import av

    first_video: float | None = None
    end_video: float | None = None
    first_audio: float | None = None
    end_audio: float | None = None
    video_frames = 0
    audio_frames = 0
    stream_summaries: list[dict[str, str]] = []

    started = time.perf_counter()
    with av.open(str(path)) as container:
        streams = list(container.streams)
        stream_summaries = [
            {
                "type": stream.type,
                "codec": stream.codec_context.name,
                "time_base": str(stream.time_base),
            }
            for stream in streams
        ]
        decode_streams: dict[str, int] = {}
        if any(stream.type == "video" for stream in streams):
            decode_streams["video"] = 0
        if any(stream.type == "audio" for stream in streams):
            decode_streams["audio"] = 0
        for frame in container.decode(**decode_streams):
            frame_time = _frame_time_seconds(frame)
            if isinstance(frame, av.VideoFrame):
                video_frames += 1
                if frame_time is not None:
                    first_video = frame_time if first_video is None else first_video
                    duration = (
                        float(frame.duration * frame.time_base)
                        if frame.duration is not None and frame.time_base is not None
                        else 0.0
                    )
                    end_video = frame_time + duration
            elif isinstance(frame, av.AudioFrame):
                audio_frames += 1
                if frame_time is not None:
                    first_audio = frame_time if first_audio is None else first_audio
                    end_audio = frame_time + (frame.samples / frame.sample_rate)

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    start_offset_ms = (
        abs(first_video - first_audio) * 1000.0
        if first_video is not None and first_audio is not None
        else None
    )
    end_offset_ms = (
        abs(end_video - end_audio) * 1000.0
        if end_video is not None and end_audio is not None
        else None
    )
    drift_ms = (
        abs(end_offset_ms - start_offset_ms)
        if start_offset_ms is not None and end_offset_ms is not None
        else None
    )
    return {
        "streams": stream_summaries,
        "video_frames": video_frames,
        "audio_frames": audio_frames,
        "first_video_seconds": first_video,
        "end_video_seconds": end_video,
        "first_audio_seconds": first_audio,
        "end_audio_seconds": end_audio,
        "start_av_offset_ms": start_offset_ms,
        "end_av_offset_ms": end_offset_ms,
        "drift_increment_ms": drift_ms,
        "decode_elapsed_ms": elapsed_ms,
    }


def _measure_pyav_startup(path: Path) -> float:
    import av

    started = time.perf_counter()
    with av.open(str(path)) as container:
        video_stream = next(
            (stream for stream in container.streams if stream.type == "video"),
            None,
        )
        if video_stream is None:
            raise RuntimeError("video stream missing")
        next(container.decode(video=0))
    return (time.perf_counter() - started) * 1000.0


def _measure_pyav_seek(path: Path, target_seconds: float) -> float:
    import av

    with av.open(str(path)) as container:
        video_stream = next(
            (stream for stream in container.streams if stream.type == "video"),
            None,
        )
        if video_stream is None:
            raise RuntimeError("video stream missing")
        started = time.perf_counter()
        container.seek(
            int(target_seconds * av.time_base),
            backward=True,
            any_frame=False,
        )
        for frame in container.decode(video=0):
            frame_time = _frame_time_seconds(frame)
            if frame_time is None or frame_time + 0.100 >= target_seconds:
                break
        else:
            raise RuntimeError("seek produced no video frame")
        return (time.perf_counter() - started) * 1000.0


def _measure_pyav_pause(path: Path) -> float:
    import av

    pause_requested = threading.Event()
    pause_acknowledged = threading.Event()
    resume_requested = threading.Event()
    worker_error: list[BaseException] = []

    def worker() -> None:
        try:
            with av.open(str(path)) as container:
                next(stream for stream in container.streams if stream.type == "video")
                for _frame in container.decode(video=0):
                    if pause_requested.is_set():
                        pause_acknowledged.set()
                        if not resume_requested.wait(timeout=2.0):
                            raise TimeoutError("pause gate was not resumed")
                        return
                    time.sleep(0.002)
        except BaseException as exc:
            worker_error.append(exc)
            pause_acknowledged.set()

    thread = threading.Thread(target=worker, name="QuickRec-PyAV-Spike")
    thread.start()
    time.sleep(0.030)
    started = time.perf_counter()
    pause_requested.set()
    if not pause_acknowledged.wait(timeout=2.0):
        resume_requested.set()
        thread.join(timeout=2.0)
        raise TimeoutError("pause was not acknowledged")
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    resume_requested.set()
    thread.join(timeout=2.0)
    if thread.is_alive():
        raise RuntimeError("pause worker did not stop")
    if worker_error:
        raise RuntimeError("pause worker failed") from worker_error[0]
    return elapsed_ms


def _decode_audio_head(path: Path, seconds: float = 1.0) -> Any:
    import av
    import numpy as np

    chunks: list[Any] = []
    sample_count = 0
    target_samples = int(48_000 * seconds)
    resampler = av.AudioResampler(format="fltp", layout="stereo", rate=48_000)
    with av.open(str(path)) as container:
        audio_stream = next(
            (stream for stream in container.streams if stream.type == "audio"),
            None,
        )
        if audio_stream is None:
            raise RuntimeError(f"audio stream missing: {path}")
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                array = converted.to_ndarray()
                if array.ndim == 1:
                    array = array.reshape(1, -1)
                chunks.append(array.astype(np.float32, copy=False))
                sample_count += array.shape[-1]
                if sample_count >= target_samples:
                    break
            if sample_count >= target_samples:
                break
    if not chunks:
        raise RuntimeError(f"no audio samples decoded: {path}")
    merged = np.concatenate(chunks, axis=-1)
    if merged.shape[0] == 1:
        merged = np.repeat(merged, 2, axis=0)
    return merged[:, :target_samples]


def _measure_pyav_four_source_mix(paths: tuple[Path, ...]) -> dict[str, Any]:
    import numpy as np

    if len(paths) != 4:
        raise ValueError("exactly four audio samples are required")
    decoded = [_decode_audio_head(path) for path in paths]
    common_samples = min(chunk.shape[-1] for chunk in decoded)
    stacked = np.stack([chunk[:, :common_samples] for chunk in decoded], axis=0)
    mixed = stacked.mean(axis=0)
    peak_before_limit = float(np.max(np.abs(mixed)))
    limited = np.clip(mixed, -1.0, 1.0)
    return {
        "source_count": len(decoded),
        "channels": int(limited.shape[0]),
        "samples": int(limited.shape[1]),
        "sample_rate": 48_000,
        "peak_before_limit": peak_before_limit,
        "peak_after_limit": float(np.max(np.abs(limited))),
        "finite": bool(np.isfinite(limited).all()),
    }


def _measure_pyaudio_output(
    paths: tuple[Path, ...],
    *,
    seconds: float = 0.250,
    gain: float = 0.20,
) -> dict[str, Any]:
    import numpy as np
    import pyaudio

    decoded = [_decode_audio_head(path, seconds=seconds) for path in paths]
    common_samples = min(chunk.shape[-1] for chunk in decoded)
    stacked = np.stack([chunk[:, :common_samples] for chunk in decoded], axis=0)
    mixed = np.clip(stacked.mean(axis=0) * gain, -1.0, 1.0)
    interleaved = mixed.T.astype(np.float32, copy=False).tobytes()

    audio = pyaudio.PyAudio()
    stream = None
    started = time.perf_counter()
    try:
        device = audio.get_default_output_device_info()
        stream = audio.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=48_000,
            output=True,
            frames_per_buffer=1024,
        )
        stream.write(interleaved)
        stream.stop_stream()
        return {
            "device_name": str(device.get("name", "")),
            "device_index": int(device.get("index", -1)),
            "frames_written": common_samples,
            "elapsed_ms": (time.perf_counter() - started) * 1000.0,
            "portaudio": pyaudio.get_portaudio_version_text(),
        }
    finally:
        if stream is not None:
            stream.close()
        audio.terminate()


def probe_pyav(inputs: SpikeInputs) -> BackendReport:
    report = BackendReport(backend="pyav")
    initial = _process_snapshot()
    baseline = initial
    try:
        import av
        import numpy as np

        report.available = True
        report.version = av.__version__
        report.resources["ffmpeg"] = av._core.library_meta
        warmup_started = time.perf_counter()
        np.dot(np.ones((64, 64)), np.ones((64, 64)))
        _measure_pyav_startup(inputs.sample)
        report.metrics["audio_warmup"] = _measure_pyaudio_output(
            inputs.audio_samples,
            seconds=0.050,
            gain=0.0,
        )
        report.metrics["import_and_warmup_ms"] = (
            time.perf_counter() - warmup_started
        ) * 1000.0
        baseline = _process_snapshot()

        startup_ms = _measure_pyav_startup(inputs.sample)
        report.metrics["startup_ms"] = startup_ms
        report.add_check(
            "startup",
            startup_ms <= STARTUP_LIMIT_MS,
            value=startup_ms,
            limit=STARTUP_LIMIT_MS,
        )

        seek_targets = (3.0, 11.0, 23.0)
        seek_times = [
            _measure_pyav_seek(inputs.sample, target) for target in seek_targets
        ]
        max_seek_ms = max(seek_times)
        report.metrics["seek_ms"] = seek_times
        report.add_check(
            "random_seek",
            max_seek_ms <= SEEK_LIMIT_MS,
            value=max_seek_ms,
            limit=SEEK_LIMIT_MS,
        )

        pause_ms = _measure_pyav_pause(inputs.sample)
        report.metrics["pause_ms"] = pause_ms
        report.add_check(
            "pause",
            pause_ms <= PAUSE_LIMIT_MS,
            value=pause_ms,
            limit=PAUSE_LIMIT_MS,
        )

        sample_timestamps = _decode_pyav_timestamps(inputs.sample)
        long_timestamps = _decode_pyav_timestamps(inputs.long_sample)
        report.metrics["sample_timestamps"] = sample_timestamps
        report.metrics["long_timestamps"] = long_timestamps

        start_offset_ms = sample_timestamps["start_av_offset_ms"]
        report.add_check(
            "av_sync",
            start_offset_ms is not None and start_offset_ms <= SYNC_LIMIT_MS,
            value=start_offset_ms,
            limit=SYNC_LIMIT_MS,
        )
        drift_ms = long_timestamps["drift_increment_ms"]
        report.add_check(
            "long_drift",
            drift_ms is not None and drift_ms <= DRIFT_LIMIT_MS,
            value=drift_ms,
            limit=DRIFT_LIMIT_MS,
        )

        silent_data = _decode_pyav_timestamps(inputs.silent)
        report.metrics["silent_sample"] = silent_data
        report.add_check(
            "silent_h264",
            silent_data["video_frames"] > 0 and silent_data["audio_frames"] == 0,
            value={
                "video_frames": silent_data["video_frames"],
                "audio_frames": silent_data["audio_frames"],
            },
        )

        path_results = {}
        for path in (inputs.sample, *inputs.audio_samples):
            path_results[str(path)] = _measure_pyav_startup(path)
        report.metrics["path_startup_ms"] = path_results
        report.add_check(
            "unicode_and_space_paths",
            all(value <= STARTUP_LIMIT_MS for value in path_results.values()),
            value=path_results,
            limit=STARTUP_LIMIT_MS,
        )

        mix = _measure_pyav_four_source_mix(inputs.audio_samples)
        report.metrics["four_source_mix"] = mix
        report.add_check(
            "four_audio_mix",
            mix["source_count"] == 4
            and mix["channels"] == 2
            and mix["finite"]
            and mix["peak_after_limit"] <= 1.0,
            value=mix,
        )

        audio_output = _measure_pyaudio_output(inputs.audio_samples)
        report.metrics["audio_output"] = audio_output
        report.add_check(
            "audio_output",
            audio_output["frames_written"] > 0,
            value=audio_output,
        )

        top_source_startup = _measure_pyav_startup(inputs.audio_samples[-1])
        report.metrics["top_video_source"] = str(inputs.audio_samples[-1])
        report.add_check(
            "fixed_top_video_selection",
            top_source_startup <= STARTUP_LIMIT_MS,
            value=top_source_startup,
            limit=STARTUP_LIMIT_MS,
            detail="The highest active track is decoded as the sole video source.",
        )

        try:
            _measure_pyav_startup(inputs.missing)
        except (FileNotFoundError, OSError):
            report.add_check("missing_media", True)
        else:
            report.add_check("missing_media", False, detail="missing file was accepted")

        try:
            _measure_pyav_startup(inputs.corrupt)
        except Exception as exc:
            report.metrics["corrupt_error"] = f"{type(exc).__name__}: {exc}"
            report.add_check("corrupt_media", True)
        else:
            report.add_check("corrupt_media", False, detail="corrupt file was accepted")

        report.add_check(
            "continuous_segments",
            _measure_pyav_startup(inputs.sample) <= STARTUP_LIMIT_MS
            and _measure_pyav_startup(inputs.audio_samples[1]) <= STARTUP_LIMIT_MS,
            detail="Both adjacent segment sources initialize within the startup gate.",
        )
    except Exception as exc:
        report.errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        time.sleep(0.050)
        after = _process_snapshot()
        report.resources["initial"] = initial
        report.resources["baseline"] = baseline
        report.resources["after"] = after
        if "thread_count" in baseline and "thread_count" in after:
            thread_delta = after["thread_count"] - baseline["thread_count"]
            child_delta = len(after["child_pids"]) - len(baseline["child_pids"])
            report.metrics["thread_delta"] = thread_delta
            report.metrics["child_process_delta"] = child_delta
            report.add_check(
                "resource_release",
                thread_delta <= 0 and child_delta <= 0,
                value={
                    "thread_delta": thread_delta,
                    "child_process_delta": child_delta,
                },
            )
    return report


def _wait_until(predicate: Any, *, timeout: float, interval: float = 0.010) -> bool:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def probe_mpv(inputs: SpikeInputs) -> BackendReport:
    report = BackendReport(backend="libmpv")
    initial = _process_snapshot()
    baseline = initial
    if inputs.libmpv_dir is None:
        report.errors.append("libmpv directory was not provided")
        return report
    os.environ["PATH"] = str(inputs.libmpv_dir) + os.pathsep + os.environ["PATH"]
    try:
        import mpv

        report.available = True
        report.version = getattr(mpv, "__version__", "unknown")
        player = mpv.MPV(
            vo="null",
            ao="null",
            ytdl=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
            loglevel="warn",
        )
        report.version = (
            f"python-mpv {getattr(mpv, '__version__', 'unknown')}; "
            f"{player.mpv_version}"
        )
        baseline = _process_snapshot()
        started = time.perf_counter()
        player.play(str(inputs.sample))
        player.wait_until_playing(timeout=5.0)
        startup_ms = (time.perf_counter() - started) * 1000.0
        report.metrics["startup_ms"] = startup_ms
        report.add_check(
            "startup",
            startup_ms <= STARTUP_LIMIT_MS,
            value=startup_ms,
            limit=STARTUP_LIMIT_MS,
        )

        seek_times = []
        for target in (3.0, 11.0, 23.0):
            started = time.perf_counter()
            player.seek(target, "absolute+exact")
            reached = _wait_until(
                lambda: player.time_pos is not None
                and abs(float(player.time_pos) - target) <= 0.300,
                timeout=2.0,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if not reached:
                raise TimeoutError(f"libmpv seek did not reach {target}")
            seek_times.append(elapsed_ms)
        max_seek_ms = max(seek_times)
        report.metrics["seek_ms"] = seek_times
        report.add_check(
            "random_seek",
            max_seek_ms <= SEEK_LIMIT_MS,
            value=max_seek_ms,
            limit=SEEK_LIMIT_MS,
        )

        started = time.perf_counter()
        player.pause = True
        if not _wait_until(lambda: bool(player.pause), timeout=1.0):
            raise TimeoutError("libmpv pause was not acknowledged")
        pause_ms = (time.perf_counter() - started) * 1000.0
        report.metrics["pause_ms"] = pause_ms
        report.add_check(
            "pause",
            pause_ms <= PAUSE_LIMIT_MS,
            value=pause_ms,
            limit=PAUSE_LIMIT_MS,
        )
        report.metrics["avsync_seconds"] = player.avsync
        avsync_ms = abs(float(player.avsync or 0.0)) * 1000.0
        report.add_check(
            "av_sync",
            avsync_ms <= SYNC_LIMIT_MS,
            value=avsync_ms,
            limit=SYNC_LIMIT_MS,
        )

        report.add_check(
            "fixed_top_video_selection",
            False,
            detail="A deterministic multi-source compositor is not provided by this probe.",
        )
        report.add_check(
            "four_audio_mix",
            False,
            detail="Four independent timeline sources require a custom graph or multi-instance sync.",
        )
        player.terminate()
    except Exception as exc:
        report.errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        time.sleep(0.100)
        after = _process_snapshot()
        report.resources["initial"] = initial
        report.resources["baseline"] = baseline
        report.resources["after"] = after
        if "thread_count" in baseline and "thread_count" in after:
            thread_delta = after["thread_count"] - baseline["thread_count"]
            child_delta = len(after["child_pids"]) - len(baseline["child_pids"])
            report.metrics["thread_delta"] = thread_delta
            report.metrics["child_process_delta"] = child_delta
            report.add_check(
                "resource_release",
                thread_delta <= 0 and child_delta <= 0,
                value={
                    "thread_delta": thread_delta,
                    "child_process_delta": child_delta,
                },
            )
    return report


def probe_qt_multimedia(inputs: SpikeInputs) -> BackendReport:
    report = BackendReport(backend="qt_multimedia")
    initial = _process_snapshot()
    baseline = initial
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    try:
        from PyQt5.QtCore import QCoreApplication, QUrl
        from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer

        report.available = True
        from PyQt5.QtCore import QT_VERSION_STR

        report.version = QT_VERSION_STR
        app = QCoreApplication.instance() or QCoreApplication([])
        player = QMediaPlayer()
        player.setMuted(True)
        baseline = _process_snapshot()
        errors: list[str] = []
        player.error.connect(lambda *_: errors.append(player.errorString()))

        player.setMedia(QMediaContent(QUrl.fromLocalFile(str(inputs.sample))))
        started = time.perf_counter()
        player.play()

        def started_playing() -> bool:
            app.processEvents()
            return (
                player.state() == QMediaPlayer.PlayingState
                and player.duration() > 0
            )

        if not _wait_until(started_playing, timeout=5.0):
            raise TimeoutError(
                "Qt Multimedia did not start: " + "; ".join(errors or ["no error"])
            )
        startup_ms = (time.perf_counter() - started) * 1000.0
        report.metrics["startup_ms"] = startup_ms
        report.add_check(
            "startup",
            startup_ms <= STARTUP_LIMIT_MS,
            value=startup_ms,
            limit=STARTUP_LIMIT_MS,
        )

        seek_times = []
        for target_ms in (3_000, 11_000, 23_000):
            started = time.perf_counter()
            player.setPosition(target_ms)

            def reached_target() -> bool:
                app.processEvents()
                return abs(player.position() - target_ms) <= 350

            if not _wait_until(reached_target, timeout=2.0):
                raise TimeoutError(f"Qt Multimedia seek did not reach {target_ms}")
            seek_times.append((time.perf_counter() - started) * 1000.0)
        max_seek_ms = max(seek_times)
        report.metrics["seek_ms"] = seek_times
        report.add_check(
            "random_seek",
            max_seek_ms <= SEEK_LIMIT_MS,
            value=max_seek_ms,
            limit=SEEK_LIMIT_MS,
        )

        started = time.perf_counter()
        player.pause()

        def paused() -> bool:
            app.processEvents()
            return player.state() == QMediaPlayer.PausedState

        if not _wait_until(paused, timeout=1.0):
            raise TimeoutError("Qt Multimedia pause was not acknowledged")
        pause_ms = (time.perf_counter() - started) * 1000.0
        report.metrics["pause_ms"] = pause_ms
        report.add_check(
            "pause",
            pause_ms <= PAUSE_LIMIT_MS,
            value=pause_ms,
            limit=PAUSE_LIMIT_MS,
        )

        report.add_check(
            "fixed_top_video_selection",
            False,
            detail="QMediaPlayer is a single-source baseline.",
        )
        report.add_check(
            "four_audio_mix",
            False,
            detail="QMediaPlayer does not expose deterministic four-source mixing.",
        )
        player.stop()
        player.deleteLater()
        app.processEvents()
    except Exception as exc:
        report.errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        time.sleep(0.100)
        after = _process_snapshot()
        report.resources["initial"] = initial
        report.resources["baseline"] = baseline
        report.resources["after"] = after
        if "thread_count" in baseline and "thread_count" in after:
            thread_delta = after["thread_count"] - baseline["thread_count"]
            child_delta = len(after["child_pids"]) - len(baseline["child_pids"])
            report.metrics["thread_delta"] = thread_delta
            report.metrics["child_process_delta"] = child_delta
            report.add_check(
                "resource_release",
                thread_delta <= 0 and child_delta <= 0,
                value={
                    "thread_delta": thread_delta,
                    "child_process_delta": child_delta,
                },
            )
    return report


def _build_inputs(args: argparse.Namespace) -> SpikeInputs:
    audio_samples = tuple(Path(value).resolve() for value in args.audio_sample)
    if len(audio_samples) != 4:
        raise ValueError("--audio-sample must be supplied exactly four times")
    return SpikeInputs(
        sample=Path(args.sample).resolve(),
        silent=Path(args.silent).resolve(),
        long_sample=Path(args.long_sample).resolve(),
        corrupt=Path(args.corrupt).resolve(),
        missing=Path(args.missing).resolve(),
        audio_samples=audio_samples,
        libmpv_dir=Path(args.libmpv_dir).resolve() if args.libmpv_dir else None,
    )


def _validate_inputs(inputs: SpikeInputs) -> dict[str, Any]:
    required = (
        inputs.sample,
        inputs.silent,
        inputs.long_sample,
        inputs.corrupt,
        *inputs.audio_samples,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing spike inputs: " + ", ".join(missing))
    if inputs.missing.exists():
        raise ValueError(f"missing-media fixture unexpectedly exists: {inputs.missing}")
    return {
        str(path): {
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in required
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="QuickRec v1.9.2 playback backend technical spike"
    )
    parser.add_argument(
        "--backend",
        choices=("all", "pyav", "mpv", "qt"),
        default="all",
    )
    parser.add_argument("--sample", required=True)
    parser.add_argument("--silent", required=True)
    parser.add_argument("--long-sample", required=True)
    parser.add_argument("--corrupt", required=True)
    parser.add_argument("--missing", required=True)
    parser.add_argument("--audio-sample", action="append", required=True)
    parser.add_argument("--libmpv-dir")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    inputs = _build_inputs(args)
    input_manifest = _validate_inputs(inputs)
    probes = {
        "pyav": probe_pyav,
        "mpv": probe_mpv,
        "qt": probe_qt_multimedia,
    }
    selected = tuple(probes) if args.backend == "all" else (args.backend,)
    started = time.perf_counter()
    reports = [probes[name](inputs) for name in selected]
    result = {
        "schema_version": 1,
        "generated_at_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "executable": sys.executable,
            "frozen": bool(getattr(sys, "frozen", False)),
            "cwd": str(Path.cwd()),
        },
        "limits_ms": {
            "startup": STARTUP_LIMIT_MS,
            "seek": SEEK_LIMIT_MS,
            "pause": PAUSE_LIMIT_MS,
            "sync": SYNC_LIMIT_MS,
            "drift": DRIFT_LIMIT_MS,
        },
        "inputs": input_manifest,
        "reports": [
            {
                **asdict(report),
                "passed": report.passed,
            }
            for report in reports
        ],
        "elapsed_ms": (time.perf_counter() - started) * 1000.0,
    }
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(report.available for report in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
