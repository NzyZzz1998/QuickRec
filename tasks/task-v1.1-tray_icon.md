# 任务：系统托盘模块更新 (tray_icon.py) — v1.1

**模块**：`src/ui/tray_icon.py`（更新）
**说明**：动态菜单切换 + Toast 通知增强。基于 v1.0 信号桥模式扩展。

## 前置依赖
- [x] main.py 理解回调机制

## 子任务

### 1. 动态菜单切换
- [x] `_SignalBridge` 新增信号：`start_region_requested`, `pause_resume_requested`, `stop_requested`
- [x] 新增 `_is_recording` 和 `_is_paused` 状态标志
- [x] 实现 `_build_idle_menu()`：全屏录制 / 区域录制 / 设置 / 打开保存文件夹 / 退出
- [x] 实现 `_build_recording_menu()`：暂停/继续 / 停止录制 / 设置 / 打开保存文件夹 / 退出
- [x] 实现 `set_recording_state(recording, paused)` 方法：切换菜单并调用 `_icon.update_menu()`
- [x] 暂停/继续按钮文字根据 `_is_paused` 动态切换（"⏸ 暂停录制" / "▶ 继续录制"）

### 2. Toast 通知增强
- [x] 安装 winotify（`pip install winotify`）
- [x] 实现 `show_notification_with_action(title, msg, action_label, action_callback)` 方法
- [x] 优先使用 winotify Toast 通知：标题 + 内容 + "打开文件夹" 按钮
- [x] 点击"打开文件夹"→ `explorer.exe /select,<output_path>`
- [x] 降级链：winotify → pystray.notify()（v1.0 方式）
- [x] 导入失败时静默降级到 pystray 通知

### 3. 托盘菜单回调扩展
- [x] callbacks 字典新增：`start_fullscreen`, `start_region`, `pause_resume`, `stop`
- [x] `_handle_start()` 拆分为 `_handle_start_fullscreen()` 和 `_handle_start_region()`
- [x] 新增 `_handle_pause_resume()` 和 `_handle_stop()` 处理函数

## 验收标准
- [ ] 空闲状态显示菜单：全屏录制 / 区域录制 / 设置 / 打开保存文件夹 / 退出
- [ ] 录制中状态显示菜单：暂停/继续 / 停止录制 / 设置 / 打开保存文件夹 / 退出
- [ ] 暂停状态"暂停"变为"继续"
- [ ] Toast 通知显示"打开文件夹"按钮
- [ ] winotify 不可用时降级为纯文本通知