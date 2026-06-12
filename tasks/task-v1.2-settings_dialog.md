# 任务：设置对话框更新 (settings_dialog.py) — v1.2

**模块**：`src/ui/settings_dialog.py`（更新）
**说明**：新增开机自启、录制倒计时、鼠标高亮复选框 + 窗口录制快捷键 + 画质动态显示。

## 前置依赖
- [x] config.py（新增配置项 + get_native_resolution）
- [x] autostart.py（开机自启注册表操作）

## 子任务

### 1. 新增控件
- [x] `_cb_auto_start: QCheckBox` — 开机自启复选框
  - 文本："开机自启"
  - 勾选时调用 `autostart.enable_autostart()`
  - 取消时调用 `autostart.disable_autostart()`
- [x] `_cb_countdown: QCheckBox` — 录制倒计时复选框
  - 文本："录制倒计时"
  - 勾选后启用 `_spin_countdown_seconds` 控件
  - 默认不勾选（配置 show_countdown=False）
- [x] `_spin_countdown_seconds: QSpinBox` — 倒计时秒数输入框
  - 范围 1-10，默认 3
  - 仅在 `_cb_countdown` 勾选时启用
  - 与 `_cb_countdown` 的 toggled 信号联动
- [x] `_cb_mouse_highlight: QCheckBox` — 鼠标点击高亮复选框
  - 文本："鼠标点击高亮"
  - 默认不勾选（配置 mouse_highlight=False）
- [x] `_shortcut_window: _ShortcutRecorder` — 窗口录制快捷键
  - 使用已有的 _ShortcutRecorder 控件
  - 默认值："Ctrl+Shift+W"

### 2. 画质下拉框动态显示
- [x] `_refresh_quality_combo()` 方法
  - 调用 `ConfigManager.get_native_resolution()` 获取主显示器分辨率
  - "原生"选项显示为 `"原生(1920×1080)"` 格式（动态）
  - 其他选项保持固定文本："高(1080p)"、"中(720p)"、"低(480p)"
- [x] 在 `__init__` 中调用 `_refresh_quality_combo()`

### 3. 布局调整
- [x] 将开机自启、录制倒计时、鼠标点击高亮放在同一行（或两行）
- [x] 窗口录制快捷键放在暂停快捷键之后
- [x] 保持与 v1.1 设置界面风格一致

### 4. _load_config 扩展
- [x] 读取 `auto_start` → 设置 `_cb_auto_start` 勾选状态
  - 额外检查注册表实际值：`autostart.is_autostart_enabled()` 确保一致性
- [x] 读取 `show_countdown` → 设置 `_cb_countdown` 勾选状态
- [x] 读取 `countdown_seconds` → 设置 `_spin_countdown_seconds` 值
- [x] 读取 `mouse_highlight` → 设置 `_cb_mouse_highlight` 勾选状态
- [x] 读取 `shortcut_window` → 设置 `_shortcut_window` 值

### 5. _save_config 扩展
- [x] 保存 `show_countdown` 到 config
- [x] 保存 `countdown_seconds` 到 config
- [x] 保存 `mouse_highlight` 到 config
- [x] 保存 `auto_start` 到 config
  - 同时调用 `autostart.enable_autostart()` 或 `autostart.disable_autostart()` 操作注册表
- [x] 保存 `shortcut_window` 到 config

## 验收标准
- [x] 开机自启勾选后注册表有 QuickRec 项
- [x] 取消勾选后注册表项被删除
- [x] 打开设置时开机自启状态与注册表实际值一致
- [x] 原生画质显示当前实际分辨率（如 "原生(1920×1080)"）
- [x] 倒计时复选框控制秒数输入框启用/禁用
- [x] 窗口录制快捷键可录制和保存
- [x] 所有意控件保存和加载正常
- [x] 旧版配置加载后新字段有默认值