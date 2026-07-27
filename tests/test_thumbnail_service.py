from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from services.thumbnail_service import (
    ThumbnailCommandResult,
    ThumbnailErrorCode,
    ThumbnailGenerationRequest,
    ThumbnailService,
)
from utils.media_metadata import MediaMetadataResult
from utils.thumbnail_cache import ThumbnailCacheStore


def _jpeg_bytes(width: int = 320, height: int = 180) -> bytes:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :, 1] = 160
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    assert ok
    return encoded.tobytes()


def _source(tmp_path: Path, name: str = "测试 视频.mp4") -> Path:
    path = tmp_path / name
    path.write_bytes(b"video-source")
    return path


class ScriptedRunner:
    def __init__(self, outcomes: list[ThumbnailCommandResult], jpeg: bytes | None = None) -> None:
        self.outcomes = list(outcomes)
        self.jpeg = jpeg
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        *,
        timeout: float,
        cancel_event: threading.Event | None,
    ) -> ThumbnailCommandResult:
        del timeout, cancel_event
        self.commands.append(command)
        outcome = self.outcomes.pop(0)
        if outcome.ok and self.jpeg is not None:
            Path(command[-1]).write_bytes(self.jpeg)
        return outcome


def _service(
    tmp_path: Path,
    runner: ScriptedRunner,
    *,
    metadata: MediaMetadataResult | None = None,
) -> ThumbnailService:
    return ThumbnailService(
        ThumbnailCacheStore(tmp_path / "cache"),
        ffmpeg_path=str(tmp_path / "ffmpeg.exe"),
        probe=lambda _path: metadata
        or MediaMetadataResult(True, duration_sec=20, width=1920, height=1080, fps=60),
        command_runner=runner,
    )


def test_command_uses_argument_array_and_fixed_preview_contract(tmp_path: Path) -> None:
    runner = ScriptedRunner([ThumbnailCommandResult(True, 0)], _jpeg_bytes())
    service = _service(tmp_path, runner)
    source = _source(tmp_path)

    result = service.generate(ThumbnailGenerationRequest("material-1", source))
    command = runner.commands[0]

    assert result.ok
    assert command[0] == str(tmp_path / "ffmpeg.exe")
    assert command[1:5] == ["-y", "-ss", "2.000", "-i"]
    assert command[5] == str(source)
    filter_value = command[command.index("-vf") + 1]
    assert "scale=320:180:force_original_aspect_ratio=decrease" in filter_value
    assert "pad=320:180:(ow-iw)/2:(oh-ih)/2" in filter_value
    assert command[-1].endswith(".tmp.jpg")


def test_generation_falls_back_from_ten_percent_to_one_second(tmp_path: Path) -> None:
    runner = ScriptedRunner(
        [
            ThumbnailCommandResult(False, 1, stderr="first seek failed"),
            ThumbnailCommandResult(True, 0),
        ],
        _jpeg_bytes(),
    )
    service = _service(tmp_path, runner)

    result = service.generate(ThumbnailGenerationRequest("material-1", _source(tmp_path)))

    assert result.ok
    assert result.source_position_sec == 1.0
    assert runner.commands[0][runner.commands[0].index("-ss") + 1] == "2.000"
    assert runner.commands[1][runner.commands[1].index("-ss") + 1] == "1.000"


def test_generation_falls_back_to_first_decodable_frame(tmp_path: Path) -> None:
    runner = ScriptedRunner(
        [
            ThumbnailCommandResult(False, 1, stderr="ten percent failed"),
            ThumbnailCommandResult(False, 1, stderr="one second failed"),
            ThumbnailCommandResult(True, 0),
        ],
        _jpeg_bytes(),
    )
    service = _service(tmp_path, runner)

    result = service.generate(ThumbnailGenerationRequest("material-1", _source(tmp_path)))

    assert result.ok
    assert result.source_position_sec == 0.0
    assert "-ss" not in runner.commands[2]


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (
            ThumbnailCommandResult(False, -1, start_error="access denied"),
            ThumbnailErrorCode.START_FAILED,
        ),
        (
            ThumbnailCommandResult(False, -1, timed_out=True),
            ThumbnailErrorCode.TIMEOUT,
        ),
        (
            ThumbnailCommandResult(False, -1, cancelled=True),
            ThumbnailErrorCode.CANCELLED,
        ),
        (
            ThumbnailCommandResult(False, 7, stderr="decoder error"),
            ThumbnailErrorCode.NONZERO_EXIT,
        ),
    ],
)
def test_command_failures_return_specific_error_codes(
    tmp_path: Path,
    outcome: ThumbnailCommandResult,
    expected: ThumbnailErrorCode,
) -> None:
    runner = ScriptedRunner([outcome, outcome, outcome])
    service = _service(tmp_path, runner)

    result = service.generate(ThumbnailGenerationRequest("material-1", _source(tmp_path)))

    assert not result.ok
    assert result.error_code == expected


def test_missing_ffmpeg_is_reported_before_command_start(tmp_path: Path) -> None:
    runner = ScriptedRunner([])
    service = ThumbnailService(
        ThumbnailCacheStore(tmp_path / "cache"),
        ffmpeg_path="",
        probe=lambda _path: MediaMetadataResult(
            True,
            duration_sec=2,
            width=1920,
            height=1080,
            fps=30,
        ),
        command_runner=runner,
    )

    result = service.generate(ThumbnailGenerationRequest("material-1", _source(tmp_path)))

    assert not result.ok
    assert result.error_code == ThumbnailErrorCode.FFMPEG_MISSING
    assert runner.commands == []


def test_invalid_or_wrong_sized_jpeg_is_rejected(tmp_path: Path) -> None:
    runner = ScriptedRunner(
        [
            ThumbnailCommandResult(True, 0),
            ThumbnailCommandResult(True, 0),
            ThumbnailCommandResult(True, 0),
        ],
        _jpeg_bytes(160, 90),
    )
    service = _service(tmp_path, runner)

    result = service.generate(ThumbnailGenerationRequest("material-1", _source(tmp_path)))

    assert not result.ok
    assert result.error_code == ThumbnailErrorCode.IMAGE_INVALID
    assert not list((tmp_path / "cache" / "images").glob("*.jpg"))


def test_empty_thumbnail_output_has_distinct_error_code(tmp_path: Path) -> None:
    runner = ScriptedRunner(
        [
            ThumbnailCommandResult(True, 0),
            ThumbnailCommandResult(True, 0),
            ThumbnailCommandResult(True, 0),
        ],
        b"",
    )
    service = _service(tmp_path, runner)

    result = service.generate(
        ThumbnailGenerationRequest("material-1", _source(tmp_path))
    )

    assert not result.ok
    assert result.error_code == ThumbnailErrorCode.IMAGE_EMPTY


def test_low_cache_disk_space_stops_preview_without_running_ffmpeg(
    tmp_path: Path,
) -> None:
    runner = ScriptedRunner([ThumbnailCommandResult(True, 0)], _jpeg_bytes())
    service = _service(tmp_path, runner)

    with patch(
        "services.thumbnail_service.shutil.disk_usage",
        return_value=SimpleNamespace(free=0),
    ):
        result = service.generate(
            ThumbnailGenerationRequest("material-1", _source(tmp_path))
        )

    assert not result.ok
    assert result.error_code == ThumbnailErrorCode.DISK_SPACE_LOW
    assert runner.commands == []


def test_cache_hit_skips_ffmpeg(tmp_path: Path) -> None:
    runner = ScriptedRunner([ThumbnailCommandResult(True, 0)], _jpeg_bytes())
    service = _service(tmp_path, runner)
    request = ThumbnailGenerationRequest("material-1", _source(tmp_path))

    first = service.generate(request)
    second = service.generate(request)

    assert first.ok and not first.cached
    assert second.ok and second.cached
    assert second.path == first.path
    assert len(runner.commands) == 1


def test_cancel_before_generation_does_not_create_cache(tmp_path: Path) -> None:
    runner = ScriptedRunner([ThumbnailCommandResult(True, 0)], _jpeg_bytes())
    service = _service(tmp_path, runner)
    cancelled = threading.Event()
    cancelled.set()

    result = service.generate(
        ThumbnailGenerationRequest("material-1", _source(tmp_path)),
        cancel_event=cancelled,
    )

    assert not result.ok
    assert result.error_code == ThumbnailErrorCode.CANCELLED
    assert runner.commands == []


@pytest.mark.skipif(
    not (Path(__file__).parent.parent / "ffmpeg" / "ffmpeg.exe").is_file(),
    reason="bundled ffmpeg is unavailable",
)
def test_real_bundled_ffmpeg_generates_decodable_jpeg_in_unicode_path(tmp_path: Path) -> None:
    ffmpeg = Path(__file__).parent.parent / "ffmpeg" / "ffmpeg.exe"
    source = tmp_path / "中文 空格" / "真实样本.mp4"
    source.parent.mkdir(parents=True)
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=30",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stderr
    service = ThumbnailService(
        ThumbnailCacheStore(tmp_path / "cache"),
        ffmpeg_path=str(ffmpeg),
    )

    result = service.generate(ThumbnailGenerationRequest("material-real", source))

    assert result.ok, result.error
    assert result.path is not None
    decoded = cv2.imdecode(np.frombuffer(result.path.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape[:2] == (180, 320)


def test_runner_receives_cancel_event_and_timeout(tmp_path: Path) -> None:
    runner = ScriptedRunner([ThumbnailCommandResult(True, 0)], _jpeg_bytes())
    service = _service(tmp_path, runner)
    cancel_event = threading.Event()

    with patch.object(service, "_run_command", wraps=service._run_command) as wrapped:
        result = service.generate(
            ThumbnailGenerationRequest("material-1", _source(tmp_path)),
            cancel_event=cancel_event,
        )

    assert result.ok
    assert wrapped.call_args.kwargs["timeout"] == 10
    assert wrapped.call_args.kwargs["cancel_event"] is cancel_event
