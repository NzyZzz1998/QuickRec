# QuickRec Full v1.9.4 自动验证记录

## 1. 验证结论

| 项目 | 结果 |
| --- | --- |
| 验证阶段 | D10 自动化门禁与 D11 RC8 候选包验证 |
| 结论 | 自动化与 D11 验收通过 |
| 发布判断 | RC8 通过，可以正式发布 |
| 验证日期 | 2026-07-30 |
| 当前分支 | `test` |
| 基线提交 | `bfa36435f8ba30bb00f0bbaf95e8cfc9b1e13b8b` |
| 应用版本 | `v1.9.4` |
| 代码回滚点 | tag `v1.9.3` |

本候选包由尚未提交的 v1.9.4 工作区生成。为避免把同一基线上的不同工作区误认为同一构建，
本文件以候选包路径、二进制 SHA256 和冻结 CLI 报告锁定 RC8 身份。RC1 至 RC7
均已失效；RC4 长样本、RC5 录制入口互斥、RC6 候选清理、入库重试、覆盖与取消，
以及 RC7 停滞和真实系统重启，仅作为未受 RC8 定向修复影响的继承证据。

## 2. 候选包身份

| 对象 | 路径或值 |
| --- | --- |
| 分发目录 | `E:\QRtest\QuickRec-v1.9.4-rc8-dist\QuickRec` |
| 构建目录 | `E:\QRtest\QuickRec-v1.9.4-rc8-build` |
| 分发目录大小 | `503917239` 字节，318 个文件 |
| GUI | `E:\QRtest\QuickRec-v1.9.4-rc8-dist\QuickRec\QuickRec.exe` |
| GUI 大小 / 时间 | `7476148` 字节 / `2026-07-30 14:10:50` |
| GUI SHA256 | `08A2ACCAFBA45C4DA02AFB2C00135B04D3CE2C606E48583AD08E30465BBA81C9` |
| CLI | `E:\QRtest\QuickRec-v1.9.4-rc8-dist\QuickRec\QuickRecCLI.exe` |
| CLI 大小 / 时间 | `6712443` 字节 / `2026-07-30 14:10:50` |
| CLI SHA256 | `FF52A346B74232BFC1CE43DAFBD84FBA164EC3481CABC8CB2EBB1E34B4737C21` |
| FFmpeg SHA256 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| FFprobe SHA256 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |

构建命令：

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm `
  --distpath E:\QRtest\QuickRec-v1.9.4-rc8-dist `
  --workpath E:\QRtest\QuickRec-v1.9.4-rc8-build
```

PyInstaller 成功生成同一 onedir 中的 `QuickRec.exe` 和 `QuickRecCLI.exe`。构建日志存在
`pycparser.lextab`、`pycparser.yacctab`、`sip` 隐式导入提示及 license expression 校验提示；
packaging 测试、冻结 CLI、PyAV、FFmpeg 和 FFprobe 实际运行均通过，当前未形成运行时阻塞。

## 3. 自动化测试

### 3.1 导出定向回归

以下范围合并执行：

- 导出模型、计划、滤镜图、执行、验证和原子提交；
- 队列、事务、退出协调；
- 导出对话框、导出页和工作台协调；
- CLI 导出合同；
- 录制与导出互斥；
- 素材入库和主流程回归。

RC8 新增三个失败优先测试并通过：

- 队列预留目标参与安全后缀计算；
- `enqueue()` 拒绝竞态重复目标；
- 导出配置弹窗在小可用区域内保持底栏可见。

三个新测试通过，受影响模块定向回归 `65 passed`。

### 3.2 全量非硬件测试

覆盖率证据：

```text
E:\QRtest\QuickRec-v1.9.4-rc8-coverage.json
```

结果：

```text
1238 passed, 31 deselected, 66 subtests passed
Total coverage: 84.09%
```

### 3.3 增量覆盖率

| 分组 | 实际覆盖率 | 门槛 | 结果 |
| --- | ---: | ---: | --- |
| 时间线剪辑核心 | 87.72% | 85% | 通过 |
| 时间线 UI 协调 | 80.29% | 80% | 通过 |
| QuickRec CLI 核心 | 87.80% | 85% | 通过 |
| 导出计划与持久化 | 90.15% | 90% | 通过 |
| 导出执行与 CLI | 87.44% | 85% | 通过 |
| 导出 UI 协调 | 88.48% | 80% | 通过 |

### 3.4 Packaging

```text
19 passed, 1250 deselected
```

## 4. 静态和文档门禁

| 检查 | 结果 |
| --- | --- |
| Ruff | 通过 |
| Mypy | 通过，75 个源文件无问题 |
| Compileall | 通过 |
| `git diff --check` | 通过，仅有 Git 换行提示 |
| UTF-8 与乱码检查 | 通过，当前 v1.9.4 事实源和原型文本均可按 UTF-8 读取 |
| Markdown 内部链接 | 通过，当前版本内部链接有效 |

Ruff 扫描时对四个历史 pytest 临时目录出现访问拒绝警告；这些目录不属于 v1.9.4
源文件和候选包，规则扫描仍以 `All checks passed` 完成。

## 5. Frozen CLI 短样本

证据目录：

```text
E:\QRtest\QuickRec-v1.9.4-rc4-acceptance
```

验证内容：

1. `doctor --json` 报告 `QuickRec Full`、版本 `1.9.4`、`frozen=true`。
2. Python 3.12、FFmpeg 8.0.1、FFprobe 8.0.1 和 PyAV 18.0.0 均可用。
3. `export validate` 使用正式 PlanBuilder 成功冻结 timeline schema v2 计划。
4. `export smoke` 使用正式 Executor、Verifier 和 Committer 成功导出。
5. 输出为 H.264/AAC、640×360、30 FPS、4 秒。
6. 输出文件 SHA256 为
   `AEB8E2736390238296E774F20EB1D090F01D27447E76255BB023BB844A599614`。
7. 真实 `%APPDATA%\QuickRec` 聚合指纹前后均为
   `6F9502DA920820B7858F9B5402151E0130A956BEC87CD405A5E5188556A7880A`。

## 6. RC4 至 RC7 继承证据与 RC8 候选包验证

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 1080p60 / 30 分钟 / 100 片段 | 通过 | 输出 SHA256 `801FCA88373DC5D7FAB2380F9BB71F6F6D6035666002578FAFC6F128BEF694BD` |
| 1080p120 / 30 分钟 / 100 片段 | 通过 | 输出 SHA256 `0184A6DED34AE0384DD64DF0887F509FCD56B04115093B7DEA7B2205877E3A96` |
| 4K60 / 30 分钟 / 100 片段 | 通过 | 输出 SHA256 `AFB45A75396293CDBB13DD90F3D2DDA58E7F3E600BEE11F3FDE8F3F6E1BC5FE5` |
| 最多 8 路音频 | 通过 | H.264/AAC 输出、FFprobe、FFT 与用户真实听音均通过 |
| 工作台关闭后后台导出 | 通过 | 17% 关闭、72% 重开、100% 完成截图 |
| 应用异常终止恢复 | 通过 | 旧运行任务恢复为中断，手动重试 attempt 2 成功 |
| frozen 取消/超时 | 通过 | 退出码 5，输出目录为空，无残留媒体进程 |
| 全屏录制回归 | 通过 | 61.666667 秒 H.264 录制成功并自动入库 |
| 录制与导出互斥 | 通过 | RC5 运行长导出时三个工作台录制入口均禁用；导出结束后恢复 |
| 目标冲突候选清理 | 通过 | RC6 冻结包返回 `target_conflict`；旧目标哈希不变，本次 `.part.mp4` 不存在，无残留 FFmpeg |
| 入库失败与持久重试 | 通过 | RC6 正式 MP4 在隔离索引写入失败时仍成功；失败跨重启保留，GUI 重试后只入库 1 条，attempt 仍为 1，输出哈希不变 |
| GUI 排队任务取消 | 通过 | RC6 排队任务经二次确认后为 `cancelled`；正式输出、候选文件、过滤脚本和媒体进程均不存在 |
| GUI 4K60 长时运行 | 通过 | RC6 GUI 隔离队列完成 1800 秒任务；输出大小 `2437703365` 字节，SHA256 `AFB45A...5FE5`，与 RC4/RC2 独立结果一致 |
| GUI 显式覆盖取消 | 通过 | 既有目标预检通过并出现二次确认；选择“否”后目标 SHA256 仍为 `9E7E65...81A3`，队列无对应任务 |
| Qt 进程级 125%/150% 缩放补查 | 通过（补充证据） | 同一 RC6 EXE 在隔离 APPDATA 下使用 `QT_SCALE_FACTOR=1.25/1.5` 检查录制、导出、项目、时间线、导出配置和覆盖确认；未见裁切、重叠或不可点击控件，但不替代真实 Windows DPI |
| v1.9.3 GUI 回归补证 | 通过 | RC6 项目打开、时间线播放结束、素材库详情、项目冲突保护与恢复副本、自动保存持久化、区域录制和窗口录制通过；四类音频机器证据完整，RC8 GS03 麦克风样本由用户确认声音正常 |
| 120 秒停滞提示与继续等待 | 通过 | RC7 冻结 FFmpeg 后约 121.7 秒持久显示“可能停滞”；继续等待将状态重置并使同一 attempt 从 8% 恢复至 11% |
| 300 秒停滞安全终止 | 通过 | 独立 attempt 约 338.053 秒完成终止与清理，符合 300 秒停滞阈值及后续清理开销；无正式输出、候选、过滤脚本或残留媒体进程 |
| Windows 系统重启恢复 | 通过 | RC7 真实重启后，原运行任务为 `interrupted`、原排队任务仍为 `queued`、队列保持暂停且无 FFmpeg 自动续跑 |
| 排队目标预留 | 通过 | RC8 对已被未完成任务占用的目标自动生成 `(1)` 安全后缀；队列最终校验拒绝竞态重复目标 |
| 150% 导出配置底栏 | 通过 | RC8 先在 `QT_SCALE_FACTOR=1.5` 下完成定向修复复验，随后在真实 Windows 125%/150% 系统缩放下验证工作台、导出页、配置/预检、成功/失败详情和覆盖确认；底栏与原生确认框完整可见 |

三档长样本任务结束后不存在 QuickRecCLI、FFmpeg 或 FFprobe 残留进程。
`H-194-05` 已由 RC4 正式关闭。

RC6 候选清理证据位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup\evidence
```

其中 `before.json` 与 `after.json` 记录旧目标、两份历史失败样本和本次 attempt 的
前后状态；`D11-RC6-target-conflict-candidate-cleaned.jpg` 记录 GUI 失败反馈。

RC6 入库失败持久重试证据位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\ingestion-retry\evidence
```

`before-retry.json`、`after-retry.json` 与 `after-successful-restart.json`
证明输出 SHA256 始终为
`9E7E65BF6EBC8BA796F583B151BCB5F115E1BFD8E39150373E7192CD3C1281A3`、
编码 attempt 始终为 1，最终索引恰好 1 条且二次重启不重复。四张 GUI 截图分别
覆盖导出成功但入库失败、跨重启保持、重试成功和素材库可见。

RC6 v1.9.3 回归补证位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\regression\evidence
```

项目冲突保护、恢复副本、正常自动保存及重开持久化均有截图。音频侧已生成无声、
系统声音、麦克风和双音频样本，并以 FFprobe、astats、运行日志和中央索引交叉
核对。系统声音样本 RMS 为 `-33.49 dB`，双音频样本 RMS 为 `-36.45 dB`。
RC8 使用 HECATE GS03 新增清晰麦克风样本
`E:\QRtest\QuickRec-v1.9.4-rc8-acceptance\mic-clear-speech-gs03\workspace\output\QuickRec_20260730_150737.mp4`；
其时长 `10.055` 秒、AAC 48 kHz 双声道、平均音量 `-41.3 dB`、峰值
`-21.8 dB`，用户实际听音确认声音正常。

八路正式 MP4 已另行原样提取为
`E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\audio-listening\v1.9.4-eight-audio-listening.wav`，
规格为 PCM s16le、48 kHz、双声道、6.016 秒，SHA256 为
`320328DB4ED060B7C5D3CBADDBBF25B8B86EDB1ED06F671C4852DA430957FCD9`；
同目录包含单频、4 路和 8 路三个 2 秒听音分段。该资产仅简化人工听辨，不替代
真实听音结论。用户于 2026-07-30 确认阶段变化存在，且没有爆音、卡顿、明显
失真、提前声音或残留声音。

RC6 进程级缩放补充截图位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\gui-cancel\evidence
```

125% 覆盖录制页和导出页；150% 覆盖录制页、导出页、项目页、剪辑工作台、
导出配置和显式覆盖确认框。确认框选择“否”后，目标文件 SHA256 仍为
`9E7E65BF6EBC8BA796F583B151BCB5F115E1BFD8E39150373E7192CD3C1281A3`，
队列无对应任务。该证据只证明 Qt 进程级缩放下的布局与交互，不替代 Windows
系统 125%/150% 缩放验收。

RC6 随后完成授权覆盖成功分支和运行中取消。覆盖任务
`job-430ba2a9f4174c7895793bbd3e0f5ba1` 成功生成 H.264、1920×1080、
60 FPS、AAC、6 秒输出，目标 SHA256 更新为
`B67C5103777E0348D089F0DCC683076866BB2A07FA5F6BF1E662D88B3804A704`，
且无覆盖事务残留。4K60、30 分钟任务
`job-a35edc29a44d45c3bee33071ba5906b4` 在 30% 时经 GUI 确认取消，
最终无正式输出、候选文件、过滤脚本或残留媒体进程。结构化证据位于
`gui-cancel\evidence\after-authorized-*.json`。

RC7 完成真实停滞语义定向复验。第一条 attempt 在不执行“继续等待”时以
`failure_kind=stalled` 安全结束；第二条 attempt 在 120 秒提示后执行“继续等待”，
持久队列中的 `stalled` 从 `true` 恢复为 `false`，进度从 8% 继续至 11%，随后
通过 GUI 受控取消并完整清理。证据位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\stall\evidence
```

关键文件为 `stall-warning-120.json`、`continue-waiting-reset.json`、
`continue-waiting-progress-resumed.json`、`stall-timeout-300-result.json`、
`continue-path-controlled-cancel-cleanup.json` 和 `D11-RC7-*.png`。验收结束后
QuickRec、QuickRecCLI、FFmpeg 和 FFprobe 进程均为 0，真实用户 APPDATA 未被写入。

RC7 还完成真实 Windows 重启恢复。重启前运行中的
`job-4f7ee141d6004ee38dee1c52a36720a8` 在重新启动 RC7 后恢复为
`interrupted`，排队任务 `job-facae4cf166b4524a02b24205d407b88` 保持
`queued`，队列保持暂停且没有 FFmpeg 自动运行。前后队列、运行器状态和截图位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\remaining\evidence
```

随后发现两个 RC7 发布阻塞：排队任务目标没有参与新计划的安全后缀计算，以及
真实 Windows 150% 下导出配置底栏被裁切。修复后生成 RC8。RC8 冻结 CLI
`doctor --json`、包内 FFprobe 和中文空格媒体路径解析均通过；同名排队目标
定向复验生成 `(1)` 安全后缀，150% Qt 等效缩放下导出配置底栏完整可见。
证据位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc8-acceptance\evidence
```

RC8 随后在真实 Windows 125% 和 150% 系统缩放下完成专项复验，覆盖录制
工作台、导出导航、配置、预检、成功/失败任务详情、结果操作和显式覆盖二次
确认。系统最终恢复为 100%，相关进程为 0，真实 `%APPDATA%\QuickRec`
前后哈希零变化。结构化汇总为同目录
`D11-RC8-windows-dpi-summary.json`，D11.23 更新为“通过”。

### 6.1 发布收口复核

2026-07-30 在正式提交前对待发布工作区再次执行完整门禁：

```text
python -m pytest -m "not hardware and not packaging" -q
1238 passed, 31 deselected, 66 subtests passed

python -m pytest -m packaging -q
19 passed, 1250 deselected

python -m pytest -m "not hardware and not packaging" --cov=src
Total coverage: 84.09%

python -m ruff check src tests scripts
python -m mypy
python -m compileall -q src tests scripts
全部通过
```

增量覆盖率依次为 `87.72%`、`80.29%`、`87.80%`、`90.15%`、
`87.44%` 和 `88.48%`，均达到对应门槛。正式 ZIP 由锁定 RC8 目录生成，
包含 GUI、CLI、FFmpeg 和 FFprobe：

```text
E:\QRtest\QuickRec-v1.9.4-win-x64.zip
SHA256: 8969FDE7CA57853E4D658033AA91469B4990B5A5843711FDCA4662D841DD0997
```

## 7. D11 当前结论

详细逐项结果和人工补证步骤见
[`manual-verification.md`](manual-verification.md)。八路真实听音和 v1.9.3
完整 GUI 回归已经闭合。D10 自动化门禁为“通过”，D11 为 `27/27`。产品
负责人已确认将 `LIMIT-194-01` 作为 v1.9.4 已知缺陷，并安排到后续版本进行
受队列和 attempt 归属保护的陈旧临时文件治理。真实系统重启验收目录当前无
临时文件残留，更早的强制结束样本继续作为证据保留。该限制不再阻塞本版，
v1.9.4 已完成发布收口并正式发布。
