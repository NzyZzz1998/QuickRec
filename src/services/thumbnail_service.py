"""使用随包 FFmpeg 生成项目素材静态预览。"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import cv2
import numpy as np

from utils.media_metadata import MediaMetadataResult, probe_media, resolve_ffmpeg_path
from utils.thumbnail_cache import (
    ThumbnailCacheEntry,
    ThumbnailCacheStore,
    ThumbnailFingerprint,
)

logger = logging.getLogger("QuickRec")


class ThumbnailErrorCode(StrEnum):
    SOURCE_MISSING = "source_missing"
    FFMPEG_MISSING = "ffmpeg_missing"
    START_FAILED = "start_failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    NONZERO_EXIT = "nonzero_exit"
    IMAGE_EMPTY = "image_empty"
    IMAGE_INVALID = "image_invalid"
    CACHE_UNWRITABLE = "cache_unwritable"
    CACHE_INDEX_WRITE_FAILED = "cache_index_write_failed"
    DISK_SPACE_LOW = "disk_space_low"
    UNEXPECTED = "unexpected"


@dataclass(frozen=True)
class ThumbnailGenerationRequest:
    material_id: str
    source_path: Path
    force: bool = False

    def __init__(
        self,
        material_id: str,
        source_path: str | Path,
        force: bool = False,
    ) -> None:
        object.__setattr__(self, "material_id", str(material_id))
        object.__setattr__(self, "source_path", Path(source_path))
        object.__setattr__(self, "force", bool(force))


@dataclass(frozen=True)
class ThumbnailCommandResult:
    ok: bool
    returncode: int
    stderr: str = ""
    timed_out: bool = False
    cancelled: bool = False
    start_error: str = ""


@dataclass(frozen=True)
class ThumbnailGenerationResult:
    ok: bool
    material_id: str
    path: Path | None = None
    entry: ThumbnailCacheEntry | None = None
    source_position_sec: float | None = None
    cached: bool = False
    error_code: ThumbnailErrorCode | None = None
    error: str = ""
    attempts: int = 0

    @property
    def retryable(self) -> bool:
        return self.error_code not in {
            None,
            ThumbnailErrorCode.SOURCE_MISSING,
            ThumbnailErrorCode.FFMPEG_MISSING,
            ThumbnailErrorCode.CANCELLED,
        }


CommandRunner = Callable[
    [list[str]],
    ThumbnailCommandResult,
]
Probe = Callable[[str | Path], MediaMetadataResult]


class ThumbnailService:
    def __init__(
        self,
        cache: ThumbnailCacheStore,
        *,
        ffmpeg_path: str | None = None,
        probe: Probe = probe_media,
        command_runner: Callable[..., ThumbnailCommandResult] | None = None,
        timeout: float = 10,
    ) -> None:
        self.cache = cache
        self.ffmpeg_path = (
            resolve_ffmpeg_path()
            if ffmpeg_path is None
            else str(ffmpeg_path)
        )
        self._probe = probe
        self._command_runner = command_runner
        self.timeout = float(timeout)

    def generate(
        self,
        request: ThumbnailGenerationRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> ThumbnailGenerationResult:
        started_at = time.monotonic()
        if cancel_event is not None and cancel_event.is_set():
            return self._failure(
                request,
                ThumbnailErrorCode.CANCELLED,
                "thumbnail generation cancelled",
            )
        source = request.source_path
        if not source.is_file():
            return self._failure(
                request,
                ThumbnailErrorCode.SOURCE_MISSING,
                "source video is missing",
            )
        if not self.ffmpeg_path:
            return self._failure(
                request,
                ThumbnailErrorCode.FFMPEG_MISSING,
                "ffmpeg executable not found",
            )
        try:
            fingerprint = ThumbnailFingerprint.from_file(
                request.material_id,
                source,
            )
        except OSError as exc:
            return self._failure(
                request,
                ThumbnailErrorCode.SOURCE_MISSING,
                str(exc),
            )
        if not request.force:
            cached = self.cache.lookup(fingerprint)
            if cached.entry is not None and cached.path is not None:
                logger.info(
                    "thumbnail cache hit: material_id=%s fingerprint=%s",
                    request.material_id,
                    fingerprint.cache_key[:12],
                )
                return ThumbnailGenerationResult(
                    True,
                    request.material_id,
                    cached.path,
                    cached.entry,
                    cached.entry.source_position_sec,
                    cached=True,
                )
        free_bytes = self._cache_free_bytes()
        if free_bytes is not None and free_bytes < 8 * 1024 * 1024:
            return self._failure(
                request,
                ThumbnailErrorCode.DISK_SPACE_LOW,
                "insufficient disk space for thumbnail cache",
            )

        metadata = self._safe_probe(source)
        positions = self._candidate_positions(metadata)
        last_code = ThumbnailErrorCode.NONZERO_EXIT
        last_error = "ffmpeg did not produce a thumbnail"
        attempts = 0
        for position in positions:
            if cancel_event is not None and cancel_event.is_set():
                return self._failure(
                    request,
                    ThumbnailErrorCode.CANCELLED,
                    "thumbnail generation cancelled",
                    attempts=attempts,
                )
            attempts += 1
            temp_path = self.cache.create_temp_path(fingerprint.cache_key)
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            command = self._build_command(source, temp_path, position)
            outcome = self._run_command(
                command,
                timeout=self.timeout,
                cancel_event=cancel_event,
            )
            if not outcome.ok:
                last_code, last_error = self._command_error(outcome)
                self._remove_temp(temp_path)
                if last_code in {
                    ThumbnailErrorCode.START_FAILED,
                    ThumbnailErrorCode.TIMEOUT,
                    ThumbnailErrorCode.CANCELLED,
                }:
                    break
                continue
            if not temp_path.is_file() or temp_path.stat().st_size == 0:
                last_code = ThumbnailErrorCode.IMAGE_EMPTY
                last_error = "ffmpeg produced an empty thumbnail"
                self._remove_temp(temp_path)
                continue
            image_size = self._validate_jpeg(temp_path)
            if image_size != (320, 180):
                last_code = ThumbnailErrorCode.IMAGE_INVALID
                last_error = (
                    "thumbnail image is invalid"
                    if image_size is None
                    else f"thumbnail size is {image_size[0]}x{image_size[1]}"
                )
                self._remove_temp(temp_path)
                continue
            written = self.cache.commit(
                temp_path,
                fingerprint,
                width=320,
                height=180,
                source_position_sec=position,
            )
            if not written.ok or written.entry is None:
                self._remove_temp(temp_path)
                return self._failure(
                    request,
                    ThumbnailErrorCode.CACHE_INDEX_WRITE_FAILED,
                    written.error or "thumbnail cache write failed",
                    attempts=attempts,
                )
            prune = self.cache.prune(
                protected_keys={fingerprint.cache_key}
            )
            if not prune.ok:
                logger.warning(
                    "thumbnail cache cleanup incomplete: removed=%s "
                    "remaining_bytes=%s error=%s",
                    len(prune.removed_keys),
                    prune.remaining_bytes,
                    _short_error(prune.error),
                )
            logger.info(
                "thumbnail generated: material_id=%s position=%.3f attempts=%s "
                "elapsed_ms=%s bytes=%s",
                request.material_id,
                position,
                attempts,
                int((time.monotonic() - started_at) * 1000),
                written.path.stat().st_size if written.path.is_file() else 0,
            )
            return ThumbnailGenerationResult(
                True,
                request.material_id,
                written.path,
                written.entry,
                position,
                attempts=attempts,
            )
        return self._failure(
            request,
            last_code,
            last_error,
            attempts=attempts,
        )

    def _cache_free_bytes(self) -> int | None:
        candidate = self.cache.root
        while not candidate.exists() and candidate.parent != candidate:
            candidate = candidate.parent
        try:
            return int(shutil.disk_usage(candidate).free)
        except OSError:
            return None

    def _safe_probe(self, source: Path) -> MediaMetadataResult:
        try:
            return self._probe(source)
        except Exception as exc:
            logger.warning(
                "thumbnail metadata probe failed: file=%s error=%s",
                source.name,
                _short_error(str(exc)),
            )
            return MediaMetadataResult(False, error=str(exc))

    @staticmethod
    def _candidate_positions(metadata: MediaMetadataResult) -> tuple[float, ...]:
        positions: list[float] = []
        if metadata.ok and metadata.duration_sec:
            positions.append(max(0.0, float(metadata.duration_sec) * 0.1))
        positions.extend((1.0, 0.0))
        unique: list[float] = []
        for value in positions:
            rounded = round(value, 3)
            if rounded not in unique:
                unique.append(rounded)
        return tuple(unique)

    def _build_command(
        self,
        source: Path,
        output: Path,
        position: float,
    ) -> list[str]:
        command = [self.ffmpeg_path, "-y"]
        if position > 0:
            command.extend(("-ss", f"{position:.3f}"))
        command.extend(
            (
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-vf",
                (
                    "scale=320:180:force_original_aspect_ratio=decrease,"
                    "pad=320:180:(ow-iw)/2:(oh-ih)/2:color=0x111827"
                ),
                "-q:v",
                "3",
                "-an",
                "-f",
                "image2",
                str(output),
            )
        )
        return command

    def _run_command(
        self,
        command: list[str],
        *,
        timeout: float,
        cancel_event: threading.Event | None,
    ) -> ThumbnailCommandResult:
        if self._command_runner is not None:
            return self._command_runner(
                command,
                timeout=timeout,
                cancel_event=cancel_event,
            )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
        except OSError as exc:
            return ThumbnailCommandResult(
                False,
                -1,
                start_error=str(exc),
            )
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                self._terminate(process)
                _stdout, stderr = process.communicate()
                return ThumbnailCommandResult(
                    False,
                    process.returncode or -1,
                    stderr=stderr or "",
                    cancelled=True,
                )
            if time.monotonic() >= deadline:
                self._terminate(process)
                _stdout, stderr = process.communicate()
                return ThumbnailCommandResult(
                    False,
                    process.returncode or -1,
                    stderr=stderr or "",
                    timed_out=True,
                )
            time.sleep(0.05)
        _stdout, stderr = process.communicate()
        return ThumbnailCommandResult(
            process.returncode == 0,
            process.returncode,
            stderr=stderr or "",
        )

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        try:
            process.terminate()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                pass

    @staticmethod
    def _validate_jpeg(path: Path) -> tuple[int, int] | None:
        try:
            payload = path.read_bytes()
            decoded = cv2.imdecode(
                np.frombuffer(payload, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if decoded is None or len(decoded.shape) < 2:
                return None
            height, width = decoded.shape[:2]
            return int(width), int(height)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _command_error(
        outcome: ThumbnailCommandResult,
    ) -> tuple[ThumbnailErrorCode, str]:
        if outcome.cancelled:
            return ThumbnailErrorCode.CANCELLED, "thumbnail generation cancelled"
        if outcome.timed_out:
            return ThumbnailErrorCode.TIMEOUT, "ffmpeg timed out"
        if outcome.start_error:
            return ThumbnailErrorCode.START_FAILED, outcome.start_error
        return (
            ThumbnailErrorCode.NONZERO_EXIT,
            outcome.stderr.strip() or f"ffmpeg exited with {outcome.returncode}",
        )

    @staticmethod
    def _remove_temp(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    @staticmethod
    def _failure(
        request: ThumbnailGenerationRequest,
        code: ThumbnailErrorCode,
        error: str,
        *,
        attempts: int = 0,
    ) -> ThumbnailGenerationResult:
        logger.warning(
            "thumbnail generation failed: material_id=%s code=%s "
            "attempts=%s error=%s",
            request.material_id,
            code.value,
            attempts,
            _short_error(error),
        )
        return ThumbnailGenerationResult(
            False,
            request.material_id,
            error_code=code,
            error=error,
            attempts=attempts,
        )


def _short_error(value: str, limit: int = 300) -> str:
    return str(value or "").strip().replace("\r", " ").replace("\n", " ")[:limit]
