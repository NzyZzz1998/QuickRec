# 任务：设置对话框模块 (settings_dialog.py)

**模块**：`src/ui/settings_dialog.py`
**说明**：提供用户修改配置的界面。

## 前置依赖
- [x] PyQt5 5.15.10 (Anaconda 已安装)
- [x] config 模块完成

## 子任务

### 1. 实现 SettingsDialog 类 (QDialog)
- [x] 继承 QDialog
- [x] 配置管理器连接
- [x] 信号: config_saved

### 2. 控件定义
- [x] 保存路径输入 + 浏览按钮
- [x] 画质选择 (high/medium/low)
- [x] 帧率选择 (30/60)
- [x] 快捷键显示 (只读)
- [x] 保存/取消按钮

### 3. 功能实现
- [x] 打开时显示当前配置值
- [x] 修改后保存到 ConfigManager
- [x] 浏览按钮打开文件夹选择器
- [x] 取消按钮不保存修改

## 验收标准
- [x] 打开时显示当前配置值
- [x] 修改后保存，下次打开显示新值
- [x] 浏览按钮打开文件夹选择器
- [x] 取消按钮不保存修改