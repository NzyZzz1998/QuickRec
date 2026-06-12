# 任务：设置对话框模块更新 (settings_dialog.py) — v1.1

**模块**：`src/ui/settings_dialog.py`（更新）
**说明**：新增音频源选择和区域录制快捷键设置。基于 v1.0 SettingsDialog 扩展。

## 前置依赖
- [x] config.py 新增 audio_source 和 shortcut_area 配置项
- [x] hotkey_manager.py 理解 _ShortcutRecorder 实现

## 子任务

### 1. 音频源选择下拉框
- [x] 在帧率（fps）选择行下方新增音频源选择行
- [x] 创建 `_combo_audio_source: QComboBox`，使用 `AUDIO_OPTIONS` 映射填充
- [x] 选项文本：无 / 系统声音 / 麦克风 / 两者都有
- [x] 对应配置值：none / system / microphone / both
- [x] 标签文字："音频源"

### 2. 区域录制快捷键设置
- [x] 在暂停快捷键行下方新增区域录制快捷键行
- [x] 创建 `_shortcut_area: _ShortcutRecorder`（复用 v1.0 已有的自定义控件）
- [x] 默认值：`Ctrl+Shift+A`
- [x] 标签文字："区域录制"

### 3. 配置加载与保存
- [x] `_load_config()` 方法新增：读取 `audio_source` 配置，设置下拉框当前索引
- [x] `_load_config()` 方法新增：读取 `shortcut_area` 配置，设置快捷键显示
- [x] `_save_config()` 方法新增：将音频源选项值写入配置
- [x] `_save_config()` 方法新增：将区域快捷键写入配置

### 4. 布局调整
- [x] 音频源行插入在帧率行和快捷键区域之间
- [x] 区域快捷键行追加在暂停快捷键行之后
- [x] 确保设置对话框整体布局协调、间距一致
- [x] 对话框宽度需要适当增加以容纳新增控件

## 验收标准
- [ ] 设置对话框显示音频源下拉框（4个选项）
- [ ] 设置对话框显示区域录制快捷键录制器
- [ ] 加载时正确回显当前配置的音频源和快捷键
- [ ] 保存时正确写入 audio_source 和 shortcut_area 配置
- [ ] 旧版 v1.0 配置加载后音频源默认为"无"，区域快捷键默认为 Ctrl+Shift+A