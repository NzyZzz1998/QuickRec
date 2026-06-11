# 任务：全局快捷键模块 (hotkey_manager.py)

**模块**：`src/hotkey/hotkey_manager.py`
**说明**：注册和监听全局键盘快捷键。

## 前置依赖
- [x] 安装 keyboard 包 (pip install keyboard)

## 子任务

### 1. 实现 HotkeyManager 类
- [x] 定义 `HotkeyManager` 类
- [x] `register(shortcut, callback)` 注册快捷键
- [x] `unregister(shortcut)` 取消注册
- [x] `start_listening()` 开始监听
- [x] `stop_listening()` 停止监听
- [x] `parse_shortcut(shortcut)` 解析快捷键字符串

### 2. 快捷键格式
- [x] 输入格式：`Ctrl+Shift+R`
- [x] 输出：`['ctrl', 'shift', 'r']`
- [x] 统一小写规范化存储
- [x] 重复注册返回 False

### 3. 单元测试
- [x] 测试快捷键解析正确
- [x] 测试重复注册返回 False
- [x] 测试取消未注册的快捷键返回 False

## 验收标准
- [x] 全局快捷键有效
- [x] 重复注册防护
- [x] 所有单元测试通过