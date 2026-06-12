# 任务：音频录制模块 (audio_capturer.py) — v1.1 新增

**模块**：`src/recorder/audio_capturer.py`（新增文件）
**说明**：录制系统声音和/或麦克风音频，与视频同步保存。基于 pyaudiowpatch + pyaudio。

## 前置依赖
- [ ] config 模块完成（audio_source 配置项）
- [ ] recorder_manager.py 理解临时文件缓存方案

## 子任务

### 1. AudioSource 枚举和 AudioCapturer 类框架
- [ ] 定义 `AudioSource` 枚举：NONE / SYSTEM / MICROPHONE / BOTH
- [ ] 创建 `AudioCapturer` 类，__init__ 接收 source 和 output_dir
- [ ] 定义类属性：_source, _sample_rate, _channels, _sample_width, _is_recording, _audio_thread

### 2. WASAPI 系统声音捕获
- [ ] 实现 `_find_wasapi_loopback()` 方法：使用 pyaudiowpatch 查找环形缓冲区输出设备
- [ ] 找不到设备时返回 None，优雅降级
- [ ] 验证 pyaudiowpatch 安装（`pip install pyaudiowpatch`）

### 3. 麦克风捕获
- [ ] 使用 pyaudio 打开默认输入设备
- [ ] 验证 pyaudio 安装（`pip install pyaudio`）

### 4. 音频捕获线程
- [ ] 实现 `start()` 方法：初始化音频流、创建 WAV 文件、启动捕获线程
- [ ] 实现 `_capture_loop()` 方法：循环读取音频数据并写入 WAV 文件
- [ ] BOTH 模式：同时打开系统声音和麦克风流，分别写入两个 WAV 文件
- [ ] 实现 `stop()` 方法：关闭音频流、关闭 WAV 文件、返回临时文件路径列表

### 5. WAV 文件写入
- [ ] 使用 Python `wave` 模块直接写入 WAV 临时文件
- [ ] SYSTEM 模式：一个 WAV 文件（`<output>.audio_sys.wav`）
- [ ] MICROPHONE 模式：一个 WAV 文件（`<output>.audio_mic.wav`）
- [ ] BOTH 模式：两个独立 WAV 文件

### 6. 优雅降级
- [ ] AudioCapturer.start() 返回 False 时：log 警告，RecorderManager 继续无声录制
- [ ] 音频设备不可用或不支持时：自动降级为 AudioSource.NONE

## 验收标准
- [ ] SYSTEM 模式可捕获系统声音并写入 WAV 文件
- [ ] MICROPHONE 模式可捕获麦克风输入并写入 WAV 文件
- [ ] BOTH 模式可同时捕获两路音频
- [ ] 音频设备初始化失败时不影响视频录制
- [ ] WAV 文件采样率/声道数正确，可被 FFmpeg 识别