# 任务：录制控制模块 (recorder_manager.py)

**模块**：`src/recorder/recorder_manager.py`
**说明**：协调屏幕捕获和视频编码，管理录制生命周期。

## 前置依赖
- [x] screen_capturer 模块完成
- [x] video_encoder 模块完成
- [x] file_namer 模块完成
- [x] disk_checker 模块完成
- [x] config 模块完成

## 子任务

### 1. 实现 RecorderState 枚举
- [x] IDLE - 空闲
- [x] RECORDING - 录制中
- [x] PAUSED - 暂停
- [x] STOPPING - 停止中

### 2. 实现 RecorderManager 类
- [x] `__init__(config)` 初始化
- [x] `start_fullscreen()` 开始全屏录制
- [x] `start_region(region)` 开始区域录制
- [x] `pause()` 暂停录制
- [x] `resume()` 恢复录制
- [x] `stop()` 停止录制，返回文件路径
- [x] `get_state()` 获取当前状态
- [x] `get_elapsed()` 获取已录制时长

### 3. 录制循环
- [x] 独立线程运行录制循环
- [x] 根据 fps 控制捕获频率
- [x] 暂停时跳过写入
- [x] 磁盘满时自动停止（write_frame 失败时中断）

### 4. 单元测试
- [x] 测试初始状态为 IDLE
- [x] 测试 start 后状态为 RECORDING
- [x] 测试 pause/resume 状态流转
- [x] 测试 stop 后返回有效文件路径
- [x] 测试空闲时停止返回空字符串
- [x] 测试录制时长格式正确
- [x] 测试连续 start-stop 无资源泄漏

## 验收标准
- [x] 状态流转正确
- [x] 录制文件可正常播放
- [x] 暂停/恢复功能正常
- [x] 所有单元测试通过 (7/7)