# QuickRec

Windows 屏幕录制工具，基于 Python 3.12 + PyQt5 + dxcam + OpenCV VideoWriter。

> 当前稳定版本：**v1.2**（master 分支）
> 开发中版本：v1.3（test 分支，含窗口录制恢复 + H.264 FFmpeg pipe 管线）

## 功能概览

| 版本 | 主要功能 |
|------|---------|
| v1.0 | 全屏录制、系统托盘、全局快捷键、QoS |
| v1.1 | 区域录制、音频源选择（系统声音/麦克风/两者）、Toast 通知、结果条、FFmpeg 音视频混合 |
| **v1.2** | 鼠标点击高亮、原生画质优化、开机自启、录制倒计时、设置对话框扩展 |

详细请见 `doc/PRD-QuickRec.md`。

## 录制模式

- **全屏录制** — 录制主显示器全部内容
- **区域录制** — 框选屏幕区域录制
- ~~**窗口录制**~~ — 延期至 v1.3（dxcam 资源管理、最大化窗口坐标、QMessageBox 托盘兼容性问题，详见 [bugfix-log.md](doc/bugfix-log.md) Bug #38-#41）

## 默认快捷键

| 功能 | 快捷键 |
|------|-------|
| 开始全屏录制 | `Ctrl + Shift + R` |
| 停止录制 | `Ctrl + Shift + S` |
| 暂停/恢复 | `Ctrl + Shift + P` |
| 区域录制 | `Ctrl + Shift + A` |

可在设置对话框点击录制修改。

## 依赖

- **Python**：CPython 3.12.8（不用 Anaconda）
- **截图**：dxcam 0.3.0（DirectX 快速捕获）
- **编码**：OpenCV `cv2.VideoWriter(mp4v)`（v1.2 方案，录制 JPEG 缓存到临时文件、停止后后台后编码；v1.3 改为 FFmpeg pipe H.264）
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
│   ├── ui/                   界面（toolbar/tray/area_selector/click_highlighter/...）
│   ├── hotkey/               全局快捷键
│   └── utils/                工具（disk_checker/file_namer/autostart）
├── ffmpeg/                   FFmpeg 可执行文件（音频混合用）
├── doc/                      文档（PRD / TecDesign / 测试用例 / bugfix-log）
├── tasks/                    v1.2 任务明细（已归档，v1.3 起用 progress.md）
├── tests/                    单元测试
├── build_std.spec            PyInstaller 打包配置
└── requirements.txt
```

## 开发运行

```bash
# 在项目根目录
D:\Work\Software\Python\python.exe src/main.py
```

## 打包

```bash
D:\Work\Software\Python\python.exe -m PyInstaller build_std.spec --noconfirm
```

输出在 `dist/QuickRec/`。

## 文档

- [PRD-QuickRec.md](doc/PRD-QuickRec.md) — 产品需求文档
- [Tec-design-v1.2.md](doc/Tec-design-v1.2.md) — v1.2 详细技术设计
- [v1.2-test-cases.md](doc/v1.2-test-cases.md) — v1.2 测试用例（97 项）
- [bugfix-log.md](doc/bugfix-log.md) — Bug 修复日志（Bug #1-#49）
- [tasks/](tasks/) — v1.2 任务明细文档
- [dev-plan-v1.2.md](doc/dev-plan-v1.2.md) — v1.2 开发计划

## 技术亮点

- **稳定 60fps**：dxcam + `timeBeginPeriod(1)` 提升定时器精度；JPEG 缓存 + 后编码降低录制循环耗时到 ~7ms/帧
- **线程安全**：所有跨线程回调（pynput/pystray/编码线程）通过 `pyqtSignal` 信号桥转发到 Qt 主线程
- **音视频混合**：v1.1 引入 soundcard WASAPI loopback + FFmpeg 后混合（`-c:v copy -c:a aac`）
- **Win32 互操作**：ctypes EnumWindows 窗口枚举、winreg 开机自启、GetSystemMetrics 原生分辨率

## 环境依赖重要说明

**必须用 CPython（标准 Python 3.12.8）**，不要用 Anaconda 的 Python，否则 dxcam / pyaudio 等原生扩展可能不兼容。

## 仓库与分支

- 远程：`git@github.com:NzyZzz1998/QuickRec.git`
- 分支：`master`（v1.2 稳定）、`test`（v1.3 开发）
- tag：`v1.1`、`v1.2` 已发布

## 许可

仅个人学习用途。