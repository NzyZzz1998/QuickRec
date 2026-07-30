# QuickRec Full v1.9.4 导出技术门禁记录

## 0. 追踪信息

| 项目 | 内容 |
| --- | --- |
| 目标版本 | QuickRec Full v1.9.4 |
| 当前状态 | 开发前短样本技术门禁通过，正式实现与发布门禁待执行 |
| 验证日期 | 2026-07-29 |
| 代码基线 | tag `v1.9.3` / `bfa36435f8ba30bb00f0bbaf95e8cfc9b1e13b8b` |
| 需求事实源 | `doc/releases/v1.9.4/prd.md` |
| 原型事实源 | `doc/releases/v1.9.4/prototype/` |
| 证据目录 | `E:\QRtest\QuickRec-v1.9.4-technical-gates` |
| Lite 边界 | `E:\codex\QuickRec-Lite` 未修改 |

本记录用于关闭 PRD 中 `H-194-01`、`H-194-02` 和 `H-194-04` 的开发前可行性门禁。
它不证明正式导出实现、候选包长样本或 GUI 验收已经完成。

## 1. 环境与工具

| 项 | 实际值 |
| --- | --- |
| 操作系统 | Windows |
| FFmpeg | 8.0.1 essentials build |
| FFprobe | 8.0.1 essentials build |
| FFmpeg 路径 | `E:\codex\QuickRec\ffmpeg\ffmpeg.exe` |
| FFprobe 路径 | `E:\codex\QuickRec\ffmpeg\ffprobe.exe` |
| Python | `D:\Work\Software\Python\python.exe` |
| 媒体路径 | `E:\QRtest\QuickRec-v1.9.4-technical-gates\media\中文 空格` |

输入由 8 个受控 H.264/AAC MP4 构成。每个文件为 6 秒、320×180、30 FPS、
48 kHz 双声道，并分别包含 300、400、500、600、700、800、900 和 1000 Hz
正弦波。

## 2. FFmpeg 图验证

### 2.1 场景

受控时间线共 6 秒：

- 0～4 秒：底层红色视频；
- 2～4 秒：高层蓝色视频全画面覆盖；
- 4～6 秒：没有活动视频，输出黑场；
- 0～2 秒：1 路音频，增益 `1/1`；
- 2～4 秒：4 路音频，每路增益 `1/4`；
- 4～6 秒：8 路音频，每路增益 `1/8`；
- 混合结果经过统一限制器。

滤镜图通过 UTF-8 文件传递，输入路径同时包含中文和空格。

### 2.2 FFmpeg 8 语法结论

随包 FFmpeg 8.0.1 会把 `-filter_complex_script` 标记为弃用，当前正式语法应使用：

```text
-/filter_complex <UTF-8 滤镜图文件>
```

v1.9.4 实现不得继续使用已弃用参数，也不得把复杂图拼成 Windows 单条命令字符串。
参数必须以数组传入，滤镜图文件必须在任务结束后按状态规则清理或保留为诊断证据。

### 2.3 画面结果

| 时间点 | 预期 | 实际证据 | 结论 |
| --- | --- | --- | --- |
| 1 秒 | 底层红色视频 | `output/frame-1.png` | 通过 |
| 3 秒 | 高层蓝色视频覆盖 | `output/frame-3.png` | 通过 |
| 5 秒 | 空白时间线黑场 | `output/frame-5.png` | 通过 |

结果证明短样本可以表达“最高有效视频轨全画面覆盖”和“空白区黑场”。高层素材错误时
不得回退显示底层素材，该失败语义仍需在正式 `ExportPlan` 校验和执行测试中覆盖。

### 2.4 三档输出规格

| 档位 | FFmpeg | 分辨率 | FPS | 视频 | 音频 | 时长 | 结论 |
| --- | ---: | --- | --- | --- | --- | ---: | --- |
| 1080p60 | 0 | 1920×1080 | 60/1 | H.264 / yuv420p | AAC / 48 kHz / 2ch | 6 秒 | 通过 |
| 1080p120 | 0 | 1920×1080 | 120/1 | H.264 / yuv420p | AAC / 48 kHz / 2ch | 6 秒 | 通过 |
| 4K60 | 0 | 3840×2160 | 60/1 | H.264 / yuv420p | AAC / 48 kHz / 2ch | 6 秒 | 通过 |

证据：

- `output/profile-spike-report.json`
- `logs/ffmpeg-1080p60.log`
- `logs/ffmpeg-1080p120.log`
- `logs/ffmpeg-4k60.log`

这些是纯色短样本，不能代表 30 分钟、100 片段真实项目的软件编码速度。

## 3. 八路音频门禁

### 3.1 正式导出图

FFT 检查结果：

| 区间 | 预期频率 | 实际检测 | 结论 |
| --- | --- | --- | --- |
| 0～2 秒 | 300 Hz | 300 Hz | 通过 |
| 2～4 秒 | 300、400、500、600 Hz | 全部检测到 | 通过 |
| 4～6 秒 | 300～1000 Hz 共 8 路 | 全部检测到 | 通过 |

幅度随 `1/N` 规则变化：

- 单路主峰约 2988；
- 四路每个主峰约 748；
- 八路每个主峰约 374。

证据：`output/audio-fft-report.json`。

### 3.2 PyAV 预览可行性

使用现有 `_AvAudioDecoder` 同时打开 8 个 MP4，在 4.5 秒位置分别读取
`2×960` 样本并按 `1/N` 混合：

| 项 | 结果 |
| --- | --- |
| 成功解码源数量 | 8 |
| 单源块形状 | 2×960 |
| 混合块形状 | 2×960 |
| 有限值检查 | 通过 |
| 混合峰值 | 0.0768657 |
| 首轮打开、seek、读取和混合耗时 | 88.804 ms |

证据：`output/preview-8-source-report.json`。

当前生产代码仍存在两个明确实现差距：

1. `PyAVPlaybackBackend.capabilities.max_audio_sources` 仍为 4；
2. `mix_audio_blocks` 仍使用固定 `0.25`，不是按活动源数量动态使用 `1/N`。

因此结论是“8 路预览技术可行”，不是“8 路预览已经实现”。正式实现后仍需真实听音、
同步、资源释放和候选包验证。

## 4. 输出验证与原子提交

### 4.1 FFprobe

主短样本临时输出：

```text
E:\QRtest\QuickRec-v1.9.4-technical-gates\output\
.quickrec-export-spike-attempt-1.part.mp4
```

SHA-256：

```text
D11B2F1310D2D29DBC4A83F2887D88F813920DE0D047954832E2141A6FD84CE9
```

FFprobe 实际结果：

| 字段 | 实际值 |
| --- | --- |
| 时长 | 6.000000 秒 |
| 视频 | H.264、640×360、30/1、yuv420p |
| 音频 | AAC、48 kHz、双声道 |
| 容器 | MP4 |

损坏 `.part.mp4` 的 FFprobe 退出码为 1，提交未执行，已有目标 SHA-256 前后完全一致。

### 4.2 覆盖事务

在同目录、同卷使用真实 `os.replace` 验证 5 种场景：

| 场景 | 实际结果 | 结论 |
| --- | --- | --- |
| 默认禁止覆盖 | 旧目标保持，生成 `中文 目标_2.mp4` | 通过 |
| 显式覆盖成功 | 新目标提交，回滚备份删除 | 通过 |
| 旧目标已转备份、临时文件尚未提交 | 启动恢复旧目标并清理临时文件 | 通过 |
| 新目标已提交、回滚备份尚未删除 | 验证新目标后删除备份 | 通过 |
| 目标出现第三方未知内容 | 目标、临时文件和备份全部保留 | 通过 |

旧目标 SHA-256：

```text
FA87DE88B06C16A7C934850877BDF0D294FB4F40322DA5B41BC67CD0885F61D3
```

新目标 SHA-256：

```text
D11B2F1310D2D29DBC4A83F2887D88F813920DE0D047954832E2141A6FD84CE9
```

证据：

- `output/overwrite-transaction-report.json`
- `overwrite/default-deny/`
- `overwrite/success/`
- `overwrite/crash-before-commit/`
- `overwrite/crash-after-commit/`
- `overwrite/ambiguous/`
- `overwrite/verification-blocked-20260729/`

## 5. 门禁判断

| 门禁 | 开发前结论 | 仍需在实现后验证 |
| --- | --- | --- |
| `H-194-01` FFmpeg 表达 schema v2 | 通过短样本可行性门禁 | 100 片段、非零源入点、损坏素材、真实项目 |
| `H-194-02` 8 路预览与导出 | 通过解码和混合可行性门禁 | 生产上限改造、真实听音、同步、长时资源 |
| `H-194-04` 覆盖事务恢复 | 通过文件系统原语门禁 | 正式事务日志、逐阶段故障注入、真实进程终止 |
| `H-194-05` 30 分钟三档软件编码 | 未关闭 | 候选包工作站长样本 |

允许进入开发承接和实现规划。以下情况仍会阻止正式发布：

- 预览与导出未统一为最多 8 路和同一 `1/N` 规则；
- 正式 ExportPlan 不能稳定生成滤镜图；
- 30 分钟三档任一候选包门禁失败；
- 覆盖恢复存在数据丢失或歧义自动处理；
- 中文、空格或 Windows 长路径在正式实现中失败；
- FFprobe 验证失败的文件被提交。

## 6. 证据边界

本轮没有：

- 修改业务代码；
- 修改 QuickRec Lite；
- 写入真实 `%APPDATA%\QuickRec`；
- 修改真实项目、素材库或用户视频；
- 打包候选版本；
- 执行提交、推送、tag 或 Release。

所有脚本、输入、临时输出和故障样本均位于隔离证据目录。
