# QuickRec Lite

QuickRec Lite 是 QuickRec 的轻量化产品线工作区。当前正式版本为 **Lite v0.1**，已于 2026-08-12 完成候选包验收和正式发布收口。本目录只承接 Lite 路线，不承接 QuickRec Full 的工作台与创作能力。

> 当前路径：`E:\codex\QuickRec-Lite`
>
> 稳定分支：`lite-master`
>
> 集成分支：`lite-test`
>
> 当前标签：`lite-v0.1`（`408c376`）
>
> 当前文档入口：`doc/current.md`
>
> 当前版本目录：`doc/releases/lite-v0.1/`

历史 `lite-v0` tag 继续固定指向 Lite v0 版本点 `c15940e feat: prepare QuickRec Lite v0`，本次发布没有移动或重写该标签。`lite-v0.1` 固定指向发布提交 `408c376`；稳定/集成分支后续可以包含发布状态文档，不代表移动发布 tag。

## Lite v0.1 范围

Lite v0.1 保留：

- 全屏录制。
- 原生分辨率、固定 60 FPS 录制链路。
- 无声、系统声、麦克风、系统声 + 麦克风四类音频模式。
- 托盘、设置页、快捷键、保存路径等基础入口。
- 独立打包目录与进程身份：`QuickRec-Lite/QuickRec-Lite.exe`。

Lite v0.1 不包含：

- 区域录制。
- 窗口录制。
- 录制倒计时。
- 鼠标点击高亮。
- QuickRec Full v1.4.1 诊断导出能力。
- Full 工作台、素材库、项目、时间线、剪辑、导出队列和诊断中心。

v0.1 重点变化：

- Full/Lite 独立 EXE、产品 ID、单实例、配置、临时目录、开机启动和通知身份。
- 旧 Full 配置仅按白名单复制，不移动、不删除、不覆盖。
- 原子配置保存、设置失败回滚和快捷键事务。
- 系统声设备匹配、双音频立体声混合与时间对齐。
- 静态桌面回退、非阻塞停止和统一帧调度。
- 区域/窗口/倒计时/点击高亮专属代码退出 Lite 运行图与打包图。

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
    lite-v0.1/
      prd.md
      dev_plan.md
      progress.md
      manual-verification.md
      verification.md
      release-notes.md
      package-size-report.md
      prototype/
  archive/
    README.md
```

Lite 当前文档树只维护 Lite v0 与 v0.1 所需资料。若需要查看 QuickRec Full 历史 PRD、技术设计、验证、发布记录、v1.4.1 诊断导出文档或 Full 原型，请查看 `E:\codex\QuickRec`。

## 运行

```powershell
cd E:\codex\QuickRec-Lite
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python src/main.py
```

## 测试

```powershell
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80
```

Lite CI 独立覆盖：

- `lite-master` / `lite-test` push。
- 目标为 `lite-master` / `lite-test` 的 Pull Request。
- `lite-master`、`lite-test` 和 `lite-v*` push 的 Windows packaging smoke。

硬件冒烟：

```powershell
python scripts/hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen --fps 60
```

## 打包

```powershell
python scripts/stage_ffmpeg.py --output ffmpeg/ffmpeg.exe
python -m PyInstaller build_std.spec --clean --noconfirm
```

输出目录：

```text
dist/QuickRec-Lite/QuickRec-Lite.exe
```

正式发布包为 `QuickRec-Lite-v0.1-win-x64.zip`，SHA256 为 `AA307EC1B7B95CBB4F516DECABFD420DD58A3E97B9624C6445F6086C6DCBDD34`。完整身份和验收状态见 [v0.1 验证报告](doc/releases/lite-v0.1/verification.md)，发布页见 [QuickRec Lite v0.1](https://github.com/NzyZzz1998/QuickRec/releases/tag/lite-v0.1)。
