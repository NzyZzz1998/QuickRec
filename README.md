# QuickRec Lite

QuickRec Lite 是从 QuickRec v1.4 稳定基线拆分出的轻量级桌面录屏工具，基于 Python 3.12、PyQt5、dxcam 和 FFmpeg 构建。

> 当前版本：QuickRec Lite v0  
> 当前分支：`lite-test`  
> 发布候选：`dist/QuickRec/QuickRec.exe`  
> 发布策略：Lite v0 优先保证全屏录制、音频和打包稳定；体积目标低于 200MB，但不作为发布阻断项。

## 功能概览

| 版本 | 状态 | 主要内容 |
| --- | --- | --- |
| v1.0 | 已完成 | 全屏录制、系统托盘、全局快捷键、QoS |
| v1.1 | 已完成 | 区域录制、音频源选择、Toast 通知、结果条 |
| v1.2 | 已完成 | 鼠标点击高亮、原生画质优化、开机自启、录制倒计时 |
| v1.3 | 已完成 | 指定窗口录制、H.264 实时编码、打包体积优化、DPI 缩放、磁盘空间预警、临时文件清理 |
| v1.4 | 已完成 / 待发布 | 稳定性与工程化大型优化：测试基线、CI/Lint/mypy、录制状态机与事件流、窗口移动稳定化、音频自检与降级、本地硬件冒烟、体积分析、Lite/Full 规划 |
| Lite v0 | 已完成 / 待发布 | 独立轻量分支：仅保留全屏录制，固定原生分辨率和 60fps，保留四种音频模式，移除区域/窗口录制、倒计时和鼠标高亮入口 |

详细需求见 [doc/PRD-QuickRec.md](doc/PRD-QuickRec.md)。

## Lite v0 录制模式

- **全屏录制**：Lite v0 唯一用户可见录制模式，录制主显示器全部内容。
- **固定输出**：原生分辨率 + 60fps。
- **音频模式**：保留无声、系统声音、麦克风、系统声音 + 麦克风。
- **不包含**：区域录制、窗口录制、录制倒计时、鼠标点击高亮。

## 默认快捷键

| 功能 | 快捷键 |
| --- | --- |
| 开始全屏录制 | `Ctrl + Shift + R` |
| 停止录制 | `Ctrl + Shift + S` |
| 暂停/恢复 | `Ctrl + Shift + P` |

Lite v0 只保留开始、停止、暂停/恢复三组快捷键设置。若本机已有旧配置，会继续读取用户自定义的三组快捷键；区域/窗口快捷键不再注册。

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

Lite v0 稳定包体积为 `257.89MB`。主要体积来源是 FFmpeg、OpenCV/cv2、PyQt5、NumPy 和 Python runtime。Lite v0 的体积目标为低于 `200MB`，但不作为发布阻断项；当前版本优先保证 dxcam/cv2 捕获链路和内置 FFmpeg 稳定可用。

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

## Lite v0 验证状态

- 全量测试：`231 passed, 23 deselected, 18 subtests passed`
- `ruff check .`：通过
- `mypy`：通过
- `compileall src scripts tests`：通过
- 本地硬件冒烟：通过，输出 `E:\QRtest\QuickRec_20260708_133603.mp4`
- 设置窗口 Computer Use 验证：通过
- 全屏录制手动流程：通过
- 四种音频模式：通过
- PyInstaller 打包：通过
- 打包产物启动和录制：通过，输出 `E:\QRtest\QuickRec_20260708_152150.mp4`

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
| [doc/lite/PRD-QuickRec-Lite.md](doc/lite/PRD-QuickRec-Lite.md) | Lite v0 PRD |
| [doc/lite/implementation-plan-lite.md](doc/lite/implementation-plan-lite.md) | Lite v0 实施计划 |
| [doc/lite/progress.md](doc/lite/progress.md) | Lite v0 总体进度 |
| [doc/lite/lite-v0-test-cases.md](doc/lite/lite-v0-test-cases.md) | Lite v0 测试用例 |
| [doc/lite/lite-v0-package-size-report.md](doc/lite/lite-v0-package-size-report.md) | Lite v0 打包体积报告 |
| [doc/lite/release-notes-lite-v0.md](doc/lite/release-notes-lite-v0.md) | Lite v0 发布说明 |
| [doc/bugfix-log.md](doc/bugfix-log.md) | Bug 修复日志 |

## 当前限制

1. 打包体积仍偏大，Lite v0 以稳定性优先，保留 cv2 和原始 FFmpeg。
2. 当前仅支持主显示器全屏录制。
3. 区域录制和窗口录制在 Lite v0 中没有用户入口。
4. 录制倒计时和鼠标点击高亮在 Lite v0 中没有用户入口。
5. 编码参数固定，暂未暴露高级设置。
6. CI 无法覆盖真实桌面录制，发布前需要本地硬件验收。

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
- Full 正式发布分支：`master`
- Lite 开发分支：`lite-test`
- Lite 稳定分支：`lite-master`
- Lite tag：`lite-v0`（发布收口后创建）

## 许可

仅个人学习用途。
