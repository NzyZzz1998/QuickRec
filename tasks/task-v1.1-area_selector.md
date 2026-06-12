# 任务：区域录制模块 (area_selector.py) — v1.1 更新

**模块**：`src/ui/area_selector.py`
**说明**：全屏遮罩 + 拖拽选择矩形区域。v1.0 已有基础代码，v1.1 修复 Win11 点击穿透并新增确认对话框。

## 前置依赖
- [ ] config 模块完成（shortcut_area 配置项）
- [ ] main.py 信号桥模式理解

## 子任务

### 1. Win11 点击穿透修复
- [ ] 移除 `Qt.Tool` 窗口标志（这是点击穿透的根因）
- [ ] 保留 `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`
- [ ] 添加 `Qt.StrongFocus` 焦点策略
- [ ] `show_fullscreen()` 中确保 `raise_()` → `activateWindow()` → `setFocus()` 调用顺序

### 2. 确认对话框
- [ ] 拖拽完成后（mouseReleaseEvent）判断选区尺寸
- [ ] 选区 >= MIN_SIZE：在选区中心显示确认浮动按钮（"开始录制" / "取消"）
- [ ] "开始录制" → emit `region_selected(x, y, w, h)` → close
- [ ] "取消" → emit `cancelled` → close

### 3. 最小尺寸提示
- [ ] 选区 < MIN_SIZE 时：在释放位置显示红色提示 "选区太小 (最小 100x100)"
- [ ] 红色提示 1 秒后自动消失
- [ ] emit `cancelled` → close

### 4. 边框视觉优化
- [ ] 选区边框从蓝色实线改为白色虚线
- [ ] 半透明遮罩 alpha 值调优确保选中区域清晰可见

### 5. 与 main.py 集成
- [ ] main.py 添加 `_AreaBridge` 信号桥
- [ ] main.py 添加 `_on_start_region()` → 创建 AreaSelector 并连接信号
- [ ] main.py 添加 `_on_region_selected(x, y, w, h)` → 调用 `RecorderManager.start_region()`
- [ ] main.py 添加 `_on_selection_cancelled()`
- [ ] TrayIcon 添加"区域录制"菜单项
- [ ] HotkeyBridge 添加 `area_requested` 信号
- [ ] 注册快捷键 `Ctrl+Shift+A`

## 验收标准
- [ ] Win11 下可正常拖拽选区（不点击穿透）
- [ ] ESC 和右键可取消
- [ ] 选区太小时显示红色提示
- [ ] 确认对话框正常弹出和响应
- [ ] 确认后开始区域录制，工具栏正常显示
- [ ] 快捷键 Ctrl+Shift+A 可触发区域录制