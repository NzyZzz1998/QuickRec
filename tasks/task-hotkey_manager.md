# 任务：全局快捷键模块 (hotkey_manager.py)

**模块**：`src/hotkey/hotkey_manager.py`
**说明**：注册和监听全局键盘快捷键。

## 前置依赖
- [ ] 安装 keyboard 包 (pip install keyboard)

## 子任务

### 1. 实现 HotkeyManager 类
- [ ] 定义 `HotkeyManager` 类
- [ ] `register(shortcut, callback)` 注册快捷键
- [ ] `unregister(shortcut)` 取消注册
- [ ] `start_listening()` 开始监听
- [ ] `stop_listening()` 停止监听
- [ ] `parse_shortcut(shortcut)` 解析快捷键字符串

### 2. 快捷键格式
- [ ] 输入格式：`Ctrl+Shift+R`
- [ ] 输出：`['ctrl', 'shift', 'r']`
- [ ] 必须包含至少一个修饰键

### 3. 单元测试
- [ ] 测试快捷键解析正确
- [ ] 测试注册后按下快捷键触发回调
- [ ] 测试重复注册返回 False

## 验收标准
- [ ] 全局快捷键有效
- [ ] 后台/最小化时仍有效
- [ ] 所有单元测试通过
