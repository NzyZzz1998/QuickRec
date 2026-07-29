# QuickRec Full v1.9.3 开发日志

## 2026-07-29：D0 开始

### 本轮目标

- 完成开发承接；
- 固定 v1.9.2、架构优化和 v1.9.3 的边界；
- 进入 D1 非零源入点播放准确性技术门禁；
- 按 D0-D10 顺序推进到验收入口。

### 执行基线

- 事实源：
  - `doc/releases/v1.9.3/prd.md`
  - `doc/releases/v1.9.3/prototype/`
  - `doc/releases/v1.9.3/dev_plan.md`
  - `doc/releases/v1.9.3/progress.md`
- 当前分支：`master`
- 当前 HEAD：`91ab91cba324658d9bfadb7016a31f8e4e380efb`
- 当前 tag：`v1.9.2`
- 回滚点：`v1.9.2`，不得移动或重写。
- 进入实现授权：已获得（2026-07-29）。
- 提交、推送、tag 和 Release：未授权。
- QuickRec Lite：不属于本版范围，不得修改。

### 既有未提交内容边界

当前工作区在 v1.9.3 实施前已经存在三类内容：

1. 已完成并验证的架构优化：
   - 单实例；
   - `TimelineSession` 媒体与录制保护拆分；
   - `ProjectSaveCoordinator`；
   - `SchemaMigrationRegistry`；
   - 混合增量历史；
   - 类型化录制完成事件。
2. v2.0 架构与贡献归属治理文档。
3. v1.9.3 需求池、PRD、高保真原型和开发承接文档。

实施过程中不得撤销前两类内容，也不得把 v2.0 贡献归属治理文档改写为
v1.9.3 功能文档。由于当前未授权 commit，本轮通过文件清单、测试证据和本日志保持
边界，不执行 Git 提交。

### 已有验证

- 架构优化全量测试：912 passed，27 deselected，56 subtests passed。
- 架构优化总体覆盖率：83.51%。
- Packaging：15 passed，924 deselected。
- Ruff、Mypy、Compileall、`git diff --check`：通过。
- v1.9.3 原型测试：10 passed。
- 原型视口：1920×1080、1216×760、960×640。

这些证据只在相关代码未变化时继承；实施修改对应模块后必须重跑。

### D0 证据

- 基线证据目录：`E:\QRtest\QuickRec-v1.9.3-baseline`
- Git 状态：`baseline-git-status.txt`
- Diff 摘要：`baseline-diff-stat.txt`
- 文件 SHA256：`baseline-sha256.json`
- 分支、HEAD 与 tag：`baseline-identity.json`
- 记录文件：48 个。

架构相关定向回归：

```text
168 passed in 2.69s
```

D0 结论：通过。现有改动未提交，但身份、文件边界和内容哈希已在仓库外证据目录
固定，可以进入 D1。

## 2026-07-29：D1 播放准确性技术门禁

新增：

- `scripts/generate_v193_editing_media.py`
- `scripts/v193_playback_accuracy_spike.py`
- `tests/test_v193_playback_accuracy.py`
- `doc/releases/v1.9.3/playback-accuracy-spike.md`

先后发现并修复三项播放边界：

1. AAC backward seek 后未丢弃目标点前采样；
2. 视频帧结束边界使用闭区间，分割点重复上一帧；
3. 解码器 `release()` 未清空迭代器和 stream 引用，线程退出依赖对象销毁。

修复后的关键结果：

- 30/60/120 FPS 视频 seek 均为 0.51 帧；
- AAC 边界误差 0 ms；
- 连续视频分割接缝 0 μs，无重复帧；
- 30 秒末端音画偏差 16 ms；
- 10 分钟漂移增量 0 ms；
- Backend seek 低于 70 ms，pause 低于 1 ms；
- 释放后线程与子进程增量均为 0；
- 源码和真实 PyInstaller frozen 协议全部通过；
- 相关自动测试 16 passed。

证据目录：

```text
E:\QRtest\QuickRec-v1.9.3-playback-spike
```

D1 结论：通过，可以进入 D2。

## 2026-07-29：D2 timeline schema v2 与延迟迁移

实现：

- timeline 当前 schema 提升到 v2，同时保留 v1 内存读取与序列化；
- `TimelineTrack.locked` 成为 v2 正式字段，v1 默认只读为 `false`；
- v2 允许非零源入点和局部源时长，并保持一倍速时长与关联组不变量；
- 注册 v1→v2 迁移，未知字段、实体扩展和项目其他扩展完整往返；
- 新增 `upgrade_timeline_for_v2_edit()`，显式构造 v2 候选；
- v1 兼容轨道改名继续保存 v1；
- 第一次轨道锁定使用现有项目事务创建 v1 `.bak` 后原子保存 v2；
- 写入失败时文件、内存和撤销栈保持不变。

验证：

```text
86 passed in 1.66s
Ruff：通过
Mypy：通过
```

真实回滚验证使用 tag `v1.9.2` 的归档源码读取 v2 fixture：

```text
project_ok=true
timeline status=unsupported
read_only=true
raw_schema=2
fixture SHA256 before/after：
8CBCC75A45267DFE2085B8570F2CB1063DECA25C3D7AB7904118C2F5E5D45A58
```

旧版源码和证据目录：

```text
E:\QRtest\QuickRec-v1.9.3-schema-compat
```

D2 结论：通过，可以进入 D3。

## 2026-07-29：D3 剪辑候选、关联组与全局波纹

新增：

- `src/services/timeline_edit_service.py`
- `tests/test_timeline_edit_service.py`

实现边界：

- 纯 `TimelineEditService` 只读取项目与时间线快照并返回候选，不写文件、不依赖 Qt；
- 候选携带来源指纹、规范化边界、影响摘要、冲突和建议选中对象；
- 视频边界按可信 FPS 归一化，缺失 FPS 时使用 100 ms 下限，独立音频使用
  20 ms 下限；
- 关联视频与音频保持原子裁剪、分割和删除；
- 分割保持左侧身份，并为右侧片段和右侧关联组生成新身份；
- 裁剪缩短、延长和删除使用固定全局波纹；
- 锁定轨道、删除区间交叉、插入点交叉和同轨重叠在提交前阻止；
- 无效候选不修改正式时间线。

验证：

```text
TimelineEditService：14 passed
领域、schema 与模型联合回归：66 passed
Ruff：通过
Mypy：通过
100 次混合合法裁剪：通过
100 片段波纹预检（200 次测量）：
  P50 1.384 ms
  P95 1.415 ms
  Max 3.080 ms
```

D3 结论：通过，可以进入 D4。

## 2026-07-29：D4 命令、原子保存、历史与回滚

实现：

- `TimelineCommandService` 新增裁剪、分割和全局波纹删除候选预览入口；
- 提交入口只接受带来源指纹的已验证候选，时间线变化后拒绝陈旧候选；
- 候选预览不写项目文件、不改变内存和历史；
- 每次候选提交只执行一次原子项目保存并形成一条历史；
- 裁剪和轨道锁在 schema 头兼容时使用实体增量历史；
- 分割和全局波纹删除使用安全快照历史；
- 第一次 v2 剪辑把 v1→v2 迁移、备份、校验和保存并入同一事务；
- 保存失败保留同一候选供重试，放弃后回到最后成功状态；
- 删除片段只修改时间线，不删除项目素材引用或原始媒体。

验证：

```text
时间线领域、命令、历史、schema、模型与会话：120 passed
Ruff：通过
Mypy：通过
100 片段候选提交：16.434 ms
旧 schema 首次裁剪：
  v1 -> v2 原子保存：通过
  v1 .bak：通过
  撤销恢复 v1：通过
  重做恢复 v2：通过
```

D4 结论：通过，可以进入 D5。

## 2026-07-29：D5 PyQt 剪辑交互与布局

实现：

- 新增裁剪手势、左右手柄、候选覆盖层、精确时间码检查器和影响确认弹窗；
- 分割按钮、右键菜单和 `Ctrl+B` 复用同一命令事务；
- `Delete` 进入全局波纹删除确认，轨道提供锁定入口和只读视觉；
- 检查器采用固定头尾与可滚动内容，960×640 下不再越出时间线面板；
- 输入时间码时按 `Delete` 只编辑文本，不误删时间线片段；
- 取消空候选不再无条件重绑画布或干扰项目切换。

验证：

```text
PyQt 剪辑交互、命令、窗口与播放协调：54 passed
Ruff：通过
Mypy：通过
```

Windows 原生截图证据：

```text
E:\QRtest\QuickRec-v1.9.3-ui-windows
```

覆盖 960×640、1216×760 和 1600×900；检查器始终处于父面板内，窄窗口
可以滚动访问完整输入和操作区。

## 2026-07-29：D6 编辑后播放计划与真实准确性

实现：

- 编辑提交后使用已重新定位的项目媒体路径原子替换播放计划；
- 播放头在新总时长内夹紧，编辑候选预览不修改正式播放计划；
- 撤销和重做重建播放计划但不自动开始播放；
- 保持解码失败、项目切换、关闭窗口和退出应用的既有资源释放语义。

自动回归：

```text
播放准确性、PyAV、运行时、查询与页面协调：48 passed
Ruff：通过
Mypy：通过
```

源码与重新构建的 frozen 协议均通过，证据目录：

```text
E:\QRtest\QuickRec-v1.9.3-d6-playback
```

关键证据：

```text
source-report.json
SHA256 382690485BD39FCEBE6079B59D539CF47AD34540DF1CD251865C037B4CE2DDE9

frozen-report.json
SHA256 7BA8E8BF280D3E9155614D5215A4C5F43538DA621F8259A6C04C94010238FB07

QuickRecV193PlaybackSpike.exe
SHA256 7BA30766B97AC2AA999A6488EB87A799D3CF3B073065E9075679A5323AFCC0A2
```

视频、音频、连续接缝、30 秒与 10 分钟同步、中文空格路径和资源释放全部达到
PRD 门槛。D6 结论：通过，可以进入 D7。

## 2026-07-29：D7 异常恢复、日志与诊断

实现：

- 新增时间线片段健康检查，统一识别素材缺失和关联组结构异常；
- 缺失片段保留身份、源范围和时间位置，禁用裁剪与分割，但允许确认后波纹删除；
- 关联异常片段整组禁用移动、裁剪、分割和删除，不自动猜测修复关系；
- 片段属性在只读、归档和缺失状态下仍可查看，写操作显示具体禁用原因；
- 重新定位后的中央素材事实可恢复同一素材的全部片段，不改片段与关联身份；
- 损坏时间线不再残留显示上一项目画布，项目素材和备份恢复入口继续可用；
- 命令诊断增加迁移、候选、波纹影响、保存、撤销重做和待保存状态；
- 播放诊断增加最近跳转目标、源边界、耗时、结果与资源释放状态；
- 新增日志只记录项目 ID、命令类别、计数和阶段，不记录媒体完整路径。

验证：

```text
D7 缺失、关联、只读、恢复、日志、诊断与资源回归：158 passed
Ruff：通过
Mypy：通过
```

D7 结论：通过，可以进入 D8。

## 2026-07-29 D8 独立 QuickRecCLI

- 新增独立 `src/cli_entry.py` 与 `src/cli/`，实现 JSON v1、稳定退出码、超时、stdout/stderr 分离和无 GUI 导入边界。
- 实现 `doctor`、`probe`、`project validate`、`timeline validate`、隔离全屏 `record` 和 `smoke --suite editing`。
- 会修改状态的命令强制独立工作区和证据目录，并在命令期间隔离 APPDATA、LOCALAPPDATA、TEMP 与输出目录。
- editing smoke 只操作输入项目副本，覆盖 timeline v1 到 v2、裁剪、分割、候选零副作用、播放查询和重载。
- 双入口 PyInstaller 试包成功，`QuickRec.exe` 与 `QuickRecCLI.exe` 位于同一目录并共享 `_internal`。
- 源码与 frozen CLI 的 doctor、editing smoke、真实 30 FPS 全屏录制、FFprobe 和时间线校验均通过。
- 真实录制门禁发现静态桌面下 DXCam 可能无法提供首帧；补充一次性 Pillow 静态首帧兜底，实时帧到达后仍由 DXCam 覆盖。相关非硬件测试 20 项通过。

## 2026-07-29 D9 全量质量门禁与 RC1

- 全量非硬件回归 `1031 passed, 29 deselected, 62 subtests passed`；
- Packaging `17 passed, 1043 deselected`；
- 总体覆盖率 83.55%；
- 剪辑核心 87.65%、剪辑 UI 协调 80.11%、CLI 核心 88.05%；
- Ruff、Mypy、Compileall 和 `git diff --check` 通过；
- `build_std.spec` 在同一目录生成 `QuickRec.exe` 与 `QuickRecCLI.exe`，
  并共享 FFmpeg、FFprobe 与 PyAV；
- 冻结 CLI 的 doctor、editing smoke、真实 30 FPS 全屏录制、probe 和
  timeline validate 均通过；
- RC1 GUI 进程在隔离环境下完成基础启动观察，没有立即崩溃；
- 创建 `verification.md`、`manual-verification.md` 和 `bugfix-log.md`；
- RC1 仅进入 D10 验收，不视为已发布版本。

## 2026-07-29 D10 RC1 至 RC3 定向修复与复验

- RC1 验收发现删除片段后选择摘要仍保留已删除片段，RC1 随即失效；
- RC2 修复删除后的选择清理，但分割后选择摘要仍显示分割前的片段 ID 和源范围，
  RC2 随即失效；
- RC3 将选择摘要统一改为从最新时间线模型重新计算，避免继续使用分割前的缓存状态；
- 新增 PyQt 回归断言，验证分割后自动选中新右侧片段，并显示收窄后的源范围；
- 受影响测试 `14 passed`，随后重新通过全量、Packaging、Ruff、Mypy、
  Compileall、覆盖率和 `git diff --check`；
- RC3 冻结包中的 doctor、editing smoke、真实全屏录制、probe、
  project validate 和 timeline validate 均通过；
- RC3 GUI 定向复验中，分割后摘要与项目文件一致，截图证据：
  `E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-split-summary-refreshed.jpg`；
- 全局波纹删除的最终确认属于破坏性 GUI 操作，尚未获得本次操作确认，因此未执行；
- RC3 当前仅为候选验收包，D10 完整 GUI 验收结束前不得发布。
