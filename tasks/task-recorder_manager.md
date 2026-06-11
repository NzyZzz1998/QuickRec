# 任务：录制控制模块 (recorder_manager.py)

**模块**：`src/recorder/recorder_manager.py`
**说明**：协调屏幕捕获和视频编码，管理录制生命周期。

## 前置依赖
- [ ] screen_capturer 模块完成
- [ ] video_encoder 模块完成
- [ ] file_namer 模块完成
- [ ] disk_checker 模块完成
- [ ] config 模块完成

## 子任务

### 1. 实现 RecorderState 枚举
- [ ] IDLE - 空闲
- [ ] COUNTDOWN - 倒计时
- [ ] RECORDING - 录制中
- [ ] PAUSED - 暂停
- [ ] STOPPING - 停止中

### 2. 实现 RecorderManager 类
- [ ] `__init__(config)` 初始化
- [ ] `start_fullscreen()` 开始全屏录制
- [ ] `start_region(region)` 开始区域录制
- [ ] `pause()` 暂停录制
- [ ] `resume()` 恢复录制
- [ ] `stop()` 停止录制，返回文件路径
- [ ] `get_state()` 获取当前状态
- [ ] `get_elapsed()` 获取已录制时长

### 3. 录制循环
- [ ] 独立线程运行录制循环
- [ ] 根据 fps 控制捕获频率
- [ ] 暂停时跳过写入
- [ ] 磁盘满时自动停止

### 4. 单元测试
- [ ] 测试 start 后状态为 RECORDING
- [ ] 测试 pause/resume 状态流转
- [ ] 测试 stop 后返回有效文件路径
- [ ] 测试连续 start-stop 无资源泄漏

## 验收标准
- [ ] 状态流转正确
- [ ] 录制文件可正常播放
- [ ] 暂停/恢复功能正常
- [ ] 所有单元测试通过
