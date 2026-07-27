# QuickRec Full 当前事实入口

## 当前定位

- 产品线：QuickRec Full。
- 当前公开正式版本：v1.9.1。
- 当前发布分支：`master`。
- 当前发布标签：`v1.9.1`。
- 开发与集成分支：`test`。
- 当前工作区：`E:\codex\QuickRec`。
- QuickRec Lite：`E:\codex\QuickRec-Lite`，不属于本版范围。
- 当前阶段：v1.9.1 已完成 D8 GUI 验收并正式发布。
- 历史实施分支：`feature/v1.9-project-workspace`，仅保留在本地，不单独推送远端。

## v1.9.1 发布状态

v1.9.1 在 v1.9 项目工作区基础上补齐静态首帧预览和基础素材使用闭环：

- 项目素材列表和详情区提供静态首帧。
- 支持刷新单条预览和批量重建。
- 支持项目页打开视频、定位所在目录，以及跳转并选中全局素材库记录。
- 文件缺失时保留历史预览并显示缺失状态。
- 缓存独立保存于 `%LOCALAPPDATA%\QuickRec\ThumbnailCache\v1`，默认上限 500 MiB。
- 项目、项目索引和中央素材索引不写入预览路径或任务状态。

当前门禁：

- D8 GUI 验收：通过。
- 全量测试：`714 passed, 26 deselected, 52 subtests passed`。
- 总体覆盖率：`85.89%`。
- Packaging：`14 passed, 726 deselected`。
- Ruff、mypy、compileall、UTF-8、文档链接和 `git diff --check`：通过。
- 实际首帧、文件打开、中文空格路径定位、DPI 布局和托盘退出：通过。
- QuickRec Lite：未修改。

正式发布资产：

```text
目录: E:\QRtest\QuickRec-v1.9.1-rc6-dist\QuickRec
EXE: E:\QRtest\QuickRec-v1.9.1-rc6-dist\QuickRec\QuickRec.exe
EXE SHA256: 33B7DB1EB96007D75BF933D5600EE813A03ED42390CAE3A93EAD0960B9C6C7D9
FFmpeg SHA256: 5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D
FFprobe SHA256: 192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D
ZIP: E:\QRtest\QuickRec-v1.9.1-win-x64.zip
ZIP SHA256: FD859E4EA0065119BE06C382BCE3FA2C76774DB23711C21023F0A95A1F61F588
```

## v1.9.1 当前文档

- PRD：[releases/v1.9.1/prd.md](releases/v1.9.1/prd.md)
- 实施计划：[releases/v1.9.1/dev_plan.md](releases/v1.9.1/dev_plan.md)
- 进度：[releases/v1.9.1/progress.md](releases/v1.9.1/progress.md)
- 自动化验证：[releases/v1.9.1/verification.md](releases/v1.9.1/verification.md)
- GUI 验收：[releases/v1.9.1/manual-verification.md](releases/v1.9.1/manual-verification.md)
- 缺陷记录：[releases/v1.9.1/bugfix-log.md](releases/v1.9.1/bugfix-log.md)
- 发布说明：[releases/v1.9.1/release-notes.md](releases/v1.9.1/release-notes.md)
- 变更日志：[releases/v1.9.1/changelog.md](releases/v1.9.1/changelog.md)

## v1.9 历史发布状态

v1.9 的唯一产品主线是本地项目工作区基础：

- 工作台新增“项目”一级页面。
- 项目支持创建、原地打开、重命名、说明编辑、归档、恢复和安全删除。
- 素材以稳定 ID 引用加入一个或多个项目，不复制或移动原视频。
- 支持项目内全屏、区域和窗口录制，并分别反馈视频保存、素材入库和项目关联。
- 支持项目缺失、损坏、只读、备份恢复和外部修改冲突处理。
- 删除项目默认不处理视频；可证明独占的素材可由用户选择移入 Windows 回收站。

当前门禁：

- D8 GUI 验收：`24/24`，通过。
- 全量测试：`642 passed, 26 deselected, 52 subtests passed`。
- 总体覆盖率：`85.76%`。
- Packaging：`14 passed, 654 deselected`。
- Ruff、mypy、compileall、UTF-8、文档链接和 `git diff --check`：通过。
- 三类录制、四类音频、真实 120 FPS 自检、三档 DPI、设置成功/失败、诊断和安全删除：通过。
- QuickRec Lite：未修改。

正式发布资产：

```text
目录: E:\QRtest\QuickRec-v1.9-dist-r8\QuickRec
EXE: E:\QRtest\QuickRec-v1.9-dist-r8\QuickRec\QuickRec.exe
EXE SHA256: CFE6BC6D4FC342039A0B410B4CF80FC9A34BAD47908F671AE9161FC63F7A9D47
FFmpeg SHA256: 5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D
FFprobe SHA256: 192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D
ZIP: E:\QRtest\QuickRec-v1.9-win-x64.zip
ZIP SHA256: B683D051D8D0442B3503F8C5AD9FAE96F8D5538510E890E98F48EB3A1562F446
```

## v1.9 历史文档

- PRD：[releases/v1.9/prd.md](releases/v1.9/prd.md)
- 实施计划：[releases/v1.9/dev_plan.md](releases/v1.9/dev_plan.md)
- 进度：[releases/v1.9/progress.md](releases/v1.9/progress.md)
- 自动化验证：[releases/v1.9/verification.md](releases/v1.9/verification.md)
- GUI 验收：[releases/v1.9/manual-verification.md](releases/v1.9/manual-verification.md)
- 缺陷记录：[releases/v1.9/bugfix-log.md](releases/v1.9/bugfix-log.md)
- 发布说明：[releases/v1.9/release-notes.md](releases/v1.9/release-notes.md)
- 变更日志：[releases/v1.9/changelog.md](releases/v1.9/changelog.md)

## v1.8 历史发布状态

v1.8 包含两条正式产品主线：

1. Full 工作台基础壳与完整视觉改版，将录制、素材库、设置和诊断统一到单实例工作台。
2. 单显示器环境下的 1080p120 全屏录制，包括能力检测、快速校验、性能告警和诊断信息。

当前发布阻塞项已经关闭：

- D11 GUI、DPI 与真实硬件验收：`24/24`。
- 全量测试：`523 passed, 1 skipped, 25 deselected, 48 subtests passed`。
- Packaging：`13 passed`。
- Ruff、项目门禁 mypy、compileall、UTF-8 和 `git diff --check`：通过。
- 三次 1080p120 技术门禁：通过。
- 无声、系统声音、麦克风、系统声音＋麦克风：通过。
- 双音频 10 分钟漂移增量：`-8.333 ms`，通过 `20 ms` 门槛。
- r13 四事件音画最大绝对偏移：`18.229 ms`，通过 `40 ms` 门槛。
- 100%、125%、150% DPI：通过。
- QuickRec Lite：未修改。

## 当前候选身份

正式发布包：

```text
目录: E:\QRtest\QuickRec-v1.8-release-dist\QuickRec
EXE: E:\QRtest\QuickRec-v1.8-release-dist\QuickRec\QuickRec.exe
EXE SHA256: 8BDB84FB08198E927C722E41AC37276A796AD168C55183EE6C24194F2BFE7EA6
ZIP: E:\QRtest\QuickRec-v1.8-win-x64.zip
ZIP SHA256: 78AD1AA5EABCE77211607CE7135C9656923892B5D9C837F92E4EF6C961B10B27
```

D11 音画同步定向复验使用 r13；正式发布包在同一生产修复基础上更新版本号为
`v1.8` 并重新构建，已通过基础启动和 ZIP 内容检查。

## 当前版本文档

- PRD：[releases/v1.8/prd.md](releases/v1.8/prd.md)
- 实施计划：[releases/v1.8/dev_plan.md](releases/v1.8/dev_plan.md)
- 进度：[releases/v1.8/progress.md](releases/v1.8/progress.md)
- 自动化验证：[releases/v1.8/verification.md](releases/v1.8/verification.md)
- GUI 与硬件验收：[releases/v1.8/manual-verification.md](releases/v1.8/manual-verification.md)
- 缺陷记录：[releases/v1.8/bugfix-log.md](releases/v1.8/bugfix-log.md)
- 发布说明：[releases/v1.8/release-notes.md](releases/v1.8/release-notes.md)
- 变更日志：[releases/v1.8/changelog.md](releases/v1.8/changelog.md)
- 高保真原型：[releases/v1.8/prototype/index.html](releases/v1.8/prototype/index.html)
- 视觉核对：[releases/v1.8/visual-verification.md](releases/v1.8/visual-verification.md)

## 历史稳定点

- v1.9.1：当前公开正式版。
- v1.9：历史稳定版，也是 v1.9.1 的直接回滚点。
- v1.8：历史稳定版，也是 v1.9 的直接回滚点。
- v1.7：历史稳定版，也是 v1.8 的直接回滚点。
- v1.6.1：待入库恢复补丁。
- v1.6：中央素材库。
- v1.5：最近录制。
- v1.4.1：诊断导出；tag 固定指向 `16c7dce`，不得移动或重写。

## v1.8 回滚

1. 退出 QuickRec。
2. 如果当前配置使用 `fps=120`，在回滚前将其改为 `60`。
3. 使用 `v1.7` tag 对应代码或 v1.7 GitHub Release 发布包。
4. 保留 `%APPDATA%\QuickRec\recordings.json`、待入库记录和所有录制视频。
5. 回滚不需要删除素材索引；工作台布局和 120 FPS 能力缓存可由旧版本忽略。

## v1.9 回滚

1. 退出 QuickRec。
2. 使用 `v1.8` tag 或 v1.8 GitHub Release 发布包。
3. 保留 `%APPDATA%\QuickRec\projects.json`、所有 `project.qrproj`、`.bak`、中央素材索引和视频。
4. v1.8 会忽略 v1.9 项目数据，不需要删除或迁移。
5. 不移动或重写 `v1.8` 及更早 tag。

## v1.9.1 回滚

1. 退出 QuickRec。
2. 使用 `v1.9` tag 或 v1.9 GitHub Release 发布包。
3. 保留首帧缓存也可安全回滚；v1.9 会忽略该缓存。
4. 保留项目文件、项目索引、中央素材索引和所有视频。
5. 不移动或重写 `v1.9` 及更早 tag。
