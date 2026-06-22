# QuickRec 项目进度总览

> 最后更新: 2026-06-22
> 稳定版本：v1.2（master）；v1.3 在 test 分支开发
> 任务明细归档在 `tasks/` 目录，本文件汇总按版本组织的进度

## 环境状态

| 项目 | 状态 | 版本 | 说明 |
|-----|------|------|------|
| Python | ✅ 已安装 | 3.12.8 | CPython（不要用 Anaconda） |
| PyQt5 | ✅ 已安装 | 5.15.10 | |
| numpy | ✅ 已安装 | 2.4.6 | opencv-python 依赖升级 |
| dxcam | ✅ 已安装 | 0.3.0 | 替代 mss，DirectX 屏幕捕获 |
| comtypes | ✅ 已安装 | 1.4.16 | dxcam 依赖 |
| opencv-python | ✅ 已安装 | 4.13.0 | |
| keyboard | ❌ 已移除 | - | 替换为 pynput |
| pynput | ✅ 已安装 | 1.8.2 | 替代 keyboard，无需管理员权限 |
| pystray | ✅ 已安装 | 0.19.5 | |
| pyaudio | ✅ 已安装 | ≥0.2.14 | 麦克风捕获 |
| soundcard | ✅ 已安装 | ≥0.4 | 系统声音 WASAPI loopback |
| winotify | ✅ 已安装 | ≥1.1 | Windows Toast 通知 |
| pyinstaller | ✅ 已安装 | 6.20.0 | |
| FFmpeg | ✅ 就位 | 8.0.1 | `ffmpeg/ffmpeg.exe`（94MB） |

---

## v1.0 进度 ✅ 已完成

> v1.0 目标：全屏录制最小可用版本 + 系统托盘 + 全局快捷键
> 任务明细：`tasks/task-v1.0-*.md`

### v1.0 模块进度

- [x] 项目初始化和依赖安装（[task-v1.0-setup](../tasks/task-v1.0-setup.md)）
  - [x] 安装 PyQt5、numpy、opencv-python、pystray、pyinstaller、mss/keyboard（后续被替代）
  - [x] 生成 requirements.txt
  - [x] 创建项目目录结构（src/recorder, src/ui, src/utils, src/hotkey, tests）

- [x] 配置管理模块（config.py — [task-v1.0-config](../tasks/task-v1.0-config.md)）
  - [x] ConfigManager 类（get/set/save/load/reset）
  - [x] defaults 字典：save_path / quality / fps / shortcut_start|stop|pause
  - [x] 配置文件持久化到 `AppData/Roaming/QuickRec/config.json`
  - [x] 单元测试 8/8 通过

- [x] 文件命名模块（file_namer.py — [task-v1.0-file_namer](../tasks/task-v1.0-file_namer.md)）
  - [x] FileNamer.generate 基础格式 `QuickRec_YYYYMMDD_HHmmss.mp4`
  - [x] 冲突检测：同秒追加序号 `_001.mp4`
  - [x] 目标目录不存在自动创建
  - [x] 单元测试 5/5 通过

- [x] 磁盘空间检查模块（disk_checker.py — [task-v1.0-disk_checker](../tasks/task-v1.0-disk_checker.md)）
  - [x] get_free_space / estimate_size_per_minute（高 60MB/min、中 30MB/min、低 15MB/min）
  - [x] is_low_space 判定
  - [x] 单元测试 6/6 通过

- [x] 屏幕捕获模块（screen_capturer.py — [task-v1.0-screen_capturer](../tasks/task-v1.0-screen_capturer.md)）
  - [x] ScreenCapturer 类，全屏/区域捕获
  - [x] 返回 BGR numpy ndarray
  - [x] 单元测试 6/6 通过

- [x] 视频编码模块（video_encoder.py — [task-v1.0-video_encoder](../tasks/task-v1.0-video_encoder.md)）
  - [x] VideoEncoder 基于 OpenCV VideoWriter，fourcc `mp4v`
  - [x] write_frame / close / is_open / get_frame_count
  - [x] 自动建目录
  - [x] 单元测试 5/5 通过

- [x] 录制控制模块（recorder_manager.py — [task-v1.0-recorder_manager](../tasks/task-v1.0-recorder_manager.md)）
  - [x] RecorderState 枚举（IDLE/RECORDING/PAUSED/STOPPING）
  - [x] start_fullscreen / pause / resume / stop
  - [x] 帧率控制循环
  - [x] 单元测试 7/7 通过

- [x] 区域选择模块（area_selector.py — [task-v1.0-area_selector](../tasks/task-v1.0-area_selector.md)）
  - [x] AreaSelector 全屏半透明遮罩 + 鼠标拖选
  - [x] ESC 取消 + 尺寸标签
  - [x] region_selected / cancelled 信号
  - [x] 单元测试 6/6 通过
  - ⚠️ v1.0 未使用（Win11 兼容性问题，推迟到 v1.1 修复）

- [x] 录制工具栏模块（toolbar.py — [task-v1.0-toolbar](../tasks/task-v1.0-toolbar.md)）
  - [x] RecordingToolbar：红色指示灯 + 计时器 + 暂停/停止/取消按钮
  - [x] 无边框置顶半透明，可拖动
  - [x] 单元测试 8/8 通过

- [x] 设置对话框（settings_dialog.py — [task-v1.0-settings_dialog](../tasks/task-v1.0-settings_dialog.md)）
  - [x] 保存路径浏览 + 画质/帧率选择 + 快捷键显示（只读）
  - [x] config_saved 信号
  - [x] 单元测试 5/5 通过

- [x] 系统托盘模块（tray_icon.py — [task-v1.0-tray_icon](../tasks/task-v1.0-tray_icon.md)）
  - [x] pystray 托盘图标 + 菜单
  - [x] show/hide/show_notification
  - [x] 单元测试 3/3 通过

- [x] 全局快捷键模块（hotkey_manager.py — [task-v1.0-hotkey_manager](../tasks/task-v1.0-hotkey_manager.md)）
  - [x] HotkeyManager（v1.0 用 keyboard，v1.0 Bug #3 后替换为 pynput）
  - [x] register/unregister/start_listening/stop_listening
  - [x] parse_shortcut 解析 `Ctrl+Shift+R` 格式
  - [x] 单元测试 7/7 通过

- [x] 主程序入口（main.py — [task-v1.0-main](../tasks/task-v1.0-main.md)）
  - [x] 初始化各模块、信号桥连接
  - [x] 快捷键绑定 + 托盘菜单回调
  - [x] 录制流程集成 + 退出流程

### v1.0 开发阶段

| 阶段 | 内容 | 依赖 | 状态 |
|-----|------|------|------|
| 1 | setup + config + file_namer + disk_checker | 无 | ✅ |
| 2 | screen_capturer + video_encoder + recorder_manager | 阶段 1 | ✅ |
| 3 | area_selector + toolbar + settings_dialog | 阶段 2 | ✅ |
| 4 | hotkey_manager + tray_icon | 阶段 3 | ✅ |
| 5 | main.py 入口集成 | 所有模块 | ✅ |
| 6 | 完整功能测试 + 打包 | 阶段 5 | ✅ |
| 7 | Bug 修复 (#1-#19，详见 [bugfix-log](bugfix-log.md)) | — | ✅ 58/66 测试通过；v1.0 仅保留全屏录制，区域录制推迟至 v1.1 |

---

## v1.1 进度 ✅ 已完成（2026-06-12）

> v1.1 目标：区域录制 + 音频源选择 + 通知增强 + FFmpeg 音视频混合
> 任务明细：`tasks/task-v1.1-*.md`
> 测试结果：76 用例 → 75 通过 / 1 跳过 / 0 失败；打包后功能全部通过

### v1.1 模块进度

- [x] 配置扩展（config.py — [task-v1.1-config](../tasks/task-v1.1-config.md)）
  - [x] 新增 `audio_source` 默认 "none" + `shortcut_area` 默认 `Ctrl+Shift+A`
  - [x] AUDIO_OPTIONS 映射（无/系统声音/麦克风/两者都有）
  - [x] 旧版 v1.0 配置向后兼容

- [x] 区域录制修复（area_selector.py — [task-v1.1-area_selector](../tasks/task-v1.1-area_selector.md)）
  - [x] Win11 点击穿透修复（移除 Qt.Tool，添加 StrongFocus + raise_/activateWindow/setFocus）
  - [x] 拖选完成后展示确认浮动按钮（开始录制 / 取消）
  - [x] 选区 < 100×100 红色提示，1 秒自动消失
  - [x] 边框视觉优化（白色虚线）

- [x] 音频录制模块新增（audio_capturer.py — [task-v1.1-audio_capturer](../tasks/task-v1.1-audio_capturer.md)）
  - [x] AudioSource 枚举：NONE/SYSTEM/MICROPHONE/BOTH
  - [x] WASAPI 系统声音捕获（pyaudiowpatch → 后切到 soundcard，见 Bug #24）
  - [x] 麦克风捕获（pyaudio）
  - [x] 独立音频线程 + WAV 写入
  - [x] BOTH 模式双路独立录制
  - [x] 设备不可用优雅降级无声

- [x] 录制控制扩展（recorder_manager.py — [task-v1.1-recorder_manager](../tasks/task-v1.1-recorder_manager.md)）
  - [x] RecordMode 枚举（FULLSCREEN / REGION）
  - [x] 音频初始化（_start 读取 audio_source 并构造 AudioCapturer）
  - [x] 音频停止（_stop_and_encode 收集 _audio_temp_paths）
  - [x] FFmpeg 音视频混合（_encode_loop 阶段，`-c:v copy -c:a aac`）
  - [x] _get_ffmpeg_path 多路径查找（_MEIPASS → 同级 dir → 项目根 → PATH）

- [x] 系统托盘扩展（tray_icon.py — [task-v1.1-tray_icon](../tasks/task-v1.1-tray_icon.md)）
  - [x] _SignalBridge 新增 start_region/pause_resume/stop 信号
  - [x] 动态菜单切换：空闲 / 录制中 / 暂停
  - [x] Toast 通知增强（winotify 降级链 pystray）
  - [x] show_notification_with_action 带"打开文件夹"按钮

- [x] 录制工具栏结果条（toolbar.py — [task-v1.1-toolbar](../tasks/task-v1.1-toolbar.md)）
  - [x] 结果条布局：`✓ 时长 | 已保存 | 📂 打开 | ✕ 关闭`
  - [x] 5 秒自动关闭（Bug #26 后改为无操作 5 秒重置）
  - [x] "已保存"按钮打开视频文件；"📂 打开"打开文件夹并选中（Bug #25 修复）

- [x] 设置对话框扩展（settings_dialog.py — [task-v1.1-settings_dialog](../tasks/task-v1.1-settings_dialog.md)）
  - [x] 音频源下拉框（AUDIO_OPTIONS 映射）
  - [x] 区域录制快捷键录入（_ShortcutRecorder 复用 v1.0）
  - [x] 加载/保存扩展

- [x] 主程序入口扩展（main.py — [task-v1.1-main](../tasks/task-v1.1-main.md)）
  - [x] _AreaBridge 信号桥（region_selected/cancelled）
  - [x] _HotkeyBridge.area_requested 信号 + 区域录制流程
  - [x] 托盘回调扩展（start_fullscreen/start_region/pause_resume/stop）
  - [x] 编码完成回调（_SavedBridge + Toast + 结果条）

- [x] FFmpeg 集成与打包（[task-v1.1-ffmpeg_setup](../tasks/task-v1.1-ffmpeg_setup.md)）
  - [x] FFmpeg 8.0.1 就位（ffmpeg/ffmpeg.exe，94MB）
  - [x] build_std.spec hiddenimports 补 audio_capturer / winotify
  - [x] requirements.txt 添加 pyaudiowpatch / pyaudio / winotify
  - [x] .gitignore 添加 ffmpeg/ 目录
  - [x] _get_ffmpeg_path 修复开发环境路径（Bug #21）

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
| 8 | main.py 信号桥 + 流程集成 | 所有 | ✅ |
| 9 | FFmpeg 打包配置 | recorder_manager | ✅ |
| 10 | 集成测试 + 打包验证 | 全部 | ✅ 75/76 通过；打包后功能全部通过 |

### v1.1 关键 Bug 修复
- #20 AreaSelector GC → 存为 `self._area_selector`
- #21 _get_ffmpeg_path 开发路径三层 dirname
- #22 结果条关闭误发 cancelled
- #23 区域录制画质缩放保宽高比
- #24 pyaudiowpatch 0xC0000005 → soundcard 替换
- #25 结果条打开文件夹不选中文件
- #26 自动关闭被永久停掉 → 重置倒计时
- #27 winotify 参数名 + add_actions + URI
- #28 打包后找不到 FFmpeg（_MEIPASS）

---

## v1.2 进度 ✅ 已完成（窗口录制延期至 v1.3）

> v1.2 目标：鼠标点击高亮 + 原生画质优化 + 开机自启 + 录制倒计时 + 窗口录制（延期）
> 任务明细：`tasks/task-v1.2-*.md`
> 测试结果：62 通过 / 24 延期（窗口录制相关） / 0 失败；单元测试 26/26 通过

### v1.2 模块进度

#### 基础设施
- [x] 配置扩展（config.py — [task-v1.2-config](../tasks/task-v1.2-config.md)）
  - [x] 新增 shortcut_window / show_countdown / countdown_seconds / mouse_highlight / auto_start
  - [x] 新增 get_native_resolution() 静态方法（GetSystemMetrics）
  - [x] 旧版 v1.1 配置向后兼容

#### 工具模块
- [x] 开机自启模块新增（autostart.py — [task-v1.2-autostart](../tasks/task-v1.2-autostart.md)）
  - [x] is_autostart_enabled / enable_autostart / disable_autostart（HKCU\Run）
  - [x] 无需管理员权限；打包后路径指向 QuickRec.exe

#### UI 模块
- [x] 鼠标点击高亮新增（click_highlighter.py — [task-v1.2-click_highlighter](../tasks/task-v1.2-click_highlighter.md)）
  - [x] _ClickBridge 信号桥 + ClickCircle 扩散动画
  - [x] ClickHighlighter（pynput.mouse.Listener 独立线程）
  - [x] 左键扩散圆圈 300ms，右键不显示
  - [x] mouse_highlight 开关 + 录制停止后不响应

- [x] 录制工具栏倒计时（toolbar.py — [task-v1.2-toolbar-countdown](../tasks/task-v1.2-toolbar-countdown.md)）
  - [x] countdown_finished 信号 + _countdown_timer (1s)
  - [x] start_countdown / cancel_countdown / _show_countdown_ui
  - [x] ESC 键取消倒计时
  - [x] 工具栏高度 40→56px，倒计时数字 36→28px 居中（Bug #43）

- [x] 窗口选择器新增（window_selector.py — [task-v1.2-window_selector](../tasks/task-v1.2-window_selector.md)）⚠️ 延期
  - [x] Win32 EnumWindows + 类名黑名单过滤
  - [x] WindowSelector QDialog + QListWidget + 刷新/选择/取消
  - [x] window_selected / cancelled 信号
  - ⚠️ 选择窗口后崩溃 / 列表过多系统窗口等 → 整体延期（详见 Bug #29-#41）

- [x] 窗口边框高亮新增（window_highlighter.py — [task-v1.2-window_highlighter](../tasks/task-v1.2-window_highlighter.md)）⚠️ 延期
  - [x] 100ms QTimer 位置更新 + 绿色虚线（#00e676, 2px, DashLine）
  - [x] show_highlight / hide_highlight
  - ⚠️ 同窗口录制延期

- [x] 设置对话框扩展（settings_dialog.py — [task-v1.2-settings_dialog](../tasks/task-v1.2-settings_dialog.md)）
  - [x] 开机自启复选框 + 注册表同步
  - [x] 倒计时复选框 + 秒数（QComboBox，Bug #44 改 QSpinBox→QComboBox）
  - [x] 鼠标高亮复选框 + 窗口录制快捷键
  - [x] 画质下拉框动态显示原生分辨率
  - [x] Fusion 样式

- [x] 系统托盘更新（tray_icon.py — [task-v1.2-tray_icon](../tasks/task-v1.2-tray_icon.md)）
  - [x] _SignalBridge.start_window_requested 信号
  - [x] 空闲菜单新增"窗口录制"项

#### 录制模块
- [x] 屏幕捕获扩展（screen_capturer.py — [task-v1.2-screen_capturer](../tasks/task-v1.2-screen_capturer.md)）
  - [x] update_region(region) 动态更新 dxcam 捕获区域
  - [x] _last_dxcam_region 缓存避免重复重建（Bug #30）
  - [x] get_monitor_size 返回当前区域尺寸

- [x] 录制控制器扩展（recorder_manager.py — [task-v1.2-recorder_manager](../tasks/task-v1.2-recorder_manager.md)）⚠️ 窗口录制相关延期
  - [x] RecordMode.WINDOW 枚举（延期）
  - [x] start_window(hwnd) + _get_window_rect（GetWindowRect，Bug #38 改 GetClientRect，延期）
  - [x] _record_loop 200ms update_region + 窗口丢失 emit（延期）
  - [x] _WindowLostBridge 信号桥（延期）

#### 入口集成
- [x] 主程序入口扩展（main.py — [task-v1.2-main](../tasks/task-v1.2-main.md)）
  - [x] _WindowBridge / _WindowLostBridge 信号桥
  - [x] 窗口录制流程（_on_start_window / _on_window_selected / _do_start_window / _on_window_lost）（延期）
  - [x] 倒计时集成（全屏/区域/窗口）+ 全局 ESC 回调（Bug #46/#48）
  - [x] 鼠标高亮控制（_update_highlight_state）
  - [x] 窗口高亮生命周期管理（延期）

### v1.2 开发阶段

| 阶段 | 内容 | 依赖 | 状态 |
|-----|------|------|------|
| 1 | config.py 新增配置项 + autostart.py | 无 | ✅ |
| 2 | click_highlighter.py 鼠标高亮 | config | ✅ |
| 3 | toolbar.py 倒计时模式 | config（可与阶段 2 并行） | ✅ |
| 4 | settings_dialog.py 设置更新 | config, autostart | ✅ |
| 5 | 窗口录制核心（window_selector + window_highlighter + screen_capturer + recorder_manager） | config | ✅（延期） |
| 6 | main.py 集成 + tray_icon.py 菜单更新 | 所有模块 | ✅（窗口录制延期） |
| 7 | 集成测试 + 打包验证 | 全部 | ✅ 62 通过 / 24 延期 / 0 失败；窗口录制功能整体延期至 v1.3 |

### v1.2 关键 Bug 修复（窗口录制相关）
- #29 窗口选择器过多系统窗口 → 扩充 _SYSTEM_CLASSES 黑名单
- #30 选中窗口崩溃 0xC0000409 → ctypes.wintypes 显式导入 + dxcam 缓存
- #31 选窗口不前置 → SetForegroundWindow
- #32 ctypes.wintypes 未导入崩溃
- #33 Qt.WA_TransparentForMouseInput 拼写 → Events
- #34 QRect 方法缺括号 → left()/top()
- #37 窗口丢失崩溃 + QMessageBox 不显示 → 托盘通知
- #38 最大化窗口 GetWindowRect 负坐标 → GetClientRect + ClientToScreen
- #39 非倒计时不显工具栏
- #41 窗口录制整体延期决策（注释代码不删除，v1.3 重新实现）
- #42 停止录制后鼠标高亮仍显示
- #43 倒计时数字过大被裁切 → 56px + 28px
- #44 QSpinBox 渲染乱码 → QComboBox
- #46 倒计时期间 ESC 无效 → 去掉 Qt.Tool
- #47 倒计时 Ctrl+Shift+R 重置而非取消
- #48 全局 ESC 回调（set_esc_callback）
- #49 托盘打开文件夹路径斜杠 → normpath

---

## 总览

| 版本 | 状态 | 主要交付 |
|-----|------|---------|
| v1.0 | ✅ | 全屏录制 + 系统托盘 + 全局快捷键 + QoS |
| v1.1 | ✅ | 区域录制 + 音频源 + Toast 通知 + 结果条 + FFmpeg 音视频混合 |
| v1.2 | ✅（窗口录制延期） | 鼠标高亮 + 原生画质 + 开机自启 + 倒计时；窗口录制延期至 v1.3 |

> v1.3（test 分支）：窗口录制深度重写 + H.264 FFmpeg pipe 实时编码 + 打包体积优化（334→259MB）+ DPI + 磁盘预警 + 临时文件三层清理。详见 test 分支 `doc/progress.md`。

## 依赖关系图

```
setup (最先)
  │
  ├─> config.py (无依赖)
  ├─> file_namer.py (无依赖)
  ├─> disk_checker.py (无依赖)
  ├─> autostart.py (无依赖)              ← v1.2 新增
  │
  ├─> screen_capturer.py (依赖: dxcam)   ← v1.2 新增 update_region
  ├─> video_encoder.py (依赖: opencv-python)
  │
  ├─> hotkey_manager.py (依赖: pynput)   ← keyboard 已替换
  │
  ├─> area_selector.py (依赖: PyQt5)
  ├─> toolbar.py (依赖: PyQt5)           ← v1.2 倒计时
  ├─> settings_dialog.py (依赖: config + PyQt5 + autostart)
  ├─> tray_icon.py (依赖: pystray + PyQt5)
  ├─> click_highlighter.py (依赖: pynput + PyQt5)   ← v1.2 新增
  ├─> window_selector.py (依赖: ctypes + PyQt5)    ← v1.2 新增（延期）
  ├─> window_highlighter.py (依赖: ctypes + PyQt5) ← v1.2 新增（延期）
  ├─> audio_capturer.py (依赖: soundcard / pyaudio) ← v1.1 新增
  │
  ├─> recorder_manager.py (依赖: capturer + encoder + audio + file_namer + checker + config)
  │
  └─> main.py (依赖: 所有模块)
```