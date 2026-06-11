# QuickRec 详细技术设计文档

## 1. 技术栈总览

| 层级 | 技术 | 版本 | 用途 |
|-----|------|------|------|
| 语言 | Python | 3.10+ | 主开发语言 |
| UI 框架 | PyQt5 | 5.15+ | 桌面界面开发 |
| 屏幕捕获 | mss | 9.0+ | 高性能屏幕截图 |
| 视频编码 | OpenCV | 4.8+ | 将帧序列编码为 MP4 |
| 数值计算 | NumPy | 1.24+ | 图像数据处理 |
| 热键 | pynput | 1.7+ | 全局快捷键监听（替代 keyboard，无需管理员权限） |
| 系统托盘 | pystray | 0.19+ | 系统托盘图标 |
| 打包 | PyInstaller | 6.0+ | 打包为单个 .exe |
| 配置管理 | Python 内置 json | - | 读写 config.json |

### 1.1 开发环境

```
Python 环境: D:\Work\Software\Anaconda
创建虚拟环境: conda create -n quickrec python=3.10
```

### 1.2 依赖安装

```bash
conda activate quickrec
pip install pyqt5 mss opencv-python numpy pynput pystray pyinstaller
```

---

## 2. 项目架构

### 2.1 目录结构

```
QuickRec_dev/
├── doc/
│   ├── PRD-QuickRec.md          # 产品需求文档
│   └── Tec-design.md            # 技术设计文档（本文件）
├── src/
│   ├── main.py                  # 程序入口
│   ├── config.py                # 配置管理模块
│   ├── recorder/
│   │   ├── __init__.py
│   │   ├── screen_capturer.py   # 屏幕捕获模块
│   │   ├── video_encoder.py     # 视频编码模块
│   │   └── recorder_manager.py  # 录制控制模块（协调捕获+编码）
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── tray_icon.py         # 系统托盘模块
│   │   ├── toolbar.py           # 录制工具栏窗口
│   │   ├── area_selector.py     # 区域选择窗口
│   │   └── settings_dialog.py   # 设置对话框
│   ├── hotkey/
│   │   ├── __init__.py
│   │   └── hotkey_manager.py    # 全局快捷键模块
│   └── utils/
│       ├── __init__.py
│       ├── file_namer.py        # 文件自动命名
│       └── disk_checker.py      # 磁盘空间检查
├── tests/
│   ├── test_config.py           # 配置模块测试
│   ├── test_recorder.py         # 录制模块测试
│   ├── test_file_namer.py       # 命名模块测试
│   └── test_disk_checker.py     # 磁盘检查测试
├── build/                       # PyInstaller 输出目录（自动生成）
├── dist/                        # 打包后的 exe（自动生成）
├── requirements.txt             # Python 依赖列表
└── build.spec                   # PyInstaller 打包配置
```

### 2.2 模块依赖关系

```
main.py
├── config.py (配置管理)
├── ui/tray_icon.py (系统托盘)
│   └── ui/toolbar.py (录制工具栏)
│       └── ui/settings_dialog.py (设置)
│       └── hotkey/hotkey_manager.py (快捷键 - pynput)
└── recorder/recorder_manager.py (录制控制器)
    ├── recorder/screen_capturer.py (屏幕捕获)
    └── recorder/video_encoder.py (视频编码)

注：area_selector.py 代码保留在仓库中，但 v1.0 未使用（推迟到 v1.1）
```

模块之间通过接口通信，不直接依赖实现类。

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

**质量预设映射表**：

| quality 值 | 分辨率上限 | 码率 (kbps) |
|-----------|-----------|------------|
| high      | 1920x1080 | 8000       |
| medium    | 1280x720  | 4000       |
| low       | 854x480   | 2000       |

**核心类**：

```
class ConfigManager:
    """配置管理器"""

    - config_path: str              # 配置文件完整路径
    - defaults: dict                # 默认配置值

    + get(key: str, default: Any) -> Any    # 读取配置
    + set(key: str, value: Any) -> None     # 设置配置
    + save() -> None                        # 持久化到文件
    + load() -> None                        # 从文件加载
    + reset() -> None                       # 恢复默认配置
```

**独立测试点**：
- 配置文件不存在时，自动创建并使用默认值
- 配置文件存在时，正确加载
- 配置文件格式错误时，使用默认值并记录日志
- set + save + load 后值一致

---

### 3.2 屏幕捕获模块 (screen_capturer.py)

**职责**：捕获屏幕或指定区域的图像帧。

**核心类**：

```
class ScreenCapturer:
    """屏幕捕获器"""

    - monitor: dict                 # mss 的 monitor 对象，包含 left/top/width/height
    - sct: MSS                      # mss 实例

    + __init__(region: tuple)       # 初始化，region=(left, top, width, height) 或 None(全屏)
    + capture_frame() -> ndarray    # 捕获一帧，返回 numpy 数组 (BGR 格式)
    + get_fps() -> int              # 当前捕获帧率
    + close() -> None               # 释放资源
```

**输入**：
- 全屏模式：region=None，自动获取主显示器尺寸
- 区域模式：region=(x, y, w, h)，由区域选择器传入

**输出**：
- 每帧返回 numpy ndarray，形状为 (height, width, 3)，BGR 颜色空间（OpenCV 原生格式）

**独立测试点**：
- 全屏捕获返回正确分辨率的帧
- 区域捕获返回指定尺寸的帧
- 连续捕获帧率稳定
- close 后不可再捕获

---

### 3.3 视频编码模块 (video_encoder.py)

**职责**：将帧序列编码为 MP4 文件并写入磁盘。

**核心类**：

```
class VideoEncoder:
    """视频编码器（基于 OpenCV VideoWriter）"""

    - writer: VideoWriter           # OpenCV 视频写入器
    - file_path: str                # 输出文件路径
    - fps: int                      # 帧率
    - frame_size: tuple             # 帧尺寸 (width, height)
    - bitrate: int                  # 码率
    - frame_count: int              # 已写入帧数

    + __init__(file_path: str, fps: int, frame_size: tuple, bitrate: int)
    + write_frame(frame: ndarray) -> bool   # 写入一帧，返回是否成功
    + close() -> None                       # 完成写入，关闭文件
    + is_open() -> bool                     # 编码器是否处于打开状态
    + get_frame_count() -> int              # 已写入帧数
```

**编码参数**：
- 编码器：OpenCV 内置 `VideoWriter` + `mp4v` fourcc
- 输入帧格式：BGR numpy ndarray
- 输出格式：MP4 (H.264 兼容)

**独立测试点**：
- 写入 100 帧后 close，生成可播放的 MP4 文件
- 文件路径不存在时自动创建目录
- 磁盘满时 write_frame 返回 False
- close 后文件正确结束，可正常播放

---

### 3.4 录制控制模块 (recorder_manager.py)

**职责**：协调屏幕捕获和视频编码，管理录制生命周期（开始/暂停/停止）。

**核心类**：

```
class RecorderState(Enum):
    IDLE = "idle"
    COUNTDOWN = "countdown"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"

class RecorderManager:
    """录制管理器"""

    - state: RecorderState                  # 当前状态
    - capturer: ScreenCapturer              # 屏幕捕获器实例
    - encoder: VideoEncoder                 # 视频编码器实例
    - recording_thread: Thread              # 录制线程
    - stop_event: Event                     # 停止信号
    - config: ConfigManager                 # 配置管理器
    - start_time: float                     # 录制开始时间戳
    - pause_time: float                     # 暂停时的累计时长

    + __init__(config: ConfigManager)
    + start_fullscreen() -> bool            # 开始全屏录制
    + start_region(region: tuple) -> bool   # 开始区域录制
    + pause() -> bool                       # 暂停录制
    + resume() -> bool                      # 恢复录制
    + stop() -> str                         # 停止录制，返回文件路径
    + get_state() -> RecorderState          # 获取当前状态
    + get_elapsed() -> str                  # 获取已录制时长 "MM:SS"
    + _record_loop() -> None                # 录制线程主循环（内部使用）
    + _check_disk_space() -> bool           # 检查磁盘空间（内部使用）
    + _generate_filepath() -> str           # 生成输出文件路径（内部使用）
```

**状态流转**：

```
IDLE → COUNTDOWN → RECORDING → PAUSED → RECORDING → STOPPING → IDLE
                                  ↓
                              STOPPING → IDLE
```

**录制循环逻辑** (`_record_loop`)：
```
while stop_event 未触发:
    if 处于 PAUSED 状态:
        sleep(0.05)
        continue
    frame = capturer.capture_frame()
    if encoder.write_frame(frame) == False:
        记录错误，触发停止
    sleep(1 / fps - 已耗时)  # 维持目标帧率
```

**独立测试点**：
- start 后状态变为 RECORDING，_record_loop 开始运行
- pause 后帧不再写入，resume 后恢复
- stop 后返回有效文件路径，文件可播放
- 录制中途磁盘满，自动停止并保留已录制部分
- 连续 start-stop 多次，无资源泄漏

---

### 3.5 系统托盘模块 (tray_icon.py)

**职责**：管理系统托盘图标，提供托盘菜单。

**核心类**：

```
class TrayIcon:
    """系统托盘"""

    - icon: pystray.Icon            # pystray 托盘实例
    - callbacks: dict               # 回调函数映射

    + show() -> None                # 显示托盘图标
    + hide() -> None                # 隐藏托盘图标
    + show_notification(msg: str)   # 弹出系统通知
    + set_menu(menu_items: list)    # 设置托盘菜单

    # 默认菜单项:
    # - "▶ 开始录制" → 触发全屏录制
    # - "⚙ 设置"    → 打开设置对话框
    # - "📁 打开保存文件夹" → 打开 save_path
    # - "───────────"
    # - "✕ 退出"    → 退出程序
```

**独立测试点**：
- 托盘图标显示正确
- 点击菜单项触发对应回调
- 退出时图标正确移除

---

### 3.6 录制工具栏模块 (toolbar.py)

**职责**：录制中的悬浮控制窗口，显示录制状态和提供控制按钮。

**核心类**：

```
class RecordingToolbar(QWidget):
    """录制工具栏"""

    - timer: QTimer                 # 计时器
    - elapsed: int                  # 已录制秒数
    - label_timer: QLabel           # 计时器显示
    - btn_pause: QPushButton        # 暂停按钮
    - btn_stop: QPushButton         # 停止按钮
    - btn_cancel: QPushButton       # 取消按钮
    - recording: bool               # 是否正在录制（非暂停）

    # 信号:
    + paused: Signal()              # 用户点击暂停
    + resumed: Signal()             # 用户点击继续
    + stopped: Signal()             # 用户点击停止
    + cancelled: Signal()           # 用户点击取消

    + start_countdown(seconds: int) # 开始倒计时显示
    + update_timer()                # 更新计时器显示 "MM:SS"
    + set_paused(paused: bool)      # 切换暂停/继续状态
```

**UI 布局**（对应 PRD 4.2）：
```
┌──────────────────────────────────────────────┐
│  ● 00:03:25  │  ⏸ 暂停  │  ⏹ 停止  │  ✕ 取消 │
└──────────────────────────────────────────────┘
```

**样式规范**：
- 背景色：`#1a1a2e`，透明度 90%
- 圆角：8px
- 录制状态：红色圆点 + 红色 `#e74c3c`
- 字体：计时器用等宽字体 `Consolas`，其他用系统默认
- 无边框窗口：`FramelessWindowHint | WindowStaysOnTopHint`
- 可拖动：鼠标按下记录偏移，移动时更新窗口位置

**独立测试点**：
- 计时器每秒更新，格式正确
- 暂停按钮文字在"暂停"/"继续"之间切换
- 拖动窗口位置正常
- 始终置顶

---

### 3.7 区域选择模块 (area_selector.py)

**职责**：全屏遮罩 + 矩形区域选择。

**核心类**：

```
class AreaSelector(QWidget):
    """区域选择器"""

    - is_drawing: bool              # 是否正在拖拽
    - start_point: QPoint           # 拖拽起点
    - end_point: QPoint             # 拖拽终点
    - label_size: QLabel            # 显示区域尺寸

    # 信号:
    + region_selected: Signal(int, int, int, int)  # (x, y, width, height)
    + cancelled: Signal()                          # 用户取消

    + show_fullscreen()             # 全屏半透明遮罩
    + mousePressEvent               # 记录起点
    + mouseMoveEvent                # 更新终点，重绘
    + mouseReleaseEvent             # 发送 region_selected
    + keyPressEvent                 # ESC 取消
    + paintEvent                    # 绘制选区矩形和尺寸标签
```

**交互流程**：
```
1. 调用 show_fullscreen() → 全屏半透明遮罩
2. 鼠标按下 → 记录起点
3. 鼠标拖拽 → 实时绘制矩形，显示尺寸标签 "1280 x 720"
4. 鼠标松开 → 发送 region_selected(x, y, w, h)
5. ESC 键 → 发送 cancelled
```

**独立测试点**：
- 拖拽绘制矩形位置和大小正确
- 尺寸标签实时更新
- ESC 取消正常
- 最小区域限制（至少 100x100）

---

### 3.8 设置对话框模块 (settings_dialog.py)

**职责**：提供用户修改配置的界面。

**核心类**：

```
class SettingsDialog(QDialog):
    """设置对话框"""

    - config: ConfigManager         # 配置管理器
    - edit_save_path: QLineEdit     # 保存路径输入
    - combo_quality: QComboBox      # 画质选择 (高/中/低)
    - combo_fps: QComboBox          # 帧率选择 (30/60)
    - input_shortcut_start: QLabel  # 开始快捷键显示
    - input_shortcut_stop: QLabel   # 停止快捷键显示

    # 信号:
    + config_saved: Signal()        # 配置保存成功

    + load_config()                 # 从 ConfigManager 加载当前值到控件
    + save_config()                 # 从控件读取值，写入 ConfigManager
    + browse_save_path()            # 打开文件夹选择对话框
    + record_shortcut()             # 进入快捷键录制模式
```

**对应 PRD 4.4 界面设计**。

**独立测试点**：
- 打开时显示当前配置值
- 修改后保存，下次打开显示新值
- 浏览按钮打开文件夹选择器
- 取消按钮不保存修改

---

### 3.9 全局快捷键模块 (hotkey_manager.py)

**职责**：注册和监听全局键盘快捷键。基于 pynput 库实现，无需管理员权限。

**核心类**：

```
class HotkeyManager:
    """快捷键管理器（基于 pynput）"""

    - listener: Listener                # pynput 键盘监听器
    - hotkeys: dict                    # {frozenset(键码): 回调函数}
    - current_keys: set                # 当前按下的键集合

    + register(shortcut: str, callback) -> bool   # 注册快捷键
    + unregister(shortcut: str) -> bool           # 取消注册
    + unregister_all() -> None                    # 取消所有注册
    + start_listening() -> None                   # 启动监听线程
    + stop_listening() -> None                    # 停止监听线程
```

**快捷键解析规则**：
- 输入格式：`Ctrl+Shift+R`（不区分大小写）
- `_parse_to_pynput()` 将字符串转为 pynput 键码集合
- Ctrl/Shift/Alt 支持左右键兼容匹配
- 必须包含至少一个修饰键，不允许单键快捷键

**独立测试点**：
- 解析 `Ctrl+Shift+R` 正确
- 注册后按下快捷键，回调被触发
- 程序最小化/后台时快捷键仍有效
- 重复注册同一快捷键时返回 False

---

### 3.10 文件命名模块 (file_namer.py)

**职责**：生成录制文件的文件名。

**核心类**：

```
class FileNamer:
    """文件命名器"""

    + generate(save_dir: str, prefix: str) -> str
      # 返回: save_dir / "QuickRec_YYYYMMDD_HHmmss.mp4"
      # 如果文件名冲突，自动追加序号: "QuickRec_YYYYMMDD_HHmmss_001.mp4"
```

**命名规则**：
- 格式：`QuickRec_20260611_143025.mp4`
- 冲突时：`QuickRec_20260611_143025_001.mp4`
- 目录不存在时自动创建

**独立测试点**：
- 生成的文件名符合格式
- 同一秒录制两次，文件名不冲突
- 目录不存在时自动创建

---

### 3.11 磁盘空间检查模块 (disk_checker.py)

**职责**：检查目标磁盘是否有足够空间继续录制。

**核心类**：

```
class DiskChecker:
    """磁盘空间检查"""

    + get_free_space(path: str) -> int          # 返回可用字节数
    + estimate_size_per_minute(res: tuple, fps: int) -> int  # 估算每分钟文件大小
    + is_low_space(path: str, threshold_mb: int) -> bool     # 是否低于阈值
```

**估算公式**（基于码率）：
- 高画质 8000kbps ≈ 60MB/分钟
- 中画质 4000kbps ≈ 30MB/分钟
- 低画质 2000kbps ≈ 15MB/分钟

**触发时机**：
- 开始录制前检查，低于阈值则拒绝
- 录制过程中每 30 秒检查一次
- 低于阈值时自动停止录制

**独立测试点**：
- 正确返回磁盘可用空间
- 估算文件大小误差在 ±20% 内
- 低空间时返回 True

---

## 4. 主程序入口 (main.py)

**职责**：初始化所有模块，启动应用。

**启动流程**：
```
1. 创建 QApplication
2. 初始化 ConfigManager，加载配置
3. 初始化 RecorderManager
4. 初始化 TrayIcon，显示托盘图标
5. 注册全局快捷键（Ctrl+Shift+R/S/P）
6. 进入事件循环
```

**快捷键触发动作**：
- `Ctrl+Shift+R` → 开始全屏录制（无区域选择，直接录制）
- `Ctrl+Shift+S` → 停止录制，保存文件
- `Ctrl+Shift+P` → 暂停/恢复录制

**退出流程**：
```
1. 如果正在录制，先 stop
2. 停止快捷键监听
3. 隐藏托盘图标
4. 退出 QApplication
```

---

## 5. 模块测试计划

每个模块可独立测试，不需要依赖 UI 或其他模块。

| 模块 | 测试方式 | 关键用例 |
|-----|---------|---------|
| ConfigManager | 单元测试 | 默认值、读写一致性、文件损坏恢复 |
| ScreenCapturer | 单元测试 | 全屏/区域捕获、帧率稳定性 |
| VideoEncoder | 单元测试 | 写入帧、文件可播放、磁盘满处理 |
| RecorderManager | 集成测试 | 状态流转、暂停恢复、崩溃恢复 |
| AreaSelector | 手动/UI 测试 | 拖拽选区、尺寸显示、ESC 取消 |
| SettingsDialog | 手动/UI 测试 | 配置加载保存、取消不保存 |
| HotkeyManager | 单元测试 | 快捷键解析、注册冲突 |
| FileNamer | 单元测试 | 命名格式、冲突处理 |
| DiskChecker | 单元测试 | 空间计算、阈值判断 |

---

## 6. 打包部署

### 6.1 PyInstaller 配置 (build.spec)

```python
# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['mss', 'cv2', 'pynput', 'pynput.keyboard', 'pynput.keyboard._win32', 'pystray', 'PIL', 'six'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='QuickRec',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

### 6.2 打包命令

```bash
# 打包为单个 exe
pyinstaller build.spec

# 输出位置: dist/QuickRec.exe
# 预计大小: 30-50MB
```

### 6.3 打包注意事项

- `console=True`：开发期间显示控制台窗口便于调试，正式发布改为 `console=False`
- `pynput` 库不需要管理员权限，可正常监听全局按键
- `mss` 的 DLL 依赖会被 PyInstaller 自动处理

---

## 7. 已知限制和风险

| 项目 | 说明 | 应对 |
|-----|------|------|
| pynput 全局快捷键 | pynput 无需管理员权限即可监听全局按键 | 已替代 keyboard 库 |
| mp4v 编码质量 | OpenCV 内置 mp4v 不如 x264，但无需 FFmpeg | 可接受 MVP 质量，v1.1 可切换 x264 |
| 高 DPI 缩放 | PyQt 在 4K 屏幕上可能缩放不正确 | 启动时设置 QApplication.setAttribute(AA_EnableHighDpiScaling) |
| 多显示器 | v1.0 只支持主显示器录制 | v2.0 添加显示器选择 |
| 无音频 | v1.0 不录制声音 | v1.1 添加 PyAudio |
| 区域录制兼容性 | Windows 11 上 Qt.Tool + WA_TranslucentBackground 导致点击穿透 | v1.0 去掉区域录制，v1.1 修复后启用 |
| pystray 线程安全 | pystray 回调在独立线程，不能直接操作 Qt 组件 | 使用 pyqtSignal 信号桥转发到 Qt 主线程 |

---

## 8. 开发里程碑

| 阶段 | 时间 | 交付内容 |
|-----|------|---------|
| 环境搭建 | 第 1 天 | 创建虚拟环境，安装依赖，验证 mss 捕获截图 |
| 核心录制 | 第 2-4 天 | ScreenCapturer + VideoEncoder + RecorderManager，能录出 MP4 |
| UI 界面 | 第 5-7 天 | 工具栏 + 区域选择器 + 托盘图标 |
| 设置+快捷键 | 第 8-9 天 | SettingsDialog + HotkeyManager + ConfigManager |
| 辅助功能 | 第 10 天 | 文件命名 + 磁盘检查 + 倒计时 |
| 测试+修复 | 第 11-12 天 | 各模块测试，bug 修复 |
| 打包 | 第 13-14 天 | PyInstaller 打包，安装测试 |
