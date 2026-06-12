# 任务：系统托盘模块更新 (tray_icon.py) — v1.2

**模块**：`src/ui/tray_icon.py`（更新）
**说明**：空闲菜单新增"窗口录制"选项。

## 前置依赖
- [x] 无（仅 UI 更新）

## 子任务

### 1. 信号桥扩展
- [x] `_SignalBridge` 新增 `start_window_requested = pyqtSignal()`

### 2. 空闲菜单更新
- [x] `_build_idle_menu()` 新增 "窗口录制" 菜单项
  - 位于"区域录制"之后
  - 回调：`self._bridge.start_window_requested.emit`

### 3. 回调字典扩展
- [x] `_callbacks` 新增 `"start_window": self._on_start_window` 键
- [x] `_on_start_window()` 方法：通过信号桥发射 `start_window_requested`

### 4. 菜单项文字
- [x] 空闲菜单顺序：
  - ▶ 全屏录制
  - ▢ 区域录制
  - 🖥 窗口录制 ← 新增
  - ⚙ 设置
  - 📁 打开保存文件夹
  - ───
  - ✕ 退出

## 验收标准
- [x] 空闲状态托盘菜单显示"窗口录制"选项
- [x] 点击"窗口录制"触发 `start_window_requested` 信号
- [x] 录制中菜单不变（暂停/继续、停止、设置、打开文件夹、退出）
- [x] 与已有菜单项功能无冲突