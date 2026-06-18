# QuickRec v1.3 详细技术设计文档

> 版本: v1.3
> 创建时间: 2026-06-18
> 状态: 开发中
> 前置版本: v1.2（详见 Tec-design-v1.2.md）

---

## 1. 版本概述

### 1.1 v1.3 新增/变更功能清单

基于 PRD v1.3 需求，在 v1.2 基础上新增/变更以下功能：

| 编号 | 功能 | 说明 | PRD 编号 |
|-----|------|------|---------|
| E1 | H.264 实时编码 | 零拷贝管线：dxcam 帧直接通过 FFmpeg stdin pipe 编码 H.264 MP4；去除 JPEG 临时文件 + 后编码步骤；无音频时停止即完成 | E1 |
| N1 | 指定窗口录制 **（从延期恢复）** | 删除 v1.2 遗留注释代码，从零重写；简化窗口丢失处理（关闭→自停保存，最小化→暂停+托盘通知，无 QMessageBox） | F3 |
| N2 | 临时文件三层清理 | 会话目录隔离（%TEMP%/QuickRec/session_<pid>_<ts>/）；录制结束/atexit/启动扫描三层机制清理崩溃遗留 | R3 |
| N3 | 磁盘空间不足预警 | 开始录制前检查保存路径磁盘剩余空间；< 1GB 弹窗警告可选继续；< 200MB 阻断录制 | P9 |
| N4 | 打包体积优化 | PyInstaller spec 排除不需要的 Qt 插件/模块，UPX 压缩，目标从 ~334MB 降至 < 150MB | S5 |
| N5 | DPI 缩放适配 | QApplication 高 DPI 属性设置，修复 4K/150% 缩放下 UI 错位 | R1 |

**关键设计决策**：

1. 编码管线：**FFmpeg pipe 实时编码**，dxcam BGR24 帧直接通过 stdin 送 FFmpeg 编码 H.264（CRF 23, preset medium）；无音频时停止后文件 < 1 秒可用
2. 有音频时：**方案 1（后混合）**——视频仅 pipe 到 FFmpeg 编码（session_dir/video.mp4），音频单独录制 WAV，停止后 FFmpeg 二次转封装混合（-c:v copy -c:a aac，1-3 秒）
3. 窗口录制：**从零重写**（删除 v1.2 所有注释代码），窗口丢失处理简化为"关闭→自停保存，最小化→暂停+托盘通知"
4. 临时文件：**会话目录隔离**，录制中视频/音频临时文件统一在 %TEMP%/QuickRec/session_<pid>_<ts>/ 下管理
5. H.264 参数：**内部固定 CRF 23 + preset medium**，不暴露给用户；1080p/30fps 约 8MB/min
6. 磁盘预警：**仅录制前检查一次**，不持续轮询；< 1GB 预警可选继续，< 200MB 阻断

### 1.2 v1.3 不包含

- 多显示器录制（录制指定屏幕）→ v2.0+
- 录制历史管理窗口 → v2.0+
- 编码参数可配置（CRF/preset）→ 内部固定

---

## 2. 模块设计

### 2.1 H.264 实时编码模块 (video_encoder.py) — 重写

**职责**：将 OpenCV VideoWriter(mp4v) 替换为 FFmpeg subprocess pipe，实现 H.264 实时编码。外部接口（write_frame/close）保持不变，对 recorder_manager 透明。

**技术选型**：使用 `subprocess.Popen` 启动 FFmpeg 子进程，通过 `stdin=subprocess.PIPE` 写入原始 BGR24 帧数据。

```python
class VideoEncoder:
    """H.264 视频编码器（FFmpeg pipe）

    启动 FFmpeg 子进程，通过 stdin pipe 写入原始 BGR24 帧。
    FFmpeg 自动编码为 H.264 MP4 文件。

    参数：
        ffmpeg_path: FFmpeg 可执行文件路径
        output_path: 输出 MP4 文件路径
        fps: 帧率（影响 H.264 时间基）
        frame_size: (width, height) 帧尺寸，必须与写入帧一致
        crf: H.264 CRF 质量参数（默认 23）
        preset: H.264 编码预设（默认 "medium"）
    """

    - _output_path: str
    - _fps: int
    - _frame_size: tuple  # (width, height)
    - _proc: subprocess.Popen
    - _is_open: bool
    - _frame_count: int

    + __init__(output_path, fps, frame_size, ffmpeg_path, crf=23, preset="medium")
    + write_frame(frame: np.ndarray) -> bool  # BGR24 (H, W, 3) → pipe
    + close() -> bool                          # 关闭 pipe，等待 FFmpeg 退出
    + is_open() -> bool                       # pipe 是否可写入
```

**FFmpeg 命令构造**：

```python
def _build_cmd(self):
    return [
        self._ffmpeg_path, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{self._frame_size[0]}x{self._frame_size[1]}",  # WxH
        "-r", str(self._fps),                                   # 帧率
        "-pix_fmt", "bgr24",
        "-i", "pipe:0",                                         # stdin
        "-c:v", "libx264",
        "-crf", str(self._crf),                                 # 默认 23
        "-preset", self._preset,                                # 默认 medium
        "-pix_fmt", "yuv420p",                                 # 最大兼容
        self._output_path,
    ]
```

**FFmpeg 参数说明**：

| 参数 | 值 | 说明 |
|-----|-----|------|
| `-f rawvideo -vcodec rawvideo -pix_fmt bgr24` | 输入格式 | 从 stdin 接收 BGR24 原始帧 |
| `-s WxH` | 帧尺寸 | 必须与 write_frame 传入的 frame.shape 一致 |
| `-r FPS` | 帧率 | 影响 H.264 时间基和容器帧率 |
| `-c:v libx264` | 视频编码器 | H.264 软件编码 |
| `-crf 23` | 质量系数 | 0=无损，23=默认高质量，28=一般；1080p 约 8MB/min |
| `-preset medium` | 编码速度 | ultrafast 更快文件大，slow 更小文件慢 |
| `-pix_fmt yuv420p` | 输出像素格式 | 确保在所有播放器上正常显示 |

**write_frame 实现**：

```python
def write_frame(self, frame: np.ndarray) -> bool:
    """写入一帧 BGR24 数据到 FFmpeg stdin

    Args:
        frame: numpy ndarray, shape (H, W, 3), dtype uint8, BGR

    Returns:
        True 写成功，False pipe 已关闭
    """
    if not self._is_open:
        return False
    try:
        self._proc.stdin.write(frame.tobytes())
        self._frame_count += 1
        return True
    except (BrokenPipeError, OSError):
        self._is_open = False
        return False
```

**帧写入格式**：`frame.tobytes()` 将 numpy BGR24 数组以行优先（C-order）序列化为字节流：
```
B0 G0 R0 B1 G1 R1 ... B(W-1) G(W-1) R(W-1)  ← row 0
B0 G0 R0 ...                                   ← row 1
...
共 (H × W × 3) 字节
```

**close 实现**：

```python
def close(self) -> bool:
    """关闭 stdin pipe，等待 FFmpeg 退出

    1. 关闭 stdin（FFmpeg 收到 EOF，开始 flush 剩余帧）
    2. 等待进程退出（最多 30 秒超时）
    3. 检查 returncode

    Returns:
        True 编码成功（returncode == 0）
    """
    if not self._is_open:
        return True
    self._is_open = False
    try:
        self._proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    try:
        self._proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        self._proc.kill()
        self._proc.wait()
        return False
    return self._proc.returncode == 0
```

**错误处理**：

| 场景 | 处理方式 |
|-----|---------|
| FFmpeg 找不到（FileNotFoundError） | __init__ 抛出异常，调用方降级 |
| 进程中途退出（BrokenPipeError） | write_frame 返回 False，recorder_manager 停止录制 |
| close 超时（TimeoutExpired） | 强制 kill()，返回 False |
| __del__ 中进程仍在运行 | terminate()，忽略异常 |

---

### 2.2 临时文件管理模块 (temp_cleaner.py) — 新增

**职责**：管理录制会话目录的生命周期，提供三层清理机制防止临时文件泄漏。

**设计决策**：使用专用的会话目录（%TEMP%/QuickRec/session_<pid>_<ts>/）隔离每次录制的临时文件。通过 PID + atexit + 启动扫描三层保障。

**会话目录结构**：

```
%TEMP%/QuickRec/
└── session_<pid>_<timestamp>/
    ├── video.mp4            ← FFmpeg 视频输出（录制中持续写入）
    ├── audio_system.wav     ← 系统声音（如有）
    └── audio_mic.wav        ← 麦克风（如有）
```

```python
class TempCleaner:
    """临时文件清理器

    管理录制会话目录的生命周期：
    - 第一层：录制正常结束/取消时删除当次 session 目录
    - 第二层：程序正常退出时 atexit 钩子删除
    - 第三层：程序启动时扫描清理无活跃进程的遗留目录
    """

    BASE_DIR = os.path.join(tempfile.gettempdir(), "QuickRec")

    @classmethod
    def create_session_dir(cls) -> str:
        """创建当次录制会话目录

        命名规则: session_{os.getpid()}_{int(time.time())}
        创建目录，返回绝对路径。
        """

    @classmethod
    def cleanup_session(cls, session_dir: str):
        """删除会话目录（录制结束/取消时调用）

        使用 shutil.rmtree，忽略文件不存在的 OSError。
        """

    @classmethod
    def cleanup_stale(cls):
        """启动时扫描 %TEMP%/QuickRec/session_* 并清理遗留目录

        遍历所有 session_* 目录：
        1. 解析目录名中的 PID
        2. os.kill(pid, 0) 检查进程是否存在
        3. 进程不存在 → 删除该目录
        4. 当前进程 PID → 跳过（多实例保护）
        """

    @classmethod
    def register_atexit(cls, session_dir: str):
        """注册 atexit 钩子，程序正常退出时清理 session 目录

        使用 atexit.register(cleanup_session, session_dir)
        """
```

**进程存活检查（不引入新依赖）**：

```python
@classmethod
def _is_pid_alive(cls, pid: int) -> bool:
    """检查指定 PID 的进程是否仍存活

    Windows 上 os.kill(pid, 0) 等价于 OpenProcess + 检查，
    不发送信号，只检测进程存在性。
    """
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
```

**cleanup_stale 实现**：

```python
@classmethod
def cleanup_stale(cls):
    if not os.path.isdir(cls.BASE_DIR):
        return
    current_pid = os.getpid()
    for entry in os.listdir(cls.BASE_DIR):
        if not entry.startswith("session_"):
            continue
        try:
            # 解析 session_<pid>_<timestamp>
            parts = entry.split("_")
            pid = int(parts[1])
        except (IndexError, ValueError):
            continue
        if pid == current_pid:
            continue  # 当前进程，跳过
        if not cls._is_pid_alive(pid):
            session_dir = os.path.join(cls.BASE_DIR, entry)
            try:
                shutil.rmtree(session_dir)
                logger.info(f"已清理崩溃遗留目录: {session_dir}")
            except OSError:
                pass
```

**三层清理时序**：

```
录制开始：
  session_dir = TempCleaner.create_session_dir()
  TempCleaner.register_atexit(session_dir)

录制正常结束/取消：
  TempCleaner.cleanup_session(session_dir)     → 第一层
  atexit.unregister(...)                       → 取消 atexit 钩子

程序异常退出（未走到 atexit）：
  [下次启动时] TempCleaner.cleanup_stale()     → 第三层（兜底）

程序正常退出：
  atexit 钩子触发 → cleanup_session()          → 第二层
```

---

### 2.3 录制管线重构 (recorder_manager.py) — 重构

**职责**：重构录制循环——去除 JPEG 临时文件方案，改为 FFmpeg pipe 实时编码；接入 TempCleaner 会话目录管理；取消注释窗口录制模式（RecordMode.WINDOW）。

**v1.2 → v1.3 变更总览**：

| 变更 | v1.2（旧） | v1.3（新） |
|-----|-----------|-----------|
| 视频编码 | JPEG 压缩 → 写 .tmp → 停止后 cv2 VideoWriter(mp4v) | 原始帧 → FFmpeg stdin pipe → H.264 (libx264) |
| 临时文件 | .tmp 文件在输出目录同级 | TempCleaner 会话目录 |
| 停止后等待 | 解码 JPEG + 编码 mp4v（数秒到数十秒） | 无音频：< 1秒；有音频：1-3秒（音频后混合） |
| 窗口录制 | 代码全部注释，延期 | 恢复并重写（RecordMode.WINDOW, start_window, 窗口跟踪） |

**操作变更总结**：

| 删除方法/字段 | 新增方法/字段 |
|-------------|-------------|
| `_JPEG_QUALITY`, `_JPEG_PARAMS` | `_session_dir: str` |
| `_temp_file`, `_temp_file_handle` | `_video_temp_path: str` |
| `_total_frames` | `_finalize_thread: threading.Thread` |
| `_compress_frame()` | `_finalize()` |
| `_encode_loop()` | `stop_window()` (恢复) |
| `_cleanup_temp_file()` | `_get_window_rect()` (恢复) |
| | `_get_window_title()` (恢复) |

**RecordMode 恢复**：

```python
class RecordMode(Enum):
    """录制模式枚举"""
    FULLSCREEN = "fullscreen"   # 全屏录制
    REGION = "region"           # 区域录制（v1.1）
    WINDOW = "window"           # 指定窗口录制（v1.3 恢复）
```

**RecorderManager 新增/变更字段**：

```python
class RecorderManager:
    # --- v1.1/v1.2 保留 ---
    - _state: RecorderState
    - _mode: RecordMode
    - _capturer: ScreenCapturer
    - _record_thread: threading.Thread
    - _stop_event: threading.Event
    - _resume_event: threading.Event
    - _output_path: str
    - _fps: int
    - _frame_size: tuple
    - _encode_size: tuple
    - _audio_capturer: AudioCapturer
    - _ffmpeg_path: str
    - _on_saved: callable

    # --- v1.3 新增（替换旧字段）---
    - _session_dir: str              # TempCleaner 会话目录
    - _video_temp_path: str          # session_dir/video.mp4
    - _encoder: VideoEncoder         # FFmpeg pipe 编码器

    # --- v1.3 恢复（从 v1.2 注释恢复）---
    - _window_hwnd: int              # 窗口录制目标句柄
    - _window_title: str             # 窗口标题
    - _window_lost_bridge: _WindowLostBridge  # 窗口丢失信号桥
```

**_start() 方法变更**：

```python
def _start(self, region=None, hwnd=None) -> bool:
    """内部启动录制（v1.3 重构：去除 JPEG 临时文件，接入 TempCleaner）

    变更点：
    1. 不再创建 .tmp 文件
    2. 创建 session 目录（TempCleaner）
    3. 音频 WAV 改写到 session_dir
    4. VideoEncoder 在录制线程中初始化
    """
    with self._lock:
        if self._state != RecorderState.IDLE:
            return False

        # 录制模式判断
        self._mode = RecordMode.FULLSCREEN
        if region:
            self._mode = RecordMode.REGION
        elif hwnd:                                      # v1.3 恢复
            self._mode = RecordMode.WINDOW
            self._window_hwnd = hwnd
            rect = self._get_window_rect(hwnd)
            region = (rect.left(), rect.top(), rect.width(), rect.height())

        # v1.3: 创建 session 目录（替代旧 .tmp 文件）
        self._session_dir = TempCleaner.create_session_dir()
        TempCleaner.register_atexit(self._session_dir)
        self._video_temp_path = os.path.join(self._session_dir, "video.mp4")

        # 创建捕获器（不变）
        self._capturer = ScreenCapturer(region=region)
        self._frame_size = self._capturer.get_monitor_size()
        self._encode_size = self._get_target_size() or self._frame_size
        self._fps = self._config.get("fps", 30)
        self._output_path = FileNamer.generate(save_path)

        # v1.1: 音频初始化（v1.3: 音频 WAV 写到 session_dir）
        audio_source_str = self._config.get("audio_source", "none")
        if audio_source_str != AudioSource.NONE:
            self._audio_capturer = AudioCapturer(
                source=audio_source_str,
                output_dir=self._session_dir,  # 改写到 session_dir
            )
            self._audio_capturer.start(output_stem="audio")

        # 启动录制线程
        self._record_thread = threading.Thread(
            target=self._record_loop, daemon=True
        )
        self._record_thread.start()
        return True
```

**_record_loop() 方法变更**：

```python
def _record_loop(self):
    """录制线程主循环（v1.3 重构：FFmpeg pipe 替代 JPEG）

    变更点：
    1. 录制循环开头初始化 VideoEncoder（FFmpeg pipe）
    2. 不再调用 _compress_frame()，直接写原始帧到 pipe
    3. BGR24 帧在写入 pipe 前做画质缩放（cv2.resize）
    4. 窗口模式下每 200ms 更新捕获区域
    5. 录制结束 close() encoder（替代 flush temp file）
    """
    # 1. 启动 dxcam（不变）
    self._capturer.start()

    # 2. 初始化 VideoEncoder（FFmpeg pipe，替代 .tmp 文件）
    self._encoder = VideoEncoder(
        output_path=self._video_temp_path,
        fps=self._fps,
        frame_size=self._encode_size,
        ffmpeg_path=self._ffmpeg_path,
    )

    # 3. 录制循环
    fps = self._fps
    frame_interval = 1.0 / fps
    rec_start = time.time()
    frames_written = 0
    was_paused = False
    last_window_update = 0  # v1.3: 窗口位置更新时间戳

    while not self._stop_event.is_set():
        # 暂停等待（不变）
        if not self._resume_event.wait(timeout=0.1):
            if self._stop_event.is_set(): break
            was_paused = True
            continue

        if was_paused:
            rec_start = time.time() - frames_written * frame_interval
            was_paused = False

        # v1.3: 窗口模式下定期更新捕获区域
        if self._mode == RecordMode.WINDOW and self._window_hwnd:
            now = time.time()
            if now - last_window_update >= 0.2:
                rect = self._get_window_rect(self._window_hwnd)
                if rect is None:
                    # 窗口丢失 → 停止录制
                    user32 = ctypes.windll.user32
                    reason = "closed" if not user32.IsWindow(self._window_hwnd) else "minimized"
                    self._encoder.close()
                    self._window_lost_bridge.window_lost.emit(reason)
                    break
                self._capturer.update_region(
                    (rect.left(), rect.top(), rect.width(), rect.height())
                )
                last_window_update = now

        # 捕获帧
        frame = self._capturer.capture_frame()
        if frame is None:
            if not self._capturer._started:
                break
            continue

        # v1.3: 画质缩放在写 pipe 前（不再等到编码阶段）
        if self._encode_size != self._frame_size:
            frame = cv2.resize(frame, self._encode_size, interpolation=cv2.INTER_LINEAR)

        # 补齐跳过的帧
        target_frame = int((time.time() - rec_start) / frame_interval)
        while frames_written < target_frame:
            if not self._encoder.write_frame(frame):
                break
            frames_written += 1

        # 写入当前帧到 FFmpeg pipe
        if not self._encoder.write_frame(frame):
            break
        frames_written += 1

        # 帧率控制（不变）
        next_time = rec_start + frames_written * frame_interval
        wait = next_time - time.time()
        if wait > 0.002:
            time.sleep(max(wait - 0.001, 0.001))

    # 4. 关闭编码器（替代 flush tmp file + 释放 dxcam）
    self._encoder.close()
    self._encoder = None
    if self._capturer:
        self._capturer.close()
        self._capturer = None
```

**_stop_and_encode() → _finalize() 变更**：

```python
def _stop_and_encode(self):
    """后台线程：等待录制结束，启动最终化"""
    if self._record_thread and self._record_thread.is_alive():
        self._record_thread.join(timeout=5.0)

    # 停止音频
    self._audio_temp_paths = []
    if self._audio_capturer:
        paths = self._audio_capturer.stop()
        self._audio_temp_paths = [p for p in paths if os.path.exists(p)]

    # 取消：删除 session_dir
    if self._cancelled:
        TempCleaner.cleanup_session(self._session_dir)
        self._state = RecorderState.IDLE
        return

    # 保存：启动最终化线程
    self._state = RecorderState.SAVING
    self._finalize_thread = threading.Thread(target=self._finalize, daemon=True)
    self._finalize_thread.start()

def _finalize(self):
    """后台线程：音频混合 → 移动文件到最终路径 → 清理 session_dir

    步骤：
    1. 如果有音频 → FFmpeg 转封装混合（音频 AAC + 视频 copy）
    2. 移动 session_dir/video.mp4（或混合后的文件）到最终输出路径
    3. 删除 session_dir
    4. 通知主线程编码完成
    """
    try:
        result_path = self._video_temp_path

        if self._audio_temp_paths:
            mixed = self._mix_audio_if_available()
            if mixed:
                result_path = mixed

        # 移动到最终路径
        shutil.move(result_path, self._output_path)
        result_path = self._output_path
    except Exception as e:
        logger.error(f"最终化失败: {e}")
        result_path = ""
    finally:
        TempCleaner.cleanup_session(self._session_dir)
        self._state = RecorderState.IDLE
        if self._on_saved:
            self._on_saved(result_path)
```

**_mix_audio_if_available() 适配**：

```python
def _mix_audio_if_available(self) -> str:
    """将音频混入视频（v1.3 适配：输入在 session_dir）

    与 v1.2 逻辑相同，仅源路径从 self._output_path 改为 self._video_temp_path。
    混合后的文件写回 session_dir/mixed.mp4。
    """
    if not self._audio_temp_paths or not self._ffmpeg_path:
        return ""
    temp_video = self._video_temp_path  # session_dir/video.mp4
    mixed_output = os.path.join(self._session_dir, "mixed.mp4")

    cmd = [self._ffmpeg_path, "-y", "-i", temp_video]
    for audio_path in self._audio_temp_paths:
        cmd.extend(["-i", audio_path])

    if len(self._audio_temp_paths) == 1:
        cmd.extend(["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                     mixed_output])
    elif len(self._audio_temp_paths) == 2:
        cmd.extend(["-filter_complex", "[1:a][2:a]amerge=inputs=2[a]",
                     "-map", "0:v", "-map", "[a]",
                     "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                     mixed_output])

    subprocess.run(cmd, check=True, timeout=120,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return mixed_output
```

**窗口录制恢复（从 v1.2 注释恢复并修正）**：

```python
class _WindowLostBridge(QObject):
    """窗口丢失信号桥（录制线程 → Qt 主线程）"""
    window_lost = pyqtSignal(str)  # "closed" / "minimized"

def start_window(self, hwnd: int) -> bool:
    """开始窗口录制（v1.3 恢复）"""
    if not ctypes.windll.user32.IsWindow(hwnd):
        return False
    self._window_title = self._get_window_title(hwnd)
    return self._start(hwnd=hwnd)

@staticmethod
def _get_window_rect(hwnd: int):
    """获取窗口客户区屏幕位置和尺寸

    使用 GetClientRect + ClientToScreen 获取不含边框阴影的客户区坐标。
    与 v1.2 GetWindowRect 不同，不会返回最大化窗口的负坐标。

    Returns:
        QRect 或 None（窗口无效/不可见/最小化时）
    """
    import ctypes
    import ctypes.wintypes  # 必须显式导入

    user32 = ctypes.windll.user32
    if not user32.IsWindow(hwnd):
        return None
    if not user32.IsWindowVisible(hwnd):
        return None
    if user32.IsIconic(hwnd):
        return None  # 最小化时由录制循环检测并 emit window_lost

    client_rect = ctypes.wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(client_rect))
    width = client_rect.right
    height = client_rect.bottom
    if width < 10 or height < 10:
        return None

    point = ctypes.wintypes.POINT()
    point.x = client_rect.left
    point.y = client_rect.top
    user32.ClientToScreen(hwnd, ctypes.byref(point))

    from PyQt5.QtCore import QRect
    return QRect(point.x, point.y, width, height)

@staticmethod
def _get_window_title(hwnd: int) -> str:
    """获取窗口标题"""
    title_length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if title_length == 0:
        return ""
    title = ctypes.create_unicode_buffer(title_length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, title, title_length + 1)
    return title.value
```

---

### 2.4 窗口选择器模块 (window_selector.py) — 重写

**职责**：**删除** v1.2 所有注释代码，从零重写。枚举当前可见窗口列表，过滤系统窗口，让用户选择录制目标。

**v1.2 已知问题（全部修复）**：

| 问题 | 根因 | v1.3 修复 |
|-----|------|---------|
| ctypes.wintypes 未导入 → 0xC0000409 崩溃 | WNDENUMPROC 回调中 `ctypes.wintypes.RECT()` 属性查找失败 | 顶部 `import ctypes.wintypes` |
| UWP 窗口被过滤掉 | `ApplicationFrameWindow` 在黑名单中 | 从黑名单移除 |
| 系统控件出现在列表中 | 窗口类名黑名单不完整 | 扩充黑名单 |

```python
class WindowSelector(QDialog):
    """窗口选择对话框

    枚举当前所有可见窗口，用户选择一个后通过 window_selected 信号返回窗口句柄。
    """

    window_selected = pyqtSignal(int, str)   # (hwnd, title)
    cancelled = pyqtSignal()                 # 用户取消或关闭对话框

    - _windows: list[tuple[int, str, bool]]  # (hwnd, title, is_minimized)
    - _list_widget: QListWidget
    - _btn_refresh: QPushButton
    - _btn_select: QPushButton
    - _btn_cancel: QPushButton

    + __init__(parent=None)
    + refresh_windows()          # 重新枚举窗口列表
    - _enum_windows() -> list    # Win32 API 枚举
    - _on_item_double_clicked()  # 双击选择
    - _on_select_clicked()       # 确定按钮
```

**对话框 UI**：

```
┌─ 选择录制窗口 ────────────────────────┐
│ [刷新]                                │
│ ┌──────────────────────────────────┐  │
│ │ Chrome - 标签页标题               │  │
│ │ 记事本 - 无标题                   │  │
│ │ 计算器（最小化）                  │  │
│ └──────────────────────────────────┘  │
│            [选择]  [取消]             │
└──────────────────────────────────────┘
```

- 双击列表项 = 点击"选择"
- 对话框右上角 X = cancelled

**窗口枚举过滤策略**（_enum_windows 实现）：

```python
@staticmethod
def _enum_windows() -> list[tuple[int, str, bool]]:
    """枚举所有可见窗口

    过滤规则（全部满足才保留）：
    1. IsWindow(hwnd) 为 True
    2. IsWindowVisible(hwnd) 为 True
    3. GetWindowTextLength(hwnd) > 0
    4. 不含 WS_EX_TOOLWINDOW 扩展样式（工具窗口，无任务栏图标）
    5. 窗口类名不在黑名单中
    6. 不是 QuickRec 自身窗口（通过窗口属性判断）

    Returns:
        [(hwnd, title, is_minimized), ...]
    """
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    results = []

    def enum_callback(hwnd, lparam):
        try:
            # 1. 基本有效性
            if not user32.IsWindow(hwnd):
                return True
            if not user32.IsWindowVisible(hwnd):
                return True
            # 2. 标题非空
            title_len = user32.GetWindowTextLengthW(hwnd)
            if title_len == 0:
                return True
            title = ctypes.create_unicode_buffer(title_len + 1)
            user32.GetWindowTextW(hwnd, title, title_len + 1)
            # 3. 排除工具窗口
            ex_style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            if ex_style & 0x00000080:  # WS_EX_TOOLWINDOW
                return True
            # 4. 类名黑名单
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            if class_name.value in cls._SYSTEM_CLASSES:
                return True
            # 5. 排除自身
            # (通过窗口属性 {QUICKREC} 标记判断)
            if not lparam:
                results.append((hwnd, title.value, bool(user32.IsIconic(hwnd))))
        except Exception:
            pass  # 单窗口失败不影响整体枚举
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return results
```

**系统窗口类名黑名单**：

```python
_SYSTEM_CLASSES = {
    "Shell_TrayWnd",            # 任务栏
    "Progman",                  # 桌面
    "WorkerW",                  # 桌面辅助
    "DV2ControlHost",           # 开始菜单
    "MsgrIMEWindowClass",       # 输入法浮窗
    "SysShadow",                # 菜单投影
    "Button",                    # 按钮
    "ComboBox",                 # 下拉框
    "Edit",                     # 编辑框
    "Static",                   # 静态文本
    "tooltips_class32",         # 提示框
    "Windows.UI.Core.CoreWindow", # UWP 核心窗口（通常无标题）
}
```

**选中最小化窗口时的恢复操作**：

```python
def _on_select_clicked(self):
    item = self._list_widget.currentItem()
    if not item: return
    hwnd, title, is_minimized = item.data(Qt.UserRole)
    if is_minimized:
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)       # SW_RESTORE
        time.sleep(0.1)                  # 等待恢复动画
        user32.SetForegroundWindow(hwnd)
    self.window_selected.emit(hwnd, title)
    self.accept()
```

---

### 2.5 窗口边框高亮模块 (window_highlighter.py) — 重写

**职责**：**删除** v1.2 所有注释代码，从零重写。在目标窗口周围绘制绿色虚线边框，每 100ms 更新位置跟随窗口移动。

**v1.2 已知问题（全部修复）**：

| 问题 | 根因 | v1.3 修复 |
|-----|------|---------|
| WA_TransparentForMouseInput 不存在 | 属性名拼写错误 | 改为 `Qt.WA_TransparentForMouseEvents` |
| ctypes.wintypes 未导入 → 崩溃 | 同 window_selector | `import ctypes.wintypes` |
| 目标窗口关闭后崩溃 | GetWindowRect 返回全零未处理 | 检查返回值，失败则 hide_highlight() |

```python
class WindowHighlighter(QWidget):
    """录制窗口边框高亮指示器

    在目标窗口四周绘制绿色虚线边框，通过 100ms QTimer 跟踪窗口位置。
    仅作为屏幕叠加层可见，不渲染到视频帧。
    """

    - _hwnd: int                    # 目标窗口句柄
    - _timer: QTimer                # 位置更新定时器（100ms）

    + __init__(hwnd: int, parent=None)
    + show_highlight()              # 显示边框，启动定时器
    + hide_highlight()              # 隐藏边框，停止定时器
    + hwnd: int                     # 属性：返回 _hwnd
    - _update_position()            # GetWindowRect 更新 geometry
    - paintEvent(event)             # 绘制绿色虚线边框
```

**窗口标志与属性设置**：

```python
def __init__(self, hwnd: int, parent=None):
    super().__init__(parent)

    # 窗口标志
    self.setWindowFlags(
        Qt.FramelessWindowHint |
        Qt.WindowStaysOnTopHint |
        Qt.Tool |
        Qt.WindowTransparentForInput  # 鼠标穿透（窗口标志）
    )

    # Widget 属性
    self.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # 注意：Events 非 Input
    self.setAttribute(Qt.WA_NoSystemBackground, True)
    self.setAttribute(Qt.WA_TranslucentBackground, True)

    self._hwnd = hwnd
    self._timer = QTimer(self)
    self._timer.setInterval(100)
    self._timer.timeout.connect(self._update_position)

    self._update_position()
```

**边框绘制**：

```python
def paintEvent(self, event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#00e676"), 2, Qt.DashLine)  # 亮绿色虚线 2px
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)                    # 透明填充
    painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
    painter.end()
```

**位置更新与窗口关闭保护**：

```python
def _update_position(self):
    import ctypes
    import ctypes.wintypes

    rect = ctypes.wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(self._hwnd, ctypes.byref(rect)):
        # GetWindowRect 失败 → 目标窗口已关闭
        self.hide_highlight()
        return

    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return

    self.setGeometry(rect.left, rect.top, w, h)
```

---

### 2.6 磁盘空间预警模块 (disk_checker.py) — 扩展

**职责**：在现有 `DiskChecker` 基础上新增预警/阻断阈值常量和 `check_before_recording()` 函数。新增 `show_disk_warning()` Qt 对话框函数（写入 `src/utils/disk_warning_dialog.py`）。

**新增常量**：

```python
# v1.3 新增
WARN_THRESHOLD_MB = 1024    # 1GB（1024MB），低于此值弹窗告知
BLOCK_THRESHOLD_MB = 200    # 200MB，低于此值拒绝录制
```

**新增函数**：

```python
@staticmethod
def check_before_recording(save_path: str) -> tuple[str, int]:
    """开始录制前检查磁盘空间

    Args:
        save_path: 保存路径（文件或目录）

    Returns:
        ("ok", free_mb): 空间充足（>= 1GB），可以开始录制
        ("warn", free_mb): 空间不足（200MB ~ 1GB），建议提醒
        ("block", free_mb): 空间严重不足（< 200MB），应阻断录制
    """
    free_bytes = DiskChecker.get_free_space(save_path)
    free_mb = free_bytes // (1024 * 1024)

    if free_mb < BLOCK_THRESHOLD_MB:
        return ("block", free_mb)
    elif free_mb < WARN_THRESHOLD_MB:
        return ("warn", free_mb)
    else:
        return ("ok", free_mb)
```

**预警对话框（src/utils/disk_warning_dialog.py 或内联函数）**：

```python
def show_disk_warning(free_mb: int, block: bool, parent=None) -> bool:
    """显示磁盘空间不足对话框

    Args:
        free_mb: 剩余空间（MB）
        block: True=阻断对话框（仅确定），False=预警对话框（继续/取消）
        parent: 父窗口（托盘应用中可为 None）

    Returns:
        True=用户选择继续（block=True 时恒返回 False）
    """
    if block:
        QMessageBox.critical(
            parent, "QuickRec",
            f"磁盘剩余空间严重不足（剩余 {free_mb} MB），无法开始录制。\n"
            f"请清理磁盘后重试。"
        )
        return False
    else:
        reply = QMessageBox.warning(
            parent, "QuickRec",
            f"磁盘剩余空间不足（剩余 {free_mb} MB），录制可能中断。\n"
            f"是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes
```

**调用方式（main.py 中三种录制入口共用）**：

```python
def _check_disk_space(self) -> bool:
    """录制前磁盘空间检查。返回 True 表示可以继续。"""
    save_path = self._config.get("save_path")
    status, free_mb = DiskChecker.check_before_recording(save_path)
    if status == "block":
        show_disk_warning(free_mb, block=True)
        return False
    elif status == "warn":
        return show_disk_warning(free_mb, block=False)
    return True
```

---

### 2.7 主程序入口 (main.py) — 窗口录制恢复 + DPI

**职责**：取消注释 v1.2 窗口录制相关代码，简化窗口丢失处理（用托盘通知替代 QMessageBox）；新增 DPI 适配设置。

**恢复的信号桥（从 v1.2 注释恢复）**：

```python
class _HotkeyBridge(QObject):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    area_requested = pyqtSignal()
    window_requested = pyqtSignal()  # v1.3: 从注释恢复

class _WindowBridge(QObject):
    """窗口选择器信号桥"""
    window_selected = pyqtSignal(int, str)   # (hwnd, title)
    cancelled = pyqtSignal()

class _WindowLostBridge(QObject):
    """窗口丢失信号桥（录制线程 → Qt 主线程）"""
    window_lost = pyqtSignal(str)            # "closed" / "minimized"
```

**QuickRecApp 恢复的字段和方法**：

```python
class QuickRecApp:
    # --- v1.3 恢复（从 v1.2 注释恢复）---
    - _window_highlighter: WindowHighlighter | None
    - _window_selector: WindowSelector | None     # 实例属性防 GC

    def _on_start_window(self):
        """窗口录制入口：显示窗口选择器"""
        if self._recorder.get_state() != RecorderState.IDLE:
            return
        if self._toolbar and self._toolbar.is_countdown_mode():
            self._toolbar.cancel_countdown()
            self._hide_toolbar()
            self._hotkey.set_esc_callback(None)
            return

        self._window_selector = WindowSelector()
        self._window_selector.window_selected.connect(
            lambda hwnd, title: self._window_bridge.window_selected.emit(hwnd, title)
        )
        self._window_selector.cancelled.connect(self._window_bridge.cancelled.emit)
        self._window_selector.exec_()

    def _on_window_selected(self, hwnd, title):
        """窗口选择完成：创建高亮、开始录制"""
        self._window_selector = None

        # 提至前台
        user32 = ctypes.windll.user32
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
            time.sleep(0.2)
        user32.SetForegroundWindow(hwnd)

        # 边框高亮
        self._window_highlighter = WindowHighlighter(hwnd)
        self._window_highlighter.show_highlight()

        # 开始录制
        if self._config.get("show_countdown", False):
            self._show_toolbar()
            self._toolbar.start_countdown(self._config.get("countdown_seconds", 3))
            self._toolbar.countdown_finished.connect(
                lambda: self._do_start_window(hwnd)
            )
            self._hotkey.set_esc_callback(self._on_countdown_esc)
        else:
            self._show_toolbar()
            self._do_start_window(hwnd)

    def _do_start_window(self, hwnd):
        """窗口录制实际启动"""
        self._hotkey.set_esc_callback(None)
        if self._toolbar:
            self._toolbar.start_recording_timer()
        if not self._recorder.start_window(hwnd):
            logger.error("窗口录制启动失败")
            self._hide_toolbar()
            return
        self._tray.set_recording_state(True)
        self._update_highlight_state()
```

**窗口丢失处理（v1.3 简化版：托盘通知替代 QMessageBox）**：

```python
def _on_window_lost(self, reason: str):
    """录制窗口丢失：简化处理，不弹 QMessageBox

    v1.2 使用 QMessageBox，在托盘应用中不可靠（可能被系统隐藏）。
    v1.3 改为托盘通知 + 自动处理：
    - closed → 自动停止并保存，托盘通知"录制窗口已关闭，视频已保存"
    - minimized → 自动暂停，托盘通知"录制窗口已最小化，录制已暂停"
    """
    # 停止窗口高亮
    if self._window_highlighter:
        self._window_highlighter.hide_highlight()
        self._window_highlighter = None

    if reason == "closed":
        self._tray.show_notification("录制窗口已关闭，视频已保存")
        self._on_stop_recording()
    elif reason == "minimized":
        self._recorder.pause()
        if self._toolbar:
            self._toolbar.set_paused(True)
        self._tray.set_recording_state(True, paused=True)
        self._tray.show_notification("录制窗口已最小化，录制已暂停。恢复窗口后点击工具栏\"继续\"按钮继续录制。")
```

**工具栏结果条勾子**（集成需求，每次录制开始时初始化录制模式按钮的勾子）：

在 `_show_toolbar()` 方法中，录制工具栏**显示录制模式按钮（暂停、停止、取消）**，结果条按钮初始隐藏，录制完成由 `show_result()` 切换。

**快捷键注册恢复**：

```python
def _setup_hotkeys(self):
    # v1.0/v1.1/v1.2 保留不变
    shortcut_start = self._config.get("shortcut_start", "Ctrl+Shift+R")
    shortcut_stop = self._config.get("shortcut_stop", "Ctrl+Shift+S")
    shortcut_pause = self._config.get("shortcut_pause", "Ctrl+Shift+P")
    shortcut_area = self._config.get("shortcut_area", "Ctrl+Shift+A")

    self._hotkey.register(shortcut_start, self._hotkey_bridge.start_requested.emit)
    self._hotkey.register(shortcut_stop, self._hotkey_bridge.stop_requested.emit)
    self._hotkey.register(shortcut_pause, self._hotkey_bridge.pause_requested.emit)
    self._hotkey.register(shortcut_area, self._hotkey_bridge.area_requested.emit)

    # v1.3: 从注释恢复
    shortcut_window = self._config.get("shortcut_window", "Ctrl+Shift+W")
    self._hotkey.register(shortcut_window, self._hotkey_bridge.window_requested.emit)
```

**信号桥连接（v1.3 恢复）**：

```python
# 窗口选择器信号桥
self._window_bridge = _WindowBridge()
self._window_bridge.window_selected.connect(self._on_window_selected)
self._window_bridge.cancelled.connect(self._on_window_cancelled)

# 窗口丢失信号桥
self._window_lost_bridge = _WindowLostBridge()
self._window_lost_bridge.window_lost.connect(self._on_window_lost)
self._recorder._window_lost_bridge.window_lost.connect(
    self._window_lost_bridge.window_lost.emit
)
```

**DPI 适配（v1.3 新增）**：

```python
# 在 main() 函数中 QApplication 创建之前：
def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)       # v1.3 新增
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)         # v1.3 新增
    app = QuickRecApp()
    sys.exit(app.run())
```

> **注意**：这两行必须在 `QApplication(sys.argv)` 之前调用。Qt6 默认启用，PyQt5 需要手动设置。

---

### 2.8 托盘菜单模块 (tray_icon.py) — 小改

**职责**：取消注释 v1.2 遗留的窗口录制菜单项和信号。

**`_build_idle_menu()` 恢复**：

```python
def _build_idle_menu(self):
    return pystray.Menu(
        pystray.MenuItem("▶ 全屏录制", self._on_start_fullscreen),
        pystray.MenuItem("▢ 区域录制", self._on_start_region),
        pystray.MenuItem("🖥 窗口录制", self._on_start_window),  # v1.3 恢复
        pystray.MenuItem("⚙ 设置", self._on_settings),
        pystray.MenuItem("📁 打开保存文件夹", self._on_open_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("✕ 退出", self._on_exit),
    )
```

**`_SignalBridge` 新增信号**：

```python
class _SignalBridge(QObject):
    # v1.1/v1.2 保留
    start_fullscreen_requested = pyqtSignal()
    start_region_requested = pyqtSignal()
    pause_resume_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    # v1.3 恢复
    start_window_requested = pyqtSignal()
```

**回调映射扩展**：

```python
self._bridge.start_window_requested.connect(self._handle_start_window)

def _handle_start_window(self):
    if "start_window" in self._callbacks:
        self._callbacks["start_window"]()
```

---

### 2.9 设置对话框模块 (settings_dialog.py) — 小改

**职责**：取消注释 v1.2 遗留的窗口录制快捷键设置行。

**恢复的控件**（取消注释）：

```python
# 布局中恢复此行（取消注释）：
self._shortcut_window = _ShortcutRecorder("Ctrl+Shift+W")
self._shortcut_window.shortcut_changed.connect(
    lambda s: self._shortcut_window.setText(s)
)
form.addRow("窗口录制:", self._shortcut_window)
```

**`_load_config()` / `_save_config()` 恢复**：

```python
# _load_config:
self._shortcut_window.setText(
    str(self._config.get("shortcut_window", "Ctrl+Shift+W"))
)

# _save_config:
self._config.set("shortcut_window", self._shortcut_window.text())
```

---

### 2.10 打包体积优化 (build_std.spec) — 优化

**当前体积分析**：

| 组件 | 估算大小 | 优化措施 |
|-----|---------|---------|
| Python 运行时 | ~30MB | 不变 |
| Qt5 核心 DLL | ~80MB | 排除不用的 Qt 插件 |
| 不用的 Qt 插件 | ~50MB | **排除** Bluetooth, WebEngine, 3D, Qml, Sql 等 |
| OpenCV | ~120MB | v1.3 不再用 cv2 编码视频，仅缩放 |
| FFmpeg | ~95MB | 不变（必须） |
| 其他依赖 | ~20MB | 不变 |

**build_std.spec 排除项**：

```python
a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('ffmpeg/ffmpeg.exe', 'ffmpeg'),
    ],
    hiddenimports=[...],  # 不变
    excludes=[
        # Qt 不需要的模块
        'Qt5Bluetooth', 'Qt5Bluetooth.dll',
        'Qt5Designer', 'Qt5Designer.dll',
        'Qt5Help', 'Qt5Help.dll',
        'Qt5Location', 'Qt5Location.dll',
        'Qt5Multimedia', 'Qt5Multimedia.dll',
        'Qt5MultimediaWidgets', 'Qt5MultimediaWidgets.dll',
        'Qt5Qml', 'Qt5Qml.dll',
        'Qt5Quick', 'Qt5Quick.dll',
        'Qt5QuickWidgets', 'Qt5QuickWidgets.dll',
        'Qt5Sensors', 'Qt5Sensors.dll',
        'Qt5SerialPort', 'Qt5SerialPort.dll',
        'Qt5Sql', 'Qt5Sql.dll',
        'Qt5Svg', 'Qt5Svg.dll',
        'Qt5Test', 'Qt5Test.dll',
        'Qt5WebChannel', 'Qt5WebChannel.dll',
        'Qt5WebEngine', 'Qt5WebEngine.dll',
        'Qt5WebEngineCore', 'Qt5WebEngineCore.dll',
        'Qt5WebEngineWidgets', 'Qt5WebEngineWidgets.dll',
        'Qt5WebSockets', 'Qt5WebSockets.dll',
        'Qt5Xml', 'Qt5Xml.dll',
        # OpenCV 不需要的组件
        'cv2.cv2',  # 保留 cv2 本身
    ],
)
```

**最终检查**（保留的 Qt 模块）：
- `Qt5Core` — Qt 核心
- `Qt5Gui` — 图形系统
- `Qt5Widgets` — Widget 组件
- `Qt5Network` — pynput 可能依赖
- `Qt5WinExtras` — Windows 集成（如需要）

---

## 3. 新增依赖

v1.3 无新增外部依赖。所有新功能使用 Python 标准库或现有依赖实现。

| 功能 | 实现方式 | 新增依赖 |
|-----|---------|---------|
| H.264 编码 | FFmpeg（已有，v1.1 引入内置） | 无 |
| 临时文件清理 | `tempfile`, `atexit`, `shutil`, `os.kill`（标准库） | 无 |
| 窗口枚举/重写 | `ctypes` + `ctypes.wintypes`（标准库） | 无 |
| 磁盘预警 | `shutil.disk_usage`（已有）+ `QMessageBox`（已有） | 无 |
| DPI 适配 | `Qt.AA_EnableHighDpiScaling`（PyQt5 已有） | 无 |

---

## 4. 项目架构更新

### 4.1 目录结构变化

```
QuickRec_dev/src/
├── main.py                      # 更新: 恢复窗口录制代码, 新增 DPI 设置, 磁盘检查勾子
├── config.py                    # 不变 (shortcut_window 已存在于 defaults)
├── recorder/
│   ├── recorder_manager.py      # 重构: FFmpeg pipe + TempCleaner + 窗口录制恢复
│   ├── screen_capturer.py      # 不变 (update_region() v1.2 已实现)
│   ├── video_encoder.py         # 重写: OpenCV mp4v → FFmpeg libx264 pipe
│   └── audio_capturer.py        # 不变
├── ui/
│   ├── tray_icon.py             # 小改: 恢复窗口录制菜单项
│   ├── toolbar.py               # 不变
│   ├── settings_dialog.py       # 小改: 恢复窗口录制快捷键行
│   ├── area_selector.py          # 不变
│   ├── window_selector.py       # 重写: 删除注释代码, 修复 ctypes 导入和过滤
│   ├── window_highlighter.py    # 重写: 删除注释代码, 修复属性名和崩溃
│   └── click_highlighter.py     # 不变
├── hotkey/
│   └── hotkey_manager.py        # 不变
├── utils/
│   ├── file_namer.py            # 不变
│   ├── disk_checker.py          # 扩展: 新增 check_before_recording(), 阈值常量
│   ├── disk_warning_dialog.py   # 新增: show_disk_warning() Qt 对话框
│   ├── autostart.py             # 不变
│   └── temp_cleaner.py          # 新增: 三层临时文件清理
└── 信号桥: Tray/Hotkey/Saved/Area/Window/WindowLost → Qt 主线程
```

### 4.2 模块依赖关系更新

```
main.py（六处信号桥: Tray/Hotkey/Saved/Area/Window/WindowLost → Qt 主线程）
├── config.py（不变）
├── ui/tray_icon.py（恢复"窗口录制"菜单项）
├── ui/toolbar.py（不变）
├── ui/settings_dialog.py（恢复窗口快捷键行）
├── ui/window_selector.py（重写: Win32 枚举 + 选择对话框）
├── ui/window_highlighter.py（重写: 绿色虚线边框 + 位置跟踪）
├── ui/click_highlighter.py（不变）
├── ui/area_selector.py（不变）
├── hotkey/hotkey_manager.py（不变：仅注册新 shortcut_window）
├── utils/temp_cleaner.py（新增: 会话目录管理）
├── utils/disk_checker.py（扩展: 预警/阻断阈值）
├── utils/disk_warning_dialog.py（新增: QMessageBox 对话框）
└── recorder/recorder_manager.py（重构: FFmpeg pipe + 窗口录制恢复）
    ├── recorder/video_encoder.py（重写: FFmpeg pipe libx264）
    ├── recorder/screen_capturer.py（不变: update_region 保持）
    ├── recorder/audio_capturer.py（不变: 仅输出路径改为 session_dir）
    ├── utils/file_namer.py（不变）
    └── utils/temp_cleaner.py（使用 TempCleaner）
```

---

## 5. 模块测试计划

| 模块 | 方式 | 关键用例 |
|-----|------|---------|
| VideoEncoder | 单元 + 集成 | FFmpeg 进程启动成功；write_frame 返回 True；close 后文件可播放；BrokenPipeError 处理 |
| TempCleaner | 单元 | create_session_dir 创建目录；cleanup_stale 删除无活跃进程目录；atexit 正确注册 |
| 录制管线（recorder_manager） | 集成 | 无音频录制 → 停止后 < 1 秒可播放；有音频录制 → 最终文件有视频+音频；画质缩放后分辨率正确 |
| WindowSelector | UI 测试 | 窗口列表显示；系统窗口被过滤；双击选择；取消关闭 |
| WindowHighlighter | UI 测试 | 边框跟随窗口移动；窗口关闭后崩溃恢复（hide_highlight）；鼠标穿透 |
| 窗口录制全流程 | 集成 | 选择窗口→录制→暂停→恢复→停止；窗口关闭自动停止保存；窗口最小化暂停+通知 |
| DiskChecker | 单元 | check_before_recording 三种返回值；阈值边界值（1024/200 MB） |
| 打包 | 手动 | 打包后 exe 能启动；排除的 Qt 插件不缺关键 DLL；打包体积 < 250MB（目标 < 150MB 需多次迭代） |
| DPI | UI 测试 | 150%/200% 缩放下工具栏大小正常，设置对话框控件不重叠 |

---

## 6. 开发里程碑

| 阶段 | 内容 | 依赖 | 可并行 |
|-----|------|------|-------|
| 1 | video_encoder.py 重写 (FFmpeg pipe) | 无 | ✓ |
| 2 | temp_cleaner.py 新增 | 无 | ✓ 与 1 并行 |
| 3 | disk_checker.py 扩展 + disk_warning_dialog.py | 无 | ✓ 与 1 并行 |
| 4 | window_selector.py + window_highlighter.py 重写 | 无 | ✓ 与 1 并行 |
| 5 | recorder_manager.py 重构 (pipe + 会话目录 + 窗口恢复) | 1, 2 | 必须等 1+2 |
| 6 | main.py 窗口录制恢复 | 4, 5 | 必须等 4+5 |
| 7 | settings_dialog.py + tray_icon.py 小改 | 无 | ✓ 与 6 并行 |
| 8 | build_std.spec 优化 + DPI | 无 | ✓ 与 6 并行 |
| 9 | 集成测试 + 打包 | 全部 | 最后 |

**关键路径**：video_encoder → recorder_manager → main → 集成测试

---

## 7. 风险与应对

| 风险 | 影响 | 应对 |
|-----|------|------|
| FFmpeg 子进程崩溃 | 正在录制的视频可能损坏 | 输出到 session_dir（不污染保存目录），启动时 TempCleaner.cleanup_stale() 清理遗留 |
| H.264 实时编码 CPU 占用高于 JPEG | 低端设备录制卡顿 | CRF 23 + preset medium 平衡；profile 对比 v1.2 和 v1.3 的 CPU 占用 |
| 窗口录制代码从零重写 | 可能引入新的边界 bug | 参考 v1.2 注释代码中已验证正确的部分（GetClientRect 坐标计算、窗口过滤规则） |
| 窗口丢失给托盘通知 | 托盘通知可能被用户忽略 | 通知文本明确写明当前状态和下一步操作；工具栏暂停状态同步显示 |
| 打包后排除的 DLL 导致启动崩溃 | 关键 Qt 插件被误删 | 保留核心 Qt 模块（Core/Gui/Widgets/Network/WinExtras）；platform/qwindows 插件必保留 |
| DPI 属性设置（PyQt5 非默认） | 高 DPI 环境未生效 | 两行 setAttribute 必须在 QApplication() 前；多 DPI 环境测试验证 |