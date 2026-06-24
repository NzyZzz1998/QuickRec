# QuickRec v1.3 开发计划

> 版本: v1.3
> 创建时间: 2026-06-18
> 状态: 开发中
> 前置版本: v1.2（已完成，tag v1.2，窗口录制延期至本版本）

---

## 1. 开发总览

### 1.1 v1.3 目标功能

| 编号 | 功能 | 说明 | 涉及模块 |
|-----|------|------|---------|
| E1 | H.264 实时编码 | 零拷贝管线：dxcam → FFmpeg pipe → libx264 MP4；去除 JPEG 临时文件后编码 | video_encoder, recorder_manager |
| F3 | 指定窗口录制（深度重写） | 删除 v1.2 注释代码从零重写；简化窗口丢失处理（关闭→自停保存，最小化→暂停+托盘通知） | window_selector, window_highlighter, recorder_manager, main |
| R3 | 临时文件三层清理 | 会话目录隔离（%TEMP%/QuickRec/session_<pid>_<ts>/）+ atexit + 启动扫描 | temp_cleaner, recorder_manager, main |
| P9 | 磁盘空间不足预警 | 开始录制前检查；< 1GB 预警可选继续；< 200MB 阻断录制 | disk_checker, main |
| S5 | 打包体积优化 | PyInstaller excludes 排除不需要的 Qt 插件，目标 < 150MB | build_std.spec |
| R1 | DPI 缩放适配 | QApplication 高 DPI 属性设置 | main |
| — | 窗口录制快捷键恢复 | 取消注释 v1.2 遗留代码 | settings_dialog |
| — | 窗口录制菜单恢复 | 取消注释 v1.2 遗留的托盘菜单项 | tray_icon |

### 1.2 不变模块

| 模块 | 说明 |
|------|------|
| area_selector.py | 无需修改 |
| toolbar.py | 无需修改（倒计时/结果条 v1.2 已完成） |
| audio_capturer.py | 无需修改（仅输出路径改为 session_dir，由 recorder_manager 传参） |
| screen_capturer.py | 无需修改（update_region v1.2 已实现） |
| hotkey_manager.py | 无需修改（仅注册新 shortcut_window 快捷键） |
| config.py | 无需修改（shortcut_window 等 v1.2 已添加） |
| file_namer.py | 无需修改 |
| autostart.py | 无需修改 |
| click_highlighter.py | 无需修改 |

### 1.3 新增依赖

无。v1.3 所有新功能使用 Python 标准库（`tempfile`, `atexit`, `shutil`, `os.kill`, `ctypes.wintypes`）或已有依赖（`PyQt5`, `pynput`）实现。H.264 编码使用已内置的 FFmpeg（v1.1 引入）。

---

## 2. 开发阶段

### 阶段 1：编码 + 工具基础（无依赖，可并行）

**目标**：为录制管线重构提供 FFmpeg pipe 编码器、临时文件管理器、磁盘预警系统。

#### 1.1 video_encoder.py — FFmpeg pipe H.264 重写

**改动量**：中（删除旧 OpenCV 实现，重写为 FFmpeg subprocess，~100 行）

**内容**：
- 删除 `cv2.VideoWriter` 相关代码
- 实现 `_build_cmd()` — 构造 `ffmpeg -f rawvideo -pix_fmt bgr24 -i pipe:0 -c:v libx264 -crf 23 -preset medium -pix_fmt yuv420p {output}`
- 实现 `__init__(output_path, fps, frame_size, ffmpeg_path)` — `subprocess.Popen(cmd, stdin=PIPE)`
- 实现 `write_frame(frame: np.ndarray) -> bool` — `frame.tobytes()` 写入 stdin，捕获 `BrokenPipeError`
- 实现 `close() -> bool` — stdin.close + proc.wait(30s) + 检查 returncode
- 实现 `__del__()` — terminate 保底
- 错误处理：FileNotFoundError（抛异常给调用方）、BrokenPipeError（write_frame 返回 False）、TimeoutExpired（kill + 返回 False）

**验证**：
- [ ] mock Popen 验证命令行参数拼接（帧尺寸、帧率、CRF=23、preset=medium、yuv420p）
- [ ] 写入 100 帧 1920×1080 BGR24 → 输出可播放 H.264 MP4 → 视频时长正确
- [ ] close 后 write_frame 返回 False，不抛异常
- [ ] 传入不存在的 ffmpeg 路径 → `__init__` 抛出 FileNotFoundError

#### 1.2 temp_cleaner.py — 三层临时文件清理（新增）

**改动量**：小（全新工具模块，~70 行）

**内容**：
- `TempCleaner.BASE_DIR = os.path.join(tempfile.gettempdir(), "QuickRec")`
- `create_session_dir()` — `makedirs("session_{pid}_{ts}")`，返回绝对路径
- `cleanup_session(dir)` — `shutil.rmtree(dir)`，忽略 OSError
- `_is_pid_alive(pid)` — `os.kill(pid, 0)` 不依赖 psutil
- `cleanup_stale()` — 遍历 session_* 目录，解析 PID，清理非活跃进程目录（跳过当前 PID）
- `register_atexit(dir)` — `atexit.register(cleanup_session, dir)`

**验证**：
- [ ] `create_session_dir()` 返回路径存在，命名包含当前 PID
- [ ] `cleanup_session()` 删除目录
- [ ] `cleanup_stale()` 删除 dead PID 目录，保留 live PID 目录，保留当前进程目录
- [ ] `register_atexit()` 后正常退出 → 目录被自动删除

#### 1.3 disk_checker.py — 磁盘空间预警（扩展）

**改动量**：小（新增 2 个常量 + 1 个函数 + 1 个 Qt 对话框，~40 行新增）

**内容**：
- 新增 `WARN_THRESHOLD_MB = 1024`、`BLOCK_THRESHOLD_MB = 200`
- 实现 `check_before_recording(save_path) -> ("ok"|"warn"|"block", free_mb)` — 用现有 `get_free_space()` 获取空间后转 MB 对比阈值
- 实现 `show_disk_warning(free_mb, block, parent) -> bool` — block=True 用 `QMessageBox.critical`（仅确定），block=False 用 `QMessageBox.warning`（Yes/No）

**验证**：
- [ ] mock `get_free_space` 返回 800MB → `check_before_recording` 返回 `("warn", 800)`
- [ ] mock `get_free_space` 返回 150MB → `check_before_recording` 返回 `("block", 150)`
- [ ] 阈值边界：1024MB → "warn"，199MB → "block"

---

### 阶段 2：窗口录制 UI（无依赖，可与阶段 1 并行）

**目标**：重写窗口选择器和边框高亮，修复 v1.2 所有已知崩溃 bug。

#### 2.1 window_selector.py — 窗口选择器重写

**改动量**：中（删除 v1.2 所有注释代码，从零重写，~150 行）

**内容**：
- 顶部 `import ctypes; import ctypes.wintypes`（修复 0xC0000409 崩溃）
- `_SYSTEM_CLASSES` 类名黑名单（Shell_TrayWnd, Progman, WorkerW, Button, ComboBox, tooltips_class32 等 12 类）
- `_enum_windows()` — WNDENUMPROC 回调 + EnumWindows；过滤：可见 + 有标题 + 无 TOOLWINDOW + 类名不在黑名单
- WindowSelector(QDialog) UI — QListWidget + [刷新] [选择] [取消] 按钮
- 双击列表项 / 点击选择 → `window_selected.emit(hwnd, title, is_minimized)`
- 最小化窗口选择 → SW_RESTORE + sleep 0.1s + SetForegroundWindow
- 窗口关闭(X) → `cancelled.emit()`

**验证**：
- [ ] 对话框列表显示 Chrome/记事本等正常窗口
- [ ] 不显示任务栏、桌面、系统控件
- [ ] 双击触发 window_selected 信号
- [ ] 最小化窗口被选中后自动恢复并前置

#### 2.2 window_highlighter.py — 边框高亮重写

**改动量**：小（删除 v1.2 所有注释代码，从零重写，~60 行）

**内容**：
- 窗口标志：`FramelessWindowHint | WindowStaysOnTopHint | Tool | WindowTransparentForInput`
- `setAttribute(Qt.WA_TransparentForMouseEvents, True)` — **注意必须是 Events 非 Input**（v1.2 Bug）
- `paintEvent()` — QPen(#00e676, 2px, DashLine) 绘制绿色虚线矩形
- `_update_position()` — GetWindowRect → setGeometry；失败时 hide_highlight（窗口关闭不崩溃）
- `show_highlight()` → show + timer.start(100)
- `hide_highlight()` → timer.stop + hide

**验证**：
- [ ] 绿色虚线边框跟随 Notepad 窗口移动
- [ ] 关闭 Notepad → 边框消失不崩溃
- [ ] 边框不拦截鼠标事件（穿透可点击下层的窗口按钮）

---

### 阶段 3：录制管线重构（依赖：阶段 1）

**目标**：去掉 JPEG 临时文件方案，改为 FFmpeg pipe 实时编码；恢复窗口录制模式。

#### 3.1 recorder_manager.py — 录制管线重构

**改动量**：大（删除 JPEG 编码全链路 + 新增 pipe 编码 + 恢复窗口模式 + 接入 TempCleaner，~200 行变更）

**删除**：
- `_JPEG_QUALITY`、`_JPEG_PARAMS` 常量
- `_temp_file`、`_temp_file_handle`、`_total_frames` 字段
- `_compress_frame()` 方法
- `_encode_loop()` 方法（JPEG→OpenCV mp4v 编码循环）
- `_cleanup_temp_file()` 方法

**新增**：
- `_session_dir`、`_video_temp_path`、`_encoder`(VideoEncoder)、`_finalize_thread` 字段
- `_finalize()` 方法 — 音频混合 → shutil.move → cleanup_session → on_saved 回调

**修改 `_start()`**：
- 创建 session 目录（`TempCleaner.create_session_dir()` + `register_atexit`）
- 音频 WAV 输出路径改为 `self._session_dir`（通过 `AudioCapturer(output_dir=self._session_dir)`）
- 不再创建 .tmp 文件；VideoEncoder 在录制线程中初始化

**修改 `_record_loop()`**：
- 录制循环开头 `VideoEncoder(self._video_temp_path, fps, encode_size, ffmpeg_path)`
- 去掉 `_compress_frame()`，直接 `self._encoder.write_frame(frame)` 写 BGR24 到 pipe
- 画质缩放 `cv2.resize` 移到写 pipe 前（在录制线程，而非编码线程）
- 结束：`self._encoder.close()`

**修改 `_stop_and_encode()`**：
- 等待录制线程 join → 停止音频 → 取消则 `cleanup_session()` → 保存则启动 `_finalize()` 线程

**恢复窗口录制**：
- 取消注释 `RecordMode.WINDOW` 枚举值
- 取消注释 `_WindowLostBridge(QObject)` 信号桥类
- 恢复 `_window_hwnd`、`_window_title` 字段
- 恢复 `start_window(hwnd)` 方法
- 恢复 `_get_window_rect(hwnd)` — GetClientRect + ClientToScreen（非 GetWindowRect，避免最大化负坐标）
- 恢复 `_get_window_title(hwnd)`
- 恢复 `_record_loop()` 中窗口位置跟踪 — 200ms 间隔 `update_region()` + 窗口丢失时 `window_lost.emit()`

**验证**：
- [ ] 无音频全屏录制 5 秒 → 停止后 < 1 秒文件可播放 → 视频时长/分辨率正确
- [ ] 有音频（系统声音）录制 5 秒 → 停止后 1~5 秒 → 文件含音频轨道
- [ ] 取消录制 → session_dir 被清理 → 无输出文件
- [ ] 窗口录制：选择 Notepad → 录制 5 秒 → 视频内容为 Notepad 窗口
- [ ] 录制中关闭 Notepad → 录制自动停止 → 托盘通知 → 文件保存

---

### 阶段 4：主程序集成（依赖：阶段 2 + 阶段 3）

**目标**：在 main.py 中恢复窗口录制流程 + 接入磁盘预警 + DPI 设置。

#### 4.1 main.py — 窗口录制恢复 + DPI + 磁盘检查

**改动量**：中（恢复 v1.2 注释代码 + 简化窗口丢失 + 新增 DPI/磁盘检查勾子，~100 行变更）

**DPI 设置（2 行）**：
```python
# main() 函数中，QApplication 创建之前
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
```

**磁盘检查勾子**：
- 实现 `_check_disk_space() -> bool` 方法
- 在 `_on_start_fullscreen()`、`_on_start_region()`、`_on_start_window()` 三种入口调用 `_check_disk_space()`，返回 False 则不启动录制

**恢复窗口录制**：
- 恢复 `_HotkeyBridge.window_requested` 信号（取消注释）
- 恢复 `_WindowBridge`、`_WindowLostBridge` 信号桥类定义及实例化
- 恢复 `_setup_hotkeys()` 中 `shortcut_window` 快捷键注册
- 实现 `_on_start_window()` — 创建 `WindowSelector`（保存为 `self._window_selector` 防 GC）
- 实现 `_on_window_selected(hwnd, title)` — 最小化恢复 + SetForeground → WindowHighlighter → 倒计时/直接录制
- 实现 `_do_start_window(hwnd)` — `recorder.start_window(hwnd)` + `_update_highlight_state()`
- 实现 `_on_window_lost(reason)` — **简化版**：closed→`_on_stop_recording()`+托盘通知；minimized→`pause()`+托盘通知
- 实现 `_on_window_cancelled()` — `self._window_selector = None`
- 在 `_handle_saved()`、`_on_exit()`、`_on_cancel_recording()` 中恢复 `_window_highlighter = None` 清理

**托盘回调**：
- `callbacks` 字典中 `"start_window"` 项已存在（v1.2 已添加但从未生效）

**验证**：
- [ ] Ctrl+Shift+W 弹出窗口选择对话框
- [ ] 选择窗口后出现绿色边框 + 开始录制
- [ ] 录制中关闭目标窗口 → 自动停止 + 托盘通知"录制窗口已关闭，视频已保存"
- [ ] 录制中最小化目标窗口 → 自动暂停 + 托盘通知
- [ ] 倒计时开启时窗口录制 → 3→2→1 → 开始录制
- [ ] 磁盘空间 < 200MB → 点开始录制 → 阻断弹窗 → 不录制
- [ ] 磁盘空间 < 1GB → 点开始录制 → 警告弹窗 → 选"是"继续 / 选"否"取消
- [ ] 150% DPI 缩放 → 工具栏/设置对话框不夸大小、控件不重叠

---

### 阶段 5：设置 + 托盘小改（无依赖，可与阶段 4 并行）

**目标**：取消注释 v1.2 遗留的窗口录制快捷键和菜单项。

#### 5.1 settings_dialog.py — 恢复窗口录制快捷键

**改动量**：极小（取消注释 3 处，~5 行）

**内容**：
- 取消注释 `self._shortcut_window = _ShortcutRecorder("Ctrl+Shift+W")` 控件定义
- 恢复 `_load_config()` 中 `self._shortcut_window.setText(...)` 行
- 恢复 `_save_config()` 中 `self._config.set("shortcut_window", ...)` 行

**验证**：
- [ ] 设置对话框中出现"窗口录制: [Ctrl+Shift+W]"行
- [ ] 点击可录制新快捷键组合
- [ ] 保存后新快捷键生效

#### 5.2 tray_icon.py — 恢复窗口录制菜单项

**改动量**：极小（取消注释 3 处，~5 行）

**内容**：
- 恢复 `_build_idle_menu()` 中 `pystray.MenuItem("🖥 窗口录制", self._on_start_window)` 行
- 取消注释 `_SignalBridge.start_window_requested = pyqtSignal()`
- 恢复 `_handle_start_window()` → `self._callbacks["start_window"]()` 回调

**验证**：
- [ ] 右键托盘图标 → 菜单中显示"🖥 窗口录制"
- [ ] 点击"窗口录制" → 弹出窗口选择对话框

---

### 阶段 6：打包优化（无依赖，独立）

**目标**：减小 PyInstaller 打包体积，从 ~334MB 降至 < 150MB。

#### 6.1 build_std.spec — 排除不需要的 Qt 模块

**改动量**：小（修改 excludes 列表，~20 行）

**排除的 Qt 模块**：
```
Qt5Bluetooth, Qt5Designer, Qt5Help, Qt5Location,
Qt5Multimedia, Qt5MultimediaWidgets, Qt5Qml, Qt5Quick,
Qt5QuickWidgets, Qt5Sensors, Qt5SerialPort, Qt5Sql,
Qt5Svg, Qt5Test, Qt5WebChannel, Qt5WebEngine,
Qt5WebEngineCore, Qt5WebEngineWidgets, Qt5WebSockets, Qt5Xml
```

**验证**：
- [ ] `pyinstaller build_std.spec --noconfirm` 打包成功
- [ ] `dist/QuickRec/QuickRec.exe` 正常启动（不报 Qt5xxx.dll 缺失）
- [ ] 工具栏、托盘菜单、设置对话框功能正常
- [ ] 打包后体积 < 250MB（首次），目标 < 150MB（迭代优化 UPX 参数）

---

### 阶段 7：集成测试与打包验证（依赖：所有模块）

**目标**：全功能验证 + 最终打包。

#### 7.1 功能回归测试

| 测试场景 | 验证点 |
|---------|--------|
| 全屏录制（无音频） | 与 v1.2 行为一致，视频为 H.264 编码 |
| 全屏录制（有音频） | 停止后 ~1-5 秒完成，文件含音频轨道 |
| 区域录制 | 与 v1.2 行为一致 |
| 窗口录制（正常） | 选择窗口 → 绿色边框 → 录制 → 停止 → 视频内容正确 |
| 窗口录制（关闭） | 录制中关闭窗口 → 自动停止 + 托盘通知 → 视频已保存 |
| 窗口录制（最小化） | 录制中最小化 → 自动暂停 + 托盘通知 → 恢复窗口后可继续 |
| 倒计时（全屏/区域/窗口） | 3→2→1 显示正常，ESC 取消，快捷键取消 |
| 鼠标点击高亮 | 与 v1.2 行为一致 |
| 磁盘空间预警 | < 1GB 弹窗可选继续，< 200MB 弹窗阻断 |
| DPI 缩放（150%/200%） | 工具栏/设置对话框大小正常，控件不重叠 |
| 设置对话框 | 窗口录制快捷键出现、可修改、保存生效 |
| 托盘菜单 | 空闲菜单含"🖥 窗口录制"，点击弹窗选择器 |

#### 7.2 打包验证

```bash
cd E:\CC_Learning\QuickRec_dev
D:\Work\Software\Python\python.exe -m PyInstaller build_std.spec --clean --noconfirm
```

- [ ] 打包成功
- [ ] `dist/QuickRec/QuickRec.exe` 能启动
- [ ] 全屏录制 → 生成 H.264 MP4 → 可播放
- [ ] 区域录制 → 正常
- [ ] 窗口录制 → 选择→高亮→录制→停止 全链路正常
- [ ] copy 到其他目录运行（验证 DLL 依赖完整性）
- [ ] 打包体积 < 250MB（首次目标）

---

## 3. 开发顺序与依赖图

```
阶段 1: 编码 + 工具基础（无依赖，最先开发）
  ├─ 1.1: video_encoder.py    FFmpeg pipe 重写
  ├─ 1.2: temp_cleaner.py     临时文件清理（新增）
  └─ 1.3: disk_checker.py     磁盘预警（扩展）
  │
  ├─→ 阶段 3: recorder_manager.py 管线重构（依赖: 阶段 1）
  │
  ├─→ 阶段 2: 窗口录制 UI（无依赖，可与阶段 1 并行）
  │     ├─ 2.1: window_selector.py     窗口选择器重写
  │     └─ 2.2: window_highlighter.py  边框高亮重写
  │
  ├─→ 阶段 4: main.py 集成（依赖: 阶段 2 + 阶段 3）
  │     └─ DPI + 磁盘检查勾子 + 窗口录制恢复 + 信号桥
  │
  ├─→ 阶段 5: 设置 + 托盘小改（无依赖，可与阶段 4 并行）
  │     ├─ 5.1: settings_dialog.py   恢复窗口快捷键行
  │     └─ 5.2: tray_icon.py         恢复窗口录制菜单项
  │
  └─→ 阶段 6: 打包优化（无依赖，独立）
        └─ 6.1: build_std.spec       排除不需要的 Qt 模块
        │
        └─→ 阶段 7: 集成测试 + 打包验证（依赖: 全部）
```

**关键路径**：video_encoder → recorder_manager → main → 集成测试

**可并行开发**：
- 阶段 1（video_encoder / temp_cleaner / disk_checker）全部可并行
- 阶段 2（window_selector / window_highlighter）内部并行
- 阶段 1 与阶段 2 互相独立，可同时启动
- 阶段 5 与阶段 6 与阶段 4 可并行

**总模块数**：10 个（7 个重写/新增 + 3 个小改）

---

## 4. 风险与注意事项

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| FFmpeg 子进程崩溃 | 正在录制视频损坏 | 输出到 session_dir（不污染保存目录），启动时 TempCleaner.cleanup_stale() 清理遗留 |
| H.264 实时编码 CPU 占用高于 JPEG | 低端设备录制卡顿 | CRF=23 + preset=medium 平衡；对比 v1.2 和 v1.3 CPU 占用做 profile |
| 窗口选择器重写引入新 bug | 窗口枚举遗漏/误过滤 | 参考 v1.2 已验证的过滤规则 + 多版本 Windows 验证 |
| 窗口录制代码全部重写 | 边界 case 遗漏 | 参考 v1.2 注释代码中已验证正确的部分（GetClientRect, ClientToScreen） |
| 打包后排除的 DLL 导致启动崩溃 | 关键 Qt 插件被误删 | 保留 Core/Gui/Widgets/Network 等核心模块；platform/qwindows.dll 必保留 |
| DPI 高缩放下 UI 错位 | 控件重叠/文字截断 | 两行 setAttribute 必须在 QApplication 前；多 DPI 环境测试 |
| 窗口丢失托盘通知被用户忽略 | 用户不知道录制已暂停 | 通知文本明确写明原因和下一步操作；工具栏状态同步显示 |
| recorder_manager 改动量大（~200 行） | 可能引入回归 bug | 分步实施：先改 pipe 编码（无音频验证）→ 再加 session_dir → 最后窗口录制 |

---

## 5. 文件改动清单

| 文件 | 改动类型 | 改动量 |
|------|---------|--------|
| src/recorder/video_encoder.py | 重写 | 中（~100 行，删除 OpenCV + 重写 FFmpeg pipe） |
| src/utils/temp_cleaner.py | 新增 | 小（~70 行） |
| src/utils/disk_checker.py | 扩展 | 小（~40 行新增） |
| src/recorder/recorder_manager.py | 重构 | 大（~200 行变更：删除 JPEG + 新增 pipe + 恢复窗口模式 + 接入 TempCleaner） |
| src/ui/window_selector.py | 重写 | 中（~150 行，删除 v1.2 注释代码从零重写） |
| src/ui/window_highlighter.py | 重写 | 小（~60 行，删除 v1.2 注释代码从零重写） |
| src/main.py | 更新 | 中（~100 行变更：恢复窗口录制 + DPI + 磁盘检查勾子） |
| src/ui/settings_dialog.py | 小改 | 极小（~5 行，取消注释窗口快捷键行） |
| src/ui/tray_icon.py | 小改 | 极小（~5 行，取消注释窗口录制菜单项） |
| build_std.spec | 优化 | 小（~20 行 excludes 列表） |
| src/ui/toolbar.py | 不变 | — |
| src/ui/area_selector.py | 不变 | — |
| src/hotkey/hotkey_manager.py | 不变 | — |
| src/recorder/screen_capturer.py | 不变 | — |
| src/recorder/audio_capturer.py | 不变（仅 recorder_manager 传 output_dir 路径变更） | — |
| src/config.py | 不变 | — |
| src/utils/file_namer.py | 不变 | — |
| src/utils/autostart.py | 不变 | — |
| src/ui/click_highlighter.py | 不变 | — |
