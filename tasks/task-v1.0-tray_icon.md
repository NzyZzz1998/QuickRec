# 任务：系统托盘模块 (tray_icon.py)

**模块**：`src/ui/tray_icon.py`
**说明**：管理系统托盘图标。

## 前置依赖
- [x] 安装 pystray 包 (pip install pystray)
- [x] PyQt5 5.15.10 (Anaconda 已安装)

## 子任务

### 1. 实现 TrayIcon 类
- [x] 使用 pystray 创建托盘图标
- [x] 默认图标 (自定义绘制圆形录制图标)

### 2. 菜单项
- [x] "▶ 开始录制" → 触发录制
- [x] "⚙ 设置" → 打开设置对话框
- [x] "📁 打开保存文件夹" → 打开 save_path
- [x] "✕ 退出" → 退出程序

### 3. 功能
- [x] `show()` 显示托盘图标
- [x] `hide()` 隐藏托盘图标
- [x] `show_notification(msg)` 弹出系统通知
- [x] `set_menu(menu_items)` 设置菜单

## 验收标准
- [x] 托盘图标正常显示
- [x] 菜单项点击触发正确
- [x] 通知弹出正常