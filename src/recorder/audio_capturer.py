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

        # pyaudiowpatch 和 pyaudio 实例（与流同生命周期）
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
                        logger.info("BOTH 模式降级为仅麦克风")
                        self._source = AudioSource.MICROPHONE
                    else:
                        return False

            if self._source in (AudioSource.MICROPHONE, AudioSource.BOTH):
                if not self._start_mic(output_stem):
                    logger.warning("麦克风捕获初始化失败")
                    if self._source == AudioSource.BOTH:
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
        if not self._is_recording.is_set():
            # 已经停止或从未启动
            self._cleanup()
            return []

        self._is_recording.clear()

        # 等待音频线程结束（先让线程停止读取数据）
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=5.0)

        paths = []

        # 先关闭 WAV 文件（确保所有数据刷盘），再关闭音频流
        if self._system_wav:
            try:
                self._system_wav.close()
            except Exception:
                pass
            self._system_wav = None
            if self._system_temp_path and os.path.exists(self._system_temp_path):
                paths.append(self._system_temp_path)

        if self._mic_wav:
            try:
                self._mic_wav.close()
            except Exception:
                pass
            self._mic_wav = None
            if self._mic_temp_path and os.path.exists(self._mic_temp_path):
                paths.append(self._mic_temp_path)

        # 关闭音频流
        if self._system_stream:
            try:
                self._system_stream.stop_stream()
                self._system_stream.close()
            except Exception:
                pass
            self._system_stream = None

        if self._mic_stream:
            try:
                self._mic_stream.stop_stream()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

        # 关闭 PyAudio 实例
        if self._pa_wp:
            try:
                self._pa_wp.terminate()
            except Exception:
                pass
            self._pa_wp = None

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

    def _find_wasapi_loopback(self, pa: "pyaudiowpatch.PyAudio") -> dict | None:
        """在给定的 PyAudio 实例上查找 WASAPI 环形缓冲区输出设备

        使用同一 PyAudio 实例发现设备，确保索引可用于后续 open() 调用。

        Args:
            pa: 已初始化的 pyaudiowpatch.PyAudio 实例

        Returns:
            设备信息字典，未找到返回 None
        """
        try:
            # 方法1: 查找默认输出设备的 loopback（推荐方式）
            # 先获取默认输出设备，然后查找其 loopback 设备
            try:
                default_output = pa.get_default_output_device_info()
                default_name = default_output.get("name", "").lower()
                # 搜索与默认输出设备同名的 loopback 设备
                for i in range(pa.get_device_count()):
                    info = pa.get_device_info_by_index(i)
                    if info.get("isLoopbackDevice", False):
                        # loopback 设备名称通常包含输出设备名称
                        loopback_name = info.get("name", "").lower()
                        if default_name and default_name.split("(")[0].strip() in loopback_name:
                            logger.info(f"找到默认输出设备的 loopback: {info.get('name')}")
                            return info
            except Exception as e:
                logger.debug(f"查找默认输出 loopback 失败: {e}")

            # 方法2: 遍历所有设备查找 loopback（取第一个可用的）
            device_count = pa.get_device_count()
            for i in range(device_count):
                info = pa.get_device_info_by_index(i)
                if info.get("isLoopbackDevice", False):
                    logger.info(f"找到 loopback 设备 (index {i}): {info.get('name')}")
                    return info

            logger.warning("未找到任何 WASAPI loopback 设备")
            return None
        except Exception as e:
            logger.error(f"查找 WASAPI loopback 设备异常: {e}")
            return None

    def _start_system(self, output_stem: str) -> bool:
        """初始化 WASAPI 系统声音捕获

        在同一 PyAudio 实例上完成设备发现和流打开，避免跨实例索引不匹配。
        """
        try:
            import pyaudiowpatch as pawp

            # 创建 PyAudio 实例（发现设备和打开流用同一实例）
            self._pa_wp = pawp.PyAudio()

            # 在同一实例上查找 loopback 设备
            device_info = self._find_wasapi_loopback(self._pa_wp)
            if not device_info:
                logger.warning("未找到 WASAPI 环形缓冲区设备")
                self._cleanup_system()
                return False

            # 获取设备实际参数
            self._sample_rate = int(device_info.get("defaultSampleRate", 48000))
            # loopback 设备的 maxInputChannels 为输入通道数
            channels = device_info.get("maxInputChannels", 2)
            if channels < 1:
                channels = 2
            self._channels = channels

            logger.info(f"系统声音设备: {device_info.get('name')}, "
                         f"{self._sample_rate}Hz, {self._channels}ch, "
                         f"index={device_info['index']}")

            # 打开 loopback 流（使用同一实例的设备索引）
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
            logger.warning(f"系统声音捕获初始化失败: {e}", exc_info=True)
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
            logger.warning(f"麦克风捕获初始化失败: {e}", exc_info=True)
            self._cleanup_mic()
            return False

    def _capture_loop(self):
        """音频捕获线程主循环

        从音频流读取 PCM 数据并写入 WAV 文件。
        读取错误时记录日志并跳出循环，不崩溃。
        """
        logger.info("音频捕获线程启动")
        chunk_size = 1024
        read_errors = 0
        max_errors = 10

        try:
            while self._is_recording.is_set():
                # 系统声音
                if self._system_stream and self._system_wav:
                    try:
                        data = self._system_stream.read(
                            chunk_size, exception_on_overflow=False
                        )
                        self._system_wav.writeframes(data)
                    except OSError as e:
                        # 流已关闭，退出循环
                        logger.debug(f"系统声音流已关闭: {e}")
                        break
                    except Exception as e:
                        read_errors += 1
                        if read_errors >= max_errors:
                            logger.error(f"系统声音连续读取错误过多，停止音频捕获")
                            break
                        logger.warning(f"系统声音读取异常 ({read_errors}/{max_errors}): {e}")

                # 麦克风
                if self._mic_stream and self._mic_wav:
                    try:
                        data = self._mic_stream.read(
                            chunk_size, exception_on_overflow=False
                        )
                        self._mic_wav.writeframes(data)
                    except OSError as e:
                        logger.debug(f"麦克风流已关闭: {e}")
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
        if self._system_stream:
            try:
                self._system_stream.stop_stream()
                self._system_stream.close()
            except Exception:
                pass
            self._system_stream = None
        if self._pa_wp:
            try:
                self._pa_wp.terminate()
            except Exception:
                pass
            self._pa_wp = None
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