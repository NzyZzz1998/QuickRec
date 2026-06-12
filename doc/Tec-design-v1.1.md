# QuickRec v1.1 详细技术设计文档

> 版本: v1.1
> 创建时间: 2026-06-11
> 更新时间: 2026-06-12
> 状态: 设计完成，待开发
> 前置版本: v1.0（详见 Tec-design-v1.0.md）

---

## 1. 版本概述

### 1.1 v1.1 新增功能清单

基于 PRD 功能列表，v1.1 在 v1.0 基础上新增以下功能：

| 编号 | 功能 | 说明 | PRD 编号 |
|-----|------|------|---------|
| N1 | 区域录制 | 用户拖拽选择矩形区域录制（修复 Win11 兼容性） | F2 |
| N3 | 音频源选择 | 可选系统声音/麦克风/两者/无 | P4, F4/F5/F6 |
| N4 | 录制完成通知增强 | Toast 通知可快速打开文件所在文件夹 | S4 |

**已在 v1.0 完成的功能**（不再出现在 v1.1 计划中）：

| 编号 | 功能 | 说明 |
|-----|------|------|
| — | 自定义快捷键 | 已通过 `_ShortcutRecorder` 实现 |
| — | 帧率选择 | 已在设置对话框中实现（30fps/60fps） |
| — | 画质四档位 | 已实现 native(2K)/high(1080p)/medium(720p)/low(480p) |

### 1.2 v1.1 不包含

- F3 指定窗口录制（推迟到 v2.0）
- P6 开机自启（推迟到 v2.0）
- P7 录制倒计时（推迟到 v2.0）
- 画中画模式（推迟到 v2.0）
- 多显示器选择（推迟到 v2.0）

---

## 2. 模块设计

### 2.1 区域录制模块 (area_selector.py) — 更新

**职责**：提供全屏遮罩 + 拖拽选择矩形区域的界面。

**v1.0 遗留问题**：`Qt.Tool` 窗口标志与 `Qt.WA_TranslucentBackground` 在 Windows 11 上组合使用时导致点击穿透，无法接收输入事件。

**v1.1 修复方案**（v1.0 已有代码基础）：

```python
class AreaSelector(QWidget):
    """区域选择器（v1.1 修复版，解决 Win11 点击穿透）"""

    region_selected = pyqtSignal(int, int, int, int)  # (x, y, width, height)
    cancelled = pyqtSignal()

    MIN_SIZE = 100  # 最小选区边长

    - _start_point: QPoint          # 拖拽起点
    - _end_point: QPoint            # 拖拽终点
    - _is_drawing: bool             # 是否正在拖拽
    - _selected_rect: QRect         # 已确认的选区

    + __init__(parent=None)
    + show_fullscreen()             # 覆盖所有屏幕，激活焦点
    + paintEvent(event)             # 绘制半透明遮罩 + 选区 + 尺寸标签
    + mousePressEvent(event)        # 左键开始拖拽，右键取消
    + mouseMoveEvent(event)         # 拖拽中更新终点
    + mouseReleaseEvent(event)      # 完成拖拽 → 确认对话框
    + keyPressEvent(event)          # ESC 取消
```

**Win11 修复要点**：

- 移除 `Qt.Tool` 窗口标志，仅保留 `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`
- 添加 `Qt.StrongFocus` 焦点策略
- `show_fullscreen()` 中调用 `raise_()` → `activateWindow()` → `setFocus()` 确保接收输入

**v1.1 新增改进**：

1. **确认对话框**：拖拽完成后在选区中心弹出"开始录制"和"取消"按钮，避免误操作
2. **最小尺寸提示**：选区太小时显示红色边框和"选区太小 (最小 100x100)"文字，1秒后自动取消
3. **边框优化**：选区边框从蓝色实线改为白色虚线动画

**交互流程**：

```
用户操作: 托盘菜单"区域录制" / 快捷键 Ctrl+Shift+A
    ↓
main.py: _on_start_region()
    ↓
显示 AreaSelector（全屏半透明遮罩）
    ↓
用户拖拽选择矩形区域 → 释放鼠标
    ↓
选区 >= MIN_SIZE?
├── 是 → 显示确认对话框（"开始录制" / "取消"）
│        ├── "开始录制" → region_selected 信号 → main.py → start_region()
│        └── "取消" → cancelled 信号
└── 否 → 显示红色提示 → cancelled 信号
```

**线程安全**：AreaSelector 是 QWidget，全部在 Qt 主线程操作。但快捷键触发通过 `_HotkeyBridge` 信号桥转发到主线程再创建 AreaSelector，与 v1.0 快捷键触发流程一致。

---

### 2.2 音频录制模块 (audio_capturer.py) — 新增

**职责**：录制系统声音和/或麦克风音频，与视频同步保存。

**技术选型**：使用 `pyaudiowpatch`（WASAPI 环形缓冲区）捕获系统声音，`pyaudio` 捕获麦克风。

**核心类**：

```python
class AudioSource(Enum):
    """音频源枚举"""
    NONE = "none"               # 无音频（v1.0 默认行为）
    SYSTEM = "system"            # 系统声音（WASAPI 环形缓冲区）
    MICROPHONE = "microphone"    # 麦克风输入
    BOTH = "both"               # 系统声音 + 麦克风（两路独立文件）

class AudioCapturer:
    """音频捕获器（基于 pyaudiowpatch + pyaudio）

    录制时将音频 PCM 数据写入 WAV 临时文件，停止后由 RecorderManager
    在编码阶段使用 FFmpeg 混入视频。音频线程独立于录制线程。

    优雅降级：若音频初始化失败，继续无声录制，不影响视频。
    """

    - _source: AudioSource               # 音频源类型
    - _sample_rate: int                  # 实际采样率（WASAPI 默认 48000）
    - _channels: int                      # 声道数（系统声音=2ch，麦克风=1ch）
    - _sample_width: int                 # 采样位深（字节），通常 2（16bit）
    - _is_recording: threading.Event     # 录制进行中标志
    - _audio_thread: threading.Thread    # 音频捕获线程
    - _system_stream: pawp.Stream        # WASAPI 系统声音流
    - _mic_stream: pyaudio.Stream        # 麦克风流
    - _system_wav: wave.Wave_write       # 系统声音 WAV 文件
    - _mic_wav: wave.Wave_write          # 麦克风 WAV 文件
    - _system_temp_path: str             # 系统声音临时文件路径
    - _mic_temp_path: str                # 麦克风临时文件路径
    - _pa_wp: pyaudiowpatch.PyAudio      # WASAPI 实例
    - _pa_mic: pyaudio.PyAudio          # 麦克风实例

    + __init__(source: AudioSource, output_dir: str)
    + start() -> bool                    # 初始化音频流并开始捕获
    + stop() -> list[str]                # 停止捕获，返回临时文件路径列表
    + get_sample_rate() -> int           # 获取实际采样率
    + get_channels() -> int              # 获取声道数
```

**音频临时文件格式**：

使用 Python `wave` 模块直接写入 WAV 文件，与 v1.0 视频临时文件（TLV 格式）类比：

- SYSTEM 模式：一个 WAV 文件（`<output>.audio_sys.wav`）
- MICROPHONE 模式：一个 WAV 文件（`<output>.audio_mic.wav`）
- BOTH 模式：两个独立 WAV 文件

```python
# 音频捕获线程执行逻辑
def _capture_loop(self):
    while self._is_recording.is_set():
        if self._source in (AudioSource.SYSTEM, AudioSource.BOTH):
            data = self._system_stream.read(chunk_size, exception_on_overflow=False)
            self._system_wav.writeframes(data)
        if self._source in (AudioSource.MICROPHONE, AudioSource.BOTH):
            data = self._mic_stream.read(chunk_size, exception_on_overflow=False)
            self._mic_wav.writeframes(data)
```

**线程模型**：

```
主线程 (Qt)                    录制线程                    音频线程
    │                              │                          │
    ├─ _on_start_region()         │                          │
    │   start_region() ─────────→ _start()                  │
    │                              ├─ capturer.start()        │
    │                              │   AudioCapturer.start()──┤─ 打开音频流
    │                              │   _record_thread.start() │   _capture_loop()
    │                              │                          │   写WAV文件
    │   [录制中...]                │   _record_loop()          │
    │                              │   JPEG → 临时文件         │
    │                              │                          │
    ├─ _on_stop_recording()       │                          │
    │   recorder.stop() ──────────→ _stop_and_encode()        │
    │                              │   capturer.close()        │
    │                              │   AudioCapturer.stop()────┤─ 关闭音频流
    │                              │   join(record_thread)     │   关闭 WAV
    │                              │   启动 encode_thread       │
    │   [保存中...]                │                          │
    │                              │   _encode_loop()          │
    │                              │   视频编码                 │
    │                              │   FFmpeg 混入音频 ────────┤─ subprocess
    │                              │                          │
    │   _handle_saved() ←─────────┤─ on_saved 信号桥         │
    │   通知 + 结果条              │                          │
```

**WASAPI 设备发现**：

```python
def _find_wasapi_loopback(self) -> dict | None:
    """查找 WASAPI 环形缓冲区输出设备

    pyaudiowpatch 提供了 get_loopback_device_info() 可直接获取。
    环形缓冲区设备名称通常包含 "Speaker" 或 "立体声混音"。

    若未找到设备, 返回 None，AudioCapturer.start() 将返回 False。
    """
```

**优雅降级链**：

```
尝试初始化音频捕获
    ↓ 初始化失败（设备不可用/权限不足）
log 警告："音频捕获初始化失败，继续无声录制"
AudioCapturer = None
audio_source = NONE
    ↓ 继续录制（仅视频）
```

**BOTH 模式音频合并**：

SYSTEM 和 MICROPHONE 可能有不同的采样率，因此保存为两个独立 WAV 文件。FFmpeg 使用 `amerge` 滤镜合并：

```bash
ffmpeg -y \
    -i video.mp4 \           # 视频
    -i audio_sys.wav \        # 系统声音
    -i audio_mic.wav \        # 麦克风
    -filter_complex "[1:a][2:a]amerge=inputs=2[a]" \
    -map 0:v -map "[a]" \
    -c:v copy -c:a aac -b:a 192k \
    -shortest \
    output.mp4
```

---

### 2.3 系统托盘模块 (tray_icon.py) — 更新

**v1.1 新增**：动态菜单切换 + Toast 通知。

**信号桥扩展**：

```python
class _SignalBridge(QObject):
    """pystray 线程 → Qt 主线程的信号桥"""
    start_fullscreen_requested = pyqtSignal()    # 全屏录制
    start_region_requested = pyqtSignal()        # 区域录制（v1.1 新增）
    pause_resume_requested = pyqtSignal()        # 暂停/继续（v1.1 新增）
    stop_requested = pyqtSignal()                # 停止录制（v1.1 新增）
    settings_requested = pyqtSignal()
    exit_requested = pyqtSignal()

class TrayIcon:
    # v1.0 字段保留
    - _icon: pystray.Icon
    - _callbacks: dict
    - _bridge: _SignalBridge

    # v1.1 新增字段
    - _is_recording: bool                # 录制状态标志
    - _is_paused: bool                    # 暂停状态标志
    - _output_path: str                   # 最近一次录制输出路径（用于"打开文件夹"）

    + set_recording_state(recording: bool, paused: bool = False)
        """切换菜单状态：空闲菜单 ↔ 录制中菜单"""
    + show_notification_with_action(title, msg, action_label, action_callback)
        """显示带操作按钮的 Toast 通知"""
    - _build_idle_menu() -> pystray.Menu           # 空闲状态菜单
    - _build_recording_menu() -> pystray.Menu       # 录制中菜单
    - _rebuild_menu()                              # 重建并更新菜单
```

**动态菜单设计**：

pystray 的 `Menu` 创建后不可变。使用 `MenuItem` 的 `default` 参数为 callable，每次菜单显示时动态计算文字：

```python
# 空闲菜单
"▶ 全屏录制"
"▢ 区域录制"
"⚙ 设置"
"📁 打开保存文件夹"
"───"
"✕ 退出"

# 录制中菜单
"⏸ 暂停录制"  /  "▶ 继续录制"  # 根据 _is_paused 切换文字
"⏹ 停止录制"
"⚙ 设置"
"📁 打开保存文件夹"
"───"
"✕ 退出"
```

**Toast 通知实现**：

```python
def show_notification_with_action(self, title, msg, action_label, action_callback):
    """显示带操作按钮的 Toast 通知

    降级链：winotify → win10toast → pystray.notify()
    """
    # 优先使用 winotify（Windows 10/11）
    try:
        from winotify import Notification, audio
        toast = Notification(
            app_id="QuickRec",
            title=title,
            body=msg,
        )
        toast.add_actions([action_label, "explorer.exe /select," + output_path])
        toast.show()
        return
    except Exception:
        pass

    # 降级：pystray 纯文本通知
    self.show_notification(msg, title)
```

---

### 2.4 录制工具栏模块 (toolbar.py) — 更新

**v1.1 新增**：编码完成后的结果条模式。

```python
class RecordingToolbar(QWidget):
    # v1.0 信号保留
    paused = pyqtSignal()
    resumed = pyqtSignal()
    stopped = pyqtSignal()
    cancelled = pyqtSignal()

    # v1.1 新增信号
    open_folder_requested = pyqtSignal()   # 点击"📂 打开"按钮
    open_file_requested = pyqtSignal()      # 点击"已保存"按钮（播放视频）

    # v1.1 新增状态
    - _result_mode: bool                    # 是否处于结果展示模式
    - _auto_close_timer: QTimer             # 5秒自动关闭定时器
    - _output_path: str                     # 输出文件路径

    + show_result(output_path: str, file_size: str)
        """编码完成后切换到结果条模式

        结果条布局：
        ┌──────────────────────────────────────────────────┐
        │  ✓ 00:00:30  │  已保存  │  📂 打开  │  ✕ 关闭  │
        └──────────────────────────────────────────────────┘
        - 计时器停留显示最终时长
        - "已保存" 按钮：用默认播放器打开视频
        - "📂 打开" 按钮：打开文件所在文件夹并选中文件
        - "✕ 关闭" 按钮：关闭工具栏
        - 5秒后自动关闭
        """
```

**状态流转**：

```
录制中: ● 00:03:25 | ⏸ 暂停 | ⏹ 停止 | ✕ 取消
    ↓ stop()
保存中: ● 保存中...（所有按钮禁用）
    ↓ _handle_saved()
结果条: ✓ 00:03:25 | 已保存 | 📂 打开 | ✕ 关闭
    ↓ 5秒后自动关闭
```

---

### 2.5 录制控制模块 (recorder_manager.py) — 更新

**v1.1 新增**：录制模式、音频集成、FFmpeg 混合。

```python
class RecordMode(Enum):
    """录制模式枚举"""
    FULLSCREEN = "fullscreen"    # 全屏录制
    REGION = "region"            # 区域录制

class RecorderManager:
    # v1.0 字段保留（略）

    # v1.1 新增字段
    - _mode: RecordMode                          # 录制模式
    - _audio_capturer: AudioCapturer | None      # 音频捕获器
    - _audio_source: AudioSource                   # 音频源类型
    - _ffmpeg_path: str                            # FFmpeg 可执行文件路径
    - _audio_temp_paths: list[str]                 # 音频临时文件路径列表

    # v1.0 方法保留
    + start_fullscreen() -> bool
    + start_region(region: tuple) -> bool
    + pause() -> bool
    + resume() -> bool
    + stop(cancel=False) -> str
    + get_state() -> RecorderState
    + get_elapsed() -> str
    + is_saving() -> bool
    + wait_until_idle(timeout=60.0)

    # v1.1 新增/修改方法
    + get_mode() -> RecordMode
    - _start(region=None) -> bool       # 修改: 加入音频初始化
    - _stop_and_encode()                 # 修改: 加入音频停止
    - _encode_loop()                     # 修改: 视频编码后加音频混合
    - _get_ffmpeg_path() -> str          # 新增: 定位 FFmpeg
    - _mix_audio_video(video_path, audio_paths, output_path)  # 新增: FFmpeg 混合
```

**`_start()` 方法扩展**（音频初始化）：

```python
def _start(self, region=None) -> bool:
    # ... v1.0 启动逻辑不变 ...

    # v1.1 新增: 音频初始化
    audio_source_str = self._config.get("audio_source", "none")
    self._audio_source = AudioSource(audio_source_str)

    if self._audio_source != AudioSource.NONE:
        self._audio_capturer = AudioCapturer(
            source=self._audio_source,
            output_dir=os.path.dirname(self._output_path)
        )
        if not self._audio_capturer.start():
            logger.warning("音频捕获初始化失败，继续无声录制")
            self._audio_capturer = None
            self._audio_source = AudioSource.NONE
```

**`_stop_and_encode()` 方法扩展**（音频停止）：

```python
def _stop_and_encode(self):
    # 等待录制线程结束（v1.0 逻辑）
    if self._record_thread and self._record_thread.is_alive():
        self._record_thread.join(timeout=5.0)

    # 关闭临时文件和捕获器（v1.0 逻辑）
    ...

    # v1.1 新增: 停止音频捕获
    self._audio_temp_paths = []
    if self._audio_capturer:
        try:
            paths = self._audio_capturer.stop()
            self._audio_temp_paths = paths if isinstance(paths, list) else [paths]
        except Exception as e:
            logger.error(f"停止音频捕获异常: {e}")
        self._audio_capturer = None

    # 取消录制时清理音频临时文件
    if self._cancelled:
        for p in self._audio_temp_paths:
            ...
        self._cleanup_temp_file()
        ...

    # 启动编码线程（v1.0 逻辑）
    ...
```

**`_encode_loop()` 方法扩展**（音频混合步骤）：

```python
def _encode_loop(self):
    try:
        # Step 1: 视频编码（v1.0 逻辑不变）
        encoder = VideoEncoder(self._output_path, self._fps, self._encode_size)
        # ... 逐帧编码 ...
        encoder.close()

        # Step 2: 音频混合（v1.1 新增）
        if self._audio_temp_paths and self._ffmpeg_path:
            temp_video = self._output_path + ".video_only.mp4"
            os.rename(self._output_path, temp_video)

            try:
                self._mix_audio_video(temp_video, self._audio_temp_paths, self._output_path)
                os.remove(temp_video)
            except Exception as e:
                logger.error(f"音频混入失败，保留纯视频: {e}")
                # 降级：恢复纯视频文件
                if os.path.exists(temp_video):
                    os.replace(temp_video, self._output_path)

        elif self._audio_temp_paths and not self._ffmpeg_path:
            logger.warning("FFmpeg 不可用，无法混入音频，保留纯视频")

        # 清理音频临时文件
        for p in self._audio_temp_paths:
            if os.path.exists(p):
                os.remove(p)

        result_path = self._output_path
    except Exception as e:
        ...

    finally:
        self._cleanup_temp_file()
        with self._lock:
            self._state = RecorderState.IDLE
        if self._on_saved:
            self._on_saved(result_path)
```

**FFmpeg 混合方法**：

```python
def _mix_audio_video(self, video_path: str, audio_paths: list[str], output_path: str):
    """使用 FFmpeg 混合音视频

    Args:
        video_path: 纯视频文件路径
        audio_paths: 音频 WAV 文件路径列表（1或2个）
        output_path: 最终输出文件路径
    """
    cmd = [self._ffmpeg_path, "-y", "-i", video_path]

    # 每个音频源作为独立输入
    for audio_path in audio_paths:
        cmd.extend(["-i", audio_path])

    if len(audio_paths) == 1:
        # 单音频源：直接混入
        cmd.extend([
            "-c:v", "copy",       # 视频直接拷贝
            "-c:a", "aac",        # 音频编码为 AAC
            "-b:a", "192k",       # 音频比特率
            "-shortest",           # 以最短的流为准
        ])
    elif len(audio_paths) == 2:
        # BOTH 模式：使用 amerge 滤镜合并系统声音和麦克风
        cmd.extend([
            "-filter_complex", "[1:a][2:a]amerge=inputs=2[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
        ])

    cmd.append(output_path)

    result = subprocess.run(
        cmd, check=True, timeout=120,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
```

**FFmpeg 定位**：

```python
def _get_ffmpeg_path(self) -> str:
    """定位 FFmpeg 可执行文件

    搜索顺序:
    1. 应用目录下的 ffmpeg/ffmpeg.exe（打包内置）
    2. 系统 PATH 环境变量
    3. 返回空字符串（无音频混合能力）
    """
    # 1. 应用目录
    app_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
    local_ffmpeg = os.path.join(app_dir, "ffmpeg", "ffmpeg.exe")
    if os.path.isfile(local_ffmpeg):
        return local_ffmpeg

    # 2. 系统 PATH
    import shutil
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # 3. 未找到
    return ""
```

**状态流转**（更新）：

```
IDLE → RECORDING → PAUSED → RECORDING → STOPPING → IDLE (取消)
                    ↓                      ↓
                 STOPPING               SAVING → IDLE
                                         ↑ (on_saved 信号桥通知结果)
                                         可选: 音频混合步骤
```

---

### 2.6 配置管理模块 (config.py) — 更新

```python
class ConfigManager:
    defaults = {
        # v1.0 保留
        "save_path": "~/Videos/QuickRec",
        "quality": "high",
        "fps": 30,
        "shortcut_start": "Ctrl+Shift+R",
        "shortcut_stop": "Ctrl+Shift+S",
        "shortcut_pause": "Ctrl+Shift+P",
        "show_countdown": False,
        "countdown_seconds": 3,

        # v1.1 新增
        "audio_source": "none",              # none / system / microphone / both
        "shortcut_area": "Ctrl+Shift+A",     # 区域录制
    }

    # QUALITY_SIZES 不变
```

---

### 2.7 设置对话框模块 (settings_dialog.py) — 更新

新增音频源选择和区域录制快捷键：

```python
# 音频源选项：显示文本 → 配置值
_AUDIO_OPTIONS = [
    ("无", "none"),
    ("系统声音", "system"),
    ("麦克风", "microphone"),
    ("两者都有", "both"),
]

class SettingsDialog(QDialog):
    config_saved = pyqtSignal()

    # v1.0 控件保留
    - _edit_save_path: QLineEdit
    - _combo_quality: QComboBox
    - _combo_fps: QComboBox
    - _shortcut_start: _ShortcutRecorder
    - _shortcut_stop: _ShortcutRecorder
    - _shortcut_pause: _ShortcutRecorder

    # v1.1 新增控件
    - _combo_audio_source: QComboBox        # 音频源选择
    - _shortcut_area: _ShortcutRecorder       # 区域录制快捷键
```

**设置界面布局更新**：

```
┌─ QuickRec 设置 ──────────────────────────────┐
│                                              │
│  保存路径    [C:\Users\xxx\Videos\QuickRec]  │
│  画质        ○ 原生(2K) ○ 高(1080p)           │
│              ○ 中(720p)  ○ 低(480p)           │
│  帧率        ○ 30fps  ○ 60fps                │
│  音频源      ○ 无                              │    ← 新增
│              ○ 系统声音                          │    ← 新增
│              ○ 麦克风                            │    ← 新增
│              ○ 两者都有                          │    ← 新增
│  开始快捷键  [Ctrl+Shift+R] 🎹               │
│  停止快捷键  [Ctrl+Shift+S] 🎹               │
│  暂停快捷键  [Ctrl+Shift+P] 🎹               │
│  区域录制快捷键 [Ctrl+Shift+A] 🎹             │    ← 新增
│                                              │
│              [ 保存 ]  [ 取消 ]               │
└──────────────────────────────────────────────┘
```

---

### 2.8 快捷键管理模块 (hotkey_manager.py) — 不变

无需修改。v1.1 仅新增注册快捷键 `Ctrl+Shift+A`，在 `main.py` 的 `_setup_hotkeys()` 中添加即可。

---

### 2.9 主程序入口 (main.py) — 更新

**新增信号桥**：

```python
class _AreaBridge(QObject):
    """区域选择器信号桥"""
    region_selected = pyqtSignal(int, int, int, int)  # (x, y, w, h)
    cancelled = pyqtSignal()
```

**HotkeyBridge 扩展**：

```python
class _HotkeyBridge(QObject):
    """将 pynput 线程的快捷键回调安全转发到 Qt 主线程"""
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    area_requested = pyqtSignal()        # v1.1 新增
```

**新增回调**：

```python
class QuickRecApp:
    def __init__(self):
        # v1.0 字段保留 ...

        # v1.1 新增: 区域录制信号桥
        self._area_bridge = _AreaBridge()
        self._area_bridge.region_selected.connect(self._on_region_selected)
        self._area_bridge.cancelled.connect(self._on_selection_cancelled)

        # 托盘回调扩展
        self._tray = TrayIcon(
            config=self._config,
            callbacks={
                "start_fullscreen": self._on_start_fullscreen,    # 原 "start"
                "start_region": self._on_start_region,            # v1.1 新增
                "pause_resume": self._on_pause_resume,            # v1.1 新增
                "stop": self._on_stop_recording,                   # v1.1 新增
                "settings": self._show_settings,
                "exit": self._on_exit,
            }
        )

    def _setup_hotkeys(self):
        # v1.0 绑定保留 ...
        # v1.1 新增: 区域录制快捷键
        shortcut_area = self._config.get("shortcut_area", "Ctrl+Shift+A")
        self._hotkey.register(shortcut_area, self._hotkey_bridge.area_requested.emit)

    # v1.1 新增方法
    def _on_start_fullscreen(self):
        """全屏录制（原 _on_start_recording）"""

    def _on_start_region(self):
        """区域录制：显示区域选择器"""
        if self._recorder.get_state() != RecorderState.IDLE:
            return
        selector = AreaSelector()
        selector.region_selected.connect(
            lambda x, y, w, h: self._area_bridge.region_selected.emit(x, y, w, h)
        )
        selector.cancelled.connect(self._area_bridge.cancelled.emit)
        selector.show_fullscreen()

    def _on_region_selected(self, x, y, w, h):
        """区域选择完成：开始录制"""
        if not self._recorder.start_region(region=(x, y, w, h)):
            logger.error("区域录制启动失败")
            return
        self._show_toolbar()
        self._tray.set_recording_state(True)

    def _on_selection_cancelled(self):
        """区域选择取消"""
        pass

    def _handle_saved(self, output_path: str):
        """主线程: 编码完成（v1.0 扩展）"""
        if output_path:
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            size_str = f"{file_size_mb:.1f}MB"
            # v1.1: Toast 通知带"打开文件夹"按钮
            self._tray.show_notification_with_action(
                title="录制已保存",
                msg=f"{os.path.basename(output_path)} ({size_str})",
                action_label="打开文件夹",
                action_callback=lambda: os.startfile(os.path.dirname(output_path))
            )
            # v1.1: 工具栏显示结果条
            if self._toolbar:
                self._toolbar.show_result(output_path, size_str)
        else:
            logger.error("编码保存失败")
            self._tray.show_notification("保存失败")

        self._tray.set_recording_state(False)
        self._hide_toolbar()
```

---

## 3. 新增依赖

| 库 | 版本 | 用途 | 打包影响 |
|----|------|------|---------|
| pyaudiowpatch | 0.2+ | WASAPI 系统声音捕获 | ~1MB |
| pyaudio | 0.2+ | 麦克风音频捕获 | ~2MB（含 PortAudio DLL） |
| winotify | 1.1+ | Windows 10/11 Toast 通知 | ~100KB |
| FFmpeg (binary) | — | AAC 音频编码 + 音视频混合 | ~15MB |

**FFmpeg 打包方式**：

- 将 `ffmpeg.exe` 放在应用目录的 `ffmpeg/` 子目录下
- `build_std.spec` 中添加 `binaries=[('ffmpeg/ffmpeg.exe', 'ffmpeg')]`
- `_get_ffmpeg_path()` 按优先级搜索：应用目录 → 系统 PATH → 返回空字符串
- FFmpeg 不可用时自动降级为无声视频

**注意**：`ffmpeg-python` 包不在依赖列表中，直接使用 `subprocess.run()` 调用 FFmpeg 命令行。

---

## 4. 项目架构更新

### 4.1 目录结构变化

```
QuickRec_dev/src/
├── main.py                      # 更新: _AreaBridge, 区域录制入口, Toast 通知
├── config.py                    # 更新: 新增 audio_source, shortcut_area
├── recorder/
│   ├── recorder_manager.py      # 更新: RecordMode, 音频集成, FFmpeg 混合
│   ├── screen_capturer.py       # 不变
│   ├── video_encoder.py         # 不变
│   └── audio_capturer.py        # 新增: 音频捕获模块
├── ui/
│   ├── tray_icon.py             # 更新: 动态菜单, Toast 通知
│   ├── toolbar.py               # 更新: 结果条模式, 打开文件夹按钮
│   ├── area_selector.py          # 更新: Win11 修复, 确认对话框, 最小尺寸提示
│   └── settings_dialog.py        # 更新: 音频源选择, 区域快捷键
├── hotkey/
│   └── hotkey_manager.py         # 不变
└── utils/
    ├── file_namer.py             # 不变
    └── disk_checker.py           # 不变
```

### 4.2 模块依赖关系更新

```
main.py（三处信号桥: Tray/Hotkey/Areas/Saved → Qt 主线程）
├── config.py（新增 audio_source, shortcut_area）
├── ui/tray_icon.py（动态菜单 + Toast 通知）
├── ui/toolbar.py（结果条 + 打开文件夹）
├── ui/area_selector.py（Win11 修复 + 确认对话框）
├── ui/settings_dialog.py（音频源 + 区域快捷键）
├── hotkey/hotkey_manager.py（不变）
└── recorder/recorder_manager.py（录制模式 + 音频 + FFmpeg）
    ├── recorder/screen_capturer.py（不变）
    ├── recorder/video_encoder.py（不变）
    ├── recorder/audio_capturer.py（新增: pyaudiowpatch + pyaudio）
    ├── utils/file_namer.py（不变）
    └── utils/disk_checker.py（不变）
```

---

## 5. 模块测试计划

| 模块 | 测试方式 | 关键用例 |
|-----|---------|---------|
| AreaSelector | 手动/UI | Win11 下拖拽选区、ESC/右键取消、最小尺寸提示、确认对话框 |
| AudioCapturer | 单元测试 | 系统声音捕获、麦克风捕获、设备不可用时降级、空音频流 |
| RecorderManager | 集成测试 | 全屏+声频、区域+声频、无声降级、BOTH 模式混音 |
| TrayIcon | 手动测试 | 动态菜单切换（空闲/录制中/暂停）、Toast 通知 |
| Toolbar | 手动测试 | 结果条显示、打开文件夹、5秒自动关闭 |
| SettingsDialog | 手动/单元测试 | 音频源选择保存/加载、区域快捷键录制 |
| FFmpeg mixing | 集成测试 | 音视频时长一致、无声降级、FFmpeg 缺失时仅视频 |
| ConfigManager | 单元测试 | audio_source 默认值、shortcut_area 读写、旧配置兼容 |

---

## 6. 开发里程碑

| 阶段 | 内容 | 依赖 |
|-----|------|------|
| 区域录制 | 修复 AreaSelector Win11 兼容性，确认对话框，托盘菜单更新 | AreaSelector 原有代码 |
| 音频录制 | AudioCapturer 模块，WAV 写入，FFmpeg 混合 | FFmpeg binary |
| 通知增强 | TrayIcon 动态菜单 + Toast 通知 + Toolbar 结果条 | winotify |
| 集成测试 | 全模式功能测试 + 打包验证 | 所有模块 |

---

## 7. 风险与应对

| 风险 | 影响 | 应对 |
|-----|------|------|
| Win11 区域选择器仍点击穿透 | 区域录制不可用 | 备选：Win32 API CreateWindow 创建覆盖层 |
| pyaudiowpatch 设备兼容性 | 部分设备音频捕获失败 | 捕获失败时自动降级为无声录制 |
| WASAPI 环形缓冲区设备枚举 | 某些声卡无此设备 | 回退到 pyaudio waveOut；提示用户启用立体声混音 |
| BOTH 模式两路音频采样率不同 | 合并后音频速度异常 | FFmpeg amerge 滤镜自动重采样 |
| FFmpeg 打包体积 | 安装包从 ~50MB 增至 ~65MB | 可接受；或提供 FFmpeg-free 版本 |
| FFmpeg 不可用 | 无法混入音频 | 降级：保留无声 MP4，通知用户 |
| pystray 动态菜单不刷新 | 录制状态切换后菜单不变 | 使用 MenuItem callable 参数；或 icon.update_menu() |
| winotify 在 Windows 7 不可用 | Toast 通知失败 | 降级链：winotify → win10toast → pystray.notify() |