# 任务：主程序入口更新 (main.py) — v1.2

**模块**：`src/main.py`（更新）
**说明**：新增窗口录制流程、倒计时流程、鼠标高亮控制、快捷键注册扩展。

## 前置依赖
- [x] config.py（新增配置项）
- [x] click_highlighter.py（鼠标点击高亮）
- [x] window_selector.py（窗口选择器）
- [x] window_highlighter.py（窗口边框高亮）
- [x] toolbar.py（倒计时模式）
- [x] recorder_manager.py（WINDOW 模式 + window_lost 信号）
- [x] autostart.py（开机自启检查）
- [x] tray_icon.py（窗口录制菜单项）

## 子任务

### 1. 新增信号桥
- [x] `_WindowBridge(QObject)` 类
  - `window_selected = pyqtSignal(int, str)` — (hwnd, title)
  - `cancelled = pyqtSignal()`
- [x] `_WindowLostBridge(QObject)` 类
  - `window_lost = pyqtSignal(str)` — "closed" / "minimized"
- [x] `_HotkeyBridge` 新增 `window_requested = pyqtSignal()` 信号

### 2. 新增字段
- [x] `_window_highlighter: WindowHighlighter | None = None`（窗口边框高亮）
- [x] `_click_highlighter: ClickHighlighter`（鼠标点击高亮）
- [x] `_window_selector: WindowSelector | None = None`（窗口选择器，防 GC）
- [x] `_window_bridge: _WindowBridge`（窗口选择信号桥）
- [x] `_window_lost_bridge: _WindowLostBridge`（窗口丢失信号桥）

### 3. 窗口录制流程
- [x] `_on_start_window()` 方法
  - 检查 `recorder.get_state() == IDLE`
  - 创建 `WindowSelector` 实例（保存为 `_window_selector` 防 GC）
  - 连接 `window_selected` → `_window_bridge.window_selected`
  - 连接 `cancelled` → `_window_bridge.cancelled`
  - `exec_()` 显示对话框
- [x] `_on_window_selected(hwnd, title)` 方法
  - 创建 `WindowHighlighter(hwnd)` → `show_highlight()`
  - 检查 `show_countdown` 配置：
    - True → 显示工具栏 + 开始倒计时 → `countdown_finished` 连接 `_do_start_window(hwnd)`
    - False → 直接调用 `_do_start_window(hwnd)`
- [x] `_do_start_window(hwnd)` 方法
  - 调用 `recorder.start_window(hwnd)`
  - 失败时 log.error + 隐藏工具栏
  - 成功时显示工具栏 + 设置托盘录制状态
  - 调用 `_update_highlight_state()`（鼠标高亮）
- [x] `_on_window_lost(reason)` 方法
  - 调用 `recorder.pause()`
  - 设置 `toolbar.set_paused(True)`
  - 弹出 QMessageBox 提示："录制窗口已[关闭/最小化]，录制已暂停"
  - 提供两个选项："停止录制并保存" / "继续等待"
  - "停止录制并保存" → `recorder.stop()`

### 4. 倒计时集成
- [x] `_on_start_fullscreen()` 方法更新
  - 检查 `show_countdown` 配置
  - True → `toolbar.start_countdown(seconds)` → `countdown_finished` 连接 `_do_start_fullscreen`
  - False → 直接 `_do_start_fullscreen()`
- [x] `_do_start_fullscreen()` 方法（原 `_on_start_fullscreen` 重命名）
  - 实际启动全屏录制
- [x] 区域录制同样处理倒计时流程
- [x] ESC 键/快捷键取消倒计时
  - 快捷键触发时检查 `toolbar._countdown_mode`
  - 若在倒计时中 → `toolbar.cancel_countdown()`

### 5. 鼠标高亮控制
- [x] `_update_highlight_state()` 方法
  - 判断 `config.mouse_highlight and recorder.state == RECORDING`
  - True → `click_highlighter.start()`
  - False → `click_highlighter.stop()`
- [x] 录制开始时调用 `_update_highlight_state()`
- [x] 录制结束时（`_handle_saved`）调用 `_click_highlighter.stop()`

### 6. 窗口高亮生命周期
- [x] 录制开始时创建 `WindowHighlighter(hwnd)` → `show_highlight()`
- [x] 录制结束时（`_handle_saved`）调用 `hide_highlight()` + 置 None
- [x] 录制取消时同理清理

### 7. 快捷键注册扩展
- [x] `_setup_hotkeys()` 新增：
  - `shortcut_window = config.get("shortcut_window", "Ctrl+Shift+W")`
  - `self._hotkey.register(shortcut_window, self._hotkey_bridge.window_requested.emit)`

### 8. 托盘回调扩展
- [x] `_callbacks` 字典新增 `"start_window": self._on_start_window`
- [x] `_hotkey_bridge.window_requested.connect(self._on_start_window)`

### 9. _handle_saved 清理
- [x] 清理 `_window_highlighter`（hide + None）
- [x] 停止 `_click_highlighter`

## 验收标准
- [x] Ctrl+Shift+W 触发窗口选择对话框
- [x] 托盘菜单"窗口录制"触发窗口选择
- [x] 窗口选择后正确开始录制 + 边框高亮
- [x] 窗口关闭/最小化时暂停并弹窗提示
- [x] 倒计时在所有录制模式（全屏/区域/窗口）下正确工作
- [x] ESC 取消倒计时正确工作
- [x] 鼠标高亮在录制开启时启动、停止时关闭
- [x] 窗口录制结束后清理边框高亮