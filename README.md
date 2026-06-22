# QuickRec

Windows 屏幕录制工具，基于 Python 3.12 + PyQt5 + dxcam + FFmpeg。

> 当前开发版本：**v1.3**（test 分支）
> 稳定版本：v1.2（master 分支）

## 功能概览

| 版本 | 状态 | 主要功能 |
|------|------|---------|
| v1.0 | ✅ | 全屏录制、系统托盘、全局快捷键、QoS |
| v1.1 | ✅ | 区域录制、音频源选择（系统声音/麦克风/两者）、Toast 通知、结果条 |
| v1.2 | ✅ | 鼠标点击高亮、原生画质优化、开机自启、录制倒计时 |
| **v1.3** | ✅ 已开发 | 指定窗口录制（深度重写）、H.264 实时编码（零拷贝管线）、打包体积优化（334→259MB）、DPI 缩放、磁盘空间预警、临时文件三层清理 |

详细版本说明见 [doc/PRD-QuickRec.md](doc/PRD-QuickRec.md)。

## 录制模式

- **全屏录制** — 录制主显示器全部内容
- **区域录制** — 框选屏幕区域录制
- **窗口录制**（v1.3 恢复）— 选择任意可见窗口，跟随移动；最小化暂停、关闭自停保存

## 默认快捷键

| 功能 | 快捷键 |
|------|-------|
| 开始全屏录制 | `Ctrl + Shift + R` |
| 停止录制 | `Ctrl + Shift + S` |
| 暂停/恢复 | `Ctrl + Shift + P` |
| 区域录制 | `Ctrl + Shift + A` |
| 窗口录制 | `Ctrl + Shift + W` |

可在设置对话框自定义；约一键组合可修改，单键不可。

## 环境需求

| 组件 | 要求 |
|------|-----|
| 操作系统 | Windows 10 / 11（64 位） |
| Python | **CPython 3.12.8**（不要用 Anaconda，否则 dxcam/pyaudio 原生扩展不兼容） |
| 截图 | dxcam 0.3.0（DirectX 快速捕获）+ comtypes |
| 编码 | FFmpeg 8.0.1（libx264 CRF=23 preset=superfast + tune=zerolatency，pipe stdin；`stderr=DEVNULL` 防死锁） |
| UI | PyQt5 5.15 |
| 音频 | soundcard（系统声音 WASAPI loopback）、pyaudio（麦克风） |
| 托盘 | pystray |
| 快捷键 | pynput（无需管理员权限） |
| 通知 | winotify（Windows 10/11 Toast） |
| 打包 | PyInstaller 6.20+ |

完整依赖版本见 [requirements.txt](requirements.txt)。

## 项目目录结构

```
QuickRec/
├── src/                      源码
│   ├── main.py               主程序入口
│   ├── config.py             配置管理
│   ├── recorder/             录制引擎（screen_capturer/video_encoder/recorder_manager/audio_capturer）
│   ├── ui/                   界面（toolbar/tray_icon/area_selector/window_selector/window_highlighter/click_highlighter）
│   ├── hotkey/               全局快捷键
│   └── utils/                工具（disk_checker/temp_cleaner/file_namer/autostart）
├── ffmpeg/                   FFmpeg 可执行文件（音视频混合用，不纳入 git）
├── doc/                      文档（PRD / TecDesign / 测试用例 / bugfix-log / progress / dev-plan）
├── tests/                    单元测试（test_v1_3.py 等）
├── build_std.spec            PyInstaller 打包配置
└── requirements.txt
```

## 安装与运行

### 1. 克隆仓库

```bash
git clone git@github.com:NzyZzz1998/QuickRec.git
cd QuickRec
git checkout test   # v1.3 开发版
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
python -m PyInstaller build_std.spec --clean --noconfirm
```

输出在 `dist/QuickRec/`，体积约 259MB（含 FFmpeg 97MB + cv2 73MB + numpy 27MB + Qt 18MB，核心依赖不可进一步压缩），运行 `dist/QuickRec/QuickRec.exe`。

## 单元测试

```bash
python -m pytest tests/test_v1_3.py -v
```

v1.3 单元测试 21 用例 / 21 通过 / 2 跳过。覆盖 VideoEncoder、TempCleaner、DiskChecker、RecorderManager 窗口方法、Config 向后兼容、WindowHighlighter。

## 文档

| 文档 | 说明 |
|------|-----|
| [doc/PRD-QuickRec.md](doc/PRD-QuickRec.md) | 产品需求文档 |
| [doc/Tec-design-v1.3.md](doc/Tec-design-v1.3.md) | v1.3 详细技术设计 |
| [doc/v1.3-test-cases.md](doc/v1.3-test-cases.md) | v1.3 测试用例（88 项） |
| [doc/bugfix-log.md](doc/bugfix-log.md) | Bug 修复日志（Bug #1-#58） |
| [doc/progress.md](doc/progress.md) | 开发进度总览 |
| [doc/dev-plan-v1.3.md](doc/dev-plan-v1.3.md) | v1.3 开发计划 |

## 技术亮点

- **零拷贝 H.264 管线**：dxcam BGR24 帧 → subprocess stdin pipe → FFmpeg libx264 实时编码 → MP4，无需 JPEG 临时文件后编码；`stderr=DEVNULL` 规避 pipe 缓冲满死锁（Bug #58）
- **稳定 60fps**：dxcam + `timeBeginPeriod(1)` 提升定时器精度
- **会话目录隔离**：`%TEMP%/QuickRec/session_<pid>_<ts>/` 三层清理（正常退出/atexit/启动扫描）
- **线程安全**：所有跨线程回调（pynput/pystray/编码线程）通过 `pyqtSignal` 信号桥转发到 Qt 主线程
- **DPI 适配**：`AA_EnableHighDpiScaling` + `AA_UseHighDpiPixmaps`
- **窗口录制稳化**：主线程异步化置前台 + Alt 键绕过 Windows 前台锁；minimized 同步暂停等用户点"继续"

## 当前版本主要缺陷 / 不足

1. **打包体积仍偏大** — 259MB 未达 150MB 目标，核心依赖（cv2 73MB + ffmpeg 97MB + numpy 27MB + Qt 18MB ≈ 215MB）不可进一步压缩
2. **窗口移动跟随有延迟** — dxcam 在 region 变化时需 stop/release + create/start 重建 camera，100ms 更新间隔下移动窗口仍有可见延迟
3. **特殊窗口录制不一定可用** — 部分游戏全屏/UWP/DWM 自定义渲染窗口客户区不可枚举，`_get_window_rect` 返回 None 启动失败（友好提示但不支持）
4. **磁盘预警只检查一次** — 仅录制前检查磁盘空间，录制过程中磁盘写满不会被中断
5. **仅支持单显示器** — 录制始终绑定主显示器，无法选择次显示器
6. **编码参数固定** — CRF=23 + preset=superfast + tune=zerolatency 内部固定，不暴露给高级用户
7. **音频回退路径脆弱** — soundcard WASAPI loopback 在边缘设备可能仍有兼容性问题
8. **打包后功能部分待手工验证** — T11.3-T11.6 打包后全屏/窗口/托盘菜单/设置对话框功能留待手工回归

## 未来迭代规划

**v1.4 微迭代**：`coming soon...`
- 🔲 窗口移动跟随延迟优化（评估用 Windows Graphics Capture API 替代 dxcam 区域更新，或采用双缓冲 camera 切换）
- 🔲 特殊窗口录制兼容性（Windows Graphics Capture 支持游戏全屏/UWP/DWM 窗口）
- 🔲 录制中磁盘写满持续监控 + 中断保存
- 🔲 编码参数（CRF / preset）暴露给高级用户设置
- 🔲 打包体积：尝试 opencv-python-headless + 移除 ffmpeg 内置版本，目标 < 200MB

**v2.0 功能扩展**：`coming soon...`
- 🔲 多显示器录制选择
- 🔲 录制历史管理窗口（列出最近录制、一键打开/删除/再编辑）
- 🔲 鼠标按键事件丰富化（点击位置轨迹、按键计数、滚轮事件高亮）
- 🔲 录制计划任务（定时开始/停止录制）
- 🔲 视频简单剪辑（裁剪首尾、片段拼接）
- 🔲 macOS / Linux 跨平台支持评估

## 仓库与分支

- 远程：`git@github.com:NzyZzz1998/QuickRec.git`
- 分支：`master`（v1.2 稳定）、`test`（v1.3 开发）
- tag：`v1.1`、`v1.2` 已发布；`v1.3` 待发布

## 许可

仅个人学习用途。