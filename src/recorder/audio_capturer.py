"""
音频捕获模块

录制系统声音和/或麦克风音频，与视频同步保存为 WAV 临时文件。
停止后由 RecorderManager 在编码阶段使用 FFmpeg 混入视频。

优雅降级：若音频初始化失败，start() 返回 False，不影响视频录制。
"""

import logging
import os
import threading
import wave

logger = logging.getLogger("QuickRec")


class AudioSource:
    """音频源枚举"""
    NONE = "none"
    SYSTEM = "system"
    MICROPHONE = "microphone"
    BOTH = "both"


class AudioCapturer:
    """音频捕获器（基于 pyaudiowpatch + pyaudio）

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

        # 音频流和 WAV 文件
        self._system_stream = None
        self._mic_stream = None
        self._system_wav = None
        self._mic_wav = None
        self._system_temp_path = ""
        self._mic_temp_path = ""

        # pyaudiowpatch 和 pyaudio 实例
        self._pa_wp = None
        self._pa_mic = None

    def start(self, output_stem: str = "") -> bool:
        """初始化音频流并开始捕获

        Args:
            output_stem: 输出文件名前缀（不含扩展名），空则自动生成

        Returns:
            True 表示初始化成功并开始录制，False 表示失败
        """
        try:
            if self._source in (AudioSource.SYSTEM, AudioSource.BOTH):
                if not self._start_system(output_stem):
                    logger.warning("系统声音捕获初始化失败")
                    if self._source == AudioSource.BOTH:
                        # BOTH 模式系统声音失败，尝试仅麦克风
                        logger.info("BOTH 模式降级为仅麦克风")
                        self._source = AudioSource.MICROPHONE
                    else:
                        return False

            if self._source in (AudioSource.MICROPHONE, AudioSource.BOTH):
                if not self._start_mic(output_stem):
                    logger.warning("麦克风捕获初始化失败")
                    if self._source == AudioSource.BOTH:
                        # BOTH 模式麦克风失败，检查系统声音是否已启动
                        if self._system_stream:
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
        """停止捕获，返回临时文件路径列表

        Returns:
            WAV 临时文件路径列表，失败时返回空列表
        """
        self._is_recording.clear()

        # 等待音频线程结束
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=3.0)

        paths = []

        # 关闭系统声音流
        if self._system_stream:
            try:
                self._system_stream.stop_stream()
                self._system_stream.close()
            except Exception:
                pass
            self._system_stream = None

        if self._system_wav:
            try:
                self._system_wav.close()
                paths.append(self._system_temp_path)
            except Exception:
                pass
            self._system_wav = None

        if self._pa_wp:
            try:
                self._pa_wp.terminate()
            except Exception:
                pass
            self._pa_wp = None

        # 关闭麦克风流
        if self._mic_stream:
            try:
                self._mic_stream.stop_stream()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

        if self._mic_wav:
            try:
                self._mic_wav.close()
                paths.append(self._mic_temp_path)
            except Exception:
                pass
            self._mic_wav = None

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

    def _find_wasapi_loopback(self) -> dict | None:
        """查找 WASAPI 环形缓冲区输出设备

        pyaudiowpatch 提供了 get_loopback_device_info() 可直接获取。
        若未找到设备，返回 None。
        """
        try:
            import pyaudiowpatch as pawp
            pa = pawp.PyAudio()
            try:
                # 尝试获取默认输出设备的 loopback
                wasapi_info = pa.get_loopback_device_info()
                if wasapi_info:
                    return wasapi_info
            except Exception:
                pass

            # 遍历所有设备查找 loopback
            device_count = pa.get_device_count()
            for i in range(device_count):
                info = pa.get_device_info_by_index(i)
                if info.get("isLoopbackDevice", False):
                    return info
                # 查找包含 speaker/立体声混音 的 loopback 设备
                name = info.get("name", "").lower()
                if "loopback" in name:
                    return info

            return None
        finally:
            try:
                pa.terminate()
            except Exception:
                pass

    def _start_system(self, output_stem: str) -> bool:
        """初始化 WASAPI 系统声音捕获"""
        try:
            import pyaudiowpatch as pawp

            device_info = self._find_wasapi_loopback()
            if not device_info:
                logger.warning("未找到 WASAPI 环形缓冲区设备")
                return False

            self._pa_wp = pawp.PyAudio()

            # 获取设备实际采样率
            self._sample_rate = int(device_info.get("defaultSampleRate", 48000))
            self._channels = device_info.get("maxInputChannels", 2)

            # 打开 loopback 流
            self._system_stream = self._pa_wp.open(
                format=pawp.paInt16,
                channels=self._channels,
                rate=self._sample_rate,
                input=True,
                input_device_index=device_info["index"],
                frames_per_buffer=1024,
            )

            # 创建 WAV 临时文件
            stem = output_stem or "audio_sys"
            self._system_temp_path = os.path.join(
                self._output_dir, f"{stem}.audio_sys.wav"
            )
            self._system_wav = wave.open(self._system_temp_path, "wb")
            self._system_wav.setnchannels(self._channels)
            self._system_wav.setsampwidth(2)  # 16-bit
            self._system_wav.setframerate(self._sample_rate)

            logger.info(f"系统声音捕获初始化成功: {self._sample_rate}Hz, {self._channels}ch")
            return True

        except Exception as e:
            logger.warning(f"系统声音捕获初始化失败: {e}")
            self._cleanup_system()
            return False

    def _start_mic(self, output_stem: str) -> bool:
        """初始化麦克风捕获"""
        try:
            import pyaudio

            self._pa_mic = pyaudio.PyAudio()

            mic_channels = 1  # 麦克风通常单声道
            mic_rate = self._sample_rate

            self._mic_stream = self._pa_mic.open(
                format=pyaudio.paInt16,
                channels=mic_channels,
                rate=mic_rate,
                input=True,
                frames_per_buffer=1024,
            )

            # 创建 WAV 临时文件
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
            logger.warning(f"麦克风捕获初始化失败: {e}")
            self._cleanup_mic()
            return False

    def _capture_loop(self):
        """音频捕获线程主循环"""
        logger.info("音频捕获线程启动")
        chunk_size = 1024

        try:
            while self._is_recording.is_set():
                # 系统声音
                if self._system_stream and self._system_wav:
                    try:
                        data = self._system_stream.read(
                            chunk_size, exception_on_overflow=False
                        )
                        self._system_wav.writeframes(data)
                    except Exception as e:
                        logger.error(f"系统声音读取异常: {e}")
                        break

                # 麦克风
                if self._mic_stream and self._mic_wav:
                    try:
                        data = self._mic_stream.read(
                            chunk_size, exception_on_overflow=False
                        )
                        self._mic_wav.writeframes(data)
                    except Exception as e:
                        logger.error(f"麦克风读取异常: {e}")
                        break

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
        if self._pa_wp:
            try:
                self._pa_wp.terminate()
            except Exception:
                pass
            self._pa_wp = None
        if self._system_stream:
            try:
                self._system_stream.stop_stream()
                self._system_stream.close()
            except Exception:
                pass
            self._system_stream = None
        # 删除未完成的临时文件
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
        if self._pa_mic:
            try:
                self._pa_mic.terminate()
            except Exception:
                pass
            self._pa_mic = None
        if self._mic_stream:
            try:
                self._mic_stream.stop_stream()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None
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