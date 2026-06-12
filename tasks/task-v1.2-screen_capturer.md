# 任务：屏幕捕获模块更新 (screen_capturer.py) — v1.2

**模块**：`src/recorder/screen_capturer.py`（更新）
**说明**：新增 `update_region()` 方法，支持窗口录制时动态更新捕获区域。

## 前置依赖
- [x] 无（独立模块更新）

## 子任务

### 1. 新增 update_region 方法
- [x] `update_region(self, region: tuple) -> None` 方法
  - 参数 `region: (left, top, width, height)` 新的捕获区域
  - 更新 `self._region` 为新值
  - 重新计算 `self._dxcam_region` 为 `(left, top, left + width, top + height)` 格式（dxcam 坐标）
  - 如果 `_camera` 已启动，下一帧 `capture_frame()` 自动使用新区域
- [x] 更新 `get_monitor_size()` 方法
  - 若 `_region` 不为 None，返回 `_region` 的 (width, height)
  - 否则返回全屏尺寸

### 2. 窗口录制兼容
- [x] 确认 `update_region()` 在录制循环中调用时线程安全
  - `_region` 和 `_dxcam_region` 是简单元组赋值，Python GIL 保证原子性
  - 不需要额外锁

## 验收标准
- [x] `update_region((100, 200, 800, 600))` 后 `capture_frame()` 返回新区域的帧
- [x] 区域更新不影响录制帧率（无额外延迟）
- [x] `get_monitor_size()` 返回当前捕获区域的尺寸
- [x] 全屏录制时 `update_region` 不影响现有行为