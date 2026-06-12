# 任务：配置管理模块更新 (config.py) — v1.1

**模块**：`src/config.py`（更新）
**说明**：新增 audio_source 和 shortcut_area 配置项。基于 v1.0 ConfigManager 扩展。

## 前置依赖
- [ ] 无（独立模块）

## 子任务

### 1. 新增配置项
- [x] `defaults` 字典新增 `"audio_source": "none"` 配置项
  - 可选值：none / system / microphone / both
  - 默认值 "none"（与 v1.0 无音频行为一致）
- [x] `defaults` 字典新增 `"shortcut_area": "Ctrl+Shift+A"` 配置项
  - 区域录制的默认快捷键
- [x] 确保 `get()` 和 `set()` 方法正常读写新配置项

### 2. 向后兼容
- [x] 旧版 v1.0 配置文件加载时，缺失 `audio_source` 自动填入 "none"
- [x] 旧版 v1.0 配置文件加载时，缺失 `shortcut_area` 自动填入 "Ctrl+Shift+A"
- [x] ConfigManager 已有 `_ensure_defaults()` 机制确保新字段自动填充

### 3. 音频源选项映射
- [x] 新增类变量或模块常量 `AUDIO_OPTIONS`：
  ```python
  AUDIO_OPTIONS = [
      ("无", "none"),
      ("系统声音", "system"),
      ("麦克风", "microphone"),
      ("两者都有", "both"),
  ]
  ```
- [ ] settings_dialog.py 可导入此映射用于下拉框

## 验收标准
- [ ] `config.get("audio_source")` 默认返回 "none"
- [ ] `config.get("shortcut_area")` 默认返回 "Ctrl+Shift+A"
- [ ] 旧版 v1.0 配置文件加载后新字段有默认值
- [ ] `config.set("audio_source", "system")` 正确保存和读取