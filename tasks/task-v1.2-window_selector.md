# 任务：窗口选择器模块 (window_selector.py) — v1.2

**模块**：`src/ui/window_selector.py`（新增）
**说明**：枚举当前可见窗口列表，让用户选择一个窗口作为录制目标。

## 前置依赖
- [ ] 无（独立 UI 模块，仅依赖 PyQt5 和 ctypes）

## 子任务

### 1. Win32 窗口枚举
- [ ] `_enum_visible_windows() -> list[tuple[int, str, QRect]]` 静态方法
  - 使用 `ctypes.windll.user32.EnumWindows` 枚举窗口
  - 使用 `GetWindowTextW` 获取窗口标题
  - 使用 `GetWindowRect` 获取窗口位置和尺寸
  - 使用 `IsWindowVisible` 过滤不可见窗口
  - 使用 `GetClassName` 过滤系统窗口类黑名单
  - 过滤空标题窗口
  - 过滤 QuickRec 自身窗口（工具栏、设置对话框等）
  - 返回 `[(hwnd, title, rect), ...]`

### 2. 系统窗口类黑名单
- [ ] 定义 `_SYSTEM_WINDOW_CLASSES` 集合
  - `Progman`（桌面）
  - `Shell_TrayWnd`（任务栏）
  - `WorkerW`（桌面辅助窗口）
  - `IME`（输入法）
  - 其他通过测试补充的系统窗口类名

### 3. 对话框 UI
- [ ] `WindowSelector(QDialog)` 类
  - 信号：`window_selected = pyqtSignal(int, str)` — (hwnd, title)
  - 信号：`cancelled = pyqtSignal()`
  - 窗口列表使用 `QListWidget` 显示
  - 每个列表项显示窗口图标（通过 `WM_GETICON` 获取）+ 窗口标题
  - 底部两个按钮："选择" 和 "取消"
- [ ] `refresh_windows()` 方法 — 重新枚举并刷新列表
- [ ] `_on_item_double_clicked(item)` — 双击选择窗口
- [ ] `_on_select_clicked()` — 点击"选择"按钮发射 `window_selected`
- [ ] `_on_cancel_clicked()` — 点击"取消"按钮发射 `cancelled`

### 4. 对话框样式
- [ ] 窗口标题 "选择录制窗口"
- [ ] 暗色主题风格，与 QuickRec 整体风格一致
- [ ] 对话框大小约 400×500
- [ ] 列表项足够一行显示窗口标题

## 验收标准
- [ ] 对话框显示当前可见窗口列表
- [ ] 系统桌面、任务栏不在列表中
- [ ] QuickRec 自身窗口不在列表中
- [ ] 双击列表项选择窗口并关闭对话框
- [ ] 点击"选择"按钮选择当前选中项
- [ ] 点击"取消"或关闭对话框发射 `cancelled` 信号
- [ ] 窗口大小/位置信息通过 `window_selected` 信号传出