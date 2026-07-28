# QuickRec Full v1.9.2 自动验证与发布包记录

## 1. 当前结论

- 当前阶段：D9、D10 与发布收口已完成。
- 当前结论：**自动化通过，RC13 验收通过，正式发布包验证通过**。
- 发布状态：**v1.9.2 正式发布**。
- 验证日期：2026-07-28。
- 需求事实源：[prd.md](prd.md)。
- 实施事实源：[dev_plan.md](dev_plan.md)。
- 进度事实源：[progress.md](progress.md)。
- GUI 事实源：[manual-verification.md](manual-verification.md)。
- 缺陷事实源：[bugfix-log.md](bugfix-log.md)。

## 2. 源码身份

| 项目 | 内容 |
| --- | --- |
| 项目路径 | `E:\codex\QuickRec` |
| 实现分支 | `test`，正式发布分支为 `master` |
| 基线 HEAD | `402c2c62294cb22a38ecad59214eb6789363ce56` |
| 当前正式版本 | `v1.9.2` |
| 目标版本 | `v1.9.2` |
| 发布标识 | tag `v1.9.2` |
| 回滚点 | tag `v1.9.1`，不得移动或重写 |
| Lite 状态 | `E:\codex\QuickRec-Lite` 未修改，`lite-master` 工作区干净 |

RC13 来源是上述基线加 v1.9.2 实现差异。D10 通过后仅更新版本事实源并重新构建
正式发布包；业务实现未再变化。

## 3. 自动化与质量门禁

| 检查 | 结果 |
| --- | --- |
| TDD 失败测试 | 播放日志、完整适配、录制期禁写、停止后解锁和状态刷新均先失败后通过 |
| 录制锁受影响回归 | `92 passed` |
| 标准全量测试 | `867 passed, 27 deselected, 56 subtests passed` |
| Packaging | `15 passed, 879 deselected` |
| 总体覆盖率 | `83.56%`，高于 80% 门槛 |
| 时间线核心增量覆盖率 | `86.44%`，高于 85% 门槛 |
| 播放与页面协调增量覆盖率 | `82.23%`，高于 80% 门槛 |
| Ruff | 通过 |
| Mypy | 项目配置门禁通过，检查 43 个源文件 |
| Compileall | 通过 |
| `git diff --check` | 通过 |
| UTF-8 与乱码检查 | 通过 |
| CI | 包含全量覆盖率 JSON 与两组增量覆盖率门禁 |

标准测试默认排除 `hardware` 与 `packaging` 标记；Packaging 已独立执行。
额外执行的非项目标准命令 `python -m mypy src` 暴露 4 个既有排除模块中的
21 个遗留问题；它不属于当前配置门禁，但已作为后续质量债记录，不能用来
反向宣称全仓 Mypy 已覆盖。

## 4. RC13 候选包身份

候选目录：

```text
E:\QRtest\QuickRec-v1.9.2-rc13-dist\QuickRec
```

| 对象 | 大小 | 修改时间 | SHA256 |
| --- | ---: | --- | --- |
| `QuickRec.exe` | `7,233,597` 字节 | 2026-07-28 16:27:32 | `28F89D701183C8018737559CFF5E159287607BB4FD25AB46313E5010BFEE5C5C` |
| `ffmpeg.exe` | `99,264,000` 字节 | RC13 构建 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| `ffprobe.exe` | `99,066,368` 字节 | RC13 构建 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |

- 分发目录文件数：317。
- 分发目录总大小：496,962,245 字节。
- 包内包含 PyAV 18.0.0、FFmpeg 和 FFprobe。
- 包内 FFprobe 已解析中文空格路径的 H.264/AAC 受控样本。
- RC13 结束后无残留 QuickRec、FFmpeg 或 FFprobe 进程。

### 4.1 正式发布包

正式发布包由 RC13 已验收业务源更新 `APP_VERSION` 为 `v1.9.2` 后重新构建：

| 对象 | 大小 | 修改时间 | SHA256 |
| --- | ---: | --- | --- |
| `QuickRec.exe` | `7,233,597` 字节 | 2026-07-28 19:06:29 | `5383A34E50F963E224AF67D299B58B3903FDBC84F4A5CAA3B955B9C4AE75A5FA` |
| `ffmpeg.exe` | `99,264,000` 字节 | 2026-07-28 19:06:30 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| `ffprobe.exe` | `99,066,368` 字节 | 2026-07-28 19:06:30 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |
| `QuickRec-v1.9.2-win-x64.zip` | `187,791,183` 字节 | 2026-07-28 19:07:43 | `AA4D234F0AA4E3B8342B29A5AABD7CD9A76E45BCF140696748A1A9A490848BA1` |

- 发布目录：`E:\QRtest\QuickRec-v1.9.2-release-dist\QuickRec`。
- 分发目录：317 个文件，共 496,962,245 字节。
- ZIP 包含 `QuickRec/QuickRec.exe`，完整性检查通过。
- 正式 EXE 在隔离 APPDATA 下完成 8 秒基础启动验证，进程随后正常清理。
- 包内 PyAV、FFmpeg、FFprobe 及编解码 DLL 完整。

## 5. 候选继承边界

| 候选 | 状态 | 原因 |
| --- | --- | --- |
| RC1 | 失效 | 补齐播放错误操作后代码已变化 |
| RC2 | 失效 | 后续补齐保存失败、外部冲突与验收修复 |
| RC3 | 失效 | 缺失素材降级日志存在刷新周期洪泛 |
| RC4 | 失效 | 30 分钟时间线“适配”受 25% 最小缩放限制 |
| RC5 | 失效 | 后续补齐会话刷新、资源释放和播放状态修复 |
| RC6 | 失效 | 长时播放持续保留非活动解码器 |
| RC7 | 失效 | 暂停状态图标语义错误 |
| RC8 | 失效 | 后续补齐外部冲突恢复与撤销/重做 GUI |
| RC9 | 失效 | 后续补齐录制协调验收 |
| RC10 | 失效 | 录制期间时间线变更未被真正阻止 |
| RC11 | 失效 | 停止录制后剪辑锁未释放 |
| RC12 | 失效 | 解锁后标题仍显示只读 |
| RC13 | 最终验收候选 | 录制中禁写、停止后解锁和状态文案均已定向复验 |

历史候选中未受后续窄变更影响的工作台、播放、错误降级、DPI、编排和恢复
证据按候选演进边界继承；录制协调必须以 RC13 重新验证。

## 6. 包内媒体工具验证

RC13 包内 FFprobe 已解析历史中文空格路径 H.264/AAC 样本，并解析本轮录制：

```text
E:\QRtest\QuickRec-v1.8-final-manual-20260726\recordings\QuickRec_20260726_101237.mp4
```

结果：

| 项目 | 结果 |
| --- | --- |
| 视频 | H.264、1920×1080、120 FPS |
| 音频 | AAC、48 kHz、双声道 |
| 时长 | 31.000 秒 |
| 中文与空格路径 | 通过 |

RC13 定向录制结果：

| 项目 | 结果 |
| --- | --- |
| 文件 | `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\recordings\QuickRec_20260728_163414.mp4` |
| 视频 | H.264、1920×1080、30 FPS、4815 帧 |
| 时长 | 160.500 秒 |
| 文件大小 | 5,068,555 字节 |
| SHA256 | `3EB6A27CD8966108EBE1063350206C04ECE2164FFF743DDD1DA15481916FFA7A` |
| FFprobe | 包内 `ffprobe.exe` 返回码 0 |

RC13 录制模式、FPS 与捕获音频回归：

| 范围 | 结果 |
| --- | --- |
| 区域录制 | 644×1080、30 FPS、20.967 秒；索引 `mode=region`；抽帧与选区一致 |
| 窗口录制 | 320×532、30 FPS、32.700 秒；索引 `mode=window`；计算器内容变化可见 |
| 60 FPS | 1920×1080、60 FPS、12.983 秒，779 帧 |
| 120 FPS | 能力检测平均 119.424 FPS、最低每秒 116 FPS；录制运行平均 119.908 FPS、最低 116 FPS、丢帧 3 |
| 无声 | 输出无音频流，索引 `audio_source=none` |
| 系统声音 | AAC 48 kHz 双声道，均值 -9.3 dB、峰值 -3.0 dB，索引 `audio_source=system` |
| 麦克风 | AAC 48 kHz 双声道，日志确认 48 kHz 单声道输入，索引 `audio_source=microphone` |
| 系统声音＋麦克风 | 日志确认系统声 2ch 与麦克风 1ch 独立输入和对齐，输出 AAC 48 kHz 双声道 |
| 120 设置下区域/窗口 | 两种模式均明确按 60 FPS 输出，保存配置仍为 120 |

详细文件哈希、抽帧和日志证据见
`doc/releases/v1.9.2/manual-verification.md` 的 16.3 节。

## 7. RC4 真实播放与错误降级

隔离目录：

```text
E:\QRtest\QuickRec-v1.9.2-rc4-acceptance
```

受控项目包含 2 条轨道、4 个片段，同一中文空格路径 H.264/AAC 素材连续使用两次。

已验证：

- 剪辑工作台默认最大化，主工作台同时存在。
- PyAV 生产后端出画，短时播放完成。
- 素材临时缺失时显示明确占位，不崩溃、不露出错误下层画面。
- 素材恢复后重新播放正常。
- 连续缺失期间只记录 2 条不同状态转换告警，不再按约 16 毫秒周期重复。
- 关闭剪辑工作台后，线程由 147 降至 57，句柄由 1196 降至 898。
- 日志记录 `timeline playback released ... result=ok`。

主要证据：

```text
E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\D10-RC4-missing-media-degraded.png
E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\D10-RC4-recovered-playback.png
E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\recordings\QuickRecDiagnostics\quickrec.log
```

## 8. RC4 DPI 与布局

| 缩放 | 方式 | 结果 | 证据 |
| --- | --- | --- | --- |
| 100% | 本机原生缩放 | 通过 | RC3 100% 与 960×640 截图；RC4 受影响代码不涉及布局 |
| 125% | `QT_SCALE_FACTOR=1.25` | 通过 | `evidence\D10-RC4-editor-dpi125.png` |
| 150% | `QT_SCALE_FACTOR=1.5` | 通过 | `evidence\D10-RC4-editor-dpi150.png` |

125% 与 150% 使用同一 RC4、同一隔离 APPDATA 和同一项目数据。关键导航按钮、
素材区、预览区、播放栏和时间线工具栏均位于最大化窗口可视范围内。

## 9. RC4 真实录制与索引

输出：

```text
E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\recordings\QuickRec_20260728_075722.mp4
```

| 项目 | 结果 |
| --- | --- |
| 视频 | H.264、1920×1080、30 FPS |
| 时长 | 4.400 秒 |
| 文件大小 | 218,724 字节 |
| SHA256 | `90394FE7A6B9B207813B6A22ABEE87038E0E5726EB8FD8B66D6AA4B7C95F76D2` |
| 音频 | 无音频流，符合隔离配置 |
| 中央索引 | 写入 1 条 `available` 记录 |
| 索引一致性 | 路径、分辨率、FPS、模式、音频和文件状态一致 |
| 日志 | 捕获、编码、保存、入库、缩略图恢复和退出语义完整 |

自动化第一次启动未重定向控制台，导致 stdout 管道无人读取并阻塞 Python logging。
Py-Spy 证明这是验收工具问题；重定向 stdout/stderr 后，同一 RC4 正常完成上述录制。
详细证据见 [bugfix-log.md](bugfix-log.md)。

## 10. 环境保护

- 真实用户中央索引：
  `C:\Users\win\AppData\Roaming\QuickRec\recordings.json`。
- 大小：2,164 字节。
- 修改时间：2026-07-11 00:58:46。
- SHA256：
  `B455034DC7F1755AA979DCF9B09A7563E129BEE4C2E246CD2D27D0279CCE167A`。
- 验收前后未删除、覆盖或迁移该文件。
- 未修改真实配置、真实项目、用户视频、系统 DPI 或 ACL。
- `E:\codex\QuickRec-Lite` 保持 `lite-master` 干净。

## 11. 自动压力与长时媒体补证

### 11.1 8+8 轨、100 片段与 30 分钟

受控项目：

```text
E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\stress-8x8-100
```

| 项目 | 结果 |
| --- | --- |
| 视频轨 / 音频轨 | 8 / 8 |
| 片段数 | 100 |
| 时间线总时长 | 1,800,000,000 微秒，精确 30 分钟 |
| 会话加载 | 2.759 毫秒 |
| 首次离屏界面渲染 | 30.856 毫秒 |
| 55 次连续命令 | 1,134.198 毫秒 |
| 50 次撤销 | 916.007 毫秒 |
| 50 次重做 | 990.211 毫秒 |
| 撤销历史上限 | 精确限制为 50 步 |
| 结果一致性 | 操作后仍为 16 轨、100 片段、30 分钟 |

结构化证据：

```text
E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\stress-8x8-100\evidence\D10-stress-8x8-100-report.json
```

该项证明模型、事务和 Qt 画布压力基线成立；离屏截图不替代 RC4 打包产物的
真实拖放和可用性验收。

### 11.2 长时播放与音频

当前 PyAV 生产路线再次执行统一技术门禁：

| 项目 | 结果 |
| --- | --- |
| 启动 | 4.604 毫秒，通过 1.5 秒门槛 |
| 最慢随机跳转 | 33.201 毫秒，通过 500 毫秒门槛 |
| 暂停 | 2.011 毫秒，通过 200 毫秒门槛 |
| 30 秒起始音画偏差 | 0 毫秒 |
| 30 秒漂移增量 | 16 毫秒，通过 20 毫秒门槛 |
| 10 分钟漂移增量 | 0 毫秒，通过 20 毫秒门槛 |
| 四路音频混合 | 48 kHz、双声道、有限值 |
| 真实设备输出 | PortAudio 写入 12,000 帧 |
| 资源释放 | 线程增量 0、媒体子进程增量 0 |
| 音频设备不可用 | 3 项定向状态与 UI 测试通过 |

证据：

```text
E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\D10-RC4-pyav-longrun-report.json
```

该项证明媒体技术门禁与硬件输出路径成立；用户实际听音和 RC4 打包 GUI
连续 10 分钟播放仍属于人工补证。

### 11.3 RC5 长时间线完整适配

RC4 在 30 分钟压力项目中点击“适配完整时间线”后受 25% 最小缩放限制，只能
显示前约 1 分 30 秒。修复采用共享缩放边界后，RC5 使用 8 条视频轨、8 条音频轨、
100 个片段和 30 分钟总时长的打包 GUI 夹具完成定向复验：

| 项目 | 结果 |
| --- | --- |
| 打包 GUI 适配比例 | 0.6% |
| 时间标尺范围 | 完整覆盖 00:00 至 30:00 |
| 轨道 / 片段 | 16 轨 / 100 片段 |
| 源码大视口比例 | 1.3%，重开窗口后保持 |
| 打包证据 | `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-fit-30min-8x8-100.jpg` |

该项关闭“完整时间线无法适配”的发布阻塞，但不替代真实片段拖放、吸附和
主观压力交互验收。

### 11.4 RC5 布局、交互规则与恢复边界

RC5 打包 GUI 已实际验证分隔条鼠标拖动、“专注时间线”和“放大预览”，压力项目
在专注模式下可显示全部 16 条轨道。方向键微调使分隔条移动 12 像素，双击后
恢复默认边界。截图位于：

```text
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-splitter-mouse.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-focus-timeline2.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-enlarge-preview.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-splitter-keyboard-printwindow.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-splitter-doubleclick2-printwindow.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-packaged-clip-drag-saved.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-packaged-clip-drag-undo.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-packaged-drag-report.json
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-button-add-material.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-button-add-undo.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-track-move-down.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-native-material-drag.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-track-add.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-track-add-rename-move-undo.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-unknown-version-readonly.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-corrupt-with-backup-restored.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-corrupt-no-backup-rebuilt-empty.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-archived-project-readonly.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-project-material-remove-confirm.png
E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-project-material-removed-source-preserved.png
```

RC5 打包 GUI 中，首个视频片段实际从 0 秒移动到 4.9 秒，关联音频片段同步移动并
自动保存。点击真实“撤销”按钮后，两者均恢复到 0 秒；与操作前备份相比，时间线
语义完全恢复，仅项目 `updated_at` 发生变化。

同一受控素材通过按钮连续加入两次后，时间线分别新增两组关联视频/音频片段，
片段数由 100 增至 104；两次撤销后恢复为 100。首条视频轨下移及撤销也完成，
轨道顺序恢复且未改动片段语义。

同一素材通过原生拖放落到 2.33 秒后生成关联视频/音频片段并自动保存；撤销后
恢复原始空时间线。新增视频/音频轨、重命名“旁白轨”、上移、删除和多步撤销
均在 RC5 打包 GUI 中完成，最终恢复操作前 2 轨数据。

恢复与只读 GUI 抽样已验证：

- 未知时间线版本在项目页禁用“进入剪辑”，不覆盖项目文件；
- 归档项目可进入剪辑工作台只读查看，全部编辑入口禁用，文件哈希不变；
- 损坏时间线使用有效 `.bak` 恢复后可播放，原损坏文件另行保留；
- 无备份时取消不改文件，确认后保留损坏副本并创建空时间线，项目素材仍存在。
- 中央素材移动后显示缺失，取消重新定位不改索引，中文空格路径重新定位后恢复
  可用；从项目移除素材时，取消不改项目，确认仅移除项目引用，原视频和中央
  素材索引均保留。

补充定向测试结果：

| 范围 | 结果 | 主要覆盖 |
| --- | --- | --- |
| 多轨交互与布局 | 9 passed | Qt 鼠标拖动、吸附/Alt 关闭吸附、轨道兼容、同轨冲突、跨轨移动、原子回滚、16 轨/100 片段、键盘与双击复位 |
| 缺失、恢复与只读 | 14 passed | 素材移除事务、归档拒写、损坏恢复、未知版本只读、重新定位路径 |
| 录制协调与资源释放 | 11 passed | 三种录制入口、双工作台隐藏/恢复、诊断跳转、播放释放 |
| 既有能力分域回归 | 400 passed，18 subtests passed | 项目、素材、首帧、录制、音频配置、FPS、设置、诊断、托盘、快捷键和工作台 |

片段拖动、按钮/原生加入、轨道管理、关联组自动保存与撤销，以及重新定位、
素材移除、归档/未知版本只读和有/无备份恢复均已有打包 GUI 证据。冲突拒绝、
长撤销链以及真实音视频设备仍需对应验收；自动化结果不替代实际听音。

## 12. D10 闭合状态

1. 同轨重叠拒绝和跨类型拒绝已通过 RC13 打包 GUI 负向抽样，拒绝反馈明确，
   项目文件 SHA256 前后不变。
2. RC8 连续 10 分钟播放及资源曲线已通过；RC13 四路活动音频已完成生产混音
   分析、播放日志核对和用户实际扬声器听音。
3. 剪辑工作台录制中禁写和停止后解锁，以及区域/窗口、四种捕获音频和
   30/60/120 FPS 回归均已通过 RC13。
4. 重新定位、素材移除确认、归档/未知版本只读、损坏恢复和外部冲突恢复均已
   通过。

## 13. 当前判断

D9 自动化、静态检查、覆盖率、打包结构和媒体工具已通过。RC13 是当前唯一
候选；D10 的双工作台、编排、短时与长时播放、缺失恢复、资源释放、三档缩放、
全屏/区域/窗口录制、四种捕获音频、30/60/120 FPS 和录制期禁写/停止后解锁
已有真实证据。同轨重叠和跨类型轨道拒绝已通过真实拖放，四路时间线音频也已
完成实际扬声器听音，因此当前结论为**通过**，v1.9.2 可进入发布收口。

## 14. RC8 播放状态与终点回归

RC7 之后修复了活动项目快照刷新、非活动解码器释放和暂停按钮图标同步。任何
早于 RC8 的候选都不再作为最终发布对象。

### 14.1 自动验证

| 检查 | 结果 |
| --- | --- |
| 播放按钮与 2 秒终点定向测试 | 7 项通过 |
| 播放 UI、运行时与查询联合回归 | 29 项通过 |
| 50 组连续视频/音频片段解码器边界 | 通过；活动解码器集合始终各不超过 1 个 |
| 相关播放联合回归 | 39 项通过 |
| 标准全量 | 861 项通过，27 项取消选择，56 项子测试通过 |
| 总体覆盖率 | 83.31%，通过 80% 门禁 |
| 时间线核心增量覆盖率 | 85.77%，通过 85% 门禁 |
| 播放协调增量覆盖率 | 80.96%，通过 80% 门禁 |
| Packaging | 15 项通过，872 项取消选择 |
| Ruff | 通过 |
| Mypy | 43 个源文件通过 |
| Compileall | 通过 |

2 秒单素材 GUI 单元回归明确验证：

- 时间线总时长为 `2,000,000 µs`；
- 时钟推进到素材结束后，状态为 `ended`；
- 播放头固定在 `00:02.000 / 00:02.000`；
- 播放计时器停止；
- 状态文字为“播放结束”；
- 按钮恢复播放文字与播放图标。

### 14.2 RC8 候选身份

| 项目 | 值 |
| --- | --- |
| 候选目录 | `E:\QRtest\QuickRec-v1.9.2-rc8-dist\QuickRec` |
| EXE | `E:\QRtest\QuickRec-v1.9.2-rc8-dist\QuickRec\QuickRec.exe` |
| EXE SHA256 | `878C711A7326D42958679458457156FC178E814B8F53A12DB9D54FC71F80410A` |
| EXE 大小 | 7,232,333 字节 |
| 分发目录 | 317 个文件，496,960,981 字节 |
| FFmpeg SHA256 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| FFprobe SHA256 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |
| 隔离验收目录 | `E:\QRtest\QuickRec-v1.9.2-rc8-acceptance` |

包内 FFprobe 已解析中文空格路径的 2 秒 H.264/AAC 样本。RC8 还建立了独立
“单素材 2 秒终点验证”项目，其项目文件包含一组 2 秒关联视频/音频片段，
用于和 30 分钟压力编排分开验收。

### 14.3 当前边界

- RC8 打包 GUI 已确认暂停图标和 2 秒终点。
- 连续 10 分钟资源曲线已闭合，非活动解码器不会持续累积。
- 后续候选继续处理外部冲突、撤销/重做和录制协调。

## 15. RC9-RC13 录制协调与最终候选

### 15.1 RC9-RC10 补充验收

- RC9 实际验证外部冲突被拒绝，重新加载项目后可继续编辑。
- RC10 实际验证七步撤销/重做、新命令清空重做分支和重复轨道换序后的选择
  稳定性。
- RC10 在录制期间尝试时间线操作后项目发生变化，确认运行时仅展示只读文案
  而没有真正阻止命令；该候选失效。
- `INVALID-D10-RC10-duplicate-process-test-contamination.jpg` 是验收工具启动
  重复实例造成的污染证据，不计为 QuickRec 产品缺陷。

### 15.2 RC11-RC13 修复演进

| 候选 | 自动/GUI 结果 | 状态 |
| --- | --- | --- |
| RC11 | 录制中编辑控件禁用；停止保存后仍保持锁定 | 失效 |
| RC12 | 日志解锁成功；标题只读状态未刷新 | 失效 |
| RC13 | 录制中禁写；停止后标题、按钮和编辑操作恢复 | 当前候选 |

RC13 真实桌面证据：

- 录制期间标题为“项目文件只读 · 编辑操作已禁用”，结构编辑按钮均禁用。
- 停止保存后标题恢复“已自动保存”，开始录制重新可用；选中现有轨道后
  重命名、移动和删除恢复可用。
- 受控项目 SHA256 前后均为
  `82A6B24B7E60F59F150DBC1B506664FE3BB35A163917713B4374965C0F5EF1FE`。
- 日志明确记录 `active=True` 和保存后的 `active=False`。
- 截图：
  - `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-recording-editor-read-only.jpg`
  - `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-recording-stop-editor-unlocked.jpg`
- 真实用户中央索引 SHA256 保持
  `B455034DC7F1755AA979DCF9B09A7563E129BEE4C2E246CD2D27D0279CCE167A`。
- 验收结束后无残留 QuickRec 进程。

### 15.3 当前发布判断

录制协调、录制模式回归、非法拖放拒绝和四路音频实际听音的发布阻塞均已关闭：

1. 四路受控项目使用 4 个同时活动的音频源，生产混音块为非零有限值，并包含
   C4、E4、G4、C5 四个目标频率。
2. Windows 输出切换到实际扬声器 `HECATE G1500 BAR` 并重启 RC13 后，用户
   确认播放有声音。
3. 日志记录 `audio_sources=4`、`muted=False`、12 秒正常结束和资源释放成功。

因此 RC13 当前为**验收通过的候选包**，D10 结论为**通过**。重复启动同一 EXE
可创建第二应用进程的问题已登记为 `BUG-009`，按本版 PRD 边界作为非阻塞已知
限制，建议后续独立治理。

非法拖放证据：

- 同轨重叠提示“目标位置与同轨道现有片段重叠”；
- 跨类型提示“视频片段和音频片段只能在同类轨道之间移动”；
- 两次操作前后项目 SHA256 均为
  `82A6B24B7E60F59F150DBC1B506664FE3BB35A163917713B4374965C0F5EF1FE`；
- 截图位于 RC13 `evidence` 目录，具体路径与哈希见
  `manual-verification.md` 的 16.4 节。
