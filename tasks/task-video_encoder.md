# 任务：视频编码模块 (video_encoder.py)

**模块**：`src/recorder/video_encoder.py`
**说明**：将帧序列编码为 MP4 文件并写入磁盘。

## 前置依赖
- [ ] 安装 opencv-python 包 (pip install opencv-python)

## 子任务

### 1. 实现 VideoEncoder 类
- [ ] 定义 `VideoEncoder` 类
- [ ] 实现 `__init__(file_path, fps, frame_size, bitrate)`
- [ ] 实现 `write_frame(frame)` 写入一帧
- [ ] 实现 `close()` 完成写入并关闭文件
- [ ] 实现 `is_open()` 检查状态

### 2. 编码参数
- [ ] 使用 OpenCV VideoWriter
- [ ] fourcc: `mp4v`
- [ ] 输入：BGR numpy ndarray
- [ ] 输出：MP4 文件

### 3. 单元测试
- [ ] 测试写入 100 帧后 close，生成可播放的 MP4
- [ ] 测试目录不存在时自动创建
- [ ] 测试磁盘满时 write_frame 返回 False
- [ ] 测试 close 后文件可正常播放

## 验收标准
- [ ] 能正确编码为 MP4
- [ ] 文件可在常见播放器中播放
- [ ] 所有单元测试通过
