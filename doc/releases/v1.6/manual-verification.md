# QuickRec Full v1.6 GUI 手动验收

> 状态：通过（实现类发布阻塞已关闭；持久重试入口已确认延后；三档 DPI 人工补证已通过）
> 本文是 D7 GUI 验收唯一操作清单；自动化通过不能代替本清单。

## 1. 锁定验收对象

- 分支：`feature/v1.6-material-library`
- 构建时 HEAD：`73ad5a7`（工作区包含尚未提交的 v1.6 与 Bugfix 改动）
- EXE：`E:\QRtest\QuickRec-v1.6-bugfix3-dist\QuickRec\QuickRec.exe`
- EXE 修改时间：`2026-07-12 01:40:24 +08:00`
- EXE 大小：`6,859,907` 字节
- EXE SHA256：`F1C8F2F971D5DD62067955B939D5DB9293C13DA930D1DFC653007F59596392E8`
- 完整目录大小：`369,558,179` 字节
- 旧候选 SHA256 `3D50ACCDE7D6CF06579A4AE5AEBE92D3A0B605C633D5AEC9D65B783842424C85` 仅保留失败记录；对应二进制目录已在最终候选锁定后清理。
- 全屏 smoke：`E:\QRtest\v1.6-acceptance\QuickRec_20260711_005904.mp4`

验收开始前必须重新计算 EXE SHA256；不一致时停止验收，不能混用证据。

## 2. 隔离环境

在新的 PowerShell 窗口执行：

```powershell
$AcceptanceRoot = 'E:\QRtest\QuickRec-v1.6-bugfix-acceptance'
$env:APPDATA = Join-Path $AcceptanceRoot 'AppDataRoaming'
New-Item -ItemType Directory -Force $env:APPDATA | Out-Null
New-Item -ItemType Directory -Force (Join-Path $AcceptanceRoot 'videos-a') | Out-Null
New-Item -ItemType Directory -Force (Join-Path $AcceptanceRoot 'videos-b') | Out-Null
Get-FileHash 'E:\QRtest\QuickRec-v1.6-bugfix3-dist\QuickRec\QuickRec.exe' -Algorithm SHA256
& 'E:\QRtest\QuickRec-v1.6-bugfix3-dist\QuickRec\QuickRec.exe'
```

验收期间的中央索引应位于：

```text
E:\QRtest\QuickRec-v1.6-bugfix-acceptance\AppDataRoaming\QuickRec\recordings.json
```

不要删除真实 `%APPDATA%\QuickRec\recordings.json`。本次基础启动曾按产品逻辑迁移真实旧历史，该文件需要由用户决定是否继续保留。

## 3. 自动化与打包前置证据

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 全量测试 | 通过 | `333 passed, 24 deselected, 22 subtests passed` |
| 全量 coverage | 通过 | `83.01%` |
| 媒体元数据 coverage | 通过 | `83.15%` |
| ruff | 通过 | `python -m ruff check src tests` |
| mypy | 通过 | 15 个源文件 |
| compileall | 通过 | `python -m compileall -q src tests` |
| packaging 标记测试 | 通过 | `12 passed` |
| PyInstaller | 通过 | 独立 dist/work 目录，构建耗时约 47 秒 |
| 包内 ffprobe | 通过 | 可解析 H.264、640×480 受控视频 |
| EXE 基础启动 | 通过 | 进程保持运行 4 秒后正常结束 |
| 全屏硬件 smoke | 通过 | `OK: video stream ok` |

## 4. 素材库入口与录制回归

### V16-U1 双入口

- [x] 空闲托盘菜单显示“素材库”，不再显示“最近录制”。
- [ ] 录制中托盘菜单仍显示停止、暂停等原操作，并保留“素材库”。
- [x] 完成一条录制后，结果条显示“素材库”。
- [x] 两个入口打开同一个素材库窗口体验；关闭后可再次打开，不产生异常重复窗口。

### V16-G1 三种录制模式

- [x] 全屏录制 MP4 可播放，并已由上一轮三个样本及 FFprobe 证明。
- [x] 区域录制尺寸和画面正常。
- [x] 窗口录制内容与所选资源管理器窗口一致。
- [x] 三种模式的新记录均进入隔离 APPDATA 中的中央素材索引。

### V16-G2 四种音频

- [x] 无声录制。
- [x] 系统声录制。
- [x] 麦克风录制。
- [x] 系统声 + 麦克风录制。
- [x] 已生成的视频可解析，素材详情中的音频来源与实际选择一致。

## 5. 中央索引与素材详情

### V16-I1 跨保存路径

1. 设置保存目录为 `videos-a`，完成一条录制。
2. 设置保存目录为 `videos-b`，完成一条录制。
3. 打开素材库。

- [x] 多个录制目录的视频同时出现在素材库。
- [x] 中央索引只有一个，路径位于隔离 APPDATA。
- [x] 本轮抽样记录包含时长、分辨率、FPS、模式、音频和文件大小。

### V16-I3 分页与状态

- [x] 默认最多显示 50 条。
- [x] 每次“加载更多”增加 50 条，最多 200 条。
- [ ] 空素材库显示“暂无素材”。
- [x] 移动一个测试 MP4 后显示“文件已移动或删除”。
- [x] 无法解析元数据的受控文件显示“元数据不完整”。
- [x] 选中素材后右侧详情同步。
- [ ] 复制路径得到完整绝对路径。

## 6. 迁移、恢复与重建

### V16-M1 当前路径首次迁移

1. 在隔离保存目录准备 v1.5 `QuickRecMetadata\recordings.json` 和对应视频。
2. 关闭并重新启动验收包。

- [x] 首次迁移显示新增、重复和跳过摘要。
- [x] 旧索引 SHA256 前后完全一致。
- [x] 再次启动不重复新增或重复主动提示。

### V16-M4 手动导入

- [ ] 点击“导入旧目录”，选择另一个 v1.5 保存目录。
- [ ] 先显示预览摘要；取消时中央索引不变。
- [ ] 再次操作并确认后一次性写入中央索引。

### V16-R1 损坏恢复

- [x] 在受控索引已有 `.bak` 后损坏主 JSON。
- [x] 重启后自动恢复最近有效备份。
- [x] 损坏原件按时间戳归档。
- [ ] 无有效备份时不创建空索引覆盖原件，并可使用“重建目录”。

### V16-R4 目录重建与取消

- [x] 所选目录同时准备 `QuickRec_*.mp4`、普通 MP4 和子目录 QuickRec 视频。
- [x] 只发现当前层级 `QuickRec_*.mp4`。
- [x] 扫描期间窗口保持响应。
- [x] 取消后中央索引不变。
- [ ] 候选重新定位必须逐项确认，确认前不修改路径。

## 7. 文件操作

### V16-L1 单项重新定位

- [ ] 为缺失素材选择新的 MP4。
- [ ] 成功后路径和元数据更新，素材 ID 与原始录制时间不变。
- [ ] 选择已被其他素材使用的路径时不覆盖原记录。

### V16-U4 仅移除索引

- [x] “从素材库移除”显示确认说明。
- [x] 确认后记录消失，实际 MP4 仍存在。
- [x] 取消时记录和视频都不变。

### V16-U5 Windows 回收站

- [x] 对受控测试 MP4 点击“删除视频文件”。
- [x] 确认文案明确说明移入 Windows 回收站且不删除其他文件。
- [x] 确认后原路径文件消失、E 盘回收站新增项目且索引记录被移除。
- [x] 同目录诊断日志、旧索引和旁车文件保持不变。
- [x] 取消时索引和视频保持不变。

## 8. 失败降级

### V16-F1 中央索引不可写

1. 备份隔离中央索引与 ACL。
2. 安全设置隔离索引目录不可写。
3. 完成一条录制。

- [x] MP4 仍保存成功。
- [x] UI 未误报录制失败，日志和通知均记录“录制已保存”。
- [x] 素材索引失败被单独记录。
- [x] 结果条提供“重试入库”；用户多次点击后日志出现多次重试写入尝试。
- [ ] 恢复权限后重试成功，按钮恢复为“素材库”。
- [x] 日志包含写入失败上下文，不包含视频或音频内容。
- [x] 测试后恢复隔离索引目录结构和配置。

## 9. 设置、诊断、DPI 与边界

- [ ] 设置页可打开、保存并在重启后保持。
- [x] v1.4.1 复制诊断、打开日志目录和导出诊断文件正常。
- [x] 100%、125%、150% DPI 下冷启动素材库，主要窗口和操作按钮均可访问。
- [x] 长文件名和长路径未遮挡右侧操作按钮；列表必要时提供横向滚动。
- [x] QuickRec Lite 工作区保持干净。
- [ ] WGC、120 FPS、完整工作台和 AI 未被误实现为 v1.6 运行时功能。

## 10. D7 第一批实际结果（2026-07-11）

### 10.1 验收身份与环境

- 验收包：`E:\QRtest\QuickRec-v1.6-dist\QuickRec\QuickRec.exe`
- SHA256：`3D50ACCDE7D6CF06579A4AE5AEBE92D3A0B605C633D5AEC9D65B783842424C85`
- 分支：`feature/v1.6-material-library`
- 构建时 HEAD：`73ad5a778ff6e27a399d016f4ebb749ddc78438b`
- 隔离 APPDATA：`E:\QRtest\QuickRec-v1.6-acceptance\AppDataRoaming`
- 中央索引：`E:\QRtest\QuickRec-v1.6-acceptance\AppDataRoaming\QuickRec\recordings.json`
- 日志副本：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\D7-first-batch-quickrec.log`
- 元数据对照：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\D7-first-batch-metadata.json`
- 音量分析：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\D7-first-batch-audio-volume.txt`

### 10.2 GUI 基础链路

| 验收项 | 实际结果 | 证据 | 结论 |
| --- | --- | --- | --- |
| 启动、托盘与素材库 | 锁定 EXE 正常启动；用户从托盘打开素材库；窗口可关闭并再次打开，未出现重复窗口 | Computer Use 本轮桌面操作；中央索引共 13 条 | 通过 |
| 结果条入口 | 录制完成结果条显示“素材库” | Computer Use 本轮桌面截图 | 通过 |
| 两入口完整点击闭环 | 托盘入口与结果条入口均能打开素材库，关闭后可再次打开 | 用户于 2026-07-11 手动复测确认 | 通过 |
| 素材库布局 | 列表、详情、操作按钮及 13/13 计数可见，无明显裁切、重叠或乱码 | Computer Use 本轮桌面截图 | 通过 |
| 设置与诊断 | 设置页可打开；诊断分组存在；复制、打开目录、导出均成功 | 日志 02:13:33、02:14:15、02:14:34；导出文件见下 | 通过 |

诊断导出文件：`E:\QRtest\QuickRec-v1.6-acceptance\diagnostics\diagnostic_20260711_021434.txt`。文件为严格 UTF-8，可读，包含 v1.6 和隔离环境上下文。

### 10.3 录制与元数据精确核对

| 模式/音频 | 文件 | 索引时长 | FFprobe 时长 | 误差 | 分辨率 | FPS | 音频流 | 结论 |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- |
| 区域/无声 | `videos-a\QuickRec_20260711_015125.mp4` | 75.491601 秒 | 75.366667 秒 | 0.124934 秒 | 854x374 | 30 | 0 | 通过 |
| 窗口/无声 | `videos-a\QuickRec_20260711_015451.mp4` | 3.202212 秒 | 3.100000 秒 | 0.102212 秒 | 852x480 | 30 | 0 | 通过 |
| 全屏/系统声 | `audio-system\QuickRec_20260711_015634.mp4` | 30.909325 秒 | 30.466667 秒 | 0.442658 秒 | 854x480 | 30 | AAC 48kHz 双声道 | 通过 |
| 全屏/麦克风 | `audio-microphone\QuickRec_20260711_015801.mp4` | 9.859898 秒 | 9.400000 秒 | 0.459898 秒 | 854x480 | 30 | AAC 48kHz 单声道 | 通过（用户补测） |
| 全屏/双音频 | `audio-both\QuickRec_20260711_020129.mp4` | 29.986734 秒 | 29.533333 秒 | 0.453401 秒 | 854x480 | 30 | AAC 48kHz 三声道 | 通过（用户补测） |

所有抽样文件的索引路径、宽高、FPS、文件大小、模式、音频模式和存在状态均与文件系统及 FFprobe 一致。时长误差范围为 `0.102212-0.459898` 秒，均小于本轮采用的 0.5 秒容许值。

- 区域关键帧：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\D7-B-region-frame.png`
- 窗口关键帧：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\D7-B-window-frame.png`
- 系统声样本平均音量 `-31.9 dB`、峰值 `-21.1 dB`，可证明受控系统测试音被捕获。
- 自动采集的麦克风样本平均音量 `-84.3 dB`、峰值 `-68.0 dB`，只证明单声道结构；用户随后使用真实麦克风输入手动复测，确认语音可听，结论更新为通过。
- 双音频样本为三声道，平均音量 `-33.6 dB`、峰值 `-21.0 dB`；用户随后手动复测确认系统声音与麦克风语音均可听，结论更新为通过。

### 10.4 第一批人工补证

用户于 `2026-07-11` 确认以下项目均已通过：

- 录制结果条“素材库”入口可以正常打开素材库窗口。
- 麦克风模式录制后可听到有效语音，素材详情音频模式正确。
- 系统声音加麦克风模式录制后，两路内容均可听，素材详情音频模式正确。

本次补证由用户在锁定验收包上手动完成，未提供新的截图、MP4 或 FFprobe 文件路径；结论依据用户明确验收确认记录。

### 10.5 尚未覆盖

本轮未执行 v1.5 迁移、备份恢复、目录重建、重新定位、仅移除索引、Windows 回收站、失败降级与重试入库、200 条上限和 100%/125%/150% DPI。这些项目保持待验证，不能据此进入发布收口。

### 10.6 环境恢复

- 已停止全部 QuickRec 进程。
- 隔离配置已恢复为保存目录 `videos-a`、音频模式 `none`。
- 真实 `%APPDATA%\QuickRec\recordings.json` 验收后 SHA256 仍为 `B455034DC7F1755AA979DCF9B09A7563E129BEE4C2E246CD2D27D0279CCE167A`，大小仍为 2164 字节，修改时间仍为 `2026-07-11 00:58:46`。
- QuickRec Lite 工作区保持干净。

## 11. D7 第二批实际结果（2026-07-11）

### 11.1 验收身份

- 实际分支：`feature/v1.6-material-library`。任务提示中的 `feature/v1.6-full-foundation` 与 Git 实况不一致，本轮未切换分支。
- HEAD：`73ad5a778ff6e27a399d016f4ebb749ddc78438b`
- 锁定 EXE：`E:\QRtest\QuickRec-v1.6-dist\QuickRec\QuickRec.exe`
- SHA256：`3D50ACCDE7D6CF06579A4AE5AEBE92D3A0B605C633D5AEC9D65B783842424C85`
- 第二批隔离根目录：`E:\QRtest\QuickRec-v1.6-acceptance\second-batch`
- 预检：`evidence\00-preflight.json`
- 环境恢复：`evidence\99-environment-restored.json`

### 11.2 分项结果

| 验收项 | 结论 | 实际结果与证据 |
| --- | --- | --- |
| v1.5 历史迁移 | 通过 | 2 条真实 MP4 迁移成功；GUI 显示 2/2；旧索引哈希不变。证据：`A1-after-first-migration.json`、`A1-material-library.jpg` |
| 重复迁移幂等性 | 通过 | 二次启动前后均为 2 条，中央索引 SHA256 完全一致。证据：`A2-idempotency.json` |
| 备份恢复 | 通过 | 损坏主 JSON 后从 `.bak` 恢复 2 条记录，恢复文件哈希等于备份，并生成损坏归档。证据：`A3-backup-recovery.json` |
| 目录重建 | 未通过 | 普通 MP4 和子目录样本未被扫描，但两个可由包内 FFprobe 解析的视频仍被标记为“元数据不完整”，损坏伪 MP4 也被加入索引。证据：`A4-rebuild-result.jpg`、`B-file-actions.json` |
| 重新定位 | 未通过 | 缺失状态与取消正确；选择损坏 MP4 后仍更新路径并禁用再次定位；选择有效 MP4 后也被标为元数据不完整。证据：`B4-missing-state.jpg`、`B1-invalid-relink-accepted.jpg`、`B1-valid-relink.jpg` |
| 仅移除索引 | 通过 | 取消不变；确认后索引减少，原视频仍存在。证据：`B2-remove-index.jpg`、`B-file-actions.json` |
| Windows 回收站 | 通过 | 取消不变；确认后原路径文件消失、E 盘回收站新增项目、索引减少，未清空回收站。证据：`B3-recycle-result.jpg`、`B1-relink-setup.json`、`A-B-quickrec.log` |
| 索引失败降级 | 通过 | 可逆阻断索引目录时，4.033 秒 H.264 MP4 正常保存并可解析，中央索引未误写，日志明确区分保存成功和索引失败。证据：`C1-recording-saved-index-failed.json`、`C-quickrec.log` |
| 重试入库 | 待验证 | 结果条仅保留 5 秒；用户多次点击时索引目录仍处于阻断状态，日志记录多次失败重试；恢复后结果条已关闭，未形成成功闭环。证据：`C2-retry-window-expired.json`、`C-quickrec.log` |
| 200 条与加载更多 | 通过 | 锁定包真实迁移 201 条并保留最新 200 条；GUI 按 50、100、150、200 展示，200 条时按钮消失，首尾为 `page-200` 和 `page-001`。证据：`D-201-migration.json`、`D-050-items.jpg` 至 `D-200-last-item.jpg` |
| 100%/125%/150% DPI | 部分通过 | 三档均以同一锁定 EXE 冷启动并保存素材库截图，主要控件可访问；未逐档重复所有确认弹窗，长列表状态列需要横向滚动。证据：`D-200-items.jpg`、`E-125-cold-start-active.jpg`、`E-150-cold-start.jpg` |

### 11.3 发布阻塞

1. 打包产物中的目录重建和重新定位无法为实际可解析 MP4 写入时长、分辨率和 FPS。
2. 重新定位接受不可解析 MP4，并把记录改为“元数据不完整”后禁用再次定位。
3. 重试入库尚未在恢复写入条件后形成成功 GUI 闭环。

### 11.4 未覆盖

- 手动“导入旧目录”的预览、取消和确认链路。
- 无有效备份时的恢复失败界面。
- 回收站失败时索引保留。
- 0 条和 1 条分页夹具，以及删除/新增后页码自动修正。
- 三档 DPI 下逐一重复重新定位、移除索引和回收站确认框。

### 11.5 环境恢复

- QuickRec 与 Windows 设置进程均已停止。
- 显示缩放已恢复为 100%，`AppliedDPI=96`。
- 所有临时目录占位和权限等价故障注入均已恢复。
- 真实 `%APPDATA%\QuickRec\recordings.json` 与 `config.json` 的 SHA256、大小和修改时间均与预检一致。
- QuickRec Lite 工作区保持干净。

## 12. 结论规则

- 所有发布阻断项有真实证据：标记“通过”，可进入发布收口。
- 核心链路通过但仍有人工项：标记“部分通过”，不可发布。
- 任一录制模式、视频保存、迁移安全、回收站边界或失败降级失败：标记“未通过”，进入 bugfix。
- 验收完成后更新本文件的实际结果、截图、MP4、JSON 和日志路径，同时只在 `progress.md` 更新状态与阻塞。

## 13. D7 发布阻塞 Bugfix 定向复验（2026-07-11）

### 13.1 新候选身份

- 分支：`feature/v1.6-material-library`
- 构建时 HEAD：`73ad5a778ff6e27a399d016f4ebb749ddc78438b` 加未提交 Bugfix 工作区。
- EXE：原 Bugfix1 候选目录已清理，身份由以下 SHA256 和验收证据保留。
- EXE SHA256：`69D092DDAF48757D4941429AB10D74072EE2E0B9ED07783CA43BE9D7C8F3551F`
- FFprobe：`E:\QRtest\QuickRec-v1.6-bugfix-dist\QuickRec\_internal\ffmpeg\ffprobe.exe`
- FFprobe SHA256：`192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D`
- 隔离目录：`E:\QRtest\QuickRec-v1.6-bugfix-acceptance`
- 旧候选 SHA256 `3D50ACCDE7D6CF06579A4AE5AEBE92D3A0B605C633D5AEC9D65B783842424C85` 已失效，仅保留为失败证据。

### 13.2 定向复验结果

| 验收项 | 结论 | 实际结果与证据 |
| --- | --- | --- |
| 目录重建 | 通过 | 扫描 3 个 MP4：成功 2、失败 1；两个有效文件显示 3 秒、852 × 480，损坏 MP4 未入库，非视频未扫描。证据：`evidence\11-rebuild-preview-2.jpg`、`evidence\12-rebuild-success.jpg` |
| 重新定位损坏文件 | 通过 | 明确提示 FFprobe 不可解析，原索引路径及缺失状态不变，“重新定位”仍可用。证据：`evidence\21-relink-corrupt-rejected.jpg` |
| 重新定位有效文件 | 通过 | 失败后再次选择中文空格路径有效 MP4，路径及 3 秒、852 × 480、30 FPS 完整更新。证据：`evidence\22-relink-valid-success.jpg` |
| 重启持久化 | 通过 | 重启后中央索引仍为 3 条，重新定位路径与完整元数据保持。证据：`evidence\32-index-before-restart.json`、`evidence\40-restart-persistence.jpg` |
| 手动导入 | 通过 | 受控旧索引包含有效 MP4、损坏 MP4、非视频；结果新增 1、跳过 2。证据：`evidence\30-import-preview.jpg`、`evidence\31-import-success.jpg` |
| 重试入库 | 部分通过 | 结果条存续期间可重试；结果条关闭后没有持久恢复入口。该限制已确认进入后续版本，本版不改动且不阻塞发布。 |

### 13.3 当前结论

BUG-V16-D7-001 与 BUG-V16-D7-002 已关闭。持久重试入口已按产品决策延后，不再作为 v1.6 发布阻塞。D7 仍需完成既有非阻塞补证后再判断是否进入发布收口。

## 14. D7 剩余边界与 Bugfix3 复验（2026-07-12）

### 14.1 最终候选身份

- EXE：`E:\QRtest\QuickRec-v1.6-bugfix3-dist\QuickRec\QuickRec.exe`
- EXE SHA256：`F1C8F2F971D5DD62067955B939D5DB9293C13DA930D1DFC653007F59596392E8`
- FFprobe SHA256：`192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D`
- 隔离目录：`E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining`
- 自动验证：全量 340 passed、24 deselected、22 subtests passed；packaging 12 passed；ruff、mypy、compileall、`git diff --check` 通过。

### 14.2 分项结果

| 验收项 | 结论 | 实际结果与证据 |
| --- | --- | --- |
| 无备份损坏恢复 | 通过 | 初始明确显示索引解析失败并保留损坏归档；确认目录重建后成功写入 1 条有效素材。证据：`evidence\50-no-backup-load-failure.jpg`、`54-bugfix2-rebuild-preview.jpg`、`55-no-backup-rebuild-one-item.jpg` |
| 1 条边界 | 通过 | 显示 `1 / 1`，时长 3 秒、分辨率 852 × 480，操作区正常。证据：`evidence\55-no-backup-rebuild-one-item.jpg` |
| 0 条边界 | 通过 | 显示“暂无素材”，右侧所有详情字段清空为 `-`，操作按钮禁用。证据：`evidence\58-bugfix3-zero-state.jpg` |
| 回收站失败 | 通过 | 独立进程锁定测试视频后，界面显示 `WinError 32`；视频仍存在、索引仍保留 1 条。证据：`evidence\59-recycle-failure-keeps-index.jpg`、`60-recycle-failure-filesystem.json` |
| DPI 确认框 | 通过 | 用户于 2026-07-13 按 `manual-dpi-verification.md` 完成 100%、125%、150% 下素材库主窗口、重新定位、移除索引和回收站确认框的人工验证，全部通过。 |

### 14.3 当前结论

实现类发布阻塞均已关闭，三档 DPI 人工视觉补证已通过。D7 总体结论更新为“通过”，可以进入发布收口确认点；本轮未执行 commit、push、tag 或 GitHub Release。
