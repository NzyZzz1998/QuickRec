"""PyAV 解码、固定音频混合与 PyAudio 输出适配器。"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from services.playback_backend import BackendCapabilities, BackendFrame
from services.timeline_query import ActiveClip, PlaybackPlan, mix_audio_blocks

_AUDIO_RATE = 48_000
_AUDIO_CHANNELS = 2
_DEFAULT_AUDIO_BLOCK = 960
logger = logging.getLogger("QuickRec")


class VideoDecoder(Protocol):
    def frame_at(
        self,
        position_us: int,
        *,
        force_seek: bool = False,
    ) -> NDArray[np.uint8]: ...

    def release(self) -> None: ...


class AudioDecoder(Protocol):
    def samples_at(
        self,
        position_us: int,
        sample_count: int,
        *,
        force_seek: bool = False,
    ) -> NDArray[np.float32]: ...

    def release(self) -> None: ...


class AudioOutput(Protocol):
    def start(self) -> None: ...

    def pause(self) -> None: ...

    def write(self, block: NDArray[np.float32]) -> None: ...

    def release(self) -> None: ...


class PlaybackDependencyError(RuntimeError):
    """生产播放依赖缺失。"""


class PyAVPlaybackBackend:
    """把后端无关播放计划映射为 PyAV/PyAudio 操作。"""

    capabilities = BackendCapabilities("PyAV", "18.0.0", max_audio_sources=4)

    def __init__(
        self,
        *,
        video_decoder_factory: Callable[[Path], VideoDecoder] | None = None,
        audio_decoder_factory: Callable[[Path], AudioDecoder] | None = None,
        audio_output_factory: Callable[[], AudioOutput] | None = None,
    ) -> None:
        self._video_decoder_factory = (
            video_decoder_factory or _AvVideoDecoder
        )
        self._audio_decoder_factory = (
            audio_decoder_factory or _AvAudioDecoder
        )
        self._audio_output_factory = (
            audio_output_factory or _PyAudioOutput
        )
        self._video_decoders: dict[tuple[str, str], VideoDecoder] = {}
        self._audio_decoders: dict[tuple[str, str], AudioDecoder] = {}
        self._audio_output: AudioOutput | None = None
        self._last_position_us: int | None = None
        self._muted = False
        self._released = False

    def prepare(self, plan: PlaybackPlan) -> BackendFrame:
        if self._released:
            return _fatal("backend_released", "playback backend was released")
        self._last_position_us = plan.position_us
        self._prune_inactive_decoders(plan)
        video = self._render_video(plan, force_seek=True)
        if video.fatal:
            return video
        try:
            self._ensure_audio_decoders(plan)
            if plan.audio and not self._muted:
                self._ensure_audio_output()
        except PlaybackDependencyError as exc:
            return _fatal("backend_missing", str(exc))
        except OSError as exc:
            return BackendFrame(
                ok=False,
                video_frame=video.video_frame,
                video_status=video.video_status,
                audio_status="unavailable",
                audio_unavailable=True,
                error_kind="audio_device_unavailable",
                error=str(exc),
            )
        except Exception as exc:
            return BackendFrame(
                ok=False,
                video_frame=video.video_frame,
                video_status=video.video_status,
                audio_status="error",
                error_kind="audio_prepare_failed",
                error=str(exc),
            )
        return BackendFrame(
            ok=video.ok,
            video_frame=video.video_frame,
            video_status=video.video_status,
            audio_status=(
                "muted" if self._muted else "ready" if plan.audio else "silent"
            ),
            error_kind=video.error_kind,
            error=video.error,
        )

    def play(self) -> BackendFrame:
        if self._released:
            return _fatal("backend_released", "playback backend was released")
        if self._audio_output is not None and not self._muted:
            try:
                self._audio_output.start()
            except OSError as exc:
                return BackendFrame(
                    ok=False,
                    audio_status="unavailable",
                    audio_unavailable=True,
                    error_kind="audio_device_unavailable",
                    error=str(exc),
                )
        return BackendFrame(audio_status="muted" if self._muted else "ready")

    def pause(self) -> BackendFrame:
        if self._audio_output is not None:
            try:
                self._audio_output.pause()
            except OSError as exc:
                return BackendFrame(
                    ok=False,
                    audio_status="error",
                    error_kind="audio_pause_failed",
                    error=str(exc),
                )
        return BackendFrame(audio_status="muted" if self._muted else "ready")

    def seek(self, plan: PlaybackPlan) -> BackendFrame:
        if self._released:
            return _fatal("backend_released", "playback backend was released")
        self.stop_audio()
        self._last_position_us = plan.position_us
        self._prune_inactive_decoders(plan)
        video = self._render_video(plan, force_seek=True)
        if video.fatal:
            return video
        errors: list[str] = []
        for active in plan.audio[: self.capabilities.max_audio_sources]:
            try:
                decoder = self._audio_decoder(active)
                decoder.samples_at(
                    active.source_position_us,
                    1,
                    force_seek=True,
                )
            except Exception as exc:
                errors.append(f"{active.clip.clip_id}: {exc}")
        if errors:
            return BackendFrame(
                ok=False,
                video_frame=video.video_frame,
                video_status=video.video_status,
                audio_status="error",
                error_kind="audio_seek_failed",
                error="; ".join(errors),
            )
        return BackendFrame(
            ok=video.ok,
            video_frame=video.video_frame,
            video_status=video.video_status,
            audio_status=(
                "muted" if self._muted else "ready" if plan.audio else "silent"
            ),
            error_kind=video.error_kind,
            error=video.error,
        )

    def render(self, plan: PlaybackPlan) -> BackendFrame:
        if self._released:
            return _fatal("backend_released", "playback backend was released")
        self._prune_inactive_decoders(plan)
        video = self._render_video(plan)
        if video.fatal:
            return video
        audio_status = "muted" if self._muted else "silent"
        audio_errors: list[str] = []
        if plan.audio and not self._muted:
            try:
                block_size = self._audio_block_size(plan.position_us)
                blocks: list[NDArray[np.float32]] = []
                for active in plan.audio[
                    : self.capabilities.max_audio_sources
                ]:
                    if not active.source.file_exists:
                        audio_errors.append(
                            f"{active.clip.clip_id}:missing_media"
                        )
                        continue
                    try:
                        blocks.append(
                            self._audio_decoder(active).samples_at(
                                active.source_position_us,
                                block_size,
                            )
                        )
                    except Exception as exc:
                        audio_errors.append(
                            f"{active.clip.clip_id}:{type(exc).__name__}"
                        )
                        logger.warning(
                            "timeline audio source failed: clip_id=%s "
                            "kind=%s",
                            active.clip.clip_id,
                            type(exc).__name__,
                        )
                if blocks:
                    mixed = mix_audio_blocks(blocks)
                    self._ensure_audio_output().write(mixed)
                    audio_status = (
                        "degraded" if audio_errors else "ready"
                    )
                else:
                    audio_status = "error" if audio_errors else "silent"
            except OSError as exc:
                return BackendFrame(
                    ok=False,
                    video_frame=video.video_frame,
                    video_status=video.video_status,
                    audio_status="unavailable",
                    audio_unavailable=True,
                    error_kind="audio_device_unavailable",
                    error=str(exc),
                )
            except Exception as exc:
                audio_status = "error"
                audio_errors.append(f"output:{type(exc).__name__}")
        self._last_position_us = plan.position_us
        return BackendFrame(
            ok=video.ok and not bool(audio_errors),
            video_frame=video.video_frame,
            video_status=video.video_status,
            audio_status=audio_status,
            error_kind=(
                "audio_decode_failed" if audio_errors else video.error_kind
            ),
            error="; ".join(audio_errors) or video.error,
        )

    def stop_audio(self) -> None:
        if self._audio_output is not None:
            try:
                self._audio_output.pause()
            except OSError:
                pass

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        if self._muted:
            self.stop_audio()

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        for video_decoder in self._video_decoders.values():
            video_decoder.release()
        for audio_decoder in self._audio_decoders.values():
            audio_decoder.release()
        self._video_decoders.clear()
        self._audio_decoders.clear()
        if self._audio_output is not None:
            self._audio_output.release()
            self._audio_output = None

    def _render_video(
        self,
        plan: PlaybackPlan,
        *,
        force_seek: bool = False,
    ) -> BackendFrame:
        active = plan.video
        if active is None:
            return BackendFrame(video_status="blank")
        if not active.source.file_exists:
            return BackendFrame(
                ok=False,
                video_status="missing",
                error_kind="missing_media",
                error=f"video source is missing: {active.clip.clip_id}",
            )
        try:
            frame = self._video_decoder(active).frame_at(
                active.source_position_us,
                force_seek=force_seek,
            )
        except PlaybackDependencyError as exc:
            return _fatal("backend_missing", str(exc))
        except Exception as exc:
            return BackendFrame(
                ok=False,
                video_status="error",
                error_kind="video_decode_failed",
                error=str(exc),
            )
        return BackendFrame(video_frame=frame, video_status="ready")

    def _video_decoder(self, active: ActiveClip) -> VideoDecoder:
        key = (active.clip.clip_id, str(active.source.path))
        decoder = self._video_decoders.get(key)
        if decoder is None:
            decoder = self._video_decoder_factory(active.source.path)
            self._video_decoders[key] = decoder
        return decoder

    def _audio_decoder(self, active: ActiveClip) -> AudioDecoder:
        key = (active.clip.clip_id, str(active.source.path))
        decoder = self._audio_decoders.get(key)
        if decoder is None:
            decoder = self._audio_decoder_factory(active.source.path)
            self._audio_decoders[key] = decoder
        return decoder

    def _ensure_audio_decoders(self, plan: PlaybackPlan) -> None:
        for active in plan.audio[: self.capabilities.max_audio_sources]:
            if active.source.file_exists:
                self._audio_decoder(active)

    def _ensure_audio_output(self) -> AudioOutput:
        if self._audio_output is None:
            self._audio_output = self._audio_output_factory()
        return self._audio_output

    def _prune_inactive_decoders(self, plan: PlaybackPlan) -> None:
        active_video_keys = (
            {(plan.video.clip.clip_id, str(plan.video.source.path))}
            if plan.video is not None
            else set()
        )
        active_audio_keys = {
            (active.clip.clip_id, str(active.source.path))
            for active in plan.audio[: self.capabilities.max_audio_sources]
        }
        released_video = _release_inactive(
            self._video_decoders,
            active_video_keys,
        )
        released_audio = _release_inactive(
            self._audio_decoders,
            active_audio_keys,
        )
        if released_video or released_audio:
            logger.debug(
                "timeline playback decoders pruned: video=%d audio=%d",
                released_video,
                released_audio,
            )

    def _audio_block_size(self, position_us: int) -> int:
        previous = self._last_position_us
        if previous is None or position_us <= previous:
            return _DEFAULT_AUDIO_BLOCK
        elapsed_us = min(50_000, max(10_000, position_us - previous))
        return max(1, round(elapsed_us * _AUDIO_RATE / 1_000_000))


def _release_inactive[DecoderT: VideoDecoder | AudioDecoder](
    decoders: dict[tuple[str, str], DecoderT],
    active_keys: set[tuple[str, str]],
) -> int:
    released = 0
    for key in list(decoders):
        if key in active_keys:
            continue
        decoder = decoders.pop(key)
        try:
            decoder.release()
        except Exception as exc:
            logger.warning(
                "timeline decoder release failed: kind=%s",
                type(exc).__name__,
            )
        released += 1
    return released


class _AvVideoDecoder:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._av = _import_av()
        self._container = self._av.open(str(path))
        self._stream = next(
            (
                stream
                for stream in self._container.streams
                if stream.type == "video"
            ),
            None,
        )
        if self._stream is None:
            self.release()
            raise ValueError(f"video stream missing: {path.name}")
        self._frames = iter(self._container.decode(video=0))
        self._last_image: NDArray[np.uint8] | None = None
        self._last_start_us = -1
        self._last_end_us = -1
        self._released = False

    def frame_at(
        self,
        position_us: int,
        *,
        force_seek: bool = False,
    ) -> NDArray[np.uint8]:
        target = max(0, int(position_us))
        if (
            force_seek
            or target < self._last_start_us
            or target > self._last_end_us + 500_000
        ):
            self._seek(target)
        if (
            self._last_image is not None
            and self._last_start_us <= target < self._last_end_us
        ):
            return self._last_image
        for frame in self._frames:
            start_us = _frame_time_us(frame)
            duration_us = _frame_duration_us(frame)
            end_us = start_us + max(1, duration_us)
            image = np.asarray(
                frame.to_ndarray(format="rgb24"),
                dtype=np.uint8,
            )
            self._last_image = image
            self._last_start_us = start_us
            self._last_end_us = end_us
            if target < end_us:
                return image
        if self._last_image is not None:
            return self._last_image
        raise EOFError(f"no video frame decoded: {self._path.name}")

    def release(self) -> None:
        container = getattr(self, "_container", None)
        if container is not None:
            container.close()
            self._container = None
        self._frames = None
        self._stream = None
        self._last_image = None
        self._released = True

    def _seek(self, target_us: int) -> None:
        if self._released or self._container is None:
            raise RuntimeError("video decoder was released")
        self._container.seek(target_us, backward=True, any_frame=False)
        self._frames = iter(self._container.decode(video=0))
        self._last_image = None
        self._last_start_us = -1
        self._last_end_us = -1


class _AvAudioDecoder:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._av = _import_av()
        self._container = self._av.open(str(path))
        self._stream = next(
            (
                stream
                for stream in self._container.streams
                if stream.type == "audio"
            ),
            None,
        )
        if self._stream is None:
            self.release()
            raise ValueError(f"audio stream missing: {path.name}")
        self._frames: Any = None
        self._resampler: Any = None
        self._buffer: NDArray[np.float32] = np.zeros(
            (_AUDIO_CHANNELS, 0),
            dtype=np.float32,
        )
        self._cursor_us: int | None = None
        self._discard_before_us: int | None = None
        self._released = False

    def samples_at(
        self,
        position_us: int,
        sample_count: int,
        *,
        force_seek: bool = False,
    ) -> NDArray[np.float32]:
        target = max(0, int(position_us))
        count = max(1, int(sample_count))
        if (
            force_seek
            or self._cursor_us is None
            or abs(target - self._cursor_us) > 10_000
        ):
            self._seek(target)
        self._fill(count)
        block = self._buffer[:, :count]
        self._buffer = self._buffer[:, count:]
        self._cursor_us = target + round(count * 1_000_000 / _AUDIO_RATE)
        return block.astype(np.float32, copy=False)

    def release(self) -> None:
        container = getattr(self, "_container", None)
        if container is not None:
            container.close()
            self._container = None
        self._frames = None
        self._resampler = None
        self._stream = None
        self._buffer = np.zeros((_AUDIO_CHANNELS, 0), dtype=np.float32)
        self._released = True

    def _seek(self, target_us: int) -> None:
        if self._released or self._container is None:
            raise RuntimeError("audio decoder was released")
        self._container.seek(target_us, backward=True, any_frame=False)
        self._frames = iter(self._container.decode(audio=0))
        self._resampler = self._av.AudioResampler(
            format="fltp",
            layout="stereo",
            rate=_AUDIO_RATE,
        )
        self._buffer = np.zeros((_AUDIO_CHANNELS, 0), dtype=np.float32)
        self._cursor_us = target_us
        self._discard_before_us = target_us

    def _fill(self, sample_count: int) -> None:
        if self._frames is None or self._resampler is None:
            self._seek(self._cursor_us or 0)
        chunks: list[NDArray[np.float32]] = []
        buffered = self._buffer.shape[1]
        while buffered < sample_count:
            try:
                frame = next(self._frames)
            except StopIteration:
                chunks.append(
                    np.zeros(
                        (_AUDIO_CHANNELS, sample_count - buffered),
                        dtype=np.float32,
                    )
                )
                break
            for converted in self._resampler.resample(frame):
                array = np.asarray(
                    converted.to_ndarray(),
                    dtype=np.float32,
                )
                if array.ndim == 1:
                    array = array.reshape(1, -1)
                if array.shape[0] == 1:
                    array = np.repeat(array, _AUDIO_CHANNELS, axis=0)
                array = self._discard_samples_before_target(
                    converted,
                    array,
                )
                if array.shape[1] == 0:
                    continue
                chunks.append(array[:_AUDIO_CHANNELS])
                buffered += array.shape[1]
                if buffered >= sample_count:
                    break
        if chunks:
            self._buffer = np.concatenate(
                [self._buffer, *chunks],
                axis=1,
            )

    def _discard_samples_before_target(
        self,
        frame: Any,
        array: NDArray[np.float32],
    ) -> NDArray[np.float32]:
        target_us = self._discard_before_us
        if target_us is None:
            return array
        if frame.pts is None or frame.time_base is None:
            raise RuntimeError(
                "audio seek frame is missing timestamp metadata"
            )
        frame_start_us = round(float(frame.pts * frame.time_base) * 1_000_000)
        frame_end_us = frame_start_us + round(
            array.shape[1] * 1_000_000 / _AUDIO_RATE
        )
        if frame_end_us <= target_us:
            return array[:, :0]
        if frame_start_us < target_us:
            delta_us = target_us - frame_start_us
            discard = min(
                array.shape[1],
                (delta_us * _AUDIO_RATE + 999_999) // 1_000_000,
            )
            array = array[:, discard:]
        self._discard_before_us = None
        return array


class _PyAudioOutput:
    def __init__(self) -> None:
        try:
            pyaudio = importlib.import_module("pyaudio")
        except ImportError as exc:
            raise PlaybackDependencyError("PyAudio is not installed") from exc
        self._pyaudio_module = pyaudio
        self._owner = pyaudio.PyAudio()
        self._stream = self._owner.open(
            format=pyaudio.paFloat32,
            channels=_AUDIO_CHANNELS,
            rate=_AUDIO_RATE,
            output=True,
            frames_per_buffer=_DEFAULT_AUDIO_BLOCK,
        )
        self._released = False

    def start(self) -> None:
        if self._released:
            raise OSError("audio output was released")
        if self._stream.is_stopped():
            self._stream.start_stream()

    def pause(self) -> None:
        if not self._released and not self._stream.is_stopped():
            self._stream.stop_stream()

    def write(self, block: NDArray[np.float32]) -> None:
        if self._released:
            raise OSError("audio output was released")
        self.start()
        interleaved = np.ascontiguousarray(
            block.T,
            dtype=np.float32,
        )
        self._stream.write(interleaved.tobytes())

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            if not self._stream.is_stopped():
                self._stream.stop_stream()
        finally:
            self._stream.close()
            self._owner.terminate()


def _import_av() -> Any:
    try:
        return importlib.import_module("av")
    except ImportError as exc:
        raise PlaybackDependencyError("PyAV 18.0.0 is not installed") from exc


def _frame_time_us(frame: Any) -> int:
    if frame.pts is None or frame.time_base is None:
        return 0
    return max(0, round(float(frame.pts * frame.time_base) * 1_000_000))


def _frame_duration_us(frame: Any) -> int:
    if frame.duration is None or frame.time_base is None:
        rate = getattr(frame, "rate", None)
        if rate:
            return max(1, round(1_000_000 / float(rate)))
        return 33_333
    return max(1, round(float(frame.duration * frame.time_base) * 1_000_000))


def _fatal(error_kind: str, error: str) -> BackendFrame:
    return BackendFrame(
        ok=False,
        fatal=True,
        video_status="error",
        audio_status="error",
        error_kind=error_kind,
        error=error,
    )
