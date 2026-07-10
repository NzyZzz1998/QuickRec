# QuickRec Full

QuickRec Full 是 QuickRec 的完整功能产品线工作区，当前正式版本为 **v1.5**。v1.4.1 继续作为上一稳定回滚点，本目录不承接 QuickRec Lite 的轻量化裁剪路线。

> 当前路径：`E:\codex\QuickRec`
> 当前发布分支：`master`
> 当前标签：`v1.5`
> 当前文档入口：`doc/current.md`
> 当前版本目录：`doc/releases/v1.5/`
> v1.5 发布包：`QuickRec-v1.5-win-x64.zip`

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
  technical/
  verification/
  prototypes/
  archive/
```

当前发布文档统一位于 `doc/releases/v1.5/`：

- `prd.md`
- `dev_plan.md`
- `progress.md`
- `manual-verification.md`
- `release-notes.md`
- `changelog.md`

## 运行

```powershell
cd E:\codex\QuickRec
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python src/main.py
```

## 测试

```powershell
python -m pytest tests/test_config.py tests/test_diagnostics.py tests/test_settings_dialog.py tests/test_main_workflow.py -q
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
