# QuickRec Full

> 面向 Windows 的本地屏幕录制与素材管理工具。支持全屏、区域和窗口录制，
> 四类音频模式、中央素材库、诊断导出，以及素材搜索、筛选和排序。

[![Release](https://img.shields.io/badge/release-v1.7-2563EB)](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.7)
![平台](https://img.shields.io/badge/平台-Windows-111827)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![状态](https://img.shields.io/badge/状态-正式发布-16A34A)

## 当前版本

QuickRec Full **v1.7** 是当前正式版本，已完成开发、自动化门禁、独立打包和 GUI
验收。v1.7 在 v1.6.1 中央素材库基础上增加素材关键词搜索、条件筛选和结果排序。

| 项目 | 当前值 |
| --- | --- |
| 正式分支 | `master` |
| 正式标签 | `v1.7` |
| 发布包 | `QuickRec-v1.7-win-x64.zip` |
| ZIP SHA256 | `0C200C549D1E4ED495BC381298E1A3157B1534526337899DB9ED9C655A37E963` |
| 文档事实源 | [`doc/current.md`](doc/current.md) |
| 发布资料 | [`doc/releases/v1.7/`](doc/releases/v1.7/) |

[下载 QuickRec Full v1.7](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.7)

## 能做什么

### 屏幕录制

- 全屏、区域和窗口三种录制模式。
- 无声、系统声音、麦克风、系统声音＋麦克风四种音频模式。
- 托盘菜单、全局快捷键、倒计时和浮动录制工具栏。
- FFmpeg H.264 实时编码，支持录制状态、磁盘空间和失败降级。
- 输出视频不叠加 QuickRec 自绘光标；点击高亮只作为桌面实时提示。

### 中央素材库

- 在 `%APPDATA%\QuickRec\recordings.json` 维护跨保存路径中央索引。
- 展示时长、分辨率、FPS、录制模式、音频模式和文件大小。
- 支持 v1.5 历史迁移、手动导入、目录重建、备份恢复和文件重新定位。
- 支持关键词搜索、状态/模式/音频/时间筛选和结果排序。
- 支持复制路径、仅移除索引，以及将视频移入 Windows 回收站。
- 索引失败不会改写“视频已经保存”的事实，可通过待入库机制恢复。

### 设置与诊断

- 保存路径、画质、FPS、音频、倒计时、快捷键和开机自启。
- 复制诊断信息、打开日志目录、导出诊断文件和自定义诊断目录。
- 诊断信息仅保存在本地，不上传到云端。

## 工作流程

```mermaid
flowchart LR
    A["全屏 / 区域 / 窗口"] --> B["DXCam 捕获"]
    B --> C["FFmpeg H.264 编码"]
    D["系统声音 / 麦克风"] --> C
    C --> E["本地 MP4"]
    E --> F["中央素材索引"]
    F --> G["搜索 / 筛选 / 排序"]
    G --> H["打开 / 定位 / 整理"]
    C -. "失败上下文" .-> I["本地诊断导出"]
```

视频保存与素材索引是两条独立结果：视频成功生成后，即使索引或元数据处理失败，
QuickRec 也不会误报视频保存失败。

## 快速运行

要求：Windows、Python 3.12，以及项目根目录下可用的 `ffmpeg/ffmpeg.exe` 和
`ffmpeg/ffprobe.exe`。

```powershell
cd E:\codex\QuickRec
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python src/main.py
```

应用启动后驻留系统托盘，可通过托盘菜单或快捷键开始录制。

## 测试

```powershell
python -m pytest -q
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80 -q
python -m pytest -m packaging -q
python -m ruff check src tests
python -m mypy
python -m compileall -q src scripts
```

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

## 文档导航

```text
doc/
├── current.md
├── product/
├── releases/
│   ├── v1.4.1/     # 诊断导出
│   ├── v1.5/       # 最近录制
│   ├── v1.6/       # 中央素材库
│   ├── v1.6.1/     # 待入库恢复补丁
│   └── v1.7/       # 当前正式版本
├── technical/
├── verification/
├── prototypes/
└── archive/
```

v1.7 主要资料：

- [PRD](doc/releases/v1.7/prd.md)
- [实施计划](doc/releases/v1.7/dev_plan.md)
- [进度看板](doc/releases/v1.7/progress.md)
- [验证汇总](doc/releases/v1.7/verification.md)
- [手动验收](doc/releases/v1.7/manual-verification.md)
- [发布说明](doc/releases/v1.7/release-notes.md)
- [变更日志](doc/releases/v1.7/changelog.md)

## 开发版本

下一版本 v1.8 正在 [`test` 分支](https://github.com/NzyZzz1998/QuickRec/tree/test)
进行工作台、视觉改版和 1080p120 录制验收。开发分支内容不代表当前正式发布承诺，
请从 Releases 下载稳定版本。

## 回滚与产品线

- v1.7 的直接回滚点为 `v1.6.1`。
- `v1.4.1` tag 固定指向诊断导出发布提交 `16c7dce`，未被移动或重写。
- QuickRec Lite 已拆分到 `E:\codex\QuickRec-Lite`，Full 与 Lite 独立维护。
