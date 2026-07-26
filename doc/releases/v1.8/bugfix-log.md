# QuickRec Full v1.8 Bugfix 记录

## BUG-V18-001：静态桌面停止录制时线程无法退出

### 状态

- 严重度：发布阻塞。
- 发现阶段：D10 候选包前硬件 smoke。
- 当前状态：已修复，自动测试与真实硬件定向复验通过。
- 影响范围：全屏、区域和窗口录制共用的 dxcam 帧读取链路。

### 复现

1. 在没有持续可见变化的桌面启动录制。
2. dxcam 已建立帧缓冲，但尚未提供首个新桌面帧。
3. 请求停止录制。
4. 录制状态持续停留在停止中，`wait_until_idle()` 超时。

失败线程证据：

```text
record_loop -> ScreenCapturer.capture_frame()
            -> dxcam.get_latest_frame()
stop_thread -> RecorderManager._stop_and_encode()
            -> record_thread.join()
```

### 根因

dxcam 0.3.0 的 `get_latest_frame()` 会循环等待帧可用。桌面没有新帧时，该调用无法返回，录制线程因而无法重新检查 `_stop_event`，停止线程又在等待录制线程退出，形成无限等待。

### 修复

- `ScreenCapturer.capture_frame()` 改为读取 dxcam 当前环形缓冲区的非阻塞 `grab()`。
- 首次无帧时短暂等待并再读取一次；仍无帧则返回 `None`，由录制循环重新检查停止状态。
- 不改变 FFmpeg、编码帧率、录制状态机或音频链路。
- 将 `screen_capturer.py` 纳入 mypy 和 coverage，不再依赖旧排除项隐藏质量结果。

### 验证

- 失败测试先证明旧实现调用阻塞 API，修复后通过。
- `tests/test_screen_capturer.py` 非硬件测试：`11 passed, 8 deselected`。
- 模块覆盖率：`92%`，高于 80% 门槛。
- 受影响定向测试：`65 passed, 8 deselected`。
- 动态桌面 30 FPS smoke：285 帧，视频流可解析。
- 动态桌面 60 FPS smoke：566 帧，视频流可解析。
- 最终候选包真实快捷键录制：939 帧，正常停止、保存并进入中央素材索引。

### 证据

- 30 FPS：`E:\QRtest\QuickRec-v1.8-workbench-acceptance-20260724\source-smoke-calc-30`
- 60 FPS：`E:\QRtest\QuickRec-v1.8-workbench-acceptance-20260724\source-smoke-calc-60`
- 最终候选包：`E:\QRtest\QuickRec-v1.8-workbench-candidate-20260724-r3\QuickRec`
- 最终候选输出：`E:\QRtest\QuickRec-v1.8-workbench-acceptance-20260724-r3\recordings\QuickRec_20260724_033313.mp4`

### 回退

如该修复引入新的 dxcam 兼容问题，可回退 `screen_capturer.py` 与对应测试；但不得恢复为无限等待而直接发布，应重新设计可中断的帧等待契约。

## BUG-V18-002：工作台同进程页面记忆被托盘入口重置

### 状态

- 严重度：重要缺陷。
- 发现阶段：D11 候选包 GUI 验收。
- 当前状态：已修复，自动测试与 `r5` 真实桌面定向复验通过。
- 影响范围：工作台托盘入口、关闭隐藏和同进程页面记忆。

### 复现

1. 打开工作台并切换到“素材库”。
2. 点击工作台关闭按钮，使窗口隐藏但不退出 QuickRec。
3. 双击托盘图标重新打开工作台。
4. `r3`、`r4` 会错误回到“录制”，未恢复关闭前页面。

### 根因

缺陷由两层状态覆盖共同造成：

1. 托盘默认动作显式调用 `_show_workbench(WorkbenchPage.RECORDING)`，每次打开都会强制切换录制页。
2. 移除该参数后，`WorkbenchCoordinator._last_page` 仍可能是旧值。工作台通过自身 `closeEvent()` 隐藏时没有调用协调器的 `hide()`，协调器没有同步窗口当前页。

### 修复

- 托盘默认入口改为 `_show_workbench()`，不再携带强制目标页。
- `WorkbenchCoordinator.open(page=None)` 在已有存活窗口时读取 `window.current_page`，以真实窗口状态作为恢复依据。
- 保留显式目标页入口：素材库、设置和诊断等路由仍可明确切换目标页。
- 不修改工作台首次启动默认录制页的规则。

### 测试先行证据

- 新增托盘默认入口不强制重置页面的主流程测试。
- 新增“窗口自身关闭隐藏后，协调器恢复窗口当前页”的测试。
- 第二项测试在修复前稳定失败：期望 `materials`，实际为 `recording`。
- 修复后定向测试：`37 passed`。
- 最终全量测试：`460 passed, 25 deselected, 44 subtests passed`。

### 候选包复验

- 最终候选包：`E:\QRtest\QuickRec-v1.8-workbench-candidate-20260724-r5\QuickRec`
- EXE SHA256：`8735DAB9AF7A3631636E8CFCFCE77A82EA1C1C37112B059B857ABEF838C7B407`
- 隔离目录：`E:\QRtest\QuickRec-v1.8-workbench-acceptance-20260724-r5`
- 实际结果：在素材库页关闭工作台后，双击托盘重新打开仍显示素材库页；QuickRec 进程未退出，也未出现第二个工作台窗口。

### 回退

如需回退本修复，应同时回退托盘默认入口和协调器页面同步测试。不得只恢复强制录制页参数，否则会再次破坏 PRD 规定的同进程页面记忆。

## BUG-V18-003：120 FPS 自检在编码队列满时无法结束

### 状态

- 严重度：发布阻塞。
- 发现阶段：D10 新候选包 frozen 路径集成验证。
- 当前状态：已修复，自动测试、`r7` 等价 frozen 路径和打包 GUI 自检通过。
- 影响范围：120 FPS 自检取消、超时与正式录制停止响应。

### 复现与证据

1. 使用 `r6` 包内 FFmpeg/FFprobe 运行生产自检。
2. 自检超过一分钟仍未结束。
3. 进程检查确认 Python 与包内 FFmpeg 均存活，FFmpeg 正在接收 1920×1080@120 原始视频。
4. 旧实现的异步 `write_frame()` 在队列满时只会持续重试，不读取取消事件，也没有截止时间。

### 根因

生产自检虽然持有取消事件，但事件无法穿透到编码器队列写入边界。编码消费速度落后时，调用线程被困在无限 `queue.Full` 循环，自检时长、取消按钮和外层清理逻辑均无法生效。

### 修复

- `VideoEncoder.write_frame()` 增加可选取消事件和提交超时。
- 等待队列期间每次检查取消、worker 错误和截止时间。
- 生产自检使用 1 秒单帧提交上限；取消后退出送帧并进入统一清理。
- 正式 120 FPS 录制复用相同契约；用户停止时不把主动取消等待误判为编码失败。
- 30/60 FPS 同步路径行为保持不变。

### 验证

- 新增“队列满时响应取消”和“队列满时有界超时”失败测试。
- 修复前两项均因接口不支持而失败，修复后通过。
- 录制、自检和编码定向测试：`75 passed`。
- 全量测试：`513 passed, 25 deselected, 46 subtests passed`。
- 覆盖率：`86.07%`。
- Packaging：`13 passed, 525 deselected`。
- `r7` 等价 frozen 路径验证能够结束，包内工具路径正确，临时 MP4 已清理，失败结果未写入能力缓存。
- `r7` 打包 GUI 自检随后通过：平均 `119.434 FPS`、最低每秒 `112 FPS`，通过结果正确写入隔离能力缓存。

### 候选与剩余边界

- `r6` 已失效，不得继续作为验收身份。
- `r7` 已完成真实 GUI 自检，随后因进度显示优化失效。
- `r8` 只包含终态符号优化，不再作为最终候选。
- 当前候选为 `r9`，EXE SHA256：`49B017367A071FC2D9A271292DCD5AA3B18FB913E3F28E6AD85740DBCF2F7FC2`。

## BUG-V18-004：工作台状态文案不同步且未保存提示按钮未中文化

### 状态

- 严重度：一般缺陷。
- 发现阶段：D11 `r9` 候选包 GUI 验收。
- 当前状态：已修复，自动测试与 `r10` 真实桌面定向复验通过。
- 影响范围：工作台侧栏运行状态、设置页和诊断页未保存提示。

### 复现

1. 使用 `r9` 开始全屏录制并重新打开工作台。
2. 录制页正确显示“全屏录制中”，但侧栏底部仍显示“空闲 / 托盘持续运行”。
3. 在设置页制造未保存修改并切换页面。
4. 提示正文为中文，但标准按钮显示 `Save / Discard / Cancel`。

### 根因与修复

- 侧栏状态原为创建窗口时写死的静态标签，没有接入录制状态同步。
- `QMessageBox` 使用系统标准按钮文字，当前打包环境没有提供中文翻译。
- 工作台新增运行状态同步接口，并由录制状态协调器统一更新准备、录制、暂停、保存和空闲状态。
- 设置页与诊断页显式设置“保存 / 放弃 / 取消”按钮文字，不依赖系统语言包。

### 验证

- 新增工作台侧栏状态生命周期测试。
- 定向测试：`64 passed`。
- 全量测试：`514 passed, 25 deselected, 46 subtests passed`。
- Packaging：`13 passed, 526 deselected`。
- Ruff、项目配置范围 mypy（22 个源文件）、compileall 和 `git diff --check`：通过。
- `r10` 中文提示证据：`E:\QRtest\QuickRec-v1.8-acceptance-20260725-r10\evidence\D11-11-unsaved-dialog-zh.jpg`。
- `r10` 状态同步证据：`E:\QRtest\QuickRec-v1.8-acceptance-20260725-r10\evidence\D11-10-recording-state-synced.jpg`。

### 候选包

- `r9` 继续保留 120 FPS 自检和四音频阶段性证据，`r10` 保留工作台状态与设置弹窗证据；二者均不再是最终代码身份。
- `r10` 进一步发现素材库标准确认按钮显示 `Yes / No`，根因是 Qt 标准按钮没有应用级中文翻译。
- 应用级翻译器统一覆盖“是 / 否、保存 / 放弃 / 取消、确定 / 关闭 / 重试”等 Qt 标准动作。
- 新候选：`E:\QRtest\QuickRec-v1.8-candidate-20260725-r11\QuickRec\QuickRec.exe`。
- EXE SHA256：`C715897585C9EED4E164668EDA25AB11765D38F32D8A6C99979706637321BAD8`。
- `r11` 素材库确认框显示“是 / 否”，取消后测试素材和索引均保持不变。
- 证据：`E:\QRtest\QuickRec-v1.8-acceptance-20260725-r11\evidence\D11-12-remove-index-confirm-zh.jpg`。

## BUG-V18-005：120 FPS 双音频录制存在约 105 ms 音频滞后

### 状态

- 严重度：发布阻塞。
- 发现阶段：D11 最终音画同步验收。
- 当前状态：已复现并完成量化，尚未修复。
- 影响范围：1080p120 全屏录制的感知音画同步；固定延迟的具体影响模式仍需定向确认。

### 复现

1. 使用 `r11` 候选包和隔离配置，设置全屏、1080p120、系统声音＋麦克风。
2. 使用 FFmpeg 生成 25 秒同步源，在第 5、10、15、20 秒同时产生白色闪屏和
   1500Hz 提示音。
3. 通过独立 Edge 验收配置播放同步源，由 QuickRec 全局快捷键开始和停止录制。
4. 将录制视频降采样为 120 FPS 亮度序列，将 AAC 解码为 48kHz PCM，分别检测
   闪屏和音频脉冲起点。

### 实际结果

- 源文件四次音画偏移均为 0 ms。
- QuickRec 录制四次偏移为：
  - 113.333 ms
  - 88.333 ms
  - 88.333 ms
  - 130 ms
- 平均音频滞后约 105 ms，最大绝对偏移 130 ms，超过 PRD 的 40 ms 上限。
- 短测第一到第四事件偏移变化 16.667 ms。
- 10 分钟双音频文件视频时长 600.733333 秒、音频时长 600.725 秒，
  首端差 0 ms、末端差 -8.333 ms，长时漂移增量符合 20 ms 上限。

### 证据

```text
E:\QRtest\QuickRec-v1.8-final-manual-20260726\recordings\QuickRec_20260726_104708.mp4
E:\QRtest\QuickRec-v1.8-final-manual-20260726\sync-analysis\sync-source.mp4
E:\QRtest\QuickRec-v1.8-final-manual-20260726\sync-analysis\source-sync-analysis-report.json
E:\QRtest\QuickRec-v1.8-final-manual-20260726\sync-analysis\recorded-sync-analysis-report.json
```

### 根因边界与下一步

当前证据证明源时间轴和分析算法无误，也证明录制结果存在稳定量级的音频滞后；
尚不能仅凭现象判断延迟来自系统回环缓冲、音频采集启动时序、视频首帧时间戳、
混音或最终封装，因此本轮不直接修改业务代码。

下一轮应使用系统化调试：

1. 分别测量系统声音、麦克风和双音频模式的固定偏移。
2. 记录捕获首帧、首个音频样本、编码首包和混音输入的单调时钟。
3. 对比源码环境与 frozen 候选包。
4. 补充失败测试后实施最小修复。
5. 重新打包并复用相同时间戳同步源，绝对偏移不超过 40 ms 才能关闭缺陷。
