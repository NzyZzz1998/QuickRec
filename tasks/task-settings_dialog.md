# 任务：设置对话框模块 (settings_dialog.py)

**模块**：`src/ui/settings_dialog.py`
**说明**：提供用户修改配置的界面。

## 前置依赖
- [x] PyQt5 5.15.10 (Anaconda 已安装)
- [ ] config 模块完成

## 子任务

### 1. 实现 SettingsDialog 类 (QDialog)
- [ ] 标准对话框布局
- [ ] 各配置项控件布局

### 2. 控件定义
- [ ] 保存路径：QLineEdit + 浏览按钮
- [ ] 画质：QComboBox (高/中/低)
- [ ] 帧率：QComboBox (30/60)
- [ ] 快捷键显示：QLabel (显示当前快捷键)

### 3. 功能实现
- [ ] 打开时加载当前配置值
- [ ] 修改后保存到 config
- [ ] 取消按钮不保存修改
- [ ] 浏览按钮打开文件夹选择器 (QFileDialog)

### 4. 信号定义
- [ ] `config_saved()` - 配置保存成功

## 验收标准
- [ ] 界面布局正确
- [ ] 配置加载/保存正常
- [ ] 取消不保存
