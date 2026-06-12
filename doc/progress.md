# QuickRec 项目进度总览

> 最后更新: 2026-06-12

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
- [x] [项目初始化和依赖安装](tasks/task-v1.0-setup.md)
  - [x] 安装 dxcam (0.3.0) 和 comtypes (1.4.16)
  - [x] 安装 pyqt5、opencv-python、numpy、pynput、pystray、pyinstaller
  - [x] 安装 pystray (0.19.5)
  - [x] 安装 pyinstaller (6.20.0)
  - [x] 生成 requirements.txt
  - [x] 创建项目目录结构

### 核心模块 (无依赖，可独立开发)
- [x] [配置管理模块 (config.py)](tasks/task-v1.0-config.md)
  - [x] ConfigManager 类实现
  - [x] 默认值定义
  - [x] 文件路径处理
  - [x] 异常处理
  - [x] 单元测试 (8/8 通过)

- [x] [文件命名模块 (file_namer.py)](tasks/task-v1.0-file_namer.md)
  - [x] FileNamer 类实现
  - [x] 命名规则
  - [x] 目录处理
  - [x] 单元测试 (5/5 通过)

- [x] [磁盘空间检查模块 (disk_checker.py)](tasks/task-v1.0-disk_checker.md)
  - [x] DiskChecker 类实现
  - [x] 空间估算逻辑
  - [x] 单元测试 (6/6 通过)

### 录制引擎
- [x] [屏幕捕获模块 (screen_capturer.py)](tasks/task-v1.0-screen_capturer.md)
  - [x] ScreenCapturer 类实现
  - [x] 全屏/区域捕获
  - [x] 数据格式验证
  - [x] 单元测试 (6/6 通过)

- [x] [视频编码模块 (video_encoder.py)](tasks/task-v1.0-video_encoder.md)
  - [x] VideoEncoder 类实现
  - [x] 编码参数配置
  - [x] 单元测试 (5/5 通过)

- [x] [录制控制模块 (recorder_manager.py)](tasks/task-v1.0-recorder_manager.md)
  - [x] RecorderState 枚举
  - [x] RecorderManager 类实现
  - [x] 录制循环
  - [x] 单元测试 (7/7 通过)

### UI 模块
- [x] [区域选择模块 (area_selector.py)](tasks/task-v1.0-area_selector.md)
  - [x] AreaSelector 类实现
  - [x] 交互逻辑 (鼠标拖拽、ESC取消)
  - [x] 显示信息 (尺寸标签、边框高亮)
  - [x] 单元测试 (6/6 通过)
  - ⚠️ v1.0 未使用（Windows 11 兼容性问题，推迟到 v1.1）

- [x] [录制工具栏模块 (toolbar.py)](tasks/task-v1.0-toolbar.md)
  - [x] RecordingToolbar 类实现
  - [x] UI 元素 (指示灯、计时器、按钮)
  - [x] 交互功能 (暂停/恢复、拖拽)
  - [x] 单元测试 (8/8 通过)

- [x] [设置对话框模块 (settings_dialog.py)](tasks/task-v1.0-settings_dialog.md)
  - [x] SettingsDialog 类实现
  - [x] 控件定义 (路径、画质、帧率、快捷键)
  - [x] 功能实现 (加载、保存、浏览)
  - [x] 单元测试 (5/5 通过)

- [x] [系统托盘模块 (tray_icon.py)](tasks/task-v1.0-tray_icon.md)
  - [x] TrayIcon 类实现
  - [x] 菜单项 (录制、设置、打开文件夹、退出)
  - [x] 功能实现 (显示、隐藏、通知)
  - [x] 单元测试 (3/3 通过)

- [x] [全局快捷键模块 (hotkey_manager.py)](tasks/task-v1.0-hotkey_manager.md)
  - [x] HotkeyManager 类实现（基于 pynput，原 keyboard 已移除）
  - [x] 快捷键格式解析（键集合匹配）
  - [x] Ctrl/Shift/Alt 左右键兼容
  - [x] start_listening / stop_listening 生命周期管理
  - [x] 单元测试 (7/7 通过)

### 入口和集成
- [x] [主程序入口 (main.py)](tasks/task-v1.0-main.md)
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

## 开发阶段

### 第一阶段 ✅
1. ✅ **task-v1.0-setup** - 安装依赖，创建目录
2. ✅ **task-v1.0-config** - 配置管理
3. ✅ **task-v1.0-file_namer** + **task-v1.0-disk_checker** - 工具模块

### 第二阶段 ✅
4. ✅ **task-v1.0-screen_capturer** - 屏幕捕获
5. ✅ **task-v1.0-video_encoder** - 视频编码
6. ✅ **task-v1.0-recorder_manager** - 录制控制

### 第三阶段 ✅
7. ✅ **task-v1.0-area_selector** - 区域选择
8. ✅ **task-v1.0-toolbar** - 录制工具栏
9. ✅ **task-v1.0-settings_dialog** - 设置对话框

### 第四阶段 ✅
10. ✅ **task-v1.0-hotkey_manager** - 全局快捷键
11. ✅ **task-v1.0-tray_icon** - 系统托盘

### 第五阶段 ✅
12. ✅ **task-v1.0-main** - 主程序入口

### 第六阶段 ✅
14. ✅ **完整功能测试** - 58/66 单元测试通过（8个 test_config 失败是已有 mock 路径问题）
15. ✅ **打包** - PyInstaller 打包为 QuickRec.exe

### 第七阶段 ✅ Bug 修复
16. ✅ **Bug 修复** - 修复 7 个 bug（详见 [bugfix-log.md](bugfix-log.md)）
    - pystray 线程安全（信号桥）
    - 暂停录制无法停止（_resume_event 重写）
    - keyboard → pynput（无需管理员权限）
    - 工具栏位置居中
    - 区域选择器点击穿透（推迟到 v1.1）
    - 设置对话框线程安全
    - \_\_del\_\_ 资源释放异常保护
17. ✅ **v1.0 范围调整** - 去掉区域录制，仅保留全屏录制
18. ✅ **重新打包** - 确认所有修改后打包成功

### 第八阶段 ✅ 帧缓存方案与Bug修复
19. ✅ **Bug #8 修复** - 60fps录制视频时长偏短/倍速播放
    - 根因：实时编码+截图合计31ms/帧，仅32fps，帧数不足导致时长偏短
    - 方案1: mss→dxcam，帧捕获从30ms降至5ms（不够，60fps仍需31ms/帧）
    - 方案2: 内存缓存JPEG帧+后编码（内存占用过大，1440p/60fps 4GB仅缓存3.6分钟）
    - 方案3（最终）: JPEG临时文件缓存+后编码，内存始终MB级，录制循环约7ms/帧
20. ✅ **Bug #9 修复** - 取消录制仍生成文件
21. ✅ **Bug #10** - 多次连续录制失败（待Bug#8修复后重测）
22. ✅ **技术文档更新** - Tec-design.md 更新dxcam、临时文件缓存方案

### 第九阶段 ✅ v1.0 Bug 修复（续）
23. ✅ **Bug #17 修复** - 点击停止后工具栏"保存中"不消失
    - 根因：QTimer.singleShot 从编码线程调用不可靠，改用 pyqtSignal 信号桥转发
24. ✅ **Bug #18 修复** - 录制期间 GUI 冻结，快捷键和托盘菜单均不响应
    - 根因1：录制线程忙等待 `while pass` 占满 CPU/GIL，主线程无法获得执行时间
    - 根因2：dxcam 在主线程初始化导致短暂冻结
    - 根因3：stop() 中 join(5s) 阻塞主线程
    - 修复：消除忙等待改用 time.sleep 释放 GIL；dxcam 延迟到录制线程初始化；stop() 异步非阻塞
25. ✅ **Bug #19 修复** - 快捷键触发录制后 GUI 冻结、工具栏不出现
    - 根因：pynput 回调在其线程直接操作 Qt UI，违反线程安全
    - 修复：新增 _HotkeyBridge 信号桥，快捷键回调通过 pyqtSignal 转发到主线程
26. ✅ **v1.0 测试通过** - 全部功能测试用例通过（除 T8.1/T8.6/T8.7 跳过、T10.x 未专项测试）

---

## v1.1 进度 ✅ 已完成（2026-06-12）

> v1.1 目标：区域录制 + 音频源选择 + 通知增强
> 测试结果：76 用例 → 75 通过 / 1 跳过 / 0 失败；已打包并通过打包后功能验证

### v1.1 模块进度

- [x] [区域录制模块 (area_selector.py)](../tasks/task-v1.1-area_selector.md)
  - [x] Win11 点击穿透修复（移除 Qt.Tool，添加 StrongFocus）
  - [x] 确认对话框（开始录制 / 取消）
  - [x] 最小尺寸提示（红色提示 < 100x100）
  - [x] 边框视觉优化（白色虚线）
  - [x] 与 main.py 集成（_AreaBridge 信号桥）

- [x] [音频录制模块 (audio_capturer.py)](../tasks/task-v1.1-audio_capturer.md) — 新增文件
  - [x] AudioSource 枚举和 AudioCapturer 类框架
  - [x] WASAPI 系统声音捕获（pyaudiowpatch）
  - [x] 麦克风捕获（pyaudio）
  - [x] 音频捕获线程和 WAV 写入
  - [x] BOTH 模式双路独立录制
  - [x] 优雅降级（设备不可用时无声录制）

- [x] [录制控制模块 (recorder_manager.py)](../tasks/task-v1.1-recorder_manager.md) — 更新
  - [x] RecordMode 枚举（FULLSCREEN / REGION）
  - [x] 音频初始化（_start 方法扩展）
  - [x] 音频停止（_stop_and_encode 方法扩展）
  - [x] 音频混合（_encode_loop + FFmpeg）
  - [x] FFmpeg 集成（_get_ffmpeg_path + _mix_audio_video）
  - [x] 配置扩展（audio_source 默认值）

- [x] [系统托盘模块 (tray_icon.py)](../tasks/task-v1.1-tray_icon.md) — 更新
  - [x] _SignalBridge 新增信号（start_region / pause_resume / stop）
  - [x] 动态菜单切换（空闲 / 录制中 / 暂停）
  - [x] Toast 通知增强（winotify 降级链）
  - [x] 托盘菜单回调扩展

- [x] [录制工具栏模块 (toolbar.py)](../tasks/task-v1.1-toolbar.md) — 更新
  - [x] 结果条模式（✓ 时长 | 已保存 | 📂 打开 | ✕ 关闭）
  - [x] 5 秒自动关闭定时器
  - [x] "已保存" 按钮打开视频文件
  - [x] "📂 打开" 按钮打开文件夹并选中

- [x] [配置管理模块 (config.py)](../tasks/task-v1.1-config.md) — 更新
  - [x] 新增 audio_source 默认配置
  - [x] 新增 shortcut_area 默认配置
  - [x] 旧版配置向后兼容

- [x] [设置对话框模块 (settings_dialog.py)](../tasks/task-v1.1-settings_dialog.md) — 更新
  - [x] 音频源选择下拉框
  - [x] 区域录制快捷键设置
  - [x] 配置加载与保存扩展

- [x] [主程序入口 (main.py)](../tasks/task-v1.1-main.md) — 更新
  - [x] _AreaBridge 信号桥
  - [x] _HotkeyBridge 扩展（area_requested）
  - [x] 区域录制流程（_on_start_region / _on_region_selected）
  - [x] 托盘回调扩展（start_fullscreen / start_region / pause_resume / stop）
  - [x] 编码完成回调增强（Toast 通知 + 结果条）
  - [x] 工具栏信号连接（open_folder / open_file）

- [x] [FFmpeg 打包配置](../tasks/task-v1.1-ffmpeg_setup.md)
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

## v1.2 进度 🚧 开发中

> v1.2 目标：指定窗口录制 + 鼠标点击高亮 + 原生画质优化 + 开机自启 + 录制倒计时

### v1.2 模块进度

#### 基础设施
- [ ] [配置管理模块更新 (config.py)](../tasks/task-v1.2-config.md) — v1.2
  - [ ] 新增配置项（shortcut_window, show_countdown, countdown_seconds, mouse_highlight, auto_start）
  - [ ] 新增 get_native_resolution() 静态方法
  - [ ] 旧版配置向后兼容

#### 工具模块
- [ ] [开机自启模块 (autostart.py)](../tasks/task-v1.2-autostart.md) — 新增
  - [ ] is_autostart_enabled() 注册表读取
  - [ ] enable_autostart() 注册表写入
  - [ ] disable_autostart() 注册表删除

#### UI 模块
- [ ] [鼠标点击高亮模块 (click_highlighter.py)](../tasks/task-v1.2-click_highlighter.md) — 新增
  - [ ] _ClickBridge 信号桥
  - [ ] ClickCircle 扩散圆圈动画
  - [ ] ClickHighlighter 管理器（pynput 鼠标监听）

- [ ] [录制工具栏倒计时 (toolbar.py)](../tasks/task-v1.2-toolbar-countdown.md) — 更新
  - [ ] 倒计时 UI（大号数字 + 取消提示）
  - [ ] start_countdown / cancel_countdown 方法
  - [ ] countdown_finished 信号
  - [ ] ESC 键取消倒计时

- [ ] [窗口选择器 (window_selector.py)](../tasks/task-v1.2-window_selector.md) — 新增
  - [ ] Win32 窗口枚举（EnumWindows + 过滤）
  - [ ] 窗口列表对话框 UI
  - [ ] window_selected / cancelled 信号

- [ ] [窗口边框高亮 (window_highlighter.py)](../tasks/task-v1.2-window_highlighter.md) — 新增
  - [ ] 绿色虚线边框绘制
  - [ ] 位置跟踪定时器（100ms）
  - [ ] show_highlight / hide_highlight

- [ ] [设置对话框更新 (settings_dialog.py)](../tasks/task-v1.2-settings_dialog.md) — 更新
  - [ ] 开机自启复选框 + 注册表同步
  - [ ] 倒计时复选框 + 秒数输入
  - [ ] 鼠标高亮复选框
  - [ ] 窗口录制快捷键
  - [ ] 画质下拉框动态显示分辨率

- [ ] [系统托盘更新 (tray_icon.py)](../tasks/task-v1.2-tray_icon.md) — 更新
  - [ ] 空闲菜单新增"窗口录制"
  - [ ] start_window_requested 信号

#### 录制模块
- [ ] [屏幕捕获更新 (screen_capturer.py)](../tasks/task-v1.2-screen_capturer.md) — 更新
  - [ ] update_region() 动态更新捕获区域

- [ ] [录制控制器更新 (recorder_manager.py)](../tasks/task-v1.2-recorder_manager.md) — 更新
  - [ ] RecordMode.WINDOW 枚举
  - [ ] start_window() 方法
  - [ ] _record_loop 窗口位置跟踪
  - [ ] _WindowLostBridge 信号桥

#### 入口集成
- [ ] [主程序入口更新 (main.py)](../tasks/task-v1.2-main.md) — 更新
  - [ ] _WindowBridge / _WindowLostBridge 信号桥
  - [ ] 窗口录制流程（_on_start_window / _on_window_selected / _do_start_window）
  - [ ] 倒计时集成（全屏/区域/窗口）
  - [ ] 鼠标高亮控制
  - [ ] 窗口高亮生命周期管理
  - [ ] 快捷键注册扩展

### v1.2 开发阶段

| 阶段 | 内容 | 依赖 | 状态 |
|-----|------|------|------|
| 1 | config.py 新增配置项 + autostart.py | 无 | ⬜ |
| 2 | click_highlighter.py 鼠标高亮 | config | ⬜ |
| 3 | toolbar.py 倒计时模式 | config（可与阶段 2 并行） | ⬜ |
| 4 | settings_dialog.py 设置更新 | config, autostart | ⬜ |
| 5 | 窗口录制核心（window_selector + window_highlighter + screen_capturer + recorder_manager） | config | ⬜ |
| 6 | main.py 集成 + tray_icon.py 菜单更新 | 所有模块 | ⬜ |
| 7 | 集成测试 + 打包验证 | 全部 | ⬜ |