# QuickRec Full v1.8 验证记录

## 1. 当前结论

- 验证阶段：D10 工程门禁与 D11 GUI 验收。
- 当前结论：**自动化、工作台核心 GUI、120 FPS 技术门禁和 D11 音画同步验收均通过。**
- 发布状态：发布门禁通过，已授权执行正式发布。
- 验证日期：2026-07-26。
- 分支：`test`。
- HEAD：`fee1bec6a10239aa4edd47ebab7ad6555eebc9a8`，工作区包含尚未提交的音画同步最小修复。
- 正式发布基线：`v1.7`。

麦克风、双音频、10 分钟漂移、音画绝对偏移、缓存失效、快速校验、设置失败、
素材操作、窗口几何和三档 DPI 均已闭合。当前没有 D11 发布阻塞项。

## 2. 质量门禁

| 检查 | 结果 | 证据摘要 |
| --- | --- | --- |
| 全量 pytest | 通过 | `523 passed, 1 skipped, 25 deselected, 48 subtests passed` |
| 全项目覆盖率 | 通过 | 当前完整 coverage 结果为 `86.08%`，门槛 80% |
| Packaging 测试 | 通过 | `13 passed, 536 deselected` |
| Ruff | 通过 | `All checks passed!` |
| Mypy | 通过 | 22 个源文件无问题 |
| Compileall | 通过 | `src`、`scripts`、`tests` 编译通过 |
| UTF-8 / 乱码扫描 | 通过 | 未发现替换字符或常见乱码片段 |
| `git diff --check` | 通过 | 无空白错误；仅 Git 行尾转换提示 |

Mypy 的正式门禁命令为 `python -m mypy`，由 `pyproject.toml` 锁定 22 个受控源文件。额外执行 `python -m mypy src` 会在 5 个尚未纳入门禁的历史模块中报告 22 条既有类型债务；该结果不改变当前门禁结论，但不能表述为“全项目 mypy 已覆盖”。

本轮新增测试：

- 托盘默认入口不强制重置工作台页面。
- 工作台自身关闭隐藏后，协调器从存活窗口读取当前页面。
- 同一进程重新打开工作台恢复最后页面。

## 3. 120 FPS 技术门禁

- 真实 `1920×1080@120Hz` 三次正式重复全部通过。
- 三次真实源结果分别为：
  - `120.196 FPS / 最低 119`
  - `120.119 FPS / 最低 120`
  - `120.363 FPS / 最低 120`
- 三次编码交付均稳定在约 120 FPS，最大 backlog 均低于 9 ms。
- 生产链路 5 秒全屏录制输出 `601` 帧，视频时长 `5.008333` 秒。
- 生产自检输出 `600` 帧，平均 `119.617 FPS`、最低每秒 `117 FPS`，通过后写入隔离能力缓存并清理临时视频。
- 正式结论：技术门禁通过，D8/D9 已恢复实施。
- 详细证据：[120fps-spike.md](120fps-spike.md)。

## 4. 历史工作台候选包身份

历史工作台候选目录：

```text
E:\QRtest\QuickRec-v1.8-workbench-candidate-20260724-r5\QuickRec
```

| 文件 | SHA256 |
| --- | --- |
| `QuickRec.exe` | `8735DAB9AF7A3631636E8CFCFCE77A82EA1C1C37112B059B857ABEF838C7B407` |
| `_internal\ffmpeg\ffmpeg.exe` | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| `_internal\ffmpeg\ffprobe.exe` | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |

分发目录包含 244 个文件，总大小为 428,099,587 字节。

候选演进：

- `r3`：完成三类录制、设置、素材和诊断 GUI 取证。
- `r4`：修复托盘入口强制跳转录制页，但发现协调器缓存仍可能过期。
- `r5`：修复协调器从存活窗口恢复当前页面，为最终代码身份。
- `r1`、`r2`、`r3`、`r4` 均不得作为最终发布包；`r3` 未受后续改动影响的录制证据可以继承。

## 5. 工作台 GUI 验证

历史工作台候选隔离目录：

```text
E:\QRtest\QuickRec-v1.8-workbench-acceptance-20260724-r5
```

已通过：

- 首次打开工作台默认进入录制页。
- 录制、素材库、设置、诊断四页可正常切换。
- 关闭工作台仅隐藏窗口，QuickRec 进程继续驻留。
- 在素材库页关闭后，双击托盘重新打开仍恢复素材库页。
- 同一进程页面记忆不再被托盘入口或协调器旧缓存重置。

工作台三类录制、设置、素材和诊断证据位于：

```text
E:\QRtest\QuickRec-v1.8-workbench-acceptance-20260724-r3
```

录制抽样：

| 模式 | 文件 | 解析结果 |
| --- | --- | --- |
| 全屏 | `QuickRec_20260724_222638.mp4` | H.264，1920×1080，30 FPS，83.766667 秒 |
| 区域 | `QuickRec_20260724_225109.mp4` | H.264，1920×996，30 FPS，26.166667 秒 |
| 窗口 | `QuickRec_20260724_223635.mp4` | H.264，1122×632，30 FPS，17.5 秒 |

详情见 [manual-verification.md](manual-verification.md)。

## 6. 已闭合缺陷

### BUG-V18-001

静态桌面下 dxcam 等待新帧导致停止线程无法退出。改用可中断的非阻塞读取后，自动测试、30/60 FPS 硬件 smoke 和候选包真实录制均通过。

### BUG-V18-002

工作台在素材库页关闭后，从托盘重新打开会错误返回录制页。修复托盘入口强制页参数，并让协调器从存活窗口读取当前页后，新增测试和 `r5` 真实桌面复验通过。

详情见 [bugfix-log.md](bugfix-log.md)。

## 7. 尚未完成

- 托盘“打开工作台”菜单入口的独立截图。
- 窗口几何持久化与真实离屏修正。
- 录制中重新打开工作台的只读状态。
- 浮动结果条与窗口选择取消。
- 设置保存持久化及保存失败。
- 素材筛选、排序与文件操作。
- 诊断目录保存持久化。
- 旧 `r5` 候选包不包含已恢复实施的 D8/D9，不能作为 v1.8 最终候选包；需重新打包后验证设置、自检、快速校验和正式 120 FPS 录制。

这些项目必须在 [manual-verification.md](manual-verification.md) 中获得真实 GUI 证据，不能由自动化结果替代。

## 8. 2026-07-25 D8/D9 专项自动化收口

- D8 能力服务与设置入口完成：自检失败保留原有效 FPS，并提供重新检测和直达诊断入口。
- D9 正式录制接入完成：记录捕获帧、提交帧、编码完成帧、掉帧、平均 FPS、最低每秒 FPS 和最大 backlog。
- 120 FPS 未稳定达标时，视频继续正常保存；工作台结果区和系统通知明确提示性能状态。
- 磁盘持续保护按本次有效 FPS、画质和 `libx264-superfast` 编码配置保守估算，录制前 1 GB 警告与 200 MB 阻断规则保持不变。
- 全量测试：`513 passed, 25 deselected, 46 subtests passed`。
- 新能力模块专项测试：`27 passed`，合计覆盖率 `84.50%`；生产自检 `90%`、自检弹窗 `86%`、能力运行时 `100%`。
- 定向录制、磁盘、主流程和工作台测试：`100 passed`。
- Packaging：`13 passed, 525 deselected`。
- Ruff、mypy（22 个纳入门禁的源文件）、compileall 和 `git diff --check`：通过。
- 上述自动化收口后已生成 `r7` 新候选包；旧 `r5` 仅保留历史工作台证据，不能作为 v1.8 发布对象。

## 9. r7 候选包与 frozen 路径验证

候选目录：

```text
E:\QRtest\QuickRec-v1.8-candidate-20260725-r7\QuickRec
```

| 文件 | SHA256 |
| --- | --- |
| `QuickRec.exe` | `8B54B8F3F869EB8374F8DCFBBD5841657569837A4287DB2BF4F3BC6A88B26B5A` |
| `_internal\ffmpeg\ffmpeg.exe` | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| `_internal\ffmpeg\ffprobe.exe` | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |

- 分发目录包含 244 个文件，总大小 428,134,400 字节。
- 基础启动通过，进程可正常启动和停止。
- 等价 frozen 路径集成验证实际解析并调用上述包内 FFmpeg/FFprobe。
- 自检不再无限等待，失败后临时 MP4 清理完成，能力缓存未错误写入。
- 本次桌面复制出现 `DXGI_ERROR_ACCESS_LOST` 恢复事件，最终性能门禁失败；该结果证明失败收口正常，但不能替代打包程序 GUI 自检通过证据。
- 证据：`E:\QRtest\QuickRec-v1.8-acceptance-20260725-r7\frozen-selftest\frozen-selftest-output.txt`。
- `r6` 在队列满时可能无限等待，已失效并仅作为 BUG-V18-003 证据保留。

## 10. r7 GUI 自检与 r9 候选包

- `r7` 打包程序 GUI 自检通过，平均 `119.434 FPS`、最低每秒 `112 FPS`。
- 通过缓存位于隔离 APPDATA，记录的 FFmpeg 版本与候选包内工具一致；临时测试视频已清理。
- 自检运行百分比由程序使用 Segoe UI 常规数字绘制，并按填充区域切换深色或白色；真实 Windows 静态窗口确认 `42%` 正常。
- 自检完成态不再显示 `100%`，改用不依赖字体的矢量符号：通过为绿色对勾、失败为红色叉号、取消为灰色横线。
- 全量测试：`513 passed, 25 deselected, 46 subtests passed`。
- Packaging：`13 passed, 525 deselected`。
- 自检对话框定向测试：`7 passed`；Ruff、mypy、compileall 和 `git diff --check` 通过。
- `r8` 仅包含终态符号优化，因运行百分比字形尚未复核而失效。
- 新候选目录：`E:\QRtest\QuickRec-v1.8-candidate-20260725-r9\QuickRec`。
- `QuickRec.exe` SHA256：`49B017367A071FC2D9A271292DCD5AA3B18FB913E3F28E6AD85740DBCF2F7FC2`。
- 分发目录包含 244 个文件，总大小 428,136,809 字节；基础启动通过。
- 包内 FFmpeg/FFprobe 哈希保持不变。

## 11. r10 候选包与工作台状态收口

- `r9` GUI 验收发现录制时侧栏仍显示空闲，且未保存提示按钮依赖系统翻译而显示英文。
- 修复后定向测试 `64 passed`，全量测试 `514 passed, 25 deselected, 46 subtests passed`。
- Packaging `13 passed, 526 deselected`；Ruff、项目 mypy、compileall 和 `git diff --check` 通过。
- 当前候选目录：`E:\QRtest\QuickRec-v1.8-candidate-20260725-r10\QuickRec`。
- `QuickRec.exe` SHA256：`D8C114E84A4D84398B9BF1CC013B93B98DD04F349927C5366B1D43FAA552DFF7`。
- 分发目录包含 244 个文件，总大小 428,137,674 字节。
- `r10` 真实 1080p120 无声录制输出 46.016667 秒视频，平均 `119.925 FPS`、最低每秒 `116 FPS`，正常保存并进入中央素材索引。
- 未保存提示中文化和录制状态同步已通过真实 GUI 定向复验。

## 12. r11 候选包与 Qt 标准按钮中文化

- `r10` 素材库确认框仍显示 `Yes / No`，证明单独修复设置弹窗不足以覆盖 Qt 标准确认框。
- 新增应用级 Qt 标准按钮翻译器，并纳入 PyInstaller 隐式导入和 packaging 检查。
- 翻译器自动测试、主流程替身兼容测试和全量回归通过。
- 全量测试：`515 passed, 25 deselected, 48 subtests passed`。
- Packaging：`13 passed, 527 deselected`。
- 当前候选目录：`E:\QRtest\QuickRec-v1.8-candidate-20260725-r11\QuickRec`。
- `QuickRec.exe` SHA256：`C715897585C9EED4E164668EDA25AB11765D38F32D8A6C99979706637321BAD8`。
- 分发目录包含 244 个文件，总大小 428,139,325 字节。
- `r11` 素材库确认框显示“是 / 否”；取消后索引与实际视频均未改变。
- `r11` 基础 1080p120 无声录制可解析并正常入库。

## 13. r11 三档 DPI 复验

- 使用真实 Windows Qt 平台，在三个独立进程中分别设置 100%、125%、150%
  进程级缩放；未修改 Windows 全局显示比例。
- 取证脚本：`scripts/capture_v18_ui_implementation.py`。
- 证据目录：`E:\QRtest\QuickRec-v1.8-dpi-r11-20260725-windows`。
- 每档 23 张截图，共 69 张；包含四页、录制结果状态、素材边界状态、最小设置页、
  浮动工具栏、区域/窗口选择器、120 FPS 检测状态、快速校验、性能告警和关键确认框。
- 100%、125%、150% 下均未发现文字裁切、控件重叠、横向溢出或关键按钮不可见。
- 150% 下 960×640 逻辑尺寸设置页保留独立滚动区，底部“放弃更改 / 保存更改”
  完整可见。
- 120 FPS 运行状态显示正常 `42%` 数字；通过/失败状态使用矢量符号；
  中文确认按钮完整。
- 截图尺寸清单位于 `image-dimensions.csv`，全部截图哈希位于 `sha256.txt`。
- 取证脚本 Ruff 与 `git diff --check` 通过。
- 证据边界：这是 `r11` 同代码身份的 Windows Qt 渲染复验，不是系统全局缩放切换。

## 14. r11 剩余可自动验收边界

- 验证脚本：`scripts/verify_v18_remaining_acceptance.py`。
- 报告：`E:\QRtest\QuickRec-v1.8-remaining-20260725-r11\automated-boundaries\verification-report.json`。
- Windows Qt 集成验证通过：窗口离屏修正、设置保存持久化、设置写入失败回滚、
  诊断目录持久化、素材组合查询、复制路径、中文空格路径重新定位、仅移除索引、
  受控副本移入 Windows 回收站。
- 120 FPS 能力缓存验证通过：环境匹配时可用；刷新率、分辨率、保存磁盘、CPU、
  GPU、FFmpeg 或编码配置变化后均不可用。
- `tests/test_main_workflow.py` 补强快速校验缓存匹配、重新检测、当前录制 60 FPS
  和取消四条分支。
- `r11` 打包程序通过真实全局快捷键完成三次录制，输出均为
  1920×1080@30 FPS H.264，日志与中央索引一致，浮动结果条实际出现。
- 全量测试：`519 passed, 25 deselected, 48 subtests passed`。
- Packaging：`13 passed, 531 deselected`。
- Ruff、mypy、compileall 和 `git diff --check`：通过。

## 15. r11 最终音频与同步测量

- 隔离目录：`E:\QRtest\QuickRec-v1.8-final-manual-20260726`。
- 麦克风 30 秒、双音频 30 秒和双音频 10 分钟均生成
  1920×1080@120 FPS、AAC 48kHz 双声道文件，并进入隔离中央索引。
- 三段音频平均/峰值分别为 `-42.7/-3.7 dB`、`-25.0/-9.6 dB`、
  `-27.6/-8.6 dB`，不存在静音轨。
- FFmpeg 生成的时间戳同步源包含四次同时闪屏与提示音；源文件测量偏移均为 0 ms。
- `r11` 录制结果四次音频相对视频偏移为 `113.333`、`88.333`、
  `88.333`、`130 ms`，平均约 `105 ms`，超过 40 ms 发布阈值。
- 短测首尾偏移变化为 `16.667 ms`；10 分钟文件首端差为 0 ms、末端差为
  `-8.333 ms`，漂移增量符合 20 ms 要求。
- 结论：D11.19～D11.21 通过；D11.22 因绝对偏移未通过。
- 证据：
  `E:\QRtest\QuickRec-v1.8-final-manual-20260726\sync-analysis\recorded-sync-analysis-report.json`
  和 `source-sync-analysis-report.json`。

## 16. BUG-V18-005 修复与 r13 定向复验

### 根因与实现

- 音频捕获早于视频首帧写入，但原 WAV 与封装链路没有保存二者的单调时钟关系。
- 系统回环实际起点还包含输出缓冲和默认设备周期；当前设备实测合计 `56.625 ms`。
- 修复后每条音轨记录启动时刻和设备延迟，视频记录首帧成功写入时刻，混音前按
  有效起点分别执行 `atrim` 或 `adelay`。
- `r12` 忽略设备延迟而过度补偿，已失效并保留为排查证据；`r13` 使用设备实测
  延迟完成最终复验。

### 自动验证

- 专项：`63 passed`。
- 全量：`523 passed, 1 skipped, 25 deselected, 48 subtests passed`。
- Packaging：`13 passed, 536 deselected`。
- Ruff、项目门禁 mypy、compileall 和 `git diff --check`：通过。

### r13 身份

```text
EXE: E:\QRtest\QuickRec-v1.8-candidate-20260726-r13\QuickRec\QuickRec.exe
EXE SHA256: 1ECE0901BBD0EC36ADDEBE2A04D3599E0174DAF944B5563884FA39E6F8E59321
FFprobe SHA256: 192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D
证据目录: E:\QRtest\QuickRec-v1.8-audio-sync-r13
```

最终四次音画偏移为 `+15.104 ms`、`+6.771 ms`、`+6.771 ms`、
`-18.229 ms`，最大绝对偏移 `18.229 ms`，通过 `40 ms` 门槛。
r11 的 10 分钟漂移增量为 `-8.333 ms`，通过 `20 ms` 门槛；本次仅校正固定起点，
不改变音视频节奏。D11.22 与 BUG-V18-005 均已关闭。

## 17. D12 最终发布包

版本号更新为 `v1.8` 后重新执行完整质量门禁：

- 全量与 coverage：`523 passed, 1 skipped, 25 deselected, 48 subtests passed`，
  总覆盖率 `85.39%`。
- Packaging：`13 passed, 536 deselected`。
- Ruff、项目门禁 mypy、compileall 和 `git diff --check`：通过。
- 最终分发目录包含 244 个文件，共 428,142,083 字节。
- 最终 EXE 隔离启动 5 秒，进程保持正常，随后正常结束验证进程。
- ZIP 可读取并包含 EXE、FFmpeg 和 FFprobe。
- GitHub 连接器列出的远端分支为 `lite-master`、`lite-test`、`master`、`test`；
  `v1.8` ref 查询返回不存在，当前没有同名远端冲突。

最终身份：

```text
EXE: E:\QRtest\QuickRec-v1.8-release-dist\QuickRec\QuickRec.exe
EXE SHA256: 8BDB84FB08198E927C722E41AC37276A796AD168C55183EE6C24194F2BFE7EA6
ZIP: E:\QRtest\QuickRec-v1.8-win-x64.zip
ZIP SHA256: 78AD1AA5EABCE77211607CE7135C9656923892B5D9C837F92E4EF6C961B10B27
```
