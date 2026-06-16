# 任务：鼠标点击高亮模块 (click_highlighter.py) — v1.2

**模块**：`src/ui/click_highlighter.py`（新增）
**说明**：录制时左键点击在屏幕叠加层显示扩散圆圈动画，默认关闭，仅在屏幕可见不渲染到视频帧。

## 前置依赖
- [x] config.py（mouse_highlight 配置项）

## 子任务

### 1. 信号桥
- [x] `_ClickBridge(QObject)` 类
  - `click_occurred = pyqtSignal(int, int)` — 鼠标点击 (x, y) 从 pynput 线程转发到 Qt 主线程

### 2. ClickCircle 动画
- [x] `ClickCircle(QWidget)` 类
  - 无边框透明窗口：`Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`
  - 设置 `Qt.WA_TransparentForMouseInput` 使其不拦截鼠标事件
  - 圆圈参数：半径 0→30px，持续时间 300ms，颜色 `rgba(231, 76, 60, 180)` (#e74c3c)
  - 使用 `QPropertyAnimation` 控制半径和透明度动画
  - 动画结束后 `deleteLater()` 自动销毁
  - `paintEvent` 绘制半透明红色圆环（边框宽度 3px）

### 3. ClickHighlighter 管理器
- [x] `ClickHighlighter` 类
  - `_enabled: bool` — 是否启用（根据配置）
  - `_listener: pynput.mouse.Listener | None` — 鼠标监听器
  - `_bridge: _ClickBridge` — 信号桥
  - `start()` — 启动 pynput 鼠标监听（仅监听左键点击）
  - `stop()` — 停止监听
  - `is_running() -> bool` — 是否正在监听
  - `set_enabled(enabled: bool)` — 动态开关
  - `_on_click(x, y, button)` — pynput 回调，过滤仅 Button.left
  - `_show_click_effect(x, y)` — 在 Qt 主线程创建 ClickCircle

### 4. 性能考量
- [x] 每个 ClickCircle 独立 QWidget，动画结束后 deleteLater()
- [x] pynput.mouse.Listener 独立线程运行
- [x] 点击回调通过 _ClickBridge 信号桥转发到 Qt 主线程
- [x] 不在录制中时 start() 不执行（由 main.py 控制）

## 验收标准
- [x] 左键点击显示扩散圆圈动画，约 300ms 后消失
- [x] 右键点击不显示动画
- [x] `mouse_highlight=False` 时 ClickHighlighter 不启动监听
- [x] 录制停止后动画不再出现
- [x] 连续快速点击时多个 ClickCircle 同时存在互不干扰
- [x] ClickCircle 不拦截鼠标事件（设置 WA_TransparentForMouseInput）