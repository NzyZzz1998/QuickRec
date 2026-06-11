# 任务：主程序入口 (main.py)

**模块**：`src/main.py`
**说明**：初始化所有模块，启动应用。

## 前置依赖
- [x] 所有其他模块完成

## 子任务

### 1. 初始化流程
- [x] 创建 QApplication
- [x] 初始化 ConfigManager
- [x] 初始化 RecorderManager
- [x] 初始化 TrayIcon
- [x] 初始化 HotkeyManager

### 2. 快捷键绑定
- [x] `Ctrl+Shift+R` → 显示 AreaSelector / 开始录制
- [x] `Ctrl+Shift+S` → stop()
- [x] `Ctrl+Shift+P` → pause()/resume()

### 3. UI 流程
- [x] 托盘右键菜单 → 设置 / 录制 / 退出
- [x] 快捷键 → 区域选择器 → 录制
- [x] 录制时显示 Toolbar
- [x] 停止时关闭 Toolbar

### 4. 退出流程
- [x] 如果正在录制，先 stop
- [x] 停止快捷键监听
- [x] 退出 QApplication

### 5. 异常处理
- [x] 全局异常捕获，记录日志
- [x] 崩溃时尽量保留录制文件

## 验收标准
- [x] 程序正常启动
- [x] 快捷键有效
- [x] 录制流程完整
- [x] 退出时资源正确释放