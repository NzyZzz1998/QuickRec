# QuickRec Lite 当前事实入口

## 当前定位

- 产品线：QuickRec Lite
- 当前正式版本：Lite v0.1
- 稳定分支：`lite-master`
- 集成分支：`lite-test`
- 当前正式标签：`lite-v0.1`
- 当前工作区：`E:\codex\QuickRec-Lite`
- 当前发布包：`E:\QRtest\QuickRec-Lite-v0.1-rc2-dist\QuickRec-Lite-v0.1-win-x64.zip`

历史 `lite-v0` tag 固定指向 `c15940e feat: prepare QuickRec Lite v0`，v0.1 发布没有移动、覆盖或重写该标签。当前 `lite-v0.1` tag 固定指向 `408c376 feat(lite-v0.1): isolate product identity and harden recording`；分支后续的发布状态文档不改变该发布点。

## v0.1 当前状态

QuickRec Lite v0.1 的产品主线是 **Full/Lite 运行身份隔离与稳定性收口**。开发、自动化、打包和真实候选包验收已经完成，RC2 结论为“通过”，正式版本已发布。

已完成：

- 独立产品 ID、EXE/进程名、单实例、配置、临时目录、默认输出、开机启动、托盘和通知身份。
- 旧配置白名单迁移，旧文件只读。
- 原子配置保存、开机启动回滚和快捷键冲突保护。
- 音频设备匹配、双音频 `amix` 与共同起点对齐。
- 静态桌面回退、非阻塞停止、统一 60 FPS 调度和 FPS 感知磁盘估算。
- 删除 Lite 不可达的区域/窗口/倒计时/点击高亮专属运行模块。
- 固定依赖、FFmpeg staging、release manifest、独立 CI 与 Packaging 门禁。

验证事实：

```text
pytest: 231 passed, 11 deselected
coverage: 81.14%（门禁 80%）
核心模块 coverage: 90%（门禁 85%）
协调模块 coverage: 88%（门禁 80%）
packaging: 7 passed, 235 deselected
ruff / mypy / compileall: 通过
硬件 smoke: 通过，约 59.87 FPS
GUI/候选包: 通过
```

## 当前文档

- PRD：`doc/releases/lite-v0.1/prd.md`
- 实施计划：`doc/releases/lite-v0.1/dev_plan.md`
- 进度：`doc/releases/lite-v0.1/progress.md`
- 手动验收：`doc/releases/lite-v0.1/manual-verification.md`
- 验证报告：`doc/releases/lite-v0.1/verification.md`
- 发布说明：`doc/releases/lite-v0.1/release-notes.md`
- 包体积：`doc/releases/lite-v0.1/package-size-report.md`
- 原型：`doc/releases/lite-v0.1/prototype/`

Lite v0 历史资料仍保留在 `doc/releases/lite-v0/`。

## 产品边界

Lite 只提供单显示器全屏录制、四种音频模式、托盘、快捷键、设置和本地保存。区域/窗口录制、120 FPS、高刷新率、工作台、素材库、项目、时间线、剪辑、导出队列、Full 诊断中心、AI 和云同步均不属于 v0.1。

Full 历史和当前资料由 `E:\codex\QuickRec` 维护，Lite 不保存其副本。

## 当前发布状态

Lite v0.1 以 `lite-v0.1` tag 和 [GitHub Release](https://github.com/NzyZzz1998/QuickRec/releases/tag/lite-v0.1) 作为正式发布事实源。两个 Lite 分支已同步，tag CI 的测试与 Packaging 均通过。后续维护从 `lite-test` 集成并在验证后快进 `lite-master`，不得移动既有发布 tag。
