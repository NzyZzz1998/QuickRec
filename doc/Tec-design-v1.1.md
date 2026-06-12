# QuickRec v1.1 详细技术设计文档

> 版本: v1.1
> 创建时间: 2026-06-11
> 状态: 设计中
> 前置版本: v1.0（详见 Tec-design-v1.0.md）

---

## 1. 版本概述

### 1.1 v1.1 新增功能清单

基于 PRD 功能列表，v1.1 在 v1.0 基础上新增以下功能：

| 编号 | 功能 | 说明 | PRD 编号 |
|-----|------|------|---------|
| N1 | 区域录制 | 用户拖拽选择矩形区域录制 | F2 |
| N2 | 指定窗口录制 | 点击某个窗口，只录制该窗口内容 | F3 |
| N3 | 音频源选择 | 可选系统声音/麦克风/两者/无 | P4, F4/F5/F6 |
| N4 | 录制完成通知增强 | 完成后通知可快速打开文件所在文件夹 | S4 |

**已在 v1.0 完成的功能**（不再出现在 v1.1 计划中）：

| 编号 | 功能 | 说明 |
|-----|------|------|
| - | 自定义快捷键 | 已通过 `_ShortcutRecorder` 实现（Bug #13 修复） |
| - | 帧率选择 | 已在设置对话框中实现（30fps/60fps 切换） |
| - | 画质四档位 | 已实现 native(2K)/high(1080p)/medium(720p)/low(480p) |

### 1.2 v1.1 不包含

- P6 开机自启（推迟到 v2.0）
- P7 录制倒计时（推迟到 v2.0）
- 画中画模式（推迟到 v2.0）
- 多显示器选择（推迟到 v2.0）

---

## 2. 模块设计

### 2.1 区域录制模块 (area_selector.py)

**职责**：提供全屏遮罩 + 拖拽选择矩形区域的界面。

**v1.0 遗留问题**：`Qt.Tool` 窗口标志与 `Qt.WA_TranslucentBackground` 在 Windows 11 上组合使用时导致点击穿透，无法接收输入事件。

**v1.1 修复方案**（已有代码基础）：

```python
class AreaSelector(QWidget):
    """区域选择器"""

    region_selected = pyqtSignal(int, int, int, int)  # (x, y, width, height)
    cancelled = pyqtSignal()

    MIN_SIZE = 100  # 最小选区 100x100

    def _init_ui(self):
        # 关键修复：移除 Qt.Tool，仅用 FramelessWindowHint + WindowStaysOnTopHint
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)

    def show_fullscreen(self):
        # 覆盖所有屏幕
        desktop = QApplication.desktop()
        self.setGeometry(desktop.geometry())
        self.show()
        self.raise_()          # 提升到最顶层
        self.activateWindow()  # 激活窗口
        self.setFocus()         # 强制获取焦点

    # 交互：
    # - 左键拖拽选择区域
    # - 右键取消选择
    # - ESC 取消选择
    # - 选中区域实时显示尺寸标签 "1280 x 720"
    # - 选区太小时视为取消
```

**v1.1 新增改进**：
- 选区确认对话框：拖拽完成后显示"开始录制"和"取消"按钮，避免误操作
- 选区尺寸限制最小值提示
- 选区高亮边框优化（蓝色 → 白色虚线动画边框）

**录制流程集成**：

```
用户操作: 托盘菜单"区域录制" / 快捷键 Ctrl+Shift+A
    ↓
显示 AreaSelector（全屏半透明遮罩）
    ↓
用户拖拽选择矩形区域
    ↓
region_selected 信号 → main.py
    ↓
RecorderManager.start_region(region=(x, y, w, h))
    ↓
显示工具栏，开始录制
```

**托盘菜单更新**：

```
┌──────────────────┐
│  ▶ 全屏录制       │    ← 原"开始录制"改为"全屏录制"
│  ▢ 区域录制       │    ← 新增
│  ⚙ 设置          │
│  📁 打开保存文件夹 │
│  ─────────────    │
│  ✕ 退出           │
└──────────────────┘

录制中菜单：
┌──────────────────┐
│  ⏸ 暂停/继续      │
│  ⏹ 停止录制       │
│  ⚙ 设置          │
│  📁 打开保存文件夹 │
│  ─────────────    │
│  ✕ 退出           │
└──────────────────┘
```

**快捷键更新**：

| 功能 | 快捷键 |
|-----|-------|
| 全屏录制 | `Ctrl+Shift+R`（不变） |
| 区域录制 | `Ctrl+Shift+A`（新增） |
| 停止录制 | `Ctrl+Shift+S`（不变） |
| 暂停/继续 | `Ctrl+Shift+P`（不变） |

---

### 2.2 指定窗口录制模块 (window_selector.py) — 新增

**职责**：提供窗口列表和窗口高亮选择界面，用户点击某窗口后只录制该窗口内容。

**核心类**：

```python
class WindowInfo:
    """窗口信息"""
    hwnd: int             # 窗口句柄
    title: str            # 窗口标题
    class_name: str       # 窗口类名
    rect: tuple           # (left, top, right, bottom)
    process_name: str     # 进程名
    is_visible: bool      # 是否可见

class WindowSelector(QWidget):
    """窗口选择器"""

    window_selected = pyqtSignal(int, int, int, int)  # (x, y, width, height)
    cancelled = pyqtSignal()

    def _init_ui(self):
        """初始化界面"""
        # 全屏半透明遮罩 + 窗口列表
        # 鼠标悬停时高亮当前窗口边框
        # 点击选择窗口
        # ESC 取消

    def _enumerate_windows(self) -> list[WindowInfo]:
        """枚举所有可见窗口"""
        # 使用 Win32 API: EnumWindows + GetWindowText + IsWindowVisible
        # 过滤：仅含标题、可见、不包含 QuickRec 自身

    def _highlight_window(self, hwnd: int):
        """高亮指定窗口边框"""
        # 在目标窗口周围绘制红色边框
        # 显示窗口标题和尺寸信息

    def _on_window_clicked(self, hwnd: int):
        """用户选择窗口"""
        # 获取窗口位置 → 发射 window_selected 信号
        # 考虑窗口最小化的情况 → 提示用户先恢复窗口
```

**技术方案**：

1. **窗口枚举**：使用 `ctypes.windll.user32.EnumWindows` + `GetWindowTextW` 枚举所有可见窗口
2. **窗口高亮**：在目标窗口位置绘制半透明覆盖层（类似区域选择器），边框高亮选中窗口
3. **窗口内容捕获**：调用 `dxcam.create(region=window_rect)` 截取指定区域，与区域录制复用同一捕获逻辑
4. **窗口位置追踪**：录制期间每帧检查窗口位置（`GetWindowRect`），如果窗口移动则更新捕获区域

**窗口移动处理**：

```python
def _record_loop(self):
    """录制循环 - 窗口录制模式"""
    while not self._stop_event.is_set():
        # 每帧检查窗口位置
        if self._window_hwnd:
            new_rect = get_window_rect(self._window_hwnd)
            if new_rect != self._last_rect:
                self._last_rect = new_rect
                # 更新捕获区域（暂停捕获 → 重新 start）
                self._update_capture_region(new_rect)
```

**托盘菜单集成**：

```
┌──────────────────┐
│  ▶ 全屏录制       │
│  ▢ 区域录制       │
│  🖥 窗口录制      │    ← 新增
│  ⚙ 设置          │
│  📁 打开保存文件夹 │
│  ─────────────    │
│  ✕ 退出           │
└──────────────────┘
```

**快捷键**：`Ctrl+Shift+W` 开始窗口录制（可自定义）

---

### 2.3 音频录制模块 (audio_capturer.py) — 新增

**职责**：录制系统声音和/或麦克风音频，与视频同步保存。

**技术选型**：使用 `pyaudiowpatch`（PyAudio 的 Windows 环形缓冲区分支）捕获 WASAPI 音频流。

**核心类**：

```python
class AudioSource(Enum):
    NONE = "none"           # 无音频
    SYSTEM = "system"       # 系统声音
    MICROPHONE = "microphone"  # 麦克风
    BOTH = "both"           # 系统声音 + 麦克风

class AudioCapturer:
    """音频捕获器（基于 pyaudiowpatch）"""

    - _source: AudioSource              # 音频源类型
    - _system_stream: pyaudiowpatch.Stream  # 系统声音流
    - _mic_stream: pyaudio.Stream       # 麦克风流
    - _audio_chunks: list                # 音频数据块列表
    - _is_recording: bool
    - _sample_rate: int                  # 采样率
    - _channels: int                     # 声道数

    + __init__(source: AudioSource, sample_rate=44100)
    + start() -> bool                    # 开始音频捕获
    + stop() -> bytes                    # 停止捕获，返回合并的音频数据
    + get_sample_rate() -> int           # 获取采样率
    + get_channels() -> int              # 获取声道数
```

**逐帧同步方案**：

音频数据以 PCM 格式存储，在视频编码阶段作为独立音轨混入 MP4 容器。

```
录制时：
  录制线程：截图 → JPEG 写临时文件（与 v1.0 相同）
  音频线程：collect audio chunks → PCM 数据写入临时音频文件

编码时：
  视频编码线程：读临时文件 → 解压帧 → 写 VideoWriter（与 v1.0 相同）
  音频混入：将 PCM 数据编码为 AAC → 混入 MP4 容器
```

**音频编码选择**：

| 方案 | 优点 | 缺点 |
|-----|------|------|
| 方案A：pyaudiowpatch + FFmpeg 混入 | 音质好，AAC 编码标准 | 需要 FFmpeg 依赖 |
| 方案B：pyaudiowpatch + OpenCV 写入 | 无额外依赖 | OpenCV 不支持音频轨道 |
| 方案C：pyaudiowpatch + 直接输出 WAV | 最简单实现 | 文件体积大，需后处理转码 |

**选择方案A**：FFmpeg 混入方案。FFmpeg 以二进制形式嵌入（约 15MB），提供 AAC 编码能力。

**音频混合流程**：

```python
def _mix_audio_video(self, video_path: str, audio_path: str, output_path: str):
    """使用 FFmpeg 混合音视频"""
    cmd = [
        self._ffmpeg_path, "-y",
        "-i", video_path,         # 视频输入
        "-i", audio_path,         # 音频输入
        "-c:v", "copy",           # 视频直接拷贝
        "-c:a", "aac",            # 音频编码为 AAC
        "-shortest",               # 以较短的流为准
        output_path
    ]
    subprocess.run(cmd, check=True)
    # 删除原始无声视频和临时音频文件
```

**配置更新** (config.py)：

```python
defaults = {
    ...
    "audio_source": "none",  # none / system / microphone / both
}
```

**设置对话框更新** (settings_dialog.py)：

新增音频源选择区域：

```
┌─ QuickRec 设置 ────────────────────┐
│                                    │
│  保存路径    [C:\Videos\QuickRec]   │
│  画质        ○ 原生(2K) ○ 高(1080p) │
│              ○ 中(720p)  ○ 低(480p) │
│  帧率        ○ 30fps  ○ 60fps      │
│  音频源      ○ 无                    │
│              ○ 系统声音              │
│              ○ 麦克风                │
│              ○ 两者都有              │
│  快捷键      [Ctrl+Shift+R] 🎹     │
│                                    │
│              [ 保存 ]  [ 取消 ]     │
└────────────────────────────────────┘
```

---

### 2.4 录制完成通知增强 (tray_icon.py)

**职责**：录制完成后弹出系统通知，包含"打开文件夹"可点击操作。

**v1.0 现状**：使用 `pystray.Icon.notify()` 显示纯文本通知，无法交互。

**v1.1 改进**：使用 Windows 10/11 原生 Toast 通知，支持操作按钮。

**技术方案**：

```python
from win10toast import ToastNotifier  # 或使用 winotify

class TrayIcon:
    ...
    def show_notification_with_action(self, title: str, msg: str, action_label: str, action_callback):
        """显示带操作按钮的 Toast 通知"""
        # 使用 winotify 发送 Toast 通知
        # 通知中包含"打开文件夹"按钮
        # 点击按钮触发 action_callback
```

**备选方案**：如果 Toast 通知库不可靠，退化为 v1.0 的纯文本通知，同时在工具栏上增加"打开文件夹"按钮。

**通知行为**：

```
录制停止 → 编码完成
    ↓
Toast 通知: "录制已保存"
    内容: QuickRec_20260611_143025.mp4 (15.2MB)
    按钮: [打开文件夹]
    ↓
点击"打开文件夹" → explorer.exe 打开保存路径并选中文件
```

**工具栏增强**：

编码完成后（`on_saved` 返回后），短暂显示结果通知：

```
┌──────────────────────────────────────────────────┐
│  ✓ 00:00:30  │  已保存  │  📂 打开  │  ✕ 关闭    │
└──────────────────────────────────────────────────┘
```

- "已保存" 按钮点击 → 用默认播放器打开视频
- "📂 打开" 按钮点击 → 打开文件所在文件夹并选中文件
- "✕ 关闭" → 关闭工具栏
- 5 秒后自动关闭

---

## 3. RecorderManager 更新

### 3.1 录制模式扩展

```python
class RecordMode(Enum):
    FULLSCREEN = "fullscreen"    # 全屏录制
    REGION = "region"            # 区域录制
    WINDOW = "window"            # 窗口录制

class RecorderManager:
    def __init__(self, config, on_saved=None):
        ...
        self._mode: RecordMode = RecordMode.FULLSCREEN
        self._window_hwnd: int = 0        # 窗口录制时的窗口句柄
        self._window_rect: tuple = (0, 0, 0, 0)  # 窗口录制时的窗口区域

    def start_fullscreen(self) -> bool:
        """全屏录制"""
        self._mode = RecordMode.FULLSCREEN
        return self._start(region=None)

    def start_region(self, region: tuple) -> bool:
        """区域录制"""
        self._mode = RecordMode.REGION
        return self._start(region=region)

    def start_window(self, hwnd: int) -> bool:
        """窗口录制"""
        self._mode = RecordMode.WINDOW
        self._window_hwnd = hwnd
        rect = get_window_rect(hwnd)  # 获取窗口位置
        region = (rect.left, rect.top, rect.width, rect.height)
        return self._start(region=region)
```

### 3.2 音频集成

```python
class RecorderManager:
    def __init__(self, config, on_saved=None):
        ...
        self._audio_capturer: AudioCapturer = None
        self._audio_source: AudioSource = AudioSource.NONE

    def _start(self, region=None) -> bool:
        ...
        # 音频初始化
        audio_source = self._config.get("audio_source", "none")
        self._audio_source = AudioSource(audio_source)
        if self._audio_source != AudioSource.NONE:
            self._audio_capturer = AudioCapturer(self._audio_source)
            if not self._audio_capturer.start():
                logger.warning("音频捕获初始化失败，继续无声录制")
                self._audio_capturer = None

    def stop(self, cancel=False) -> str:
        ...
        # 音频停止
        audio_data = None
        if self._audio_capturer:
            audio_data = self._audio_capturer.stop()
            self._audio_capturer = None

        # 如果有音频数据，编码时混入
        self._audio_data = audio_data
```

### 3.3 编码循环更新

```python
def _encode_loop(self):
    """编码线程：视频编码 + 音频混入"""
    try:
        # 视频编码（与 v1.0 相同）
        encoder = VideoEncoder(self._output_path, self._fps, self._encode_size)
        with open(self._temp_file, "rb") as fh:
            for i in range(self._total_frames):
                # 读取帧 → 解压 → 缩放 → 写入
                ...
        encoder.close()

        # 音频混入
        if self._audio_data and self._audio_source != AudioSource.NONE:
            audio_temp = self._output_path + ".audio.wav"
            # 写入 WAV 临时文件
            self._write_wav(audio_temp, self._audio_data)
            # FFmpeg 混入音频
            final_output = self._output_path
            temp_video = self._output_path + ".video.mp4"
            os.rename(final_output, temp_video)
            self._mix_audio_video(temp_video, audio_temp, final_output)
            os.remove(temp_video)
            os.remove(audio_temp)

        self._on_saved(self._output_path)
    except Exception as e:
        ...
```

---

## 4. HotkeyManager 更新

### 4.1 新增快捷键

```python
# 注册新的快捷键
self._hotkey.register(shortcut_area, self._on_start_region)      # Ctrl+Shift+A
self._hotkey.register(shortcut_window, self._on_start_window)     # Ctrl+Shift+W
```

### 4.2 配置更新

```python
# config.py defaults 新增
"shortcut_area": "Ctrl+Shift+A",     # 区域录制
"shortcut_window": "Ctrl+Shift+W",    # 窗口录制
```

设置对话框新增两个快捷键录制控件：

```
开始快捷键:    [Ctrl+Shift+R] 🎹
停止快捷键:    [Ctrl+Shift+S] 🎹
暂停快捷键:    [Ctrl+Shift+P] 🎹
区域录制快捷键: [Ctrl+Shift+A] 🎹     ← 新增
窗口录制快捷键: [Ctrl+Shift+W] 🎹     ← 新增
```

---

## 5. TrayIcon 更新

### 5.1 动态菜单

v1.0 的托盘菜单是静态构建的。v1.1 需要根据录制状态动态切换菜单项。

```python
class TrayIcon:
    def _build_menu(self):
        """根据录制状态构建菜单"""
        if self._is_recording:
            items = [
                MenuItem("⏸ 暂停录制" if not self._is_paused else "▶ 继续录制", ...),
                MenuItem("⏹ 停止录制", ...),
            ]
        else:
            items = [
                MenuItem("▶ 全屏录制", ...),
                MenuItem("▢ 区域录制", ...),
                MenuItem("🖥 窗口录制", ...),
            ]
        items += [
            MenuItem("⚙ 设置", ...),
            MenuItem("📁 打开保存文件夹", ...),
            MenuItem("---", None, visible=False),
            MenuItem("✕ 退出", ...),
        ]
        self._icon.menu = pystray.Menu(*items)
        self._icon.update_menu()
```

### 5.2 通知增强

```python
def show_notification_with_action(self, title, msg, action_label, action_callback):
    """显示带操作按钮的 Toast 通知"""
    # 优先使用 winotify（Windows 10/11 Toast）
    # 备选 win10toast
    # 最终降级为 pystray.notify()
```

---

## 6. ConfigManager 更新

### 6.1 新增配置项

```python
defaults = {
    ...
    "audio_source": "none",       # none / system / microphone / both
    "shortcut_area": "Ctrl+Shift+A",    # 区域录制
    "shortcut_window": "Ctrl+Shift+W",  # 窗口录制
}
```

---

## 7. 新增依赖

| 库 | 版本 | 用途 |
|----|------|------|
| pyaudiowpatch | 0.2+ | WASAPI 音频捕获（系统声音环形缓冲区） |
| pyaudio | 0.2+ | 麦克风音频捕获 |
| winotify | 1.1+ | Windows 10/11 Toast 通知（带操作按钮） |
| ffmpeg-python | 0.2+ | FFmpeg Python 绑定（音视频混合） |

**FFmpeg 嵌入方案**：
- 将 `ffmpeg.exe` 打包到应用目录（约 15MB）
- 首次运行时从内置资源解压到临时目录
- 或由用户手动安装 FFmpeg 并添加到 PATH

**评估**：音频混入方案可能需要调整。如果 FFmpeg 体积过大，可考虑：
1. 仅输出无声 MP4（v1.0 方案），音频后处理
2. 使用 OpenCV 写入 AVI 容器 + 音频轨道
3. 使用 moviepy 库混合音视频

---

## 8. 项目架构更新

### 8.1 目录结构变化

```
QuickRec_dev/src/
├── main.py                      # 新增区域/窗口录制入口
├── config.py                    # 新增 audio_source, shortcut_area, shortcut_window
├── recorder/
│   ├── recorder_manager.py      # 新增 RecordMode, 音频集成
│   ├── screen_capturer.py       # 不变（区域捕获已支持）
│   ├── video_encoder.py         # 不变
│   └── audio_capturer.py        # 新增：音频捕获模块
├── ui/
│   ├── tray_icon.py             # 更新：动态菜单, 通知增强
│   ├── toolbar.py               # 更新：完成通知, 打开文件夹按钮
│   ├── area_selector.py          # 更新：Win11 兼容性修复, 确认对话框
│   ├── window_selector.py        # 新增：窗口选择器
│   └── settings_dialog.py        # 更新：音频源选择, 新增快捷键
├── hotkey/
│   └── hotkey_manager.py         # 不变
├── utils/
│   ├── file_namer.py            # 不变
│   ├── disk_checker.py           # 不变
│   └── window_utils.py          # 新增：Win32 窗口枚举工具
└── ffmpeg/                       # 新增：FFmpeg 二进制（可选）
    └── ffmpeg.exe
```

### 8.2 模块依赖关系更新

```
main.py
├── config.py
├── ui/tray_icon.py (动态菜单 + Toast 通知)
├── ui/toolbar.py (完成通知 + 打开文件夹)
├── ui/area_selector.py (Win11 修复)
├── ui/window_selector.py (新增：窗口选择器)
├── ui/settings_dialog.py (音频源 + 新快捷键)
├── hotkey/hotkey_manager.py
└── recorder/recorder_manager.py (录制模式 + 音频)
    ├── recorder/screen_capturer.py
    ├── recorder/video_encoder.py
    ├── recorder/audio_capturer.py (新增)
    ├── utils/file_namer.py
    ├── utils/disk_checker.py
    └── utils/window_utils.py (新增)
```

---

## 9. 主程序 main.py 更新

```python
class QuickRecApp:
    def __init__(self):
        ...
        # 新增快捷键
        self._setup_hotkeys()  # 包含区域和窗口录制快捷键

        # 新增回调
        self._tray = TrayIcon(
            config=self._config,
            callbacks={
                "start": self._on_start_fullscreen,      # 原 "start"
                "start_area": self._on_start_region,      # 新增
                "start_window": self._on_start_window,    # 新增
                "pause_resume": self._on_pause_resume,    # 新增（录制中暂停）
                "stop": self._on_stop_recording,           # 新增（录制中停止）
                "settings": self._show_settings,
                "exit": self._on_exit,
            }
        )

    def _on_start_region(self):
        """区域录制：显示区域选择器"""
        selector = AreaSelector()
        selector.region_selected.connect(self._on_region_selected)
        selector.cancelled.connect(self._on_selection_cancelled)
        selector.show_fullscreen()

    def _on_region_selected(self, x, y, w, h):
        """区域选择完成：开始录制"""
        if self._recorder.start_region(region=(x, y, w, h)):
            self._show_toolbar()

    def _on_start_window(self):
        """窗口录制：显示窗口选择器"""
        selector = WindowSelector()
        selector.window_selected.connect(self._on_window_selected)
        selector.cancelled.connect(self._on_selection_cancelled)
        selector.show()

    def _on_window_selected(self, x, y, w, h):
        """窗口选择完成：开始录制"""
        if self._recorder.start_region(region=(x, y, w, h)):
            self._show_toolbar()
```

---

## 10. 模块测试计划

| 模块 | 测试方式 | 关键用例 |
|-----|---------|---------|
| AreaSelector | 手动/UI | Win11 下可拖拽选区、ESC/右键取消、最小尺寸限制 |
| WindowSelector | 手动/UI | 窗口列表显示正确、点击选择、最小化窗口提示 |
| AudioCapturer | 单元测试 | 系统声音捕获、麦克风捕获、两者同时、静音设备处理 |
| RecorderManager | 集成测试 | 全屏/区域/窗口三种模式、音频同步、编码音视频混合 |
| TrayIcon | 手动测试 | 动态菜单切换、Toast 通知操作按钮 |
| SettingsDialog | 手动测试 | 音频源选择保存、新增快捷键录制 |
| FFmpeg 混入 | 集成测试 | 音视频时长一致、无声降级、FFmpeg 缺失时仅视频 |

---

## 11. 开发里程碑

| 阶段 | 时间 | 交付内容 |
|-----|------|---------|
| 区域录制 | 第 1-3 天 | 修复 Win11 兼容性，集成 AreaSelector，托盘菜单"区域录制" |
| 窗口录制 | 第 4-6 天 | 窗口枚举、窗口选择器 UI、窗口位置追踪录制 |
| 音频录制 | 第 7-10 天 | pyaudiowpatch 集成、音频捕获、FFmpeg 混音、设置对话框音频选项 |
| 通知增强 | 第 11-12 天 | Toast 通知、工具栏完成状态、打开文件夹按钮 |
| 测试修复 | 第 13-14 天 | 三种模式全面测试、音频同步测试、打包验证 |
| 打包发布 | 第 15 天 | v1.1 打包、更新文档 |

---

## 12. 风险与应对

| 风险 | 影响 | 应对 |
|-----|------|------|
| Win11 区域选择器仍然点击穿透 | 区域录制不可用 | 备选方案：使用 Win32 API 画选区覆盖层替代 Qt Widget |
| pyaudiowpatch 环境兼容性 | 部分设备音频捕获失败 | 捕获失败时自动降级为无声录制，不影响视频 |
| FFmpeg 打包体积 | 安装包从 ~50MB 增至 ~65MB | 可选：将 FFmpeg 作为外部依赖，用户按需安装 |
| 窗口位置追踪性能 | 每帧 GetWindowRect 增加开销 | 仅在窗口录制模式下每 10 帧检查一次位置 |
| Toast 通知兼容性 | Windows 7 不支持 Toast 通知 | 降级为 pystray.notify() 纯文本通知 |
| dxcam 区域捕获精度 | 窗口边框/阴影影响截图范围 | 使用 DWM API 获取窗口客户区矩形，排除阴影 |