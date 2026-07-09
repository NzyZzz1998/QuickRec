# QuickRec Full

QuickRec Full 是 QuickRec 的完整功能产品线工作区，当前版本为 **v1.4.1**。本目录包含 v1.4.1 诊断导出能力的发布成果，不承接 QuickRec Lite 的轻量化裁剪路线。

> 当前路径：`E:\codex\QuickRec`  
> 当前分支：`feature/v1.4.x-diagnostics`  
> 当前标签：`v1.4.1`  
> 当前文档入口：`doc/current.md`  
> 当前版本目录：`doc/releases/v1.4.1/`  
> 当前发布产物：`dist/QuickRec/QuickRec.exe`

`v1.4.1` tag 固定指向诊断导出发布提交 `16c7dce feat(v1.4.x): add diagnostic export workflow`。后续 HEAD 可能包含 workspace split / 文档治理提交，不代表移动或重写 `v1.4.1` 发布点。

## 当前能力

- 全屏录制。
- 区域录制。
- 窗口录制。
- 无声、系统声、麦克风、系统声 + 麦克风四类音频模式。
- 托盘、快捷键、设置页、保存路径、开机自启等基础桌面能力。
- FFmpeg 实时编码、录制状态机、事件流、音频自检和降级。
- v1.4.1 诊断导出能力：复制诊断信息、打开日志目录、导出诊断文件、自定义诊断目录。

## 文档结构

```text
doc/
  current.md
  product/
    PRD-QuickRec.md
  releases/
    v1.4/
    v1.4.1/
  technical/
  verification/
  prototypes/
  archive/
```

当前发布文档统一位于 `doc/releases/v1.4.1/`：

- `prd.md`
- `dev_plan.md`
- `progress.md`
- `acceptance-checklist.md`
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
