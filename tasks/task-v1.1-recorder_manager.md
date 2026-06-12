# 任务：录制控制模块更新 (recorder_manager.py) — v1.1

**模块**：`src/recorder/recorder_manager.py`（更新）
**说明**：新增录制模式、音频集成、FFmpeg 混合。基于 v1.0 临时文件缓存方案扩展。

## 前置依赖
- [ ] audio_capturer 模块完成
- [ ] FFmpeg 可执行文件就位（ffmpeg/ffmpeg.exe 或系统 PATH）

## 子任务

### 1. RecordMode 枚举
- [x] 定义 `RecordMode` 枚举：FULLSCREEN / REGION
- [x] `start_fullscreen()` 设置 `self._mode = RecordMode.FULLSCREEN`
- [x] `start_region()` 设置 `self._mode = RecordMode.REGION`

### 2. 音频初始化（_start 方法扩展）
- [x] 在 `_start()` 中读取 config `audio_source`
- [x] 若 audio_source != NONE，创建 AudioCapturer 实例并调用 start()
- [x] start() 失败时 log 警告，设为 NONE 继续无声录制
- [x] 新增字段：_audio_capturer, _audio_source, _ffmpeg_path, _audio_temp_paths

### 3. 音频停止（_stop_and_encode 方法扩展）
- [x] 在录制线程 join 后、编码之前：调用 AudioCapturer.stop()
- [x] stop() 返回临时文件路径列表，保存到 _audio_temp_paths
- [x] 取消录制时：清理音频临时文件

### 4. 音频混合（_encode_loop 方法扩展）
- [x] 视频编码完成后，检查 _audio_temp_paths 是否有值且 _ffmpeg_path 是否可用
- [x] 有音频且有 FFmpeg：重命名视频为临时文件 → 调用 FFmpeg 混合 → 删除临时文件
- [x] 有音频但无 FFmpeg：log 警告，保留纯视频文件
- [x] 清理所有音频临时文件

### 5. FFmpeg 集成
- [x] 实现 `_get_ffmpeg_path()` 方法：搜索应用目录/ffmpeg/ → 系统 PATH → 返回空字符串
- [x] 实现 `_mix_audio_video()` 方法：subprocess 调用 FFmpeg 混合音视频
- [x] 单音频源：`-i video -i audio -c:v copy -c:a aac -shortest`
- [x] BOTH 模式：`-filter_complex "[1:a][2:a]amerge=inputs=2[a]" -map 0:v -map "[a]"`
- [x] FFmpeg 失败时降级：恢复纯视频文件，log 错误

### 6. 配置扩展
- [x] config.py 新增 `audio_source` 默认值 "none"

## 验收标准
- [ ] 全屏录制 + 系统声音：生成含音频的 MP4
- [ ] 全屏录制 + 无音频：与 v1.0 行为一致
- [ ] 音频初始化失败时：无声录制正常工作
- [ ] FFmpeg 不可用时：视频文件正常，log 警告
- [ ] BOTH 模式：系统声音和麦克风都混入视频