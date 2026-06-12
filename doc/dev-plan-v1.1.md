# QuickRec v1.1 开发计划

> 版本: v1.1
> 创建时间: 2026-06-12
> 状态: 待开发
> 前置版本: v1.0（已完成）

---

## 1. 开发总览

### 1.1 v1.1 目标功能

| 编号 | 功能 | 说明 | 涉及模块 |
|-----|------|------|---------|
| N1 | 区域录制 | 修复 Win11 兼容性 + 确认对话框 + 最小尺寸提示 | area_selector, main |
| N2 | 音频录制 | 系统声音 / 麦克风 / 两者 | audio_capturer, recorder_manager, config, settings_dialog |
| N3 | 动态托盘菜单 | 空闲/录制中菜单切换 + Toast 通知 | tray_icon, main |
| N4 | 结果条 | 编码完成后显示结果 + 打开文件夹 | toolbar, main |
| N5 | 音频源设置 | 设置对话框新增音频源选择 | config, settings_dialog |
| N6 | 区域录制快捷键 | Ctrl+Shift+A 触发区域选择 | config, main, hotkey |

### 1.2 不变模块

| 模块 | 说明 |
|------|------|
| screen_capturer.py | 无需修改，region 参数已支持 |
| video_encoder.py | 无需修改 |
| file_namer.py | 无需修改 |
| disk_checker.py | 无需修改 |
| hotkey_manager.py | 无需修改，仅注册新快捷键 |

### 1.3 新增依赖

| 库 | 版本 | 用途 |
|----|------|------|
| soundcard | 0.4.6 | WASAPI loopback 系统声音捕获 |
| pyaudio | 0.2.14 | 麦克风音频捕获 |
| winotify | 1.1 | Windows Toast 通知 |
| FFmpeg binary | 8.0.1 | 音视频混合（subprocess 调用） |

> 注：系统声音原计划用 pyaudiowpatch，因其 WASAPI `read()` 阻塞挂起，最终改用 soundcard（见 bugfix-log Bug #24）。

---

## 2. 开发阶段

### 阶段 1：基础设施（无依赖，最先开发）

**目标**：为后续所有模块提供配置和常量基础。

#### 1.1 config.py 更新

**改动量**：小（仅新增2个配置项）

**内容**：
- `defaults` 字典新增 `"audio_source": "none"`
- `defaults` 字典新增 `"shortcut_area": "Ctrl+Shift+A"`
- 新增 `AUDIO_OPTIONS` 常量供 settings_dialog 使用

**验证**：
- [ ] `config.get("audio_source")` 返回 "none"
- [ ] `config.get("shortcut_area")` 返回 "Ctrl+Shift+A"
- [ ] 旧版配置文件加载后新字段有默认值

**任务文件**：[task-v1.1-config.md](task-v1.1-config.md)

---

### 阶段 2：区域录制（依赖：config, main.py 理解）

**目标**：修复 Win11 点击穿透，区域录制可用。

#### 2.1 area_selector.py 更新

**改动量**：中（Win11 修复 + 确认对话框 + 最小尺寸提示 + 边框优化）

**当前代码问题**：
- `Qt.Tool` 标志已移除（v1.0 修复中已处理）
- 选区太小时直接 `cancelled.emit()`，无提示
- 无确认对话框，松手即开始录制
- 边框为蓝色实线

**改动内容**：

1. **确认对话框**（新增）：
   - `mouseReleaseEvent` 中选区 >= MIN_SIZE 时，在选区中心显示确认浮动按钮
   - "开始录制" 按钮 → `region_selected` 信号 → `close()`
   - "取消" 按钮 → `cancelled` 信号 → `close()`
   - 实现：使用两个 QPushButton 作为浮动子控件，定位到选区中心

2. **最小尺寸提示**（新增）：
   - 选区 < MIN_SIZE 时显示红色提示文字 "选区太小 (最小 100x100)"
   - 使用 QLabel 浮动显示，QTimer.singleShot(1000) 后自动消失
   - 同时 `cancelled.emit()` → `close()`

3. **边框视觉优化**（修改）：
   - 选区边框从蓝色实线改为白色虚线：`QPen(QColor(255, 255, 255), 2, Qt.DashLine)`

**验证**：
- [ ] Win11 下可正常拖拽选区（不点击穿透）
- [ ] ESC 和右键可取消
- [ ] 选区太小时显示红色提示
- [ ] 确认对话框正常弹出和响应

**任务文件**：[task-v1.1-area_selector.md](task-v1.1-area_selector.md)

---

### 阶段 3：音频录制（依赖：config, FFmpeg binary）

**目标**：独立音频捕获模块，WAV 写入，能被 recorder_manager 集成。

#### 3.1 audio_capturer.py 新增

**改动量**：大（全新模块）

**新增文件**：`src/recorder/audio_capturer.py`

**核心类**：
```
AudioSource: NONE / SYSTEM / MICROPHONE / BOTH（普通常量类，值即配置字符串）
AudioCapturer:  # 系统声音: soundcard, 麦克风: pyaudio
  + __init__(source: str, output_dir: str)
  + start(output_stem: str = "") -> bool
  + stop() -> list[str]  # 返回临时 WAV 文件路径列表
  + get_sample_rate() -> int
  + get_channels() -> int
  - _find_loopback_mic()  # soundcard: 查找默认扬声器的 loopback 设备
  - _capture_loop()  # 音频捕获线程主循环
```

**关键设计决策**：
- 音频线程独立于录制线程，同时写入 WAV 临时文件
- BOTH 模式：两路独立 WAV 文件（不同采样率无法直接合并）
- WASAPI 系统声音设备查找：`soundcard` 的 `all_microphones(include_loopback=True)`，匹配默认扬声器对应的 loopback 设备
- 初始化失败时 `start()` 返回 `False`，recorder_manager 降级为无声录制
- `stop()` 关闭音频流、关闭 WAV 文件、返回路径列表

**WAV 临时文件命名**：
- SYSTEM 模式：`<output_stem>.audio_sys.wav`
- MICROPHONE 模式：`<output_stem>.audio_mic.wav`
- BOTH 模式：两个文件

**验证**：
- [ ] SYSTEM 模式可捕获系统声音并写入 WAV 文件
- [ ] MICROPHONE 模式可捕获麦克风输入并写入 WAV 文件
- [ ] BOTH 模式可同时捕获两路音频
- [ ] 音频设备初始化失败时不影响视频录制
- [ ] WAV 文件可被 FFmpeg 正确识别

**任务文件**：[task-v1.1-audio_capturer.md](task-v1.1-audio_capturer.md)

#### 3.2 FFmpeg 打包配置

**改动量**：小

**内容**：
1. 下载 FFmpeg Windows 静态编译版，放置 `ffmpeg/ffmpeg.exe`
2. `build_std.spec` 的 **`datas`** 添加 `('ffmpeg/ffmpeg.exe', 'ffmpeg')`
3. `.gitignore` 添加 `ffmpeg/`
4. `_get_ffmpeg_path()` frozen 分支优先用 `sys._MEIPASS`（onedir 下指向 `_internal`）定位

**验证**：
- [ ] `ffmpeg/ffmpeg.exe -version` 可运行
- [ ] 打包后 `dist/QuickRec/_internal/ffmpeg/ffmpeg.exe` 存在

**任务文件**：[task-v1.1-ffmpeg_setup.md](task-v1.1-ffmpeg_setup.md)

---

### 阶段 4：录制控制集成（依赖：audio_capturer, FFmpeg）

**目标**：recorder_manager 支持区域录制模式和音频混合。

#### 4.1 recorder_manager.py 更新

**改动量**：大（核心改动)

**当前代码要点**：
- `start_fullscreen()` → `_start(region=None)`，已支持 region 参数
- `_start()` 方法中 ScreenCapturer 延迟初始化
- `_stop_and_encode()` 后台线程处理录制结束
- `_encode_loop()` 后台线程处理编码
- 临时文件缓存方案（JPEG TLV 格式）

**改动内容**：

1. **RecordMode 枚举**（新增）：
   - `FULLSCREEN = "fullscreen"`
   - `REGION = "region"`
   - 新增 `_mode` 字段，`start_fullscreen()` 设置 FULLSCREEN，`start_region()` 设置 REGION
   - 新增 `get_mode()` 方法

2. **`_start()` 方法扩展**（修改）：
   ```
   执行位置：在 ScreenCapturer 创建之后、录制线程启动之前
   新增逻辑：
   1. 读取 config 中 audio_source
   2. 转换为 AudioSource 枚举
   3. 若非 NONE，创建 AudioCapturer 实例并调用 start()
   4. start() 失败时 log 警告，置空 capturer，继续无声录制
   5. 新增字段初始化：_audio_capturer, _audio_source, _ffmpeg_path, _audio_temp_paths
   ```

3. **`_stop_and_encode()` 方法扩展**（修改）：
   ```
   执行位置：录制线程 join 之后、启动编码线程之前
   新增逻辑：
   1. 若 _audio_capturer 非空，调用 stop() 获取临时文件路径列表
   2. stop() 异常时 log 错误，置空 temp_paths
   3. 取消录制时：清理音频临时文件
   ```

4. **`_encode_loop()` 方法扩展**（修改）：
   ```
   执行位置：视频编码完成之后、清理之前
   新增逻辑（Step 2: 音频混合）：
   1. 若 _audio_temp_paths 非空且 _ffmpeg_path 可用：
      a. 重命名视频为 .video_only.mp4 临时文件
      b. 调用 _mix_audio_video()
      c. 成功后删除 .video_only.mp4
      d. 失败时恢复纯视频文件，log 错误
   2. 若有音频但无 FFmpeg：
      log 警告，保留纯视频
   3. 清理所有音频临时文件
   ```

5. **`_get_ffmpeg_path()` 方法**（新增）：
   - 搜索顺序：`sys.executable` 目录 → 项目目录 → 系统 PATH → 空字符串

6. **`_mix_audio_video()` 方法**（新增）：
   - 单音频源：`-c:v copy -c:a aac -b:a 192k -shortest`
   - BOTH 模式：`-filter_complex "[1:a][2:a]amerge=inputs=2[a]"`

**验证**：
- [ ] 全屏录制 + 无音频：与 v1.0 行为一致
- [ ] 全屏录制 + 系统声音：生成含音频的 MP4
- [ ] 音频初始化失败时：无声录制正常工作
- [ ] FFmpeg 不可用时：视频文件正常，log 警告
- [ ] 区域录制设置 RECORDING 模式

**任务文件**：[task-v1.1-recorder_manager.md](task-v1.1-recorder_manager.md)

---

### 阶段 5：UI 更新（依赖：config, area_selector）

**目标**：托盘动态菜单、Toast 通知、结果条、设置对话框更新。

#### 5.1 tray_icon.py 更新

**改动量**：大

**当前代码要点**：
- `_SignalBridge` 仅有 `start_requested`、`settings_requested`、`exit_requested` 三个信号
- `_build_menu()` 构建静态菜单，5 个选项
- 托盘回调通过 `_callbacks` 字典分发

**改动内容**：

1. **_SignalBridge 扩展**（修改）：
   ```
   新增信号：
   - start_fullscreen_requested = pyqtSignal()
   - start_region_requested = pyqtSignal()
   - pause_resume_requested = pyqtSignal()
   - stop_requested = pyqtSignal()
   
   原 start_requested 改为 start_fullscreen_requested
   新增 start_region_requested
   ```

2. **状态字段**（新增）：
   - `_is_recording: bool = False`
   - `_is_paused: bool = False`

3. **动态菜单**（修改）：
   - `_build_idle_menu()` → "全屏录制 / 区域录制 / 设置 / 打开保存文件夹 / 退出"
   - `_build_recording_menu()` → "暂停/继续 / 停止录制 / 设置 / 打开保存文件夹 / 退出"
   - 暂停/继续按钮文字根据 `_is_paused` 动态切换
   - 使用 `MenuItem` 的 `default` callable 参数
   - `set_recording_state(recording, paused)` 方法：切换菜单并调用 `_icon.update_menu()`

4. **回调处理**（修改）：
   ```
   _handle_start → _handle_start_fullscreen（重命名）
   新增 _handle_start_region
   新增 _handle_pause_resume
   新增 _handle_stop
   
   callbacks 键名更新：
   "start_fullscreen", "start_region", "pause_resume", "stop", "settings", "exit"
   ```

5. **Toast 通知**（新增）：
   ```
   show_notification_with_action(title, msg, action_label, action_callback):
     优先: winotify（Windows 10/11 Toast 通知）
     降级: pystray.notify()
   ```
   - winotify: 创建 Notification，添加 action 按钮
   - 导入失败时静默降级到 pystray

**验证**：
- [ ] 空闲状态显示：全屏录制 / 区域录制 / 设置 / 打开保存文件夹 / 退出
- [ ] 录制中状态显示：暂停/继续 / 停止录制 / 设置 / 打开保存文件夹 / 退出
- [ ] 暂停状态"暂停"变为"继续"
- [ ] Toast 通知显示"打开文件夹"按钮

**任务文件**：[task-v1.1-tray_icon.md](task-v1.1-tray_icon.md)

#### 5.2 toolbar.py 更新

**改动量**：中

**当前代码要点**：
- 4 个信号：paused、resumed、stopped、cancelled
- 3 个按钮：暂停、停止、取消
- `show_saving()` 显示保存中状态
- `set_paused()` 切换暂停/继续按钮文字

**改动内容**：

1. **新增信号**：
   - `open_folder_requested = pyqtSignal()` — 点击"📂 打开"按钮
   - `open_file_requested = pyqtSignal()` — 点击"已保存"按钮

2. **新增状态**：
   - `_result_mode: bool = False`
   - `_auto_close_timer: QTimer` — 5 秒自动关闭
   - `_output_path: str = ""`

3. **`show_result(output_path, file_size)` 方法**（新增）：
   - 停止计时器，显示最终时长
   - 红色指示灯 → 绿色 ✓
   - 替换按钮为："已保存" | "📂 打开" | "✕ 关闭"
   - "已保存" → `open_file_requested` 信号
   - "📂 打开" → `open_folder_requested` 信号
   - "✕ 关闭" → 关闭工具栏
   - 启动 5 秒自动关闭定时器
   - 点击任何按钮时停止定时器

4. **按钮切换逻辑**：
   - 用 `QHBoxLayout.clear()` 或隐藏/显示控件切换按钮组
   - 录制中显示：暂停 | 停止 | 取消
   - 保存中显示：所有按钮禁用（已有）
   - 结果条显示：已保存 | 📂 打开 | ✕ 关闭

**验证**：
- [ ] 编码完成后工具栏切换到结果条模式
- [ ] "已保存" 按钮打开视频文件
- [ ] "📂 打开" 按钮打开文件夹并选中
- [ ] 5 秒后自动关闭
- [ ] 点击按钮后停止自动关闭定时器

**任务文件**：[task-v1.1-toolbar.md](task-v1.1-toolbar.md)

#### 5.3 settings_dialog.py 更新

**改动量**：小

**当前代码要点**：
- 表单布局：保存路径 / 画质 / 帧率 / 开始快捷键 / 停止快捷键 / 暂停快捷键
- `_ShortcutRecorder` 自定义快捷键录制控件

**改动内容**：

1. **音频源选择下拉框**（新增）：
   - `_combo_audio_source: QComboBox`
   - 使用 `config.AUDIO_OPTIONS` 填充选项
   - 标签："音频源"
   - 插入在帧率行之后

2. **区域录制快捷键**（新增）：
   - `_shortcut_area: _ShortcutRecorder`
   - 默认值："Ctrl+Shift+A"
   - 标签："区域录制快捷键"
   - 插入在暂停快捷键之后

3. **配置加载/保存**（修改）：
   - `_load_config()`：读取 `audio_source` 和 `shortcut_area`
   - `_save_config()`：写入 `audio_source` 和 `shortcut_area`

**验证**：
- [ ] 对话框显示音频源下拉框和区域快捷键
- [ ] 加载时回显当前配置
- [ ] 保存时正确写入新配置项
- [ ] 旧版配置加载后新字段有默认值

**任务文件**：[task-v1.1-settings_dialog.md](task-v1.1-settings_dialog.md)

---

### 阶段 6：主程序集成（依赖：所有模块）

**目标**：将所有 v1.1 模块通过 main.py 串联。

#### 6.1 main.py 更新

**改动量**：中

**当前代码要点**：
- `_SavedBridge` 和 `_HotkeyBridge` 两个信号桥
- `_on_start_recording` / `_on_stop_recording` / `_on_pause_resume` 三个回调
- 托盘回调字典：`{"start": ..., "settings": ..., "exit": ...}`
- `_handle_saved()` 简单显示通知

**改动内容**：

1. **_AreaBridge 信号桥**（新增）：
   ```python
   class _AreaBridge(QObject):
       region_selected = pyqtSignal(int, int, int, int)
       cancelled = pyqtSignal()
   ```

2. **_HotkeyBridge 扩展**（修改）：
   - 新增 `area_requested = pyqtSignal()`
   - 连接 `area_requested` → `_on_start_region`

3. **托盘回调扩展**（修改）：
   ```python
   callbacks = {
       "start_fullscreen": self._on_start_fullscreen,  # 原 "start"
       "start_region": self._on_start_region,           # 新增
       "pause_resume": self._on_pause_resume,           # 新增
       "stop": self._on_stop_recording,                 # 新增
       "settings": self._show_settings,
       "exit": self._on_exit,
   }
   ```

4. **新增方法**：
   - `_on_start_fullscreen()`：原 `_on_start_recording()` 重命名
   - `_on_start_region()`：创建 AreaSelector 并连接信号
   - `_on_region_selected(x, y, w, h)`：调用 `recorder.start_region()`
   - `_on_selection_cancelled()`：空操作

5. **快捷键注册扩展**（修改）：
   ```python
   shortcut_area = self._config.get("shortcut_area", "Ctrl+Shift+A")
   self._hotkey.register(shortcut_area, self._hotkey_bridge.area_requested.emit)
   ```

6. **`_handle_saved()` 增强**（修改）：
   - 计算文件大小
   - 调用 `tray.show_notification_with_action()` 显示 Toast 通知
   - 调用 `toolbar.show_result()` 显示结果条
   - `tray.set_recording_state(False)` 切换回空闲菜单

7. **工具栏信号连接**（新增）：
   - `toolbar.open_folder_requested` → `lambda: os.startfile(os.path.dirname(path))` 或 `subprocess.run(["explorer.exe", "/select," + path])`
   - `toolbar.open_file_requested` → `lambda: os.startfile(path)`

**验证**：
- [ ] 快捷键 Ctrl+Shift+A 触发区域选择器
- [ ] 托盘菜单"区域录制"触发区域选择器
- [ ] 区域选择完成 → 开始区域录制 → 状态正确
- [ ] 编码完成后 Toast 通知 + 结果条
- [ ] 结果条"打开"按钮功能正常

**任务文件**：[task-v1.1-main.md](task-v1.1-main.md)

---

### 阶段 7：集成测试与打包

**目标**：全功能验证 + PyInstaller 打包。

#### 7.1 功能测试

| 测试场景 | 验证点 |
|---------|--------|
| 全屏录制（无音频） | 与 v1.0 行为一致 |
| 全屏录制（系统声音） | MP4 含音频 |
| 全屏录制（麦克风） | MP4 含音频 |
| 全屏录制（两者都有） | MP4 含双路混合音频 |
| 区域录制 | 选区正常、确认对话框、录制正常 |
| 区域录制 + 音频 | 区域帧率正常、音频同步 |
| 音频初始化失败 | 无声录制正常，log 警告 |
| FFmpeg 不可用 | 纯视频正常，log 警告 |
| 托盘空闲菜单 | 全屏录制 / 区域录制 / 设置 / 打开文件夹 / 退出 |
| 托盘录制中菜单 | 暂停/继续 / 停止 / 设置 / 打开文件夹 / 退出 |
| Toast 通知 | winotify 显示"打开文件夹"按钮 |
| 结果条 | 显示时长 / 已保存 / 打开 / 关闭 / 5秒自动关闭 |
| 设置对话框 | 音频源选择、区域快捷键 |
| 快捷键 Ctrl+Shift+A | 触发区域选择 |

#### 7.2 打包验证

```bash
cd E:\CC_Learning\QuickRec_dev
D:\Work\Software\Python\Scripts\pyinstaller.exe build_std.spec --noconfirm
```

- [ ] `dist/QuickRec/QuickRec.exe` 可运行
- [ ] `dist/QuickRec/ffmpeg/ffmpeg.exe` 存在
- [ ] 打包体积 < 80MB
- [ ] 无音频场景正常工作
- [ ] 通知功能正常

---

## 3. 开发顺序与依赖图

```
阶段 1: config.py（无依赖）
  │
  ├─→ 阶段 2: area_selector.py（依赖: config 理解）
  │
  ├─→ 阶段 3: audio_capturer.py（依赖: config）
  │     │
  │     └─→ 阶段 4: recorder_manager.py（依赖: audio_capturer）
  │
  ├─→ 阶段 5: UI 模块（可并行）
  │     ├─ 5.1: tray_icon.py
  │     ├─ 5.2: toolbar.py
  │     └─ 5.3: settings_dialog.py
  │
  └─→ 阶段 6: main.py（依赖: 所有模块）
        │
        └─→ 阶段 7: 集成测试 + 打包
```

**关键路径**：config → audio_capturer → recorder_manager → main → 测试

**可并行开发**：area_selector、tray_icon、toolbar、settings_dialog 可同时进行

---

## 4. 风险与注意事项

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| Win11 区域选择器仍点击穿透 | 区域录制不可用 | 已在 v1.0 修复（移除 Qt.Tool），确认测试 |
| soundcard loopback 设备兼容性 | 部分设备无法捕获系统声音 | start() 返回 False 时降级为无声录制 |
| BOTH 模式两路采样率不同 | 合并后音频速度异常 | FFmpeg amerge 滤镜自动重采样 |
| FFmpeg 打包体积增加 | 安装包增加 ~95MB | 仅打包 ffmpeg.exe，可接受 |
| pystray 动态菜单 | 录制状态切换后菜单不刷新 | 使用 MenuItem callable + icon.update_menu() |
| winotify 导入失败 | Toast 通知降级为纯文本 | 降级链：winotify → pystray.notify() |

---

## 5. 文件改动清单

| 文件 | 改动类型 | 改动量 |
|------|---------|--------|
| src/config.py | 更新 | 小（+2 配置项 + 1 常量） |
| src/ui/area_selector.py | 更新 | 中（确认对话框 + 提示 + 边框） |
| src/recorder/audio_capturer.py | 新增 | 大（全新模块 ~200行） |
| src/recorder/recorder_manager.py | 更新 | 大（音频集成 + FFmpeg + RecordMode） |
| src/ui/tray_icon.py | 更新 | 大（动态菜单 + Toast + 信号扩展） |
| src/ui/toolbar.py | 更新 | 中（结果条模式 + 新信号） |
| src/ui/settings_dialog.py | 更新 | 小（+1 下拉框 + 1 快捷键） |
| src/main.py | 更新 | 中（_AreaBridge + 区域流程 + 托盘回调） |
| ffmpeg/ffmpeg.exe | 新增 | 二进制文件 |
| build_std.spec | 更新 | 小（+1 binary 条目） |
| .gitignore | 更新 | 小（+ ffmpeg/） |
| requirements.txt | 更新 | 小（+3 依赖） |