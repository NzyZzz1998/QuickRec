# QuickRec Full v1.9.4 Bugfix 记录

## 1. 文档边界

本文只记录 v1.9.4 候选包验收期间发现并处理的缺陷、失效候选包和已知限制。
开发任务状态仍以 `progress.md` 为准，自动验证以 `verification.md` 为准。

## 2. 已修复缺陷

### BUG-194-01 重复素材导出导致异常内存增长

| 项目 | 内容 |
| --- | --- |
| 发现阶段 | RC1 长样本门禁 |
| 严重度 | 发布阻塞 |
| 影响 | 同一素材被大量片段重复引用时，滤镜图通过 `split/asplit` 扩展，长样本内存可增长至约 79 GB，无法稳定交付 |
| 根因 | 重复片段共享同一解码输入并进行大规模分支，生命周期与缓冲叠加，不适合 100 片段长时间线 |
| 修复 | 对重复素材片段使用独立可寻址 `movie=...:seek_point=...:streams=dv/da:dec_threads=1` 输入，保持每个片段源范围独立 |
| 回归 | 1080p60、1080p120、4K60 三档 30 分钟、100 片段 RC4 导出全部完成 |
| 状态 | 已关闭 |

RC1 因该缺陷失效，不能继续作为候选包。

### BUG-194-02 导出配置数值显示为本地化符号

| 项目 | 内容 |
| --- | --- |
| 发现阶段 | RC2 GUI 验收 |
| 严重度 | 重要 |
| 影响 | 宽度、高度等 `QSpinBox` 数值在当前系统区域设置下显示为非标准数字符号，难以识别 |
| 根因 | Qt 数值控件继承系统 locale |
| 修复 | 导出配置数值控件显式使用 `QLocale.c()` |
| 证据 | `D11-RC4-export-config-ascii-digits.jpg` |
| 状态 | 已关闭 |

RC2 因该缺陷失效，不能继续作为候选包。

### BUG-194-03 导出进度 100% 显示为本地化符号

| 项目 | 内容 |
| --- | --- |
| 发现阶段 | RC3 GUI 验收 |
| 严重度 | 重要 |
| 影响 | `QProgressBar` 完成百分比不是标准 `100%` 数字样式 |
| 根因 | 进度控件继承系统 locale |
| 修复 | 导出任务进度控件显式使用 `QLocale.c()` |
| 证据 | `D11-RC4-export-success-100-percent.jpg` |
| 状态 | 已关闭 |

RC3 因该缺陷失效，不能继续作为候选包。

### BUG-194-04 导出运行时工作台录制入口未禁用

| 项目 | 内容 |
| --- | --- |
| 发现阶段 | RC4 D11 真实录制/导出互斥验收 |
| 严重度 | 重要 |
| 影响 | 应用级互斥可以阻止录制，但工作台三个录制按钮仍可点击，只通过托盘通知反馈，不符合 PRD“入口禁用并说明原因” |
| 根因 | `MediaOperationGuard` 只在录制请求回调中判定，`RecordingPage` 没有订阅或轮询导出运行状态 |
| 失败测试 | `test_recording_page_disables_all_modes_while_export_is_active`、`test_export_runtime_state_is_reflected_on_recording_page` 修复前均因缺少同步接口失败 |
| 修复 | `RecordingPage` 以 250 ms 周期读取应用协调层提供的唯一 Guard 判定；导出运行时禁用全屏、区域、窗口入口并就近展示原因，导出结束后自动恢复 |
| 自动回归 | 76 项受影响回归、1228 项全量测试、84.10% 覆盖率、19 项 Packaging 及全部静态门禁通过 |
| GUI 证据 | `E:\QRtest\QuickRec-v1.9.4-rc5-acceptance\gui\evidence\D11-RC5-export-running-recording-entry-disabled.png` |
| 状态 | 已关闭 |

RC4 因该 PRD 偏差失效，不能继续作为候选包。

### BUG-194-05 提交前目标冲突留下完整候选文件

| 项目 | 内容 |
| --- | --- |
| 发现阶段 | RC5 D11 目标保护复验 |
| 严重度 | 发布阻塞 |
| 影响 | FFmpeg 与 FFprobe 已成功生成并验证候选文件后，提交器因既有目标冲突拒绝提交；任务正确失败且旧目标未被覆盖，但完整 `.part.mp4` 留在输出目录，占用与正式导出相当的磁盘空间 |
| 根因 | `FormalExportAttemptRunner` 在提交失败后直接返回结果，没有区分“尚未创建提交事务”的普通拒绝与“已有事务记录”的不确定提交；前者缺少候选文件清理 |
| 失败测试 | `test_formal_attempt_runner_removes_candidate_after_pretransaction_commit_failure` 修复前可稳定复现；`test_formal_attempt_runner_preserves_candidate_for_ambiguous_commit_transaction` 同时保护不确定事务证据 |
| 修复 | 提交失败且不存在 `transaction_path` 时清理本次候选文件；存在事务记录时继续保留候选、备份和事务文件，由恢复流程处理；清理失败会追加脱敏异常类型 |
| 自动回归 | 135 项受影响回归、1230 项全量非硬件测试、84.10% 覆盖率、19 项 Packaging 及全部静态门禁通过 |
| Frozen 证据 | `E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup\evidence\after.json` |
| GUI 证据 | `E:\QRtest\QuickRec-v1.9.4-rc6-acceptance\candidate-cleanup\evidence\D11-RC6-target-conflict-candidate-cleaned.jpg` |
| 状态 | 已关闭 |

RC5 因该磁盘清理缺陷失效，不能继续作为候选包。RC6 使用同一 6 秒、8 路音频、
中文空格路径冻结计划进行真实打包复验：旧目标前后 SHA256 均为
`9E7E65BF6EBC8BA796F583B151BCB5F115E1BFD8E39150373E7192CD3C1281A3`，
本次 `attempt-d498e87cfd444156acf9e97378cda38d` 的候选文件不存在，历史两份失败
证据哈希保持不变，且没有残留 FFmpeg 进程。

### BUG-194-06 停滞状态未持久化且无法主动继续等待

| 项目 | 内容 |
| --- | --- |
| 发现阶段 | RC6 D11 真实停滞语义验收准备 |
| 严重度 | 发布阻塞 |
| 影响 | Executor 能产生停滞快照并在 300 秒后终止，但队列任务没有持久 `stalled` 状态，GUI 无法稳定表达 120 秒警告，也没有“继续等待”操作来重置当前 attempt 的停滞计时 |
| 根因 | 停滞只存在于瞬时进度回调；`ExportJob`、`ExportQueueService` 和导出页之间缺少持久状态及由 UI 回传给执行器的控制信号 |
| 失败测试 | 新增停滞状态序列化、队列持久化、非停滞拒绝、继续等待信号、Executor 计时重置和 GUI 操作合同；修复前缺少对应字段与接口 |
| 修复 | `ExportJob` 增加向后兼容的 `stalled` 字段；队列持久化停滞状态并提供 `continue_waiting(job_id)`；`CancellationToken` 传递一次性继续等待信号；Executor 重置停滞窗口；导出页显示“可能停滞”、120 秒说明和“继续等待”按钮 |
| 自动回归 | 新增 5 项通过，停滞相关 61 项通过，受影响范围 249 项通过；全量 1235 项通过、31 项跳过，覆盖率 84.11%；19 项 Packaging 通过 |
| GUI 证据 | `E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\stall\evidence\D11-RC7-*.png` |
| 结构化证据 | 同目录 `stall-warning-120.json`、`continue-waiting-reset.json`、`continue-waiting-progress-resumed.json`、`stall-timeout-300-result.json` |
| 状态 | 已关闭 |

RC6 因缺少可验收的完整停滞交互而失效。RC7 在冻结 FFmpeg 后约 121.7 秒持久
显示停滞警告；点击“继续等待”后同一 attempt 从 8% 恢复到 11%。另一独立
attempt 在约 338.053 秒完成终止和清理，符合 300 秒停滞阈值及后续清理开销，
且没有正式输出、候选文件、过滤脚本或残留媒体进程。

### BUG-194-07 未完成队列任务的输出目标未参与预留

| 项目 | 内容 |
| --- | --- |
| 发现阶段 | RC7 Windows 系统重启恢复与后续队列复验 |
| 严重度 | 发布阻塞 |
| 影响 | 两个未完成任务可冻结为同一正式输出路径；先完成的任务占用目标后，后完成任务会在长时间编码和验证结束时才以目标冲突失败，浪费时间和磁盘资源 |
| 根因 | `ExportPlanBuilder` 仅检查当前文件系统是否存在同名目标，不知道持久队列中未完成任务已预留的目标；`enqueue()` 也缺少竞态下的最终唯一性检查 |
| 失败测试 | `test_reserved_queue_targets_are_included_in_safe_suffix_selection`、`test_enqueue_rejects_target_reserved_by_another_incomplete_job` 修复前失败 |
| 修复 | 预检把未完成队列任务的规范化目标路径传入计划构建器，安全后缀同时跳过文件系统目标和队列预留目标；`enqueue()` 增加最终竞态校验 |
| 自动回归 | 新增两项失败测试通过，受影响模块定向回归 65 项通过；全量 1238 项通过、31 项排除、66 个子测试通过 |
| GUI 证据 | `E:\QRtest\QuickRec-v1.9.4-rc8-acceptance\evidence\D11-RC8-queued-target-safe-suffix.jpg` |
| 结构化证据 | 同目录 `D11-RC8-queued-target-safe-suffix-queue.json` |
| 状态 | 已关闭 |

### BUG-194-08 真实 Windows 150% 下导出配置底栏被裁切

| 项目 | 内容 |
| --- | --- |
| 发现阶段 | RC7 D11 三档 DPI 验收 |
| 严重度 | 发布阻塞 |
| 影响 | 导出配置窗口在 150% 缩放和较小可用桌面区域下超出可视范围，底部取消、预检和加入队列操作不可完整访问 |
| 根因 | 对话框固定最小高度，没有根据当前屏幕 `availableGeometry()` 收敛尺寸和位置 |
| 失败测试 | `test_export_dialog_fits_footer_inside_small_available_geometry` 修复前失败 |
| 修复 | 降低基础最小尺寸，并在 `showEvent()` 中按当前屏幕可用区域限制窗口大小、居中和保持底栏可见 |
| 自动回归 | 新增布局失败测试通过；受影响模块定向回归 65 项通过 |
| 失败证据 | `E:\QRtest\QuickRec-v1.9.4-rc7-acceptance\remaining\evidence\D11-RC7-windows-dpi-150-export-dialog-clipped.png` |
| 修复证据 | `E:\QRtest\QuickRec-v1.9.4-rc8-acceptance\evidence\D11-RC8-qt-scale-150-export-dialog-footer-visible.jpg`、`D11-RC8-windows-dpi-150-export-dialog.png`、`D11-RC8-windows-dpi-150-overwrite-confirm.png` |
| 状态 | 已关闭；RC8 已通过真实 Windows 125%/150% 系统缩放复验 |

RC7 因上述两个缺陷失效，不能作为发布候选。RC8 为当前候选。

## 3. 已知限制

### LIMIT-194-01 强制结束进程可能留下可归属临时文件

| 项目 | 内容 |
| --- | --- |
| 场景 | 在长任务运行中强制结束 QuickRec 和子 FFmpeg，用于验证中断恢复 |
| 实际结果 | 队列可恢复为 `interrupted`，新 attempt 不复用旧候选文件；旧 `.filter.txt` 和 `.part.mp4` 仍保留 |
| 数据安全 | 没有覆盖旧目标，没有生成错误正式文件，临时文件可以根据 attempt 身份明确归属 |
| 当前处理 | 产品负责人确认作为 v1.9.4 已知缺陷保留；受控验收样本继续作为失败证据，不自动删除 |
| 发布影响 | 不阻塞 v1.9.4 发布；后续版本必须新增只删除“可证明过期且不再被引用”临时文件的治理任务，并重新执行强制中断与系统重启验收 |

证据位于受控长样本输出目录，包含：

```text
.quickrec-export-attempt-56d76...filter.txt
.quickrec-export-attempt-56d76...part.mp4
```

不得在缺少队列、attempt 和进程归属证明时批量删除 `.part.mp4`。

2026-07-30 复核结果：

- 真实系统重启验收目录 `remaining` 中不存在残留的
  `.quickrec-export-attempt-*` 文件；
- 更早的强制结束验收目录 `stall` 仍保留一组可归属的过滤脚本和未完成
  MP4，证明极端终止路径仍存在治理缺口；
- 后续修复应在启动恢复完成后，结合队列状态、`attempt_id`、提交事务和活动
  进程进行精确清理，禁止按通配符批量删除。

## 4. 候选包有效性

| 候选包 | 状态 | 原因 |
| --- | --- | --- |
| RC1 | 失效 | 重复素材长样本内存异常 |
| RC2 | 失效 | 配置数值本地化符号 |
| RC3 | 失效 | 进度百分比本地化符号 |
| RC4 | 失效 | 导出运行时工作台录制入口未禁用 |
| RC5 | 失效 | 提交前目标冲突留下完整候选文件 |
| RC6 | 失效 | 缺少持久停滞状态和“继续等待”控制语义 |
| RC7 | 失效 | 未完成队列目标可冲突；真实 Windows 150% 下导出配置底栏被裁切 |
| RC8 | 当前有效候选 | 已关闭排队目标冲突并通过真实 Windows 125%/150% 导出配置复验；D11 仍有听音补证项 |

## 5. 当前结论

已确认的八个候选包缺陷均已修复。RC8 已完成排队目标安全后缀、150% Qt
等效缩放定向复验和真实 Windows 125%/150% 复验；RC7 的真实停滞、系统重启恢复，RC6 的目标保护、候选清理、
入库重试、覆盖和取消，RC5 的录制入口互斥以及 RC4 的导出长样本继续作为
未受后续修复影响的继承证据。D11 尚有八路真实听音和麦克风清晰人声回归
补证，不能据此宣布 v1.9.4 可发布。
