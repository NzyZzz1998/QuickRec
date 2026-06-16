# QuickRec v1.2 开发计划

> 版本: v1.2
> 创建时间: 2026-06-13
> 状态: 已完成（窗口录制延期）
> 前置版本: v1.1（已完成，tag v1.1）

---

## 1. 开发总览

### 1.1 v1.2 目标功能

| 编号 | 功能 | 说明 | 涉及模块 |
|-----|------|------|---------|
| N1 | 指定窗口录制 | 窗口枚举选择 + 边框高亮 + 跟随移动 + 丢失暂停（延期） | window_selector, window_highlighter, recorder_manager, screen_capturer, main |
| N2 | 鼠标点击高亮 | 左键点击扩散圆圈动画，仅屏幕叠加层，默认关闭 | click_highlighter, config, settings_dialog, main |
| N3 | 原生画质优化 | "原生"档动态匹配主显示器分辨率，设置界面显示实际值 | config, settings_dialog |
| N4 | 开机自启 | 注册表 HKEY_CURRENT_USER\Run 操作，设置中勾选 | autostart, settings_dialog, config |
| N5 | 录制倒计时 | 工具栏内 3→2→1 倒计时显示，可 ESC/快捷键取消 | toolbar, config, settings_dialog, main |
| N6 | 窗口录制快捷键 | Ctrl+Shift+W 触发窗口选择 | config, settings_dialog, main, hotkey |
| N7 | 托盘菜单更新 | 空闲菜单新增"窗口录制"选项 | tray_icon, main |

### 1.2 不变模块

| 模块 | 说明 |
|------|------|
| area_selector.py | 无需修改，区域录制逻辑不变 |
| video_encoder.py | 无需修改 |
| audio_capturer.py | 无需修改，窗口录制共享音频流程 |
| file_namer.py | 无需修改 |
| disk_checker.py | 无需修改 |

### 1.3 新增依赖

无。v1.2 所有新功能使用 Python 标准库（ctypes Win32 API、winreg）或已有依赖（pynput、PyQt5）实现。

---

## 2. 开发阶段

### 阶段 1：基础设施（无依赖，最先开发）

**目标**：为后续所有模块提供配置和常量基础。

#### 1.1 config.py 更新

**改动量**：小（+5 配置项 + 1 静态方法）

**内容**：
- `defaults` 字典新增 `"shortcut_window": "Ctrl+Shift+W"`
- `defaults` 字典新增 `"show_countdown": False`
- `defaults` 字典新增 `"countdown_seconds": 3`
- `defaults` 字典新增 `"mouse_highlight": False`
- `defaults` 字典新增 `"auto_start": False`
- 新增静态方法 `get_native_resolution()` → 调用 `GetSystemMetrics(0/1)` 获取主显示器分辨率

**验证**：
- [ ] `config.get("shortcut_window")` 返回 `"Ctrl+Shift+W"`
- [ ] `config.get("show_countdown")` 返回 `False`
- [ ] `config.get("mouse_highlight")` 返回 `False`
- [ ] `config.get("auto_start")` 返回 `False`
- [ ] `ConfigManager.get_native_resolution()` 返回正确的主显示器分辨率
- [ ] 旧版配置文件加载后新字段有默认值

#### 1.2 autostart.py 新增

**改动量**：小（全新工具模块，~50 行）

**内容**：
- `is_autostart_enabled() -> bool`：读取 `HKEY_CURRENT_USER\Run\QuickRec`
- `enable_autostart() -> bool`：写入注册表项
- `disable_autostart() -> bool`：删除注册表项
- `_get_executable_path() -> str`：获取当前可执行文件路径（打包后=sys.executable）

**验证**：
- [ ] `enable_autostart()` 写入注册表后 `is_autostart_enabled()` 返回 True
- [ ] `disable_autostart()` 删除注册表项后 `is_autostart_enabled()` 返回 False
- [ ] 打包后路径正确指向 QuickRec.exe

---

### 阶段 2：鼠标点击高亮（依赖：config）

**目标**：实现屏幕叠加层的鼠标点击扩散圆圈动画。

#### 2.1 click_highlighter.py 新增

**改动量**：中（全新模块，~120 行）

**核心类**：

```python
class _ClickBridge(QObject):
    """pynput 鼠标线程 → Qt 主线程信号桥"""
    click_occurred = pyqtSignal(int, int)   # (x, y)

class ClickCircle(QWidget):
    """单击扩散圆圈动画（~300ms）"""
    # 半径 0→30px + 透明度 1→0

class ClickHighlighter:
    """鼠标点击高亮管理器"""
    + start()           # 启动 pynput 鼠标监听
    + stop()            # 停止监听
    + set_enabled(bool) # 动态开关
    + is_running()      # 是否正在监听
```

**关键设计**：
- 仅左键触发高亮：`pynput.mouse.Button.left`
- `ClickCircle` 是 `QWidget`，帧标志：`Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`
- 设置 `Qt.WA_TransparentForMouseInput` 使圆圈不拦截鼠标事件
- `QPropertyAnimation` 控制半径和透明度动画，300ms 后 `deleteLater()`
- pynput 鼠标监听通过 `_ClickBridge` 信号桥转发到 Qt 主线程

**验证**：
- [ ] 左键点击显示扩散圆圈动画
- [ ] 右键点击不显示
- [ ] 动画 300ms 后自动消失
- [ ] `mouse_highlight=False` 时不启动监听
- [ ] 录制停止后高亮停止

---

### 阶段 3：录制倒计时（依赖：config，可与阶段 2 并行）

**目标**：在工具栏内显示 3→2→1 倒计时，倒计时结束后开始录制。

#### 3.1 toolbar.py 更新

**改动量**：中（+倒计时模式，~80 行新增）

**新增信号**：
- `countdown_finished = pyqtSignal()` — 倒计时结束

**新增状态**：
- `_countdown_mode: bool = False`
- `_countdown_value: int = 0`
- `_countdown_timer: QTimer` — 1 秒间隔

**新增方法**：
- `start_countdown(seconds: int = 3)` — 显示工具栏，开始倒计时
- `cancel_countdown()` — 取消倒计时，隐藏工具栏
- `_countdown_tick()` — 每秒递减，到 0 时发射 `countdown_finished`
- `_show_countdown_ui()` — 显示大号数字 + "点击取消 / 按 ESC" 提示
- `_hide_countdown_ui()` — 恢复录制 UI

**交互**：
- 倒计时期间按 ESC → `keyPressEvent` 检测 → `cancel_countdown()`
- 倒计时期间按录制快捷键（Ctrl+Shift+R/W/A） → 信号桥 → `cancel_countdown()`
- 非录制模式下 `show_countdown` 为 False → 不显示倒计时，直接开始录制

**验证**：
- [ ] 开启倒计时后点击"开始录制"显示 3→2→1
- [ ] 倒计时结束后开始录制
- [ ] ESC 键取消倒计时
- [ ] 关闭倒计时配置后直接开始录制
- [ ] 倒计时期间工具栏显示大号数字

---

### 阶段 4：开机自启 + 原生画质 + 设置界面（依赖：config、autostart）

**目标**：完成设置对话框的 v1.2 新增控件和交互。

#### 4.1 settings_dialog.py 更新

**改动量**：中（+5 个控件 + 动态画质显示）

**新增控件**：
- `_cb_auto_start: QCheckBox` — 开机自启复选框
- `_cb_countdown: QCheckBox` — 录制倒计时复选框
- `_cb_mouse_highlight: QCheckBox` — 鼠标点击高亮复选框
- `_shortcut_window: _ShortcutRecorder` — 窗口录制快捷键

**修改控件**：
- `_combo_quality: QComboBox` — "原生"档显示动态分辨率如 "原生(1920×1080)"

**`_save_config()` 新增逻辑**：
- 开机自启复选框：勾选时同时调用 `autostart.enable_autostart()`，取消时调用 `autostart.disable_autostart()`
- 倒计时/鼠标高亮复选框：仅保存到 config
- 窗口录制快捷键：保存到 config

**`_load_config()` 新增逻辑**：
- 读取新配置项回显到控件
- 开机自启复选框初始状态与注册表实际值同步（`autostart.is_autostart_enabled()`）

**设置界面布局**：

```
┌─ QuickRec 设置 ───────────────────────────────┐
│  保存路径    [C:\Users\xxx\Videos\QuickRec]    │
│  画质        ● 原生(1920×1080)  ○ 高(1080p)   │
│              ○ 中(720p)  ○ 低(480p)            │
│  帧率        ● 30fps   ○ 60fps                 │
│  音频源      ○ 无  ● 系统声音                   │
│              ○ 麦克风  ○ 两者都有               │
│  ☐ 开机自启  ☑ 录制倒计时(3秒)                 │
│  ☐ 鼠标点击高亮                               │
│  快捷键      开始: [Ctrl+Shift+R]              │
│              停止: [Ctrl+Shift+S]              │
│              暂停: [Ctrl+Shift+P]              │
│              区域: [Ctrl+Shift+A]              │
│              窗口: [Ctrl+Shift+W]              │
│              [ 保存 ]  [ 取消 ]                  │
└────────────────────────────────────────────────┘
```

**验证**：
- [ ] 开机自启勾选后注册表有 QuickRec 项
- [ ] 取消勾选后注册表项已删除
- [ ] 开机自启初始状态与注册表一致
- [ ] 原生画质显示当前实际分辨率
- [ ] 新配置项保存和加载正确
- [ ] 旧版配置加载后新字段有默认值

---

### 阶段 5：窗口录制核心（依赖：config）

**目标**：实现窗口枚举、选择、录制、位置跟踪、丢失处理全链路。

#### 5.1 window_selector.py 新增

**改动量**：中（全新模块，~150 行）

**核心类**：

```python
class WindowSelector(QDialog):
    """窗口选择对话框"""
    window_selected = pyqtSignal(int, str)   # (hwnd, title)
    cancelled = pyqtSignal()

    + __init__(parent=None)
    + refresh_windows()               # 刷新窗口列表
    - _enum_visible_windows() -> list   # Win32 EnumWindows + 过滤
    - _on_item_double_clicked(item)    # 双击选择
    - _on_select_clicked()             # 确定按钮
    - _on_cancel_clicked()             # 取消按钮
```

**窗口过滤规则**：
- 排除不可见窗口（`IsWindowVisible` 为 False）
- 排除无标题窗口（空字符串）
- 排除系统窗口（类名黑名单：Progman, Shell_TrayWnd, WorkerW, IME 等）
- 排除 QuickRec 自身窗口

**验证**：
- [ ] 对话框显示当前可见窗口列表（标题 + 图标）
- [ ] 双击或选择后点击"选择"发射 `window_selected` 信号
- [ ] 系统桌面和任务栏不在列表中
- [ ] 点击"取消"或关闭对话框发射 `cancelled` 信号

#### 5.2 window_highlighter.py 新增

**改动量**：小（全新模块，~60 行）

**核心类**：

```python
class WindowHighlighter(QWidget):
    """窗口边框绿色虚线高亮"""
    - _hwnd: int
    - _timer: QTimer    # 每 100ms 更新位置
    + show_highlight()
    + hide_highlight()
    - _update_position()   # GetWindowRect → 更新 geometry
    - paintEvent(event)    # 绿色虚线边框
```

**关键设计**：
- 窗口标志：`Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`
- 设置 `Qt.WA_TransparentForMouseInput` 使边框不拦截鼠标事件
- 边框参数：`QPen(QColor(0, 200, 0, 200), 3, Qt.DashLine)`
- `_update_position()` 每 100ms 调用 `GetWindowRect` 跟踪窗口位置

**验证**：
- [ ] 绿色虚线边框正确包围目标窗口
- [ ] 窗口移动时边框跟随
- [ ] 窗口最小化时边框隐藏
- [ ] 窗口关闭时边框销毁

#### 5.3 screen_capturer.py 更新

**改动量**：小（+1 方法，~10 行）

**新增方法**：
```python
def update_region(self, region: tuple) -> None:
    """动态更新捕获区域（窗口录制跟踪窗口位置）"""
    self._region = region
    left, top, width, height = region
    self._dxcam_region = (left, top, left + width, top + height)
```

**验证**：
- [ ] `update_region()` 后 `capture_frame()` 返回新区域的帧
- [ ] 区域更新不影响录制帧率

#### 5.4 recorder_manager.py 更新

**改动量**：中（RecordMode.WINDOW + start_window + 窗口跟踪 + 丢失处理，~100 行新增）

**新增**：

1. `RecordMode.WINDOW` 枚举值

2. `start_window(hwnd: int) -> bool` 方法：
   - 验证窗口有效性
   - 获取窗口标题
   - 设置 `_mode = RecordMode.WINDOW`，`_window_hwnd = hwnd`
   - 调用 `_start(hwnd=hwnd)`

3. `_start()` 扩展 `hwnd` 参数：
   - `hwnd` 非空时 → `RecordMode.WINDOW`，获取初始窗口区域作为 region

4. `_record_loop()` 扩展：
   - `RecordMode.WINDOW` 时每帧调用 `GetWindowRect(hwnd)` 获取最新位置
   - 窗口宽度/高度 < 10 时判定为最小化 → 通过 `_WindowLostBridge` 通知主线程
   - `GetWindowRect` 返回失败时判定为窗口关闭 → 通知主线程

5. `_WindowLostBridge` 信号桥：
   ```python
   window_lost = pyqtSignal(str)  # "closed" / "minimized"
   ```

**验证**：
- [ ] `start_window(hwnd)` 正确设置 WINDOW 模式
- [ ] 录制过程中窗口移动时捕获区域跟随
- [ ] 窗口最小化时暂停录制并提示
- [ ] 窗口关闭时暂停录制并提示
- [ ] 窗口录制 + 音频正常工作

---

### 阶段 6：主程序集成（依赖：所有模块）

**目标**：在 main.py 中串联所有 v1.2 功能。

#### 6.1 main.py 更新

**改动量**：中（新增信号桥 + 窗口录制流程 + 倒计时流程 + 高亮控制，~120 行新增）

**新增信号桥**：
```python
class _WindowBridge(QObject):
    window_selected = pyqtSignal(int, str)    # (hwnd, title)
    cancelled = pyqtSignal()

class _WindowLostBridge(QObject):
    window_lost = pyqtSignal(str)              # "closed" / "minimized"
```

**`_HotkeyBridge` 扩展**：
- 新增 `window_requested = pyqtSignal()`

**托盘回调扩展**：
- `"start_window": self._on_start_window`

**新增方法**：
- `_on_start_window()` — 显示 WindowSelector 对话框
- `_on_window_selected(hwnd, title)` — 创建 WindowHighlighter + 启动录制（或先倒计时）
- `_do_start_window(hwnd)` — 实际调用 `recorder.start_window(hwnd)`
- `_on_window_lost(reason)` — 暂停录制 + 弹窗提示
- `_update_highlight_state()` — 根据配置和录制状态启停 ClickHighlighter

**修改方法**：
- `_on_start_fullscreen()` — 加入倒计时逻辑
- `_on_start_region()` — 加入倒计时逻辑（通过 `_on_region_selected` 中转）
- `_handle_saved()` — 清理 WindowHighlighter + 停止 ClickHighlighter

**快捷键注册扩展**：
```python
shortcut_window = self._config.get("shortcut_window", "Ctrl+Shift+W")
self._hotkey.register(shortcut_window, self._hotkey_bridge.window_requested.emit)
```

6.2 tray_icon.py 更新

**改动量**：小

- `_build_idle_menu()` 新增 "窗口录制" 菜单项
- `_SignalBridge` 新增 `start_window_requested = pyqtSignal()`
- 回调字典新增 `"start_window"` 键

**验证**：
- [ ] 托盘菜单空闲状态显示"窗口录制"
- [ ] 快捷键 Ctrl+Shift+W 触发窗口选择
- [ ] 窗口选择后正确开始录制
- [ ] 倒计时流程正确（全屏/区域/窗口）
- [ ] 鼠标高亮在录制开始时启用、停止时停止
- [ ] 窗口关闭/最小化时暂停并提示

---

### 阶段 7：集成测试与打包

**目标**：全功能验证 + PyInstaller 打包。

#### 7.1 功能测试

| 测试场景 | 验证点 |
|---------|--------|
| 全屏录制（无音频） | 与 v1.1 行为一致 |
| 全屏录制（倒计时开启） | 显示 3→2→1 → 开始录制 |
| 全屏录制（倒计时开启，ESC 取消） | 取消后回到空闲 |
| 区域录制 | 与 v1.1 行为一致 |
| 窗口录制 | ~~从列表选择 → 绿色边框 → 录制内容含边框~~ 延期 |
| 窗口录制 + 移动窗口 | ~~帧内容跟随窗口位置~~ 延期 |
| 窗口录制 + 最小化 | ~~暂停录制 + 提示对话框~~ 延期 |
| 窗口录制 + 关闭窗口 | ~~暂停录制 + 停止并保存~~ 延期 |
| 窗口录制 + 音频 | ~~窗口模式 + 系统声音/麦克风正常~~ 延期 |
| 鼠标点击高亮（开启） | 左键点击显示扩散圆圈，右键不显示 |
| 鼠标点击高亮（关闭） | 配置关闭时不显示 |
| 鼠标点击高亮（不在录制中） | 不响应 |
| 原生画质显示 | 设置界面显示"原生(1920×1080)" |
| 开机自启（开启） | 注册表有 QuickRec 项 |
| 开机自启（关闭） | 注册表项已删除 |
| 托盘菜单（空闲） | 全屏录制 / 区域录制 / 窗口录制 / 设置 / 退出 |
| 设置对话框 | 所有新控件正确保存/加载 |

#### 7.2 打包验证

```bash
cd E:\CC_Learning\QuickRec_dev
D:\Work\Software\Python\Scripts\pyinstaller.exe build_std.spec --noconfirm
```

- [ ] `dist/QuickRec/QuickRec.exe` 可运行
- [ ] 开机自启功能正常（注册表操作）
- [ ] ~~窗口录制功能正常~~ 延期
- [ ] 鼠标点击高亮正常
- [ ] 无新增依赖导致打包失败

---

## 3. 开发顺序与依赖图

```
阶段 1: config.py + autostart.py（无依赖，最先开发）
  │
  ├─→ 阶段 2: click_highlighter.py（依赖: config）
  │
  ├─→ 阶段 3: toolbar.py 倒计时（依赖: config，可与阶段 2 并行）
  │
  ├─→ 阶段 4: settings_dialog.py（依赖: config, autostart）
  │
  ├─→ 阶段 5: 窗口录制核心（依赖: config）
  │     ├─ 5.1: window_selector.py
  │     ├─ 5.2: window_highlighter.py
  │     ├─ 5.3: screen_capturer.py update_region()
  │     └─ 5.4: recorder_manager.py WINDOW 模式
  │
  └─→ 阶段 6: main.py 集成（依赖: 所有模块）
        │
        └─→ 阶段 7: 集成测试 + 打包
```

**关键路径**：config → window_selector → recorder_manager(WINDOW) → main → 测试

**可并行开发**：click_highlighter、toolbar 倒计时可同时进行

---

## 4. 风险与注意事项

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| Win32 EnumWindows 过滤不完善 | 系统窗口出现在列表中 | 黑名单 + IsWindowVisible 过滤，实测补充 |
| GetWindowRect 多显示器偏移 | 窗口在副屏时坐标偏移 | 起始版本仅支持主显示器，v1.2 暂不处理多屏偏移 |
| Qt.Tool 叠加层 Win11 穿透 | ClickCircle/WindowHighlighter 不可见 | 设置 WA_TransparentForMouseInput（不需接收输入）；若仍穿透则改用 WS_EX layered |
| 窗口录制 DPI 缩放 | 高 DPI 显示器窗口尺寸不准 | 使用 DPI-aware 版本 GetWindowRect，或 ScreenCapturer 捕获时考虑缩放因子 |
| pynput 鼠标监听与键盘监听冲突 | 两个 Listener 线程同时运行 | pynput 支持 keyboard.Listener 和 mouse.Listener 独立运行，互不干扰 |
| 开机自启安全软件拦截 | 注册表写入被安全软件警告 | 仅写 HKCU\Run，无管理员权限要求；提示用户允许 |
| 倒计时 QPropertyAnimation 与录制线程冲突 | 动画卡顿 | 倒计时在 Qt 主线程，与录制线程通过信号桥通信，无直接冲突 |

---

## 5. 文件改动清单

| 文件 | 改动类型 | 改动量 |
|------|---------|--------|
| src/config.py | 更新 | 小（+5 配置项 + 1 静态方法） |
| src/utils/autostart.py | 新增 | 小（~50 行） |
| src/ui/click_highlighter.py | 新增 | 中（~120 行） |
| src/ui/window_selector.py | 新增 | 中（~150 行） |
| src/ui/window_highlighter.py | 新增 | 小（~60 行） |
| src/ui/toolbar.py | 更新 | 中（+倒计时模式，~80 行新增） |
| src/ui/settings_dialog.py | 更新 | 中（+4 控件 + 动态画质） |
| src/ui/tray_icon.py | 更新 | 小（+1 菜单项 + 1 信号） |
| src/recorder/recorder_manager.py | 更新 | 中（+WINDOW 模式 + 窗口跟踪，~100 行新增） |
| src/recorder/screen_capturer.py | 更新 | 小（+1 方法，~10 行） |
| src/main.py | 更新 | 中（+3 信号桥 + 窗口流程 + 倒计时 + 高亮，~120 行新增） |
| src/hotkey/hotkey_manager.py | 不变 | — |
| src/ui/area_selector.py | 不变 | — |
| src/recorder/audio_capturer.py | 不变 | — |
| src/recorder/video_encoder.py | 不变 | — |
| src/utils/file_namer.py | 不变 | — |
| src/utils/disk_checker.py | 不变 | — |