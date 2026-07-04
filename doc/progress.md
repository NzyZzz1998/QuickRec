# QuickRec 项目进度总览

> 最后更新: 2026-06-24

## 环境状态

| 项目 | 状态 | 版本 | 说明 |
|-----|------|------|------|
| Python | ✅ 已安装 | 3.12.8 | Anaconda base |
| PyQt5 | ✅ 已安装 | 5.15.10 | |
| numpy | ✅ 已安装 | 2.4.6 | opencv-python 依赖升级 |
| dxcam | ✅ 已安装 | 0.3.0 | 替代 mss，DirectX屏幕捕获 |
| comtypes | ✅ 已安装 | 1.4.16 | dxcam 依赖 |
| opencv-python | ✅ 已安装 | 4.13.0 | |
| keyboard | ❌ 已移除 | - | 替换为 pynput |
| pynput | ✅ 已安装 | 1.8.2 | 替代 keyboard，无需管理员权限 |
| pystray | ✅ 已安装 | 0.19.5 | |
| pyinstaller | ✅ 已安装 | 6.20.0 | |

## 模块进度

### 基础设施
- [x] 项目初始化和依赖安装
  - [x] 安装 dxcam (0.3.0) 和 comtypes (1.4.16)
  - [x] 安装 pyqt5、opencv-python、numpy、pynput、pystray、pyinstaller
  - [x] 安装 pystray (0.19.5)
  - [x] 安装 pyinstaller (6.20.0)
  - [x] 生成 requirements.txt
  - [x] 创建项目目录结构

### 核心模块 (无依赖，可独立开发)
- [x] 配置管理模块 (config.py)
  - [x] ConfigManager 类实现
  - [x] 默认值定义
  - [x] 文件路径处理
  - [x] 异常处理
  - [x] 单元测试 (8/8 通过)

- [x] 文件命名模块 (file_namer.py)
  - [x] FileNamer 类实现
  - [x] 命名规则
  - [x] 目录处理
  - [x] 单元测试 (5/5 通过)

- [x] 磁盘空间检查模块 (disk_checker.py)
  - [x] DiskChecker 类实现
  - [x] 空间估算逻辑
  - [x] 单元测试 (6/6 通过)

### 录制引擎
- [x] 屏幕捕获模块 (screen_capturer.py)
  - [x] ScreenCapturer 类实现
  - [x] 全屏/区域捕获
  - [x] 数据格式验证
  - [x] 单元测试 (6/6 通过)

- [x] 视频编码模块 (video_encoder.py)
  - [x] VideoEncoder 类实现
  - [x] 编码参数配置
  - [x] 单元测试 (5/5 通过)

- [x] 录制控制模块 (recorder_manager.py)
  - [x] RecorderState 枚举
  - [x] RecorderManager 类实现
  - [x] 录制循环
  - [x] 单元测试 (7/7 通过)

### UI 模块
- [x] 区域选择模块 (area_selector.py)
  - [x] AreaSelector 类实现
  - [x] 交互逻辑 (鼠标拖拽、ESC取消)
  - [x] 显示信息 (尺寸标签、边框高亮)
  - [x] 单元测试 (6/6 通过)
  - ⚠️ v1.0 未使用（Windows 11 兼容性问题，推迟到 v1.1）

- [x] 录制工具栏模块 (toolbar.py)
  - [x] RecordingToolbar 类实现
  - [x] UI 元素 (指示灯、计时器、按钮)
  - [x] 交互功能 (暂停/恢复、拖拽)
  - [x] 单元测试 (8/8 通过)

- [x] 设置对话框模块 (settings_dialog.py)
  - [x] SettingsDialog 类实现
  - [x] 控件定义 (路径、画质、帧率、快捷键)
  - [x] 功能实现 (加载、保存、浏览)
  - [x] 单元测试 (5/5 通过)

- [x] 系统托盘模块 (tray_icon.py)
  - [x] TrayIcon 类实现
  - [x] 菜单项 (录制、设置、打开文件夹、退出)
  - [x] 功能实现 (显示、隐藏、通知)
  - [x] 单元测试 (3/3 通过)

- [x] 全局快捷键模块 (hotkey_manager.py)
  - [x] HotkeyManager 类实现（基于 pynput，原 keyboard 已移除）
  - [x] 快捷键格式解析（键集合匹配）
  - [x] Ctrl/Shift/Alt 左右键兼容
  - [x] start_listening / stop_listening 生命周期管理
  - [x] 单元测试 (7/7 通过)

### 入口和集成
- [x] 主程序入口 (main.py)
  - [x] 初始化流程
  - [x] 快捷键绑定
  - [x] UI 流程
  - [x] 退出流程
  - [x] 异常处理

## 依赖关系图

```
setup (最先)
  │
  ├─> config.py (无依赖)
  ├─> file_namer.py (无依赖)
  ├─> disk_checker.py (无依赖)
  │
  ├─> screen_capturer.py (依赖: dxcam)
  │
  ├─> video_encoder.py (依赖: opencv-python)
  │
  ├─> hotkey_manager.py (依赖: pynput)  ← 原 keyboard 已替换
  │
  ├─> area_selector.py (依赖: PyQt5)  ← v1.0 未使用
  ├─> toolbar.py (依赖: PyQt5)
  ├─> settings_dialog.py (依赖: config + PyQt5)
  ├─> tray_icon.py (依赖: pystray + PyQt5)  ← 含信号桥线程安全
  │
  ├─> recorder_manager.py (依赖: capturer + encoder + file_namer + checker + config)
  │
  └─> main.py (依赖: 所有模块)  ← v1.0 仅全屏录制
```

### v1.0 开发阶段

| 阶段 | 内容 | 依赖 | 状态 |
|-----|------|------|------|
| 1 | setup + config + file_namer + disk_checker | 无 | ✅ |
| 2 | screen_capturer + video_encoder + recorder_manager | 依赖阶段1 | ✅ |
| 3 | area_selector + toolbar + settings_dialog | 依赖阶段2 | ✅ |
| 4 | hotkey_manager + tray_icon | 依赖阶段3 | ✅ |
| 5 | main.py 入口集成 | 依赖所有模块 | ✅ |
| 6 | 完整功能测试 + 打包 | 依赖阶段5 | ✅ |
| 7 | Bug 修复（#1-#19，详见 bugfix-log.md） | — | ✅ 58/66 测试通过；修复共 19 个 Bug；v1.0 仅保留全屏录制，区域录制推迟至 v1.1 |

---


## v1.1 进度 ✅ 已完成（2026-06-12）

> v1.1 目标：区域录制 + 音频源选择 + 通知增强
> 测试结果：76 用例 → 75 通过 / 1 跳过 / 0 失败；已打包并通过打包后功能验证

### v1.1 模块进度

- [x] 区域录制模块 (area_selector.py)
  - [x] Win11 点击穿透修复（移除 Qt.Tool，添加 StrongFocus）
  - [x] 确认对话框（开始录制 / 取消）
  - [x] 最小尺寸提示（红色提示 < 100x100）
  - [x] 边框视觉优化（白色虚线）
  - [x] 与 main.py 集成（_AreaBridge 信号桥）

- [x] 音频录制模块 (audio_capturer.py) — 新增文件
  - [x] AudioSource 枚举和 AudioCapturer 类框架
  - [x] WASAPI 系统声音捕获（pyaudiowpatch）
  - [x] 麦克风捕获（pyaudio）
  - [x] 音频捕获线程和 WAV 写入
  - [x] BOTH 模式双路独立录制
  - [x] 优雅降级（设备不可用时无声录制）

- [x] 录制控制模块 (recorder_manager.py) — 更新
  - [x] RecordMode 枚举（FULLSCREEN / REGION）
  - [x] 音频初始化（_start 方法扩展）
  - [x] 音频停止（_stop_and_encode 方法扩展）
  - [x] 音频混合（_encode_loop + FFmpeg）
  - [x] FFmpeg 集成（_get_ffmpeg_path + _mix_audio_video）
  - [x] 配置扩展（audio_source 默认值）

- [x] 系统托盘模块 (tray_icon.py) — 更新
  - [x] _SignalBridge 新增信号（start_region / pause_resume / stop）
  - [x] 动态菜单切换（空闲 / 录制中 / 暂停）
  - [x] Toast 通知增强（winotify 降级链）
  - [x] 托盘菜单回调扩展

- [x] 录制工具栏模块 (toolbar.py) — 更新
  - [x] 结果条模式（✓ 时长 | 已保存 | 📂 打开 | ✕ 关闭）
  - [x] 5 秒自动关闭定时器
  - [x] "已保存" 按钮打开视频文件
  - [x] "📂 打开" 按钮打开文件夹并选中

- [x] 配置管理模块 (config.py) — 更新
  - [x] 新增 audio_source 默认配置
  - [x] 新增 shortcut_area 默认配置
  - [x] 旧版配置向后兼容

- [x] 设置对话框模块 (settings_dialog.py) — 更新
  - [x] 音频源选择下拉框
  - [x] 区域录制快捷键设置
  - [x] 配置加载与保存扩展

- [x] 主程序入口 (main.py) — 更新
  - [x] _AreaBridge 信号桥
  - [x] _HotkeyBridge 扩展（area_requested）
  - [x] 区域录制流程（_on_start_region / _on_region_selected）
  - [x] 托盘回调扩展（start_fullscreen / start_region / pause_resume / stop）
  - [x] 编码完成回调增强（Toast 通知 + 结果条）
  - [x] 工具栏信号连接（open_folder / open_file）

- [x] FFmpeg 打包配置
  - [x] FFmpeg 8.0.1 已就位（ffmpeg/ffmpeg.exe, 94MB）
  - [x] build_std.spec 更新（添加 audio_capturer, winotify hiddenimport）
  - [x] requirements.txt 添加新依赖（pyaudiowpatch, pyaudio, winotify）— 已安装
  - [x] .gitignore 添加 ffmpeg/ 目录
  - [x] _get_ffmpeg_path() 实现（修复开发环境路径计算）

### v1.1 开发阶段

| 阶段 | 内容 | 依赖 | 状态 |
|-----|------|------|------|
| 1 | config.py 新增配置项 | 无 | ✅ |
| 2 | area_selector.py Win11 修复 + 确认对话框 | config | ✅ |
| 3 | audio_capturer.py 音频捕获 | config | ✅ |
| 4 | recorder_manager.py 录制模式 + 音频集成 | audio_capturer | ✅ |
| 5 | tray_icon.py 动态菜单 + Toast 通知 | config | ✅ |
| 6 | toolbar.py 结果条模式 | config | ✅ |
| 7 | settings_dialog.py 设置扩展 | config | ✅ |
| 8 | main.py 信号桥 + 流程集成 | 所有模块 | ✅ |
| 9 | FFmpeg 打包配置 | recorder_manager | ✅ |
| 10 | 集成测试 + 打包验证 | 全部 | ✅ 76 用例 75 通过 / 1 跳过（T6.5 降级路径）/ 0 失败；打包成功，打包后功能全部通过 |

---

## v1.2 进度 ✅ 已完成（窗口录制延期）

> v1.2 目标：指定窗口录制 + 鼠标点击高亮 + 原生画质优化 + 开机自启 + 录制倒计时
> 测试结果：62 通过 / 24 延期（窗口录制相关） / 0 失败；单元测试 26/26 通过

### v1.2 模块进度

#### 基础设施
- [x] 配置管理模块更新 (config.py) — v1.2
  - [x] 新增配置项（shortcut_window, show_countdown, countdown_seconds, mouse_highlight, auto_start）
  - [x] 新增 get_native_resolution() 静态方法
  - [x] 旧版配置向后兼容

#### 工具模块
- [x] 开机自启模块 (autostart.py) — 新增
  - [x] is_autostart_enabled() 注册表读取
  - [x] enable_autostart() 注册表写入
  - [x] disable_autostart() 注册表删除

#### UI 模块
- [x] 鼠标点击高亮模块 (click_highlighter.py) — 新增
  - [x] _ClickBridge 信号桥
  - [x] ClickCircle 扩散圆圈动画
  - [x] ClickHighlighter 管理器（pynput 鼠标监听）

- [x] 录制工具栏倒计时 (toolbar.py) — 更新
  - [x] 倒计时 UI（大号数字 + 取消提示）
  - [x] start_countdown / cancel_countdown 方法
  - [x] countdown_finished 信号
  - [x] ESC 键取消倒计时

- [x] 窗口选择器 (window_selector.py) — 新增 (延期)
  - [x] Win32 窗口枚举（EnumWindows + 过滤）
  - [x] 窗口列表对话框 UI
  - [x] window_selected / cancelled 信号

- [x] 窗口边框高亮 (window_highlighter.py) — 新增 (延期)
  - [x] 绿色虚线边框绘制
  - [x] 位置跟踪定时器（100ms）
  - [x] show_highlight / hide_highlight

- [x] 设置对话框更新 (settings_dialog.py) — 更新
  - [x] 开机自启复选框 + 注册表同步
  - [x] 倒计时复选框 + 秒数输入
  - [x] 鼠标高亮复选框
  - [x] 窗口录制快捷键
  - [x] 画质下拉框动态显示分辨率

- [x] 系统托盘更新 (tray_icon.py) — 更新
  - [x] 空闲菜单新增"窗口录制"
  - [x] start_window_requested 信号

#### 录制模块
- [x] 屏幕捕获更新 (screen_capturer.py) — 更新
  - [x] update_region() 动态更新捕获区域

- [x] 录制控制器更新 (recorder_manager.py) — 更新
  - [x] RecordMode.WINDOW 枚举 (延期)
  - [x] start_window() 方法 (延期)
  - [x] _record_loop 窗口位置跟踪 (延期)
  - [x] _WindowLostBridge 信号桥 (延期)

#### 入口集成
- [x] 主程序入口更新 (main.py) — 更新
  - [x] _WindowBridge / _WindowLostBridge 信号桥
  - [x] 窗口录制流程（_on_start_window / _on_window_selected / _do_start_window） (延期)
  - [x] 倒计时集成（全屏/区域/窗口）
  - [x] 鼠标高亮控制
  - [x] 窗口高亮生命周期管理 (延期)
  - [x] 快捷键注册扩展

### v1.2 开发阶段

| 阶段 | 内容 | 依赖 | 状态 |
|-----|------|------|------|
| 1 | config.py 新增配置项 + autostart.py | 无 | ✅ |
| 2 | click_highlighter.py 鼠标高亮 | config | ✅ |
| 3 | toolbar.py 倒计时模式 | config（可与阶段 2 并行） | ✅ |
| 4 | settings_dialog.py 设置更新 | config, autostart | ✅ |
| 5 | 窗口录制核心（window_selector + window_highlighter + screen_capturer + recorder_manager） | config | ✅ |
| 6 | main.py 集成 + tray_icon.py 菜单更新 | 所有模块 | ✅ |
| 7 | 集成测试 + 打包验证 | 全部 | ✅ 部分延期（窗口录制延期） |

---

## v1.3 进度 ✅ 已完成（2026-06-24）

> v1.3 目标：窗口录制深度重写 + H.264 实时编码（零拷贝管线）+ 打包体积优化 + 稳定性改进
> 测试结果：88 用例 → 82 通过 / 6 未测试（磁盘空间无环境）/ 0 失败；打包 259MB，打包后功能全部通过

### v1.3 模块进度

#### 编码模块

- [x] **video_encoder.py — FFmpeg pipe H.264 重写**
  - [x] 删除旧 OpenCV VideoWriter 代码
  - [x] 实现 `_build_cmd()` — 构造 FFmpeg 命令行（rawvideo → libx264 CRF23 preset medium）
  - [x] 实现 `__init__()` — subprocess.Popen 启动 FFmpeg，stdin=PIPE
  - [x] 实现 `write_frame(frame)` — BGR24 `tobytes()` 写入 stdin，捕获 BrokenPipeError 返回 False
  - [x] 实现 `close()` — stdin.close + proc.wait(30s) + 检查 returncode
  - [x] 实现 `__del__()` — terminate 保底
  - [x] 错误处理：FileNotFoundError（抛异常）→ 调用方降级；TimeoutExpired（kill）
  - [x] 单元测试：mock Popen 验证命令行参数（帧尺寸、帧率、CRF、preset、pix_fmt）
  - [x] 集成测试：写入 100 帧 1920×1080 BGR24 → 输出可播放 H.264 MP4 → close 后 write_frame 返回 False

#### 工具模块

- [x] **temp_cleaner.py — 三层临时文件清理（新增）**
  - [x] 创建 TempCleaner 类，定义 BASE_DIR = %TEMP%/QuickRec
  - [x] 实现 `create_session_dir()` — 创建 `session_{pid}_{ts}/` 目录，返回绝对路径
  - [x] 实现 `_is_pid_alive(pid)` — `os.kill(pid, 0)` 不依赖 psutil
  - [x] 实现 `cleanup_session(dir)` — `shutil.rmtree`，忽略 OSError
  - [x] 实现 `cleanup_stale()` — 遍历 session_* 目录，解析 PID，清理非活跃进程遗留
  - [x] 实现 `register_atexit(dir)` — `atexit.register(cleanup_session, dir)`
  - [x] 单元测试：创建/清理目录正常；cleanup_stale 删除 dead PID 目录、保留 live PID 目录

- [x] **disk_checker.py — 磁盘空间预警（扩展）**
  - [x] 新增 `WARN_THRESHOLD_MB = 1024`、`BLOCK_THRESHOLD_MB = 200` 常量
  - [x] 实现 `check_before_recording(save_path)` → ("ok"|"warn"|"block", free_mb)
  - [x] 实现 `show_disk_warning(free_mb, block, parent)` → bool（block=True 返回 False，False 返回用户选择）
  - [x] 在 main.py 三种录制入口（全屏/区域/窗口）的 `_start()` 前接入 `_check_disk_space()` 勾子
  - [x] 单元测试：mock get_free_space 验证三种返回值；阈值边界值（1024MB/199MB）
  - [x] 集成测试：QMessageBox.warning/critical 在托盘应用中正常显示

#### 录制核心

- [x] **recorder_manager.py — 管线重构 + 窗口录制恢复**
  - [x] 删除：`_JPEG_QUALITY`、`_JPEG_PARAMS`（常量）；`_temp_file`、`_temp_file_handle`、`_total_frames`（字段）
  - [x] 删除：`_compress_frame()`、`_encode_loop()`、`_cleanup_temp_file()`（方法）
  - [x] 新增字段：`_session_dir`、`_video_temp_path`、`_encoder`、`_finalize_thread`
  - [x] 修改 `_start()` — 创建 session 目录（temp_cleaner）；音频 WAV 输出路径改为 session_dir；VideoEncoder 在录制线程中初始化
  - [x] 修改 `_record_loop()` — 录制循环开头初始化 VideoEncoder(FFmpeg pipe)；去掉 JPEG 压缩调用，改直接写 BGR24 → `write_frame()`；画质缩放 `cv2.resize` 移到写 pipe 前
  - [x] 修改 `_stop_and_encode()` — 拆分：录制线程 join 后 → 停止音频 → 取消则 cleanup_session → 保存则 `_finalize()` 线程
  - [x] 实现 `_finalize()` — 音频有则 FFmpeg mux（`-c:v copy -c:a aac`）→ `shutil.move` 到最终路径 → `cleanup_session` → `on_saved` 回调
  - [x] 适配 `_mix_audio_if_available()` — 视频路径改为 `self._video_temp_path`
  - [x] 恢复 `RecordMode.WINDOW` 枚举值（取消注释）
  - [x] 恢复 `_WindowLostBridge(QObject)` 信号桥（取消注释）
  - [x] 恢复 `_window_hwnd`、`_window_title` 字段
  - [x] 恢复 `start_window(hwnd)` 方法
  - [x] 恢复 `_get_window_rect(hwnd)` — 使用 GetClientRect + ClientToScreen（非 GetWindowRect）
  - [x] 恢复 `_get_window_title(hwnd)` 方法
  - [x] 恢复 `_record_loop()` 窗口位置跟踪 — 200ms `update_region()` + 窗口丢失 `window_lost.emit()`
  - [x] 集成测试：无音频全屏录制 → 停止后 < 1 秒文件可播放；有音频 → 停止后 1~5 秒含音频
  - [x] 集成测试：取消录制 → session_dir 被清理、无输出文件
  - [x] 集成测试：录制 5 秒 → 视频分辨率/帧率正确 → 播放器可播

#### 窗口录制 UI

- [x] **window_selector.py — 窗口选择器重写**
  - [x] 删除 v1.2 所有注释代码
  - [x] 顶部 `import ctypes; import ctypes.wintypes`（修复 0xC0000409 崩溃）
  - [x] 定义 `_SYSTEM_CLASSES` 类名黑名单（Shell_TrayWnd, Progman, Button 等）
  - [x] 实现 `_enum_windows()` — EnumWindows 回调 + WNDENUMPROC；过滤：可见 + 有标题 + 无 TOOLWINDOW + 类名白名单 + 排除自身；返回 `[(hwnd, title, is_minimized)]`
  - [x] 实现 WindowSelector(QDialog) UI — QListWidget + [刷新][选择][取消] 按钮
  - [x] 实现双击选择 / 刷新 / 取消关闭交互
  - [x] 实现最小化窗口选择 → SW_RESTORE + SetForegroundWindow
  - [x] 集成测试：列表中出现 Chrome/记事本等，不出现任务栏和系统控件

- [x] **window_highlighter.py — 边框高亮重写**
  - [x] 删除 v1.2 所有注释代码
  - [x] `import ctypes; import ctypes.wintypes` + `Qt.WA_TransparentForMouseEvents`（修复拼写 Bug）
  - [x] 实现 `__init__` — FramelessWindowHint | StaysOnTop | Tool | WindowTransparentForInput + WA_TransparentForMouseEvents
  - [x] 实现 `paintEvent` — QPainter 绿色虚线边框（#00e676, 2px, Qt.DashLine）
  - [x] 实现 `_update_position()` — GetWindowRect → setGeometry；失败则 hide_highlight（窗口关闭不崩溃）
  - [x] 实现 `show_highlight()` / `hide_highlight()` — 显示/隐藏 + 100ms QTimer 启停
  - [x] 集成测试：边框跟随 Notepad 窗口移动；关闭 Notepad 后边框消失不崩溃

#### 入口集成

- [x] **main.py — 窗口录制恢复 + DPI**
  - [x] 在 `main()` 中 `QApplication` 创建前添加 DPI 两行：`AA_EnableHighDpiScaling` + `AA_UseHighDpiPixmaps`
  - [x] 恢复 `_HotkeyBridge.window_requested` 信号及快捷键注册（Ctrl+Shift+W → `_setup_hotkeys()`）
  - [x] 恢复 `_WindowBridge`、`_WindowLostBridge` 信号桥类定义
  - [x] 实现 `_on_start_window()` — WindowSelector 创建显示（保存为 `self._window_selector` 防 GC）
  - [x] 实现 `_on_window_selected(hwnd, title)` — 最小化恢复 + SetForeground → WindowHighlighter → 倒计时/直接录制
  - [x] 实现 `_do_start_window(hwnd)` — `recorder.start_window()` → `_update_highlight_state()`
  - [x] 实现 `_on_window_lost(reason)` — closed 自动停止保存 + 托盘通知；minimized 暂停 + 托盘通知
  - [x] 实现 `_on_window_cancelled()` — `self._window_selector = None` 清理引用
  - [x] 恢复 `__init__` 中 `_window_bridge`、`_window_lost_bridge` 信号连接
  - [x] 恢复 `_handle_saved()` / `_on_exit()` / `_on_cancel_recording()` 中 `_window_highlighter = None` 清理
  - [x] 集成测试：窗口选择→高亮→录制→停止 全链路

#### UI 小改

- [x] **settings_dialog.py — 恢复窗口录制快捷键**
  - [x] 取消注释 `_shortcut_window` 控件定义行
  - [x] 恢复 `_load_config()` 中 `shortcut_window` 加载
  - [x] 恢复 `_save_config()` 中 `shortcut_window` 保存
  - [x] 手工验证：打开设置→窗口录制快捷键出现→修改→保存→重启→新快捷键生效

- [x] **tray_icon.py — 恢复窗口录制菜单项**
  - [x] 恢复 `_build_idle_menu()` 中 `pystray.MenuItem("🖥 窗口录制", ...)` 行
  - [x] 恢复 `_SignalBridge.start_window_requested` 信号
  - [x] 恢复 `_handle_start_window()` 回调
  - [x] 手工验证：右键托盘→菜单中有"窗口录制"→点击→弹窗选择器

#### 打包与优化

- [x] **build_std.spec — 打包体积优化**
  - [x] excludes 列表添加不需要的 Qt 模块（Bluetooth/Designer/Help/Location/Multimedia/Qml/Quick/Sensors/SerialPort/Sql/Svg/Test/WebChannel/WebEngine/WebSockets/Xml 等）
  - [x] 二进制过滤排除：Qt DLL（Quick/Qml/Network/DBus/Svg/WebSockets/OpenGL）、ANGLE 软件渲染（opengl32sw/d3dcompiler_47/libGLESv2/libEGL）、OpenCV videoio ffmpeg DLL、PIL AVIF/WebP 编码器、Qt 插件（svg/webp/tiff/icns/ico/tga/wbmp/webgl/minimal）
  - [x] 打包体积从 333MB 优化至 259MB（减少 74MB / 22%）
  - [x] 验证打包：`pyinstaller build_std.spec` 成功
  - [x] 验证启动：`dist/QuickRec/QuickRec.exe` 启动正常（76MB 内存）
  - [x] 验证体积：当前 259MB，目标 < 250MB（核心依赖 cv2 73MB + ffmpeg 97MB + numpy 27MB + Qt 18MB ≈ 215MB 不可压缩，接受 259MB）

### v1.3 开发阶段

| 阶段 | 内容 | 依赖 | 状态 |
|-----|------|------|------|
| 1 | video_encoder.py + temp_cleaner.py + disk_checker.py | 无 | ✅ |
| 2 | window_selector.py + window_highlighter.py | 无 | ✅ |
| 3 | recorder_manager.py 重构 | 1 | ✅ |
| 4 | main.py 窗口录制集成 | 2, 3 | ✅ |
| 5 | settings_dialog.py + tray_icon.py 小改 | 无 | ✅ |
| 6 | build_std.spec 优化 + DPI | 无 | ✅ |
| 7 | 集成测试 + 打包验证 | 全部 | ✅ |

**并行策略**：阶段 1-2 和 5-6 全部可并行启动；阶段 3 依赖阶段 1；阶段 4 依赖阶段 2+3。阶段 7 最后。

---

## v1.4 进度 ✅ 已完成 / 待发布

> v1.4 目标：稳定性与工程化大型优化。不新增用户可见功能；先修测试基线，再建立 CI/Lint/mypy，再做架构解耦，最后完成运行时稳定性与发布收口。
> 当前结果：默认测试 `175 passed / 23 deselected`；打包体积 `257.74MB`；稳定性优先恢复 cv2，保留 OpenCV videoio ffmpeg 排除；已完成发布前手动验收。

### v1.4 计划 review 结论

- [x] PRD 已更新：`doc/PRD-QuickRec.md` 新增 v1.4 章节、质量门槛、里程碑和风险
- [x] TecDesign 已新增：`doc/Tec-design-v1.4.md`，覆盖测试基线、工程配置、CI、架构解耦、公共事件、运行时稳定性和打包验证
- [x] dev-plan 已新增：`doc/dev-plan-v1.4.md`，按 M1-M4 拆分阶段任务
- [x] v1.4 实施已完成
- [x] v1.4 测试用例文档已创建：`doc/v1.4-test-cases.md`
- [x] 实际 bug 修复已写入 `doc/bugfix-log.md`，当前至 Bug #60
- [x] README 已更新至 v1.4 发布口径

### v1.4 发布收口结果

| 项目 | 结果 |
| --- | --- |
| 默认测试 | `175 passed / 23 deselected` |
| ruff | `python -m ruff check .` 通过 |
| mypy | `python -m mypy` 通过 |
| compileall | `python -m compileall -q src tests` 通过 |
| packaging 测试 | `5 passed` |
| 打包产物 | `dist/QuickRec/QuickRec.exe` |
| 打包体积 | `257.74MB` |
| 体积结论 | 稳定性优先，恢复 cv2；继续排除 `opencv_videoio_ffmpeg*.dll` |
| tag | 准备发布 `v1.4` |

> 下方 M1-M4 checklist 保留为本轮开发的任务颗粒度记录；实际完成状态以本节发布收口结果和 `doc/v1.4-test-cases.md` 为准。

### v1.4 模块进度

#### M1 工程基线修复

- [ ] **VideoEncoder 测试修复 (`tests/test_video_encoder.py`)**
  - [ ] 阅读 `src/recorder/video_encoder.py` 当前构造函数和错误处理路径
  - [ ] 将旧测试的 3 参数构造改为显式传入 `ffmpeg_path`
  - [ ] 新增 mock Popen 夹具
  - [ ] 验证 FFmpeg 命令包含 `rawvideo`
  - [ ] 验证 FFmpeg 命令包含 `bgr24`
  - [ ] 验证 FFmpeg 命令包含 `libx264`
  - [ ] 验证 FFmpeg 命令包含 `crf=23`
  - [ ] 验证 FFmpeg 命令包含 `preset=superfast`
  - [ ] 验证 FFmpeg 命令包含 `yuv420p`
  - [ ] 新增 FFmpeg 路径为空/不存在测试
  - [ ] 新增 Popen 启动失败测试
  - [ ] 新增 BrokenPipeError 测试，确认 `write_frame()` 返回 False
  - [ ] 新增 close 后写入返回 False 测试
  - [ ] 将真实 MP4 编码测试标记为 `hardware`
  - [ ] 默认测试不依赖本机 FFmpeg

- [ ] **RecorderManager 异步 stop 测试修复 (`tests/test_recorder_manager.py`)**
  - [ ] 梳理 `RecorderManager.stop()` 当前异步契约
  - [ ] 移除“stop 立即返回 mp4 路径”的旧断言
  - [ ] 使用状态/回调断言保存完成
  - [ ] 增加 `RECORDING -> STOPPING -> SAVING -> IDLE` 状态流测试
  - [ ] 增加 `PAUSED -> STOPPING -> SAVING -> IDLE` 状态流测试
  - [ ] 增加取消路径测试：`stop(cancel=True)` 不触发成功保存
  - [ ] 增加重复 stop 测试：STOPPING/SAVING 不启动多个后台线程
  - [ ] 增加 `wait_until_idle(timeout)` 正常完成测试
  - [ ] 增加 `wait_until_idle(timeout)` 超时测试
  - [ ] 使用 fake capturer 隔离 dxcam
  - [ ] 使用 fake encoder 隔离 FFmpeg
  - [ ] 使用 fake audio capturer 隔离音频设备

- [ ] **ScreenCapturer 测试分层 (`tests/test_screen_capturer.py`)**
  - [ ] 将生命周期测试与真实捕获测试拆开
  - [ ] 使用 monkeypatch 模拟 `dxcam.create()`
  - [ ] 模拟 camera.start()
  - [ ] 模拟 camera.get_latest_frame()
  - [ ] 模拟 camera.stop()
  - [ ] 模拟 camera.release()
  - [ ] 验证未 start 时 `capture_frame()` 的契约
  - [ ] 验证 start 后可获取 fake frame
  - [ ] 验证 `update_region()` 在 region 不变时不重建 camera
  - [ ] 验证 `update_region()` 失败时清理 `_camera`
  - [ ] 验证 `update_region()` 失败时清理 `_started`
  - [ ] 增加 close 幂等性测试
  - [ ] 将真实 dxcam 捕获测试标记为 `hardware`
  - [ ] 默认测试不启动真实 dxcam

- [ ] **pytest marker 与 coverage (`pyproject.toml`)**
  - [ ] 新增 `pyproject.toml`
  - [ ] 配置 `testpaths = ["tests"]`
  - [ ] 配置 `pythonpath = ["src"]` 或等价导入方案
  - [ ] 定义 `unit` marker
  - [ ] 定义 `ui` marker
  - [ ] 定义 `hardware` marker
  - [ ] 定义 `packaging` marker
  - [ ] 给纯逻辑测试补 `unit` 或保持默认归类
  - [ ] 给 PyQt widget 测试补 `ui`
  - [ ] 给 dxcam/音频/真实桌面测试补 `hardware`
  - [ ] 给 PyInstaller/产物冒烟测试补 `packaging`
  - [ ] 接入 `pytest-cov`
  - [ ] 配置 coverage source 为 `src`
  - [ ] 配置 coverage branch 统计
  - [ ] 配置 coverage fail_under = 80
  - [ ] 移除或减少测试文件中的 `sys.path.insert`
  - [ ] 默认命令 `python -m pytest -m "not hardware and not packaging"` 全绿
  - [ ] coverage 总覆盖率 >= 80%

#### M2 CI / Lint / mypy

- [ ] **工程配置 (`pyproject.toml`)**
  - [ ] 新增 pytest 配置
  - [ ] 新增 coverage 配置
  - [ ] 新增 ruff 配置
  - [ ] 新增 mypy 配置
  - [ ] 配置 Python 目标版本为 3.12
  - [ ] 配置 ruff line-length
  - [ ] 配置 ruff lint 基础规则集
  - [ ] 配置 mypy `ignore_missing_imports = true`
  - [ ] 配置 mypy 分阶段收紧策略
  - [ ] 本地命令可读取统一配置

- [ ] **ruff 格式与 lint**
  - [ ] 安装/加入开发依赖 `ruff`
  - [ ] 运行 `python -m ruff check .` 获取问题列表
  - [ ] 修复 import 顺序问题
  - [ ] 修复未使用导入问题
  - [ ] 修复低风险 pyupgrade 问题
  - [ ] 对高风险历史问题显式忽略或暂缓
  - [ ] 运行 `python -m ruff format --check .`
  - [ ] 确认不大面积重排 UI 样式字符串
  - [ ] ruff check 通过
  - [ ] ruff format check 通过

- [ ] **mypy 类型检查**
  - [ ] 安装/加入开发依赖 `mypy`
  - [ ] 先覆盖 `src/config.py`
  - [ ] 先覆盖 `src/utils/*.py`
  - [ ] 覆盖后续新增 `recorder/state_machine.py`
  - [ ] 覆盖后续新增事件接口模块
  - [ ] 对 PyQt5 缺失类型做 ignore
  - [ ] 对 pynput 缺失类型做 ignore
  - [ ] 对 dxcam 缺失类型做 ignore
  - [ ] 控制 Any 扩散
  - [ ] mypy 命令本地通过

- [ ] **GitHub Actions (`.github/workflows/ci.yml`)**
  - [ ] 新增 `.github/` 目录
  - [ ] 新增 `.github/workflows/` 目录
  - [ ] 新增 `ci.yml`
  - [ ] 配置 checkout
  - [ ] 配置 Python 3.12
  - [ ] 安装 `requirements.txt`
  - [ ] 安装开发依赖 `pytest-cov ruff mypy`
  - [ ] 执行 `python -m compileall -q src`
  - [ ] 执行 `python -m ruff format --check .`
  - [ ] 执行 `python -m ruff check .`
  - [ ] 执行 `python -m mypy src` 或配置指定模块
  - [ ] 执行默认 pytest
  - [ ] 执行 coverage >= 80
  - [ ] CI 不运行 `hardware` 测试
  - [ ] CI 不运行 `packaging` 测试
  - [ ] GitHub Actions 至少成功运行一次

#### M3 架构解耦

- [ ] **应用控制器拆分 (`src/app_controller.py`，建议)**
  - [ ] 识别 `QuickRecApp.__init__()` 中的模块初始化职责
  - [ ] 识别 `QuickRecApp.run()` 中的应用生命周期职责
  - [ ] 识别 `_on_exit()` 中的退出收尾职责
  - [ ] 新增 `AppController` 类框架
  - [ ] 将 QApplication 生命周期装配迁移到 `AppController`
  - [ ] 将托盘启动/隐藏收尾迁移到 `AppController`
  - [ ] 将快捷键启动/停止收尾迁移到 `AppController`
  - [ ] `main.py` 保留 DPI 设置
  - [ ] `main.py` 保留异常兜底
  - [ ] `main.py` 保留最小入口
  - [ ] 应用启动行为保持不变
  - [ ] 应用退出行为保持不变

- [ ] **录制工作流拆分 (`src/workflows/recording_workflow.py`，建议)**
  - [ ] 新增 `src/workflows/` 目录
  - [ ] 新增 `RecordingWorkflow` 类框架
  - [ ] 迁移全屏录制入口流程
  - [ ] 迁移区域录制入口流程
  - [ ] 迁移窗口录制入口流程
  - [ ] 抽取共享磁盘预检查步骤
  - [ ] 抽取共享倒计时步骤
  - [ ] 抽取共享工具栏显示/隐藏步骤
  - [ ] 抽取共享托盘状态更新步骤
  - [ ] 抽取暂停/继续流程
  - [ ] 抽取停止录制流程
  - [ ] 抽取消录制流程
  - [ ] 抽取保存完成处理
  - [ ] 抽取保存失败处理
  - [ ] 全屏/区域/窗口录制入口行为保持一致
  - [ ] 倒计时取消回归通过
  - [ ] 暂停/继续回归通过
  - [ ] 停止保存回归通过

- [ ] **状态机与公共事件 (`src/recorder/state_machine.py`, `src/recorder/events.py`，建议)**
  - [ ] 新增 `RecorderStateMachine`
  - [ ] 定义 IDLE 状态转移规则
  - [ ] 定义 RECORDING 状态转移规则
  - [ ] 定义 PAUSED 状态转移规则
  - [ ] 定义 STOPPING 状态转移规则
  - [ ] 定义 SAVING 状态转移规则
  - [ ] 定义非法状态转移返回或异常策略
  - [ ] 新增 `RecorderEventType`
  - [ ] 新增 `RecorderEvent`
  - [ ] 定义 `state_changed` 事件
  - [ ] 定义 `recording_saved` 事件
  - [ ] 定义 `recording_failed` 事件
  - [ ] 定义 `window_lost` 事件
  - [ ] 定义 `disk_warning` 事件
  - [ ] 为状态机补单元测试
  - [ ] 为事件对象补单元测试
  - [ ] 移除 UI 对 `_window_lost_bridge` 等私有字段的访问

- [ ] **通知服务 (`src/services/notification_service.py`，建议)**
  - [ ] 新增 `src/services/` 目录
  - [ ] 新增 `NotificationService` 类框架
  - [ ] 统一保存成功提示
  - [ ] 统一保存失败提示
  - [ ] 统一 FFmpeg 缺失/失败提示
  - [ ] 统一磁盘空间不足提示
  - [ ] 统一窗口不可录制提示
  - [ ] 统一窗口关闭/最小化提示
  - [ ] 保留 winotify → pystray 降级链
  - [ ] 通知文案集中管理

- [ ] **资源生命周期 (`src/recorder/resource_lifecycle.py`，建议)**
  - [ ] 新增资源生命周期管理类
  - [ ] 封装 dxcam capturer 创建
  - [ ] 封装 VideoEncoder 创建
  - [ ] 封装 AudioCapturer 创建
  - [ ] 封装 session_dir 创建
  - [ ] 封装 capturer 关闭
  - [ ] 封装 encoder close/wait
  - [ ] 封装 audio stop
  - [ ] 封装 session cleanup
  - [ ] 将 `timeBeginPeriod(1)` 改为显式 acquire
  - [ ] 将 `timeEndPeriod(1)` 改为显式 release
  - [ ] 连续录制释放顺序可测试

- [ ] **窗口录制服务 (`src/recorder/window_recording_service.py`，建议)**
  - [ ] 封装 hwnd 有效性检查
  - [ ] 封装窗口标题获取
  - [ ] 封装客户区 rect 获取
  - [ ] 封装窗口最小化判断
  - [ ] 封装窗口关闭判断
  - [ ] 封装特殊窗口失败 reason
  - [ ] 封装前台置顶/恢复协作逻辑
  - [ ] 特殊窗口失败不阻塞主线程
  - [ ] 特殊窗口失败不崩溃

- [ ] **RecorderManager 收窄 (`src/recorder/recorder_manager.py`)**
  - [ ] 保留录制引擎门面职责
  - [ ] 委托状态转移给状态机
  - [ ] 委托资源创建/释放给 resource_lifecycle
  - [ ] 委托窗口判断给 window_recording_service
  - [ ] 通过公开事件发出状态和结果
  - [ ] 不再承担 UI 信号桥职责
  - [ ] 默认测试全绿
  - [ ] 三种录制模式回归通过

#### M4 运行时稳定性与发布收口

- [ ] **FFmpeg 异常路径**
  - [ ] 录制启动前检查 ffmpeg_path 非空
  - [ ] 录制启动前检查 ffmpeg_path 存在
  - [ ] 录制启动前检查 ffmpeg_path 可执行或可启动
  - [ ] 捕获 Popen 启动异常
  - [ ] Popen 启动异常转换为 `recording_failed`
  - [ ] 编码中断时停止录制循环
  - [ ] 编码中断时发出失败事件
  - [ ] `_finalize()` move 失败可诊断
  - [ ] `_mix_audio()` 失败可诊断
  - [ ] FFmpeg 缺失时不进入 RECORDING
  - [ ] FFmpeg 失败不卡死后台线程

- [ ] **临时文件清理与系统计时器**
  - [ ] 应用启动时调用 `TempCleaner.cleanup_stale()`
  - [ ] 为 cleanup_stale 启动接入补测试或验证
  - [ ] 正常录制结束清理 session_dir
  - [ ] 取消录制清理 session_dir
  - [ ] 保存失败清理 session_dir 或保留诊断策略明确
  - [ ] 封装 `timeBeginPeriod(1)`
  - [ ] 封装 `timeEndPeriod(1)`
  - [ ] 正常退出释放 timer period
  - [ ] 异常退出路径尽量释放 timer period

- [ ] **录制中磁盘持续监控**
  - [ ] 设计检查间隔（建议 30 秒）
  - [ ] 避免每帧 IO 检查
  - [ ] mock `shutil.disk_usage` 测试 ok 状态
  - [ ] mock `shutil.disk_usage` 测试 warn 状态
  - [ ] mock `shutil.disk_usage` 测试 block 状态
  - [ ] warn 状态发出 `disk_warning`
  - [ ] block 状态执行安全停止策略
  - [ ] block 状态优先保存已录内容
  - [ ] 用户提示可感知

- [ ] **退出流程与连续录制**
  - [ ] 为退出流程设置 timeout
  - [ ] 等待录制线程结束
  - [ ] 等待停止线程结束
  - [ ] 等待 finalize 线程结束
  - [ ] 超时时记录当前 recorder state
  - [ ] 超时时记录仍存活线程
  - [ ] 超时时给用户提示或日志
  - [ ] fake capturer/encoder 连续录制 3 轮自动测试
  - [ ] 真实录制连续 3 轮 hardware 冒烟
  - [ ] 退出不无限卡住

- [ ] **特殊窗口失败提示**
  - [ ] 窗口不存在提示稳定
  - [ ] 窗口最小化提示稳定
  - [ ] 客户区无法获取提示稳定
  - [ ] UWP/DWM/游戏窗口失败不崩溃
  - [ ] 失败路径不长时间阻塞 Qt 主线程
  - [ ] 日志记录 hwnd/title/reason

- [ ] **打包与体积分析**
  - [ ] 固化打包命令
  - [ ] 记录 Python 版本
  - [ ] 记录 PyInstaller 版本
  - [ ] 记录依赖版本
  - [ ] 统计 dist/QuickRec 总体积
  - [ ] 统计 FFmpeg 体积
  - [ ] 统计 OpenCV/cv2 体积
  - [ ] 统计 NumPy 体积
  - [ ] 统计 Qt/PyQt5 体积
  - [ ] 统计其他依赖体积
  - [ ] 评估 PyInstaller excludes 优化
  - [ ] 评估 UPX/strip 配置
  - [ ] 评估资源裁剪
  - [ ] 不外置 FFmpeg
  - [ ] 不替换核心依赖
  - [ ] 打包产物可启动
  - [ ] 托盘图标可显示
  - [ ] 设置对话框可打开并保存
  - [ ] 全屏录制可冒烟
  - [ ] 区域录制可冒烟
  - [ ] 窗口录制可冒烟
  - [ ] 退出后无明显残留进程
  - [x] 未达成原 < 200MB 目标时，记录体积构成和阻塞原因

### v1.4 开发阶段

| 阶段 | 内容 | 依赖 | 状态 |
|-----|------|------|------|
| M1 | 工程基线修复：测试漂移修复 + marker + coverage | PRD / TecDesign / dev-plan | ✅ 完成 |
| M2 | CI / Lint / mypy：pyproject + ruff + mypy + GitHub Actions | M1 默认测试趋稳 | ✅ 完成 |
| M3 | 架构解耦：RecordingWorkflow + 状态机 + 事件 + 服务边界初步拆分 | M1, M2 | ✅ 完成 |
| M4 | 运行时稳定性与发布收口：异常路径 + 连续录制 + 打包冒烟 + 体积分析 | M3 | ✅ 完成 |

**并行策略**：M1 内部的 VideoEncoder / RecorderManager / ScreenCapturer 测试修复可并行；M2 的 pyproject / ruff / mypy / CI 可并行推进，但必须等 M1 默认测试趋稳后收紧门槛；M3 必须在 M1 后进行，避免无回归网重构；M4 依赖 M3 的公共事件和资源生命周期边界。
