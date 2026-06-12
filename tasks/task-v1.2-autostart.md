# 任务：开机自启模块 (autostart.py) — v1.2

**模块**：`src/utils/autostart.py`（新增）
**说明**：管理开机自启注册表项，操作 HKEY_CURRENT_USER\Run。

## 前置依赖
- [x] 无（独立工具模块）

## 子任务

### 1. 注册表操作
- [x] `AUTO_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"` 常量定义
- [x] `AUTO_RUN_NAME = "QuickRec"` 注册表项名常量
- [x] `is_autostart_enabled() -> bool` 读取注册表项
  - 读取 HKCU\Run 中 QuickRec 项的值
  - 与当前可执行文件路径比较（不区分大小写）
  - 不存在或异常时返回 False
- [x] `enable_autostart() -> bool` 写入注册表项
  - 打开 HKCU\Run，写入 QuickRec 项，值为可执行文件路径
  - 打包后使用 `sys.executable` 路径
  - 成功返回 True，异常返回 False 并 log.error
- [x] `disable_autostart() -> bool` 删除注册表项
  - 删除 HKCU\Run 中 QuickRec 项
  - 项不存在时返回 True
  - 成功返回 True，异常返回 False 并 log.error
- [x] `_get_executable_path() -> str` 获取当前可执行文件路径
  - `sys.frozen` 为 True 时返回 `sys.executable`
  - 否则返回 `sys.executable`（开发环境路径）

### 2. 日志记录
- [x] 操作成功/失败均有 logger.info/error 日志

## 验收标准
- [x] `enable_autostart()` 后 `is_autostart_enabled()` 返回 True
- [x] `disable_autostart()` 后 `is_autostart_enabled()` 返回 False
- [x] 打包后路径正确指向 QuickRec.exe
- [x] 无管理员权限要求（仅 HKCU 操作）
- [x] 注册表项不存在时 `is_autostart_enabled()` 返回 False 不报错