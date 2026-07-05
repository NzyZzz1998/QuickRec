# QuickRec

QuickRec 是一款面向 Windows 的轻量级桌面录屏工具，基于 Python 3.12、PyQt5、dxcam 和 FFmpeg 构建。

> 当前版本：v1.4
> 发布候选：稳定版 `dist/QuickRec/QuickRec.exe`
> 发布策略：稳定性优先，UPX FFmpeg 体积实验暂不进入 v1.4 正式发布。

## 功能概览

| 版本 | 状态 | 主要内容 |
| --- | --- | --- |
| v1.0 | 已完成 | 全屏录制、系统托盘、全局快捷键、QoS |
| v1.1 | 已完成 | 区域录制、音频源选择、Toast 通知、结果条 |
| v1.2 | 已完成 | 鼠标点击高亮、原生画质优化、开机自启、录制倒计时 |
| v1.3 | 已完成 | 指定窗口录制、H.264 实时编码、打包体积优化、DPI 缩放、磁盘空间预警、临时文件清理 |
| v1.4 | 已完成 / 待发布 | 稳定性与工程化大型优化：测试基线、CI/Lint/mypy、录制状态机与事件流、窗口移动稳定化、音频自检与降级、本地硬件冒烟、体积分析、Lite/Full 规划 |

详细需求见 [doc/PRD-QuickRec.md](doc/PRD-QuickRec.md)。

## 录制模式

- **全屏录制**：录制主显示器全部内容，保留当前鼠标叠加方案。
- **区域录制**：框选屏幕区域录制，保留当前鼠标叠加方案。
- **窗口录制**：选择可见窗口录制；移动窗口时保持最后稳定帧，停止移动后继续更新；最小化暂停，关闭自动停止保存。v1.4 中窗口录制暂不叠加鼠标，避免后期贴图导致比例异常和大鼠标闪现。

## 默认快捷键

| 功能 | 快捷键 |
| --- | --- |
| 开始全屏录制 | `Ctrl + Shift + R` |
| 停止录制 | `Ctrl + Shift + S` |
| 暂停/恢复 | `Ctrl + Shift + P` |
| 区域录制 | `Ctrl + Shift + A` |
| 窗口录制 | `Ctrl + Shift + W` |

快捷键可在设置对话框中修改。

## 环境要求

| 组件 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 / 11 64 位 |
| Python | CPython 3.12.8 |
| 截图 | dxcam 0.3.0 + comtypes；dxcam 默认依赖 cv2 processor，因此 v1.4 保留 OpenCV |
| 编码 | FFmpeg 8.0.1，libx264 CRF=23，preset=superfast，tune=zerolatency |
| UI | PyQt5 5.15 |
| 图像处理 | OpenCV、Pillow |
| 音频 | soundcard、pyaudio |
| 托盘 | pystray |
| 快捷键 | pynput |
| 通知 | winotify |
| 打包 | PyInstaller 6.20+ |

完整依赖见 [requirements.txt](requirements.txt) 和 [requirements-dev.txt](requirements-dev.txt)。

## 项目结构

```text
QuickRec/
├── .github/workflows/        GitHub Actions CI
├── src/                      源码
│   ├── main.py               主程序入口
│   ├── config.py             配置管理
│   ├── recorder/             录制、编码、音频、状态机、事件、工作流
│   ├── ui/                   托盘、工具栏、设置、区域选择、窗口选择、高亮
│   ├── hotkey/               全局快捷键
│   └── utils/                磁盘、文件命名、临时清理、自启、窗口几何
├── scripts/                  工程化脚本：硬件冒烟、FFmpeg 能力检查、体积报告
├── ffmpeg/                   FFmpeg 可执行文件，不纳入 git
├── doc/                      PRD / TecDesign / DevPlan / 测试用例 / 发布记录 / 原型
├── tests/                    自动化测试
├── build_std.spec            PyInstaller 打包配置
├── pyproject.toml            pytest / ruff / mypy / coverage 配置
├── requirements-dev.txt      开发测试依赖
└── requirements.txt          运行和打包依赖
```

## 安装与运行

```powershell
git clone https://github.com/NzyZzz1998/QuickRec.git
cd QuickRec
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python src/main.py
```

## 打包

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm
```

输出目录：

```text
dist/QuickRec/
```

v1.4 稳定包体积为 `257.89MB`。主要体积来源是 FFmpeg、OpenCV/cv2、PyQt5、NumPy 和 Python runtime。UPX FFmpeg 实验包可降至 `187.89MB`，但由于还需要区域/窗口/真实音频/杀软误报回归，v1.4 正式发布继续使用稳定包。

## 测试

默认自动化测试：

```powershell
python -m pytest -q
```

工程检查：

```powershell
python -m compileall src scripts tests
python -m ruff check .
python -m mypy
```

覆盖率：

```powershell
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80
```

本地硬件冒烟：

```powershell
python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen
```

硬件冒烟依赖真实 Windows 桌面、dxcam 和屏幕捕获环境，CI 默认不运行。

## v1.4 验证状态

- 全量测试：`230 passed, 23 deselected, 18 subtests passed`
- `ruff check .`：通过
- `mypy`：通过
- `compileall src scripts tests`：通过
- 稳定包启动冒烟：通过
- 本地硬件冒烟：通过，输出 `E:\QRtest\QuickRec_20260705_165730.mp4`

## 文档

| 文档 | 说明 |
| --- | --- |
| [doc/PRD-QuickRec.md](doc/PRD-QuickRec.md) | 产品需求文档 |
| [doc/Tec-design-v1.4.md](doc/Tec-design-v1.4.md) | v1.4 技术设计 |
| [doc/dev-plan-v1.4.md](doc/dev-plan-v1.4.md) | v1.4 开发计划 |
| [doc/progress.md](doc/progress.md) | 总体进度 |
| [doc/v1.4-test-cases.md](doc/v1.4-test-cases.md) | v1.4 测试用例与发布前验收 |
| [doc/v1.4-package-size-report.md](doc/v1.4-package-size-report.md) | v1.4 稳定包体积报告 |
| [doc/v1.4-package-size-report-upx.md](doc/v1.4-package-size-report-upx.md) | UPX FFmpeg 实验报告 |
| [doc/v1.4-capture-backend-research.md](doc/v1.4-capture-backend-research.md) | 捕获后端研究记录 |
| [doc/release-notes-v1.4.md](doc/release-notes-v1.4.md) | v1.4 发布说明 |
| [doc/bugfix-log.md](doc/bugfix-log.md) | Bug 修复日志 |

## 当前限制

1. 打包体积仍偏大，v1.4 以稳定性优先，保留 cv2 和原始 FFmpeg。
2. 窗口录制移动时采用冻结最后稳定帧的策略，不是真正实时跟随。
3. 窗口录制暂不录制鼠标，后续评估能原生捕获光标的捕获链路。
4. 游戏全屏、UWP、DWM 自定义渲染窗口可能不可录制，v1.4 只保证失败稳定、提示清晰、不崩溃。
5. 当前仅支持主显示器录制。
6. 编码参数固定，暂未暴露高级设置。
7. CI 无法覆盖真实桌面录制，发布前需要本地硬件验收。

## 后续规划

**Lite 方向**

- 长期保持轻量、低心智负担和较少依赖。
- 默认保留全屏录制；区域录制作为未来可选能力。
- 不规划窗口录制。
- 保留托盘 UI 和基础音频能力，隐藏复杂高级配置。

**Full 方向**

- 面向创作者工作台。
- 规划录制历史、项目素材管理、轻编辑、导出队列、质量诊断中心、模板与预设。
- 评估 Windows Graphics Capture 等能原生捕获光标的捕获链路。
- 继续优化体积，但不牺牲 dxcam/cv2 捕获稳定性。

## 仓库

- GitHub: https://github.com/NzyZzz1998/QuickRec
- v1.4 正式发布分支：以稳定包为准
- tag: `v1.4`

## 许可

仅个人学习用途。
