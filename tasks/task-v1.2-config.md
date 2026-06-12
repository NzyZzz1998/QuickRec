# 任务：配置管理模块更新 (config.py) — v1.2

**模块**：`src/config.py`（更新）
**说明**：新增窗口录制快捷键、倒计时、鼠标高亮、开机自启配置项，新增 get_native_resolution() 静态方法。基于 v1.1 ConfigManager 扩展。

## 前置依赖
- [ ] 无（独立模块，最先开发）

## 子任务

### 1. 新增配置项
- [ ] `defaults` 字典新增 `"shortcut_window": "Ctrl+Shift+W"` 配置项
  - 窗口录制的默认快捷键
- [ ] `defaults` 字典新增 `"show_countdown": False` 配置项
  - 是否显示录制倒计时
- [ ] `defaults` 字典新增 `"countdown_seconds": 3` 配置项
  - 倒计时秒数，默认 3
- [ ] `defaults` 字典新增 `"mouse_highlight": False` 配置项
  - 鼠标点击高亮开关，默认关闭
- [ ] `defaults` 字典新增 `"auto_start": False` 配置项
  - 开机自启开关，默认关闭
- [ ] 确保 `get()` 和 `set()` 方法正常读写新配置项

### 2. 原生画质动态分辨率
- [ ] 新增静态方法 `get_native_resolution() -> tuple[int, int]`
  - 使用 `ctypes.windll.user32.GetSystemMetrics(0)` 获取屏幕宽度
  - 使用 `ctypes.windll.user32.GetSystemMetrics(1)` 获取屏幕高度
  - 返回 `(width, height)` 元组
- [ ] `QUALITY_SIZES` 中 `"native"` 仍为 `None`（不变，运行时动态计算）

### 3. 向后兼容
- [ ] 旧版 v1.1 配置文件加载时，缺失 `shortcut_window` 自动填入 `"Ctrl+Shift+W"`
- [ ] 旧版 v1.1 配置文件加载时，缺失 `show_countdown` 自动填入 `False`
- [ ] 旧版 v1.1 配置文件加载时，缺失 `countdown_seconds` 自动填入 `3`
- [ ] 旧版 v1.1 配置文件加载时，缺失 `mouse_highlight` 自动填入 `False`
- [ ] 旧版 v1.1 配置文件加载时，缺失 `auto_start` 自动填入 `False`
- [ ] ConfigManager 已有 `_ensure_defaults()` 机制确保新字段自动填充

## 验收标准
- [ ] `config.get("shortcut_window")` 默认返回 `"Ctrl+Shift+W"`
- [ ] `config.get("show_countdown")` 默认返回 `False`
- [ ] `config.get("countdown_seconds")` 默认返回 `3`
- [ ] `config.get("mouse_highlight")` 默认返回 `False`
- [ ] `config.get("auto_start")` 默认返回 `False`
- [ ] `ConfigManager.get_native_resolution()` 返回正确的主显示器分辨率
- [ ] 旧版 v1.1 配置文件加载后新字段有默认值