# 任务：屏幕捕获模块 (screen_capturer.py)

**模块**：`src/recorder/screen_capturer.py`
**说明**：使用 mss 捕获屏幕或指定区域的图像帧。

## 前置依赖
- [x] 安装 mss 包 (pip install mss)

## 子任务

### 1. 实现 ScreenCapturer 类
- [x] 定义 `ScreenCapturer` 类
- [x] 实现 `__init__(region=None)` 初始化
- [x] 实现 `capture_frame()` 捕获一帧
- [x] 实现 `close()` 释放资源

### 2. 捕获模式
- [x] 全屏模式：region=None，自动获取主显示器尺寸
- [x] 区域模式：region=(x, y, w, h)，只捕获指定区域

### 3. 数据格式
- [x] 返回 numpy ndarray (BGR 格式)
- [x] 验证帧尺寸正确

### 4. 单元测试
- [x] 测试全屏捕获返回正确分辨率
- [x] 测试区域捕获返回指定尺寸
- [x] 测试连续捕获帧率稳定
- [x] 测试 close 后不可再捕获

## 验收标准
- [x] 能正确捕获全屏/区域
- [x] 返回 numpy BGR 格式帧
- [x] 所有单元测试通过 (6/6)