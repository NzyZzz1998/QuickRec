# QuickRec v1.2 详细技术设计文档

> 版本: v1.2
> 创建时间: 2026-06-12
> 状态: 已完成（窗口录制延期）
> 前置版本: v1.1（详见 Tec-design-v1.1.md）

---

## 1. 版本概述

### 1.1 v1.2 新增功能清单

基于 PRD 功能列表，v1.2 在 v1.1 基础上新增以下功能：

| 编号 | 功能 | 说明 | PRD 编号 |
|-----|------|------|---------|
| N1 | 指定窗口录制 **（延期）** | 从当前可见窗口列表中选择一个窗口，录制其完整内容（含边框）；最小化/缩放/关闭时暂停并提示 | F3 |
| N2 | 鼠标点击高亮 | 左键点击时在屏幕叠加层显示扩散圆圈动画；默认关闭，设置中可开关；仅屏幕可见，不渲染到视频帧 | F8 |
| N3 | 画质原生档优化 | "原生"画质动态匹配主显示器分辨率并显示实际值如"原生(1920×1080)" | P2 |
| N4 | 开机自启 | 设置中勾选项，写入注册表 HKEY_CURRENT_USER\Run，启动后静默驻留托盘 | P6 |
| N5 | 录制倒计时 | 可选 3 秒倒计时，在工具栏显示 3→2→1；倒计时期间可 ESC 或快捷键取消；设置中开关 | P7 |
| N6 | 窗口录制快捷键 | Ctrl+Shift+W 触发窗口录制选择 | K6 |

**关键设计决策**：

1. 鼠标点击高亮：**仅屏幕叠加层**，不渲染到视频帧。默认关闭，设置中可开关
2. 窗口录制边框高亮：**仅屏幕叠加层**，绿色虚线边框标示录制目标窗口 — **延期（随窗口录制功能一同延期）**
3. 窗口移动跟踪：**跟随窗口移动**，每帧通过 GetWindowRect 更新捕获区域 — **延期（随窗口录制功能一同延期）**
4. 倒计时显示：**在工具栏内显示** 3→2→1，无全屏遮罩
5. 窗口录制 + 音频：**共享 RecorderManager 流程**，支持所有音频源模式

### 1.2 v1.2 不包含

- 多显示器支持（选择录制哪个屏幕）→ v2.0+
- 画中画模式（摄像头小窗）→ v2.0+
- 简单剪辑（裁剪头尾）→ 推迟
- 编码格式优化（mp4v → x264）→ v2.0+

---

## 2. 模块设计

### 2.1 窗口录制模块 (window_selector.py) — 新增

**职责**：枚举当前可见窗口列表，让用户选择一个窗口作为录制目标。

**技术选型**：使用 Win32 API `ctypes` 调用 `EnumWindows` + `GetWindowText` + `IsWindowVisible` 枚举窗口，`GetWindowRect` 获取窗口位置。

```python
class WindowSelector(QDialog):
    """窗口选择对话框

    显示当前可见窗口列表，用户选择一个窗口后，
    通过 window_selected 信号返回窗口句柄（HWND）和标题。
    """

    window_selected = pyqtSignal(int, str)   # (hwnd, title)
    cancelled = pyqtSignal()

    - _windows: list[tuple[int, str, QRect]]     # (hwnd, title, rect) 列表

    + __init__(parent=None)
    + refresh_windows()                 # 刷新窗口列表
    - _enum_windows() -> list           # Win32 API 枚举可见窗口
    - _on_item_double_clicked(item)     # 双击选择窗口
    - _on_select_clicked()              # 确定按钮
    - _on_cancel_clicked()              # 取消按钮

    # 内部方法
    @staticmethod
    def _enum_visible_windows() -> list[tuple[int, str, QRect]]:
        """枚举所有可见窗口

        过滤规则：
        - 排除不可见窗口（IsWindowVisible 为 False）
        - 排除无标题窗口（空字符串或仅空白）
        - 排除系统窗口（类名为隐藏窗口列表）
        - 排除自身窗口（QuickRec 工具栏、区域选择器等）
        返回: [(hwnd, title, rect), ...]
        """
```

**对话框 UI**：

```
┌─ 选择录制窗口 ──────────────────────────────────┐
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │ 🖼 Chrome - Google                        │ │
│  │ 📄 Visual Studio Code                     │ │
│  │ 📁 Windows 资源管理器                      │ │
│  │ 🖊 记事本                                  │ │
│  │ ...                                         │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│              [ 🖥 选择 ]  [ ✕ 取消 ]              │
└────────────────────────────────────────────────────┘
```

**交互流程**：

```
用户操作: 托盘菜单"窗口录制" / 快捷键 Ctrl+Shift+W
    ↓
main.py: _on_start_window()
    ↓
显示 WindowSelector 对话框
    ↓
用户从列表中选择窗口 → 双击或点击"选择"
    ↓
window_selected 信号 → main.py: _on_window_selected(hwnd, title)
    ↓
创建 WindowHighlighter（绿色虚线边框叠加层）
    ↓
recorder.start_window(hwnd)  →  开始录制
    ↓
录制过程中每帧 GetWindowRect 跟踪窗口位置
    ↓
窗口最小化/缩放/关闭 → 暂停录制 → 弹窗提示
```

**系统窗口过滤列表**（类名黑名单）：

```python
_SYSTEM_WINDOW_CLASSES = {
    "Progman",       # 桌面
    "Shell_TrayWnd", # 任务栏
    "WorkerW",       # 桌面辅助
    "IME",           # 输入法
    # ... 通过实际测试补充
}
```

---

### 2.2 窗口边框高亮 (window_highlighter.py) — 新增

**职责**：在录制目标窗口周围绘制绿色虚线边框，提示用户正在录制的窗口。

**技术选型**：使用 `QWidget` + `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool` 创建无边框透明叠加窗口，仅在桌面可见、不录制到视频帧中。

```python
class WindowHighlighter(QWidget):
    """录制窗口边框高亮指示器

    在目标窗口四周绘制绿色虚线边框。
    仅作为屏幕叠加层，不渲染到视频帧。
    """

    - _hwnd: int                  # 目标窗口句柄
    - _timer: QTimer              # 定时器，每 100ms 更新位置

    + __init__(hwnd: int, parent=None)
    + show_highlight()            # 显示高亮边框
    + hide_highlight()            # 隐藏高亮边框
    - _update_position()          # 根据目标窗口位置更新自身位置
    - paintEvent(event)           # 绘制绿色虚线边框
```

**边框绘制**：

```python
def paintEvent(self, event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(0, 200, 0, 200), 3, Qt.DashLine)  # 绿色虚线
    painter.setPen(pen)
    painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
    painter.end()
```

**位置跟踪**：`_update_position()` 每 100ms 通过 `GetWindowRect(self._hwnd)` 获取窗口最新位置，更新 Widget 的 geometry。若窗口不可见（最小化等），自动隐藏高亮边框。

**窗口事件监测**：通过 `SetWinEventHook` 监听目标窗口的 `EVENT_OBJECT_DESTROY` 和 `EVENT_SYSTEM_MINIMIZEEND` 事件，在窗口关闭/最小化时通知 `main.py` 暂停录制。

> **线程安全**：`SetWinEventHook` 回调在独立线程中执行，需通过 `pyqtSignal` 转发到 Qt 主线程。

---

### 2.3 指定窗口录制集成 (recorder_manager.py) — 更新

**v1.2 新增**：`RecordMode.WINDOW` 模式 + 窗口位置跟踪。

```python
class RecordMode(Enum):
    """录制模式枚举"""
    FULLSCREEN = "fullscreen"   # 全屏录制
    REGION = "region"           # 区域录制
    WINDOW = "window"           # 指定窗口录制（v1.2 新增）

class RecorderManager:
    # v1.1 字段保留 ...

    # v1.2 新增字段
    - _window_hwnd: int | None          # 目标窗口句柄
    - _window_title: str                # 目标窗口标题
    - _window_monitor_timer: QTimer     # 窗口位置监控定时器（Qt 主线程）

    # v1.2 新增方法
    + start_window(hwnd: int) -> bool   # 窗口录制入口
    + get_mode() -> RecordMode          # 已有（v1.1）

    # _start() 方法扩展
    - _start(region=None, hwnd=None)    # 新增 hwnd 参数
```

**`start_window(hwnd)` 流程**：

```python
def start_window(self, hwnd: int) -> bool:
    """窗口录制入口

    Args:
        hwnd: 目标窗口句柄

    Returns:
        True 如果成功开始录制

    与 start_fullscreen() / start_region() 流程一致，
    仅 RecordMode 设为 WINDOW 并传入 hwnd。
    """
    # 1. 检查窗口有效性
    if not ctypes.windll.user32.IsWindow(hwnd):
        logger.error(f"无效窗口句柄: {hwnd}")
        return False

    # 2. 获取窗口标题和初始位置
    title = self._get_window_title(hwnd)
    self._window_hwnd = hwnd
    self._window_title = title

    # 3. 调用 _start(hwnd=hwnd)
    return self._start(hwnd=hwnd)
```

**`_start()` 方法扩展**（hwnd 参数）：

```python
def _start(self, region=None, hwnd=None) -> bool:
    # ... v1.1 启动逻辑 ...

    self._mode = RecordMode.FULLSCREEN
    self._window_hwnd = None

    if region:
        self._mode = RecordMode.REGION
    elif hwnd:
        self._mode = RecordMode.WINDOW
        self._window_hwnd = hwnd
        # 获取窗口初始区域
        rect = self._get_window_rect(hwnd)
        region = (rect.left, rect.top, rect.width, rect.height)

    # ... ScreenCapturer 创建、音频初始化、录制线程启动 ...
```

**`_record_loop()` 方法扩展**（窗口位置跟踪）：

```python
def _record_loop(self):
    while self._is_recording.is_set():
        # v1.2 新增: 窗口模式下每帧更新捕获区域
        if self._mode == RecordMode.WINDOW and self._window_hwnd:
            rect = self._get_window_rect(self._window_hwnd)
            if rect is None:
                # 窗口已关闭 → 通过信号通知主线程暂停
                self._on_window_lost.emit("closed")
                break
            if rect.width < 10 or rect.height < 10:
                # 窗口已最小化 → 通过信号通知主线程暂停
                self._on_window_lost.emit("minimized")
                break
            # 更新 ScreenCapturer 的捕获区域
            self._capturer.update_region(
                (rect.left, rect.top, rect.width, rect.height)
            )

        # ... v1.1 录制逻辑不变（捕获帧、JPEG 压缩、写入临时文件） ...
```

**窗口事件信号**：

```python
class _WindowBridge(QObject):
    """窗口事件信号桥（录制线程 → Qt 主线程）"""
    window_lost = pyqtSignal(str)  # "closed" / "minimized" / "resized"
```

**窗口丢失处理流程**（`main.py`）：

```
_on_window_lost(reason: str)
    ↓
1. recorder.pause()          # 暂停录制
2. toolbar.set_paused(True)  # 工具栏显示暂停状态
3. 弹出提示对话框:
   - 窗口已关闭/最小化："录制窗口已[关闭/最小化]，录制已暂停"
   - 按钮: [停止录制并保存] [继续录制（窗口恢复后）]
   - "停止录制并保存" → recorder.stop() → 保存已录制内容
   - "继续录制" → 等待窗口恢复（如果窗口重新可见，自动恢复录制）
```

**ScreenCapturer 新增方法**：

```python
class ScreenCapturer:
    # ... v1.1 方法保留 ...

    # v1.2 新增
    + update_region(region: tuple) -> None
        """动态更新捕获区域（用于窗口录制跟踪窗口位置）

        Args:
            region: (left, top, width, height) 新的捕获区域
        """
```

---

### 2.4 鼠标点击高亮模块 (click_highlighter.py) — 新增

**职责**：在屏幕上绘制鼠标左键点击的扩散圆圈动画，仅作为叠加层可见，不渲染到视频帧。

**技术选型**：使用 `QWidget` 无边框透明窗口 + `QPropertyAnimation` 实现扩散圆圈动画。全局 `pynput` 鼠标监听器捕获左键点击事件。

```python
class ClickHighlighter:
    """鼠标点击高亮管理器

    当配置开启时，监听鼠标左键点击并在点击位置显示扩散圆圈动画。
    仅作为屏幕叠加层，不影响录制的视频帧。

    默认关闭，通过 config.mouse_highlight 开关控制。
    """

    - _enabled: bool                  # 是否启用
    - _listener: pynput.mouse.Listener # 鼠标监听器
    - _animations: list               # 当前正在播放的动画列表
    - _bridge: _ClickBridge           # 鼠标线程 → Qt 主线程信号桥

    + __init__(config: ConfigManager)
    + start()                         # 启动鼠标监听
    + stop()                          # 停止鼠标监听
    + set_enabled(enabled: bool)       # 动态开关
    - _on_click(x, y, button)         # 鼠标点击回调（pynput 线程）
    - _show_click_effect(x, y)        # 在屏幕位置显示扩散圆圈（Qt 主线程）
```

```python
class _ClickBridge(QObject):
    """pynput 鼠标线程 → Qt 主线程信号桥"""
    click_occurred = pyqtSignal(int, int)   # (x, y) 屏幕坐标
```

```python
class ClickCircle(QWidget):
    """单击扩散圆圈动画

    在屏幕 (x, y) 位置显示一个从小到大扩散的圆圈，持续 ~300ms 后消失。
    """

    + __init__(x: int, y: int, parent=None)
    - _start_animation()              # QPropertyAnimation: 半径 0→30px, 透明度 1→0
    - paintEvent(event)               # 绘制半透明红色圆圈
```

**圆圈参数**：

```python
CLICK_CIRCLE_RADIUS_MAX = 30    # 最大半径（像素）
CLICK_CIRCLE_DURATION = 300      # 动画时长（毫秒）
CLICK_CIRCLE_COLOR = (231, 76, 60, 180)  # #e74c3c with alpha
CLICK_CIRCLE_BORDER_WIDTH = 3    # 圆圈边框宽度
```

**启动/停止逻辑**：

```python
# main.py 中
def _update_highlight_state(self):
    """根据配置和录制状态决定是否启动/停止高亮"""
    should_enable = (
        self._config.get("mouse_highlight", False)  # 配置开关
        and self._recorder.get_state() == RecorderState.RECORDING  # 仅录制中
    )
    if should_enable and not self._click_highlighter.is_running():
        self._click_highlighter.start()
    elif not should_enable and self._click_highlighter.is_running():
        self._click_highlighter.stop()
```

**时序**：

```
录制开始 → 检查 config.mouse_highlight → 若开启则 ClickHighlighter.start()
    ↓
鼠标左键点击 → pynput 回调 → _ClickBridge.click_occurred → Qt 主线程
    ↓
_show_click_effect(x, y) → 创建 ClickCircle 在 (x, y) 位置
    ↓
QPropertyAnimation: 半径 0→30px + 透明度 1→0, 持续 300ms
    ↓
动画结束 → ClickCircle 自动销毁
    ↓
录制停止 → ClickHighlighter.stop()
```

> **性能**：每个 ClickCircle 是独立的 QWidget，动画结束后自动 `deleteLater()`。QPropertyAnimation 在 Qt 事件循环中运行，不占用录制线程。预计每次点击增加 < 1ms 开销，对帧率无影响（高亮在叠加层，不渲染到视频帧）。

---

### 2.5 原生画质优化 (config.py + screen_capturer.py) — 更新

**问题**：v1.0/v1.1 中 `QUALITY_SIZES` 的 `"native"` 档位固定为 `None`（即直接使用原始帧尺寸），设置界面显示"原生(2K)"是硬编码的，与实际显示器分辨率不符。

**v1.2 改动**：`"native"` 档位动态读取主显示器分辨率并显示实际值。

**config.py 更新**：

```python
class ConfigManager:
    # QUALITY_SIZES 改动：native 仍为 None（运行时动态计算）
    QUALITY_SIZES = {
        "native": None,         # 运行时动态获取主显示器分辨率
        "high": (1920, 1080),
        "medium": (1280, 720),
        "low": (854, 480),
    }

    # 新增静态方法
    @staticmethod
    def get_native_resolution() -> tuple[int, int]:
        """获取主显示器的原生分辨率

        使用 ctypes 调用 Win32 API GetSystemMetrics 获取:
        SM_CXSCREEN (0) = 屏幕宽度
        SM_CYSCREEN (1) = 屏幕高度

        Returns:
            (width, height) 主显示器分辨率
        """
        import ctypes
        user32 = ctypes.windll.user32
        width = user32.GetSystemMetrics(0)   # SM_CXSCREEN
        height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        return (width, height)
```

**settings_dialog.py 更新**：

画质下拉框刷新逻辑：

```python
def _refresh_quality_combo(self):
    """动态更新原生画质的显示文本"""
    native_w, native_h = ConfigManager.get_native_resolution()
    quality_items = [
        (f"原生({native_w}×{native_h})", "native"),
        ("高(1080p)", "high"),
        ("中(720p)", "medium"),
        ("低(480p)", "low"),
    ]
    self._combo_quality.clear()
    for label, value in quality_items:
        self._combo_quality.addItem(label, value)
```

**在 `__init__` 和 `_load_config` 中调用**：

- 初始化时调用 `_refresh_quality_combo()` 设置下拉选项
- `_load_config()` 时根据配置值选中对应项
- 如果显示器分辨率变化（如热插拔），下次设置窗口打开时重新计算

**recorder_manager.py `_get_target_size()` 不变**：

```python
def _get_target_size(self, capture_size):
    """根据画质配置计算编码尺寸

    native: 使用 capture_size 作为编码尺寸（即原始分辨率）
    其他: 按 QUALITY_SIZES 缩放（保持宽高比）
    """
    quality = self._config.get("quality", "high")
    target_size = ConfigManager.QUALITY_SIZES.get(quality)

    if target_size is None:
        # native: 使用原始捕获尺寸
        return capture_size

    # ... v1.1 缩放逻辑不变 ...
```

> **兼容性**：配置文件中存储 `"quality": "native"` 值不变。`_get_target_size()` 中 `native` 对应 `None` 的逻辑不变——录制时 ScreenCapturer 返回的帧尺寸就是主显示器原生分辨率，`native` 档位不做二次缩放。变化仅在设置界面的**显示文本**从固定"原生(2K)"改为动态"原生(1920×1080)"。

---

### 2.6 开机自启模块 (autostart.py) — 新增

**职责**：管理开机自启的注册表项，实现开机自动启动（静默驻留托盘）。

**技术选型**：通过 `winreg` 模块操作 `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run` 注册表项。

```python
import winreg
import sys
import os

AUTO_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTO_RUN_NAME = "QuickRec"

def is_autostart_enabled() -> bool:
    """检查开机自启是否已开启

    读取 HKEY_CURRENT_USER\Run 中 QuickRec 项的值，
    与当前可执行文件路径比较。
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTO_RUN_KEY, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, AUTO_RUN_NAME)
        winreg.CloseKey(key)
        # 比较路径（忽略大小写，Windows 路径不区分大小写）
        return os.path.normcase(value) == os.path.normcase(_get_executable_path())
    except FileNotFoundError:
        return False
    except Exception:
        return False

def enable_autostart() -> bool:
    """开启开机自启

    写入 HKEY_CURRENT_USER\Run 注册表项。
    无需管理员权限。

    Returns:
        True 如果成功写入
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTO_RUN_KEY, 0, winreg.KEY_SET_VALUE)
        exe_path = _get_executable_path()
        winreg.SetValueEx(key, AUTO_RUN_NAME, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"开启开机自启失败: {e}")
        return False

def disable_autostart() -> bool:
    """关闭开机自启

    删除 HKEY_CURRENT_USER\Run 中的 QuickRec 项。

    Returns:
        True 如果成功删除
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTO_RUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, AUTO_RUN_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return True  # 已经不存在
    except Exception as e:
        logger.error(f"关闭开机自启失败: {e}")
        return False

def _get_executable_path() -> str:
    """获取当前可执行文件路径

    打包后返回 exe 路径，开发环境返回 python 解释器路径。
    开机自启仅在打包后生效。
    """
    if getattr(sys, 'frozen', False):
        return sys.executable
    else:
        # 开发环境：无法自启，返回空以区分
        return sys.executable
```

> **安全提示**：仅写入 `HKEY_CURRENT_USER\Run`，不需要管理员权限。安全软件可能提示注册表修改，属于正常行为。

---

### 2.7 录制倒计时模块 (toolbar.py) — 更新

**职责**：在工具栏中显示 3→2→1 倒计时数字，倒计时结束后自动开始录制。

**设计决策**：倒计时在工具栏内显示，不使用全屏遮罩。倒计时期间用户可按 ESC 或录制快捷键取消。

```python
class RecordingToolbar(QWidget):
    # v1.1 信号保留 ...

    # v1.2 新增信号
    countdown_finished = pyqtSignal()   # 倒计时结束，可以开始录制

    # v1.2 新增状态
    - _countdown_mode: bool              # 是否处于倒计时模式
    - _countdown_value: int              # 当前倒计时数值（3, 2, 1）
    - _countdown_timer: QTimer           # 倒计时定时器（1 秒间隔）

    # v1.2 新增方法
    + start_countdown(seconds: int = 3)  # 开始倒计时
    + cancel_countdown()                 # 取消倒计时（ESC / 快捷键触发）
    - _countdown_tick()                  # 每秒倒计时回调
    - _show_countdown_ui()               # 显示倒计时界面（大号数字）
    - _hide_countdown_ui()               # 隐藏倒计时，恢复录制 UI
```

**倒计时 UI**：

```
录制前倒计时状态：
┌──────────────────────────────────────────────┐
│                 3                            │   ← 大号数字（字号 48px）
│           点击取消 / 按 ESC                   │   ← 小号提示文字
└──────────────────────────────────────────────┘
```

**流程**：

```
用户点击"开始录制" / 按快捷键
    ↓
检查 config.show_countdown 是否开启
    ├── False → 直接开始录制（v1.0/v1.1 行为不变）
    └── True  → toolbar.start_countdown(3)
                    ↓
                显示工具栏，3→2→1 倒计时
                每秒 _countdown_tick() 减 1 并更新显示
                    ↓ 倒计时到 0
                countdown_finished 信号 → main.py
                    ↓
                开始实际录制（_on_start_fullscreen / _on_start_window 等）
```

**取消倒计时**：

- 用户按 ESC 键：`toolbar.keyPressEvent` 检测 ESC → `cancel_countdown()`
- 用户按录制快捷键：pynput 回调 → 信号桥 → `cancel_countdown()`
- 取消后：工具栏隐藏，回到空闲状态

**main.py 集成**：

```python
def _on_start_fullscreen(self):
    """全屏录制入口（v1.2 更新）"""
    if self._recorder.get_state() != RecorderState.IDLE:
        return

    if self._config.get("show_countdown", False):
        # 显示倒计时
        self._show_toolbar()
        self._toolbar.start_countdown(self._config.get("countdown_seconds", 3))
        self._toolbar.countdown_finished.connect(self._do_start_fullscreen)
    else:
        self._do_start_fullscreen()

def _do_start_fullscreen(self):
    """倒计时结束后的实际录制启动"""
    if not self._recorder.start_fullscreen():
        logger.error("全屏录制启动失败")
        self._hide_toolbar()
```

---

### 2.8 配置管理模块 (config.py) — 更新

**v1.2 新增配置项**：

```python
class ConfigManager:
    defaults = {
        # v1.0 保留
        "save_path": "~/Videos/QuickRec",
        "quality": "high",
        "fps": 30,
        "shortcut_start": "Ctrl+Shift+R",
        "shortcut_stop": "Ctrl+Shift+S",
        "shortcut_pause": "Ctrl+Shift+P",
        "shortcut_area": "Ctrl+Shift+A",

        # v1.1 保留
        "audio_source": "none",

        # v1.2 新增
        "shortcut_window": "Ctrl+Shift+W",     # 窗口录制快捷键
        "show_countdown": False,                # 是否显示录制倒计时
        "countdown_seconds": 3,                 # 倒计时秒数（默认 3）
        "mouse_highlight": False,               # 鼠标点击高亮开关（默认关闭）
        "auto_start": False,                    # 开机自启开关（默认关闭）
    }
```

**新增常量**：

```python
# v1.2 新增
QUALITY_SIZES = {
    "native": None,         # 运行时动态获取主显示器分辨率
    "high": (1920, 1080),
    "medium": (1280, 720),
    "low": (854, 480),
}

@staticmethod
def get_native_resolution() -> tuple[int, int]:
    """获取主显示器分辨率（用于设置界面显示）"""
```

---

### 2.9 设置对话框模块 (settings_dialog.py) — 更新

**v1.2 新增控件**：

```python
class SettingsDialog(QDialog):
    config_saved = pyqtSignal()

    # v1.0/v1.1 控件保留 ...

    # v1.2 新增控件
    - _cb_auto_start: QCheckBox              # 开机自启复选框
    - _cb_countdown: QCheckBox               # 录制倒计时复选框
    - _cb_mouse_highlight: QCheckBox          # 鼠标点击高亮复选框
    - _shortcut_window: _ShortcutRecorder     # 窗口录制快捷键

    # v1.2 修改控件
    - _combo_quality: QComboBox              # "原生(1920×1080)" 动态显示
```

**设置界面布局更新**：

```
┌─ QuickRec 设置 ───────────────────────────────┐
│                                                │
│  保存路径    [C:\Users\xxx\Videos\QuickRec]    │
│                                                │
│  画质        ● 原生(1920×1080)  ○ 高(1080p)   │    ← 动态显示分辨率
│              ○ 中(720p)  ○ 低(480p)            │
│                                                │
│  帧率        ● 30fps   ○ 60fps                 │
│                                                │
│  音频源      ○ 无  ● 系统声音                   │
│              ○ 麦克风  ○ 两者都有               │
│                                                │
│  ☐ 开机自启  ☑ 录制倒计时(3秒)                 │    ← v1.2 新增
│  ☐ 鼠标点击高亮                               │    ← v1.2 新增
│                                                │
│  快捷键      开始: [Ctrl+Shift+R] 点击修改...   │
│              停止: [Ctrl+Shift+S] 点击修改...   │
│              暂停: [Ctrl+Shift+P] 点击修改...   │
│              区域: [Ctrl+Shift+A] 点击修改...   │
│              窗口: [Ctrl+Shift+W] 点击修改...   │    ← v1.2 新增
│                                                │
│              [ 保存 ]  [ 取消 ]                  │
└────────────────────────────────────────────────┘
```

**新增交互**：

- **开机自启复选框**：勾选时调用 `autostart.enable()`，取消时调用 `autostart.disable()`
- **录制倒计时复选框**：勾选后启用倒计时输入框，可修改秒数（3/5/10）
- **鼠标高亮复选框**：纯配置开关，仅保存到 config，录制时读取
- **窗口录制快捷键**：与区域录制快捷键相同的 `_ShortcutRecorder` 控件

**`_load_config()` 扩展**：

```python
def _load_config(self):
    # ... v1.1 逻辑保留 ...

    # v1.2 新增
    self._cb_auto_start.setChecked(self._config.get("auto_start", False))
    self._cb_countdown.setChecked(self._config.get("show_countdown", False))
    self._cb_mouse_highlight.setChecked(self._config.get("mouse_highlight", False))
    window_shortcut = self._config.get("shortcut_window", "Ctrl+Shift+W")
    self._shortcut_window.set_shortcut(window_shortcut)
```

**`_save_config()` 扩展**：

```python
def _save_config(self):
    # ... v1.1 逻辑保留 ...

    # v1.2 新增
    self._config.set("show_countdown", self._cb_countdown.isChecked())
    self._config.set("mouse_highlight", self._cb_mouse_highlight.isChecked())

    # 开机自启：同时操作注册表
    auto_start = self._cb_auto_start.isChecked()
    self._config.set("auto_start", auto_start)
    if auto_start:
        autostart.enable_autostart()
    else:
        autostart.disable_autostart()

    # 窗口录制快捷键
    self._config.set("shortcut_window", self._shortcut_window.get_shortcut())

    self._config.save()
    self.config_saved.emit()
```

---

### 2.10 托盘菜单模块 (tray_icon.py) — 更新

**v1.2 新增**：空闲菜单中添加"窗口录制"选项。

**空闲菜单更新**：

```
空闲菜单:
  ▶ 全屏录制
  ▢ 区域录制
  🖥 窗口录制          ← v1.2 新增
  ⚙ 设置
  📁 打开保存文件夹
  ───
  ✕ 退出
```

**`_SignalBridge` 扩展**：

```python
class _SignalBridge(QObject):
    # v1.1 信号保留
    start_fullscreen_requested = pyqtSignal()
    start_region_requested = pyqtSignal()
    pause_resume_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    # v1.2 新增
    start_window_requested = pyqtSignal()    # 窗口录制
```

**回调字典扩展**：

```python
callbacks = {
    "start_fullscreen": ...,
    "start_region": ...,
    "start_window": self._on_start_window,      # v1.2 新增
    "pause_resume": ...,
    "stop": ...,
    "settings": ...,
    "exit": ...,
}
```

---

### 2.11 主程序入口 (main.py) — 更新

**新增信号桥**：

```python
class _WindowBridge(QObject):
    """窗口选择器信号桥"""
    window_selected = pyqtSignal(int, str)    # (hwnd, title)
    cancelled = pyqtSignal()

class _WindowLostBridge(QObject):
    """窗口丢失信号桥（录制线程 → Qt 主线程）"""
    window_lost = pyqtSignal(str)              # "closed" / "minimized"
```

**`_HotkeyBridge` 扩展**：

```python
class _HotkeyBridge(QObject):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    area_requested = pyqtSignal()
    window_requested = pyqtSignal()        # v1.2 新增
```

**新增方法**：

```python
class QuickRecApp:
    # v1.2 新增字段
    - _window_highlighter: WindowHighlighter | None   # 窗口边框高亮
    - _click_highlighter: ClickHighlighter            # 鼠标点击高亮
    - _window_selector: WindowSelector | None         # 窗口选择器（临时引用防 GC）

    def _on_start_window(self):
        """窗口录制入口：显示窗口选择器"""
        if self._recorder.get_state() != RecorderState.IDLE:
            return
        self._window_selector = WindowSelector()
        self._window_selector.window_selected.connect(
            lambda hwnd, title: self._window_bridge.window_selected.emit(hwnd, title)
        )
        self._window_selector.cancelled.connect(self._window_bridge.cancelled.emit)
        self._window_selector.exec_()

    def _on_window_selected(self, hwnd: int, title: str):
        """窗口选择完成：开始录制"""
        # 创建边框高亮
        self._window_highlighter = WindowHighlighter(hwnd)
        self._window_highlighter.show_highlight()

        # 启动录制
        if self._config.get("show_countdown", False):
            self._show_toolbar()
            self._toolbar.start_countdown(
                self._config.get("countdown_seconds", 3)
            )
            self._toolbar.countdown_finished.connect(
                lambda: self._do_start_window(hwnd)
            )
        else:
            self._do_start_window(hwnd)

    def _do_start_window(self, hwnd: int):
        """窗口录制实际启动"""
        if not self._recorder.start_window(hwnd):
            logger.error("窗口录制启动失败")
            self._hide_toolbar()
            return
        self._show_toolbar()
        self._tray.set_recording_state(True)
        # 启动鼠标高亮（如果开启）
        self._update_highlight_state()

    def _on_window_lost(self, reason: str):
        """录制窗口丢失：暂停录制并提示"""
        self._recorder.pause()
        self._toolbar.set_paused(True)

        reason_text = {
            "closed": "录制窗口已关闭",
            "minimized": "录制窗口已最小化",
        }.get(reason, "录制窗口不可用")

        # 弹出提示对话框
        msg = QMessageBox()
        msg.setWindowTitle("QuickRec")
        msg.setText(f"{reason_text}，录制已暂停")
        msg.setInformativeText("是否停止录制并保存？")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.button(QMessageBox.Yes).setText("停止录制并保存")
        msg.button(QMessageBox.No).setText("继续等待")

        if msg.exec_() == QMessageBox.Yes:
            self._on_stop_recording()
        # 用户选择继续等待：窗口恢复时自动恢复录制（通过 WindowHighlighter 监测）

    def _update_highlight_state(self):
        """根据配置和录制状态更新鼠标高亮"""
        should_enable = (
            self._config.get("mouse_highlight", False)
            and self._recorder.get_state() == RecorderState.RECORDING
        )
        if should_enable and not self._click_highlighter.is_running():
            self._click_highlighter.start()
        elif not should_enable and self._click_highlighter.is_running():
            self._click_highlighter.stop()
```

**快捷键注册扩展**：

```python
def _setup_hotkeys(self):
    # v1.0/v1.1 绑定保留 ...
    # v1.2 新增: 窗口录制快捷键
    shortcut_window = self._config.get("shortcut_window", "Ctrl+Shift+W")
    self._hotkey.register(shortcut_window, self._hotkey_bridge.window_requested.emit)
```

**录制停止时清理**：

```python
def _handle_saved(self, output_path: str):
    # ... v1.1 逻辑保留 ...

    # v1.2 新增: 清理窗口边框高亮
    if self._window_highlighter:
        self._window_highlighter.hide_highlight()
        self._window_highlighter = None

    # v1.2 新增: 停止鼠标高亮
    self._click_highlighter.stop()
```

---

## 3. 新增依赖

v1.2 无新增外部依赖。所有新功能使用 Python 标准库或现有依赖实现：

| 功能 | 实现方式 | 新增依赖 |
|-----|---------|---------|
| 窗口枚举/位置跟踪 | `ctypes` 调用 Win32 API | 无 |
| 开机自启 | `winreg` 操作注册表 | 无 |
| 鼠标点击监听 | `pynput`（已有） | 无 |
| 点击动画 | `QPropertyAnimation`（PyQt5） | 无 |
| 倒计时 | `QTimer`（已有） | 无 |

---

## 4. 项目架构更新

### 4.1 目录结构变化

```
QuickRec_dev/src/
├── main.py                      # 更新: _WindowBridge, _WindowLostBridge, 窗口录制入口, 倒计时, 高亮
├── config.py                    # 更新: 新增 shortcut_window, show_countdown, countdown_seconds,
│                                #        mouse_highlight, auto_start, get_native_resolution()
├── recorder/
│   ├── recorder_manager.py      # 更新: RecordMode.WINDOW, start_window(), 窗口位置跟踪
│   ├── screen_capturer.py      # 更新: 新增 update_region() 动态更新捕获区域
│   ├── video_encoder.py         # 不变
│   └── audio_capturer.py        # 不变
├── ui/
│   ├── tray_icon.py             # 更新: 空闲菜单添加"窗口录制", start_window_requested 信号
│   ├── toolbar.py               # 更新: 倒计时模式, countdown_finished 信号
│   ├── settings_dialog.py       # 更新: 开机自启/倒计时/鼠标高亮复选框, 窗口快捷键, 动态画质显示
│   ├── area_selector.py          # 不变
│   ├── window_selector.py       # 新增: 窗口选择对话框
│   ├── window_highlighter.py    # 新增: 窗口边框绿色虚线高亮
│   └── click_highlighter.py     # 新增: 鼠标点击扩散圆圈动画
├── hotkey/
│   └── hotkey_manager.py        # 不变（仅注册新快捷键）
├── utils/
│   ├── file_namer.py            # 不变
│   ├── disk_checker.py          # 不变
│   └── autostart.py             # 新增: 开机自启注册表管理
└── 三处信号桥增加为五处：Tray/Hotkey/Saved/Area/Window → Qt 主线程
```

### 4.2 模块依赖关系更新

```
main.py（五处信号桥: Tray/Hotkey/Saved/Area/Window → Qt 主线程）
├── config.py（新增 shortcut_window, show_countdown, countdown_seconds,
│              mouse_highlight, auto_start, get_native_resolution）
├── ui/tray_icon.py（空闲菜单添加"窗口录制" + start_window_requested 信号）
├── ui/toolbar.py（倒计时模式 + countdown_finished 信号）
├── ui/settings_dialog.py（开机自启/倒计时/高亮复选框 + 窗口快捷键 + 动态画质）
├── ui/area_selector.py（不变）
├── ui/window_selector.py（新增: Win32 窗口枚举 + 列表选择对话框）
├── ui/window_highlighter.py（新增: 绿色虚线边框叠加层 + 位置跟踪）
├── ui/click_highlighter.py（新增: pynput 鼠标监听 + 扩散圆圈动画）
├── hotkey/hotkey_manager.py（不变，仅注册新快捷键 Ctrl+Shift+W）
├── utils/autostart.py（新增: winreg 注册表操作）
└── recorder/recorder_manager.py（RecordMode.WINDOW + 窗口位置跟踪 + window_lost 信号）
    ├── recorder/screen_capturer.py（新增: update_region() 动态更新）
    ├── recorder/video_encoder.py（不变）
    ├── recorder/audio_capturer.py（不变）
    ├── utils/file_namer.py（不变）
    └── utils/disk_checker.py（不变）
```

---

## 5. 模块测试计划

| 模块 | 测试方式 | 关键用例 |
|-----|---------|---------|
| WindowSelector | 手动/UI | 窗口列表显示、双击选择、过滤系统窗口、无可见窗口 |
| WindowHighlighter | 手动测试 | 边框跟随窗口移动、最小化时隐藏、窗口关闭时隐藏 |
| Window 录制 | 集成测试 | 窗口选择→录制→暂停→恢复→停止、窗口关闭暂停提示、窗口移动跟踪 |
| ClickHighlighter | 手动测试 | 左键点击显示圆圈、动画扩散消失、配置关闭时不显示、录制停止后不响应 |
| 倒计时 | 手动测试 | 3→2→1 工具栏显示、ESC 取消、快捷键取消、倒计时结束后开始录制 |
| 开机自启 | 单元测试 + 手动 | 注册表写入/读取/删除、勾选后重启验证、取消后验证注册表清理 |
| 原生画质 | 单元测试 | 动态获取分辨率、设置界面显示正确、1080p 显示器显示"原生(1920×1080)"、配置保存/加载 |
| ConfigManager | 单元测试 | v1.2 新配置默认值、旧 config.json 加载兼容 |
| SettingsDialog | 手动测试 | 开机自启勾选同步注册表、倒计时开关/秒数、鼠标高亮开关、窗口快捷键录制 |
| 窗口录制 + 音频 | 集成测试 | 窗口录制 + 系统声音、窗口录制 + 麦克风、窗口录制 + 两者 |

---

## 6. 开发里程碑

| 阶段 | 内容 | 依赖 |
|-----|------|------|
| 1 | config.py 更新 + autostart.py 新增 | 无 |
| 2 | settings_dialog.py 更新 | config, autostart |
| 3 | click_highlighter.py 新增 | config (mouse_highlight) |
| 4 | toolbar.py 倒计时更新 | config (show_countdown) |
| 5 | window_selector.py + window_highlighter.py 新增 | Win32 API |
| 6 | screen_capturer.py update_region() + recorder_manager.py WINDOW 模式 | 阶段 5 |
| 7 | main.py 集成（所有信号桥 + 流程串联） | 所有模块 |
| 8 | tray_icon.py 菜单更新 | main.py 回调 |
| 9 | 集成测试 + 打包 | 所有模块 |

**关键路径**：config → settings → 窗口录制全链路 → 集成

**可并行开发**：
- 阶段 3（click_highlighter）和 阶段 4（倒计时）可并行
- 阶段 1（config + autostart）独立先行

---

## 7. 风险与应对

| 风险 | 影响 | 应对 |
|-----|------|------|
| Win32 窗口枚举兼容性 | 不同 Windows 版本窗口列表获取方式不同 | 使用 EnumWindows 过渡 API，过滤不可见/系统窗口类黑名单 |
| 窗口录制移位/缩放 | 录制期间窗口变化可能影响帧捕获 | 每帧 GetWindowRect 更新，最小化/关闭时暂停并提示 |
| 鼠标点击高亮性能 | 每帧绘制动画可能增加 CPU 开销 | 高亮仅在屏幕叠加层，不渲染到视频帧；QPropertyAnimation 在 Qt 事件循环，预计 < 1ms/次 |
| pynput 鼠标监听线程冲突 | 鼠标回调与录制线程/Qt 线程冲突 | 使用 _ClickBridge 信号桥转发到 Qt 主线程，与键盘监听一致 |
| 开机自启注册表操作 | 安全软件可能警告注册表修改 | 仅写入 HKEY_CURRENT_USER\Run，无需管理员权限 |
| 倒计时与录制线程时序 | 倒计时结束与录制开始的原子性 | 倒计时在 Qt 主线程展示，结束后通过 countdown_finished 信号触发录制 |
| Qt.Tool 叠加层穿透 | WindowHighlighter/ClickCircle 可能受 Win11 点击穿透影响 | 仅用于显示（不接收鼠标输入），设置 Qt.WindowTransparentForInput 属性 |
| 区域模式下原生画质缩放 | 区域录制时"原生"按选区尺寸编码 | 保持 v1.1 行为：区域模式"原生"按全屏分辨率编码（见 PRD 需求确认） |