# QuickRec Full v1.9.4 D11 手动验收记录

## 1. 验收状态

| 项目 | 内容 |
| --- | --- |
| 当前阶段 | D11 GUI、长样本、回归与发布判断 |
| 当前结论 | 通过 |
| 当前正式版本 | v1.9.4 |
| 候选版本 | v1.9.4 RC8 |
| 自动化前置 | D10 通过 |
| 发布状态 | D11 已闭合，正式发布 |
| 验收日期 | 2026-07-30 |

本轮已经关闭三档 30 分钟软件编码门禁，并实际验证工作台导出、持久队列、
应用和 Windows 系统重启恢复、手动重试、自动入库、入库失败持久重试、
GUI 排队与运行中任务取消、显式覆盖、真实停滞提示与继续等待恢复，以及全屏
录制。RC8 还关闭了排队任务目标冲突和导出配置弹窗在小可用区域下的底栏裁切，
并通过真实 Windows 100%、125%、150% 系统缩放复验。八路混音和
v1.9.3 麦克风清晰人声均已完成真实听音。产品负责人已确认将
`LIMIT-194-01` 作为 v1.9.4 已知缺陷，并安排到后续版本治理；该限制不再阻塞
本版发布判断。

## 2. 锁定验收对象

| 对象 | 路径 / 值 |
| --- | --- |
| 项目 | QuickRec Full |
| 分支 | `test` |
| 基线 HEAD | `bfa36435f8ba30bb00f0bbaf95e8cfc9b1e13b8b` |
| 工作区状态 | v1.9.4 尚未提交；另有 4 个独立 v2.0 文档，不属于本版 |
| 分发目录 | `E:\QRtest\QuickRec-v1.9.4-rc8-dist\QuickRec` |
| 分发目录规模 | 318 个文件，`503917239` 字节 |
| GUI | `E:\QRtest\QuickRec-v1.9.4-rc8-dist\QuickRec\QuickRec.exe` |
| GUI 大小 / 时间 | `7476148` 字节 / `2026-07-30 14:10:50` |
| GUI SHA256 | `08A2ACCAFBA45C4DA02AFB2C00135B04D3CE2C606E48583AD08E30465BBA81C9` |
| CLI | `E:\QRtest\QuickRec-v1.9.4-rc8-dist\QuickRec\QuickRecCLI.exe` |
| CLI 大小 / 时间 | `6712443` 字节 / `2026-07-30 14:10:50` |
| CLI SHA256 | `FF52A346B74232BFC1CE43DAFBD84FBA164EC3481CABC8CB2EBB1E34B4737C21` |
| FFmpeg SHA256 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| FFprobe SHA256 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |

RC1 至 RC7 已被后续修复取代，不能再作为发布候选包。RC8 的 frozen
`doctor --json` 报告为 QuickRec Full 1.9.4、Python 3.12.8、PyAV 18.0.0、
FFmpeg/FFprobe 8.0.1。RC4 长样本、RC5 录制入口互斥、RC6 候选清理、
入库重试、覆盖与取消，以及 RC7 停滞和真实系统重启证据，在未受 RC8 两项
定向修复影响的范围内继续有效。

## 3. 隔离环境与证据目录

```text
当前候选包验收根目录:
E:\QRtest\QuickRec-v1.9.4-rc8-acceptance

RC8 定向复验证据:
E:\QRtest\QuickRec-v1.9.4-rc8-acceptance\evidence

RC7 停滞处理隔离根目录:
E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\stall

RC7 APPDATA:
E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\stall\AppData\Roaming

RC7 导出队列:
E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\stall\AppData\Roaming\QuickRec\Exports\queue.json

RC7 停滞复验证据:
E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\stall\evidence

继承的 RC6 候选包验收根目录:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance

RC6 候选清理隔离根目录:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup

RC6 入库失败持久重试隔离根目录:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\ingestion-retry

RC6 候选清理 APPDATA:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup\AppData\Roaming

RC6 候选清理 LOCALAPPDATA:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup\AppData\Local

RC6 候选清理 TEMP:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup\Temp

RC6 候选清理导出队列:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup\AppData\Roaming\QuickRec\Exports\queue.json

RC6 候选清理截图:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup\evidence

继承的 RC4 GUI 与长样本证据:
E:\QRtest\QuickRec-v1.9.4-rc4-acceptance

继承的 RC5 录制互斥与设置诊断证据:
E:\QRtest\QuickRec-v1.9.4-rc5-acceptance\gui\evidence

继承的 RC1 长项目和导出结果:
E:\QRtest\QuickRec-v1.9.4-rc1-acceptance\long-gates
```

候选包确实在隔离目录创建配置、队列、索引、日志和输出。QuickRec Lite
工作区保持 `lite-master`、HEAD `cfaee3ed79284d5a184454021177f6ec9de97372`
且状态干净。

## 4. 使用工具与证据来源

- Computer Use：实际操作 RC4 工作台、剪辑工作台、导出配置、预检、队列、
  暂停/继续、异常终止恢复、手动重试和结果操作；RC5 录制入口互斥；RC6
  目标冲突、候选清理、入库失败持久重试、覆盖和取消；RC7 真实停滞提示、
  继续等待、进度恢复、安全终止和真实系统重启；RC8 排队目标安全后缀与
  150% Qt 等效缩放下的导出配置弹窗。
- Frozen CLI：执行 `doctor --json`、三档 30 分钟导出和受控超时取消。
- FFprobe：核对容器、视频、音频、画布、FPS 和时长。
- FFT 报告：核对 1、4、8 路活动音频区间和动态 `1/N` 混音。
- 文件系统：核对候选包、输出、哈希、临时文件、队列和中央素材索引。
- 日志：核对任务阶段、录制保存、自动入库和异常恢复。
- 自动化测试：用于状态机、故障注入、互斥、入库失败和覆盖事务的补充证据；
  不替代必须由真实 GUI、听音、DPI 或系统重启完成的项目。

## 5. D11 验收结果

| ID | 验收项 | 实际结果 | 结论 | 主要证据 |
| --- | --- | --- | --- | --- |
| D11.1 | 候选包 SHA256 | GUI、CLI、FFmpeg、FFprobe 哈希均与 RC8 锁定值一致 | 通过 | 本文第 2 节 |
| D11.2 | 隔离 APPDATA、配置、队列、输出和证据 | 隔离目录内生成全部运行数据；Lite 未修改 | 通过 | 本文第 3 节 |
| D11.3 | 工作台创建导出任务 | 工作台完成预检、排队、执行、验证、提交和入库 | 通过 | `D11-RC4-workbench-720p30-success.jpg` |
| D11.4 | 剪辑工作台创建导出任务 | 剪辑工作台入口复用同一配置与计划创建链路 | 通过 | RC4 GUI 操作、队列计划记录 |
| D11.5 | 1080p60 与 30/60 FPS 自定义画布 | 1920×1080@60、1280×720@30 均成功；规格可由 FFprobe 核对 | 通过 | RC4 队列、输出、`D11-RC4-workbench-720p30-success.jpg` |
| D11.6 | 1080p120 与限制 | 1920×1080@120 成功；超过 1080p 的 120 FPS 组合由配置约束阻止 | 通过 | `long-gates\1080p120\evidence\export-smoke.json` |
| D11.7 | 4K60 与最大画布 | 3840×2160@60 成功；更大或奇数画布由预检阻止 | 通过 | `long-gates\4k60\evidence\export-smoke.json` |
| D11.8 | 1080p60、30 分钟 | 100 片段、1800 秒输出成功，工作台关闭后继续运行并自动入库 | 通过 | `v1.9.4 __ 30 __ 100 __ (1).mp4`、背景运行三张截图 |
| D11.9 | 1080p120、30 分钟 | frozen RC4 CLI 成功，输出 `901484585` 字节 | 通过 | SHA256 `0184A6...3A96`、对应 JSON |
| D11.10 | 4K60、30 分钟 | frozen RC4 CLI 成功，输出 `2437703365` 字节 | 通过 | SHA256 `AFB45A...5FE5`、对应 JSON |
| D11.11 | 100 片段真实项目 | 三档长样本均使用 100 片段、timeline schema v2 项目 | 通过 | 三档计划与 frozen JSON |
| D11.12 | 最多 8 路音频 | 6 秒 H.264/AAC 输出成功；FFT 证明 1、4、8 路分段与动态增益正确；用户真实听音确认阶段变化存在，且无爆音、卡顿、明显失真、提前声音或残留声音 | 通过 | `v1.9.4 eight audio (1).mp4`、`audio-fft-report.json`、`v1.9.4-eight-audio-listening.wav` |
| D11.13 | 中文、空格和长路径 | frozen CLI 在中文空格路径完成导出；长路径计划与输出通过 | 通过 | frozen 报告、队列计划 |
| D11.14 | 队列顺序、暂停和继续 | GUI 暂停/继续可用；FIFO 和单工作线程由队列记录与自动化共同证明 | 通过 | `queue.json`、GUI 状态 |
| D11.15 | 工作台关闭后后台运行 | 17% 关闭工作台，重新打开时 72%，最终 100% 并入库 | 通过 | `D11-RC4-background-export-*.png` |
| D11.16 | 应用与系统重启恢复 | RC4 已验证应用强制终止后恢复；RC7 在真实 Windows 重启后将运行任务恢复为 `interrupted`、排队任务保持 `queued`、队列保持暂停，且没有 FFmpeg 自动续跑 | 通过 | `remaining\evidence\D11-RC7-reboot2-postlaunch-queue.json`、`D11-RC7-reboot2-postlaunch-state.json`、两张 postlaunch 截图 |
| D11.17 | 运行取消和停滞 | frozen CLI 超时退出码 5，RC6 GUI 排队与运行中取消通过；RC7 在真实冻结 FFmpeg 无进度 120 秒后持久显示“可能停滞”和“继续等待”，点击后重置停滞计时并由 8% 恢复至 11%；不继续等待的独立尝试在约 338 秒完成终止与清理，符合 300 秒停滞终止及清理开销；最终受控取消无正式输出或残留媒体进程 | 通过 | `rc7-acceptance\stall\evidence\stall-warning-120.json`、`continue-waiting-reset.json`、`continue-waiting-progress-resumed.json`、`stall-timeout-300-result.json` 及 `D11-RC7-*.png` |
| D11.18 | 自动重试和手动重试 | 白名单自动重试由测试覆盖；异常终止任务在 GUI 手动重试后第二次成功 | 通过 | `job-c802...` 两次 attempt、队列测试 |
| D11.19 | 默认不覆盖 | 同名连续导出生成安全后缀；RC8 进一步把未完成队列任务的目标视为已预留，第二个计划冻结为 `(1)`，队列最终校验也拒绝竞态重复目标 | 通过 | `candidate-cleanup\evidence\after.json`、`D11-RC8-queued-target-safe-suffix.jpg`、`D11-RC8-queued-target-safe-suffix-queue.json` |
| D11.20 | 显式覆盖与逐阶段恢复 | 逐阶段故障注入和恢复自动化通过；RC6 GUI 已验证覆盖取消零副作用和授权后的成功覆盖。成功分支将目标从 SHA256 `9E7E65...81A3` 更新为 `B67C51...A704`，生成 H.264、1920×1080、60 FPS、AAC、6 秒可解析 MP4；任务和入库均为 `succeeded`，无备份、事务、候选或过滤脚本残留 | 通过 | `test_export_committer.py`、`test_export_dialogs.py`、`gui-cancel\evidence\after-authorized-overwrite.json`、`after-authorized-overwrite-queue.json`、`D11-RC6-authorized-overwrite-*.jpg` |
| D11.21 | 自动入库、失败和持久重试 | RC6 在隔离索引独占锁定时完成正式 MP4，任务保持 `succeeded` 且入库单独失败；重启后失败状态仍在，恢复写入后 GUI 重试成功，编码 attempt 仍为 1，索引恰好 1 条，二次重启不重复 | 通过 | `ingestion-retry\evidence\before-retry.json`、`after-retry.json`、`after-successful-restart.json` 及四张 GUI 截图 |
| D11.22 | 录制与导出互斥 | 四项互斥自动化通过；RC5 运行 4K60 导出时，工作台全屏、区域、窗口入口均禁用并就近说明原因；录制未启动 | 通过 | `D11-RC5-export-running-recording-entry-disabled.png`、Guard 测试 |
| D11.23 | 100%、125%、150% DPI | RC8 在真实 Windows 125% 和 150% 系统缩放下重启并完成工作台、导出页、配置弹窗、预检成功态、成功/失败任务详情、结果操作及覆盖二次确认复验；底栏、原生确认框和长路径均无裁切、重叠或不可点击控件。结束后恢复 100%，媒体进程为 0，真实 `%APPDATA%\QuickRec` 零变更 | 通过 | `D11-RC8-windows-dpi-summary.json`、`D11-RC8-windows-dpi-125-*.png`、`D11-RC8-windows-dpi-150-*.png` |
| D11.24 | v1.9.3 全功能回归 | RC8 全量自动化 1238 项通过、31 项跳过、66 个子测试通过；RC6 已补项目打开、时间线播放、素材库详情、项目冲突保护与恢复副本、自动保存持久化、区域和窗口录制；四类音频机器证据完整，RC8 使用 GS03 取得清晰麦克风样本并由用户确认声音正常 | 通过 | `regression\evidence\D11-RC6-project-*.jpg`、区域/窗口录制结果、`D11-RC6-*-audio-ffprobe.json`、`D11-RC6-*-audio-astats*.txt`、`D11-RC6-audio-library-records.json`、`mic-clear-speech-gs03\evidence\record.json` |
| D11.25 | QuickRec Lite 未修改 | Lite 工作区干净 | 通过 | `git status --short --branch` |
| D11.26 | 输出手动验收文档 | 已输出本文 | 通过 | `doc/releases/v1.9.4/manual-verification.md` |
| D11.27 | 全部 ACC 闭合与发布判断 | `ACC-194-01` 至 `ACC-194-15` 已闭合；`LIMIT-194-01` 经产品负责人确认作为后续版本治理的已知缺陷，不阻塞本版 | 通过 | 本表、第 7 节及 `bugfix-log.md` |

## 6. 关键媒体证据

### 6.1 1080p60、30 分钟、100 片段

```text
输出:
E:\QRtest\QuickRec-v1.9.4-rc1-acceptance\long-gates\projects\Exports\
v1.9.4 __ 30 __ 100 __ (1).mp4

大小:
996844591 字节

SHA256:
801FCA88373DC5D7FAB2380F9BB71F6F6D6035666002578FAFC6F128BEF694BD

规格:
H.264 / 1920×1080 / 60 FPS / AAC 双声道 / 1800 秒
```

### 6.2 1080p120、30 分钟、100 片段

```text
输出:
E:\QRtest\QuickRec-v1.9.4-rc4-acceptance\long-gates\1080p120\output\
QuickRec-export-smoke.mp4

大小:
901484585 字节

SHA256:
0184A6DED34AE0384DD64DF0887F509FCD56B04115093B7DEA7B2205877E3A96
```

### 6.3 4K60、30 分钟、100 片段

```text
输出:
E:\QRtest\QuickRec-v1.9.4-rc4-acceptance\long-gates\4k60\output\
QuickRec-export-smoke.mp4

大小:
2437703365 字节

SHA256:
AFB45A75396293CDBB13DD90F3D2DDA58E7F3E600BEE11F3FDE8F3F6E1BC5FE5
```

三档任务完成后均无残留 QuickRecCLI、FFmpeg 或 FFprobe 进程。1080p120 和
4K60 RC4 输出哈希与 RC2 的独立结果一致，证明冻结计划和执行结果具有确定性。

RC6 GUI 还在隔离队列中再次完成同一 4K60、30 分钟任务，输出：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\gui-cancel\output\
running-cancel-must-not-exist.mp4

大小:
2437703365 字节

SHA256:
AFB45A75396293CDBB13DD90F3D2DDA58E7F3E600BEE11F3FDE8F3F6E1BC5FE5
```

FFprobe 核对为 H.264、3840×2160、60 FPS、AAC 48 kHz 双声道、1800 秒。
该哈希与 RC4/RC2 独立结果相同，可作为 GUI 长时运行稳定性和确定性补证。该任务
本身为自然完成样本；运行中取消证据见第 6.11 节。

### 6.4 八路音频

```text
输出:
E:\QRtest\QuickRec-v1.9.4-rc1-acceptance\long-gates\projects\Exports\
v1.9.4 eight audio (1).mp4

大小:
173624 字节

SHA256:
B67C5103777E0348D089F0DCC683076866BB2A07FA5F6BF1E662D88B3804A704

FFT 报告:
E:\QRtest\QuickRec-v1.9.4-technical-gates\output\audio-fft-report.json
```

FFT 报告证明 0～2 秒为 300 Hz，2～4 秒为 300/400/500/600 Hz，4～6 秒为
300～1000 Hz，且活动源按 `1/N` 动态衰减。该证据不能替代真实听音。

为降低人工听音成本，已使用 RC6 包内 FFmpeg 从上述正式 MP4 原样提取 48 kHz、
双声道、16-bit PCM WAV：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\audio-listening\v1.9.4-eight-audio-listening.wav
SHA256: 320328DB4ED060B7C5D3CBADDBBF25B8B86EDB1ED06F671C4852DA430957FCD9
时长: 6.016 秒
```

同目录还提供三个 2 秒分段：

```text
phase-1-300Hz.wav
phase-2-4sources.wav
phase-3-8sources.wav
```

它们仅用于快速听辨单频、4 路和 8 路阶段，不改变正式 MP4，也不替代用户对失真、
削波、声道缺失、提前声音或残留声音的实际听音确认。

### 6.5 v1.9.3 录制回归抽样

```text
输出:
E:\QRtest\QuickRec-v1.9.4-rc4-acceptance\gui\output\
QuickRec_20260730_042520.mp4

大小:
2655681 字节

SHA256:
7361B1BA17ECA468A5CFD72AE3B2CD5B0C6B5F6AA438BE536686DF87BD773639

规格:
H.264 / 1920×1080 / 30 FPS / 无音频 / 61.666667 秒
```

日志记录 1850 帧、视频保存、中央索引写入和资源清理。

### 6.6 RC6 目标冲突与候选文件清理

```text
隔离证据:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup\evidence

任务:
job-rc6-candidate-cleanup

attempt:
attempt-d498e87cfd444156acf9e97378cda38d

冻结计划:
1280×720 / 30 FPS / 6 秒 / 9 个片段 / 8 路音频
```

任务先完成 FFmpeg 与 FFprobe，再因输出目标已存在返回 `target_conflict`。旧目标
大小前后均为 `152180` 字节，SHA256 前后均为
`9E7E65BF6EBC8BA796F583B151BCB5F115E1BFD8E39150373E7192CD3C1281A3`。
本次 `.quickrec-export-attempt-d498e87cfd444156acf9e97378cda38d.part.mp4`
不存在；两份历史失败样本大小与哈希不变；任务结束后无 FFmpeg 进程。

### 6.7 RC6 入库失败、跨重启保持与持久重试

```text
隔离根目录:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\ingestion-retry

任务:
job-2c219787914f43f584a3c294cb7415eb

冻结计划:
plan-0f06828df4f54ec599204a171a44446f
224708F98D794D92163FD9C43478678BD68F82E7EBD3CC9D638E3BB7EA7AE0F3

正式输出:
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\ingestion-retry\output\
rc6-ingestion-retry.mp4

大小 / SHA256:
152180 字节
9E7E65BF6EBC8BA796F583B151BCB5F115E1BFD8E39150373E7192CD3C1281A3

FFprobe:
H.264 / 1280×720 / 30 FPS / AAC 48 kHz 双声道 / 6 秒
```

测试仅对隔离 `recordings.json` 持有独占文件锁，未修改 ACL，也未访问真实
`%APPDATA%\QuickRec`。锁定期间，RC6 完成一次 FFmpeg 编码和正式 MP4 原子提交，
GUI 明确显示“导出成功、入库失败”；队列保存 `status=succeeded`、
`ingestion_status=failed`。关闭并重启 RC6 后失败状态仍存在。释放隔离文件锁并
点击“重试入库”后，GUI 显示“已入库”，`recordings.json` 恰好新增 1 条
`source_type=export` 记录；任务 attempt 数仍为 1，输出大小与 SHA256 不变，
没有 FFmpeg 进程或 `.part.mp4`。再次重启后索引仍为 1 条，证明重试持久且幂等。

证据目录：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\ingestion-retry\evidence
```

其中 `D11-RC6-export-succeeded-ingestion-failed.jpg` 记录编码成功而入库失败；
`D11-RC6-ingestion-failure-persists-after-restart.jpg` 记录跨进程状态；
`D11-RC6-ingestion-retry-succeeded.jpg` 与
`D11-RC6-ingested-material-visible.jpg` 记录恢复及素材库可见结果。

### 6.8 RC6 v1.9.3 GUI 回归补证

RC6 使用独立 APPDATA、LOCALAPPDATA、项目、素材、录制和证据目录：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\regression
```

已完成以下真实 GUI 与媒体核对：

- 打开迁移后的 v1.9.3 项目，项目素材与静态首帧正常显示；
- 进入剪辑工作台，2 条轨道和 3 个片段恢复正常，时间线从头播放并在
  `3.066 / 3.066` 精确结束；
- 素材库显示迁移后的 5 条历史素材，窗口录制详情与中央索引一致；
- 新建区域录制
  `QuickRec_20260730_065733.mp4`，H.264、1500×1080、30 FPS、无音频，
  SHA256 为
  `889AC12F7B941A4032F13A33CC9D27C37A564F36B9868F783B4CE54B26FFCDDD`，
  中央索引模式为 `region`；
- 新建窗口录制
  `QuickRec_20260730_070236.mp4`，H.264、1428×744、30 FPS、23.5 秒、
  无音频，SHA256 为
  `CB722D1FF1863A239A1AE4BDB8FA7168D7AD69E01423182F3CA1843F83899A30`，
  中央索引模式为 `window`；
- 窗口录制抽帧只包含选定的测试记事本窗口。画面中存在浮动录制控制条，
  与 v1.9.3 基线行为一致，不属于 RC6 新增回归。

证据目录：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\regression\evidence
```

其中包括项目、时间线和素材库截图，以及区域/窗口录制结果截图、FFprobe JSON、
中央索引 JSON 和窗口录制抽帧。

### 6.9 RC6 项目保存恢复与音频回归补证

项目保存与恢复链路已在隔离项目目录完成：

- 外部修改冲突时，RC6 保护原项目，不以当前内存状态覆盖外部文件；
- 用户确认后生成恢复副本
  `project.timeline-recovery-20260730_070828.qrproj`；
- 修正受控夹具的注册时间后，正常自动保存成功；
- 关闭并重新打开项目后，轨道名 `视频 1 RC6 自动保存` 仍存在，证明保存结果已持久化；
- 原项目、恢复副本和最终自动保存项目的 SHA256 分别为
  `E3A849...`、`C8E220...` 和 `2451EC...`。

对应截图：

```text
D11-RC6-project-external-conflict-protected.jpg
D11-RC6-project-recovery-copy-saved.jpg
D11-RC6-project-autosave-succeeded.jpg
D11-RC6-project-autosave-persisted-after-reopen.jpg
```

四类音频已完成同一 RC6 候选包下的机器核对：

| 模式 | 样本与结果 | 结论 |
| --- | --- | --- |
| 无声 | 区域和窗口录制均只有 H.264 视频流，无音频流 | 通过 |
| 系统声音 | `QuickRec_20260730_073104.mp4`，AAC 48 kHz 双声道，RMS `-33.49 dB`，峰值 `-17.97 dB` | 通过 |
| 麦克风 | RC6 旧样本输入极低；RC8 使用默认 GS03 重新录制 `QuickRec_20260730_150737.mp4`，AAC 48 kHz 双声道，平均音量 `-41.3 dB`、峰值 `-21.8 dB`，用户确认视频声音正常 | 通过 |
| 系统声音＋麦克风 | `QuickRec_20260730_074312.mp4`，AAC 48 kHz 双声道，RMS `-36.45 dB`；日志确认系统声 2 声道和麦克风 1 声道同时初始化并完成双 WAV 对齐混合 | 通过（机器证据） |

音频证据位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\regression\evidence
```

`D11-RC6-audio-library-records.json` 证明四种模式均以正确 `audio_source`
写入隔离中央索引。系统声音、麦克风和双音频样本分别保留 FFprobe 与 astats
报告。RC8 麦克风补证位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc8-acceptance\mic-clear-speech-gs03
```

输出 `QuickRec_20260730_150737.mp4` 时长 `10.055` 秒、1920×1080、30 FPS，
SHA256 为
`D508C01E84BDF31B5FBD4D60923FEA94FF64A58F48AB8D87A913893C69D6C45B`。
FFprobe、音量分析和用户实际听音均通过，因此 D11.24 更新为“通过”。

### 6.10 RC6 进程级缩放补充证据

在不修改 Windows 系统显示缩放的前提下，使用隔离 APPDATA 和同一锁定 RC6 EXE
分别设置 `QT_SCALE_FACTOR=1.25`、`QT_SCALE_FACTOR=1.5` 启动。该检查覆盖：

- 验收主机实际系统 DPI：`GetDpiForSystem=96`，即 Windows 100%；
- 125%：录制页、导出页；
- 150%：录制页、导出页、项目页、剪辑工作台、导出配置；
- 150%：既有目标的预检、显式覆盖二次确认及选择“否”后的反馈。

截图位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\gui-cancel\evidence
```

关键文件包括：

```text
D11-RC6-qt-scale-125-record-page.jpg
D11-RC6-qt-scale-125-export-page.jpg
D11-RC6-qt-scale-150-record-page.jpg
D11-RC6-qt-scale-150-export-page.jpg
D11-RC6-qt-scale-150-project-page.jpg
D11-RC6-qt-scale-150-timeline-page.jpg
D11-RC6-qt-scale-150-export-config.jpg
D11-RC6-qt-scale-150-overwrite-confirm.jpg
D11-RC6-qt-scale-150-overwrite-confirm-modal.jpg
D11-RC6-qt-scale-150-overwrite-cancelled.jpg
```

各页面和确认框均未发现明显裁切、重叠、横向溢出或不可点击控件。取消覆盖后，
目标文件仍为 `152180` 字节，SHA256 仍为
`9E7E65BF6EBC8BA796F583B151BCB5F115E1BFD8E39150373E7192CD3C1281A3`，
隔离队列中没有 `overwrite-target.mp4` 任务。由于进程级 Qt 缩放不能覆盖 Windows
系统缩放变更后的窗口位置、系统字体和原生对话框行为。该限制已由第 6.15 节
同一 RC8 的真实 Windows 系统缩放复验补齐。

### 6.11 RC6 授权覆盖与运行中取消

显式覆盖成功分支使用受控目标：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup\overwrite\overwrite-target.mp4
```

覆盖前文件为 `152180` 字节，SHA256 为
`9E7E65BF6EBC8BA796F583B151BCB5F115E1BFD8E39150373E7192CD3C1281A3`。
经 GUI 预检、独立二次确认和用户授权后，任务
`job-430ba2a9f4174c7895793bbd3e0f5ba1` 导出成功；覆盖后文件为 `173624`
字节，SHA256 为
`B67C5103777E0348D089F0DCC683076866BB2A07FA5F6BF1E662D88B3804A704`。
FFprobe 核对为 H.264、1920×1080、60 FPS、AAC 48 kHz 双声道、6 秒。
中央素材入库成功，输出目录无 `.backup`、事务、`.part.mp4` 或过滤脚本残留。

运行中取消使用 4K60、30 分钟、100 片段受控任务
`job-a35edc29a44d45c3bee33071ba5906b4`。任务运行至 30% 后经 GUI 二次确认
取消，最终状态为 `cancelled`。正式目标不存在，受控输出目录为空，FFmpeg 和
FFprobe 进程均已退出；源素材仍为 `347710051` 字节，刚完成的覆盖目标哈希也
保持不变。

完整结构化证据和截图位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\gui-cancel\evidence\
after-authorized-overwrite.json
after-authorized-overwrite-queue.json
after-authorized-running-cancel.json
after-authorized-running-cancel-queue.json
D11-RC6-authorized-overwrite-*.jpg
D11-RC6-authorized-running-cancel-*.jpg
```

### 6.12 RC7 真实停滞、继续等待与安全终止

本项使用 RC7 锁定包和 4K60、30 分钟、100 片段受控项目，只冻结当前
QuickRec 子进程中的 FFmpeg，不修改候选包、项目、源素材或真实用户数据。

第一条 attempt `attempt-479eb3ad1f6643f8831af9ae3ce6e28f` 在 FFmpeg
持续无进度时没有收到“继续等待”操作，于
`2026-07-30T10:14:00.512253+08:00` 结束。完整 attempt 用时约
`338.053` 秒，最终为 `failure_kind=stalled`、消息
`FFmpeg progress stalled`。300 秒停滞终止阈值之后完成子进程终止、状态持久化
和临时文件清理；正式输出、`.part.mp4`、过滤脚本和残留 FFmpeg 均不存在。

第二条 attempt 使用同一冻结计划。FFmpeg 在 8% 时被冻结约 121.7 秒后，GUI
持久显示：

```text
可能停滞
导出进度已超过 120 秒未更新；请选择继续等待或取消任务
继续等待
```

点击“继续等待”后，队列中的 `stalled` 立即从 `true` 重置为 `false`，attempt
数量保持为 2，FFmpeg 进程继续存活。恢复该受控进程后，进度从 8% 前进至 10%，
GUI 随后显示 11%，证明恢复的是同一实际导出 attempt，而不是只清除界面提示。
完成该验证后，经 GUI 二次确认取消任务；任务最终为 `cancelled`，没有正式输出、
候选文件、过滤脚本或残留媒体进程。

结构化证据和截图位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\stall\evidence\
build-identity.json
stall-injection-start.json
stall-timeout-300-result.json
stall-continue-injection-start.json
stall-warning-120.json
continue-waiting-reset.json
continue-waiting-progress-resumed.json
continue-path-controlled-cancel-cleanup.json
environment-restored.json
D11-RC7-stall-warning-120.png
D11-RC7-continue-waiting-reset.png
D11-RC7-progress-resumed-11pct.png
D11-RC7-continue-path-cancelled-clean.png
```

验收结束后 QuickRec、QuickRecCLI、FFmpeg 和 FFprobe 进程均为 0。真实
`%APPDATA%\QuickRec` 下关键文件均早于本轮验收启动时间，聚合检查未发现写入；
QuickRec Lite 仍保持干净。

### 6.13 RC7 真实 Windows 系统重启恢复

本项在 RC7 隔离 APPDATA 中创建一个运行中的 4K60 长任务和一个排队任务，
记录队列、运行器状态、进程及截图后执行真实 Windows 重启。系统重新启动后，
在首次启动 QuickRec 前确认没有 QuickRec 或 FFmpeg 自动运行；再次以同一隔离
环境启动 RC7 后：

- 运行任务 `job-4f7ee141d6004ee38dee1c52a36720a8` 恢复为 `interrupted`；
- 排队任务 `job-facae4cf166b4524a02b24205d407b88` 保持 `queued`；
- 队列保持暂停；
- 没有 FFmpeg 自动恢复或重复提交；
- 计划、attempt 历史和原有输出均保留。

证据位于：

```text
E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\remaining\evidence\
D11-RC7-reboot2-pre-running-4k60.jpg
D11-RC7-reboot2-pre-running-4k60-queue.json
D11-RC7-reboot2-pre-running-4k60-state.json
D11-RC7-reboot2-postboot-prelaunch-queue.json
D11-RC7-reboot2-postboot-prelaunch-state.json
D11-RC7-reboot2-postboot-prelaunch-files.json
D11-RC7-reboot2-postlaunch-queue.json
D11-RC7-reboot2-postlaunch-state.json
D11-RC7-reboot2-postlaunch-queued-ui.jpg
D11-RC7-reboot2-postlaunch-interrupted-ui.jpg
```

该实证关闭 D11.16。强制中断留下的可归属 `.filter.txt` 和 `.part.mp4`
继续按 `LIMIT-194-01` 处理，不作为错误正式输出。

### 6.14 RC8 排队目标保护与 150% 等效缩放复验

RC7 真实验收暴露两个发布阻塞：未完成队列任务的输出目标没有参与安全后缀
计算，以及真实 Windows 150% 下导出配置底栏被裁切。修复后生成 RC8，并只
重测受影响链路。

同名目标已有未完成任务时，RC8 预检将第二个计划冻结为：

```text
E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\remaining\Exports\
D11-reboot-queued-4k60 (1).mp4
```

队列同时保留两个不同目标，测试任务随后受控取消，没有删除媒体文件。证据：

```text
E:\QRtest\QuickRec-v1.9.4-rc8-acceptance\evidence\
D11-RC8-queued-target-safe-suffix.jpg
D11-RC8-queued-target-safe-suffix-queue.json
```

RC8 以 `QT_SCALE_FACTOR=1.5`、隔离 APPDATA 启动后，导出配置弹窗会根据
当前屏幕可用区域缩放并居中；取消、开始预检、加入队列三个底栏按钮均完整可见
且可点击。证据：

```text
E:\QRtest\QuickRec-v1.9.4-rc8-acceptance\evidence\
D11-RC8-qt-scale-150-export-dialog-footer-visible.jpg
```

该结果关闭目标预留缺陷，并为第 6.15 节的真实 Windows 系统缩放复验提供
定向基线。

### 6.15 RC8 真实 Windows 125%/150% DPI 复验

使用同一 RC8 GUI（SHA256
`08A2ACCAFBA45C4DA02AFB2C00135B04D3CE2C606E48583AD08E30465BBA81C9`）
和两个独立 APPDATA 副本，依次把 Windows 系统缩放从 100% 切换为 125%、
150%，每档均在关闭并重新启动 QuickRec 后实际操作。

125% 覆盖：

- 录制工作台和导出页；
- 新建导出配置弹窗及底部取消、开始预检、加入导出队列按钮；
- 30 分钟、100 片段计划的预检成功态；
- 导出成功任务的文件、目录、复制路径、查看素材和再次导出操作；
- 导出失败任务的诊断与重试操作。

150% 除上述项目外，还覆盖既有目标的显式覆盖预检和原生二次确认框，并选择
“否”取消覆盖。弹窗会按当前屏幕可用区域收敛并居中，底栏和确认按钮完整可见。
所有操作均未创建新任务、未覆盖既有视频。

证据目录：

```text
E:\QRtest\QuickRec-v1.9.4-rc8-acceptance\evidence
```

主要文件：

```text
D11-RC8-windows-dpi-125-workbench.png
D11-RC8-windows-dpi-125-export-page.png
D11-RC8-windows-dpi-125-export-dialog.png
D11-RC8-windows-dpi-125-preflight-pass.png
D11-RC8-windows-dpi-125-success-detail.png
D11-RC8-windows-dpi-125-failure-detail.png
D11-RC8-windows-dpi-150-workbench.png
D11-RC8-windows-dpi-150-export-page.png
D11-RC8-windows-dpi-150-export-dialog.png
D11-RC8-windows-dpi-150-preflight-pass.png
D11-RC8-windows-dpi-150-success-detail.png
D11-RC8-windows-dpi-150-failure-detail.png
D11-RC8-windows-dpi-150-overwrite-confirm.png
D11-RC8-windows-dpi-summary.json
```

验收结束后 Windows 缩放恢复为 100%（`AppliedDPI=96`），QuickRec、
QuickRecCLI、FFmpeg 和 FFprobe 进程均为 0。复验前后真实
`%APPDATA%\QuickRec` 的文件路径、大小、时间和 SHA256 对比没有变化。
D11.23 结论更新为“通过”。

### 6.16 RC8 音频人工门禁收口

2026-07-30 使用系统播放器完成两项最终听音：

1. 八路混音样本的 1、4、8 路阶段变化可以听到；动态 `1/N` 增益使总体响度
   不会随轨道数等比例增加。用户确认没有爆音、卡顿、明显失真、提前声音或
   残留声音，D11.12 更新为“通过”。
2. 使用 HECATE GS03 录制 10 秒麦克风样本。候选包成功生成 H.264/AAC MP4，
   音轨为 48 kHz 双声道，用户确认视频声音正常，D11.24 更新为“通过”。

录制结束后系统默认输入仍为 HECATE GS03，Windows 缩放为 100%，QuickRec、
QuickRecCLI、FFmpeg 和 FFprobe 进程均为 0。

## 7. 发布阻塞与待人工补证

八路真实听音和 v1.9.3 完整 GUI 回归均已闭合。强制结束应用后曾保留一组
可归属的中断尝试临时文件：

强制结束应用后保留了一组可归属的中断尝试临时文件：

```text
.quickrec-export-attempt-56d76...filter.txt
.quickrec-export-attempt-56d76...part.mp4
```

它们不会被后续尝试复用，也未变成正式输出。当前保留为失败证据，不自动删除。
产品负责人已确认将该问题作为 v1.9.4 已知缺陷，并在后续版本实现受队列、
`attempt_id`、提交事务和活动进程共同保护的陈旧文件治理。

本次复核确认真实系统重启验收目录 `remaining` 中临时文件数量为 0；仍有残留的
是更早的强制结束 `stall` 证据，不属于正常重启恢复残留。该缺陷不造成旧目标
覆盖、错误正式输出或用户素材丢失，因此不阻塞 v1.9.4，D11.27 已关闭。

## 8. 人工补证步骤

### MV-194-01 八路真实听音

1. [已完成] 使用系统播放器打开第 6.4 节听音样本。
2. [已完成] 0～2 秒确认单一音调，2～4 秒和 4～6 秒确认混音阶段发生变化。
3. [已完成] 确认无爆音、卡顿、明显失真、提前声音或残留声音。
4. [已完成] 记录用户实际听音结论。

通过标准：所有区间与 FFT 报告一致，主观听感无明显异常。

执行结果：已通过，详见第 6.16 节。

### MV-194-02 系统重启恢复

1. [已完成] 使用隔离环境启动 RC7。
2. [已完成] 暂停队列，创建两个长任务，再继续队列。
3. [已完成] 第一个任务进入运行后执行 Windows 正常重启。
4. [已完成] 重启后先核对进程和队列文件，再用同一隔离环境启动 RC7。
5. [已完成] 旧运行任务为“已中断”，第二个任务仍排队，队列保持暂停。
6. [已完成] 没有自动开始编码，计划与 attempt 历史保持。

通过标准：队列和计划保留，不重复提交，不自动继续，不误删输出。

执行结果：已通过，详见第 6.13 节。

### MV-194-03 GUI 取消

1. [已完成] 暂停队列并创建受控长任务。
2. [已完成] 验证排队任务取消；任务
   `job-3c601b70f2d543ad8c5aa0295bb2ca0c` 状态为 `cancelled`，没有正式输出、
   `.part.mp4`、过滤脚本或残留 FFmpeg。证据：
   `E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\gui-cancel\evidence\after-queued-cancel-queue.json`
   和
   `E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\gui-cancel\evidence\D11-RC6-queued-cancelled-before-start.jpg`。
3. [已完成] 创建 4K60、30 分钟、100 片段任务并继续队列。
4. [已完成] 进度达到 30% 时点击“取消任务”并确认。
5. [已完成] 任务进入“已取消”。
6. [已完成] 输出目录为空，队列 JSON 为 `cancelled`，FFmpeg/FFprobe 已退出。
   证据：
   `E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\gui-cancel\evidence\after-authorized-running-cancel.json`
   和同目录 `D11-RC6-authorized-running-cancel-*.jpg`。

通过标准：FFmpeg 退出；候选文件被清理；旧目标不变；没有错误正式 MP4。

### MV-194-04 GUI 显式覆盖

1. [已完成] 复制受控 MP4 为覆盖目标并记录 SHA256
   `9E7E65BF6EBC8BA796F583B151BCB5F115E1BFD8E39150373E7192CD3C1281A3`。
2. [已完成] 新建导出，选择同名目标并勾选“覆盖当前同名文件”。
3. [已完成] 预检通过并出现独立二次确认，提示 QuickRec 将使用可恢复覆盖事务。
4. [已完成] 选择“否”；计划未加入队列，旧文件哈希不变。截图：
   `E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\gui-cancel\evidence\D11-RC6-overwrite-confirm-before-cancel.jpg`
   和
   `E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\gui-cancel\evidence\D11-RC6-overwrite-cancelled.jpg`。
5. [已完成] 再次执行并确认覆盖。
6. [已完成] 新目标可解析，SHA256 更新为
   `B67C5103777E0348D089F0DCC683076866BB2A07FA5F6BF1E662D88B3804A704`，
   无永久备份、事务或候选残留。证据：
   `E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\gui-cancel\evidence\after-authorized-overwrite.json`
   和同目录 `D11-RC6-authorized-overwrite-*.jpg`。

通过标准：无确认不覆盖；失败可恢复旧目标；成功只保留可验证新目标。

### MV-194-05 入库失败与持久重试

1. 仅在隔离 APPDATA 中制造中央素材索引写入失败。
2. 完成短导出，确认任务显示“导出成功、入库失败”。
3. 关闭并重启应用，确认入库失败状态仍存在。
4. 恢复写入条件，点击“重试入库”。
5. 核对不重新执行 FFmpeg，索引只增加一条记录。

通过标准：导出事实不被改写；重试持久、幂等、可诊断。

执行结果：已按以上步骤在 RC6 隔离环境完成，结论为通过；详见第 6.7 节。

### MV-194-06 三档 DPI 与完整回归

依次将 Windows 缩放设为 100%、125%、150%，每次重启 RC8 后检查导出页和
配置/确认弹窗；随后执行区域、窗口、四类音频、时间线、项目、设置和诊断回归。
每档至少保存一张工作台和一张弹窗截图，结束后恢复原显示缩放。

执行结果：DPI 专项已通过，详见第 6.15 节；麦克风清晰人声听音已独立完成，
详见第 6.16 节。

## 9. 环境恢复要求

验收结束时必须：

1. 停止 RC8 QuickRec、QuickRecCLI、FFmpeg 和 FFprobe；
2. 恢复 Windows DPI、音频模式、权限和临时依赖；
3. 不修改或删除真实 `%APPDATA%\QuickRec` 数据；
4. 保留隔离队列、日志、截图、失败样本和中断临时文件；
5. 确认 QuickRec Lite 工作区仍干净；
6. 不提交、不推送、不打 tag、不创建 Release。

## 10. 当前发布判断

```text
D11：通过
H-194-05：三档 30 分钟软件编码门禁已关闭
系统重启恢复：通过
RC8 目标预留与 150% 等效缩放定向复验：通过
真实 Windows 100%/125%/150% DPI：通过
八路真实听音：通过
v1.9.3 完整 GUI 回归：通过
已知缺陷：LIMIT-194-01，后续版本治理
是否可进入发布收口：是
```
