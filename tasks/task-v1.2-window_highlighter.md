# 任务：窗口边框高亮模块 (window_highlighter.py) — v1.2

**模块**：`src/ui/window_highlighter.py`（新增）
**说明**：在录制目标窗口四周绘制绿色虚线边框，仅作为屏幕叠加层提示录制对象。

## 前置依赖
- [ ] 无（独立 UI 模块，仅依赖 PyQt5 和 ctypes）

## 子任务

### 1. WindowHighlighter 类
- [ ] `WindowHighlighter(QWidget)` 类
  - 构造参数：`hwnd: int`（目标窗口句柄）
  - 窗口标志：`Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`
  - 设置 `Qt.WA_TransparentForMouseInput` 使其不拦截鼠标事件
  - 设置 `Qt.WA_TranslucentBackground` 使背景透明
  - 属性 `self.setAttribute(Qt.WA_TransparentForMouseInput)` 确保点击穿透

### 2. 位置跟踪
- [ ] `_timer: QTimer` — 每 100ms 更新位置
- [ ] `_update_position()` 方法
  - 调用 `ctypes.windll.user32.GetWindowRect(hwnd)` 获取窗口最新位置
  - 更新 Widget 的 geometry 匹配窗口位置（外扩边框宽度）
  - 窗口不可见（IsWindowVisible 为 False）时自动隐藏高亮
  - 窗口句柄无效时（IsWindow 为 False）自动隐藏并停止定时器

### 3. 边框绘制
- [ ] `paintEvent(event)` 方法
  - 绘制绿色虚线边框：`QPen(QColor(0, 200, 0, 200), 3, Qt.DashLine)`
  - 边框宽度 3px，圆角 0（矩形）
  - 内部完全透明（不遮挡窗口内容）
- [ ] `show_highlight()` 方法 — 启动定时器并显示
- [ ] `hide_highlight()` 方法 — 停止定时器并隐藏

### 4. 资源清理
- [ ] `hide_highlight()` 停止 `_timer`
- [ ] Widget 关闭时清理定时器

## 验收标准
- [ ] 绿色虚线边框正确包围目标窗口（含边框）
- [ ] 窗口移动时边框跟随（100ms 内更新）
- [ ] 窗口最小化时边框自动隐藏
- [ ] 窗口关闭时边框自动隐藏并停止定时器
- [ ] 边框不拦截鼠标事件（点击穿透到下层窗口）
- [ ] 边框不遮挡窗口内容（内部透明）