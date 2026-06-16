# 任务：录制控制器更新 (recorder_manager.py) — v1.2

**模块**：`src/recorder/recorder_manager.py`（更新）
**说明**：新增 RecordMode.WINDOW 模式、窗口位置跟踪、窗口丢失暂停处理。

## 前置依赖
- [x] screen_capturer.py（update_region 方法）
- [x] config.py（新增配置项）

## 子任务

### 1. RecordMode 枚举扩展
- [x] 新增 `RecordMode.WINDOW = "window"` 枚举值
- [x] 新增字段 `_window_hwnd: int | None = None`（目标窗口句柄）
- [x] 新增字段 `_window_title: str = ""`（目标窗口标题）

### 2. start_window 方法
- [x] `start_window(self, hwnd: int) -> bool` 方法
  - 验证窗口有效性：`ctypes.windll.user32.IsWindow(hwnd)` 返回 True
  - 获取窗口标题：`GetWindowTextW(hwnd)`
  - 设置 `_mode = RecordMode.WINDOW`，`_window_hwnd = hwnd`
  - 获取初始窗口区域 `GetWindowRect(hwnd)` 作为 region 参数
  - 调用 `_start(region=region, hwnd=hwnd)`
  - 窗口无效时返回 False 并 log.error

### 3. _start 方法扩展
- [x] 新增 `hwnd=None` 参数
- [x] 当 `hwnd` 非空时：
  - 设置 `_mode = RecordMode.WINDOW`
  - 设置 `_window_hwnd = hwnd`
  - 获取初始窗口区域 `self._get_window_rect(hwnd)`
  - 传入 `ScreenCapturer(region=初始区域)`

### 4. _record_loop 窗口位置跟踪
- [x] 在录制循环中，当 `_mode == RecordMode.WINDOW` 时：
  - 每帧调用 `self._get_window_rect(self._window_hwnd)` 获取最新位置
  - 若 `GetWindowRect` 返回 None（窗口已关闭）→ 发射 `_window_lost_bridge.window_lost.emit("closed")` → break
  - 若窗口宽度 < 10 或高度 < 10（最小化）→ 发射 `window_lost.emit("minimized")` → break
  - 否则调用 `self._capturer.update_region((left, top, width, height))` 更新捕获区域

### 5. _WindowLostBridge 信号桥
- [x] 新增 `_WindowLostBridge(QObject)` 类
  - `window_lost = pyqtSignal(str)` — "closed" / "minimized"

### 6. 辅助方法
- [x] `_get_window_rect(hwnd: int) -> QRect | None` 静态方法
  - 使用 `ctypes.windll.user32.GetWindowRect(hwnd, byref(rect))` 获取窗口位置
  - 返回 `QRect(left, top, width, height)`
  - 窗口无效时返回 None
- [x] `_get_window_title(hwnd: int) -> str` 静态方法
  - 使用 `GetWindowTextW(hwnd)` 获取窗口标题
  - 返回空字符串作为 fallback

## 验收标准
- [x] `start_window(hwnd)` 正确设置 WINDOW 模式
- [x] 录制过程中窗口移动时捕获区域跟随更新
- [x] 窗口最小化时发射 `window_lost("minimized")` 信号
- [x] 窗口关闭时发射 `window_lost("closed")` 信号
- [x] 全屏录制和区域录制不受影响（回归测试）
- [x] 窗口录制 + 音频正常工作