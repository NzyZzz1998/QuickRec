# QuickRec v2.0 架构优化实施与验证

> **历史实施记录说明（2026-08-10）**
>
> 本文只证明 v1.9.2 基线上的首轮工程治理及当时验证结果，不代表 v1.9.5 之后的
> 全部实现，也不构成当前 v2.0 发布许可。当前代码、质量门禁和发布前缺口请以
> [QuickRec Full v2.0 发布前深度 Review](QuickRec-Full-v2.0-发布前深度Review-2026-08-10.md)
> 和 [当前事实入口](../current.md) 为准。

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 产品 | QuickRec Full |
| 实施基线 | `master` / `91ab91cba324658d9bfadb7016a31f8e4e380efb` |
| 基线标签 | `v1.9.2` |
| 实施日期 | 2026-07-28 |
| 文档状态 | 首轮 P0/P1 优化完成，自动化与候选包回归通过 |
| 发布状态 | 工程验证包，不是新版本发布包 |
| Lite 边界 | `E:\codex\QuickRec-Lite` 未修改 |

本轮依据
[QuickRec 架构审计报告](QuickRec-架构审计报告.md)
和
[QuickRec v2.0 架构优化方案](QuickRec-v2.0-架构优化方案.md)
实施。目标是降低现有协调类的增长风险，同时保持 v1.9.2 用户行为、项目数据格式、
录制输出和发布标签不变。

## 2. 实施原则

1. 不重写录制核心、工作台或时间线编辑器。
2. 不提升项目或时间线 schema 版本，不因打开旧项目触发改写。
3. 不改变项目原子保存、备份恢复和外部冲突保护语义。
4. 每个模块先补行为测试，再接入生产链路。
5. 保留兼容入口，允许按模块回退。
6. 不修改 QuickRec Lite，不移动或创建标签，不提交或推送。

## 3. 实施范围

### 3.1 Windows 单实例与激活

新增：

- `src/services/single_instance.py`
- `tests/test_single_instance.py`

修改：

- `src/main.py`
- `build_std.spec`
- `pyproject.toml`
- `tests/test_main_workflow.py`
- `tests/test_packaging_config.py`

**为什么改**

原有进程内录制锁不能阻止两个 Full 进程同时运行。多实例会放大配置、素材索引和项目
文件并发写入风险。

**改了什么**

- 为 Full 和 Lite 定义不同的产品身份，避免未来两个产品线相互排斥。
- Windows 下使用命名互斥量判断主实例。
- 次实例通过命名事件请求主实例激活工作台，然后正常退出。
- 主实例轮询激活请求并将现有工作台带到前台。
- 保持独立服务接口，入口只负责生命周期装配。

**收益**

- 降低用户数据并发写入风险。
- 避免托盘出现多个 Full 实例。
- 为 Lite 独立运行身份保留明确边界。

### 3.2 TimelineSession 职责拆分

新增：

- `src/services/recording_guard.py`
- `src/services/timeline_media_runtime.py`
- `tests/test_recording_guard.py`
- `tests/test_timeline_media_runtime.py`

修改：

- `src/services/timeline_session.py`
- `tests/test_timeline_session.py`

**为什么改**

`TimelineSession` 同时维护项目状态、媒体播放生命周期和录制期只读规则，继续加入剪辑能力
会使会话对象逐步成为跨层协调中心。

**改了什么**

- `RecordingGuard` 独立维护录制期间的只读保护。
- `TimelineMediaRuntime` 独立维护媒体后端、播放状态和资源释放。
- `TimelineSession` 继续承担项目绑定和会话编排，通过组合保持原公共行为。
- 使用类型协议替代媒体后端的无约束 `Any` 依赖。

**收益**

- 项目状态、媒体资源和录制保护可分别测试。
- 后续 v1.9.3 剪辑命令不需要直接操作播放后端。
- 媒体后端释放边界更清楚。

### 3.3 项目保存协调器

新增：

- `src/services/project_save_coordinator.py`
- `tests/test_project_save_coordinator.py`

修改：

- `src/services/timeline_commands.py`
- `tests/test_timeline_commands.py`

**为什么改**

时间线命令直接承担保存、冲突判断和事务回滚，后续引入裁剪、分割和 schema v2 时容易
复制保存细节。

**改了什么**

- 将项目提交、冲突处理和失败回滚入口集中到 `ProjectSaveCoordinator`。
- 保留现有“离散命令立即同步落盘”语义。
- 保存成功后才写入历史栈；保存失败时 UI、内存和撤销历史保持零副作用。
- 没有错误地引入拖动过程逐帧保存，也没有提前改为异步防抖。

**收益**

- 剪辑命令可以复用同一个事务边界。
- 保存策略未来可演进，而领域命令不需要了解文件系统细节。
- 保持当前商业版本的数据安全行为。

### 3.4 Schema 迁移注册框架

新增：

- `src/utils/schema_migrations.py`
- `tests/test_schema_migrations.py`

修改：

- `src/utils/project_store.py`
- `src/utils/timeline_model.py`
- `tests/test_project_store.py`
- `tests/test_timeline_model.py`

**为什么改**

项目和时间线已有版本字段，但迁移逻辑缺少统一注册、顺序校验和未知未来版本保护。

**改了什么**

- 提供显式、逐版本的迁移注册机制。
- 项目和时间线加载链路统一调用迁移解析。
- 当前版本没有新增迁移，因此 v1.9.2 文件不会被改写。
- 未知未来版本继续保持只读和原始数据保留。

**收益**

- v1.9.3 timeline schema v2 可以通过明确的 `v1 -> v2` 迁移接入。
- 避免把迁移散落在 UI、存储和命令层。
- 为字幕轨、导出和未来 AI 元数据保留可审计升级路径。

### 3.5 混合增量历史记录

新增：

- `src/services/timeline_history.py`
- `tests/test_timeline_history.py`

修改：

- `src/services/timeline_commands.py`

**为什么改**

完整项目快照能够可靠撤销，但简单操作也深拷贝整个项目，随着项目规模增长会增加内存和
响应时间成本。

**改了什么**

- 移动片段、重命名轨道和调整轨道顺序使用实体级增量历史。
- 复杂命令继续使用完整快照作为安全回退。
- 增量历史只保存受影响的轨道或片段前后值。
- 撤销和重做仍通过保存协调器提交，保持原子性。
- 当前项目中非时间线字段在增量撤销时不会被旧快照覆盖。

**收益**

- 高频简单操作的历史内存显著下降。
- 不要求一次性把所有既有命令重写为 Command Pattern。
- v1.9.3 可针对裁剪、分割和全局波纹逐项增加领域命令。

### 3.6 类型化录制完成事件

新增：

- `src/services/application_events.py`
- `tests/test_application_events.py`

修改：

- `src/recorder/workflow.py`
- `src/main.py`
- `tests/test_recording_workflow.py`
- `tests/test_main_workflow.py`

**为什么改**

录制完成曾同时保留管理器回调和工作流事件两个可能入口，长期容易出现重复保存反馈或
重复入库。

**改了什么**

- 新增线程安全、类型化的 `ApplicationEventHub`。
- 生产装配只从 `RecordingWorkflow` 的 `RecordingEvent` 进入保存完成 UI 桥接。
- 单个订阅者异常不会阻断其他订阅者。
- 保留 `RecorderManager` 旧回调参数以兼容既有测试和外部调用，但生产路径不再并行使用。

**收益**

- 录制保存完成只有一个事实来源。
- 后续 `recording.started`、`thumbnail.generated` 和 `export.finished` 可以按需逐个迁移。
- 避免当前阶段引入全局字符串事件总线。

## 4. 本轮未实施

以下内容仍属于后续设计，不应被表述为已经完成：

- 全量 Command Pattern 替换；
- 拖动编辑的异步防抖保存；
- 全局导航、素材、缩略图和导出事件迁移；
- QuickRecApp、TimelineEditorWindow 或 RecorderManager 全量拆分；
- 项目 schema 或 timeline schema 实际升级；
- AI Agent、导出运行时或公开自动化 CLI；
- 新剪辑功能。

## 5. 自动化验证

### 5.1 全量测试与覆盖率

```text
命令：
python -m pytest --cov=src --cov-report=term-missing
  --cov-report=json:build/coverage-architecture-final.json
  --cov-fail-under=80 -q

结果：
912 passed
27 deselected
56 subtests passed
总语句覆盖率 83.51%
```

基线为 `867 passed, 27 deselected, 56 subtests passed`。本轮新增测试覆盖单实例、会话拆分、
保存事务、迁移注册、增量历史和类型化事件。

### 5.2 工程门禁

| 检查 | 结果 |
| --- | --- |
| Packaging tests | `15 passed, 924 deselected` |
| Ruff | 通过 |
| Mypy | 通过，检查 50 个源文件 |
| Compileall | `src`、`tests`、`scripts` 通过 |
| `git diff --check` | 通过；仅有工作区换行提示 |

## 6. 候选包身份

打包命令：

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm `
  --distpath E:\QRtest\QuickRec-architecture-20260728-dist `
  --workpath E:\QRtest\QuickRec-architecture-20260728-build
```

| 产物 | 大小 | SHA256 |
| --- | ---: | --- |
| `E:\QRtest\QuickRec-architecture-20260728-dist\QuickRec\QuickRec.exe` | 7,257,085 B | `BB7065837B3D4F623BDF82C914374A3C41DE35E72507C14C234F9D87EC023C03` |
| `_internal\ffmpeg\ffmpeg.exe` | 99,264,000 B | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| `_internal\ffmpeg\ffprobe.exe` | 99,066,368 B | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |

PyInstaller 成功完成，未出现阻断错误。该目录只用于本轮工程回归，不替代 v1.9.2 正式包。

## 7. 硬件与 GUI 回归

### 7.1 源码硬件 smoke

```text
输出：
E:\QRtest\QuickRec-architecture-20260728-smoke\
QuickRec_20260728_231757.mp4

FFprobe：
H.264 / 854x480 / 15 FPS / 3.066667 秒 / 56,430 B

结论：
OK: video stream ok
```

### 7.2 打包程序单实例

- 使用隔离 `APPDATA` 和 `LOCALAPPDATA` 启动候选包。
- 首实例保持运行。
- 第二实例在 5 秒内以退出码 0 结束。
- 第二实例请求成功激活首实例现有工作台。
- 关闭工作台只隐藏窗口，后台进程继续驻留。
- 再次启动候选包后原工作台重新显示。

结论：通过。

### 7.3 工作台基础页面

实际检查：

- 录制页；
- 素材库空状态；
- 项目空状态；
- 设置页；
- 诊断页。

中文显示正常，未发现明显崩溃、重叠或乱码。该检查是基础回归，不替代后续版本的三档
DPI 和完整项目 GUI 验收。

### 7.4 打包程序真实录制

隔离配置：

```text
APPDATA：
E:\QRtest\QuickRec-architecture-20260728-runtime\AppData

输出目录：
E:\QRtest\QuickRec-architecture-20260728-package-recording
```

录制证据：

```text
文件：
QuickRec_20260728_232430.mp4

大小：
946,426 B

SHA256：
46FA41D5BFDDFDDF66AEAF3400EC2A3B97601AB6E631400EACFC78179912DCFE

FFprobe：
H.264 / 1920x1080 / 30 FPS / 38.133333 秒 / 无音频
```

实际结果：

- 全屏录制正常启动和停止；
- 结果页显示“录制已保存”；
- 显示“已加入素材库”；
- 隔离中央索引新增一条 `fullscreen / none` 记录；
- 索引中的路径、时长、分辨率、FPS 和文件大小与实际文件匹配；
- 录制完成事件没有产生重复结果或重复入库。

结论：通过。

## 8. 数据与环境保护

- 所有候选包 GUI 测试使用隔离用户目录。
- 没有读取、覆盖或删除真实用户中央索引。
- 没有修改真实用户项目文件或视频。
- 测试结束后已停止候选 QuickRec 进程。
- 没有修改 `E:\codex\QuickRec-Lite`。
- 没有移动 `v1.9.2` 标签，没有提交、推送或创建 Release。

## 9. 已知限制

1. 保存协调器当前保持同步立即保存，尚未引入 500 至 1000 毫秒防抖。
2. 增量历史只覆盖移动片段、重命名轨道和轨道排序；复杂命令仍使用快照。
3. 类型化事件目前只接管录制完成事实，不是全局事件系统。
4. 迁移注册框架已就绪，但项目和时间线版本仍保持 v1.9.2 基线。
5. 本轮候选包只对空项目页面和真实录制链路做了 GUI 回归；实际大项目时间线继续依赖
   123 项时间线自动化回归和既有 v1.9.2 发布证据。
6. Windows API 分支的单元覆盖率有限，但已用真实打包程序完成双实例往返验证。
7. 工作区存在历史 `.pytest-tmp-v191-*` 权限警告，本轮未清理，也不影响测试结论。

## 10. 回滚方式

本轮模块可以独立回滚：

| 模块 | 回滚方式 |
| --- | --- |
| 单实例 | 移除入口装配和打包声明，恢复原启动流程 |
| 会话拆分 | 将 guard/runtime 调用恢复到 `TimelineSession` 原实现 |
| 保存协调器 | 恢复命令服务直接调用项目存储 |
| 迁移注册 | 恢复当前版本直接解析，保留项目原始文件 |
| 增量历史 | 对全部命令重新使用快照历史 |
| 类型化事件 | 恢复原 workflow 回调桥接 |

任何回滚都不得修改用户项目文件、素材索引、录制文件或既有标签。代码回滚点始终是
`v1.9.2` / `91ab91cba324658d9bfadb7016a31f8e4e380efb`。

## 11. 下一阶段判断

首轮架构优化已经达到进入 v1.9.3 正式 PRD 的工程前置条件：

- 时间线媒体与录制保护边界已拆开；
- 剪辑命令可复用保存协调器；
- timeline schema v2 可接入迁移注册框架；
- 简单历史操作不再总是保存完整快照；
- 自动化 CLI 可复用类型化事件和独立服务；
- 候选包录制主链路未回退。

下一步应依据
`doc/releases/v1.9.3/clarification-record.md`
编写正式 `prd.md`，经确认后再生成 `dev_plan.md` 与 `progress.md`。不得直接把本轮架构
优化当作 v1.9.3 剪辑功能已经完成。
