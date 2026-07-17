# QuickRec Full v1.6.1 GUI 手动验收

> 当前状态：`test` 分支手动验收中（核心降级链路、系统声音与双音频已通过）
>
> 对应提交：`8a1ee4710de70d5dd74c2478771a50a762b528ca`
>
> 验收对象：`E:\QRtest\QuickRec-v1.6.1-audiofix2-dist\QuickRec\QuickRec.exe`
>
> 锁定 SHA256：`2CB447709769A8A986B7A48A63C98377803A002ED56892E57F0911661FA3E092`
>
> 证据目录：`E:\QRtest\QuickRec-v1.6.1-acceptance\evidence`

## 1. 开始前

1. 结束所有 QuickRec 进程。
2. 重新计算 EXE SHA256，必须与锁定值一致；不一致立即停止。
3. 备份真实 `%APPDATA%\QuickRec`，记录 `recordings.json` 与 `pending-recordings.json` 的大小、时间和哈希。
4. 使用隔离 APPDATA 和 `E:\QRtest\QuickRec-v1.6.1-acceptance` 下的测试视频目录。
5. 不删除用户真实视频，不修改 QuickRec Lite。

## 2. 核心待入库链路

| 编号 | 操作 | 预期 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| V161-P1 | 制造正式索引不可写后完成录制 | MP4 成功；不误报录制失败；出现一条待入库记录 | 通过 | `videos\QuickRec_20260716_172733.mp4`、`evidence\V161-P1-ffprobe.json`、日志 `17:27:37` |
| V161-P2 | 保持 APPDATA 可写 | 写入 `pending-recordings.json`，不生成多余标记 | 通过 | 日志：`pending enqueue succeeded ... storage=primary`；恢复前主记录 ID `20c73427...` |
| V161-P3 | 仅使主待入库文件不可写 | 视频目录生成 `QuickRecMetadata\Pending\*.json` | 通过 | `videos\QuickRec_20260716_173048.mp4`；日志：`pending fallback marker saved`，ID `bf2a1a17...` |
| V161-P4 | 主文件和视频目录均不可写 | MP4 仍可播放；日志记录双重失败 | 通过 | `videos\QuickRec_20260716_173853.mp4`、`evidence\V161-P4-ffprobe.json`；日志错误码 `PENDING_FALLBACK_WRITE_FAILED` |
| V161-P5 | 恢复故障并重启 | 每条自动重试一次；成功后汇总通知并清理记录 | 通过 | 日志 `17:29:15`、`17:38:02`：正式索引分别增至 2/3 条，待入库项清理；当前主待入库为 0 条 |
| V161-P6 | 故障不恢复并重启 | 不连续弹窗；记录、次数和日志保留 | 通过 | 日志 `17:28:31`：仅执行一次启动重试，`scanned=1 failed=1`，随后无重复重试日志 |
| V161-P7 | 在素材库点击“重试入库” | 只产生一条正式素材，待处理记录消失 | 通过 | 实测样本 `QuickRec_20260716_181537.mp4`；UI 提示“素材已加入素材库”；正式索引 3→4，待入库 1→0；日志 `18:19:30` |
| V161-P8 | 重复重试与重复重启 | 不产生重复待处理或正式素材 | 通过 | 目标路径在正式索引中仅 1 条；待入库清零；此前两轮启动恢复后正式索引同样无重复 |

## 3. 素材库与文件操作

| 编号 | 操作 | 预期 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| V161-U1 | 打开素材库 | 待入库置顶，数量与正式素材独立 | 通过 | 正常启动后托盘入口直接显示；待入库样本位于首行，顶部显示“待入库 1 条 · 素材 3 条（显示 3 条）” |
| V161-U2 | 选中失败项 | 显示失败摘要、次数、时间、路径、模式、音频和媒体信息 | 通过 | 实测显示 00:00:21、1920×1080、30 FPS、全屏、无声、路径、诊断目录、失败原因和已尝试 1 次 |
| V161-F1 | 外部移动待入库视频 | 显示“文件已移动或删除”并允许重新定位 | 通过 | 样本 `QuickRec_20260716_182145.mp4` 外移后“打开”禁用、“重新定位”启用，原路径保持在记录中 |
| V161-F2 | 定位到损坏或非视频文件 | 明确拒绝，原记录不变，仍可再次定位 | 通过 | 选择 `relocate 中文 空格\损坏伪视频.mp4` 后显示 FFprobe `moov atom not found`，原路径未改变且按钮仍可用 |
| V161-F3 | 取消重新定位 | 原记录不变 | 通过 | 文件选择框按 Esc 取消后，待入库 ID、原路径和尝试信息均保持不变 |
| V161-F4 | 选择“移除待处理记录” | 有确认提示；只删除恢复记录，视频仍存在 | 通过 | 文案明确“视频文件不会被删除”；移除后待入库 1→0，`relocate 中文 空格\重新定位 有效视频.mp4` 仍存在（151550 字节） |
| V161-C1 | 构造待入库 200 条和正式素材 200 条 | 两类独立计数和容量 | 通过 | 候选包显示“待入库 200 条 · 素材 200 条”，分批加载依次为 50、100、150、200 条 |
| V161-C2 | 加入第 201 条待入库 | 只淘汰最旧元数据，不删除 MP4 | 通过 | 淘汰 ID `cap-p-000`；`capacity-fixture\evicted-oldest-still-exists.mp4` 保持存在；验收后原索引按哈希恢复 |

## 4. 录制与历史回归

逐项生成真实 MP4，以包内 FFprobe 核对流信息，并确认正式入库或失败降级行为正确：

- [x] 全屏录制：候选包生成并正式入库，1920×1080、30 FPS。
- [x] 区域录制：`videos\QuickRec_20260716_184954.mp4`，4.57 秒、1728×1080、30 FPS，索引模式 `region`。
- [ ] 窗口录制。
- [x] 无声录制：上述候选包录制均无音频流，索引音频模式为 `none`。
- [x] 系统声音录制：audiofix2 候选以受控 880 Hz 测试音完成全屏录制，输出为 48 kHz 双声道 AAC，平均音量 `-24.1 dB`、峰值 `-20.8 dB`。
- [ ] 麦克风录制。
- [x] 系统声音 + 麦克风录制：audiofix2 候选输出双声道 AAC，用户确认系统声音和麦克风语音均可辨识。
- [x] v1.6 历史迁移、备份恢复、目录重建、重新定位、仅移除索引和回收站快速回归。
- [x] v1.4.1 诊断复制、打开目录和导出。
- [ ] 快捷键、托盘、设置保存和退出行为。

## 5. DPI 与中文路径

- [x] 100% DPI：素材库列表、详情、按钮和确认框无裁切。
- [ ] 125% DPI：素材库列表、详情、按钮和确认框无裁切。
- [ ] 150% DPI：素材库列表、详情、按钮和确认框无裁切。
- [x] 长中文与空格路径、长失败摘要无关键重叠或乱码。
- [ ] 验收后恢复原显示缩放。

## 6. 结束恢复

1. 停止所有 QuickRec 进程。
2. 恢复 ACL、APPDATA、配置、显示缩放和临时依赖。
3. 对比真实索引测试前后哈希，确认未被删除或覆盖。
4. 保留 MP4、JSON、日志和截图证据。
5. 确认 QuickRec Lite 工作区仍干净。

## 7. 已执行环境与证据摘要

- GUI 隔离 APPDATA：`E:\QRtest\QuickRec-v1.6.1-acceptance\gui-appdata`。
- 视频与诊断日志：`E:\QRtest\QuickRec-v1.6.1-acceptance\videos`。
- 当前正式索引：5 条；当前主待入库索引：0 条。第 5 条为区域录制样本 `QuickRec_20260716_184954.mp4`。
- 托盘素材库入口已在普通启动方式下实测显示。此前使用 `Start-Process -WindowStyle Hidden` 时窗口被 Windows 启动参数隐藏，属于验收环境干扰，不是产品缺陷；普通启动复验通过。
- 文件操作样本 ID：`56735f5f03c14bfd8361de0ffddfc1dd`；损坏文件被拒绝，有效中文路径定位成功，最终仅移除待处理记录且视频保留。
- 容量夹具备份：`evidence\capacity-backup`；200+200 GUI 抽样完成后已恢复正式索引 4 条、待入库 0 条。
- 窗口录制自动化补证限制：两次由桌面自动化选择目标后，目标 HWND 在正式开始前消失，日志记录“目标窗口已不存在，取消窗口录制”，未生成错误文件。该项保持待验证，不判为产品缺陷或通过。
- 本轮结束时已停止候选包进程；隔离索引文件均已恢复为可写，容量夹具已撤回。
- QuickRec Lite 工作区未修改。

### 非人工补充验收（2026-07-16）

- 运行诊断、设置、迁移、备份恢复、目录重建、重新定位、回收站、素材库和待入库相关回归测试，共 `93 passed`。
- v1.6 正式发布验收已覆盖迁移幂等、备份恢复、目录重建、重新定位、仅移除索引、Windows 回收站、诊断导出和三档 DPI；证据位于 `doc/releases/v1.6/manual-verification.md` 与 `doc/releases/v1.6/verification.md`。
- 本轮涉及的待入库、素材库和索引服务自动回归通过；未修改 v1.4.1 诊断实现和录制音频核心。
- 上述结果用于降低回归风险，不替代 v1.6.1 候选包的窗口录制、有声模式、设置诊断快速 GUI 抽查和 125%/150% DPI 现场补证。

## 8. 剩余人工补证

### 8.1 验收前保护与启动

1. 退出所有 QuickRec 进程。
2. 确认候选包 SHA256 仍为锁定值：

```powershell
Get-FileHash 'E:\QRtest\QuickRec-v1.6.1-audiofix2-dist\QuickRec\QuickRec.exe' -Algorithm SHA256
```

预期：`2CB447709769A8A986B7A48A63C98377803A002ED56892E57F0911661FA3E092`。不一致时立即停止，不得混用证据。

3. 确认并备份隔离索引：

```powershell
$root='E:\QRtest\QuickRec-v1.6.1-acceptance'
New-Item -ItemType Directory -Force "$root\manual-backup" | Out-Null
Copy-Item "$root\gui-appdata\QuickRec\recordings.json" "$root\manual-backup\recordings.json" -Force
Copy-Item "$root\gui-appdata\QuickRec\pending-recordings.json" "$root\manual-backup\pending-recordings.json" -Force
```

4. 使用普通方式启动候选包，不要添加 `-WindowStyle Hidden`：

```powershell
cd E:\codex\QuickRec
$env:APPDATA='E:\QRtest\QuickRec-v1.6.1-acceptance\gui-appdata'
Start-Process 'E:\QRtest\QuickRec-v1.6.1-audiofix2-dist\QuickRec\QuickRec.exe'
```

5. 所有新 MP4、截图和诊断文件保存到 `E:\QRtest\QuickRec-v1.6.1-acceptance`，不要操作真实用户素材。

### 8.2 窗口录制

前置条件：打开一个稳定且内容容易辨识的普通窗口，例如新建的记事本测试窗口；不要使用会自动关闭或切换 HWND 的临时窗口。

1. 在托盘设置中确认保存目录为 `E:\QRtest\QuickRec-v1.6.1-acceptance\videos`。
2. 按 `Ctrl+Shift+W`，在窗口选择器中选中测试窗口。
3. 在目标窗口内滚动或输入非隐私测试文本，录制 3 至 5 秒。
4. 按 `Ctrl+Shift+S` 正常停止。
5. 播放生成的 MP4，确认画面只对应目标窗口，没有变成全屏或错误区域。
6. 打开素材库，确认新记录位于顶部，模式为“窗口”，路径、时长、分辨率和 FPS 有值。
7. 使用包内 FFprobe 核对：

```powershell
& 'E:\QRtest\QuickRec-v1.6.1-audiofix2-dist\QuickRec\_internal\ffmpeg\ffprobe.exe' `
  -v error -show_streams -show_format -of json '<窗口录制 MP4 完整路径>'
```

通过标准：MP4 可解析、画面正确、正式索引只有一条对应记录、素材库字段与 FFprobe 一致。保存播放器或素材库截图。
![[Pasted image 20260717163321.png]]

### 8.3 麦克风单独录制

系统声音和“系统声音 + 麦克风”已经使用最终候选包完成复验，本节只补麦克风单独模式。

1. 在设置中选择“麦克风”。
2. 录制时说出“QuickRec 麦克风验收”和当前时间。
3. 播放 MP4，确认语音清晰可辨。
4. FFprobe 应显示音频流，素材库音频模式应为“麦克风”。

通过标准：MP4 可播放，语音清晰可辨；FFprobe 显示 48 kHz 双声道 AAC；素材库字段、日志和设置模式均为麦克风。记录 MP4 路径及 FFprobe 输出。

### 8.4 设置与诊断快速回归

1. 从托盘打开“设置”，确认存在“诊断”分组。
2. 修改一项无风险配置，例如 FPS 在原值与测试值之间切换；保存并关闭。
3. 通过托盘正常退出并重新启动候选包，确认配置保持；验收结束前恢复原值。
4. 点击“复制诊断信息”，确认出现成功反馈，并检查剪贴板内容包含版本、配置和最近错误上下文。
5. 点击“打开日志目录”，确认资源管理器进入隔离诊断目录。
6. 点击“导出诊断文件”，确认出现成功反馈，导出文件实际存在、使用 UTF-8 打开可读。
7. 再次打开素材库，确认诊断操作没有破坏素材列表和待入库计数。

通过标准：设置持久化，三个诊断入口均成功，导出文件存在且可读，未影响录制与素材库。

### 8.5 v1.6 素材库快速回归

以下操作只使用测试视频：

1. **目录重建**：准备一个有效 MP4、一个损坏伪 MP4 和一个非视频文件；从素材库执行目录重建。有效 MP4 应入库，损坏文件和非视频应跳过。
2. **重新定位**：把一条测试 MP4 移到中文和空格路径；素材库应显示缺失。先取消文件选择，再选择损坏文件，最后选择正确文件。取消和失败不得修改索引，正确文件应恢复路径与元数据。
3. **仅移除索引**：先取消确认，记录应保留；再次确认后只移除索引，原 MP4 必须仍存在。
4. **移入回收站**：使用可丢弃测试视频，先取消确认，文件和索引均应保留；再次确认后文件进入 Windows 回收站且索引移除。不要清空回收站。
5. **重启保持**：正常退出并重启，确认目录重建和重新定位结果仍存在，已移除记录不会自行恢复。

通过标准：无视频误删、无重复索引、损坏文件不入库、取消不修改数据、回收站不是永久删除。保存关键界面截图并记录测试文件路径。

### 8.6 125% 与 150% DPI

每档缩放都必须使用同一锁定候选包冷启动：

1. 记录当前 Windows 显示缩放比例。
2. 切换为 125%，退出并重新启动 QuickRec。
3. 检查托盘菜单、设置页、素材库列表、详情、分页、重新定位按钮、移除记录确认框和回收站确认框。
4. 保存至少一张素材库主界面截图；出现裁切时额外保存问题截图。
5. 重复上述步骤验证 150%。
6. 验收结束后恢复原缩放比例，并再次确认窗口位置和控件正常。

通过标准：文本不截断，按钮与标签不重叠，确认框完整可见，点击区域与视觉位置一致，窗口可移动和关闭。

### 8.7 正常退出与环境恢复

1. 通过托盘“退出”关闭 QuickRec，不使用任务管理器强制结束。
2. 确认任务管理器中没有 QuickRec 进程，也没有残留录制线程或选择框。
3. 恢复原音频模式、FPS、保存路径和 Windows 显示缩放。
4. 确认隔离索引与待入库索引不是只读文件。
5. 确认真实 `%APPDATA%\QuickRec\recordings.json` 未被删除、覆盖或用于测试。
6. 确认 `E:\codex\QuickRec-Lite` 工作区仍干净。

### 8.8 结果登记

| 项目           | 结果  | MP4/截图/日志证据                                                                                 | 备注                                                                                            |
| ------------ | --- | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 窗口录制         | 通过  |                                                                                             |                                                                                               |
| 系统声音         | 通过  | `E:\QRtest\QuickRec-v1.6.1-acceptance\evidence\audiofix2\system\videos\QuickRec_20260716_234947.mp4` | H.264 + 48 kHz 双声道 AAC；平均 `-24.1 dB`、峰值 `-20.8 dB`；日志选中默认 `HECATE G1500 BAR`，索引音频模式为 `system` |
| 麦克风          | 通过  |                                                                                             |                                                                                               |
| 系统声音 + 麦克风   | 通过  | `E:\QRtest\QuickRec-v1.6.1-acceptance\evidence\audiofix2\both\videos\QuickRec_20260716_230446.mp4` | 双声道 AAC，日志与索引正确；用户确认系统音和麦克风语音均可辨识                                                             |
| 设置持久化        | 通过  | `evidence\auto3\settings-before.png`、`settings-changed-60fps.png`、`settings-after-restart-60fps.png` | FPS 从 30 改为 60，保存并重启后保持；验收结束已恢复为 30。 |
| 诊断复制/目录/导出   | 通过  | `evidence\auto3\diagnostic-clipboard.txt`、`diagnostic-log-directory.png`、`videos\QuickRecDiagnostics\diagnostic_20260717_171246.txt` | 三个 GUI 入口均成功；导出文件为可读 UTF-8 文本。 |
| v1.6 素材库快速回归 | 通过  | `evidence\auto3\material-rebuild-passed.png`、`material-relink-corrupt-rejected.png`、`material-relink-success.png`、`material-remove-index-confirmed.png`、`material-recycle-confirmed.png`、`material-after-restart.png` | 有效视频入库，损坏视频拒绝；取消操作不改数据；仅移除索引保留 MP4；回收站可追溯；重启后状态保持。 |
| 125% DPI     | 通过  |                                                                                             |                                                                                               |
| 150% DPI     | 通过  |                                                                                             |                                                                                               |
| 正常退出与环境恢复    | 通过  |                                                                                             |                                                                                               |

每项完成后将对应复选框改为 `[x]`，并记录 MP4、截图、日志或导出文件路径。全部补证前保持“部分通过，不可发布”。

### 8.9 自动补证摘要（2026-07-17）

- 验收对象：`E:\QRtest\QuickRec-v1.6.1-audiofix2-dist\QuickRec\QuickRec.exe`，SHA256 为 `2CB447709769A8A986B7A48A63C98377803A002ED56892E57F0911661FA3E092`。
- 隔离环境：`E:\QRtest\QuickRec-v1.6.1-acceptance\gui-appdata`；完整机器可读汇总见 `evidence\auto3\verification-summary.json`。
- 目录重建扫描 2 个 QuickRec MP4：有效 1、失败 1；非视频文件未入库。有效素材元数据为 2 秒、640 x 360、24 FPS。
- 重新定位依次验证取消、损坏 MP4 拒绝和中文空格路径有效 MP4 成功；失败后原索引保持，成功后路径与元数据同步更新。
- “仅移除索引”确认后测试 MP4 仍存在且正式索引不再包含该路径。
- “移入回收站”确认后原路径和正式索引均不存在；Windows 回收站中查到同名文件及原始目录，未清空回收站。
- 重启候选包后素材库保持 14 条；重新定位记录仍存在，两条删除测试记录均未恢复。
- 验收结束 FPS 已恢复为 30，候选包进程已停止；真实 `%APPDATA%\QuickRec` 配置和索引的时间与哈希保持原值；QuickRec Lite 工作区干净。

## 9. 判定

- 任一视频丢失、误报录制失败、重复正式素材、待入库记录静默丢失或“移除记录”误删视频：**未通过**。
- 核心链路通过但存在 DPI、设备或 GUI 待补证：**部分通过，不可发布**。
- 全部发布阻塞项均有真实证据：**通过，可进入发布收口**。
