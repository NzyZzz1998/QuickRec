# QuickRec v1.0 详细技术设计文档

> 版本: v1.0 最终版
> 更新时间: 2026-06-12
> 状态: v1.0 已完成，全部测试通过

---

## 1. 技术栈总览

| 层级 | 技术 | 版本 | 用途 |
|-----|------|------|------|
| 语言 | Python | 3.12.8 | 主开发语言 |
| UI 框架 | PyQt5 | 5.15+ | 桌面界面开发 |
| 屏幕捕获 | dxcam | 0.3+ | DirectX 高性能屏幕截图（约5ms/帧） |
| 视频编码 | OpenCV | 4.8+ | 将帧序列编码为 MP4 |
| 数值计算 | NumPy | 1.24+ | 图像数据处理 |
| 热键 | pynput | 1.7+ | 全局快捷键监听（无需管理员权限） |
| 系统托盘 | pystray | 0.19+ | 系统托盘图标 |
| 打包 | PyInstaller | 6.0+ | 打包为 .exe |
| 配置管理 | Python 内置 json | - | 读写 config.json |

### 1.1 开发环境

```
Python 环境: D:\Work\Software\Python (标准 CPython 3.12.8)
注意: 不要使用 Anaconda 打包！Anaconda 的 DLL 布局与 PyInstaller 不兼容
```

> **重要**：Anaconda 把 Qt5 DLL 命名为 `Qt5Core_conda.dll`，PyInstaller hooks 找不到；
> Anaconda 把 Pillow 依赖 DLL 放在 `Library/bin/` 而非 PIL 包目录内。
> 必须使用标准 CPython 进行打包。

### 1.2 依赖安装

```bash
pip install -r requirements.txt
# 依赖列表: pynput, dxcam, comtypes, opencv-python, PyQt5, pystray, Pillow, pyinstaller
```

---

## 2. 项目架构

### 2.1 目录结构

```
QuickRec_dev/
├── doc/
│   ├── PRD-QuickRec.md              # 产品需求文档
│   ├── Tec-design-v1.0.md           # v1.0 技术设计文档（本文件）
│   ├── bugfix-log.md                # Bug 修复日志
│   └── v1.0-test-cases.md           # v1.0 测试用例
├── src/
│   ├── main.py                      # 程序入口
│   ├── config.py                    # 配置管理模块
│   ├── recorder/
│   │   ├── __init__.py
│   │   ├── screen_capturer.py       # 屏幕捕获模块（dxcam）
│   │   ├── video_encoder.py         # 视频编码模块（OpenCV VideoWriter）
│   │   └── recorder_manager.py      # 录制控制模块（临时文件缓存+后编码）
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── tray_icon.py             # 系统托盘模块（pystray + 信号桥）
│   │   ├── toolbar.py               # 录制工具栏窗口
│   │   ├── area_selector.py         # 区域选择窗口（v1.0 未启用，推迟到 v1.1）
│   │   └── settings_dialog.py        # 设置对话框（含 _ShortcutRecorder）
│   ├── hotkey/
│   │   ├── __init__.py
│   │   └── hotkey_manager.py        # 全局快捷键模块（pynput 字符串标识符匹配）
│   └── utils/
│       ├── __init__.py
│       ├── file_namer.py            # 文件自动命名
│       └── disk_checker.py          # 磁盘空间检查
├── tests/
│   ├── test_config.py
│   ├── test_recorder.py
│   ├── test_file_namer.py
│   └── test_disk_checker.py
├── build/                           # PyInstaller 输出目录（自动生成）
├── dist/                            # 打包后的 exe（自动生成）
├── requirements.txt
├── build_std.spec                   # PyInstaller 打包配置（标准 CPython 版）
└── build.spec                      # PyInstaller 打包配置（旧 Anaconda 版，已弃用）
```

### 2.2 模块依赖关系

```
main.py
├── config.py (配置管理)
├── ui/tray_icon.py (系统托盘，含 _SignalBridge 信号桥)
│   └── 主线程回调 (开始录制/设置/退出)
├── ui/toolbar.py (录制工具栏)
├── ui/settings_dialog.py (设置对话框，含 _ShortcutRecorder)
├── hotkey/hotkey_manager.py (快捷键 - pynput 字符串标识符匹配)
└── recorder/recorder_manager.py (录制控制器)
    ├── recorder/screen_capturer.py (屏幕捕获 - dxcam)
    ├── recorder/video_encoder.py (视频编码 - OpenCV mp4v)
    ├── utils/file_namer.py (文件命名)
    └── utils/disk_checker.py (磁盘检查)

注：area_selector.py 代码保留在仓库中，但 v1.0 未使用（推迟到 v1.1）
```

---

## 3. 模块详细设计

### 3.1 配置管理模块 (config.py)

**职责**：读写用户配置，提供类型安全的配置访问接口。

**存储位置**：`C:\Users\<用户名>\AppData\Roaming\QuickRec\config.json`

**配置文件结构**：

```json
{
  "save_path": "C:\\Users\\win\\Videos\\QuickRec",
  "quality": "high",
  "fps": 30,
  "shortcut_start": "Ctrl+Shift+R",
  "shortcut_stop": "Ctrl+Shift+S",
  "shortcut_pause": "Ctrl+Shift+P",
  "show_countdown": false,
  "countdown_seconds": 3
}
```

**画质预设映射表**：

| quality 值 | 分辨率 | 码率参考 |
|-----------|------|---------|
| native | 原始分辨率（如 2560x1440） | 约 35MB/分钟 |
| high | 1920x1080 | 约 25MB/分钟 |
| medium | 1280x720 | 约 15MB/分钟 |
| low | 854x480 | 约 8MB/分钟 |

**核心类**：

```python
class ConfigManager:
    QUALITY_SIZES = {
        "native": None,        # 原始分辨率，编码时不缩放
        "high": (1920, 1080),
        "medium": (1280, 720),
        "low": (854, 480),
    }

    defaults = {
        "save_path": "~/Videos/QuickRec",
        "quality": "high",
        "fps": 30,
        "shortcut_start": "Ctrl+Shift+R",
        "shortcut_stop": "Ctrl+Shift+S",
        "shortcut_pause": "Ctrl+Shift+P",
        "show_countdown": False,
        "countdown_seconds": 3,
    }

    + get(key, default) -> Any       # 读取配置
    + set(key, value) -> None         # 设置配置
    + save() -> None                  # 持久化到文件
    + load() -> None                  # 从文件加载
    + reset() -> None                 # 恢复默认配置
```

---

### 3.2 屏幕捕获模块 (screen_capturer.py)

**职责**：通过 dxcam（DirectX 屏幕捕获）捕获屏幕帧。在 1440p 下帧捕获耗时约 5ms。

**核心类**：

```python
class ScreenCapturer:
    """屏幕捕获器（基于 dxcam，延迟初始化）"""
    - _camera: dxcam.Camera           # dxcam 相机实例
    - _region: tuple | None           # 捕获区域参数
    - _dxcam_region: tuple | None     # dxcam 格式的区域参数 (left, top, right, bottom)
    - _started: bool                  # 是否已启动

    + __init__(region=None)           # 创建参数，不初始化 dxcam
    + start()                         # 在录制线程中启动 dxcam（延迟初始化）
    + capture_frame() -> ndarray      # 捕获一帧，返回 BGR numpy 数组
    + get_monitor_size() -> tuple     # 返回 (width, height)
    + close()                         # 释放资源
```

**关键实现细节**：
- `__init__` 不再调用 `dxcam.create()`，避免在主线程中初始化 DirectX 导致 GUI 冻结
- `start()` 在录制线程开头调用，负责 `dxcam.create()` 和 `camera.start()`
- `capture_frame()` 调用 `get_latest_frame()` 获取最新帧，首帧为 None 时重试一次
- `get_monitor_size()` 全屏模式下使用 `GetSystemMetrics` 获取分辨率
- `__del__` 中 close() 用 try-except 包裹，防止垃圾回收阶段异常

---

### 3.3 视频编码模块 (video_encoder.py)

**职责**：将帧序列编码为 MP4 文件并写入磁盘。基于 OpenCV VideoWriter。

**核心类**：

```python
class VideoEncoder:
    - _writer: VideoWriter             # OpenCV 视频写入器
    - _file_path: str                  # 输出文件路径
    - _fps: int                        # 帧率
    - _frame_size: tuple               # 帧尺寸 (width, height)
    - _frame_count: int                # 已写入帧数
    - _is_open: bool                   # 编码器是否打开

    + __init__(file_path, fps, frame_size, bitrate=None)
    + write_frame(frame: ndarray) -> bool   # 写入一帧
    + close() -> None                       # 完成写入，关闭文件
    + is_open() -> bool                     # 编码器是否处于打开状态
    + get_frame_count() -> int              # 已写入帧数
```

**编码参数**：
- 编码器：OpenCV `VideoWriter` + `mp4v` fourcc
- 输入帧格式：BGR numpy ndarray
- 输出格式：MP4
- 构造时自动创建输出目录

---

### 3.4 录制控制模块 (recorder_manager.py)

**职责**：协调屏幕捕获和视频编码，管理录制生命周期（开始/暂停/停止）。采用临时文件缓存方案：录制时帧以 JPEG 压缩写入磁盘临时文件，停止后后台解码写入 MP4。内存占用始终为 MB 级。

**核心类**：

```python
class RecorderState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"
    SAVING = "saving"           # 后台编码中

class RecorderManager:
    - _state: RecorderState
    - _capturer: ScreenCapturer
    - _temp_file: str                          # 临时文件路径 (.tmp)
    - _temp_file_handle: BinaryIO               # 临时文件写句柄
    - _total_frames: int                        # 总帧数
    - _fps: int                                 # 帧率
    - _frame_size: tuple                        # 捕获的原始帧尺寸 (width, height)
    - _encode_size: tuple                       # 编码目标尺寸（画质缩放后）
    - _encoder: VideoEncoder                    # 仅编码线程使用
    - _on_saved: Callable                       # 编码完成回调
    - _config: ConfigManager
    - _stop_event: threading.Event              # 停止信号
    - _resume_event: threading.Event            # set()=可录制, clear()=暂停中
    - _lock: threading.Lock                     # 状态锁

    + start_fullscreen() -> bool            # 开始全屏录制
    + start_region(region: tuple) -> bool   # 开始区域录制（v1.0 未使用）
    + pause() -> bool                       # 暂停录制（clear _resume_event）
    + resume() -> bool                      # 恢复录制（set _resume_event）
    + stop(cancel=False) -> str             # 停止录制，始终返回""，异步通知
    + get_state() -> RecorderState
    + get_elapsed() -> str                  # "MM:SS" 格式
    + is_saving() -> bool
```

**状态流转**：

```
IDLE → RECORDING → PAUSED → RECORDING → STOPPING → IDLE (取消)
                    ↓                      ↓
                 STOPPING               SAVING → IDLE
                                         ↑ (on_saved 信号桥回调通知结果)
```

**录制循环逻辑** (`_record_loop`)：
```
在录制线程中启动 dxcam (capturer.start())
创建临时文件 (.tmp) 以二进制写模式打开
while stop_event 未触发:
    if 暂停中: wait(_resume_event, timeout=0.1)
    frame = capturer.capture_frame()              # ~5ms dxcam
    compressed = cv2.imencode('.jpg', frame)        # ~2ms JPEG 压缩
    写入临时文件: [4字节长度][JPEG数据]              # ~0.1ms 写盘
    帧率控制: 绝对时间戳 + time.sleep() 释放 GIL
关闭临时文件句柄
```

**编码循环逻辑** (`_encode_loop`)：
```
打开临时文件以二进制读模式
encoder = VideoWriter(output_path, fps, encode_size)
for 每一帧:
    读取4字节长度 + JPEG数据
    frame = cv2.imdecode(jpeg_data)               # ~2ms 解压
    if encode_size != frame_size:
        frame = cv2.resize(frame, encode_size)    # 画质缩放
    encoder.write(frame)                          # ~9ms 编码写入
encoder.close()
删除临时文件
调用 on_saved 回调通知结果
```

**临时文件格式**（TLV）：
```
[4字节: frame_size][frame_size字节: JPEG数据]
[4字节: frame_size][frame_size字节: JPEG数据]
...
```

**帧率控制机制**：
- 使用绝对时间戳 `rec_start` 作为基准，每帧的目标帧号 = `(now - rec_start) / frame_interval`
- 如果因捕获延迟导致落后，用当前帧填充跳过的帧号
- 暂停恢复时通过重置 `rec_start` 保持帧号连续
- Windows 高精度定时器：`timeBeginPeriod(1)` 提升系统计时器精度到 1ms

**内存占用**：
- 录制时：仅文件句柄 + 单帧 JPEG 缓冲 ≈ 几百 KB
- 编码时：逐帧从磁盘读取解压，内存只有 1 帧 + VideoWriter 缓冲

---

### 3.5 系统托盘模块 (tray_icon.py)

**职责**：管理系统托盘图标和菜单。通过 `_SignalBridge` 信号桥将 pystray 线程回调安全转发到 Qt 主线程。

**核心类**：

```python
class _SignalBridge(QObject):
    """pystray 线程 → Qt 主线程的信号桥"""
    start_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    exit_requested = pyqtSignal()

class TrayIcon:
    - _icon: pystray.Icon           # pystray 托盘实例
    - _callbacks: dict               # {"start": func, "settings": func, "exit": func}
    - _bridge: _SignalBridge         # 信号桥

    + show() -> None                 # 显示托盘图标（run_detached）
    + hide() -> None                 # 隐藏托盘图标
    + show_notification(msg, title)   # 弹出系统通知
    + set_menu(menu_items)           # 设置托盘菜单（暂未实现动态菜单）
```

**菜单项**：
- "▶ 开始录制" → 触发开始录制回调
- "⚙ 设置" → 打开设置对话框
- "📁 打开保存文件夹" → 打开 save_path（纯 IO 操作，无需信号桥）
- "✕ 退出" → 退出程序

**线程安全设计**：
- pystray 回调在独立线程，不能直接操作 Qt 组件
- `_on_start/_on_settings/_on_exit` 只发信号
- `_handle_start/_handle_settings/_handle_exit` 在 Qt 主线程执行
- `_handle_exit` 使用 `QTimer.singleShot(0, self._stop_icon)` 延迟停止图标，避免死锁

---

### 3.6 录制工具栏模块 (toolbar.py)

**职责**：录制中的悬浮控制窗口，显示录制状态和提供控制按钮。

**核心类**：

```python
class RecordingToolbar(QWidget):
    paused = pyqtSignal()             # 用户点击暂停
    resumed = pyqtSignal()            # 用户点击继续
    stopped = pyqtSignal()           # 用户点击停止
    cancelled = pyqtSignal()         # 用户点击取消

    - _timer: QTimer                  # 计时器
    - _elapsed_seconds: int           # 已录制秒数
    - _label_timer: QLabel            # 计时器显示 "MM:SS"
    - _btn_pause: QPushButton         # 暂停/继续按钮
    - _btn_stop: QPushButton          # 停止按钮
    - _btn_cancel: QPushButton        # 取消按钮
    - _indicator: QLabel              # 录制状态指示灯

    + start_countdown(seconds=0)      # 开始计时，定位到屏幕顶部居中
    + stop_countdown()                # 停止计时
    + set_paused(paused: bool)        # 切换暂停/继续（按钮文字和指示灯颜色）
    + show_saving()                   # 显示"保存中..."状态，禁用所有按钮
```

**UI 布局**：
```
┌──────────────────────────────────────────────┐
│  ● 00:03:25  │  ⏸ 暂停  │  ⏹ 停止  │  ✕ 取消 │
└──────────────────────────────────────────────┘
```

**样式规范**：
- 背景色：`rgba(26, 26, 46, 230)`，圆角 8px
- 录制状态：红色指示灯 `#e74c3c`，暂停状态：黄色 `#f39c12`
- 计时器字体：Consolas 等宽字体
- 无边框窗口：`FramelessWindowHint | WindowStaysOnTopHint | Tool`
- 可拖动：鼠标拖拽标题区域移动
- 保存中状态：指示灯变蓝 `#3498db`，按钮全部禁用

**定位**：启动时自动移到屏幕顶部居中位置（距顶部 10px）

---

### 3.7 区域选择模块 (area_selector.py)

**职责**：全屏遮罩 + 矩形区域选择。**v1.0 未启用**，推迟到 v1.1。

**已知问题**：`Qt.Tool` 窗口标志与 `Qt.WA_TranslucentBackground` 在 Windows 11 上组合使用时，窗口被系统视为"点击穿透"覆盖层，无法接收输入事件。

**修复方案**（已完成但未启用）：
- 移除 `Qt.Tool` 窗口标志
- 添加 `Qt.StrongFocus` 焦点策略
- `show_fullscreen()` 中添加 `self.raise_()` + `self.activateWindow()` + `self.setFocus()`
- 右键点击取消选择的安全退出机制

---

### 3.8 设置对话框模块 (settings_dialog.py)

**职责**：提供用户修改配置的界面，包含自定义快捷键录制控件。

**核心类**：

```python
class _ShortcutRecorder(QLabel):
    """可点击录制快捷键的标签控件"""
    shortcut_changed = pyqtSignal(str)

    + __init__(initial_text, parent)   # 初始化，设置可点击样式
    + mousePressEvent                  # 点击进入录制模式
    + keyPressEvent                    # 捕获按键组合，Escape 取消
    + focusOutEvent                    # 失焦时取消录制，恢复原值

    # 录制模式：
    # - 点击后显示"按下快捷键..."，边框变蓝色
    # - 按下修饰键+普通键组合后自动识别（如 Ctrl+Shift+R）
    # - 单独修饰键不算有效快捷键
    # - Escape 取消录制，恢复原值
    # - Backspace 恢复默认值

class SettingsDialog(QDialog):
    config_saved = pyqtSignal()

    - _edit_save_path: QLineEdit         # 保存路径（只读 + 浏览按钮）
    - _combo_quality: QComboBox          # 画质选择
    - _combo_fps: QComboBox             # 帧率选择 (30/60)
    - _shortcut_start: _ShortcutRecorder # 开始快捷键
    - _shortcut_stop: _ShortcutRecorder  # 停止快捷键
    - _shortcut_pause: _ShortcutRecorder # 暂停快捷键

    + _load_config()                    # 从 ConfigManager 加载到控件
    + _save_config()                    # 从控件写入 ConfigManager，emit config_saved
    + _browse_save_path()               # QFileDialog 文件夹选择
```

**画质选项**：

| 显示文本 | 配置值 |
|---------|-------|
| 原生 (2K) | native |
| 高 (1080p) | high |
| 中 (720p) | medium |
| 低 (480p) | low |

**线程安全注意**：打开设置对话框时，主程序会停止全局快捷键监听（`hotkey.stop_listening()`），关闭后重新启动（`hotkey.start_listening()`），避免 pynput 全局监听与 `_ShortcutRecorder` 的键盘捕获冲突。

---

### 3.9 全局快捷键模块 (hotkey_manager.py)

**职责**：注册和监听全局键盘快捷键。基于 pynput 库实现，无需管理员权限。采用字符串标识符进行键匹配，解决 pynput KeyCode 对象不一致问题。

**核心类**：

```python
class HotkeyManager:
    - _registered: dict          # {规范化字符串: 回调函数}
    - _parsed: dict              # {规范化字符串: frozenset(键标识符)}
    - _listener: Listener        # pynput 键盘监听器
    - _current_keys: set         # 当前按下的键标识符集合
    - _triggered: set            # 已触发的快捷键（防按键按住重复触发）
    - _started: bool             # 是否正在监听

    + register(shortcut, callback) -> bool   # 注册快捷键
    + unregister(shortcut) -> bool           # 取消注册
    + unregister_all() -> None               # 取消所有注册并停止监听
    + start_listening() -> None              # 启动监听线程
    + stop_listening() -> None               # 停止监听线程
```

**字符串标识符匹配机制**：
- 将所有 pynput 键对象统一转换为字符串标识符（如 `'ctrl'`, `'shift'`, `'r'`）
- `_key_to_id()` 方法：优先用 `char` 属性，回退到 Windows 虚拟键码（VK）映射
- `_VK_MAP` 字典：A-Z 字母键、0-9 数字键、空格/回车/Tab/Esc 的 VK 到标识符映射
- 匹配方式：`frozenset` 精确匹配 — 当前按键集合必须完全等于注册组合
- `_triggered` 集合：按键按住时仅触发一次，释放后清除

**为什么不用 KeyCode 对象比较**：pynput 在修饰键按下时报告的 `KeyCode` 对象与 `KeyCode.from_char()` 创建的对象不一致。Ctrl/Shift 被按住时，后续普通键的 `KeyCode.char` 可能为 `None` 或控制字符，导致对象比较永远匹配失败。

---

### 3.10 文件命名模块 (file_namer.py)

**职责**：生成录制文件的文件名。

```python
class FileNamer:
    + generate(save_dir, prefix="QuickRec") -> str
      # 返回: save_dir / "QuickRec_YYYYMMDD_HHmmss.mp4"
      # 同名冲突时追加序号: "QuickRec_YYYYMMDD_HHmmss_001.mp4"
      # 目录不存在时自动创建
```

---

### 3.11 磁盘空间检查模块 (disk_checker.py)

**职责**：检查目标磁盘是否有足够空间继续录制。

```python
class DiskChecker:
    + get_free_space(path) -> int                 # 可用字节数
    + estimate_size_per_minute(quality, fps) -> int # 估算每分钟文件大小 (MB)
    + is_low_space(path, quality, buffer_minutes=5) -> bool # 是否低于阈值
```

**估算参考**（基于实际测试）：

| 画质 | 帧率 | 码率 | 估算大小/分钟 |
|-----|------|------|-------------|
| native (2K) | 30fps | - | ~35MB |
| high (1080p) | 30fps | 8000kbps | ~25MB |
| medium (720p) | 30fps | 4000kbps | ~15MB |
| low (480p) | 30fps | 2000kbps | ~8MB |
| native (2K) | 60fps | - | ~70MB |

---

## 4. 主程序入口 (main.py)

**职责**：初始化所有模块，协调录制流程。

**启动流程**：
```
1. 创建 QApplication（setQuitOnLastWindowClosed=False）
2. 初始化 ConfigManager，加载配置
3. 初始化 RecorderManager（传入 on_saved 回调）
4. 初始化 HotkeyManager，注册快捷键
5. 初始化 TrayIcon，显示托盘图标
6. 启动快捷键监听
7. 进入 Qt 事件循环
```

**快捷键触发动作**：
- `Ctrl+Shift+R` → `_HotkeyBridge.start_requested` 信号 → `_on_start_recording()`：开始全屏录制
- `Ctrl+Shift+S` → `_HotkeyBridge.stop_requested` 信号 → `_on_stop_recording()`：停止录制
- `Ctrl+Shift+P` → `_HotkeyBridge.pause_requested` 信号 → `_on_pause_resume()`：暂停/恢复录制

**线程安全设计**（三处信号桥）：
- `_SignalBridge`：pystray 线程回调 → Qt 主线程（开始/设置/退出）
- `_HotkeyBridge`：pynput 线程回调 → Qt 主线程（开始/停止/暂停快捷键）
- `_SavedBridge`：编码线程回调 → Qt 主线程（编码完成通知）

**关键流程**：
- **停止录制**：`stop()` 非阻塞，立即返回。后台线程 `_stop_and_encode()` 处理录制线程等待、文件清理和编码启动
- **保存中状态**：工具栏调用 `show_saving()` 显示"保存中..."
- **编码完成**：`on_saved` 通过 `_SavedBridge` pyqtSignal 安全转发到主线程更新 UI
- **设置对话框**：打开前停止快捷键监听（`stop_listening()`），关闭后重启（`start_listening()`）

**退出流程**：
```
1. 如果正在录制，先 stop（非阻塞）
2. wait_until_idle(timeout=60) 等待录制停止和编码完成
3. 处理完所有编码完成信号
4. 隐藏工具栏，停止快捷键监听
5. 隐藏托盘图标（QTimer 延迟 stop 避免 pystray 死锁）
6. 退出 QApplication
```

---

## 5. 模块测试计划

| 模块 | 测试方式 | 关键用例 |
|-----|---------|---------|
| ConfigManager | 单元测试 | 默认值、读写一致性、文件损坏恢复 |
| ScreenCapturer | 单元测试 | 全屏/区域捕获、帧率稳定性 |
| VideoEncoder | 单元测试 | 写入帧、文件可播放、磁盘满处理 |
| RecorderManager | 集成测试 | 状态流转、暂停恢复、取消录制、编码完成回调 |
| AreaSelector | 手动/UI 测试 | 拖拽选区、尺寸显示、ESC/右键取消 |
| SettingsDialog | 手动/UI 测试 | 配置加载保存、快捷键录制、画质/帧率选择 |
| HotkeyManager | 单元测试 | 快捷键解析、注册冲突、字符串标识符匹配 |
| FileNamer | 单元测试 | 命名格式、冲突处理 |
| DiskChecker | 单元测试 | 空间计算、阈值判断 |

---

## 6. 打包部署

### 6.1 PyInstaller 配置 (build_std.spec)

```python
# 使用标准 CPython 3.12.8 打包
# 命令: cd E:\CC_Learning\QuickRec_dev
#        D:\Work\Software\Python\Scripts\pyinstaller.exe build_std.spec --noconfirm

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'dxcam', 'comtypes', 'comtypes.client', 'comtypes.stream',
        'cv2', 'pynput', 'pynput.keyboard', 'pynput.keyboard._win32',
        'pystray', 'PIL', 'six'
    ],
    ...
)
exe = EXE(
    ...
    name='QuickRec',
    debug=False,
    upx=True,
    console=True,     # 开发期间显示控制台便于调试
    ...
)
```

### 6.2 打包命令

```bash
cd E:\CC_Learning\QuickRec_dev
D:\Work\Software\Python\Scripts\pyinstaller.exe build_std.spec --noconfirm
# 输出: dist/QuickRec/QuickRec.exe
```

### 6.3 打包注意事项

- **必须使用标准 CPython**，不能使用 Anaconda（DLL 布局不兼容）
- `console=True`：开发期间显示控制台窗口便于调试，正式发布改为 `console=False`
- `pynput` 库不需要管理员权限，可正常监听全局按键
- `dxcam` 的 DLL 依赖需包含在 hiddenimports 中

---

## 7. 已知限制和风险

| 项目 | 说明 | 应对 |
|-----|------|------|
| 仅全屏录制 | v1.0 仅支持全屏录制，区域录制因 Win11 兼容性问题推迟到 v1.1 | 区域选择器代码保留但未启用 |
| 无音频录制 | v1.0 不支持系统声音和麦克风录制 | v1.1 添加音频录制 |
| 单显示器 | 仅录制主显示器 | v2.0 添加显示器选择 |
| mp4v 编码质量 | OpenCV mp4v 不如 x264，但无需 FFmpeg | 可接受，v1.1 可切换 x264 |
| 临时文件大小 | 60fps 录制时临时文件约 18MB/分钟 | 编码完成后自动清理 |
| 画质缩放 | native(2K) 档位无缩放，其他档位在编码时 cv2.resize | 缩放在编码线程进行，不影响录制帧率 |
| pystray 线程安全 | pystray 回调在独立线程，不能直接操作 Qt 组件 | 使用 pyqtSignal 信号桥转发到主线程 |
| pynput 线程安全 | pynput 回调在独立线程，不能直接操作 Qt 组件 | 使用 pyqtSignal 信号桥转发到主线程 |
| 编码线程回调 | on_saved 在编码线程中调用，QTimer.singleShot 不可靠 | 使用 pyqtSignal 信号桥转发到主线程 |
| 录制线程 GIL 竞争 | 忙等待循环占满 CPU，主线程冻结 | 用 time.sleep() 替代 while pass 释放 GIL |
| dxcam 主线程初始化 | dxcam.create() 在主线程冻结 GUI | 延迟到录制线程中初始化 |
| 设置对话框快捷键冲突 | pynput 全局监听与 _ShortcutRecorder 键盘捕获冲突 | 打开设置时停止监听，关闭后重启 |

---

## 8. 开发里程碑

| 阶段 | 状态 | 交付内容 |
|-----|------|---------|
| 环境搭建 | ✅ 完成 | CPython 3.12.8 环境，dxcam 截图验证 |
| 核心录制 | ✅ 完成 | 临时文件缓存方案（JPEG 写盘 + 后编码），稳定 60fps |
| UI 界面 | ✅ 完成 | 工具栏 + 托盘图标 + 设置对话框 |
| 设置+快捷键 | ✅ 完成 | pynput 字符串标识符匹配 + _ShortcutRecorder |
| Bug 修复 | ✅ 完成 | 19 个 Bug 修复（详见 bugfix-log.md） |
| 测试+打包 | ✅ 完成 | PyInstaller 打包成功，exe 可正常运行，全部测试通过 |