# QuickRec

Windows 屏幕录制工具，基于 Python 3.12 + PyQt5 + dxcam + FFmpeg。

## 功能概览

| 版本 | 主要功能 |
|------|---------|
| v1.0 | 全屏录制（H.264/FFmpeg pipe）、系统托盘、全局快捷键、QoS |
| v1.1 | 区域录制、音频源选择（系统声音/麦克风/两者）、Toast 通知、结果条 |
| v1.2 | 鼠标点击高亮、原生画质优化、开机自启、录制倒计时、设置对话框扩展 |
| v1.3 | 指定窗口录制（深度重写）、H.264 实时编码（零拷贝管线）、打包体积优化（334→259MB）、DPI 缩放、磁盘空间预警、临时文件三层清理 |

详细版本说明见 `doc/PRD-QuickRec.md`。

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

## 依赖

- **Python**：CPython 3.12.8（不用 Anaconda）
- **截图**：dxcam 0.3.0（DirectX 快速捕获）
- **编码**：FFmpeg 8.0.1（libx264 CRF=23 preset=superfast + tune=zerolatency，pipe stdin）
- **UI**：PyQt5 5.15
- **音频**：soundcard（系统声音 WASAPI loopback）、pyaudio（麦克风）
- **托盘**：pystray
- **快捷键**：pynput（无需管理员权限）
- **通知**：winotify（Windows 10/11 Toast）

完整依赖见 `requirements.txt`。

## 目录结构

```
QuickRec_dev/
├── src/                      源码
│   ├── main.py               主程序入口
│   ├── config.py             配置管理
│   ├── recorder/             录制引擎（capturer/encoder/manager/audio）
│   ├── ui/                   界面（toolbar/tray/area_selector/window_*/click_*）
│   ├── hotkey/               全局快捷键
│   └── utils/                工具（disk_checker/temp_cleaner/file_namer/autostart）
├── ffmpeg/                   FFmpeg 可执行文件
├── doc/                      文档（PRD / TecDesign / 测试用例 / bugfix-log / progress / dev-plan）
├── tests/                    单元测试（test_v1_3.py 等）
├── build_std.spec            PyInstaller 打包配置
└── requirements.txt
```

## 开发运行

```bash
# 在项目根目录 E:\CC_Learning\QuickRec_dev
D:\Work\Software\Python\python.exe src/main.py
```

## 打包

```bash
D:\Work\Software\Python\python.exe -m PyInstaller build_std.spec --clean --noconfirm
```

输出在 `dist/QuickRec/`，体积约 259MB（含 FFmpeg 97MB + cv2 73MB + numpy 27MB + Qt 18MB，核心依赖不可进一步压缩）。

## 单元测试

```bash
D:\Work\Software\Python\python.exe -m pytest tests/test_v1_3.py -v
```

v1.3 单元测试 21 用例 / 21 通过 / 2 跳过。覆盖 VideoEncoder、TempCleaner、DiskChecker、RecorderManager 窗口方法、Config 向后兼容、WindowHighlighter。

## 文档

- [PRD-QuickRec.md](doc/PRD-QuickRec.md) — 产品需求文档
- [Tec-design-v1.3.md](doc/Tec-design-v1.3.md) — v1.3 详细技术设计
- [v1.3-test-cases.md](doc/v1.3-test-cases.md) — v1.3 测试用例（88 项）
- [bugfix-log.md](doc/bugfix-log.md) — Bug 修复日志（Bug #1-#58）
- [progress.md](doc/progress.md) — 开发进度总览
- [dev-plan-v1.3.md](doc/dev-plan-v1.3.md) — v1.3 开发计划

## 技术亮点

- **零拷贝 H.264 管线**：dxcam BGR24 帧 → subprocess stdin pipe → FFmpeg libx264 实时编码 → MP4，无需 JPEG 临时文件后编码；`stderr=DEVNULL` 规避 pipe 缓冲满死锁
- **稳定 60fps**：dxcam + `timeBeginPeriod(1)` 提升定时器精度
- **会话目录隔离**：`%TEMP%/QuickRec/session_<pid>_<ts>/` 三层清理（正常退出/atexit/启动扫描）
- **线程安全**：所有跨线程回调（pynput/pystray/编码线程）通过 `pyqtSignal` 信号桥转发到 Qt 主线程
- **DPI 适配**：`AA_EnableHighDpiScaling` + `AA_UseHighDpiPixmaps`

## 环境依赖重要说明

**必须用 CPython（标准 Python 3.12.8）**，不要用 Anaconda 的 Python，否则 dxcam / pyaudio 等原生扩展可能不兼容。

## 仓库与分支

- 远程：`git@github.com:NzyZzz1998/QuickRec.git`
- 分支：`master`（v1.2 稳定）、`test`（v1.3 开发）
- tag：`v1.1`、`v1.2` 已发布

## 许可

仅个人学习用途。