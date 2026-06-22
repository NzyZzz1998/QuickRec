# QuickRec

Windows 屏幕录制工具，基于 Python 3.12 + PyQt5 + dxcam + OpenCV VideoWriter。

> 当前稳定版本：**v1.2**（master 分支）
> 开发中版本：v1.3（test 分支，含窗口录制恢复 + H.264 FFmpeg pipe 管线）

## 功能概览

| 版本 | 状态 | 主要功能 |
|------|------|---------|
| v1.0 | ✅ | 全屏录制、系统托盘、全局快捷键、QoS |
| v1.1 | ✅ | 区域录制、音频源选择（系统声音/麦克风/两者）、Toast 通知、结果条、FFmpeg 音视频混合 |
| **v1.2** | ✅ 稳定 | 鼠标点击高亮、原生画质优化、开机自启、录制倒计时、设置对话框扩展 |

详细版本说明见 [doc/PRD-QuickRec.md](doc/PRD-QuickRec.md)。

## 录制模式

- **全屏录制** — 录制主显示器全部内容
- **区域录制** — 框选屏幕区域录制
- ~~**窗口录制**~~ — v1.2 延期，v1.3 重新实现（见下文"未来迭代规划"）

## 默认快捷键

| 功能 | 快捷键 |
|------|-------|
| 开始全屏录制 | `Ctrl + Shift + R` |
| 停止录制 | `Ctrl + Shift + S` |
| 暂停/恢复 | `Ctrl + Shift + P` |
| 区域录制 | `Ctrl + Shift + A` |

可在设置对话框点击录制修改。

## 环境需求

| 组件 | 要求 |
|------|-----|
| 操作系统 | Windows 10 / 11（64 位） |
| Python | **CPython 3.12.8**（不要用 Anaconda，否则 dxcam/pyaudio 原生扩展不兼容） |
| 截图 | dxcam 0.3.0（DirectX 快速捕获）+ comtypes |
| 编码 | OpenCV `cv2.VideoWriter(mp4v)`（v1.2 方案，JPEG 缓存 + 后编码） |
| UI | PyQt5 5.15 |
| 音频 | soundcard（系统声音 WASAPI loopback）、pyaudio（麦克风） |
| 托盘 | pystray |
| 快捷键 | pynput（无需管理员权限） |
| 通知 | winotify（Windows 10/11 Toast） |
| 打包 | PyInstaller 6.20+ |
| FFmpeg | 8.0.1（用于音视频混合，运行时随包打包） |

完整依赖版本见 [requirements.txt](requirements.txt)。

## 项目目录结构

```
QuickRec/
├── src/                      源码
│   ├── main.py               主程序入口
│   ├── config.py             配置管理
│   ├── recorder/             录制引擎（screen_capturer/video_encoder/recorder_manager/audio_capturer）
│   ├── ui/                   界面（toolbar/tray_icon/area_selector/click_highlighter/...）
│   ├── hotkey/               全局快捷键
│   └── utils/                工具（disk_checker/file_namer/autostart）
├── ffmpeg/                   FFmpeg 可执行文件（音频混合用，不纳入 git）
├── doc/                      文档（PRD / TecDesign / 测试用例 / bugfix-log / progress / dev-plan）
├── tasks/                    v1.2 任务明细归档
├── tests/                    单元测试
├── build_std.spec            PyInstaller 打包配置
└── requirements.txt
```

## 安装与运行

### 1. 克隆仓库

```bash
git clone git@github.com:NzyZzz1998/QuickRec.git
cd QuickRec
git checkout master   # v1.2 稳定版
```

### 2. 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 3. 开发运行

```bash
python src/main.py
```

### 4. 打包

```bash
python -m PyInstaller build_std.spec --noconfirm
```

输出在 `dist/QuickRec/`，运行 `dist/QuickRec/QuickRec.exe`。

## 单元测试

```bash
python -m pytest tests/ -v
```

v1.0-v1.2 共 60+ 用例，覆盖 config / file_namer / disk_checker / screen_capturer / video_encoder / recorder_manager / area_selector / toolbar / settings_dialog / tray_icon / hotkey_manager。

## 文档

| 文档 | 说明 |
|------|-----|
| [doc/PRD-QuickRec.md](doc/PRD-QuickRec.md) | 产品需求文档 |
| [doc/Tec-design-v1.2.md](doc/Tec-design-v1.2.md) | v1.2 详细技术设计 |
| [doc/v1.2-test-cases.md](doc/v1.2-test-cases.md) | v1.2 测试用例（97 项） |
| [doc/bugfix-log.md](doc/bugfix-log.md) | Bug 修复日志（Bug #1-#49） |
| [doc/progress.md](doc/progress.md) | 开发进度总览 |
| [doc/dev-plan-v1.2.md](doc/dev-plan-v1.2.md) | v1.2 开发计划 |
| [tasks/](tasks/) | v1.2 任务明细文档归档 |

## 技术亮点

- **稳定 60fps**：dxcam + `timeBeginPeriod(1)` 提升定时器精度；JPEG 缓存 + 后编码降低录制循环耗时到 ~7ms/帧
- **线程安全**：所有跨线程回调（pynput/pystray/编码线程）通过 `pyqtSignal` 信号桥转发到 Qt 主线程
- **音视频混合**：soundcard WASAPI loopback + FFmpeg 后混合（`-c:v copy -c:a aac`）
- **Win32 互操作**：ctypes EnumWindows 窗口枚举、winreg 开机自启、GetSystemMetrics 原生分辨率
- **三种录制画质**：原生(2K)/高(1080p)/中(720p)/低(480p)，区域录制保宽高比

## 当前版本主要缺陷 / 不足

1. **窗口录制功能延期** — v1.2 因 dxcam 资源释放、最大化窗口 GetWindowRect 负坐标、QMessageBox 在托盘应用不显示等问题无法稳定，整体延期（详见 [doc/bugfix-log.md](doc/bugfix-log.md) Bug #29-#41）。代码注释保留未删除，v1.3 重新实现
2. **编码格式为 mp4v** — v1.2 使用 OpenCV `VideoWriter(mp4v)`，画质与压缩率不如 H.264，文件体积偏大
3. **无 DPI 缩放适配** — 4K / 150% 缩放下 UI 元素可能错位
4. **无磁盘空间预警** — 磁盘空间不足时录制会静默失败，无提前提醒
5. **临时文件无清理机制** — 异常崩溃后 JPEG 临时文件可能残留
6. **打包体积偏大** — v1.2 打包后约 334MB（OpenCV、Qt、FFmpeg 整体打入）
7. **仅支持单显示器** — 录制始终绑定主显示器，无法选择次显示器
8. **音频回退路径脆弱** — pyaudiowpatch 在部分声卡上 stream.read 永久阻塞，已切到 soundcard 但仍有边缘设备问题

## 未来迭代规划

**v1.3**（已开发，在 test 分支）：`coming soon...`
- ✅ 窗口录制深度重写（Alt 键前台锁绕过、主线程异步化、同步暂停最小化）
- ✅ H.264 实时编码（FFmpeg pipe 零拷贝管线，libx264 CRF=23 preset=superfast + tune=zerolatency）
- ✅ 打包体积优化（334→259MB，排除不必要 Qt 模块/DLL/PIL 编解码器）
- ✅ DPI 缩放适配
- ✅ 磁盘空间预警（< 1GB 提醒 / < 200MB 阻断）
- ✅ 临时文件三层清理（session 隔离 + atexit + 启动扫描）

**v2.0 及以后**：`coming soon...`
- 🔲 多显示器录制选择
- 🔲 录制历史管理窗口
- 🔲 编码参数可配置（CRF / preset 暴露给高级用户）
- 🔲 鼠标按键事件丰富化（点击位置轨迹、按键计数）
- 🔲 录制计划任务
- 🔲 macOS / Linux 跨平台支持评估

## 仓库与分支

- 远程：`git@github.com:NzyZzz1998/QuickRec.git`
- 分支：`master`（v1.2 稳定）、`test`（v1.3 开发）
- tag：`v1.1`、`v1.2` 已发布

## 许可

仅个人学习用途。