# 任务：录制工具栏倒计时模式 (toolbar.py) — v1.2

**模块**：`src/ui/toolbar.py`（更新）
**说明**：在工具栏内显示 3→2→1 倒计时，倒计时结束后自动开始录制。支持 ESC 或快捷键取消倒计时。

## 前置依赖
- [x] config.py（show_countdown / countdown_seconds 配置项）

## 子任务

### 1. 新增信号和状态
- [x] 新增信号 `countdown_finished = pyqtSignal()` — 倒计时结束
- [x] 新增字段 `_countdown_mode: bool = False`
- [x] 新增字段 `_countdown_value: int = 0`
- [x] 新增字段 `_countdown_timer: QTimer` — 1 秒间隔定时器

### 2. 倒计时 UI
- [x] `start_countdown(seconds: int = 3)` 方法
  - 设置 `_countdown_mode = True`
  - 设置 `_countdown_value = seconds`
  - 创建 `_countdown_timer`（1 秒间隔）
  - 调用 `_show_countdown_ui()` 显示初始数字
  - 显示工具栏
- [x] `_show_countdown_ui()` 方法
  - 隐藏录制按钮（暂停/停止/取消）
  - 在计时器位置显示大号数字（字号 48px，白色粗体）
  - 下方显示 "点击取消 / 按 ESC" 提示文字
- [x] `_hide_countdown_ui()` 方法
  - 恢复录制按钮（暂停/停止/取消）
  - 恢复正常计时器显示
- [x] `_countdown_tick()` 方法
  - `_countdown_value -= 1`
  - 更新数字显示
  - 倒计时到 0 时：`_countdown_mode = False`，停止定时器，发射 `countdown_finished` 信号

### 3. 取消倒计时
- [x] `cancel_countdown()` 方法
  - 停止 `_countdown_timer`
  - 设置 `_countdown_mode = False`
  - `_hide_countdown_ui()`
  - 隐藏工具栏
- [x] `keyPressEvent` 中检测 ESC 键
  - 若 `_countdown_mode` 为 True → 调用 `cancel_countdown()`

### 4. 与录制流程集成
- [x] `show_countdown()` 仅启动倒计时，不启动录制
- [x] `countdown_finished` 信号由 main.py 连接到实际录制启动
- [x] 非录制配置 `show_countdown=False` 时直接开始录制（不经过倒计时）

## 验收标准
- [x] 开启倒计时配置后，开始录制显示 3→2→1
- [x] 每秒数字更新
- [x] 倒计时结束后发射 `countdown_finished` 信号
- [x] ESC 键取消倒计时并隐藏工具栏
- [x] 关闭倒计时配置后直接开始录制
- [x] 倒计时期间工具栏显示大号数字和取消提示