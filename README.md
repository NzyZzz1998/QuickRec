# QuickRec Full

> 面向 Windows 的本地屏幕录制与素材管理工具。支持全屏、区域和窗口录制，
> 四类音频模式、中央素材库、诊断导出，以及正在 `test` 分支推进的统一工作台与
> 1080p120 录制能力。

[![正式版本](https://img.shields.io/badge/正式版本-v1.7-2563EB)](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.7)
![开发版本](https://img.shields.io/badge/test-v1.8%20开发中-F59E0B)
![平台](https://img.shields.io/badge/平台-Windows-111827)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![测试](https://img.shields.io/badge/tests-519%20passed-16A34A)
![coverage](https://img.shields.io/badge/coverage-86.07%25-16A34A)

## 版本状态

| 产品线 | 状态 | 分支 / 标签 | 说明 |
| --- | --- | --- | --- |
| QuickRec Full v1.7 | **当前正式版** | `master` / `v1.7` | 素材搜索、筛选与排序已经发布 |
| QuickRec Full v1.8 | **开发候选** | `test` | 工作台、视觉改版和 1080p120 已实现，D11 验收完成 `20/24` |
| QuickRec Lite | 独立维护 | `E:\codex\QuickRec-Lite` | 轻量产品线，不属于本工作区 |

v1.8 尚未替换正式版本。当前剩余验收集中在真实麦克风、双音频和 10 分钟音画同步，
通过后才会进入发布收口。

- [下载 QuickRec Full v1.7](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.7)
- [查看当前事实入口](doc/current.md)
- [查看 v1.8 进度](doc/releases/v1.8/progress.md)
- [查看 v1.8 验收记录](doc/releases/v1.8/manual-verification.md)

## 产品界面

下图来自当前实际素材库界面。v1.8 将录制、素材库、设置和诊断统一并入工作台，
素材库不再作为独立用户窗口。

![QuickRec 素材库实际界面](doc/releases/v1.8/prototype/reference/material-library-current.png)

v1.8 高保真交互原型与逐页面实现核对：

- [工作台交互原型](doc/releases/v1.8/prototype/index.html)
- [原型与组件规范](doc/releases/v1.8/prototype/prototype-design.md)
- [实际实现视觉核对](doc/releases/v1.8/visual-verification.md)

## 核心能力

### 录制

- 全屏、区域和窗口三种录制模式。
- 无声、系统声音、麦克风、系统声音＋麦克风四种音频模式。
- 托盘、全局快捷键、倒计时和浮动录制工具栏。
- FFmpeg H.264 实时编码，支持录制状态、磁盘空间和编码失败降级。
- 输出视频不叠加 QuickRec 自绘光标；点击高亮仅作为桌面实时提示。

### 素材库

- 使用 `%APPDATA%\QuickRec\recordings.json` 维护跨保存路径中央索引。
- 记录时长、分辨率、FPS、录制模式、音频模式和文件大小。
- 支持关键词搜索、状态/模式/音频/时间筛选和结果排序。
- 支持历史迁移、手动导入、目录重建、备份恢复和文件重新定位。
- 支持复制路径、仅移除索引，以及将受控视频移入 Windows 回收站。
- 索引写入失败不会改写“视频已保存”的事实，可通过待入库机制重试。

### 设置与诊断

- 保存路径、质量、FPS、音频、倒计时、快捷键和开机自启配置。
- 复制诊断信息、打开日志目录、导出诊断文件和自定义诊断目录。
- 配置采用原子写入；保存失败时保留原配置并提供明确反馈。

## v1.8 开发预览

v1.8 包含两条正式产品主线：

1. **Full 工作台基础壳与视觉改版**
   - 固定侧栏统一承接录制、素材库、设置和诊断。
   - 工作台单实例、关闭隐藏、页面状态保持和离屏位置修正。
   - 区域选择器、窗口选择器、倒计时和录制工具栏继续作为独立浮动界面。

2. **单显示器 1080p120 全屏录制**
   - 设置提供 30、60、120 FPS；新安装仍默认 30 FPS。
   - 首次选择 120 FPS 时执行真实硬件能力检测。
   - 快速校验检查显示刷新率、检测缓存、FFmpeg、保存目录和磁盘空间。
   - 区域和窗口录制最高 60 FPS，不会覆盖已保存的全屏 120 设置。
   - 性能不足时保留视频并展示实际平均 FPS、最低 FPS 和稳定性告警。

当前候选包已经通过三次 1080p120 技术门禁、三档 DPI、自动化回归和主要 GUI 链路。
详细证据见 [v1.8 verification](doc/releases/v1.8/verification.md)。

## 快速运行

要求：Windows、Python 3.12，以及项目根目录下可用的 `ffmpeg/ffmpeg.exe` 和
`ffmpeg/ffprobe.exe`。

```powershell
cd E:\codex\QuickRec
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python src/main.py
```

应用启动后默认驻留系统托盘。通过托盘菜单或双击托盘图标打开工作台。

## 测试与质量门禁

```powershell
python -m pytest -q
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80 -q
python -m pytest -m packaging -q
python -m ruff check src tests scripts
python -m mypy
python -m compileall -q src scripts
```

当前 v1.8 开发提交的最近验证结果：

- 全量测试：`519 passed, 25 deselected, 48 subtests passed`
- Packaging：`13 passed`
- 覆盖率最近记录：`86.07%`
- Ruff、mypy、compileall、UTF-8 和 `git diff --check`：通过
- 100%、125%、150% DPI：通过
- QuickRec Lite：未修改

硬件冒烟：

```powershell
python scripts/hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen
```

## 打包

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm
```

默认输出目录：

```text
dist/QuickRec/
```

开发验收使用独立 `distpath` 和 `workpath`，避免覆盖当前稳定产物。

## 文档导航

```text
doc/
├── current.md                 # 当前正式版本事实入口
├── product/                   # 产品级长期文档
├── releases/
│   ├── v1.4.1/                # 诊断导出发布资料
│   ├── v1.5/                  # 最近录制
│   ├── v1.6/                  # 中央素材库
│   ├── v1.6.1/                # 待入库恢复补丁
│   ├── v1.7/                  # 当前正式版本
│   └── v1.8/                  # 当前 test 开发与验收资料
├── technical/
├── verification/
├── prototypes/
└── archive/
```

v1.8 的主要文档：

- [PRD](doc/releases/v1.8/prd.md)
- [实施计划](doc/releases/v1.8/dev_plan.md)
- [进度看板](doc/releases/v1.8/progress.md)
- [自动化验证](doc/releases/v1.8/verification.md)
- [GUI 手动验收](doc/releases/v1.8/manual-verification.md)
- [缺陷记录](doc/releases/v1.8/bugfix-log.md)

## 发布与回滚

- 当前正式 Release：[QuickRec Full v1.7](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.7)
- v1.7 ZIP SHA256：`0C200C549D1E4ED495BC381298E1A3157B1534526337899DB9ED9C655A37E963`
- 直接回滚点：`v1.6.1`
- `v1.4.1` tag 固定指向诊断导出发布提交 `16c7dce`，未被移动或重写。

QuickRec Lite 已拆分到 `E:\codex\QuickRec-Lite`，Full 与 Lite 的代码、文档、发布包和
版本标签独立维护。
