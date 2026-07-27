# QuickRec Full v1.9 GUI 手动验收清单

## 1. 当前状态

- 验收阶段：D8 GUI 手动验收。
- 当前结论：**通过**。
- 发布状态：**可进入发布收口，尚未发布**。
- 自动化事实源：[verification.md](verification.md)。
- 需求事实源：[prd.md](prd.md)。
- 进度事实源：[progress.md](progress.md)。

## 2. 锁定验收对象

| 项目 | 内容 |
| --- | --- |
| 分支 | `feature/v1.9-project-workspace` |
| 基线 HEAD | `57dbc524a31526e5f4ff64b305169c329a200c69` |
| EXE | `E:\QRtest\QuickRec-v1.9-dist-r8\QuickRec\QuickRec.exe` |
| EXE SHA256 | `CFE6BC6D4FC342039A0B410B4CF80FC9A34BAD47908F671AE9161FC63F7A9D47` |
| EXE 大小/时间 | `7,047,836` 字节 / `2026-07-27 10:21:01` |
| 隔离验收根目录 | `E:\QRtest\QuickRec-v1.9-acceptance` |
| R7 证据目录 | `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-20260727-003500` |
| R8 回收站证据目录 | `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-recycle-20260727-094500` |

开始验收前必须重新计算 EXE SHA256。若不一致，立即停止，不得混用其他构建证据。

R0-R6 均为失效候选，不得作为后续操作对象。R7 因录制页仍保留“全屏录制”主按钮角色而失效；其录制、音频、120 FPS、设置失败和诊断证据未受该视觉修复影响，继续作为继承证据。R8 是最终锁定候选。

## 3. 环境保护

1. 结束所有 QuickRec 进程。
2. 记录真实 `%APPDATA%\QuickRec` 和 `%LOCALAPPDATA%\QuickRec` 的存在状态、时间与哈希。
3. 使用独立 APPDATA、项目目录、素材索引、诊断日志和录制输出。
4. 不删除、覆盖或迁移用户真实项目、中央素材索引和视频。
5. 所有损坏、缺失、只读、外部冲突和回收站样本均由验收目录中的受控副本构造。
6. 权限、显示缩放和临时文件改动必须在验收结束后恢复。
7. 不清空 Windows 回收站。

建议目录：

```text
E:\QRtest\QuickRec-v1.9-acceptance\
  AppData\
  Projects\
  Videos\
  Diagnostics\
  Fixtures\
  Evidence\
```

## 4. 验收记录规则

每项只能标记：

- 通过
- 部分通过
- 未通过
- 待验证

每项至少记录：

- 操作时间
- 前置数据
- 实际操作
- 实际结果
- 截图路径
- 项目文件、中央索引、素材索引或 MP4 路径
- 日志关键事件
- 是否恢复环境

## 5. 当前验收结果

| 验收组 | 结论 | 主要证据 |
| --- | --- | --- |
| 候选身份、隔离与 Lite 边界 | 通过 | R8 SHA256；真实 APPDATA 前后哈希一致；Lite `git status` 干净 |
| 五页工作台与单实例 | 通过 | R7 Computer Use 实测；`D8-2-*.png` |
| 创建、打开、重命名与说明 | 通过 | `D8-3-*.png`、`D8-3-rename-and-custom-location.json` |
| 归档与恢复 | 通过 | `D8-4-project-archived.png`、`D8-4-project-recovered.png` |
| 多项目素材引用 | 通过 | `D8-5-*.png` |
| 项目内三类录制与普通录制隔离 | 通过 | R2 四个 MP4、`D8-6-project-recording-modes.json`、`D8-6-ordinary-recording-isolation.json` |
| 三段失败降级与持久重试 | 通过 | R3 失败样本、R4 项目关联恢复、R7 索引占用与启动重试 |
| 缺失与重新定位 | 通过 | `D8-8-project-relink.json`、对应截图 |
| 损坏与备份恢复 | 通过 | `D8-9-*.json`、对应截图 |
| 只读与外部冲突 | 通过 | `D8-10-external-conflict.json`、对应截图 |
| 100 项目、200 引用与长路径 | 通过 | 性能夹具；中文、空格与长路径真实项目证据 |
| 安全删除 GUI | 通过 | R7 默认不选、共享保护和取消零修改；R8 仅删除项目、独占视频回收和部分失败均通过 |
| 100% / 125% / 150% DPI | 通过 | 本机 100% 原生缩放及 R7 隔离 125%/150% Qt 缩放；项目页、删除确认、素材选择和缺失恢复截图 |
| v1.8 完整回归 | 通过 | 三类录制、四类音频、30/60/120 FPS、真实 120 FPS 自检、设置成功/失败、诊断和素材库均已补证 |

R7 录制与失败恢复证据：

- `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-20260727-003500\Diagnostics\quickrec.log`
- `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-20260727-003500\AppData\Roaming\QuickRec\recordings.json`
- `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-20260727-003500\AppData\Roaming\QuickRec\pending-recordings.json`
- `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-20260727-003500\Videos\QuickRec_20260727_003548.mp4`
- `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-20260727-003500\Videos\QuickRec_20260727_003553.mp4`
- `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-20260727-003500\Videos\QuickRec_20260727_003558.mp4`
- `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-20260727-003500\Videos\QuickRec_20260727_003642.mp4`

## 6. D8 验收项目

### D8.1 候选身份与隔离

- [x] EXE SHA256 与锁定值一致。
- [x] 包内 FFmpeg、FFprobe 存在且可执行。
- [x] 应用版本显示为 v1.9。
- [x] 隔离 APPDATA 生效。
- [x] QuickRec Lite 工作区保持干净。

### D8.2 五页工作台

1. 启动应用，确认默认驻留托盘。
2. 从托盘打开工作台。
3. 确认导航顺序为：录制、素材库、项目、设置、诊断。
4. 重复打开只激活同一工作台。
5. 关闭工作台只隐藏，不退出应用。
6. 同一进程重新打开时恢复上次页面。

- [x] 五页导航和单实例通过。
- [x] 项目页空状态、正常状态和长路径无乱码或裁切。

### D8.3 创建、打开与编辑

1. 在默认项目目录创建项目。
2. 临时选择自定义目录创建另一个项目。
3. 确认单次自定义位置不改写全局默认位置。
4. 从外部路径原地打开 `project.qrproj`。
5. 重命名并修改说明。
6. 核对 `project_id` 和物理目录均未改变。

- [x] 默认位置创建通过。
- [x] 自定义位置创建通过。
- [x] 外部项目原地打开通过。
- [x] 重命名和说明保存通过。

### D8.4 归档与恢复

1. 归档项目。
2. 确认项目进入归档视图，录制、编辑和素材调整禁用。
3. 恢复项目。
4. 确认项目回到活跃状态并重新可写。

- [x] 归档只读通过。
- [x] 恢复通过。

### D8.5 多项目素材引用

1. 准备一个有效全局素材。
2. 从素材库详情选择“加入项目”，同时加入两个项目。
3. 从其中一个项目移除。
4. 核对另一个项目引用、全局素材索引和原视频均保持不变。
5. 外部移动素材并使用全局素材库重新定位。
6. 确认两个项目都解析到全局素材的新路径。

- [x] 同一素材加入多个项目通过。
- [x] 单项目移除不影响其他项目和视频。
- [x] 全局重新定位后项目引用恢复。

### D8.6 项目内三类录制

分别从同一活跃项目执行：

1. 全屏录制。
2. 区域录制。
3. 窗口录制。

每次核对：

- MP4 成功保存并可由 FFprobe 解析。
- 中央素材索引新增一条记录。
- 当前项目新增同一稳定素材 ID 的引用。
- UI 分别显示“视频已保存、素材已入库、项目已关联”。
- 普通录制页、托盘和快捷键录制不会自动归属项目。

- [x] 全屏项目录制通过。
- [x] 区域项目录制通过。
- [x] 窗口项目录制通过。
- [x] 普通录制不自动归属通过。

### D8.7 三段失败降级

使用受控失败注入分别验证：

1. 视频保存失败：项目和素材索引不变化。
2. 视频保存成功、中央素材入库失败：视频保留，待入库记录包含目标项目 ID。
3. 中央入库成功、项目引用失败：全局素材保留，可从素材库手动加入项目。
4. 恢复条件后重试入库：目标项目仍活跃时继续幂等关联。
5. 重试前归档或移走目标项目：素材只进入全局素材库，项目不被错误修改。

- [x] 三段失败事实与反馈准确。
- [x] 重试和手动恢复路径通过。

### D8.8 缺失和重新定位

1. 移动受控项目文件，使中央索引路径失效。
2. 确认状态为“项目文件缺失”，写操作禁用。
3. 选择错误 `project_id` 的候选文件，确认拒绝且原索引不变。
4. 选择正确候选，确认路径更新并正常打开。
5. 对另一个缺失项目执行“从列表移除”，确认磁盘副本和视频不变化。

- [x] 缺失状态通过。
- [x] 错误候选拒绝通过。
- [x] 正确重新定位通过。
- [x] 仅移除中央索引通过。

### D8.9 损坏与备份恢复

1. 对受控项目制造有效 `.bak`，再损坏主文件。
2. 确认显示“从备份恢复”。
3. 取消一次，确认没有覆盖主文件。
4. 再确认恢复，检查损坏主文件的时间戳归档副本。
5. 对无有效备份的损坏项目确认不创建空项目。
6. 验证打开目录、重新定位、查看诊断和从列表移除入口。

- [x] 有备份恢复通过。
- [x] 无备份保留原文件通过。

### D8.10 只读与外部冲突

1. 把受控项目设为只读。
2. 确认重命名、素材调整、归档、删除和项目录制均禁用。
3. 恢复可写并刷新。
4. 在 QuickRec 外部修改项目文件，再尝试重命名。
5. 确认 QuickRec 停止写入，不覆盖外部内容。
6. 选择取消，确认候选名称和说明在下次编辑时恢复。
7. 再次触发并选择重新加载，确认显示外部版本。

- [x] 只读约束通过。
- [x] 外部冲突取消与重新加载通过。

### D8.11 安全删除

准备独占、共享、缺失或无法判断三类素材。

1. 打开删除确认，确认所有视频默认不勾选。
2. 确认共享和不确定素材禁用。
3. 取消，确认零修改。
4. 仅删除项目，确认视频和全局素材索引保持不变。
5. 对另一个项目勾选独占测试视频，确认视频和项目文件进入 Windows 回收站。
6. 制造单个视频回收站失败，确认项目保留且逐项结果准确。
7. 不清空回收站。

- [x] 默认不选视频通过。
- [x] 共享与不确定保护通过。
- [x] 仅删除项目通过。
- [x] 独占视频和项目文件进入回收站通过。
- [x] 部分失败保留项目通过。

R7 GUI 补证：

- 隔离目录：`E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-delete-20260727-005000`。
- 项目 `D8 Delete Main` 同时包含 1 个独占素材和 1 个被 `D8 Shared Reference` 引用的共享素材。
- 删除确认框默认未勾选任何原视频；独占素材显示“独占，可选择”，共享素材显示“共享，禁止删除”。
- 点击“取消”后对话框关闭，两个项目文件、独占视频和共享视频均继续存在，索引和项目详情未变化。
- 截图：`E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-delete-20260727-005000\Evidence\D8-17-18-delete-dialog-default-shared.png`、`D8-17-18-delete-dialog-cancelled.png`。
- 本次未确认执行“移入回收站”，因此不作为 D8.19 或 D8.20 的通过证据。

R8 真实回收站补证：

- 隔离目录：`E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-recycle-20260727-094500`。
- 仅删除项目：`D8 Shared Reference` 未勾选任何视频后执行回收；`delete-project-b\project.qrproj` 从原路径移除，`shared-material.mp4` 继续存在，中央素材索引仍保留该素材，中央项目索引仅移除目标项目。
- 独占素材回收：`exclusive-material.mp4` 与 `delete-project-a\project.qrproj` 均从原路径移除；共享视频保留，其他项目不受影响。
- 部分失败：先成功回收 `partial-success.mp4`，随后被独占占用的 `partial-locked.mp4` 返回 `[WinError 32]`；操作立即停止，项目文件和中央项目索引均保留，UI 展示“已完成 1 项”的真实结果。
- 日志：`E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-recycle-20260727-094500\Videos\QuickRecDiagnostics\quickrec.log`。
- 截图：`Evidence\D8-R8-delete-project-only-success-window.png`、`D8-R8-delete-exclusive-success.png`、`D8-R8-delete-partial-failure.png`、`D8-R8-delete-partial-state.png`。
- Windows 回收站未清空，失败样本和全部证据均保留。

### D8.12 性能、长路径和 DPI

1. 使用 100 项目受控夹具打开项目页。
2. 打开包含 200 条引用的项目。
3. 检查中文、空格和长路径。
4. 分别在 100%、125%、150% 缩放下检查项目列表、详情、恢复按钮、删除确认和素材选择器。
5. 最终恢复用户原显示缩放。

- [x] 100 项目和 200 引用无明显卡顿。
- [x] 长路径可读。
- [x] 100% DPI 通过。
- [x] 125% DPI 通过。
- [x] 150% DPI 通过。

R7 DPI 补证：

- 100% 使用本机原生 Windows 缩放，`GetDpiForSystem()` 返回 `96`；项目页和删除确认框证据为 `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-delete-20260727-005000\Evidence\D8-17-18-delete-dialog-default-shared.png` 与 `D8-17-18-delete-dialog-cancelled.png`。
- 125% 和 150% 使用同一锁定 R7 EXE、同一隔离 APPDATA 与同一受控项目数据，分别通过 `QT_SCALE_FACTOR=1.25` 和 `QT_SCALE_FACTOR=1.5` 启动，验证 Qt 页面与系统对话框在真实桌面上的缩放布局。
- 125% 截图目录：`E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-delete-20260727-005000\Evidence\dpi\`，文件为 `project-page-125.png`、`delete-dialog-125.png`、`material-selector-125.png`、`project-missing-125.png`。
- 150% 截图目录同上，文件为 `project-page-150.png`、`delete-dialog-150.png`、`material-selector-150.png`、`project-missing-150.png`。
- 三档下项目列表、详情、恢复按钮、删除确认和素材选择器均可见且可操作；超长路径通过换行、省略或横向滚动展示，没有遮挡操作按钮。
- 缺失状态由临时移动受控 `project.qrproj` 构造；两档截图完成后项目文件均已恢复，`.dpi-hold` 临时文件不存在。

### D8.13 v1.8 回归

- [x] 全屏、区域、窗口录制。
- [x] 无声、系统声音、麦克风、系统声音＋麦克风。
- [x] 30、60、120 FPS 规则。
- [x] 120 FPS 自检、快速校验和失败提示。
- [x] 素材库搜索、筛选、排序、恢复和文件操作。
- [x] 设置显式保存与保存失败行为。
- [x] 诊断复制、打开目录和导出。
- [x] 快捷键、结果条、托盘和退出行为。

R7 非破坏性回归补证：

- 四类音频使用同一锁定 R7 EXE、隔离配置和受控输出完成。无声文件 `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-20260727-003500\Videos\QuickRec_20260727_003548.mp4` 仅含 H.264 视频流；系统声音、麦克风和双音频文件位于 `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-audio-20260727-013200\Videos`。
- 系统声音文件 `QuickRec_20260727_014005.mp4` 含 `48 kHz / 2ch AAC`，受控 `997 Hz` 测试音检测幅度为 `0.353472`，平均/峰值响度为 `-22.0/-12.0 dB`。
- 麦克风文件 `QuickRec_20260727_014205.mp4` 含 `48 kHz / 2ch AAC`；本机输入信号较低但非静音，受控 `733 Hz` 响应幅度为 `0.000947`，平均/峰值响度为 `-79.9/-56.0 dB`。
- 双音频文件 `QuickRec_20260727_014448.mp4` 含 `48 kHz / 2ch AAC`，平均/峰值响度为 `-27.9/-17.2 dB`；日志同时记录系统声音与麦克风初始化、`audio.audio_sys.wav` 和 `audio.audio_mic.wav` 两条临时轨及独立时间对齐。
- 结构化证据：`E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-audio-20260727-013200\Evidence\D8-23-audio-verification.json`；SHA256 为 `686DFED6A2605FD6DD3919977C7D69DE8474E3EBC1D34475C6285DD07CBADB85`。验收后隔离配置已恢复 `audio_source=none`。
- 设置页切换“录制倒计时”后“保存更改”成功生效，随后恢复原值并再次保存；最终隔离配置 `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-delete-20260727-005000\AppData\Roaming\QuickRec\config.json` 中 `show_countdown` 为 `false`。
- 诊断页“复制诊断信息”反馈成功，剪贴板内容包含 QuickRec 与 `v1.9`；“打开日志目录”进入 `QuickRecDiagnostics`；“导出诊断文件”生成可读 UTF-8 文件 `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-delete-20260727-005000\Videos\QuickRecDiagnostics\diagnostic_20260727_010746.txt`。截图：`E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-delete-20260727-005000\Evidence\D8-23-diagnostics-export.png`。
- 素材库搜索 `exclusive` 后结果为 `1/2`；选中素材详情与索引一致，显示 `1920×1080`、`30 FPS`、`fullscreen`、`silent`；复制路径反馈成功且剪贴板为现存测试文件完整路径。截图：`D8-23-material-search.png`、`D8-23-material-detail-copy.png`。
- 真实 120 FPS 自检在 `2560×1440@300Hz` 单显示器环境通过：平均 `119.586 FPS`，最低连续一秒 `117 FPS`；缓存记录于 `d8-r7-settings-failure-20260727-014800\AppData\Roaming\QuickRec\capture-capabilities.json`，自检临时视频清理完成，用户放弃设置后有效配置保持 `30 FPS`。截图：`D8-23-120fps-selftest-before.png`、`D8-23-120fps-selftest-passed.png`。
- 设置保存失败通过真实 GUI 注入复验：页面保持打开、未保存状态保留，提示“配置未保存，原设置保持不变”，失败阶段为 `replace`；恢复后配置 SHA256 为 `5114D241AAE11AFE463BDFACB1AE1E2AB6B62BB35996677F776F0994DC81D08D`。截图：`D8-23-settings-save-failure.png`、`D8-23-settings-save-failure-restored.png`。
- 设置、配置、托盘、快捷键、主流程、120 FPS 能力服务和自检对话框定向自动回归为 `116 passed`，与上述真实 GUI 证据共同闭合回归项。
- Computer Use 已实际打开 R7 托盘菜单并确认“打开工作台”、三类录制、设置、素材库、诊断和退出入口存在；Windows 临时托盘菜单的焦点接管受到工具限制，不能将这一限制记为产品缺陷。
- R8 已复验录制页三种模式为同级次要操作，无默认选中或主按钮角色。截图：`E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-recycle-20260727-094500\Evidence\D8-R8-recording-modes-peer.png`。

## 7. 发布阻塞判断

以下任一情况均不可进入发布收口：

- 项目或视频数据丢失。
- 错误候选项目被接受。
- 损坏项目被静默当成空项目。
- 共享或不确定素材允许删除。
- 永久删除替代 Windows 回收站。
- 项目录制影响现有视频保存。
- 三段结果误报。
- 关键操作在 960×640 或三档 DPI 下不可完成。
- v1.8 录制、音频、120 FPS、设置或诊断出现回退。

当前剩余发布阻塞：**无**。

D8 发布阻塞项已全部闭合，可以进入发布收口；当前仍未提交、推送、打 tag 或创建 Release。

## 8. 验收结束恢复

- [x] 停止全部 QuickRec 和测试辅助进程。
- [x] 恢复配置、APPDATA、ACL、显示缩放和临时依赖。
- [x] 确认真实项目索引、素材索引和视频未被修改。
- [x] 保留截图、日志、JSON、MP4 和失败样本。
- [x] 确认 QuickRec Lite 工作区干净。
- [x] 不 commit、不 push、不打 tag、不创建 Release。

验收结束事实：

- 已停止全部 QuickRec 进程，未发现遗留测试锁定进程。
- 真实 `%APPDATA%\QuickRec\config.json` SHA256：`E3FC96863D862B4A2DB8080D1F3ECEC1565FF647B6A7D7D47DA6DE5038B4E8DD`。
- 真实 `%APPDATA%\QuickRec\recordings.json` SHA256：`B455034DC7F1755AA979DCF9B09A7563E129BEE4C2E246CD2D27D0279CCE167A`。
- 两个哈希与验收前锁定值一致；真实项目、素材索引和视频未被修改。
- QuickRec Lite 当前状态为 `## lite-master`，工作区干净。
