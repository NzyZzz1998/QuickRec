# 任务：配置管理模块 (config.py)

**模块**：`src/config.py`
**说明**：读写用户配置，提供类型安全的配置访问接口。

## 前置依赖
- [x] Python 3.12.8 (Anaconda 已安装)
- [x] PyQt5 5.15.10 (Anaconda 已安装)

## 子任务

### 1. 实现 ConfigManager 类
- [x] 定义 `ConfigManager` 类，包含 `config_path` 属性
- [x] 实现 `get(key, default)` 方法读取配置
- [x] 实现 `set(key, value)` 方法设置配置
- [x] 实现 `save()` 方法持久化到 JSON 文件
- [x] 实现 `load()` 方法从 JSON 文件加载
- [x] 实现 `reset()` 方法恢复默认配置

### 2. 默认值定义
- [x] 定义 `defaults` 字典包含所有默认配置项
- [x] 配置项：save_path (默认 Videos/QuickRec)
- [x] 配置项：quality (默认 "high")
- [x] 配置项：fps (默认 30)
- [x] 配置项：shortcut_start (默认 "Ctrl+Shift+R")
- [x] 配置项：shortcut_stop (默认 "Ctrl+Shift+S")
- [x] 配置项：shortcut_pause (默认 "Ctrl+Shift+P")

### 3. 文件路径处理
- [x] 配置文件路径：`C:/Users/<用户名>/AppData/Roaming/QuickRec/config.json`
- [x] 路径不存在时自动创建目录

### 4. 异常处理
- [x] 配置文件不存在时，自动创建并使用默认值
- [x] 配置文件格式错误时，使用默认值并记录日志

### 5. 单元测试
- [x] 测试默认值加载
- [x] 测试 set/save/load 一致性
- [x] 测试文件不存在时的自动创建
- [x] 测试文件损坏时的恢复

## 验收标准
- [x] 配置文件能正确读写
- [x] 异常情况不崩溃
- [x] 所有单元测试通过 (8/8)
