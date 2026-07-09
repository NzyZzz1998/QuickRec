# QuickRec Lite

QuickRec Lite 是 QuickRec 的轻量化产品线工作区，当前版本为 **Lite v0**。本目录只承接 Lite 路线，不承接 QuickRec Full 的历史文档、诊断导出发布文档或未来 Full Workbench 规划。

> 当前路径：`E:\codex\QuickRec-Lite`  
> 当前分支：`lite-master`  
> 当前标签：`lite-v0`  
> 当前文档入口：`doc/current.md`  
> 当前版本目录：`doc/releases/lite-v0/`

`lite-v0` tag 固定指向 Lite v0 版本点 `c15940e feat: prepare QuickRec Lite v0`。后续 HEAD 可能包含 workspace split / 文档治理提交，不代表移动或重写 `lite-v0` 发布点。

## 当前范围

Lite v0 保留：

- 全屏录制。
- 原生分辨率、最高 60fps 录制链路。
- 无声、系统声、麦克风、系统声 + 麦克风四类音频模式。
- 托盘、设置页、快捷键、保存路径等基础入口。
- Lite v0 打包产物：`dist/QuickRec/`。

Lite v0 不包含：

- 区域录制。
- 窗口录制。
- 录制倒计时。
- 鼠标点击高亮。
- QuickRec Full v1.4.1 诊断导出能力。
- Full v1.x 历史 PRD、技术设计、验证资料、发布记录或 Full Workbench 原型。

## 文档结构

```text
doc/
  current.md
  releases/
    lite-v0/
      README.md
      prd.md
      dev_plan.md
      progress.md
      test-cases.md
      package-size-report.md
      release-notes.md
      development-log.md
  archive/
    README.md
```

Lite 当前文档树只维护 Lite v0 所需资料。若需要查看 QuickRec Full 历史 PRD、技术设计、验证、发布记录、v1.4.1 诊断导出文档或 Full 原型，请查看 `E:\codex\QuickRec`。

## 运行

```powershell
cd E:\codex\QuickRec-Lite
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python src/main.py
```

## 测试

```powershell
python -m pytest tests/test_config.py tests/test_main_workflow.py tests/test_settings_dialog.py tests/test_tray_icon.py -q
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
