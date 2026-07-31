# QuickRec Full v1.9.5 D9 手动验收记录

## 1. 当前结论

| 项目 | 结果 |
| --- | --- |
| 验收阶段 | D9 GUI、真实媒体、DPI 与回归验收 |
| 总体结论 | 通过 |
| 当前完成度 | 31/31 项全部通过 |
| 发布判断 | 可进入发布收口 |
| 发布阻塞 | 无 |
| 验收日期 | 2026-07-31 |

RC2 曾完成大部分剪辑工作台与导出链路验收，但在真实录制中发现
`BUG-195-01`：工具栏宽度动画结束后回落到屏幕垂直中部。RC2 因此失效。
修复只涉及工具栏位置计算与对应测试；时间线、项目、播放和导出证据在全量
回归通过后继承。RC3 已重新打包，并完成三种录制模式的定向复验。

## 2. 验收对象

| 项目 | 内容 |
| --- | --- |
| 产品 | QuickRec Full v1.9.5 |
| 分支 | `test` |
| 基线 HEAD | `b3b8267e1950b8e2b9efc6d28d29b501189fd7af` |
| 工作区 | 包含尚未提交的 v1.9.5 实现与文档 |
| GUI | `E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec\QuickRec.exe` |
| GUI SHA256 | `705B227FE33F31D4EE650334D607CAAA919FC3D1B44C633CEA1E5B75B3B4A226` |
| CLI | `E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec\QuickRecCLI.exe` |
| CLI SHA256 | `1133802A8BB999B7CE198BB9EBF3F4F9D7C8160C9C9798C0248E28F940F0E386` |
| FFmpeg SHA256 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| FFprobe SHA256 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |
| RC3 验收根目录 | `E:\QRtest\QuickRec-v1.9.5-rc3-acceptance` |
| RC2 继承证据 | `E:\QRtest\QuickRec-v1.9.5-rc2-acceptance\evidence` |
| 验收时正式版本 | v1.9.4 |
| 回滚点 | tag `v1.9.4` / `b3b8267e1950b8e2b9efc6d28d29b501189fd7af` |

## 3. 环境保护

- RC3 使用独立 `APPDATA`、`LOCALAPPDATA`、`TEMP`、录制和项目目录。
- 未删除、覆盖或清空真实用户中央素材索引。
- 未修改系统 ACL、真实保存目录或全局环境变量。
- Windows 系统显示缩放已依次实测 100%、125% 和 150%，完成后恢复为原始
  100%；进程级 `QT_SCALE_FACTOR` 证据只作为补充。
- 麦克风补证期间曾将 Windows 默认输入从 `HECATE GS03 GAMING SOUND CARD`
  临时切换为 `HECATE G1500 BAR`；测试结束后已恢复 GS03，并关闭声音设置。
- 2026-07-31，使用恢复后的默认 GS03 完成麦克风和双音频最终补证；测试均在
  隔离目录进行，没有修改真实用户索引、配置或素材。
- 验收结束后已停止全部 RC3 QuickRec 进程。
- `E:\codex\QuickRec-Lite` 保持干净，未修改。

## 4. D9 验收结果

| 项目 | 结论 | 实际结果与证据 |
| --- | --- | --- |
| D9.1 候选 EXE | 通过 | RC3 GUI 路径、大小、时间和 SHA256 已锁定 |
| D9.2 CLI 与媒体工具 | 通过 | frozen doctor、editing smoke、export smoke 通过；FFmpeg/FFprobe 哈希已锁定 |
| D9.3 隔离环境 | 通过 | `E:\QRtest\QuickRec-v1.9.5-rc3-acceptance` |
| D9.4 Space 播放/暂停 | 通过 | RC2 GUI 实测播放与暂停，焦点离开输入框后生效 |
| D9.5 焦点规则 | 通过 | 输入框保护、弹窗 Esc、按钮操作和时间线快捷键未冲突 |
| D9.6 帧/秒/分割快捷键 | 通过 | `D9-C-frame-and-second-navigation.png`、`D9-C-ctrl-b-linked-split.png` |
| D9.7 Delete / Shift+Delete | 通过 | 普通删除保留空隙，全局波纹删除收缩后续内容 |
| D9.8 Ctrl+L、撤销重做、Esc | 通过 | 解绑、撤销重做和取消均有 GUI 证据 |
| D9.9 解绑与独立移动 | 通过 | `D9-B-unlinked-independent-move.png` |
| D9.10 独立裁剪和分割 | 通过 | `D9-D-unlinked-independent-trim.png`、`D9-D-unlinked-independent-split.png` |
| D9.11 独立删除 | 通过 | `D9-D-unlinked-independent-delete.png` |
| D9.12 严格重新关联 | 通过 | 候选过滤、成功重建关联和无候选状态已验证 |
| D9.13 有效轨道拖放 | 通过 | 使用真实 Windows 指针拖入时间线，片段成功写入并自动保存；`native-drag\evidence\D9-native-drag-auto-track.png` |
| D9.14 冲突/锁定轨道拖放 | 通过 | 锁定轨真实拖放显示“目标轨道已锁定”，项目轨道和片段数量不变；冲突事务由自动测试覆盖；`native-drag\evidence\D9-native-drag-locked-feedback.png` |
| D9.15 条件性自动建轨 | 通过 | 所有兼容轨不可用时真实拖放自动创建视频轨；项目由 3 轨/4 片段更新为 4 轨/5 片段并落盘 |
| D9.16 8+8 轨上限 | 通过 | `D9-G-8x8-100clips-30minutes.png` |
| D9.17 Esc/拖出画布取消 | 通过 | Esc 取消已通过；真实拖出时间线后项目哈希、mtime、大小、轨道数和片段数均不变；`native-drag\evidence\D9-native-drag-out-cancel.png` |
| D9.18 30 FPS 帧时间 | 通过 | 帧输入、跳转、边界换算通过 |
| D9.19 60 FPS 帧时间 | 通过 | `00:00:00:59` 映射到约 `0.983 s` |
| D9.20 120 FPS 帧时间 | 通过 | `00:00:00:119` 映射到约 `0.991 s`，截断误差小于 1 ms |
| D9.21 8+8 轨、100 片段 | 通过 | 压力项目可打开、操作并定位末端 |
| D9.22 30 分钟与 50 步历史 | 通过 | 30 分钟压力项目 GUI 与历史服务 50 步门禁通过 |
| D9.23 中文、空格、长路径 | 通过 | `中文 空格 压力素材.mp4` 与 frozen CLI/项目路径通过 |
| D9.24 H.264/AAC 与四类音频 | 通过 | 无声、系统声音已有证据；GS03 麦克风样本可听见口述，双音频样本可同时听见系统测试音和口述；两类最终输出均为 H.264/AAC |
| D9.25 最高视频轨一致性 | 通过 | 预览显示最高轨红色画面；导出 1 秒信号为 `Y81/U90/V240` |
| D9.26 空隙/波纹导出 | 通过 | 普通删除 3 秒处黑场；波纹删除 3 秒处为后续素材画面 |
| D9.27 三种模式工具栏位置 | 通过 | RC3 全屏、区域、窗口均为 `left=1113, top=139, 334×48` |
| D9.28 DPI 与 960×640 | 通过 | 同一 RC3 在系统级 100%、125%、150% 下重启实测；工作台、项目页、剪辑工作台和删除确认框无裁切/重叠，960×640 工作台通过，系统已恢复 100% |
| D9.29 临时清理与非归属保护 | 通过 | frozen CLI 超时取消仅保留非归属哨兵；真实 RC3 重启将运行任务恢复为 `interrupted` 并清理归属 `.part`/滤镜文件，哨兵仍存在 |
| D9.30 v1.9.4 回归与 Lite | 通过 | 三类录制、工作台、项目、播放、导出、诊断和全量测试通过；Lite 干净 |
| D9.31 验收文档与判断 | 通过 | 本文件已生成，D9 结论明确为 `31/31` 项全部通过 |

## 5. RC3 录制定向复验

### 5.1 工具栏位置

单显示器有效区域为 `2560×1392`，期望顶部安全位置为 `y=139`。

| 模式 | 工具栏矩形 | 水平中心偏差 | 结果 |
| --- | --- | ---: | --- |
| 全屏 | `1113,139,334,48` | 0 px | 通过 |
| 区域 | `1113,139,334,48` | 0 px | 通过 |
| 窗口 | `1113,139,334,48` | 0 px | 通过 |

证据目录：

```text
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-K-toolbar-position.json
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-K-toolbar-fullscreen-top-safe-area.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-K-toolbar-region-top-safe-area.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-K-toolbar-window-top-safe-area.png
```

### 5.2 录制输出

| 模式 | 文件 | FFprobe |
| --- | --- | --- |
| 全屏 | `QuickRec_20260731_021645.mp4` | H.264，1280×720，60 FPS，203.55 秒 |
| 区域 | `QuickRec_20260731_022403.mp4` | H.264，960×720，60 FPS，27.15 秒 |
| 窗口 | `QuickRec_20260731_022521.mp4` | H.264，1122×720，60 FPS，24.35 秒 |

三个文件均位于：

```text
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\recordings
```

隔离索引 `appdata\QuickRec\recordings.json` 中的 `mode` 分别为
`fullscreen`、`region`、`window`，状态均为 `available`。

## 6. 补证记录与唯一剩余人工项

### 6.1 原生拖放、吸附和自动建轨：通过

使用 RC3、隔离项目和真实 Windows 指针完成原生 Qt 拖放：

- 有效拖入成功提交，自动创建视频轨并自动保存；
- 锁定轨拒绝拖入并显示明确原因，项目保持 3 轨/4 片段；
- 再次有效拖入后项目持久化为 4 轨/5 片段；
- 拖出时间线取消后项目哈希、mtime、大小、轨道数和片段数均不变；
- Esc 取消、冲突规则、8 轨上限和原子撤销继续由既有 GUI/自动测试证据覆盖。

证据：

```text
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\native-drag\evidence\D9-native-drag-auto-track.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\native-drag\evidence\D9-native-drag-locked-feedback.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\native-drag\evidence\D9-native-drag-out-cancel.png
```

### 6.2 麦克风与双音频：最终补证通过

早期补证中，GS03 和临时默认 G1500 虽可被系统与 QuickRec 枚举，但样本接近
数字静音，因此当时没有把初始化成功或存在 AAC 流冒充为听音通过。随后恢复
GS03 为默认麦克风，并使用同一锁定 RC3 的 frozen CLI 重新执行两项测试。

| 验证项 | 麦克风 | 系统声音+麦克风 |
| --- | --- | --- |
| CLI 参数 | `--audio mic` | `--audio both` |
| `actual_audio` | `microphone` | `both` |
| 时长 | `10.04 s` | `10.00 s` |
| 视频 | H.264，1920×1080，30 FPS | H.264，1920×1080，30 FPS |
| 音频 | AAC，48 kHz，2 声道 | AAC，48 kHz，2 声道 |
| 平均音量 | `-42.4 dB` | `-27.1 dB` |
| 峰值音量 | `-24.2 dB` | `-19.6 dB` |
| 实际听音 | 用户确认可听见口述 | 用户确认可同时听见系统测试音与口述 |
| 结论 | 通过 | 通过 |

麦克风样本：

```text
MP4: E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\mic-gs03-retest2-20260731\workspace\output\QuickRec_20260731_134736.mp4
MP4 SHA256: 1E2755AFAFB1B6746357CFA1D45F69E896C864F626925F097196A96D9BFC4766
WAV: E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\mic-gs03-retest2-20260731\evidence\gs03-microphone.wav
WAV SHA256: 750530D94A75935102A1D3BA20E7800639D4CF3DF5A6C9A996F30777D8E1F28D
记录: E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\mic-gs03-retest2-20260731\evidence\record.json
```

双音频样本：

```text
MP4: E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\both-gs03-retest-20260731\workspace\output\QuickRec_20260731_134911.mp4
MP4 SHA256: DCE037E2ACC33BBE7900DE873F770DAB6570D4602FDF5F714DED8F687D03AEF9
WAV: E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\both-gs03-retest-20260731\evidence\gs03-system-and-microphone.wav
WAV SHA256: D4AB6FA05C2F80E30BA1DBCB2E7FA3C102C3F9F4702B639858F5D930575B1A19
记录: E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\both-gs03-retest-20260731\evidence\record.json
```

双音频日志确认同时初始化 G1500 loopback（48 kHz、2 声道）和 GS03 默认
麦克风（48 kHz、1 声道），并生成两份独立源 WAV 后完成混合。捕获过程中出现
过 `SoundcardRuntimeWarning: data discontinuity in recording`，但最终 MP4
正常完成、可解析且两类声音均可听；该告警记录为非阻塞运行时观察项。

最终通过标准已完整满足：不仅存在 AAC 流，而且用户实际听音确认了麦克风口述
以及双音频中的系统声音和口述。

### 6.3 系统级 DPI 与最小窗口：通过

同一 RC3 在 Windows 系统级 125% 和 150% 下分别完全重启。工作台最小窗口、
项目页、剪辑工作台、时间线操作区和项目删除确认框均无裁切、重叠或不可点击
控件。完成后已恢复用户原始 100% 缩放，并确认 QuickRec 进程全部退出。

系统级证据：

```text
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-L-system-dpi-125-workbench-960x640.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-L-system-dpi-125-editor.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-L-system-dpi-150-workbench-960x640.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-L-system-dpi-150-editor.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-L-system-dpi-150-delete-dialog.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-L-system-dpi-restored-100.png
```

### 6.4 取消与中断后的临时文件：通过

- frozen RC3 CLI 使用 `--timeout 0.05` 触发真实超时取消，退出码为 5；
- 取消后输出目录仅保留非归属哨兵，未残留归属 `.part` 或滤镜脚本；
- 构造持久化 `running` 任务及归属临时文件后启动真实 RC3，任务恢复为
  `interrupted`，队列暂停，消息为 `application exited during export`；
- RC3 清理两个归属文件，非归属哨兵保持不变；
- 取消样本哨兵 SHA256：
  `11293257D38871443DE6CD65B8F5BA51076C1DB1EEF216F2EA3FEAF805861C7B`。

证据：

```text
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\temp-cleanup-cancel
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\interruption-recovery
```

## 7. 发布判断

当前 D9 为 **通过（31/31）**：

- `BUG-195-01` 已关闭；
- 自动化、打包、三类录制、核心剪辑与导出链路没有发布阻塞；
- 原生拖放、系统级 DPI 和取消/中断清理补证已通过；
- 无声、系统声音、麦克风和双音频四类音频均已闭合；
- GS03 麦克风口述和双音频中的系统测试音+口述均完成真实听音；
- D9 没有延期项、待补证项或发布阻塞。

因此 v1.9.5 **可以进入发布收口**。本结论不等于已经提交或发布；commit、
push、tag、压缩包和 GitHub Release 仍需用户单独授权。
