# QuickRec Full v1.9.5 自动验证记录

## 1. 验证结论

| 项目 | 结果 |
| --- | --- |
| 验证阶段 | D8 自动化与候选包；D9 GUI、真实媒体与回归 |
| 结论 | D8 通过；D9 通过（31/31） |
| 发布判断 | 验收通过并完成正式发布收口 |
| 验证日期 | 2026-07-31 |
| 当前分支 | `test` |
| 基线提交 | `b3b8267e1950b8e2b9efc6d28d29b501189fd7af` |
| 候选应用版本 | `v1.9.5` |
| 验收时正式版本 | `v1.9.4` |
| 代码回滚点 | tag `v1.9.4` |

本候选包由尚未提交的 v1.9.5 工作区生成。候选身份由分发目录、二进制
SHA256、冻结 CLI 身份和本文件共同锁定。此前生成的
`E:\QRtest\QuickRec-v1.9.5-dist` 自报版本为 v1.9.4，已明确失效；RC2 又在
D9 中暴露工具栏动画后回落到屏幕中部的问题，也已失效。D9 后续证据只能使用
RC3，或在影响分析明确后继承不受工具栏修复影响的 RC2 证据。

2026-07-31，使用恢复后的默认 GS03 完成 D9.24 最终补证。麦克风样本可听见
口述，双音频样本可同时听见系统测试音和口述；两类样本均由同一锁定 RC3
生成，并通过 FFprobe、SHA256 和音量复核。本结论仍不等于授权 commit、
push、tag 或 Release。

## 2. 候选包身份

| 对象 | 路径或值 |
| --- | --- |
| 分发目录 | `E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec` |
| 构建目录 | `E:\QRtest\QuickRec-v1.9.5-rc3-build` |
| 分发目录规模 | `503984630` 字节，318 个文件 |
| GUI | `E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec\QuickRec.exe` |
| GUI 大小 / 时间 | `7531404` 字节 / `2026-07-31 02:15:15` |
| GUI SHA256 | `705B227FE33F31D4EE650334D607CAAA919FC3D1B44C633CEA1E5B75B3B4A226` |
| CLI | `E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec\QuickRecCLI.exe` |
| CLI 大小 / 时间 | `6724578` 字节 / `2026-07-31 02:15:15` |
| CLI SHA256 | `1133802A8BB999B7CE198BB9EBF3F4F9D7C8160C9C9798C0248E28F940F0E386` |
| FFmpeg | `_internal\ffmpeg\ffmpeg.exe` |
| FFmpeg SHA256 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| FFprobe | `_internal\ffmpeg\ffprobe.exe` |
| FFprobe SHA256 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |
| PyAV | 包内 `_internal\av`，冻结运行时版本 `18.0.0` |

构建命令：

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm `
  --distpath E:\QRtest\QuickRec-v1.9.5-rc3-dist `
  --workpath E:\QRtest\QuickRec-v1.9.5-rc3-build
```

PyInstaller 成功生成同一 onedir 中的 GUI 和 CLI。构建日志保留
`pycparser.lextab`、`pycparser.yacctab`、`sip` 隐式导入提示，以及
license expression 校验提示；Packaging、冻结 CLI、PyAV、FFmpeg 和
FFprobe 的实际运行均通过，未形成当前阻塞。

## 3. 自动化测试

### 3.1 分层定向验证

| 层级 | 结果 |
| --- | --- |
| D1-D7 非 Qt 服务、领域与集成回归 | `210 passed` |
| TimelineEditorWindow | `8 passed` |
| 剪辑交互 UI | `14 passed` |
| 编辑窗口 UI | `22 passed` |
| 播放 UI | `14 passed` |
| D6 新增界面合同 | `7 passed` |
| Qt 分文件隔离合计 | `65 passed` |
| D7 保存、播放、导出与 CLI 集成 | `200 passed` |

Qt 测试按文件使用独立进程，避免 Windows 下多个 PyQt 测试文件共享进程时的
既有原生访问冲突。

### 3.2 最终源码状态全量验证

默认非硬件、非 Packaging：

```text
1425 passed, 32 deselected, 72 subtests passed
```

Packaging 单独验证：

```text
20 passed, 1437 deselected
```

版本事实源更新后的版本、诊断与主流程定向回归：

```text
70 passed
```

### 3.3 Coverage

覆盖率文件：

```text
E:\codex\QuickRec\build\coverage-v1.9.5-rc3.json
```

结果：

```text
1425 passed, 32 deselected, 72 subtests passed
Total coverage: 84.14%
```

| 分组 | 实际覆盖率 | 门槛 | 结果 |
| --- | ---: | ---: | --- |
| 时间线剪辑核心 | 88.26% | 85% | 通过 |
| 时间线 UI 协调 | 80.13% | 80% | 通过 |
| v1.9.5 领域核心 | 95.24% | 85% | 通过 |
| v1.9.5 UI 协调 | 97.75% | 80% | 通过 |
| QuickRec CLI 核心 | 88.04% | 85% | 通过 |
| 导出计划与持久化 | 90.08% | 90% | 通过 |
| 导出执行与 CLI | 87.44% | 85% | 通过 |
| 导出 UI 协调 | 88.48% | 80% | 通过 |

覆盖率 omit 未扩大。录制工具栏新增的纯布局逻辑已抽取到
`src/ui/toolbar_placement.py`，并纳入 v1.9.5 UI 协调门禁。

## 4. 静态、文档与原型门禁

| 检查 | 结果 |
| --- | --- |
| Ruff | 通过；历史 pytest 临时目录仅产生 4 条访问拒绝警告 |
| Mypy | 通过，83 个源文件无问题 |
| Compileall | 通过 |
| `git diff --check` | 通过，仅有既有 LF/CRLF 提示 |
| UTF-8 与乱码检查 | 通过 |
| 文档状态与内部链接 | 通过 |
| 原型 JavaScript 与交互合同 | 通过 |
| 原型 1440×900 / 1216×760 / 960×640 | 通过，无缺失合同、未命名按钮或溢出 |

原型共校验 239 个已注册、已命名且带版本说明的交互合同。正式 GUI 的真实
100%、125%、150% DPI 仍属于 D9，不由 HTML 原型验证替代。

## 5. Frozen CLI 与真实导出

### 5.1 运行时身份

`doctor --json` 实际报告：

```text
product=QuickRec Full
version=1.9.5
frozen=true
python=3.12.8
ffmpeg=8.0.1
ffprobe=8.0.1
pyav=18.0.0
gui_initialized=false
```

### 5.2 编辑 smoke

证据目录：

```text
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\cli-workspace
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\cli-editing-smoke
```

结果：

- 输入项目未被修改；
- timeline schema v2；
- 裁剪、分割、失败回滚、播放计划与重载全部通过；
- 生成 2 条轨道、4 个片段；
- `project validate` 与 `timeline validate` 均返回稳定 JSON v1。

### 5.3 真实 FFmpeg 导出 smoke

RC2 曾使用 v1.9.4 已验收的 8 路音频项目作为只读输入，完成正式
PlanBuilder、Executor、Verifier 和 Committer 验证。工具栏修复不影响导出
模块，因此该 8 路证据继续作为继承证据。RC3 另行使用删除/波纹受控项目执行
冻结包短样本导出：

```text
RC3 输入：
E:\QRtest\QuickRec-v1.9.5-rc2-acceptance\projects\d9-delete-ripple-export\project.qrproj

RC3 输出：
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\exports\QuickRec-export-smoke.mp4

RC3 证据：
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\cli-export-smoke\export-smoke.json
```

结果：

| 项目 | 值 |
| --- | --- |
| 状态 | `succeeded` |
| 项目 | 2 条轨道、3 个片段、2 个素材 |
| 输出 | H.264 / AAC |
| 画面 | 640×360，30 FPS |
| 音频 | AAC，48 kHz，双声道 |
| 时长 | 4.000 秒 |
| 文件大小 | 55668 字节 |
| 输出 SHA256 | `330B4754F584986623D58107950311DE147BBF8039E061DFFA48C76D1D8D6B56` |

## 6. D8 判断与 D9 边界

D8 的自动化、静态、Coverage、Packaging、候选包内容、冻结 CLI 和真实短样本
导出均通过。RC3 是 D9 唯一允许继续使用的候选身份；RC2 仅保留不受
`BUG-195-01` 影响的历史验收证据。

以下项目尚未因此自动通过，必须在 D9 使用真实 GUI、真实媒体和桌面环境验证：

- 快捷键焦点与可见反馈；
- 解绑、重新关联、普通删除与波纹删除的 GUI 链路；
- 拖放预览、吸附、自动建轨、取消和轨道上限；
- 30/60/120 FPS 帧时间；
- 8+8 轨、100 片段、30 分钟和 50 步历史；
- 全屏、区域、窗口录制工具栏位置；
- 四类音频真实听音；
- 100%、125%、150% DPI；
- v1.9.4 全功能回归和 QuickRec Lite 零修改确认。

## 7. D9 RC3 补充复验

在不修改 RC3 分发目录的前提下，补齐以下真实桌面和恢复证据：

| 验证项 | 结果 | 证据 |
| --- | --- | --- |
| 原生有效拖放 | 通过 | 真实 Windows 指针触发 Qt 拖放，片段提交并自动保存 |
| 锁定轨拒绝 | 通过 | 显示“目标轨道已锁定”，项目保持 3 轨/4 片段 |
| 条件性自动建轨 | 通过 | 项目持久化为 4 轨/5 片段 |
| 拖出画布取消 | 通过 | 项目哈希、mtime、大小、轨道数和片段数不变 |
| 系统级 DPI | 通过 | 100%、125%、150% 和 960×640；结束后恢复 100% |
| 超时取消清理 | 通过 | frozen CLI 退出码 5，仅保留非归属哨兵 |
| 进程中断恢复 | 通过 | `running` 恢复为 `interrupted`，归属临时文件被清理 |
| 麦克风与双音频 | 通过 | GS03 麦克风口述可听；双音频系统测试音和口述均可听；两类输出均为 H.264/AAC，FFprobe、SHA256 和音量证据完整 |

主要证据目录：

```text
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\native-drag\evidence
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\temp-cleanup-cancel
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\interruption-recovery
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\audio-listening
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\mic-gs03-retest2-20260731
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\both-gs03-retest-20260731
```

最终音频补证的关键结果：

```text
麦克风 MP4 SHA256:
1E2755AFAFB1B6746357CFA1D45F69E896C864F626925F097196A96D9BFC4766
麦克风音量: mean -42.4 dB / max -24.2 dB

双音频 MP4 SHA256:
DCE037E2ACC33BBE7900DE873F770DAB6570D4602FDF5F714DED8F687D03AEF9
双音频音量: mean -27.1 dB / max -19.6 dB
```

当前结论为：**D8 通过；D9 `31/31` 全部通过。无声、系统声音、麦克风和
双音频四类音频均有锁定候选包证据，其中麦克风与双音频已由用户完成真实
听音确认。v1.9.5 可以进入发布收口。**

## 8. D10 发布资料核验

2026-07-31 已完成发布资料和正式发布收口核验：

- README 和 `doc/current.md` 已将 v1.9.5 标记为当前正式版本；
- `doc/current.md`、release notes、changelog、progress 和手动验收状态一致；
- README、current 和 release notes 均包含向下编辑兼容警告及跨版本备份提示；
- README、current 及 v1.9.5 目录内共 12 个 Markdown 文档的相对链接检查通过；
- 同一组 12 个文档严格 UTF-8 解码和乱码特征扫描通过；
- `git diff --check` 通过，仅有仓库既有 LF/CRLF 转换提示；
- RC3 GUI、CLI、FFmpeg 和 FFprobe SHA256 已从磁盘重新计算并与文档一致；
- `v1.9.4^{}` 仍指向
  `b3b8267e1950b8e2b9efc6d28d29b501189fd7af`；
- `E:\codex\QuickRec-Lite` 位于 `lite-master` 且工作区干净；
- 正式 ZIP 已生成，SHA256 为
  `0B4F90B0202B2F0296B463BFF196B04E7C0BCA6709A245037E390AC1B7185D59`；
- 用户已经授权执行 commit、push、annotated tag 和 GitHub Release。

D10 为 18/18；D9.24 已完成最终补证并通过。

发布授权后生成的正式 ZIP：

```text
E:\QRtest\QuickRec-v1.9.5-win-x64.zip
SHA256: 0B4F90B0202B2F0296B463BFF196B04E7C0BCA6709A245037E390AC1B7185D59
```

## 9. 最终自动预检与提交边界

2026-07-31 在当前未提交 v1.9.5 工作区重新执行完整非硬件发布前门禁：

```text
非硬件、非 Packaging：1425 passed, 32 deselected, 72 subtests passed
Packaging：20 passed, 1437 deselected
总体 Coverage：84.14%
timeline-editing-core：88.26%
timeline-editing-ui-coordination：80.13%
v1.9.5-domain-core：95.24%
v1.9.5-ui-coordination：97.75%
quickrec-cli-core：88.04%
export-planning-and-persistence：90.08%
export-execution-and-cli：87.44%
export-ui-coordination：88.48%
Ruff：通过
Mypy：83 个源文件通过
Compileall：通过
git diff --check：通过，仅有 LF/CRLF 转换提示
```

最新 Coverage JSON：

```text
E:\codex\QuickRec\build\coverage-v1.9.5-preflight.json
```

后续 v1.9.5 提交应包含：

- 当前已修改的 v1.9.5 生产代码、测试、门禁配置、README 和 `doc/current.md`；
- `doc/archive/ideas/mypm-idea-pool-v1.9.5-2026-07-30.md`；
- `doc/releases/v1.9.5/**`；
- 新增的 v1.9.5 服务、UI 协调、工具栏定位、临时清理及对应测试。

以下四份独立 v2.0 治理文档不属于 v1.9.5，必须继续保持未暂存并排除：

```text
doc/technical/QuickRec-v2.0-架构优化实施与验证.md
doc/technical/QuickRec-v2.0-架构优化方案.md
doc/technical/QuickRec-架构审计报告.md
doc/technical/v2.0-repository-attribution-governance.md
```

本次预检没有修改 QuickRec Lite，没有移动 tag，也没有执行任何外部 Git 写操作。
