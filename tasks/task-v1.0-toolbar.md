# 任务：录制工具栏模块 (toolbar.py)

**模块**：`src/ui/toolbar.py`
**说明**：录制中的悬浮控制窗口，显示录制状态和提供控制按钮。

## 子任务

### 1. 实现 RecordingToolbar 类 (QWidget)
- [x] 继承 QWidget
- [x] 无边框窗口 (FramelessWindowHint | WindowStaysOnTopHint)
- [x] 半透明背景 (#1a1a2e, 90%)
- [x] 圆角 8px

### 2. UI 元素
- [x] 录制指示灯 (红色圆点)
- [x] 计时器显示 (Consolas 字体, MM:SS)
- [x] 暂停按钮 ("⏸ 暂停" / "▶ 继续")
- [x] 停止按钮 ("⏹ 停止")
- [x] 取消按钮 ("✕ 取消")

### 3. 交互功能
- [x] 暂停时指示灯变黄色，按钮文字切换
- [x] 拖拽窗口移动
- [x] 信号: paused, resumed, stopped, cancelled

## 验收标准
- [x] 计时器每秒更新，格式正确
- [x] 暂停按钮文字在"暂停"/"继续"之间切换
- [x] 拖动窗口位置正常
- [x] 始终置顶