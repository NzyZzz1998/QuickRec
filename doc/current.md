# QuickRec Full 当前事实入口

## 当前定位

- 产品线：QuickRec Full。
- 当前公开正式版本：v1.9.5。
- 当前开发候选：无。
- 当前发布分支：`master`。
- 当前发布标签：`v1.9.5`。
- 开发与集成分支：`test`。
- 当前工作区：`E:\codex\QuickRec`。
- QuickRec Lite：`E:\codex\QuickRec-Lite`，不属于本版范围。
- 当前阶段：v1.9.5 已完成自动化门禁、D9 `31/31` 验收和正式发布收口。
- 历史实施分支：`feature/v1.9-project-workspace`，仅保留在本地，不单独推送远端。

## v1.9.5 当前发布状态

v1.9.5 在 v1.9.4 导出闭环上增强剪辑交互与轨道控制：

- 统一时间线快捷键和焦点契约；
- 支持关联音视频解绑、严格重新关联及解绑后的独立编辑；
- 区分普通删除和全局波纹删除；
- 支持帧级吸附、落点预览、类型校验和条件性自动建轨；
- 使用项目级 30/60/120 FPS 编辑基准及 `HH:MM:SS:FF`；
- 录制工具栏跟随实际录制屏幕并位于中上安全区；
- 安全清理可精确归属的导出临时文件；
- 保持最高视频轨覆盖、最多 8 路音频、timeline schema v2 和持久导出队列
  的正式语义。

正式发布资产：

```text
目录: E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec
GUI: E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec\QuickRec.exe
GUI SHA256: 705B227FE33F31D4EE650334D607CAAA919FC3D1B44C633CEA1E5B75B3B4A226
CLI: E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec\QuickRecCLI.exe
CLI SHA256: 1133802A8BB999B7CE198BB9EBF3F4F9D7C8160C9C9798C0248E28F940F0E386
FFmpeg SHA256: 5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D
FFprobe SHA256: 192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D
ZIP: E:\QRtest\QuickRec-v1.9.5-win-x64.zip
ZIP SHA256: 0B4F90B0202B2F0296B463BFF196B04E7C0BCA6709A245037E390AC1B7185D59
状态: 正式发布；D9 通过（31/31）；ACC 通过（20/20）
```

> **跨版本编辑警告**
>
> v1.9.5 项目与 v1.9.4 及更早版本不保证向下编辑兼容。旧版本可能能够读取
> 项目，但会忽略项目编辑帧率、帧级吸附、解绑/重新关联及新的删除交互。
> 不要在多个版本间反复打开并保存同一生产项目；跨版本操作前请备份
> `.qrproj` 和 `.bak`。

当前 v1.9.5 文档：

- PRD：[releases/v1.9.5/prd.md](releases/v1.9.5/prd.md)
- 实施计划：[releases/v1.9.5/dev_plan.md](releases/v1.9.5/dev_plan.md)
- 进度：[releases/v1.9.5/progress.md](releases/v1.9.5/progress.md)
- 自动验证：[releases/v1.9.5/verification.md](releases/v1.9.5/verification.md)
- GUI 验收：[releases/v1.9.5/manual-verification.md](releases/v1.9.5/manual-verification.md)
- 验收追溯矩阵：[releases/v1.9.5/acceptance-matrix.md](releases/v1.9.5/acceptance-matrix.md)
- 缺陷记录：[releases/v1.9.5/bugfix-log.md](releases/v1.9.5/bugfix-log.md)
- 发布说明：[releases/v1.9.5/release-notes.md](releases/v1.9.5/release-notes.md)
- 变更日志：[releases/v1.9.5/changelog.md](releases/v1.9.5/changelog.md)
- 高保真原型：[releases/v1.9.5/prototype/index.html](releases/v1.9.5/prototype/index.html)

## v1.9.4 发布状态

v1.9.4 在 v1.9.3 基础剪辑和全局波纹之上交付正式本地导出闭环：

- 从 timeline schema v2 构造不可变 `ExportPlan`；
- 支持最大 4K 正偶数画布和 30/60/120 FPS；
- 使用最高视频轨固定覆盖、空白黑场和最多 8 路活动音频动态混合；
- 工作台提供单工作线程持久队列、进度、取消、失败诊断、重试和重启恢复；
- FFprobe 验证通过后才执行同目录原子提交；
- 默认不覆盖，显式覆盖使用备份、事务和崩溃恢复；
- 导出成功后自动加入中央素材库，入库失败可持久重试；
- CLI 新增 `export validate` 和 `export smoke`；
- D10 自动化与 D11 `27/27` GUI、长样本和真实媒体验收通过；
- `LIMIT-194-01` 作为后续版本治理的已知缺陷，不阻塞本版；
- QuickRec Lite 未修改。

正式发布资产：

```text
目录: E:\QRtest\QuickRec-v1.9.4-rc8-dist\QuickRec
GUI: E:\QRtest\QuickRec-v1.9.4-rc8-dist\QuickRec\QuickRec.exe
GUI SHA256: 08A2ACCAFBA45C4DA02AFB2C00135B04D3CE2C606E48583AD08E30465BBA81C9
CLI: E:\QRtest\QuickRec-v1.9.4-rc8-dist\QuickRec\QuickRecCLI.exe
CLI SHA256: FF52A346B74232BFC1CE43DAFBD84FBA164EC3481CABC8CB2EBB1E34B4737C21
FFmpeg SHA256: 5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D
FFprobe SHA256: 192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D
ZIP: E:\QRtest\QuickRec-v1.9.4-win-x64.zip
ZIP SHA256: 8969FDE7CA57853E4D658033AA91469B4990B5A5843711FDCA4662D841DD0997
```

当前 v1.9.4 文档：

- PRD：[releases/v1.9.4/prd.md](releases/v1.9.4/prd.md)
- 实施计划：[releases/v1.9.4/dev_plan.md](releases/v1.9.4/dev_plan.md)
- 进度：[releases/v1.9.4/progress.md](releases/v1.9.4/progress.md)
- 自动验证：[releases/v1.9.4/verification.md](releases/v1.9.4/verification.md)
- GUI 验收：[releases/v1.9.4/manual-verification.md](releases/v1.9.4/manual-verification.md)
- 缺陷记录：[releases/v1.9.4/bugfix-log.md](releases/v1.9.4/bugfix-log.md)
- 技术门禁：[releases/v1.9.4/export-technical-spike.md](releases/v1.9.4/export-technical-spike.md)
- 发布说明：[releases/v1.9.4/release-notes.md](releases/v1.9.4/release-notes.md)
- 变更日志：[releases/v1.9.4/changelog.md](releases/v1.9.4/changelog.md)
- 高保真原型：[releases/v1.9.4/prototype/index.html](releases/v1.9.4/prototype/index.html)

## v1.9.3 历史发布状态

v1.9.3 在 v1.9.2 可播放多轨时间线基础上交付基础剪辑、固定全局波纹和
内部自动化 CLI：

- 基础剪辑支持关联音视频裁剪、分割、轨道锁和固定全局波纹；
- timeline schema v2 支持非零源入点，并从 v1 延迟、原子迁移；
- 剪辑保存、撤销重做、外部冲突、缺失和关联异常具备恢复边界；
- 新增内部自动化 `QuickRecCLI.exe`，与 GUI 共用生产服务和媒体运行时；
- 完成应用单实例、保存协调、播放运行时和录制只读守卫的最小职责拆分；
- D9 自动化、双入口打包和 D10 GUI/真实媒体验收均已通过；
- 三种录制、四种音频、30/60/120 FPS 和 100%/125%/150% DPI 回归通过；
- QuickRec Lite 未修改。

正式发布资产：

```text
目录: E:\QRtest\QuickRec-v1.9.3-rc3-dist\QuickRec
GUI: E:\QRtest\QuickRec-v1.9.3-rc3-dist\QuickRec\QuickRec.exe
GUI SHA256: 94F51E274A32E35CC2E47AA9549BF37B41BE4DD034DDBA72A66309C58E1CC986
CLI: E:\QRtest\QuickRec-v1.9.3-rc3-dist\QuickRec\QuickRecCLI.exe
CLI SHA256: 8E80AEB199D978944BED049668E0F49A840BE2455AA46CAA7318AE29A9DB0B09
FFmpeg SHA256: 5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D
FFprobe SHA256: 192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D
ZIP: E:\QRtest\QuickRec-v1.9.3-win-x64.zip
ZIP SHA256: 87A784FEBA327B60CAC01E0277B7C57320BA4BC663D3DDE58C8DE4F9D09B4F89
```

当前 v1.9.3 文档：

- PRD：[releases/v1.9.3/prd.md](releases/v1.9.3/prd.md)
- 实施计划：[releases/v1.9.3/dev_plan.md](releases/v1.9.3/dev_plan.md)
- 进度：[releases/v1.9.3/progress.md](releases/v1.9.3/progress.md)
- 自动验证：[releases/v1.9.3/verification.md](releases/v1.9.3/verification.md)
- GUI 验收：[releases/v1.9.3/manual-verification.md](releases/v1.9.3/manual-verification.md)
- 缺陷记录：[releases/v1.9.3/bugfix-log.md](releases/v1.9.3/bugfix-log.md)
- 技术门禁：[releases/v1.9.3/playback-accuracy-spike.md](releases/v1.9.3/playback-accuracy-spike.md)
- 发布说明：[releases/v1.9.3/release-notes.md](releases/v1.9.3/release-notes.md)
- 变更日志：[releases/v1.9.3/changelog.md](releases/v1.9.3/changelog.md)
- 高保真原型：[releases/v1.9.3/prototype/index.html](releases/v1.9.3/prototype/index.html)

## v1.9.2 历史发布状态

v1.9.2 在项目素材预览基础上交付可持久化、可恢复、可播放的多轨时间线：

- 项目页通过“进入剪辑”打开独立、默认最大化的剪辑工作台。
- 默认一条视频轨和一条音频轨，两类轨道分别最多 8 条。
- 支持素材加入、片段拖动、吸附、轨道管理、自动保存和 50 步撤销重做。
- 使用 PyAV 提供播放、暂停、随机跳转、固定视频覆盖和固定音频混合。
- 支持缺失素材重新定位、归档只读、损坏恢复和外部修改冲突保护。
- 通过 8+8 轨、100 片段、30 分钟、三档 DPI 和四路音频实际听音验收。

当前门禁：

- D10 GUI 与真实媒体验收：通过。
- 全量测试：`867 passed, 27 deselected, 56 subtests passed`。
- 总体覆盖率：`83.56%`。
- 时间线核心增量覆盖率：`86.44%`。
- 播放与页面协调增量覆盖率：`82.23%`。
- Packaging：`15 passed, 879 deselected`。
- Ruff、Mypy、Compileall、UTF-8、文档链接和 `git diff --check`：通过。
- QuickRec Lite：未修改。

正式发布资产：

```text
目录: E:\QRtest\QuickRec-v1.9.2-release-dist\QuickRec
EXE: E:\QRtest\QuickRec-v1.9.2-release-dist\QuickRec\QuickRec.exe
EXE SHA256: 5383A34E50F963E224AF67D299B58B3903FDBC84F4A5CAA3B955B9C4AE75A5FA
FFmpeg SHA256: 5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D
FFprobe SHA256: 192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D
ZIP: E:\QRtest\QuickRec-v1.9.2-win-x64.zip
ZIP SHA256: AA4D234F0AA4E3B8342B29A5AABD7CD9A76E45BCF140696748A1A9A490848BA1
```

## v1.9.2 当前文档

- PRD：[releases/v1.9.2/prd.md](releases/v1.9.2/prd.md)
- 实施计划：[releases/v1.9.2/dev_plan.md](releases/v1.9.2/dev_plan.md)
- 进度：[releases/v1.9.2/progress.md](releases/v1.9.2/progress.md)
- 自动化验证：[releases/v1.9.2/verification.md](releases/v1.9.2/verification.md)
- GUI 验收：[releases/v1.9.2/manual-verification.md](releases/v1.9.2/manual-verification.md)
- 缺陷记录：[releases/v1.9.2/bugfix-log.md](releases/v1.9.2/bugfix-log.md)
- 发布说明：[releases/v1.9.2/release-notes.md](releases/v1.9.2/release-notes.md)
- 变更日志：[releases/v1.9.2/changelog.md](releases/v1.9.2/changelog.md)
- 高保真原型：[releases/v1.9.2/prototype/index.html](releases/v1.9.2/prototype/index.html)

## v1.9.1 历史发布状态

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

## v1.9.1 历史文档

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

### v1.8 发布资产

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

### v1.8 历史文档

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

- v1.9.5：当前公开正式版。
- v1.9.4：历史稳定版，也是 v1.9.5 的直接回滚点。
- v1.9.3：历史稳定版，也是 v1.9.4 的直接回滚点。
- v1.9.2：历史稳定版，也是 v1.9.3 的直接回滚点。
- v1.9.1：历史稳定版，也是 v1.9.2 的直接回滚点。
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

## v1.9.2 回滚

1. 退出 QuickRec。
2. 使用 `v1.9.1` tag 或 v1.9.1 GitHub Release 发布包。
3. 保留项目文件、项目索引、中央素材索引、首帧缓存和所有视频。
4. v1.9.1 会安全忽略项目 `extensions` 中的时间线数据。
5. 不移动或重写 `v1.9.1` 及更早 tag。

## v1.9.3 回滚

1. 退出 QuickRec 和 `QuickRecCLI.exe`。
2. 使用 `v1.9.2` tag 或 v1.9.2 GitHub Release 发布包。
3. 保留项目文件、项目索引、中央素材索引、首帧缓存和所有视频。
4. v1.9.2 遇到 timeline schema v2 时会保留原始数据并只读，不得为了回滚
   删除或重建项目文件。
5. 不移动或重写 `v1.9.2` 及更早 tag。

## v1.9.4 回滚

1. 退出 QuickRec、`QuickRecCLI.exe`、FFmpeg 和 FFprobe。
2. 使用 `v1.9.3` tag 或 v1.9.3 GitHub Release 发布包。
3. 保留项目文件、项目索引、中央素材索引、时间线、首帧缓存、视频和已完成导出。
4. v1.9.3 会忽略 v1.9.4 导出队列与配置，不需要删除用户项目或素材。
5. 回滚前如有运行中任务，应先取消或等待完成。
6. 不移动或重写 `v1.9.3` 及更早 tag。
