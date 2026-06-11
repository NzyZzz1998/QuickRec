# 任务：配置管理模块 (config.py)

**模块**：`src/config.py`
**说明**：读写用户配置，提供类型安全的配置访问接口。

## 前置依赖
- [x] Python 3.12.8 (Anaconda 已安装)
- [x] PyQt5 5.15.10 (Anaconda 已安装)

## 子任务

### 1. 实现 ConfigManager 类
- [ ] 定义 `ConfigManager` 类，包含 `config_path` 属性
- [ ] 实现 `get(key, default)` 方法读取配置
- [ ] 实现 `set(key, value)` 方法设置配置
- [ ] 实现 `save()` 方法持久化到 JSON 文件
- [ ] 实现 `load()` 方法从 JSON 文件加载
- [ ] 实现 `reset()` 方法恢复默认配置

### 2. 默认值定义
- [ ] 定义 `defaults` 字典包含所有默认配置项
- [ ] 配置项：save_path (默认 Videos/QuickRec)
- [ ] 配置项：quality (默认 "high")
- [ ] 配置项：fps (默认 30)
- [ ] 配置项：shortcut_start (默认 "Ctrl+Shift+R")
- [ ] 配置项：shortcut_stop (默认 "Ctrl+Shift+S")
- [ ] 配置项：shortcut_pause (默认 "Ctrl+Shift+P")

### 3. 文件路径处理
- [ ] 配置文件路径：`C:/Users/<用户名>/AppData/Roaming/QuickRec/config.json`
- [ ] 路径不存在时自动创建目录

### 4. 异常处理
- [ ] 配置文件不存在时，自动创建并使用默认值
- [ ] 配置文件格式错误时，使用默认值并记录日志

### 5. 单元测试
- [ ] 测试默认值加载
- [ ] 测试 set/save/load 一致性
- [ ] 测试文件不存在时的自动创建
- [ ] 测试文件损坏时的恢复

## 验收标准
- [ ] 配置文件能正确读写
- [ ] 异常情况不崩溃
- [ ] 所有单元测试通过
