# 任务：屏幕捕获模块 (screen_capturer.py)

**模块**：`src/recorder/screen_capturer.py`
**说明**：使用 mss 捕获屏幕或指定区域的图像帧。

## 前置依赖
- [ ] 安装 mss 包 (pip install mss)

## 子任务

### 1. 实现 ScreenCapturer 类
- [ ] 定义 `ScreenCapturer` 类
- [ ] 实现 `__init__(region=None)` 初始化
- [ ] 实现 `capture_frame()` 捕获一帧
- [ ] 实现 `close()` 释放资源

### 2. 捕获模式
- [ ] 全屏模式：region=None，自动获取主显示器尺寸
- [ ] 区域模式：region=(x, y, w, h)，只捕获指定区域

### 3. 数据格式
- [ ] 返回 numpy ndarray (BGR 格式)
- [ ] 验证帧尺寸正确

### 4. 单元测试
- [ ] 测试全屏捕获返回正确分辨率
- [ ] 测试区域捕获返回指定尺寸
- [ ] 测试连续捕获帧率稳定
- [ ] 测试 close 后不可再捕获

## 验收标准
- [ ] 能正确捕获全屏/区域
- [ ] 返回 numpy BGR 格式帧
- [ ] 所有单元测试通过
