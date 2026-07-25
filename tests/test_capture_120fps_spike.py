from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = PROJECT_ROOT / "src" / "recorder" / "capture_metrics.py"
SPIKE_PATH = PROJECT_ROOT / "scripts" / "capture_120fps_spike.py"


def _load_module(path: Path, name: str):
    assert path.is_file(), f"missing implementation: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _frame_times(counts: list[int]) -> list[float]:
    values: list[float] = []
    for second, count in enumerate(counts):
        values.extend(second + (index + 0.5) / count for index in range(count))
    return values


def test_gate_accepts_metrics_at_all_hard_thresholds():
    metrics = _load_module(METRICS_PATH, "capture_metrics_pass")
    frame_times = _frame_times([114, 114, 114, 114, 114])
    backlog = [(index / 10, 500.0) for index in range(51)]

    result = metrics.evaluate_capture_gate(
        frame_times=frame_times,
        backlog_samples=backlog,
        duration_seconds=5.0,
    )

    assert result.passed is True
    assert result.average_fps == 114.0
    assert result.minimum_one_second_fps == 114
    assert result.maximum_backlog_ms == 500.0
    assert result.reasons == ()


def test_gate_rejects_average_fps_below_114():
    metrics = _load_module(METRICS_PATH, "capture_metrics_average")

    result = metrics.evaluate_capture_gate(
        frame_times=_frame_times([113, 113, 113, 113, 113]),
        backlog_samples=[],
        duration_seconds=5.0,
    )

    assert result.passed is False
    assert "average_fps_below_114" in result.reasons


def test_gate_rejects_any_complete_second_below_108_fps():
    metrics = _load_module(METRICS_PATH, "capture_metrics_minimum")

    result = metrics.evaluate_capture_gate(
        frame_times=_frame_times([107, 120, 120, 120, 120]),
        backlog_samples=[],
        duration_seconds=5.0,
    )

    assert result.average_fps > 114
    assert result.minimum_one_second_fps == 107
    assert "one_second_fps_below_108" in result.reasons


def test_gate_rejects_backlog_above_500ms_for_one_continuous_second():
    metrics = _load_module(METRICS_PATH, "capture_metrics_backlog_fail")
    backlog = [(1.0 + index / 10, 501.0) for index in range(11)]

    result = metrics.evaluate_capture_gate(
        frame_times=_frame_times([120, 120, 120, 120, 120]),
        backlog_samples=backlog,
        duration_seconds=5.0,
    )

    assert result.passed is False
    assert result.maximum_sustained_backlog_seconds >= 1.0
    assert "backlog_above_500ms_for_one_second" in result.reasons


def test_gate_allows_short_backlog_spike():
    metrics = _load_module(METRICS_PATH, "capture_metrics_backlog_pass")
    backlog = [(1.0 + index / 10, 900.0) for index in range(10)]
    backlog.append((2.0, 0.0))

    result = metrics.evaluate_capture_gate(
        frame_times=_frame_times([120, 120, 120, 120, 120]),
        backlog_samples=backlog,
        duration_seconds=5.0,
    )

    assert result.passed is True
    assert result.maximum_backlog_ms == 900.0
    assert result.maximum_sustained_backlog_seconds < 1.0


def test_spike_builds_real_libx264_superfast_command_for_unicode_path(tmp_path):
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_command")
    output = tmp_path / "中文 空格" / "技术门禁.mp4"

    command = spike.build_ffmpeg_command(
        ffmpeg_path=Path("E:/QuickRec/ffmpeg/ffmpeg.exe"),
        output_path=output,
        width=1920,
        height=1080,
        fps=120,
    )

    assert command[0].endswith("ffmpeg.exe")
    assert command[command.index("-s") + 1] == "1920x1080"
    assert command[command.index("-r") + 1] == "120"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-preset") + 1] == "superfast"
    assert command[command.index("-threads") + 1] == "1"
    assert command[-1] == str(output)


def test_spike_validates_ffprobe_resolution_and_rate():
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_probe")
    probe = {
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "120/1",
                "r_frame_rate": "120/1",
            }
        ]
    }

    result = spike.validate_probe_result(probe, width=1920, height=1080, fps=120)

    assert result.ok is True
    assert result.actual_fps == 120.0


def test_spike_rejects_invalid_ffprobe_payload():
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_probe_invalid")

    result = spike.validate_probe_result(
        {"streams": [{"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "0/0"}]},
        width=1920,
        height=1080,
        fps=120,
    )

    assert result.ok is False
    assert "invalid_frame_rate" in result.reasons


def test_spike_cleanup_removes_unicode_temporary_video(tmp_path):
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_cleanup")
    output = tmp_path / "中文 空格" / "temporary.mp4"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"temporary")

    removed = spike.cleanup_temporary_video(output)

    assert removed is True
    assert not output.exists()


def test_spike_reports_missing_project_binary(tmp_path):
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_missing_binary")
    spike.PROJECT_ROOT = tmp_path

    result = spike._find_project_binary("ffmpeg")

    assert result is None


def test_video_mode_duplicate_timestamp_is_still_an_encoder_frame():
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_video_mode")
    frame = object()

    class Camera:
        def __init__(self):
            self.samples = iter(((frame, 10.0), (frame, 10.0), (frame, 11.0)))

        def get_latest_frame(self, *, copy, with_timestamp):
            assert copy is False
            assert with_timestamp is True
            return next(self.samples)

    camera = Camera()

    first = spike._next_capture_frame(camera)
    second = spike._next_capture_frame(camera)
    third = spike._next_capture_frame(camera)

    assert first == (frame, 10.0)
    assert second == (frame, 10.0)
    assert third == (frame, 11.0)
    assert spike._is_source_update(None, first[1]) is True
    assert spike._is_source_update(first[1], second[1]) is False
    assert spike._is_source_update(second[1], third[1]) is True


def test_spike_builds_reproducible_dynamic_stimulus_command(tmp_path):
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_stimulus")
    ready_path = tmp_path / "中文 空格" / "stimulus-ready.json"

    command = spike.build_stimulus_command(
        python_executable=Path("E:/Python/python.exe"),
        ready_path=ready_path,
    )

    assert command[0].endswith("python.exe")
    assert command[1].endswith("capture_120fps_stimulus.py")
    assert command[2:] == ["--ready-file", str(ready_path)]


def test_spike_prepares_contiguous_i420_frame_for_reduced_pipe_contention():
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_i420")
    bgra = np.zeros((4, 4, 4), dtype=np.uint8)

    prepared = spike._prepare_frame(bgra, 4, 4)

    assert prepared.shape == (6, 4)
    assert prepared.dtype == np.uint8
    assert prepared.flags.c_contiguous is True
    assert prepared.nbytes == 4 * 4 * 3 // 2


def test_spike_partitions_cpu_affinity_without_overlapping_encoder_cores():
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_affinity")

    capture_cores, encoder_cores = spike.partition_cpu_affinity(list(range(20)))

    assert capture_cores == list(range(8))
    assert encoder_cores == list(range(8, 20))
    assert set(capture_cores).isdisjoint(encoder_cores)


def test_spike_affinity_partition_keeps_single_core_environment_usable():
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_affinity_single")

    capture_cores, encoder_cores = spike.partition_cpu_affinity([7])

    assert capture_cores == [7]
    assert encoder_cores == [7]


def test_capture_sampling_polls_twice_per_frame_without_dxcam_duplicates():
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_sampling_margin")

    assert spike.capture_sampling_fps(120) == 240
    assert spike.capture_sampling_fps(60) == 60
    assert spike.capture_video_mode(120) is False
    assert spike.capture_video_mode(60) is True


def test_delivery_schedule_catches_up_after_source_timing_gap():
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_delivery_schedule")

    due, next_elapsed = spike.delivery_schedule(
        sample_elapsed=3 / 120,
        next_delivery_elapsed=1 / 120,
        delivery_interval=1 / 120,
    )

    assert due == 3
    assert next_elapsed == 4 / 120


def test_delivery_schedule_waits_when_sample_is_early():
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_delivery_wait")

    due, next_elapsed = spike.delivery_schedule(
        sample_elapsed=0.007,
        next_delivery_elapsed=1 / 120,
        delivery_interval=1 / 120,
    )

    assert due == 0
    assert next_elapsed == 1 / 120


def test_async_encoder_moves_frame_preparation_off_capture_loop():
    spike = _load_module(SPIKE_PATH, "capture_120fps_spike_async_encoder")
    prepared_frames: list[np.ndarray] = []
    written_frames: list[memoryview] = []

    class Stdin:
        def write(self, frame):
            time.sleep(0.01)
            written_frames.append(frame)

    def prepare(frame, width, height):
        assert (width, height) == (1920, 1080)
        prepared_frames.append(frame)
        return frame

    worker = spike.AsyncFrameEncoder(
        stdin=Stdin(),
        width=1920,
        height=1080,
        fps=120,
        capture_started=time.perf_counter(),
        prepare_frame=prepare,
        queue_size=4,
    )
    worker.start()
    submitted_at = time.perf_counter()
    worker.submit(np.zeros(1, dtype=np.uint8), sequence_index=1)
    worker.submit(np.ones(1, dtype=np.uint8), sequence_index=2)
    submit_elapsed = time.perf_counter() - submitted_at
    worker.finish()

    assert submit_elapsed < 0.01
    assert len(prepared_frames) == 2
    assert len(written_frames) == 2
    assert len(worker.encoded_frame_times) == 2
    assert len(worker.write_latencies_ms) == 2
    assert len(worker.backlog_samples) == 2
