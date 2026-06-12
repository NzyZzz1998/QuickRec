# 任务：FFmpeg 打包配置 (build_std.spec + _get_ffmpeg_path) — v1.1

**模块**：`build_std.spec`（更新）+ `src/recorder/recorder_manager.py` 中的 `_get_ffmpeg_path()`
**说明**：FFmpeg 二进制文件打包和应用内定位。v1.1 新增依赖。

## 前置依赖
- [ ] FFmpeg 可执行文件就位（ffmpeg/ffmpeg.exe）
- [x] recorder_manager.py FFmpeg 混合逻辑完成

## 子任务

### 1. FFmpeg 文件准备
- [ ] 下载 FFmpeg Windows 静态编译版（ffmpeg-release-essentials.zip）
- [ ] 解压 `ffmpeg.exe` 到项目根目录 `ffmpeg/ffmpeg.exe`
- [ ] 验证 `ffmpeg/ffmpeg.exe -version` 可正常运行
- [x] 将 `ffmpeg/` 目录添加到 `.gitignore`（二进制不提交 git）

### 2. build_std.spec 更新
- [x] 在 `hiddenimports` 列表中添加 `recorder.audio_capturer` 和 `winotify`
- [ ] 验证打包后 `dist/QuickRec/ffmpeg/ffmpeg.exe` 存在且可运行（需要先下载 FFmpeg）
- [ ] 打包体积增量确认在预期范围内（~15MB）

### 3. _get_ffmpeg_path() 实现
- [x] 搜索顺序 1：`os.path.dirname(sys.executable)` + `/ffmpeg/ffmpeg.exe`（PyInstaller 打包后）
- [x] 搜索顺序 2：项目根目录 `ffmpeg/ffmpeg.exe`（开发环境）
- [x] 搜索顺序 3：`shutil.which("ffmpeg")`（系统 PATH）
- [x] 以上均未找到 → 返回空字符串，录音为无声模式
- [x] 使用 `getattr(sys, 'frozen', False)` 判断是否打包环境

### 4. 降级处理
- [x] `_get_ffmpeg_path()` 返回空字符串时，`_start()` 方法跳过音频捕获初始化
- [x] log 警告："FFmpeg 不可用，音频混合功能不可用"
- [x] 录制继续以纯视频模式工作

## 验收标准
- [ ] 开发环境：`_get_ffmpeg_path()` 找到 `ffmpeg/ffmpeg.exe` 或系统 PATH 中的 ffmpeg
- [ ] 打包后：`_get_ffmpeg_path()` 找到 `dist/QuickRec/ffmpeg/ffmpeg.exe`
- [x] 无 FFmpeg 时：录制正常进行（纯视频），log 警告
- [ ] 打包体积增加约 15MB（仅 ffmpeg.exe）
- [x] `.gitignore` 包含 `ffmpeg/` 目录