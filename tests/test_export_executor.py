from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from exporting.executor import CancellationToken, ExportExecutor
from exporting.models import (
    ExportClip,
    ExportFailureKind,
    ExportMaterialSnapshot,
    ExportOutputSpec,
    ExportPlan,
    ExportProjectSnapshot,
    ExportStage,
    ExportTimelineSnapshot,
    ExportTrack,
    RenderPolicy,
)
from exporting.verifier import ExportVerificationResult


def _plan(tmp_path: Path) -> ExportPlan:
    media = tmp_path / "中文 素材.mp4"
    media.write_bytes(b"source")
    stat = media.stat()
    return ExportPlan.create(
        plan_id="plan-executor",
        created_at="2026-07-29T12:00:00+00:00",
        project=ExportProjectSnapshot(
            "project-1",
            "执行项目",
            str(tmp_path / "project.qrproj"),
            1,
            2,
        ),
        timeline=ExportTimelineSnapshot(
            "timeline-1",
            2_000_000,
            (ExportTrack("video-1", "video", 0),),
            (
                ExportClip(
                    "video-clip",
                    "material-1",
                    "video-1",
                    None,
                    0,
                    2_000_000,
                    0,
                    2_000_000,
                ),
            ),
        ),
        materials=(
            ExportMaterialSnapshot(
                "material-1",
                str(media),
                str(media).casefold(),
                stat.st_size,
                stat.st_mtime_ns,
                "mov,mp4,m4a,3gp,3g2,mj2",
                "h264",
                320,
                180,
                30.0,
                2_000_000,
                None,
                None,
                None,
                None,
            ),
        ),
        render_policy=RenderPolicy(),
        output=ExportOutputSpec(
            320,
            180,
            30,
            str(tmp_path / "输出 目录"),
            "结果.mp4",
        ),
    )


def _python_process_factory(script_factory):
    processes: list[subprocess.Popen[str]] = []

    def factory(arguments: list[str], cwd: Path) -> subprocess.Popen[str]:
        script = script_factory(Path(arguments[-1]))
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", script],
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        processes.append(process)
        return process

    return factory, processes


def _material_ok(_plan: ExportPlan) -> ExportVerificationResult:
    return ExportVerificationResult(True)


def test_executor_parses_progress_and_keeps_verified_candidate(
    tmp_path: Path,
) -> None:
    def script(output: Path) -> str:
        return (
            "from pathlib import Path\n"
            "import time\n"
            f"Path({str(output)!r}).write_bytes(b'candidate')\n"
            "for value in (0, 1000000, 2000000):\n"
            " print(f'out_time_us={value}', flush=True)\n"
            " print('progress=continue', flush=True)\n"
            " time.sleep(0.01)\n"
            "print('progress=end', flush=True)\n"
        )

    factory, processes = _python_process_factory(script)
    progress = []
    executor = ExportExecutor(
        ffmpeg_resolver=lambda: sys.executable,
        process_factory=factory,
        material_verifier=_material_ok,
        poll_interval_seconds=0.005,
    )

    result = executor.execute(
        _plan(tmp_path),
        attempt_id="attempt-1",
        on_progress=progress.append,
    )

    assert result.ok
    assert result.stage == ExportStage.VERIFYING
    assert result.failure_kind is None
    assert result.temp_output_path is not None
    assert result.temp_output_path.is_file()
    assert result.temp_output_path.parent == tmp_path / "输出 目录"
    assert result.temp_output_path.name.endswith(".part.mp4")
    assert result.progress is not None
    assert result.progress.percent == 96
    running = [item for item in progress if item.stage == ExportStage.RUNNING]
    assert running[0].percent == 5
    assert max(item.percent for item in running) == 95
    assert all(item.percent < 100 for item in progress)
    assert all(process.poll() is not None for process in processes)
    assert not list((tmp_path / "输出 目录").glob("*.filter.txt"))


def test_executor_stops_before_launch_when_material_changed(
    tmp_path: Path,
) -> None:
    launched = False

    def factory(_arguments: list[str], _cwd: Path):
        nonlocal launched
        launched = True
        raise AssertionError("process must not start")

    executor = ExportExecutor(
        ffmpeg_resolver=lambda: sys.executable,
        process_factory=factory,
        material_verifier=lambda _plan: ExportVerificationResult(
            False,
            failure_kind=ExportFailureKind.MATERIAL_CHANGED,
            message="changed",
        ),
    )

    result = executor.execute(_plan(tmp_path), attempt_id="attempt-2")

    assert not result.ok
    assert result.failure_kind == ExportFailureKind.MATERIAL_CHANGED
    assert not launched


def test_executor_cancellation_reaps_process_and_cleans_candidate(
    tmp_path: Path,
) -> None:
    def script(output: Path) -> str:
        return (
            "from pathlib import Path\n"
            "import time\n"
            f"Path({str(output)!r}).write_bytes(b'partial')\n"
            "print('out_time_us=100000', flush=True)\n"
            "print('progress=continue', flush=True)\n"
            "time.sleep(10)\n"
        )

    factory, processes = _python_process_factory(script)
    token = CancellationToken()
    timer = threading.Timer(0.05, token.cancel)
    timer.start()
    try:
        result = ExportExecutor(
            ffmpeg_resolver=lambda: sys.executable,
            process_factory=factory,
            material_verifier=_material_ok,
            poll_interval_seconds=0.005,
            cancel_grace_seconds=0.02,
        ).execute(
            _plan(tmp_path),
            attempt_id="attempt-cancel",
            cancel_token=token,
        )
    finally:
        timer.cancel()

    assert not result.ok
    assert result.stage == ExportStage.CANCELLED
    assert result.failure_kind == ExportFailureKind.CANCELLED
    assert all(process.poll() is not None for process in processes)
    assert not list((tmp_path / "输出 目录").glob("*.part.mp4"))
    assert not list((tmp_path / "输出 目录").glob("*.filter.txt"))


def test_executor_terminates_stalled_process_and_reports_warning(
    tmp_path: Path,
) -> None:
    def script(output: Path) -> str:
        return (
            "from pathlib import Path\n"
            "import time\n"
            f"Path({str(output)!r}).write_bytes(b'partial')\n"
            "time.sleep(10)\n"
        )

    factory, processes = _python_process_factory(script)
    progress = []
    result = ExportExecutor(
        ffmpeg_resolver=lambda: sys.executable,
        process_factory=factory,
        material_verifier=_material_ok,
        poll_interval_seconds=0.005,
        stall_warning_seconds=0.03,
        stall_timeout_seconds=0.08,
        cancel_grace_seconds=0.01,
    ).execute(
        _plan(tmp_path),
        attempt_id="attempt-stall",
        on_progress=progress.append,
    )

    assert not result.ok
    assert result.stage == ExportStage.FAILED
    assert result.failure_kind == ExportFailureKind.STALLED
    assert any(item.stalled for item in progress)
    assert all(process.poll() is not None for process in processes)
    assert not list((tmp_path / "输出 目录").glob("*.part.mp4"))


def test_executor_continue_waiting_resets_stall_window(
    tmp_path: Path,
) -> None:
    def script(output: Path) -> str:
        return (
            "from pathlib import Path\n"
            "import time\n"
            f"Path({str(output)!r}).write_bytes(b'partial')\n"
            "time.sleep(10)\n"
        )

    factory, processes = _python_process_factory(script)
    token = CancellationToken()
    progress = []
    continued = False

    def on_progress(snapshot) -> None:
        nonlocal continued
        progress.append(snapshot)
        if snapshot.stalled and not continued:
            continued = True
            token.continue_waiting()

    result = ExportExecutor(
        ffmpeg_resolver=lambda: sys.executable,
        process_factory=factory,
        material_verifier=_material_ok,
        poll_interval_seconds=0.005,
        stall_warning_seconds=0.03,
        stall_timeout_seconds=0.08,
        cancel_grace_seconds=0.01,
    ).execute(
        _plan(tmp_path),
        attempt_id="attempt-stall-continued",
        cancel_token=token,
        on_progress=on_progress,
    )

    stalled_indexes = [
        index for index, item in enumerate(progress) if item.stalled
    ]
    assert continued
    assert len(stalled_indexes) >= 2
    assert any(
        not item.stalled
        for item in progress[stalled_indexes[0] + 1 : stalled_indexes[1]]
    )
    assert not result.ok
    assert result.failure_kind == ExportFailureKind.STALLED
    assert all(process.poll() is not None for process in processes)
    assert not list((tmp_path / "输出 目录").glob("*.part.mp4"))


def test_executor_reports_nonzero_exit_and_redacts_long_stderr(
    tmp_path: Path,
) -> None:
    sensitive = str(tmp_path / "private" / "source.mp4")

    def script(_output: Path) -> str:
        return (
            "import sys\n"
            f"sys.stderr.write('failed at ' + {sensitive!r} + 'x' * 70000)\n"
            "sys.stderr.flush()\n"
            "raise SystemExit(7)\n"
        )

    factory, _ = _python_process_factory(script)
    result = ExportExecutor(
        ffmpeg_resolver=lambda: sys.executable,
        process_factory=factory,
        material_verifier=_material_ok,
        poll_interval_seconds=0.005,
    ).execute(_plan(tmp_path), attempt_id="attempt-failed")

    assert not result.ok
    assert result.failure_kind == ExportFailureKind.TOOL_FAILED
    assert result.exit_code == 7
    assert sensitive not in result.stderr_tail
    assert result.stderr_tail
    assert len(result.stderr_tail.encode("utf-8")) <= 64 * 1024
