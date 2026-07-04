# QuickRec

Windows 屏幕录制工具，基于 Python 3.12 + PyQt5 + dxcam + FFmpeg。

> 当前版本：**v1.4**（test 分支）
> 稳定版本：v1.4

## 功能概览

| 版本 | 状态 | 主要功能 |
|------|------|---------|
| v1.0 | ✅ | 全屏录制、系统托盘、全局快捷键、QoS |
| v1.1 | ✅ | 区域录制、音频源选择（系统声音/麦克风/两者）、Toast 通知、结果条 |
| v1.2 | ✅ | 鼠标点击高亮、原生画质优化、开机自启、录制倒计时 |
| v1.3 | ✅ | 指定窗口录制、H.264 实时编码、打包体积优化、DPI 缩放、磁盘空间预警、临时文件三层清理 |
| **v1.4** | ✅ 已开发 | 稳定性与工程化大型优化：测试基线修复、CI/Lint/mypy、录制状态机与事件流、窗口移动稳化、区域录制鼠标指针、空音频混音防护、打包冒烟验证 |

详细版本说明见 [doc/PRD-QuickRec.md](doc/PRD-QuickRec.md)。

## 录制模式

- **全屏录制** — 录制主显示器全部内容
- **区域录制** — 框选屏幕区域录制，录制结果包含软件绘制鼠标指针
- **窗口录制** — 选择可见窗口录制；移动窗口时保持最后稳定帧，停止移动后继续更新；最小化暂停，关闭自停保存

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
| Python | **CPython 3.12.8**（不要用 Anaconda，否则 dxcam/pyaudio 原生扩展可能不兼容） |
| 截图 | dxcam 0.3.0 + comtypes；dxcam 默认 cv2 processor，因此需保留 OpenCV |
| 编码 | FFmpeg 8.0.1（libx264 CRF=23 preset=superfast + tune=zerolatency，pipe stdin；`stderr=DEVNULL` 防死锁） |
| UI | PyQt5 5.15 |
| 图像处理 | OpenCV（供 dxcam 内部颜色转换）、Pillow（轻量缩放和鼠标指针绘制） |
| 音频 | soundcard（系统声音 WASAPI loopback）、pyaudio（麦克风） |
| 托盘 | pystray |
| 快捷键 | pynput（无需管理员权限） |
| 通知 | winotify（Windows 10/11 Toast，失败时降级） |
| 打包 | PyInstaller 6.20+ |

完整依赖版本见 [requirements.txt](requirements.txt)。

## 项目目录结构

```
QuickRec/
├── .github/workflows/        GitHub Actions CI
├── src/                      源码
│   ├── main.py               主程序入口
│   ├── config.py             配置管理
│   ├── recorder/             录制引擎、状态机、事件、工作流、编码、音频、捕获
│   ├── ui/                   托盘、工具栏、设置、区域选择、窗口选择、窗口高亮、点击高亮
│   ├── hotkey/               全局快捷键
│   └── utils/                磁盘、文件命名、临时清理、自启、窗口几何
├── ffmpeg/                   FFmpeg 可执行文件（不纳入 git）
├── doc/                      PRD / TecDesign / DevPlan / 测试用例 / bugfix-log / progress / 原型
├── tests/                    自动化测试
├── build_std.spec            PyInstaller 打包配置
├── pyproject.toml            pytest / ruff / mypy / coverage 配置
├── requirements-dev.txt      开发测试依赖
└── requirements.txt          运行和打包依赖
```

## 安装与运行

### 1. 克隆仓库

```bash
git clone git@github.com:NzyZzz1998/QuickRec.git
cd QuickRec
git checkout test
```

### 2. 安装依赖

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

### 3. 开发运行

```bash
python src/main.py
```

### 4. 打包

```bash
python -m PyInstaller build_std.spec --clean --noconfirm
```

输出在 `dist/QuickRec/`，运行 `dist/QuickRec/QuickRec.exe`。

v1.4 当前打包体积约 `257.74MB`，主要由 FFmpeg、cv2、PyQt5、numpy 组成。`opencv_videoio_ffmpeg*.dll` 已排除，QuickRec 使用独立 `ffmpeg/ffmpeg.exe` 完成编码和混音。

## 测试

### 默认自动化测试

```bash
python -m pytest -q
```

当前基线：`175 passed, 23 deselected`。

### 工程检查

```bash
python -m compileall -q src tests
python -m ruff check .
python -m mypy
```

### 覆盖率

```bash
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80
```

### 打包配置测试

```bash
python -m pytest tests/test_packaging_config.py -m packaging -q
```

### 硬件/桌面测试

```bash
python -m pytest -m hardware -q
```

`hardware` 测试依赖真实 Windows 桌面、dxcam、音频设备和屏幕捕获环境，默认 CI 不运行。

## 文档

| 文档 | 说明 |
|------|-----|
| [doc/PRD-QuickRec.md](doc/PRD-QuickRec.md) | 产品需求文档 |
| [doc/Tec-design-v1.4.md](doc/Tec-design-v1.4.md) | v1.4 技术设计 |
| [doc/dev-plan-v1.4.md](doc/dev-plan-v1.4.md) | v1.4 开发计划 |
| [doc/v1.4-test-cases.md](doc/v1.4-test-cases.md) | v1.4 测试用例和发布前验收清单 |
| [doc/bugfix-log.md](doc/bugfix-log.md) | Bug 修复日志（截至 Bug #60） |
| [doc/progress.md](doc/progress.md) | 开发进度总览 |
| [doc/full-workbench-prototype/](doc/full-workbench-prototype/) | full 创作者工作台原型规划 |

## 技术亮点

- **H.264 实时编码**：dxcam BGR24 帧 → subprocess stdin pipe → FFmpeg libx264 → MP4，无需 JPEG 临时文件后编码。
- **FFmpeg 死锁防护**：编码进程 `stderr=DEVNULL`，避免 FFmpeg 进度日志填满 pipe 导致停止超时。
- **录制状态机**：抽出 `RecordingStateMachine`，覆盖 IDLE / RECORDING / PAUSED / STOPPING / SAVING 等状态转移。
- **录制事件流**：统一 saved / failed / state_changed 等事件，降低 UI 对底层私有字段的依赖。
- **工作流门面**：`RecordingWorkflow` 承接 start / pause / resume / stop 等操作，为后续 full/lite 分支拆分提供边界。
- **区域录制鼠标指针**：通过软件绘制指针解决区域录制中鼠标不可见的问题。
- **窗口移动稳化**：窗口移动时冻结最后稳定帧，避免 4K/高 DPI 下区域重建导致画面漂移。
- **空音频混音防护**：过滤只有 WAV header、无采样的音频文件，避免生成 261 字节损坏 MP4。
- **会话目录隔离**：`%TEMP%/QuickRec/session_<pid>_<ts>/`，支持正常退出、取消录制、启动扫描清理。
- **工程化基线**：pytest marker、coverage 门槛、ruff、mypy、GitHub Actions 均已接入。

## 当前版本主要缺陷 / 不足

1. **打包体积仍偏大** — v1.4 约 `257.74MB`，稳定性优先恢复 cv2；后续可评估更小 FFmpeg 构建或 opencv-python-headless。
2. **窗口移动仍非真正实时跟随** — 当前策略是移动时冻结画面，停止移动后恢复更新；这是 dxcam 区域重建限制下的稳定方案。
3. **特殊窗口兼容性有限** — 游戏全屏、UWP、DWM 自定义渲染窗口可能无法枚举客户区；v1.4 只保证失败稳定、提示清晰、不崩溃。
4. **仅支持主显示器** — 当前未提供多显示器选择。
5. **编码参数固定** — CRF=23、preset=superfast、tune=zerolatency 未暴露到设置。
6. **音频设备兼容性依赖本机环境** — soundcard WASAPI loopback 和 pyaudio 在边缘设备上仍需人工验收。
7. **CI 无法覆盖真实录制** — GitHub Actions 只覆盖纯逻辑和可模拟路径，真实 dxcam/音频/托盘仍依赖发布前手动验收。

## 后续规划

**lite 分支准备**
- 保留全屏录制、区域录制、基础托盘、基础快捷键、基础编码和保存。
- 评估移除窗口录制、混合音频、点击高亮、复杂通知和 full workbench 规划。
- 目标是更小体积、更少依赖、更简单验证路径。

**full 版本方向**
- 创作者工作台：历史录制管理、片段处理、素材/模板、批量导出等。
- 多显示器录制选择。
- Windows Graphics Capture 方案评估，改善窗口录制和特殊窗口兼容性。
- 编码参数开放给高级用户。
- 打包体积继续优化，但不牺牲 dxcam/cv2 捕获稳定性。

## 仓库与分支

- 远程：`https://github.com/NzyZzz1998/QuickRec.git`
- 分支：`master`（历史稳定）、`test`（v1.4 开发）
- tag：`v1.1`、`v1.2`、`v1.4`

## 许可

仅个人学习用途。
