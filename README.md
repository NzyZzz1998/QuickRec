# QuickRec Full

QuickRec Full 是 QuickRec 的完整功能产品线工作区，当前正式版本为 **v1.6**。v1.6 将“最近录制”升级为跨保存路径的轻量素材库基础版；v1.5 作为稳定回滚点，本目录不承接 QuickRec Lite 的轻量化裁剪路线。

> 当前路径：`E:\codex\QuickRec`
> 当前发布分支：`master`
> 当前标签：`v1.6`
> 当前文档入口：`doc/current.md`
> 当前版本目录：`doc/releases/v1.6/`
> v1.6 发布包：`QuickRec-v1.6-win-x64.zip`
> v1.6 Release：[GitHub Releases](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.6)
> 发布 ZIP SHA256：`30F002F8E085220E86C37B1EC672A47739560A80488743A4D6EDE1DB9FED6C69`

`v1.4.1` tag 固定指向诊断导出发布提交 `16c7dce feat(v1.4.x): add diagnostic export workflow`。当前 `master` 后续 HEAD 可能包含 workspace split / 文档治理提交，不代表移动或重写 `v1.4.1` 发布点。

## 当前能力

- 全屏录制。
- 区域录制。
- 窗口录制。
- 无声、系统声、麦克风、系统声 + 麦克风四类音频模式。
- 托盘、快捷键、设置页、保存路径、开机自启等基础桌面能力。
- FFmpeg 实时编码、录制状态机、事件流、音频自检和降级。
- v1.4.1 诊断导出能力：复制诊断信息、打开日志目录、导出诊断文件、自定义诊断目录。
- v1.5 最近录制能力：本地历史索引、最近 50 条、缺失状态、打开文件/目录、复制路径和移除索引。
- v1.5 录制完成结果条与托盘菜单均可进入最近录制窗口。
- v1.5 输出链路不再叠加 QuickRec 自绘光标；点击高亮仍作为桌面实时提示，不写入视频帧。

## v1.6 素材库基础版

- 中央素材索引固定在 `%APPDATA%\QuickRec\recordings.json`，跨保存路径统一展示。
- “最近录制”入口升级为“素材库”，提供列表、详情、加载更多和缺失状态。
- 支持 v1.5 历史迁移、手动导入、目录重建、备份恢复和单项重新定位。
- 新录制写入时长、输出宽高、FPS、模式、音频和文件大小；旧素材使用内置 `ffprobe` 按需补齐。
- 支持仅移除索引，或将单个视频移入 Windows 回收站。
- 已完成自动化、独立打包、硬件 smoke、三种录制模式、四类音频、素材库主链路、失败降级和 DPI GUI 验收，当前无发布阻塞。

## 文档结构

```text
doc/
  current.md
  product/
    PRD-QuickRec.md
  releases/
    v1.4/
    v1.4.1/
    v1.5/
    v1.6/
  technical/
  verification/
  prototypes/
  archive/
```

当前发布文档统一位于 `doc/releases/v1.6/`：

- `prd.md`
- `dev_plan.md`
- `progress.md`
- `manual-verification.md`
- `release-notes.md`
- `changelog.md`

v1.5 历史发布文档保留在 `doc/releases/v1.5/`；v1.6 以 `progress.md` 和 `verification.md` 为发布状态事实源。

## 运行

```powershell
cd E:\codex\QuickRec
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python src/main.py
```

## 测试

```powershell
python -m pytest -q
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80 -q
python -m ruff check src tests
python -m mypy
python -m pytest -m packaging -q
```

硬件冒烟：

```powershell
python scripts/hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen
```

## 打包

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm
```

输出目录：

```text
dist/QuickRec/
```

QuickRec Lite 已拆分到 `E:\codex\QuickRec-Lite`，不属于本工作区当前范围。
