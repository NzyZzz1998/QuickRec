# QuickRec Full v1.9 Bugfix 记录

## BUG-V19-001 项目录制成功反馈被页面刷新覆盖

### 基本信息

- 发现阶段：D8 GUI 手动验收
- 发现日期：2026-07-26
- 影响候选包：`E:\QRtest\QuickRec-v1.9-dist\QuickRec\QuickRec.exe`
- 旧候选包 SHA256：`805D58EA2446581856AFF781D2528ABAEB3374E41ACC8626543F4C9C295B7D5C`
- 严重度：发布阻塞
- 数据影响：无数据丢失；视频、中央素材索引和项目引用均成功写入

### 复现步骤

1. 在工作台项目页打开一个活跃、可写项目。
2. 从项目页发起全屏录制。
3. 正常停止并等待视频保存完成。
4. 检查项目文件和中央素材索引，确认新素材已经写入。
5. 检查恢复后的项目页状态栏。

### 预期结果

项目页显示：

```text
视频已保存；素材已入库；项目已关联
```

### 实际结果

视频、中央素材索引和项目引用均写入成功，但项目页恢复时重新加载页面，
状态栏被先前状态覆盖，用户看不到三段成功反馈。

### 根因

`QuickRecApp._handle_saved()` 先调用
`ProjectPage.show_recording_result()` 写入三段结果，再调用
`_finish_recording_request()` 恢复工作台。

恢复工作台会执行 `_show_workbench(WorkbenchPage.PROJECTS)`，其中再次调用
`ProjectPage.reload()`，覆盖刚写入的状态栏文本。失败结果链路存在相同顺序问题。

### 修复

- 项目录制成功或失败时，先隐藏录制工具栏并恢复、刷新项目页。
- 页面刷新完成后再调用 `show_recording_result()` 写入最终三段状态。
- 不修改录制、素材入库和项目关联的数据事务。

### 自动化验证

- 新增调用顺序断言，修复前稳定失败：

```text
期望：reload -> result
实际：result -> reload
```

- 修复后定向测试：

```text
2 passed
```

- `tests/test_main_workflow.py`：

```text
40 passed
```

### 定向复验要求

新候选包必须重新验证：

1. 项目内全屏、区域、窗口录制均成功保存。
2. 中央素材索引和项目引用均写入同一素材 ID。
3. 恢复工作台后显示三段成功状态。
4. 项目录制保存失败时显示三段失败状态，且不会被页面刷新覆盖。

## BUG-V19-002 中央素材索引被占用时归档失败

### 基本信息

- 发现阶段：D8 失败降级验收
- 发现日期：2026-07-26
- 严重度：发布阻塞
- 数据影响：视频文件仍可保存；旧候选包可能在读取或归档被占用的索引时中断入库降级链路

### 根因与修复

Windows 下 `recordings.json` 被独占打开时，索引读取失败后的损坏归档复制也可能因共享模式限制再次失败。旧逻辑未把第二次失败纳入可恢复错误。

- 将索引读取锁定与归档复制失败统一识别为暂态存储错误。
- 不删除、不覆盖被占用索引。
- 录制成功事实保持不变，并进入待入库持久化链路。
- 补充锁定读取、归档失败与恢复后的回归测试。

### 复验

R7 在索引被占用时正常保存 `QuickRec_20260727_003642.mp4`，日志记录 `FORMAL_INDEX_WRITE_FAILED`，解除占用并重启后待入库记录自动恢复成功。

## BUG-V19-003 持久重试未继续关联原项目

### 基本信息

- 发现阶段：D8 三段失败降级验收
- 发现日期：2026-07-26
- 严重度：发布阻塞
- 数据影响：视频和中央素材均未丢失；旧候选包在待入库重试成功后未继续关联原项目

### 根因与修复

素材库持久重试只完成中央素材入库，没有把成功结果和原始 `project_id` 继续交给项目协调器。

- 素材库页面在待入库成功后发出包含素材和项目上下文的信号。
- 应用协调器幂等执行原项目关联，并刷新项目页。
- 关联失败时保留全局素材并显示准确反馈，不误报视频保存失败。
- 增加成功、失败和重复重试测试。

### 复验

R4 受控证据显示中央索引 1 条、待入库 0 条、项目 1 条，三处使用同一素材 ID：

```text
E:\QRtest\QuickRec-v1.9-acceptance\d8-r4-20260726-235149\Evidence\D8-7-r4-persistent-retry-project-associated.json
```

## BUG-V19-004 低概率停止录制卡在采集资源释放

### 基本信息

- 发现阶段：D8 快捷键和索引失败组合回归
- 发现日期：2026-07-27
- 严重度：发布阻塞
- 数据影响：旧候选包出现一次编码已完成但录制线程未结束，需要终止进程

### 根因与修复

停止流程先关闭编码器，再同步等待 dxcam 采集线程释放。极端时序下，采集线程仍在等待帧事件，`camera.release()` 可能长期阻塞，导致后续保存回调无法完成。

- `RecorderManager.stop()` 先发送兼容 dxcam 0.3.x 的异步停止事件，再刷新编码器。
- `ScreenCapturer.close()` 将 `camera.release()` 放入守护释放线程，并仅等待 1 秒。
- 超时只记录明确告警，不无限阻塞视频保存收口。
- 增加私有事件可用、契约不可用、释放阻塞和调用次数测试。

### 自动化与复验

- 全量测试：`641 passed, 25 deselected, 52 subtests passed`。
- 总体覆盖率：`85.77%`。
- R7 连续 3 次普通录制和 1 次索引被占用录制均一次停止成功。
- 四次日志均记录异步停止，采集释放在 `4-10 ms` 内完成。
- 当前源码两轮硬件 smoke 均返回 `OK: video stream ok`。

## BUG-V19-005 录制页默认突出全屏录制

### 基本信息

- 发现阶段：D8 R7 候选包 GUI 复验
- 发现日期：2026-07-27
- 影响候选包：R7
- 严重度：重要缺陷，阻塞最终视觉验收
- 数据影响：无

### 根因

`RecordingModeCard` 仍保留 v1.8 的 `primary` 参数和 `role=primary` 属性，录制页又只为“全屏录制”传入主角色，导致它呈现为蓝色主按钮。v1.9 已确认的原型要求三种录制模式平级且默认无选中态。

新增失败测试后，修复前实际角色为：

```text
['primary', None, None]
```

### 修复

- 删除 `RecordingModeCard` 的 `primary` 参数和主角色赋值。
- 全屏、区域、窗口三个入口统一使用同级次要按钮。
- 不改变三类录制的信号、业务流程或快捷入口。

### 自动化与复验

- 新增 `test_recording_page_presents_all_modes_as_peer_actions`。
- 录制页定向测试：`7 passed`。
- 相关页面回归：`92 passed`。
- 全量测试：`642 passed, 25 deselected, 52 subtests passed`。
- 总体覆盖率：`85.76%`。
- Packaging：`13 passed, 654 deselected`。
- Ruff、mypy、compileall 和 `git diff --check`：通过。
- R7 因视觉回退失效；R8 EXE SHA256 为 `CFE6BC6D4FC342039A0B410B4CF80FC9A34BAD47908F671AE9161FC63F7A9D47`。
- R8 GUI 截图：`E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-recycle-20260727-094500\Evidence\D8-R8-recording-modes-peer.png`。

## BUG-V19-006 GitHub CI 打包环境缺少 FFmpeg 工具

### 基本信息

- 发现阶段：v1.9 `test` 分支发布前 CI
- 发现日期：2026-07-27
- 影响范围：GitHub Windows packaging smoke
- 严重度：发布工程阻塞
- 数据影响：无；业务代码、锁定 R8 包和用户数据均不受影响

### 根因

本地 `ffmpeg/` 按项目约定被 `.gitignore` 排除，`build_std.spec` 又明确要求
`ffmpeg.exe` 和 `ffprobe.exe`。GitHub 全新检出环境没有本地二进制，因此 PyInstaller
在收集数据文件前失败。基础测试、ruff、mypy 和 coverage 任务均已通过。

### 修复

- Windows packaging job 使用 Chocolatey 准备真实 FFmpeg 工具。
- 从实际安装目录复制 FFmpeg/FFprobe，不打包 Chocolatey shim。
- 复制后校验两个文件大小并实际执行 `-version`。
- 新增打包配置测试，确保工具准备步骤位于 PyInstaller 构建之前。

### 自动化与复验

- 本地 packaging：`14 passed, 654 deselected`。
- Ruff 与 `git diff --check`：通过。
- GitHub CI 运行 `30242128803`：
  - Windows test baseline：通过。
  - Windows packaging smoke：通过。
