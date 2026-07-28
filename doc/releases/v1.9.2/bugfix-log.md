# QuickRec Full v1.9.2 缺陷修复记录

## 文档边界

- 只记录 v1.9.2 开发或验收阶段确认的真实缺陷与最小修复。
- 验收工具、设备或自动化环境问题单独标注，不冒充产品缺陷。
- 任务状态写入 `progress.md`，完整验收证据写入 `manual-verification.md`。

## BUG-001：播放降级日志按刷新周期重复写入

### 状态

- 严重度：一般缺陷。
- 发布影响：不影响播放结果，但会污染诊断日志并降低问题定位效率。
- 首次发现候选：RC3。
- 修复验证候选：RC4。
- 当前状态：已修复并定向复验通过。

### 复现

1. 打开包含视频和音频片段的时间线。
2. 临时移动被引用的媒体文件。
3. 播放约 4 秒。
4. 检查 `QuickRecDiagnostics\quickrec.log`。

RC3 会在约 16 毫秒的刷新周期内重复写入同一条
`timeline playback degraded` 警告。

### 根因

`PlaybackRuntime._apply_nonfatal_result()` 每次收到同一非致命
`BackendFrame` 都直接写警告，没有记忆连续降级状态。

### 最小修复

- 记录最近一次 `(error_kind, video_status, audio_status)` 降级签名。
- 连续相同签名只记录一次。
- 正常帧恢复后清空签名；后续再次降级仍记录新的告警。
- 不改变播放、占位、错误提示或恢复语义。

### 测试与证据

- 新增失败测试：
  `test_repeated_degraded_frame_logs_once_until_recovery`。
- 定向播放回归：30 项通过。
- 标准全量：850 项通过、27 项取消选择、56 项子测试通过。
- RC4 缺失素材连续播放约 4 秒，只产生两条不同状态转换告警：
  `missing_media` 与 `audio_decode_failed`，没有周期性重复。
- 证据：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\recordings\QuickRecDiagnostics\quickrec.log`。

## BUG-002：长时间线“适配”无法展示完整编排

### 状态

- 严重度：发布阻塞。
- 发布影响：30 分钟时间线只能缩放到 25%，用户无法一次查看完整编排。
- 首次发现候选：RC4。
- 修复验证候选：RC5。
- 当前状态：已修复并完成源码与打包产物定向复验。

### 复现

1. 打开包含 8 条视频轨、8 条音频轨、100 个片段、总时长 30 分钟的项目。
2. 在剪辑工作台点击“适配完整时间线”。
3. 检查缩放比例和时间线右侧是否包含 30:00 末端。

RC4 最低只能缩放到 25%，可视范围约为前 1 分 30 秒，未满足 PRD
“完整编排进入可视区域”的要求。

### 根因

- `TimelineScale` 的规范化、滚轮缩放、显式缩放和适配算法分别硬编码了
  25% 最小缩放。
- `TimelineSession` 又独立执行一次 25% 下限，导致适配算法即使计算出更小
  比例，也无法持久化到会话状态。
- 编辑器把低于 1% 的比例取整显示为 `0%`，无法准确反馈实际状态。

### 最小修复

- 新增 `src/utils/timeline_view.py`，统一时间线缩放边界和规范化函数。
- 画布与会话共用同一缩放规则，允许长时间线按当前视口计算必要比例。
- 低于 10% 的缩放标签保留一位小数，避免显示为 `0%`。
- 不改变片段模型、保存事务、播放后端或时间线交互语义。

### 测试与证据

- 先新增并确认 3 项失败测试：
  - 30 分钟时间线适配比例应低于 25%；
  - 会话应保留长时间线所需低比例；
  - `0.5%` 不得显示为 `0%`。
- 修复后 3 项通过；时间线与播放相关回归 121 项通过。
- 标准全量：
  `853 passed, 27 deselected, 56 subtests passed`。
- 总体覆盖率 82.54%；时间线核心增量覆盖率 85.60%；播放与页面协调
  增量覆盖率 80.78%。
- Packaging 15 项通过；Ruff、Mypy、Compileall 通过。
- 修复前证据：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\stress-8x8-100\evidence\D10-source-fit-bug.jpg`。
- 源码修复证据：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\stress-8x8-100\evidence\D10-source-fit-fixed.jpg`。
- RC5 打包产物证据：
  `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-fit-30min-8x8-100.jpg`。

## 验收工具事件：未重定向控制台导致停止流程表象卡住

### 判断

- 类型：验收工具问题，不是 QuickRec 产品缺陷。
- 发布影响：无。

### 证据

自动化通过 `Start-Process` 启动 GUI 时未重定向 stdout/stderr，子进程继承了无人读取
的输出管道。Py-Spy 显示主线程、录制线程和 DXCamera 线程均在等待
`logging.StreamHandler.write()` 或其处理器锁。临时 MP4 已正常封装。

改为将 stdout/stderr 重定向到独立证据文件后，同一 RC4 正常停止、保存、入库并
退出。

证据：

- `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\RC4-harness-stdout-block-pyspy.txt`
- `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\RC4-recording-stderr.log`
- `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\recordings\QuickRec_20260728_075722.mp4`

## BUG-003：项目素材变化后剪辑会话仍使用旧快照

### 状态

- 严重度：重要缺陷。
- 发布影响：素材加入、移除或重新定位后，已经打开的剪辑工作台可能继续使用
  旧项目快照。
- 首次发现候选：RC5。
- 修复验证候选：RC6。
- 当前状态：已修复并完成自动化与打包 GUI 定向复验。

### 根因与修复

- `TimelineSession` 在打开项目时保存项目快照；项目页后续修改素材时，没有把
  新快照同步到活动会话。
- 项目页新增项目内容变化信号，由会话注册表和剪辑协调器刷新项目快照，同时
  保留时间线、播放头与撤销重做历史。
- 修复不重新创建时间线，也不扩大项目或素材模型范围。

### 证据

- 自动化覆盖活动会话刷新、已打开窗口刷新以及时间线/撤销状态保持。
- RC6 关闭并重新打开剪辑工作台后，素材与时间线均为最新状态。
- 截图：
  - `E:\QRtest\QuickRec-v1.9.2-rc6-acceptance\evidence\D10-RC6-session-refresh-live.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc6-acceptance\evidence\D10-RC6-session-refresh-reopen.png`

## BUG-004：长时间播放持续保留已离开片段的解码器

### 状态

- 严重度：发布阻塞。
- 发布影响：长时间线播放时线程、句柄和内存持续增长。
- 首次发现候选：RC6。
- 修复验证候选：RC8。
- 当前状态：**已关闭**。自动化和 RC8 打包 GUI 连续 10 分钟资源曲线均通过。

### 根因与修复

- PyAV 播放后端在准备、跳转和渲染时创建片段解码器，但没有及时释放已经离开
  活动窗口的解码器。
- 后端现在在准备、跳转和每次渲染时裁剪非活动视频与音频解码器；当前片段及
  预缓冲所需资源继续保留。
- 新增 `test_inactive_clip_decoders_are_released_during_playback`，证明时间推进后
  非活动解码器会关闭且不会影响当前片段。

### 证据

- 修复后标准测试、Packaging、Ruff、Mypy 和 Compileall 均通过。
- RC6 修复前 10 分钟抽样中，线程由 332 增至 825、句柄由 2103 增至 3574、
  内存由约 852 MB 增至 980 MB；关闭剪辑工作台后资源恢复。
- RC7 长时复验因新增播放按钮问题而中止，旧候选不再作为最终证据。
- RC8 连续 10 分钟抽样中，常态线程约 56-61、句柄约 894-919、
  Working Set 约 176-181 MB；短暂峰值随后回落，没有持续累积。
- 证据：
  - `E:\QRtest\QuickRec-v1.9.2-rc8-acceptance\evidence\D10-RC8-long-playback-10min.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc8-acceptance\evidence\D10-RC8-long-playback-process.csv`

## BUG-005：暂停状态仍显示播放三角图标

### 状态

- 严重度：一般缺陷。
- 发布影响：不影响播放状态机，但按钮文字与图标语义冲突。
- 首次发现候选：RC7。
- 修复验证候选：RC8。
- 当前状态：**已关闭**。TDD、离屏视觉和 RC8 打包 GUI 定向复验均通过。

### 根因与修复

- 播放按钮只在创建时设置一次 `play` 图标；状态刷新只切换“播放/暂停”文字。
- 新增统一按钮状态方法：播放中使用 `pause` 双竖线图标，暂停、结束和未播放
  状态使用 `play` 三角图标。
- 仅在图标状态变化时重建图标，避免 16 毫秒刷新循环重复创建图标。

### 测试与证据

- 失败测试先证明播放中最后一次图标设置仍为 `play`，修复后通过。
- 新增 2 秒单素材 GUI 回归：播放在 `00:02.000` 进入“播放结束”，计时器停止，
  播放按钮恢复为播放状态。
- 播放 UI、运行时和查询定向测试：29 项通过。
- 加入 50 组连续视频/音频片段解码器边界回归后，相关联合测试 39 项通过。
- 标准全量：861 项通过、27 项取消选择、56 项子测试通过。
- 总体覆盖率 83.31%；时间线核心 85.77%；播放协调 80.96%。
- Packaging 15 项通过；Ruff、Mypy（43 个源文件）和 Compileall 通过。
- 离屏图标证据：
  `E:\QRtest\QuickRec-v1.9.2-rc8-acceptance\evidence\D10-RC8-pause-button.png`。
- 打包 GUI 证据：
  - `E:\QRtest\QuickRec-v1.9.2-rc8-acceptance\evidence\D10-RC8-pause-icon-packaged.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc8-acceptance\evidence\D10-RC8-single-2s-end.png`

### 播放终点语义

- 普通单素材时间线以最后一个片段结束点为播放终点，不会按源文件之外的时间
  继续播放。
- 30 分钟压力项目包含 100 个真实片段实例和刻意保留的空白区；同一素材可被
  多次引用，因此 30 分钟属于夹具编排时长，不是播放器延长了 2 秒素材。
- 时间线中后方仍有片段时，中间空白继续按空白播放；本版不自动压缩用户编排。

## BUG-006：录制期间剪辑工作台仍允许结构编辑

### 状态

- 严重度：发布阻塞。
- 首次发现候选：RC10。
- 修复验证候选：RC11。
- 当前状态：**已关闭**。

### 根因与修复

- 原实现只在界面显示“录制中”状态，没有把运行时只读约束下沉到时间线会话和
  命令入口；用户仍可能执行结构命令并写入项目。
- 时间线会话新增运行时只读状态，所有变更命令统一检查；剪辑工作台同步禁用
  轨道、片段和素材加入等变更控件。
- 录制状态进入时立即锁定会话，不能依赖单个按钮文案或窗口遮罩。

### 测试与证据

- 先补录制中命令被拒绝、项目不变和控件禁用失败测试，再完成最小修复。
- RC11 录制中全部结构编辑控件禁用：
  `E:\QRtest\QuickRec-v1.9.2-rc11-acceptance\evidence\D10-RC11-recording-editor-controls-disabled.png`。
- RC10 的失败证据保留：
  `E:\QRtest\QuickRec-v1.9.2-rc10-acceptance\evidence\D10-RC10-recording-readonly-mutation-not-blocked.jpg`。

## BUG-007：停止录制后剪辑工作台未解除运行时只读

### 状态

- 严重度：发布阻塞。
- 首次发现候选：RC11。
- 修复验证候选：RC12。
- 当前状态：**已关闭**。

### 根因与修复

- `QuickRecApp._set_recording_request_state()` 只更新录制页、主工作台和设置状态，
  没有通知已打开的剪辑工作台。
- 从剪辑工作台发起录制的结束分支还会在未显式恢复 `idle` 前返回。
- 应用协调器现在把所有录制状态统一传播到剪辑窗口；剪辑来源结束路径先恢复
  `idle`，再显示剪辑工作台。

### 测试与证据

- `tests/test_main_workflow.py` 新增录制状态传播和剪辑来源结束恢复测试。
- RC11 失败证据：
  `E:\QRtest\QuickRec-v1.9.2-rc11-acceptance\evidence\D10-RC11-recording-stop-lock-not-released.png`。
- RC12 日志已记录保存后
  `timeline runtime write lock changed ... active=False`。

## BUG-008：运行时解锁后标题仍显示“项目文件只读”

### 状态

- 严重度：重要缺陷。
- 首次发现候选：RC12。
- 修复验证候选：RC13。
- 当前状态：**已关闭**。

### 根因与修复

- 会话已解除运行时只读，但标题状态文本只在加载会话时计算，没有在录制状态
  切换时同步刷新。
- 剪辑窗口新增统一保存/只读状态文本方法；进入录制显示只读，退出录制恢复
  “已自动保存”，同时保留真实待保存状态。

### 测试与证据

- 失败测试先证明解锁后标题仍为只读，修复后断言恢复“已自动保存”。
- 录制锁受影响回归 `92 passed`；标准全量
  `867 passed, 27 deselected, 56 subtests passed`；Packaging `15 passed`。
- RC13 录制中证据：
  `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-recording-editor-read-only.jpg`。
- RC13 停止后证据：
  `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-recording-stop-editor-unlocked.jpg`。
- 受控项目 SHA256 前后均为
  `82A6B24B7E60F59F150DBC1B506664FE3BB35A163917713B4374965C0F5EF1FE`。

## 验收工具事件：RC10 重复进程污染

- RC10 测试过程中辅助启动方式创建了重复 QuickRec 进程，截图已重命名为
  `INVALID-D10-RC10-duplicate-process-test-contamination.jpg`。
- 该事件属于验收工具污染，不是 QuickRec 单实例缺陷，也不计入产品结论。

## BUG-009：重复启动 EXE 可创建多个 QuickRec 应用进程

### 状态

- 严重度：重要缺陷。
- 首次确认候选：RC13。
- 当前状态：**未修复，作为非阻塞已知限制登记**。
- v1.9.2 发布影响：不阻塞本版多轨时间线验收；建议后续独立治理。

### 受控复现

1. RC13 已有进程 PID `44172` 正常运行。
2. 再次启动同一锁定 EXE。
3. Windows 创建第二个 QuickRec 进程 PID `9380`，系统托盘同时出现两个
   QuickRec 图标。
4. 两个进程路径均为
   `E:\QRtest\QuickRec-v1.9.2-rc13-dist\QuickRec\QuickRec.exe`。
5. 停止 PID `9380` 后，原进程 PID `44172` 继续正常运行。

证据：

```text
E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-duplicate-app-processes.png
SHA256: 83D9EB56535850889D6DF2E8D35EF84E57AAED44606C76F05FDF302F673675C9
```

### 与 RC10 事件的区别

- RC10 截图来自验收辅助启动污染，证据已标记为无效；该历史判断保持不变。
- RC13 是在明确记录已有进程后，主动双击同一锁定 EXE 的独立受控复现，因此
  可以确认应用进程级单实例保护尚未建立。

### 风险与建议

- 多实例可能造成重复托盘、快捷键注册冲突以及配置或索引并发写入。
- 建议后续增加应用级互斥体或本地 IPC：第二实例只通知现有实例激活工作台，
  随后立即退出。
- 后续治理需补单元测试、打包进程集成测试和重复启动 GUI 验收。
- 本轮仅记录事实，不修改 RC13 业务代码，也不改变锁定候选身份。
