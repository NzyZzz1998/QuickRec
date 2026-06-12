# 任务：主程序入口更新 (main.py) — v1.1

**模块**：`src/main.py`（更新）
**说明**：新增区域录制流程、信号桥扩展、托盘回调扩展、通知增强。基于 v1.0 QuickRecApp 扩展。

## 前置依赖
- [ ] area_selector.py 区域录制修复完成
- [ ] tray_icon.py 动态菜单和通知完成
- [ ] toolbar.py 结果条模式完成
- [ ] recorder_manager.py 区域录制和音频集成完成
- [ ] config.py 新增配置项完成

## 子任务

### 1. _AreaBridge 信号桥
- [ ] 新增 `_AreaBridge(QObject)` 类
- [ ] 信号：`region_selected = pyqtSignal(int, int, int, int)` — (x, y, w, h)
- [ ] 信号：`cancelled = pyqtSignal()`
- [ ] `QuickRecApp.__init__()` 中创建 `_area_bridge` 实例
- [ ] 连接 `region_selected` → `_on_region_selected`
- [ ] 连接 `cancelled` → `_on_selection_cancelled`

### 2. _HotkeyBridge 扩展
- [ ] 新增信号：`area_requested = pyqtSignal()`
- [ ] 连接 `area_requested` → `_on_start_region`

### 3. 区域录制流程
- [ ] 实现 `_on_start_region()` 方法：
  ```
  if recorder.state != IDLE: return
  selector = AreaSelector()
  selector.region_selected.connect(area_bridge.region_selected.emit)
  selector.cancelled.connect(area_bridge.cancelled.emit)
  selector.show_fullscreen()
  ```
- [ ] 实现 `_on_region_selected(x, y, w, h)` 方法：
  ```
  if not recorder.start_region(region=(x, y, w, h)): return
  show_toolbar()
  tray.set_recording_state(True)
  ```
- [ ] 实现 `_on_selection_cancelled()` 方法（空操作或 log）

### 4. 托盘回调扩展
- [ ] 托盘 `callbacks` 字典新增：
  - `"start_fullscreen"` → `_on_start_fullscreen`（原 `"start"` 重命名）
  - `"start_region"` → `_on_start_region`（新增）
  - `"pause_resume"` → `_on_pause_resume`（新增）
  - `"stop"` → `_on_stop_recording`（新增）
- [ ] 重命名 `_on_start_recording` → `_on_start_fullscreen`
- [ ] 实现 `_on_pause_resume()`：根据当前状态调用 pause/resume
- [ ] `_on_stop_recording()` 更新：stop 后 `tray.set_recording_state(False)`

### 5. 快捷键注册扩展
- [ ] `_setup_hotkeys()` 中新增区域录制快捷键：
  ```python
  shortcut_area = config.get("shortcut_area", "Ctrl+Shift+A")
  hotkey.register(shortcut_area, hotkey_bridge.area_requested.emit)
  ```

### 6. 编码完成回调增强
- [ ] `_handle_saved(output_path)` 方法更新：
  - 计算文件大小 `file_size_mb`
  - 调用 `tray.show_notification_with_action()` 显示 Toast 通知（带"打开文件夹"按钮）
  - 调用 `toolbar.show_result(output_path, size_str)` 显示结果条
  - 保存失败时调用 `tray.show_notification("保存失败")`
  - `tray.set_recording_state(False)` 切换回空闲菜单

### 7. 工具栏信号连接
- [ ] toolbar `open_folder_requested` 信号 → `explorer /select,<path>`
- [ ] toolbar `open_file_requested` 信号 → `os.startfile(path)`

## 验收标准
- [ ] 快捷键 Ctrl+Shift+A 触发区域选择器
- [ ] 托盘菜单"区域录制"触发区域选择器
- [ ] 区域选择完成 → 开始区域录制 → 工具栏和托盘正确切换状态
- [ ] 区域选择取消 → 无操作，回到空闲状态
- [ ] 托盘录制中菜单显示暂停/继续、停止录制
- [ ] 编码完成后显示 Toast 通知 + 结果条
- [ ] 结果条"已保存"按钮打开视频文件
- [ ] 结果条"📂 打开"按钮打开文件夹并选中