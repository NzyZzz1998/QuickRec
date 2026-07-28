# QuickRec Full v1.9.2 GUI 手动验收清单

## 1. 验收状态

- 验收阶段：D10 GUI 与真实媒体验收。
- 当前结论：**通过（RC13 的 D10 发布阻塞项已全部闭合）**。
- 发布状态：**验收通过，v1.9.2 正式发布**。
- 验收日期：2026-07-28。
- 自动化事实源：[verification.md](verification.md)。
- 需求事实源：[prd.md](prd.md)。
- 进度事实源：[progress.md](progress.md)。

本文件以 RC13 为唯一当前候选包。RC1-RC12 均已失效，仅保留缺陷发现、修复和
窄变更继承证据。RC8 已完成暂停图标、2 秒播放终点和连续 10 分钟资源曲线；
RC9-RC10 已完成外部冲突恢复、撤销/重做和轨道选择稳定性；RC11-RC13 依次
关闭录制中可编辑、停止后不解锁和解锁后状态文案不刷新的问题；RC13 已补齐
全屏/区域/窗口、四种捕获音频和 30/60/120 FPS 真包回归。四路时间线混音还
完成了实际扬声器听音，自动分析、运行日志与用户听音结论一致。

## 2. 锁定验收对象

| 项目 | 内容 |
| --- | --- |
| 项目路径 | `E:\codex\QuickRec` |
| 分支 | `test` |
| 基线 HEAD | `402c2c62294cb22a38ecad59214eb6789363ce56` |
| EXE | `E:\QRtest\QuickRec-v1.9.2-rc13-dist\QuickRec\QuickRec.exe` |
| EXE SHA256 | `28F89D701183C8018737559CFF5E159287607BB4FD25AB46313E5010BFEE5C5C` |
| EXE 大小/时间 | `7,233,597` 字节 / `2026-07-28 16:27:32` |
| 分发目录 | 317 个文件，共 `496,962,245` 字节 |
| 隔离验收根目录 | `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance` |
| 证据目录 | `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence` |

开始验收前重新计算 EXE SHA256。若不一致，立即停止，不得混用其他构建证据。

## 3. 环境保护

1. 结束所有 `QuickRec.exe`、测试播放器和辅助媒体进程。
2. 记录真实 `%APPDATA%\QuickRec`、配置、项目、中央索引和缓存的存在状态。
3. 使用隔离 `APPDATA`、`LOCALAPPDATA`、项目目录、素材目录和录制目录。
4. 不删除、覆盖或迁移用户真实项目、视频、素材索引和缓存。
5. 缺失、损坏、只读、外部冲突和保存失败均使用受控副本。
6. DPI、ACL、只读属性和依赖变更必须记录原值，结束后恢复。
7. QuickRec Lite 只检查 Git 状态，不启动、不修改。

建议目录：

```text
E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\
  appdata\
  localappdata\
  projects\
  media\
  recordings\
  evidence\
  logs\
```

## 4. 结论规则

每项只能标记：

- **通过**：真实操作和必要文件、日志或截图证据完整。
- **部分通过**：核心链路可用，但存在非阻塞缺口或证据不完整。
- **未通过**：实际结果不符合 PRD。
- **待验证**：尚未执行或受工具、设备限制。

任一数据损坏、播放主链路不可用、音画同步超限、资源残留、录制回退或候选身份
不一致均阻断发布。

## 5. D10-A 启动、窗口与录制协调

### A1 启动与双工作台

1. 使用隔离环境启动锁定 EXE。
2. 从托盘打开主工作台。
3. 创建或打开受控项目，点击“进入剪辑”。
4. 确认剪辑工作台默认最大化。
5. 再次点击“进入剪辑”，确认只激活已有剪辑窗口。
6. 点击“返回项目”和“素材工作台”，确认主工作台被激活且项目上下文保持。
7. 确认主工作台与剪辑工作台可以同时存在。
8. 关闭剪辑工作台，确认应用和托盘仍运行。

预期：

- 剪辑工作台全局单实例；
- 默认最大化，恢复窗口时最小尺寸不低于 960×640；
- 两个工作台互不替代、互相激活；
- 关闭剪辑窗口不退出 QuickRec。

证据：窗口截图、进程列表、QuickRec 日志。

### A2 剪辑工作台发起录制

1. 在剪辑工作台点击“开始录制”。
2. 分别确认全屏、区域、窗口三个入口仍使用既有流程。
3. 录制中重新打开剪辑工作台。
4. 确认剪辑工作台只显示只读录制状态，控制仍由浮动工具栏负责。
5. 停止录制，确认 MP4 正常保存并进入素材库。

预期：剪辑工作台不复制录制核心，也不接管浮动工具栏。

## 6. D10-B 布局与 DPI

分别在 100%、125%、150% DPI 下重启同一个 RC13，检查：

1. 默认约 68:32 的预览/时间线分栏。
2. 左侧素材区、预览画面、时间线和轨道头无重叠、裁切或不可点击控件。
3. 分隔条可鼠标拖动。
4. 分隔条获得焦点后可用方向键微调。
5. `Home`、`End` 到达安全边界。
6. 双击分隔条恢复默认比例。
7. “放大预览”和“专注时间线”互斥，恢复后回到上次安全分栏。
8. 960×640 恢复窗口仍可完成核心操作。
9. 长中文素材名、长轨道名和中文空格路径不会挤出按钮。

每档 DPI 至少保留一张完整剪辑工作台截图；修改显示缩放后必须恢复用户原值。

## 7. D10-C 多轨编排

### C1 素材加入与多实例

1. 准备至少 3 个 QuickRec H.264 MP4，其中一个带音频。
2. 分别用“加入时间线”和拖入轨道两种方式加入。
3. 将同一素材再次加入，确认生成新的独立 `clip_id`。
4. 关闭并重新打开项目，确认轨道、片段和位置恢复。

预期：按钮与拖放结果一致；同一素材可有多个片段实例；保存后可恢复。

### C2 拖动、吸附与冲突

1. 水平拖动片段，观察片段边缘、播放头和整秒吸附。
2. 按住 `Alt` 拖动，确认临时关闭吸附。
3. 将片段拖到同类型其他轨道。
4. 尝试制造同轨重叠。
5. 尝试把视频片段拖到音频轨。
6. 撤销和重做上述有效操作。

预期：有效拖动仅在松开后保存一次；同轨重叠和跨类型落点被拒绝且不改数据。

### C3 轨道管理与容量

1. 新增、重命名、排序和删除空轨道。
2. 删除含片段轨道，核对影响数量并分别测试取消和确认。
3. 构造 8 条视频轨和 8 条音频轨。
4. 构造 100 个片段和约 30 分钟总时长。
5. 验证缩放、滚动、选择、拖动和适配完整时间线。

预期：不超过 8+8 上限；大时间线无明显空白页、错位或不可操作状态。

### C4 自动保存与 50 步撤销

1. 连续执行多个离散编辑操作。
2. 确认每次成功操作后显示已保存。
3. 执行 50 步撤销和重做。
4. 新操作后确认重做栈清空。
5. 安全制造保存失败，确认 UI、内存、项目文件、索引和命令栈回滚。

预期：保存失败不显示成功，不留下部分提交。

## 8. D10-D 播放闭环

### D1 基础播放

1. 使用 RC4 打开包含连续片段的时间线。
2. 执行播放、暂停、暂停后继续和随机跳转。
3. 播放到末尾，再次点击播放。
4. 在空白区跳转并播放。

预期：

- 首次播放不超过 1.5 秒；
- 随机跳转不超过 500 毫秒；
- 暂停不超过 200 毫秒；
- 末尾再次播放从 0 开始；
- 空白视频区显示黑屏，存在音频时音频继续。

### D2 视频覆盖与错误

1. 构造两个重叠视频轨。
2. 确认最高活动视频轨全画面覆盖下层。
3. 让最高轨素材缺失或损坏。
4. 确认显示错误占位，不静默露出下层。
5. 制造整体后端失败，确认显示“重试播放”和“查看诊断”。
6. 恢复条件后点击重试，确认可继续播放。

### D3 音频与同步

1. 验证无声素材。
2. 验证单路有声素材。
3. 验证四路活动音频固定混合。
4. 验证音频设备不可用时“无声继续”和“取消”两条路径。
5. 播放 30 秒样本并测量音画绝对偏差。
6. 播放 10 分钟样本并测量漂移增量。

通过标准：

- 音画绝对偏差不超过 40 毫秒；
- 10 分钟漂移增量不超过 20 毫秒；
- 单个音频源失败只静音该源；
- 无残留声音或削波失控。

## 9. D10-E 缺失、恢复与只读

### E1 缺失与重新定位

1. 外部移动一个被多个片段引用的素材。
2. 确认片段、轨道、`clip_id` 和时间位置保留。
3. 进入重新定位并选择正确文件。
4. 确认全部同 `material_id` 片段恢复。

### E2 项目素材移除

1. 对仍被时间线引用的项目素材执行移除。
2. 首次确认默认阻止。
3. 再次选择连同相关片段移除。
4. 确认真实视频和中央素材索引仍存在。

### E3 只读、损坏和冲突

1. 打开归档项目，确认可查看和播放但不能编辑。
2. 打开文件只读项目，确认同样只读。
3. 构造损坏时间线且备份有效，执行“从备份恢复”。
4. 构造损坏时间线且无备份，确认先保留损坏文件，再执行“重建空时间线”。
5. 构造未知新版本，确认只读且不覆盖。
6. 在会话外修改项目文件，再执行编辑，确认不会静默覆盖。

## 10. D10-F 既有能力回归

1. 项目创建、打开、重命名、归档、恢复和删除。
2. 静态首帧预览、单项刷新、批量重建和素材库往返。
3. 全屏、区域和窗口录制。
4. 无声、系统声音、麦克风、系统声音加麦克风。
5. 30、60、120 FPS；区域和窗口在全局 120 设置下仍按 60 FPS 处理。
6. 设置显式保存、未保存提示和重启持久化。
7. 诊断复制、打开目录和导出。
8. 托盘菜单、快捷键、开机启动设置和退出。

未修改的既有链路可以继承正式版本证据，但与剪辑工作台协调相关的入口必须用
RC4 重新验证。

## 11. D10-G 退出与恢复环境

1. 播放中切换项目，确认旧媒体资源在 2 秒内释放。
2. 播放中关闭剪辑工作台。
3. 再次打开并确认没有残留播放状态。
4. 从托盘退出 QuickRec。
5. 确认无 `QuickRec.exe`、残留声音、媒体线程或辅助媒体进程。
6. 对比受控项目、中央索引和配置的预期变化。
7. 恢复 DPI、ACL、只读属性、环境变量和原配置。
8. 再次确认真实用户数据未变化。
9. 确认 `E:\codex\QuickRec-Lite` 工作区干净。

## 12. 已执行验收与证据

### 12.1 候选包、媒体工具与基础启动

- RC5 EXE、FFmpeg、FFprobe、PyAV 核心文件均已计算 SHA256。
- 分发目录共 317 个文件、496,958,046 字节。
- 包内 FFprobe 实际解析中文空格路径的 H.264/AAC 样本：
  `E:\QRtest\QuickRec-v1.8-final-manual-20260726\recordings\QuickRec_20260726_101237.mp4`。
- 包含 H.264 1920×1080@120 FPS 与 AAC 48 kHz 双声道。

### 12.2 工作台、播放与错误降级

- 从托盘打开主工作台，进入受控项目并打开剪辑工作台。
- 剪辑工作台默认最大化；主工作台与剪辑工作台同时存在。
- “素材工作台”可激活主工作台；关闭剪辑工作台不退出应用。
- RC3 已实际完成播放、暂停和时间线跳转；RC4 已重新验证短时播放、播放结束、
  素材缺失占位、文件恢复后重新播放及退出释放。
- 缺失素材截图：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\D10-RC4-missing-media-degraded.png`。
- 恢复播放截图：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\D10-RC4-recovered-playback.png`。
- 同一连续降级过程只记录 2 条不同状态转换告警，不再按 16 毫秒刷新周期洪泛：
  `missing_media/video=missing/audio=ready` 与
  `audio_decode_failed/video=missing/audio=error`。
- 关闭剪辑工作台前后，线程数由 147 降至 57，句柄数由 1196 降至 898；
  日志记录 `timeline playback released ... result=ok`，托盘退出后无残留进程。

### 12.3 自动保存、失败恢复与外部冲突

- RC3 候选包已实际制造项目文件独占，确认保存失败后保留精确候选，并提供
  “重试保存 / 查看诊断 / 放弃本次修改”。
- 解除文件占用后“重试保存”成功；随后撤销恢复原 2 轨 4 片段。
- 外部修改项目文件后，应用拒绝静默覆盖，并提供
  “重新加载 / 保存恢复副本 / 取消”。
- “保存恢复副本”生成独立 `.qrproj`，不写入项目索引，也不覆盖原项目。
- 以上事务代码未被 RC4 的播放日志去重修改触及，自动化回归与候选差异核对均通过。

### 12.4 DPI 与窗口边界

- 100% 原生缩放下验证默认最大化和 960×640 恢复窗口。
- 125% 与 150% 按历史正式验收口径，使用同一 RC4、同一隔离数据和
  `QT_SCALE_FACTOR=1.25/1.5` 启动。
- 关键按钮、项目素材区、预览区、播放栏和时间线工具栏均位于窗口可视范围内。
- 截图：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\D10-RC4-editor-dpi125.png`；
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\D10-RC4-editor-dpi150.png`。

### 12.5 RC4 录制回归

- 通过全局快捷键启动、浮动工具栏“停止”完成真实全屏无声录制。
- 输出：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\recordings\QuickRec_20260728_075722.mp4`。
- SHA256：
  `90394FE7A6B9B207813B6A22ABEE87038E0E5726EB8FD8B66D6AA4B7C95F76D2`。
- FFprobe：H.264、1920×1080、30 FPS、4.400 秒、无音频流。
- 中央索引写入 1 条 `available` 记录，路径、分辨率、FPS、音频模式与文件一致。
- 首次自动化启动未重定向控制台，导致日志输出管道阻塞；Py-Spy 证明主线程、
  录制线程与 DXCamera 线程均阻塞于 `logging.StreamHandler.write()`。改为重定向
  stdout/stderr 后同一 RC4 正常保存，因此该样本归类为验收工具问题，不是产品缺陷。
  证据：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\RC4-harness-stdout-block-pyspy.txt`。

### 12.6 环境恢复

- RC4 验收进程已全部退出，无残留 QuickRec、FFmpeg 或 FFprobe 进程。
- 真实用户中央索引保持：
  `C:\Users\win\AppData\Roaming\QuickRec\recordings.json`，
  SHA256 `B455034DC7F1755AA979DCF9B09A7563E129BEE4C2E246CD2D27D0279CCE167A`。
- QuickRec Lite 保持 `lite-master` 干净，未修改。
- 未修改系统 DPI、ACL、真实配置、真实项目或用户视频。

### 12.7 自动压力与长时播放补证

以下结果用于缩小 D10 的人工范围，但不替代打包产物 GUI 与实际听音：

- 受控压力项目：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\stress-8x8-100`。
- 项目包含 8 条视频轨、8 条音频轨、100 个片段，总时长精确 30 分钟。
- 时间线会话加载 2.759 毫秒，首次离屏界面渲染 30.856 毫秒。
- 55 次连续轨道重命名耗时 1,134.198 毫秒；撤销 50 次耗时
  916.007 毫秒；重做 50 次耗时 990.211 毫秒。
- 撤销栈严格限制为 50 步；执行后仍保持 16 轨、100 片段和 30 分钟时长。
- 结构化报告：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\stress-8x8-100\evidence\D10-stress-8x8-100-report.json`。
- 源码离屏截图：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\stress-8x8-100\evidence\D10-stress-8x8-100-source.png`。
  该截图只证明 Qt 画布能生成，不作为 RC4 打包 GUI 通过证据。
- 当前 PyAV 技术门禁再次通过：启动 4.604 毫秒、最慢随机跳转
  33.201 毫秒、暂停 2.011 毫秒、10 分钟漂移增量 0 毫秒。
- 四路音频固定混合输出为 48 kHz 双声道有限值；真实 PortAudio 设备成功写入
  12,000 帧；释放后线程和子进程增量均为 0。
- 音频设备不可用的“继续无声 / 取消”状态与免重复询问行为 3 项定向测试通过。
- 长时与音频报告：
  `E:\QRtest\QuickRec-v1.9.2-rc4-acceptance\evidence\D10-RC4-pyav-longrun-report.json`。

### 12.8 RC5 长时间线适配定向复验

- RC4 在 30 分钟压力项目中点击“适配完整时间线”后仍停留在 25%，仅显示
  前约 1 分 30 秒，判定为发布阻塞缺陷。
- 修复后重新构建 RC5，并使用 8 条视频轨、8 条音频轨、100 个片段、
  30 分钟总时长的同等受控项目实际打开打包程序。
- 点击“适配完整时间线”后显示 0.6%，时间标尺和片段编排覆盖至 30:00 末端。
- 源码大视口定向复验显示 1.3%，关闭并重新打开剪辑工作台后仍保持 1.3%。
- RC5 打包产物截图：
  `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-fit-30min-8x8-100.jpg`。
- RC5 验收结束后无残留 QuickRec、FFmpeg 或 FFprobe 进程；真实用户中央索引
  哈希保持不变，QuickRec Lite 工作区干净。

### 12.9 RC5 布局控制与定向交互补证

- 在 RC5 打包 GUI 中实际打开 8 条视频轨、8 条音频轨和 100 个片段的压力项目。
- 分隔条鼠标拖动通过：拖动后预览区与时间线区按指针位置重新分配空间。
- “专注时间线”通过：预览区隐藏，16 条轨道均可见，完整时间范围保持至 30:00。
- “放大预览”通过：时间线区隐藏，预览区占满可用工作区；两种模式互斥。
- 打包 GUI 截图：
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-splitter-mouse.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-focus-timeline2.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-enlarge-preview.png`
- 分隔条键盘微调与双击恢复已在 RC5 打包 GUI 中通过窗口句柄定向复验：
  方向键将边界向下移动 12 像素，完整双击序列将边界恢复到原默认位置。
- 后台窗口证据：
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-splitter-keyboard-printwindow.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-splitter-doubleclick2-printwindow.png`
- 片段拖动与关联组保存通过：在 RC5 打包 GUI 中将首个视频片段从 0 秒拖到
  4.9 秒，关联音频片段同步移动，界面显示“片段位置已更新并自动保存”。
- 实际点击“撤销”后，关联视频和音频片段均恢复到 0 秒。与操作前备份进行结构化
  对比后，时间线语义完全一致，仅项目 `updated_at` 更新时间发生变化。
- 片段拖动证据：
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-packaged-clip-drag-saved.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-packaged-clip-drag-undo.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-packaged-drag-report.json`
- 按钮加入时间线通过：在 RC5 打包 GUI 中连续两次点击项目素材右侧“加入时间线”，
  每次均新增一组关联视频/音频片段，片段数由 100 依次增加到 102、104；两次真实
  撤销后恢复为 100，未产生重复或孤立片段。
- 轨道顺序调整通过：将首条视频轨下移后，轨道顺序和索引同步变化；真实撤销后
  恢复原顺序，项目语义仅 `updated_at` 发生变化。
- 素材加入与轨道顺序证据：
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-button-add-material.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-button-add-undo.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-track-move-down.png`
- 原生拖入通过：从项目素材列表将中文空格路径素材直接拖入视频轨，落点为
  2.33 秒，自动生成同一关联组的视频与音频片段并保存；撤销后恢复为 2 轨
  0 片段，项目语义与操作前一致，仅 `updated_at` 变化。
- 轨道完整管理抽样通过：新增视频轨和音频轨，将新音频轨重命名为“旁白轨”、
  上移、删除，再通过多步撤销恢复到原始 2 轨；保存文件中的轨道类型、顺序和
  名称均与界面一致。
- 原生拖入与轨道管理证据：
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-native-material-drag.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-track-add.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-track-add-rename-move-undo.png`
- 未知时间线版本保护通过：“进入剪辑”禁用，项目页明确显示“时间线只读，
  项目素材仍可用”，受控项目文件哈希保持不变。
- 归档项目只读通过：剪辑工作台允许查看归档项目，但撤销、重做、增删轨道、
  重命名轨道、删除片段和加入时间线均禁用；打开前后项目 SHA256 均为
  `B67F3636CACF5C19F309EA38BFA958F567C0F1A226041A848535D8D4A8C5CC2D`。
- 损坏时间线有备份恢复通过：恢复前预览明确不可播放，确认后使用 `.bak` 恢复；
  原损坏项目保留为 `project.corrupt-*.qrproj`，恢复后的轨道、片段和预览可用。
- 损坏时间线无备份重建通过：取消确认时项目 SHA256 保持
  `B5F0604DD3C36EB05C27E8A51A4C27BA590D8B10F0DD1370FF898495A6BD6312`；
  确认后保留 `project.timeline-corrupt-*.qrproj`，创建空时间线且项目素材仍可用。
- 恢复与只读证据：
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-unknown-version-readonly.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-corrupt-with-backup-initial.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-corrupt-with-backup-confirm.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-corrupt-with-backup-restored.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-corrupt-no-backup-initial.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-corrupt-no-backup-confirm.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-corrupt-no-backup-rebuilt-empty.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-archived-project-readonly.png`
- 中央素材重新定位通过：移动受控 MP4 后，素材库正确显示文件缺失并启用
  “重新定位”；取消选择时索引 SHA256 不变，随后选择中文空格新路径成功，
  状态恢复为可用，时长、分辨率和 FPS 保持不变。
- 项目素材移除确认通过：确认框明确说明只移除项目引用并保留原视频和全局素材
  记录；取消时项目哈希不变，确认后项目素材数变为 0、中央索引仍为 1 条，
  原 MP4 继续存在。
- 重新定位与项目移除证据：
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\recordings-before-relink.json`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-project-material-remove-confirm.png`
  - `E:\QRtest\QuickRec-v1.9.2-rc5-acceptance\evidence\D10-RC5-project-material-removed-source-preserved.png`
- 早先被 Windows 前台焦点截获的无效截图已移入 `evidence\tool-interference\`，
  不作为产品证据。
- 多轨交互定向测试 9 项通过，覆盖完整 Qt 鼠标拖动事件、普通吸附、`Alt` 临时
  关闭吸附、轨道类型兼容、同轨重叠拒绝、跨轨移动、无效移动原子回滚、
  16 轨/100 片段渲染以及分隔条键盘和双击复位。
- 恢复与只读定向测试 14 项通过，覆盖素材移除事务、保存失败回滚、归档拒写、
  损坏时间线有/无备份恢复、未知版本只读、缺失素材与重新定位路径。
- 剪辑工作台录制协调与资源释放定向测试 11 项通过，覆盖三种录制入口复用、
  录制时隐藏与完成后恢复、诊断跳转、播放资源释放和工作台录制状态同步。
- 既有能力分域回归 400 项及 18 个 subtests 通过，覆盖项目生命周期、素材库与
  首帧、录制协调、音频配置、30/60/120 FPS、设置、诊断、托盘、快捷键和工作台。
- 当前标准全量测试为 854 passed、27 deselected、56 subtests passed；总体覆盖率
  83.26%，时间线核心 85.60%，播放与页面协调 80.78%；Packaging 15 项通过。
- 上述定向测试用于缩小人工范围；片段拖动、按钮/原生拖入、轨道管理、重新定位、
  素材移除确认、归档只读、未知版本保护和有/无备份恢复已经获得打包 GUI 证据。
  RC13 已补齐真实设备录制、录制入口操作和四路时间线混音的实际听音。

## 13. 验收结果表

| 验收组 | 结论 | 证据路径 | 备注 |
| --- | --- | --- | --- |
| A 启动、双工作台与录制协调 | 通过 | RC3/RC4 基础窗口证据；RC13 录制中只读、停止后解锁、录制文件、日志与项目哈希 | 剪辑工作台发起录制、录制中禁写、保存后恢复和索引写入均通过 |
| B 100%/125%/150% DPI | 通过 | `evidence\D10-RC4-editor-dpi125.png`、`dpi150.png`、RC3 100%/960×640 截图 | 125%/150% 使用隔离 Qt 缩放，沿用历史正式验收口径 |
| C 多轨编排与保存 | 通过 | RC3 保存失败与恢复副本；RC5 编排；RC10 七步撤销/重做、分支清空及轨道选择稳定性；RC13 同轨重叠与跨类型拒绝 | 两次非法拖放均显示明确反馈，项目文件 SHA256 前后不变 |
| D 播放、覆盖、音频与同步 | 通过 | RC8 暂停图标、2 秒终点、10 分钟资源曲线；RC13 四路混合分析、播放日志与用户实际听音 | 资源释放、时间线终点、四路固定混合和实际输出均通过 |
| E 缺失、恢复与只读 | 通过 | RC4 缺失/恢复；RC3 外部冲突；RC5 重新定位、素材移除、归档/未知版本及有/无备份恢复；14 项定向测试 | 数据、取消、确认、只读、恢复和原文件保护均有打包 GUI 或文件证据 |
| F v1.9.1 回归 | 通过 | RC13 全屏/区域/窗口、无声/系统声/麦克风/双音频、30/60/120 FPS 真包录制与 FFprobe/索引/日志 | 全局 120 设置下区域和窗口均按 60 FPS 输出，保存配置仍为 120 |
| G 退出与环境恢复 | 通过 | RC4/RC13 进程、真实索引哈希与 Lite Git 状态 | 无残留 QuickRec 进程，真实索引 SHA256 未变 |

## 14. 发布判断

D10 当前为**通过**。RC8 已关闭暂停图标、播放终点和长时资源释放问题；
RC9-RC10 已关闭外部冲突恢复、撤销/重做分支和轨道选择稳定性问题；RC13 已
关闭录制中编辑保护、停止后恢复以及录制模式/FPS/捕获音频回归，并完成四路
时间线混音的最终实际听音。v1.9.2 已具备进入发布收口的条件，但未经授权不
执行提交、推送、打 tag 或创建 Release。

## 15. RC8 定向复验准备

### 15.1 验收对象

- 分支：`test`。
- 源码 HEAD：`402c2c62294cb22a38ecad59214eb6789363ce56`，其后为未提交
  v1.9.2 实现与验收修复。
- EXE：
  `E:\QRtest\QuickRec-v1.9.2-rc8-dist\QuickRec\QuickRec.exe`。
- EXE SHA256：
  `878C711A7326D42958679458457156FC178E814B8F53A12DB9D54FC71F80410A`。
- 隔离环境：
  `E:\QRtest\QuickRec-v1.9.2-rc8-acceptance`。
- 真实用户中央索引复核 SHA256：
  `B455034DC7F1755AA979DCF9B09A7563E129BEE4C2E246CD2D27D0279CCE167A`。
- QuickRec Lite：`lite-master` 工作区干净。

### 15.2 自动完成项

- 播放中按钮状态切换为“暂停”与双竖线图标；暂停、结束和未播放状态恢复
  “播放”与三角图标。
- 2 秒单素材时间线在 `00:02.000` 自动结束，播放计时器停止。
- 30 分钟压力项目的总时长来自 100 个片段实例及其时间位置，不是单个 2 秒
  素材被播放器错误延长。
- RC8 包内 FFprobe 可解析中文空格路径 H.264/AAC 样本。
- 已生成暂停按钮离屏视觉证据：
  `E:\QRtest\QuickRec-v1.9.2-rc8-acceptance\evidence\D10-RC8-pause-button.png`。

### 15.3 待打包 GUI 定向复验

1. 打开“RC8 单素材 2 秒终点验证”项目并进入剪辑工作台。
2. 点击播放，确认按钮显示双竖线暂停图标。
3. 播放到 `00:02.000`，确认自动进入“播放结束”，没有继续空转。
4. 打开 8+8 轨、100 片段、30 分钟压力项目，确认中间空白区后仍能播放后续
   片段，时间线终点仍为最后片段结束点。
5. 连续播放压力项目至少 10 分钟，记录 QuickRec 线程、句柄、内存和媒体子进程
   曲线，确认非活动解码器不会持续累积。

RC8 的暂停图标、2 秒终点和连续 10 分钟资源曲线已在后续执行中完成；RC8
之后的候选演进和当前结论见下一节。

## 16. RC8-RC13 候选演进与录制协调定向复验

### 16.1 RC8-RC10 已闭合项

- RC8 打包 GUI 验证暂停按钮使用双竖线图标，2 秒单素材在 `00:02.000`
  自动结束，不继续空转。
- RC8 连续 10 分钟播放期间，常态线程约 56-61、句柄约 894-919、
  Working Set 约 176-181 MB；两次短暂峰值随后回落，没有持续累积。
- RC9 验证外部冲突被拒绝，重新加载后可继续编辑。
- RC10 验证七步撤销/重做、新命令清空重做分支，以及重复轨道换序后的选择
  稳定性。自动规模门禁继续覆盖 55 次命令与 50 次撤销/重做。
- RC10 首次发现录制期间仍可执行时间线变更，候选失效；重复进程截图属于
  验收工具污染，已单独标记 `INVALID-`，不得作为产品缺陷证据。

### 16.2 RC11-RC13 修复链路

| 候选 | 结果 | 结论 |
| --- | --- | --- |
| RC11 | 录制期间全部结构编辑控件禁用，但停止保存后剪辑锁未释放 | 失效 |
| RC12 | 日志出现 `active=False`，但标题仍显示只读，状态文案未刷新 | 失效 |
| RC13 | 录制期间只读，停止保存后恢复“已自动保存”并重新启用编辑操作 | 当前候选 |

RC13 定向复验事实：

- 录制中标题显示“项目文件只读 · 编辑操作已禁用”和“录制中”，开始录制、
  新增轨道、重命名、移动、删除轨道/片段均禁用。
- 停止并完成保存后，录制横幅消失，标题恢复“已自动保存”，开始录制重新
  可用；选中“视频 2”后，重命名、下移和删除轨道重新可用。
- 项目文件复验前后 SHA256 均为
  `82A6B24B7E60F59F150DBC1B506664FE3BB35A163917713B4374965C0F5EF1FE`，
  证明录制锁定期间没有写入项目。
- 录制文件：
  `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\recordings\QuickRec_20260728_163414.mp4`。
- 包内 FFprobe 解析通过：H.264、1920×1080、30 FPS、160.500 秒、
  4815 帧、5,068,555 字节。
- 录制文件 SHA256：
  `3EB6A27CD8966108EBE1063350206C04ECE2164FFF743DDD1DA15481916FFA7A`。
- 日志在保存完成后记录两次
  `timeline runtime write lock changed ... active=False`。
- 截图：
  - `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-recording-editor-read-only.jpg`
  - `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-recording-stop-editor-unlocked.jpg`
- 真实用户中央索引 SHA256 复验仍为
  `B455034DC7F1755AA979DCF9B09A7563E129BEE4C2E246CD2D27D0279CCE167A`；
  验收结束后无残留 QuickRec 进程。

### 16.3 RC13 录制模式、FPS 与捕获音频回归

所有项目均使用锁定 RC13、隔离 `APPDATA` 和包内 FFmpeg/FFprobe 执行。

| 项目 | 文件与结果 | 结论 |
| --- | --- | --- |
| 30 FPS 区域录制 | `QuickRec_20260728_165909.mp4`；H.264 644×1080、30 FPS、20.967 秒；索引 `mode=region`；SHA256 `D92BC24263C953F9303BE551D44B4411AA7EAD12D554072C095EF37E386E4108` | 通过 |
| 30 FPS 窗口录制 | `QuickRec_20260728_170059.mp4`；H.264 320×532、30 FPS、32.700 秒；索引 `mode=window`；计算器内容从 `7` 变为 `78`；SHA256 `4F3D860E02AF085E3C4A371128145EAEB29645DA400FF747EFF108A110AD892F` | 通过 |
| 60 FPS 全屏录制 | `QuickRec_20260728_170348.mp4`；H.264 1920×1080、60 FPS、12.983 秒；SHA256 `742DB031253E54DD48908AD96B3DB898644DDDFEDFECE08AFF46491C486F56DF` | 通过 |
| 120 FPS 能力检测 | 平均 119.424 FPS，最低每秒 116 FPS，环境为 2560×1440@300Hz；缓存写入隔离目录 | 通过 |
| 120 FPS 全屏录制 | `QuickRec_20260728_170601.mp4`；H.264 1920×1080、120 FPS、33.450 秒；运行平均 119.908 FPS、最低 116 FPS、丢帧 3；SHA256 `E02420073FADFC4CA36975125206F2FA6C7A1E3C19A5905325CF0AEB35C767C7` | 通过 |
| 无声音频 | RC13 全屏、区域和窗口样本均无音频流，索引 `audio_source=none` | 通过 |
| 系统声音 | `QuickRec_20260728_170924.mp4`；AAC 48 kHz 双声道；均值 -9.3 dB、峰值 -3.0 dB；索引 `audio_source=system` | 通过 |
| 麦克风 | `QuickRec_20260728_171036.mp4`；AAC 48 kHz 双声道；日志确认 48 kHz 单声道采集后混入，输出存在非零信号；索引 `audio_source=microphone` | 链路通过，电平较低 |
| 系统声＋麦克风 | `QuickRec_20260728_171231.mp4`；日志确认系统声 2ch 与麦克风 1ch 两路临时源及独立对齐，输出 AAC 48 kHz 双声道；均值 -15.7 dB、峰值 -9.3 dB；索引 `audio_source=both` | 链路通过 |
| 120 设置下区域限制 | `QuickRec_20260728_171550.mp4`；全局配置保持 120，实际与索引均为 60 FPS，`mode=region` | 通过 |
| 120 设置下窗口限制 | `QuickRec_20260728_171735.mp4`；全局配置保持 120，实际与索引均为 60 FPS，`mode=window` | 通过 |

抽帧证据：

- `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-region-frame.jpg`
- `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-window-frame.jpg`
- `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-window-frame-after-input.jpg`

验收结束后隔离配置恢复为 30 FPS/无声，QuickRec 与测试播放器进程均为 0；
真实用户中央索引 SHA256 仍为
`B455034DC7F1755AA979DCF9B09A7563E129BEE4C2E246CD2D27D0279CCE167A`，
QuickRec Lite 工作区保持干净。

### 16.4 RC13 非法拖放负向复验

在专注时间线模式、0.6% 完整适配视图下，以同一压力项目执行两次真实拖放：

| 项目 | 实际结果 | 结论 |
| --- | --- | --- |
| 同轨重叠 | 将 `video-clip-9` 拖到同轨已有片段位置，标题提示“目标位置与同轨道现有片段重叠” | 通过 |
| 跨类型轨道 | 将视频片段拖到音频轨，标题提示“视频片段和音频片段只能在同类轨道之间移动” | 通过 |

两次操作前后项目文件 SHA256 均为
`82A6B24B7E60F59F150DBC1B506664FE3BB35A163917713B4374965C0F5EF1FE`，
撤销栈未新增可用命令，证明拒绝操作未写入项目。

证据：

- `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-same-track-overlap-rejection.png`
  （SHA256 `C18015F56BE75C5A0C04ECEE4CC0BCCA0A4B9B39247EE9AB31CC53A317DC2D8C`）
- `E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-cross-type-rejection.png`
  （SHA256 `2BD578B292027200A1B3009D4DF71C82A7B9E3F1215D93D6862A2E74B0DD11AF`）

### 16.5 RC13 四路音频实际听音

受控听音项目：

```text
项目：RC13 四路音频实际听音
项目文件：E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\projects\v192-rc13-four-track-listening\project.qrproj
素材目录：E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\four-track-listening
```

项目包含一条视频轨和四条同时活动的音频轨，分别播放 C4、E4、G4、C5，
时长均为 12 秒。四个素材均已由 RC13 包内 FFprobe 验证为 H.264
640×360、30 FPS、AAC 48 kHz 单声道；生产项目/时间线解析结果为
5 轨、5 片段、状态 `ready`。

验证过程与结论：

1. 生产混音块不是静音：RMS 约为 `0.0062`，峰值约为 `0.01647`。
2. 频谱包含 `261.63 Hz`、`329.63 Hz`、`392 Hz` 和 `523.25 Hz` 四个目标音高。
3. 初次未听到声音时，Windows 默认输出设备为显示器
   `27M2N5500Y (NVIDIA High Definition Audio)`；这不是 QuickRec 解码或混音失败。
4. 将实际输出切换为 `HECATE G1500 BAR` 并重启 RC13 后，用户实际播放并确认
   **有声音**。
5. 日志在 `2026-07-28 18:12:28` 记录
   `audio_sources=4`、`muted=False` 和播放开始；在 `18:12:40` 正常到达
   `12,000,000 µs` 终点，在 `18:12:50` 记录资源释放成功。

日志证据：

```text
E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\recordings\QuickRecDiagnostics\quickrec.log
```

本项结论为**通过**。四路固定混合、实际扬声器输出、播放终点和资源释放证据
完整。

### 16.6 RC13 重复启动进程发现

在已有 RC13 进程 PID `44172` 的情况下再次启动同一 EXE，Windows 创建了第二个
进程 PID `9380`，并出现两个托盘图标。两个进程均来自同一锁定候选路径；停止
PID `9380` 后原进程继续正常运行。

证据：

```text
E:\QRtest\QuickRec-v1.9.2-rc13-acceptance\evidence\D10-RC13-duplicate-app-processes.png
SHA256: 83D9EB56535850889D6DF2E8D35EF84E57AAED44606C76F05FDF302F673675C9
```

该现象登记为 `BUG-009`。它是应用进程级单实例缺口，与 RC10 的验收工具污染
截图不是同一事件。v1.9.2 PRD 约束的是同一进程内主工作台和剪辑工作台单实例，
因此本项作为非阻塞已知限制，不改变本轮 D10 通过结论。
