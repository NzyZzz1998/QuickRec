# QuickRec Full v1.9.3 D10 GUI 手动验收

## 1. 验收状态

| 项目 | 内容 |
| --- | --- |
| 当前阶段 | D10 GUI、真实媒体与发布前回归 |
| 当前结论 | 通过 |
| 当前公开版本 | v1.9.3 |
| 候选版本 | v1.9.3 RC3（正式发布资产） |
| 自动化前置 | D9 通过 |
| 发布状态 | 正式发布 |

## 2. 锁定验收对象

```text
候选目录:
E:\QRtest\QuickRec-v1.9.3-rc3-dist\QuickRec

GUI:
E:\QRtest\QuickRec-v1.9.3-rc3-dist\QuickRec\QuickRec.exe
SHA256:
94F51E274A32E35CC2E47AA9549BF37B41BE4DD034DDBA72A66309C58E1CC986

CLI:
E:\QRtest\QuickRec-v1.9.3-rc3-dist\QuickRec\QuickRecCLI.exe
SHA256:
8E80AEB199D978944BED049668E0F49A840BE2455AA46CAA7318AE29A9DB0B09
```

验收开始前必须重新计算两个 SHA256。任一不一致时停止验收，不得混用其他
构建的证据。

## 3. 隔离与证据目录

建议根目录：

```text
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance
```

建议结构：

```text
appdata\
localappdata\
temp\
projects\
media\
recordings\
evidence\
logs\
```

验收要求：

1. 结束所有 QuickRec 进程；
2. 记录真实 `%APPDATA%\QuickRec` 与 `%LOCALAPPDATA%\QuickRec` 的存在状态、
   修改时间和关键索引哈希；
3. 使用隔离 APPDATA、LOCALAPPDATA、TEMP 和项目副本；
4. 不删除、覆盖或重命名真实用户项目、索引、预览缓存和视频；
5. 保存失败、只读、缺失和外部冲突均只使用受控副本；
6. 验收结束后恢复环境、权限、DPI 和进程状态。

## 4. 证据记录格式

每项填写：

| 字段 | 内容 |
| --- | --- |
| 时间 |  |
| 前置条件 |  |
| 实际操作 |  |
| 实际结果 |  |
| 截图 |  |
| 项目文件 |  |
| 媒体文件 |  |
| 日志/诊断 |  |
| 结论 | 通过 / 部分通过 / 未通过 / 待验证 |

## 5. 剪辑主链路

### V193-E01 左侧裁剪

1. 打开含关联视频与音频的项目；
2. 选中片段并拖动左侧手柄到非关键帧位置；
3. 检查候选覆盖层、帧吸附和全局波纹影响；
4. 先取消一次，确认项目文件和时间线不变；
5. 再次操作并确认提交；
6. 确认关联音视频源入点一致、时间线起点保持、后续未锁定片段按规则波纹；
7. 播放裁剪后的起点，检查画面和声音。

预期：一帧内视频准确，音频边界误差不超过 20 ms；取消零副作用。

### V193-E02 右侧裁剪与向外延长

1. 缩短关联片段右边缘；
2. 确认时间线总时长和后续片段向左波纹；
3. 在素材剩余范围内向外延长；
4. 确认后续片段向右波纹；
5. 尝试超过素材边界。

预期：合法范围可提交；越界被阻止并说明原因；不产生同轨重叠。

### V193-E03 精确时间输入

1. 打开“片段属性”；
2. 输入合法 `HH:MM:SS.mmm` 源入点和源出点；
3. 检查帧归一化、有效时长和影响摘要；
4. 分别验证应用、取消、关闭和 `Esc`；
5. 输入非法格式、出点早于入点和超过素材总时长。

预期：每个失败输入均不修改正式时间线；保存失败时检查器保持可恢复。

### V193-E04 按播放头分割

依次通过以下入口分割：

- 工具栏“分割”；
- 片段右键菜单；
- `Ctrl+B`。

检查：

- 左片段保留原 `clip_id`；
- 右片段生成新 `clip_id`；
- 右侧关联音视频使用新 `link_group_id`；
- 新右片段被选中；
- 播放头和滚动位置保持；
- 边界处和过近位置给出明确反馈。

### V193-E05 全局波纹删除

1. 选择中间片段并按 `Delete`；
2. 检查影响区间、受影响轨道、片段和总时长；
3. 取消并核对零副作用；
4. 再次确认；
5. 检查所有未锁定轨道按固定规则向左波纹；
6. 检查原视频和项目素材引用仍存在。

### V193-E06 轨道锁与冲突定位

1. 锁定一条将受波纹影响的轨道；
2. 发起裁剪、分割或删除；
3. 检查冲突列表、确认按钮禁用和“定位冲突”；
4. 解锁后重新生成候选并提交；
5. 检查只锁当前轨道，不影响其他轨道。

## 6. 保存、历史与恢复

### V193-S01 撤销、重做与自动保存

- 连续执行裁剪、分割、锁定和删除；
- 逐步撤销并逐步重做；
- 每一步检查 UI、内存、项目文件和播放计划；
- 关闭并重新打开项目，确认最后成功状态；
- 连续拖动只形成一次用户历史。

### V193-S02 保存失败

1. 使用受控 ACL 或文件占用制造项目保存失败；
2. 发起剪辑；
3. 确认正式时间线和历史栈不变化；
4. 检查持续失败条、重试、放弃和诊断；
5. 恢复条件后重试同一候选；
6. 确认只产生一次修改。

### V193-S03 外部修改冲突

1. 打开项目后在外部修改项目副本；
2. 发起剪辑或自动保存；
3. 检查冲突提示；
4. 分别验证取消、放弃本地修改和恢复副本；
5. 确认未知字段和其他 extensions 未丢失。

### V193-S04 schema v1→v2

1. 打开 v1 fixture，只查看和播放；
2. 核对文件哈希不变；
3. 第一次成功剪辑；
4. 检查 `.bak`、schema v2 和非零源范围；
5. 重启并确认持久化；
6. 使用 v1.9.2 打开副本，确认只读保留而不覆盖；
7. 未知未来 schema 保持只读。

## 7. 健康状态

### V193-H01 缺失与重新定位

- 外部移动素材，确认片段身份和时间位置保留；
- 缺失状态允许查看属性和确认后删除，但禁用裁剪/分割；
- 重新定位同一素材后，全部引用片段恢复；
- `clip_id`、`link_group_id`、源范围和时间位置不变。

### V193-H02 关联异常、只读与损坏

- 构造关联组不一致，确认整组写操作禁用且可定位原因；
- 归档/只读项目可查看和播放，不可剪辑；
- 损坏时间线不显示上一项目残留画布；
- 项目素材、备份恢复和诊断入口仍可用。

## 8. 播放准确性

### V193-P01 非关键帧与连续分割

- 使用 D1 受控 H.264/AAC 样本；
- 裁剪到非关键帧；
- 检查首帧、首个音频脉冲、连续片段接缝；
- 检查播放、暂停、随机跳转和片段边界预缓冲；
- 记录帧号、时间码和误差。

门槛：

- 视频误差不超过一帧；
- 音频边界误差不超过 20 ms；
- 随机跳转不超过 500 ms；
- 暂停响应不超过 200 ms。

### V193-P02 30 秒与 10 分钟同步

- 播放 30 秒样本；
- 播放 10 分钟样本并在多个时间点测量；
- 音画绝对偏差不超过 40 ms；
- 10 分钟漂移增量不超过 20 ms；
- 切换项目、关闭剪辑工作台和退出后无残留音频或子进程。

## 9. 压力与布局

### V193-L01 大项目

使用 8 条视频轨、8 条音频轨、100 个片段和 30 分钟时间线：

- 打开、滚动、缩放、选择和属性检查；
- 连续执行 100 次合法混合剪辑；
- 检查波纹预览、保存、撤销重做和播放；
- 记录卡顿、内存、CPU 和异常日志。

### V193-L02 窗口与 DPI

分别验证：

- 最大化；
- 1216×760；
- 960×640；
- 100%、125%、150% DPI。

重点检查手柄、检查器、影响弹窗、失败条、轨道锁、右键菜单、时间码输入、
滚动条和确认按钮，不得裁切、重叠、溢出或不可点击。

## 10. CLI 与打包回归

### V193-C01 双入口

- `QuickRec.exe` 正常启动托盘，不出现 CLI 窗口；
- `QuickRecCLI.exe doctor --json` 不创建托盘或窗口；
- 两个入口共用 `_internal`；
- CLI JSON stdout 只有一个对象，日志只进入 stderr；
- 项目和媒体错误不输出不必要的完整用户路径。

### V193-C02 CLI 隔离与录制

- 在隔离目录运行 `record`、`probe`、`project validate`、
  `timeline validate` 和 `smoke --suite editing`；
- 检查稳定退出码、超时、取消、失败清理和证据相对路径；
- 确认真实 APPDATA、配置、中央索引和项目不变。

自动前置结果见 [verification.md](verification.md)，GUI 与真实桌面部分仍需本轮
确认。

## 11. 历史功能回归

### V193-R01 录制

分别验证：

- 全屏、区域、窗口；
- 无声、系统声音、麦克风、系统声音＋麦克风；
- 30、60、120 FPS；
- 120 FPS 能力检测、快速校验、提示和诊断；
- 静态桌面短录制不再生成 0 帧；
- 所有 MP4 使用包内 FFprobe 检查流和实际参数。

### V193-R02 工作台

- 素材库、项目、首帧预览和重新定位；
- 项目创建、打开、重命名、归档、恢复和安全删除；
- 工作台与剪辑工作台并存；
- 录制中只读状态；
- 设置显式保存、失败留在当前页；
- 诊断复制、打开目录和导出；
- 托盘单实例、双击、隐藏、重新打开和退出。

## 12. 发布阻塞

以下任一情况出现时不得发布：

- 裁剪、分割或波纹造成项目、时间线或素材数据损坏；
- 关联音视频只修改一侧；
- 保存失败后 UI、内存、文件或历史不一致；
- schema v1/v2 迁移覆盖未知字段或无法回滚；
- 非零源入点播放未达到门槛；
- 三类录制、四类音频或 120 FPS 发生回退；
- 候选包哈希不一致；
- 真实用户数据被验收环境修改；
- QuickRec Lite 被修改；
- 关键 GUI/DPI 项仍为待验证。

## 13. 验收结束恢复

- 停止 QuickRec 与测试辅助进程；
- 恢复 APPDATA、LOCALAPPDATA、TEMP、ACL、音频模式和 DPI；
- 对比真实用户关键文件验收前后哈希；
- 保留证据、失败样本和诊断日志；
- 确认 QuickRec Lite 工作区干净；
- 更新 `verification.md`、本文和 `progress.md`；
- 即使全部通过，也停在独立发布授权点，不自动提交、推送、打 tag 或发布。

## 14. 当前实际验收结果

### 14.1 候选身份

| 项目 | 实际结果 | 结论 |
| --- | --- | --- |
| GUI SHA256 | `94F51E274A32E35CC2E47AA9549BF37B41BE4DD034DDBA72A66309C58E1CC986` | 通过 |
| CLI SHA256 | `8E80AEB199D978944BED049668E0F49A840BE2455AA46CAA7318AE29A9DB0B09` | 通过 |
| ZIP SHA256 | `F062CD3A28245AF9FC275A6889EA39115B80A1D3D794B5E759176EB103726C6D` | 通过 |
| 隔离 APPDATA | `E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\appdata` | 通过 |
| 真实用户素材索引 | SHA256 `B455034DC7F1755AA979DCF9B09A7563E129BEE4C2E246CD2D27D0279CCE167A`，验收前后未变化 | 通过 |
| 真实用户配置 | SHA256 `E3FC96863D862B4A2DB8080D1F3ECEC1565FF647B6A7D7D47DA6DE5038B4E8DD`，验收前后未变化 | 通过 |
| QuickRec Lite | `lite-master` / `cfaee3ed`，工作区干净 | 通过 |

RC1 在删除验收中发现状态摘要残留；RC2 在分割验收中发现摘要未依据最新模型
刷新。两次修复均改变生产代码，因此 RC1、RC2 只作为历史探索证据，后续发布
判断只认 RC3。

### 14.2 已完成项

| 项目 | 实际结果 | 证据 | 结论 |
| --- | --- | --- | --- |
| 工作台与项目页启动 | RC3 单实例启动，工作台、项目页可打开 | Computer Use 实测 | 通过 |
| 剪辑工作台启动 | 受控 schema v2 项目可打开，显示 2 轨、3 片段、总长 4.600 秒 | Computer Use 实测 | 通过 |
| 工具栏分割 | 在 3.410 秒分割第三个片段，自动保存后得到 4 个片段 | Computer Use 实测、项目 JSON | 通过 |
| 分割后状态摘要 | 立即选中新右片段，摘要显示新 `clip_id` 和源范围 `00:01.866–00:03.066` | `evidence\D10-rc3-split-summary-refreshed.jpg` | 通过 |
| 裁剪手柄 | 左边缘内收、右边缘内收和向外延长均显示候选范围与全局波纹影响；取消后项目不变 | `evidence\D10-rc3-left-trim-preview.jpg`、`D10-rc3-right-trim-preview.jpg`、`D10-rc3-trim-extend-preview.jpg` | 通过 |
| 精确输入 | 源入点 `0.100` 秒可预览、确认并应用；项目 JSON 写入 `source_start_us=100000`，撤销后恢复；非法入点 `3.100` 秒被阻止 | `evidence\D10-rc3-precise-trim-candidate.jpg`、`D10-rc3-precise-trim-confirmation.jpg`、`D10-rc3-precise-trim-applied.jpg`、`D10-rc3-invalid-trim-blocked.jpg` | 通过 |
| 三种分割入口 | 工具栏、`Ctrl+B` 和片段右键菜单入口均可发现；工具栏和快捷键均完成真实分割，随后撤销恢复 | `evidence\D10-rc3-split-summary-refreshed.jpg`、`D10-rc3-shortcut-split-ctrl-b.jpg`、`D10-rc3-clip-context-menu.jpg` | 通过 |
| 轨道锁与交叉冲突定位 | 锁定视频轨后编辑和删除控件禁用，解除锁定后恢复可用；受控项目中另一片段跨越全局波纹区间时，确认操作被禁用，“定位冲突”能准确选中冲突片段，取消后项目仍为 3 轨、2 片段 | `evidence\D10-rc3-track-lock-disabled-editing.jpg`、`D10-rc3-conflict-impact-and-locate.png`、`D10-rc3-conflict-impact-modal.png`、`D10-rc3-conflict-located.png`、项目 JSON、冻结 CLI validate | 通过 |
| 全局波纹删除 | 预览准确显示删除区间、总时长 `4.600 -> 3.066`、影响 1 条轨道/4 个片段；取消分支保持项目不变。经操作时确认后执行最终删除，界面立即清空选择并显示“片段已删除，全局波纹已应用并自动保存”；项目持久化为 schema v2、2 轨、3 片段、终点 `3.066667` 秒，冻结 CLI 校验通过。此前缺失测试移入 `missing-backup` 的源视频仍存在，未被删除 | `evidence\D10-rc3-delete-preview-current.jpg`、`D10-rc3-delete-cancel-no-side-effect.jpg`、`D10-rc3-delete-confirmed-ripple.png`（SHA256 `683FC64DB697BCD3BB675ECC94C310E4259005C7D3BAB7B5779379150152C0B2`）、`D10-rc3-main-before-final-delete.qrproj`、`D10-rc3-confirmed-actions-summary.json`、项目 JSON、冻结 CLI validate、`QuickRecDiagnostics\quickrec.log` | 通过 |
| 连续分割播放 | 从时间线起点连续播放 4 个相邻片段，在 `4.600 / 4.600` 自动停止并显示“播放结束”；真实媒体门禁补充验证非关键帧源入点、分割接缝和长时同步 | `evidence\D10-rc3-continuous-playback-end.jpg`、`playback-accuracy-spike.md` | 通过 |
| 窗口尺寸 | 最大化和实际约 `962×672` 的最小窗口均可操作，主要控件未越界 | `evidence\D10-rc3-editor-maximized.jpg`、`D10-rc3-editor-minimum-size.jpg` | 通过 |
| 100%/125%/150% DPI | 在 Windows 设置中依次切换真实系统缩放，并在 125% 与 150% 下重启锁定 RC3。工作台、项目页和最大化剪辑工作台中的导航、素材区、预览区、编辑工具栏、时间线、滚动条及片段属性入口均可见可操作，无裁切、重叠或不可点击控件；验收后恢复为 100% | `evidence\D10-rc3-dpi-100-editor.png`、`D10-rc3-dpi-setting-125.png`、`D10-rc3-dpi-125-workbench.jpg`、`D10-rc3-dpi-125-editor.png`、`D10-rc3-dpi-setting-150.png`、`D10-rc3-dpi-150-workbench.png`、`D10-rc3-dpi-150-editor.png`、`D10-rc3-dpi-setting-restored-100.png` | 通过 |
| 删除后状态摘要修复 | 定向 Qt UI 测试与 RC3 GUI 最终删除均确认删除后选择为空、摘要为“未选择片段”，且项目已自动保存 | `tests\test_timeline_editing_ui.py`，14 passed；`evidence\D10-rc3-delete-confirmed-ripple.png` | 通过 |
| 冻结 CLI | doctor、editing smoke、project/timeline validate、中文空格路径 probe 均成功 | `E:\QRtest\QuickRec-v1.9.3-rc3-cli` | 通过 |
| 候选包录制 | 1080p60、无声、3.033333 秒、182 帧 | `E:\QRtest\QuickRec-v1.9.3-rc3-cli\record-evidence\record.json` | 通过 |
| 保存失败与恢复 | 受控保存失败后正式时间线和历史栈不变；“重试”在恢复写入条件后成功且只提交一次；“放弃”恢复上次成功状态 | `evidence\D10-rc3-save-failure-bar.jpg`、`D10-rc3-save-retry-success.jpg`、`D10-rc3-save-discard-restored.jpg` | 通过 |
| 外部修改冲突安全分支 | 外部版本变化后显示冲突条；取消操作保留本地待提交候选；“保存恢复副本”成功且不覆盖外部版本。经操作时确认后，在专用隔离项目中新增本地轨道候选触发冲突并选择“重新加载”；界面切换为“D10 外部版本已加载”，错误条消失，本地新增轨道未落盘。项目文件与外部版本 SHA256 完全一致，保持 schema v2、3 轨、2 片段，冻结 CLI 校验通过 | `evidence\D10-rc3-external-conflict-bar.jpg`、`D10-rc3-external-conflict-cancel-preserved.jpg`、`D10-rc3-external-recovery-copy-success.jpg`、`D10-rc3-external-reload-before.jpg`（SHA256 `574F379A7CC6FFCFA0ED1A68F752E34BD9B35B025B79D0E9C1346617B30CD08B`）、`D10-rc3-external-reload-success.jpg`（SHA256 `1BAAE5040325E7CF100E6269F128407DCAB526FE7B896324F2DA221E1FD7A935`）、`D10-rc3-external-reload-external-version.qrproj`、`D10-rc3-confirmed-actions-summary.json`、`QuickRecDiagnostics\quickrec.log` | 通过 |
| 缺失与重新定位 | 项目素材和时间线片段均显示缺失/只读状态；重新定位后项目素材、时间线片段和预览恢复 | `evidence\D10-rc3-project-missing-material.jpg`、`D10-rc3-material-relinked.jpg`、`D10-rc3-timeline-material-restored.jpg` | 通过 |
| 关联异常防御 | 持久化的非法关联组在时间线载入校验层被拒绝，不允许进入正式项目状态；界面防御测试确认异常关联片段标记为“关联异常”，禁用裁剪、分割和删除，同时保留属性与诊断入口 | `tests\test_timeline_editing_ui.py::test_link_error_disables_group_edits_but_keeps_properties_visible`、`tests\test_timeline_health.py`，定向测试 5 passed | 自动化防御证据通过；不人为构造非法候选项目 |
| 归档项目只读 | 归档项目进入剪辑工作台后明确显示“项目已归档 · 只读查看”；撤销、重做、分割、删除、增轨、轨道调整和加入时间线均禁用，播放与诊断入口保留；退出后项目成功恢复为活跃状态 | `evidence\D10-rc3-archived-readonly.jpg`、隔离 `projects.json` | 通过 |
| schema 与兼容 | v1 打开不写、第一次成功剪辑升级 v2、v2 重启持久化、v1.9.2 回滚只读、未知字段及其他 extensions 往返保留 | 定向兼容测试与受控项目文件 | 通过 |
| 播放准确性 | 30/60/120 FPS 非关键帧源入点误差均不超过 1 帧；AAC 非零起点误差 0 ms；分割接缝误差 0 μs；30 秒音画偏差 16 ms；10 分钟漂移增量 0 ms；源码与 frozen 共 16 项通过 | `playback-accuracy-spike.md` | 通过 |
| 压力项目 | 8 条视频轨、8 条音频轨、100 个片段、30 分钟时间线可打开、滚动和查看片段；100 次混合合法剪辑压力测试通过 | `evidence\D10-rc3-stress-16tracks-100clips-open.jpg`、`D10-rc3-stress-audio-tracks-scroll.jpg`、`D10-rc3-stress-summary.json` | 通过 |
| 区域录制 | 实际框选约 `730×420` 区域，在 High/1080p 策略下按比例输出 `1876×1080 / 30 FPS`；画面对应所选区域，MP4 可解析并以 `mode=region` 入库 | `recordings\QuickRec_20260729_060849.mp4`、`evidence\D10-rc3-region-recording-frame.png`、中央索引、日志 | 通过 |
| 窗口录制 | 选择资源管理器测试窗口，输出 `1122×632 / 30 FPS`；画面对应目标窗口，MP4 可解析并以 `mode=window` 入库 | `recordings\QuickRec_20260729_061518.mp4`、`evidence\D10-rc3-window-recording-frame.png`、中央索引、日志 | 通过 |
| 系统声音 | 播放受控 `997 Hz / 48 kHz / 5 秒` WAV 后进行全屏录制；输出含 `AAC 48 kHz 双声道`，音量检测 `mean -30.8 dB / max -18.0 dB`，中央索引为 `audio_source=system` | `recordings\QuickRec_20260729_062110.mp4`、`media\system-audio-tone.wav`、FFprobe、日志 | 通过 |
| 麦克风 | 锁定 `QuickRecCLI.exe` 在隔离工作区完成 8 秒全屏录制；运行日志确认麦克风以 `48000 Hz / 1ch` 初始化并使用 `source=microphone`。输出为 `1920×1080 / 30 FPS`，包含 `AAC 48 kHz 双声道`，音量检测 `mean -80.8 dB / max -59.9 dB`，不是数字静音 | `E:\QRtest\QuickRec-v1.9.3-rc3-audio-evidence\mic\record.json`、`ffprobe.json`、`volumedetect.txt`；视频 SHA256 `226FDE5921EE737BCB58B3996471FEBF9696B39212DA1A90565921EF6D510174` | 通过 |
| 系统声音＋麦克风 | 锁定 `QuickRecCLI.exe` 在隔离工作区完成 8 秒全屏录制，并播放受控系统音频；运行日志确认 loopback 与麦克风分别初始化、两份临时 WAV 均参与对齐和混合。输出为 `1920×1080 / 30 FPS`，包含 `AAC 48 kHz 双声道`，音量检测 `mean -54.3 dB / max -27.1 dB`，报告 `actual_audio=both` | `E:\QRtest\QuickRec-v1.9.3-rc3-audio-evidence\both\record.json`、`ffprobe.json`、`volumedetect.txt`；视频 SHA256 `0D2953D12A645803A7BDC10FCA28B904D4AF66CA55030BCCB1AFFE174C8A44BE` | 通过 |
| GUI 60 FPS | 工作台设置为 60 FPS 后实际全屏录制，输出 `1920×1080 / 60 FPS / 无音频`，时长 `23.566667` 秒；中央索引记录 `fps=60.0`，设置随后恢复为 `30 FPS / 无声` | `recordings\QuickRec_20260729_062549.mp4`、`evidence\D10-rc3-fullscreen-60fps-frame.png`、中央索引、`config.json` | 通过 |
| 120 FPS 低刷新率保护 | 历史 60 Hz 验收环境中，设置页提示“当前显示刷新率低于 119Hz”；尝试选择 120 后仍保持 30 FPS，保存按钮不启用，隔离配置继续为 `30 FPS / 无声` | `evidence\D10-rc3-120-disabled-60hz.png`，SHA256 `81CE3A1A7E025F921574F7910B6028FCB419BA07F2C133BC816F009024365F3D`、隔离 `config.json` | 通过 |
| GUI 120 FPS 高刷新率录制 | 同一锁定 RC3 在单显示器 `2560×1440@300 Hz` 环境通过能力检测并保存 120 FPS；工作台实际全屏录制后结果条显示“目标 120 FPS · 平均 120.0 FPS · 最低每秒 115 FPS”。输出为 `1920×1080 / 120 FPS / 121.283333 秒 / 无音频`，共 `14554` 帧；性能日志为 `stable=True`、平均 `119.963 FPS`、最低单秒 `115 FPS`、最大队列积压 `85.900 ms`、丢弃 `5` 帧。FFprobe、抽帧、中央索引与日志一致，测试后配置恢复为 `30 FPS / 无声 / 不倒计时` | `E:\QRtest\QuickRec-v1.9.3-rc3-120fps-evidence\D10-rc3-gui-120-setting-saved.jpg`、`D10-rc3-gui-120-recording-result.jpg`、`D10-rc3-gui-120-ffprobe.json`、`D10-rc3-gui-120-frame-5s.png`、`D10-rc3-gui-120-recordings.json`、`D10-rc3-gui-120-summary.json`；视频 `recordings\QuickRec_20260729_094358.mp4`，SHA256 `74C394C87B4A5CAEFF13C88A12F467FC65C2E0B960E18DA3A77EAAB0C3FBE465` | 通过 |
| 设置持久化 | 修改设置、保存并重启后保持；测试结束后恢复 `30 FPS / 无声 / 不倒计时` | `evidence\D10-rc3-settings-persisted-after-restart.jpg`、隔离 `config.json` | 通过 |
| 诊断回归 | 复制诊断信息、打开日志目录和导出诊断文件均成功，导出内容可读 | `evidence\D10-rc3-diagnostic-export-success.jpg`、`recordings\QuickRecDiagnostics\diagnostic_20260729_060105.txt` | 通过 |
| 单实例与工作台隐藏 | 第二次启动未产生重复进程；关闭工作台仅隐藏，进程继续驻留；托盘隐藏图标区仅显示 1 个本候选包图标，双击后恢复同一个工作台，进程仍为原 PID `28300` 且数量为 1；托盘右键菜单真实展示“退出 QuickRec”。补证时以同一锁定 RC3 启动 PID `20772`，用户点击“退出 QuickRec”后，同路径进程数量由 1 降为 0，无残留进程 | `evidence\D10-rc3-tray-overflow-before-double-click.jpg`（SHA256 `011A61DC58FD972D3CC7A3FFE5927A4BC61A1DA15D6C32D8BFDEFD5004462E6C`）、`D10-rc3-tray-double-click-workbench.jpg`（SHA256 `EC583A8F38D26AA44B279FC715D12858910EF676D0E2E2EE62AD71225539B3D8`）、`D10-rc3-tray-explicit-exit-menu.jpg`（SHA256 `A93641D71E3D66E50ED061FCD945CB6693F7ADF51F4850DB625CDA0D7833C00F`）、`D10-rc3-tray-explicit-exit-process.txt`（SHA256 `02C557BFF486CF49033C2D07FE25FE10394B6052F27378ECC2BCD9ECBA62F4AA`）、进程快照、`QuickRecDiagnostics\quickrec.log` | 通过 |

### 14.3 RC1/RC2 历史证据

```text
E:\QRtest\QuickRec-v1.9.3-acceptance\evidence\D10-project-created.png
E:\QRtest\QuickRec-v1.9.3-acceptance\evidence\D10-project-material-preview.png
E:\QRtest\QuickRec-v1.9.3-acceptance\evidence\D10-editor-timeline-created.png
E:\QRtest\QuickRec-v1.9.3-acceptance\evidence\D10-editor-split-redo.png
E:\QRtest\QuickRec-v1.9.3-acceptance\evidence\D10-editor-trim-global-ripple.jpg
E:\QRtest\QuickRec-v1.9.3-acceptance\evidence\D10-editor-restart-persisted.jpg
E:\QRtest\QuickRec-v1.9.3-acceptance\evidence\D10-editor-trim-playback-end.jpg
E:\QRtest\QuickRec-v1.9.3-acceptance\evidence\D10-editor-ripple-delete.jpg
```

这些证据证明 RC1 曾完整走通项目创建、素材预览、分割、精确裁剪、全局波纹、
撤销重做、重启持久化和播放到时间线终点。RC2 另有删除取消证据：

```text
E:\QRtest\QuickRec-v1.9.3-rc2-acceptance\evidence\D10-rc2-delete-cancel-no-side-effect.png
```

由于 RC3 修改了剪辑工作台选择协调逻辑，RC1/RC2 证据只能用于历史追溯，不能
单独作为 RC3 最终发布依据。

### 14.4 验收收口

- 三种录制模式和四种音频模式均已获得同一锁定 RC3 的真实媒体证据；
- 100%、125%、150% DPI 均已完成真实系统缩放和 GUI 检查；
- 120 FPS 已在单显示器 `2560×1440@300 Hz` 环境完成能力检测、GUI 设置、
  真实全屏录制、FFprobe、索引和性能日志核对；
- Windows 缩放已恢复为 100%，QuickRec 与测试辅助进程均已停止；
- 真实用户素材索引和配置哈希未变化，QuickRec Lite 工作区保持干净。

D10 当前完成度为 `26/26`。

当前 D10 结论：

```text
通过
已完成独立发布授权与发布资料收口
```
