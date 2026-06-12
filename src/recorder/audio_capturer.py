"""
音频捕获模块

录制系统声音和/或麦克风音频，与视频同步保存为 WAV 临时文件。
停止后由 RecorderManager 在编码阶段使用 FFmpeg 混入视频。

系统声音使用 soundcard 库（WASAPI loopback），麦克风使用 pyaudio。
优雅降级：若音频初始化失败，start() 返回 False，不影响视频录制。
"""

import logging
import os
import threading
import wave

import numpy as np

logger = logging.getLogger("QuickRec")


class AudioSource:
    """音频源枚举"""
    NONE = "none"
    SYSTEM = "system"
    MICROPHONE = "microphone"
    BOTH = "both"


class AudioCapturer:
    """音频捕获器（系统声音: soundcard, 麦克风: pyaudio）

    录制时将音频 PCM 数据写入 WAV 临时文件，停止后返回文件路径列表。
    音频线程独立于录制线程，与视频帧缓存并行工作。
    """

    def __init__(self, source: str, output_dir: str):
        """
        Args:
            source: AudioSource 枚举值（"system"/"microphone"/"both"）
            output_dir: WAV 临时文件输出目录
        """
        self._source = source
        self._output_dir = output_dir

        self._sample_rate = 48000
        self._channels = 2
        self._sample_width = 2  # 16-bit = 2 bytes

        self._is_recording = threading.Event()
        self._audio_thread = None

        # 系统声音: soundcard
        self._sys_recorder = None
        self._system_wav = None
        self._system_temp_path = ""

        # 麦克风: pyaudio
        self._mic_stream = None
        self._mic_wav = None
        self._mic_temp_path = ""
        self._pa_mic = None

    def start(self, output_stem: str = "") -> bool:
        """初始化音频流并开始捕获"""
        try:
            if self._source in (AudioSource.SYSTEM, AudioSource.BOTH):
                if not self._start_system(output_stem):
                    logger.warning("系统声音捕获初始化失败")
                    if self._source == AudioSource.BOTH:
                        logger.info("BOTH 模式降级为仅麦克风")
                        self._source = AudioSource.MICROPHONE
                    else:
                        return False

            if self._source in (AudioSource.MICROPHONE, AudioSource.BOTH):
                if not self._start_mic(output_stem):
                    logger.warning("麦克风捕获初始化失败")
                    if self._source == AudioSource.BOTH:
                        if self._sys_recorder:
                            logger.info("BOTH 模式降级为仅系统声音")
                            self._source = AudioSource.SYSTEM
                        else:
                            return False
                    else:
                        return False

            self._is_recording.set()
            self._audio_thread = threading.Thread(
                target=self._capture_loop, daemon=True
            )
            self._audio_thread.start()
            logger.info(f"音频捕获开始: source={self._source}")
            return True

        except Exception as e:
            logger.error(f"音频捕获初始化异常: {e}")
            self._cleanup()
            return False

    def stop(self):
        """停止捕获，返回临时文件路径列表"""
        self._is_recording.clear()

        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=5.0)

        paths = []

        # 关闭系统声音: 先关 WAV 再关 recorder
        if self._system_wav:
            try:
                self._system_wav.close()
            except Exception:
                pass
            self._system_wav = None
            if self._system_temp_path and os.path.exists(self._system_temp_path):
                paths.append(self._system_temp_path)

        if self._sys_recorder:
            try:
                self._sys_recorder.__exit__(None, None, None)
            except Exception:
                pass
            self._sys_recorder = None

        # 关闭麦克风
        if self._mic_wav:
            try:
                self._mic_wav.close()
            except Exception:
                pass
            self._mic_wav = None
            if self._mic_temp_path and os.path.exists(self._mic_temp_path):
                paths.append(self._mic_temp_path)

        if self._mic_stream:
            try:
                self._mic_stream.stop_stream()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

        if self._pa_mic:
            try:
                self._pa_mic.terminate()
            except Exception:
                pass
            self._pa_mic = None

        logger.info(f"音频捕获停止, 文件: {paths}")
        return paths

    def get_sample_rate(self) -> int:
        return self._sample_rate

    def get_channels(self) -> int:
        return self._channels

    # --- 内部方法 ---

    def _find_loopback_mic(self):
        """查找默认扬声器的 WASAPI loopback 麦克风

        Returns:
            (microphone, sample_rate) 或 (None, 0)
        """
        try:
            import soundcard as sc

            # 先获取默认扬声器名称，再匹配其 loopback 设备
            speakers = sc.default_speaker()
            speakers_name = speakers.name.lower()

            mics = sc.all_microphones(include_loopback=True)
            for mic in mics:
                if not getattr(mic, 'isloopback', False):
                    continue
                # 优先匹配与默认扬声器同名的 loopback
                mic_name = mic.name.lower()
                if speakers_name.split("(")[0].strip() in mic_name:
                    logger.info(f"找到匹配的 loopback 设备: {mic.name}")
                    return mic, 48000
            # fallback: 取第一个 loopback
            for mic in mics:
                if getattr(mic, 'isloopback', False):
                    logger.info(f"使用首个 loopback 设备: {mic.name}")
                    return mic, 48000

            return None, 0
        except Exception as e:
            logger.error(f"查找 loopback 设备异常: {e}")
            return None, 0

    def _start_system(self, output_stem: str) -> bool:
        """初始化 WASAPI 系统声音捕获 (soundcard)"""
        try:
            loopback_mic, rate = self._find_loopback_mic()
            if not loopback_mic:
                logger.warning("未找到 WASAPI loopback 设备")
                return False

            self._sample_rate = rate
            self._channels = loopback_mic.channels

            self._sys_recorder = loopback_mic.recorder(samplerate=rate)
            self._sys_recorder.__enter__()

            stem = output_stem or "audio_sys"
            self._system_temp_path = os.path.join(
                self._output_dir, f"{stem}.audio_sys.wav"
            )
            self._system_wav = wave.open(self._system_temp_path, "wb")
            self._system_wav.setnchannels(self._channels)
            self._system_wav.setsampwidth(2)  # 16-bit
            self._system_wav.setframerate(rate)

            logger.info(f"系统声音捕获初始化成功: {rate}Hz, {self._channels}ch")
            return True

        except Exception as e:
            logger.warning(f"系统声音捕获初始化失败: {e}", exc_info=True)
            self._cleanup_system()
            return False

    def _start_mic(self, output_stem: str) -> bool:
        """初始化麦克风捕获 (pyaudio)"""
        try:
            import pyaudio

            self._pa_mic = pyaudio.PyAudio()

            mic_channels = 1
            mic_rate = self._sample_rate

            self._mic_stream = self._pa_mic.open(
                format=pyaudio.paInt16,
                channels=mic_channels,
                rate=mic_rate,
                input=True,
                frames_per_buffer=1024,
            )

            stem = output_stem or "audio_mic"
            self._mic_temp_path = os.path.join(
                self._output_dir, f"{stem}.audio_mic.wav"
            )
            self._mic_wav = wave.open(self._mic_temp_path, "wb")
            self._mic_wav.setnchannels(mic_channels)
            self._mic_wav.setsampwidth(2)  # 16-bit
            self._mic_wav.setframerate(mic_rate)

            logger.info(f"麦克风捕获初始化成功: {mic_rate}Hz, {mic_channels}ch")
            return True

        except Exception as e:
            logger.warning(f"麦克风捕获初始化失败: {e}", exc_info=True)
            self._cleanup_mic()
            return False

    def _capture_loop(self):
        """音频捕获线程主循环"""
        logger.info("音频捕获线程启动")
        chunk_size = 1024
        read_errors = 0
        max_errors = 10

        try:
            while self._is_recording.is_set():
                # 系统声音: soundcard.record() 返回 float32 numpy, 转为 int16
                if self._sys_recorder and self._system_wav:
                    try:
                        data = self._sys_recorder.record(numframes=chunk_size)
                        int16_data = (data * 32767).astype(np.int16)
                        self._system_wav.writeframes(int16_data.tobytes())
                    except OSError:
                        logger.debug("系统声音流已关闭")
                        break
                    except Exception as e:
                        read_errors += 1
                        if read_errors >= max_errors:
                            logger.error(f"系统声音连续读取错误过多，停止音频捕获")
                            break
                        logger.warning(f"系统声音读取异常 ({read_errors}/{max_errors}): {e}")

                # 麦克风: pyaudio 直接返回 int16 bytes
                if self._mic_stream and self._mic_wav:
                    try:
                        data = self._mic_stream.read(
                            chunk_size, exception_on_overflow=False
                        )
                        self._mic_wav.writeframes(data)
                    except OSError:
                        logger.debug("麦克风流已关闭")
                        break
                    except Exception as e:
                        read_errors += 1
                        if read_errors >= max_errors:
                            logger.error(f"麦克风连续读取错误过多，停止音频捕获")
                            break
                        logger.warning(f"麦克风读取异常 ({read_errors}/{max_errors}): {e}")

        except Exception as e:
            logger.error(f"音频捕获线程异常: {e}")

        logger.info("音频捕获线程结束")

    def _cleanup_system(self):
        """清理系统声音资源"""
        if self._system_wav:
            try:
                self._system_wav.close()
            except Exception:
                pass
            self._system_wav = None
        if self._sys_recorder:
            try:
                self._sys_recorder.__exit__(None, None, None)
            except Exception:
                pass
            self._sys_recorder = None
        if self._system_temp_path and os.path.exists(self._system_temp_path):
            try:
                os.remove(self._system_temp_path)
            except Exception:
                pass
            self._system_temp_path = ""

    def _cleanup_mic(self):
        """清理麦克风资源"""
        if self._mic_wav:
            try:
                self._mic_wav.close()
            except Exception:
                pass
            self._mic_wav = None
        if self._mic_stream:
            try:
                self._mic_stream.stop_stream()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None
        if self._pa_mic:
            try:
                self._pa_mic.terminate()
            except Exception:
                pass
            self._pa_mic = None
        if self._mic_temp_path and os.path.exists(self._mic_temp_path):
            try:
                os.remove(self._mic_temp_path)
            except Exception:
                pass
            self._mic_temp_path = ""

    def _cleanup(self):
        """清理所有资源"""
        self._cleanup_system()
        self._cleanup_mic()