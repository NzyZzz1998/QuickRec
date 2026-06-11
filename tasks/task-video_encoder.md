# 任务：视频编码模块 (video_encoder.py)

**模块**：`src/recorder/video_encoder.py`
**说明**：将帧序列编码为 MP4 文件并写入磁盘。

## 前置依赖
- [x] 安装 opencv-python 包 (pip install opencv-python)

## 子任务

### 1. 实现 VideoEncoder 类
- [x] 定义 `VideoEncoder` 类
- [x] 实现 `__init__(file_path, fps, frame_size, bitrate)` 初始化
- [x] 实现 `write_frame(frame)` 写入一帧
- [x] 实现 `close()` 完成写入并关闭文件
- [x] 实现 `is_open()` 检查状态

### 2. 编码参数
- [x] 使用 OpenCV VideoWriter
- [x] fourcc: `mp4v`
- [x] 输入：BGR numpy ndarray
- [x] 输出：MP4 文件

### 3. 单元测试
- [x] 测试写入帧后 close，生成有效 MP4
- [x] 测试目录不存在时自动创建
- [x] 测试 close 后写入返回 False
- [x] 测试 close 后文件可被 OpenCV 读取

## 验收标准
- [x] 能正确编码为 MP4
- [x] 文件可在常见播放器中播放
- [x] 所有单元测试通过 (5/5)