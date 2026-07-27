# QuickRec Full v1.9.1 GUI 手动验收记录

## 1. 验收结论

- 验收阶段：D8 GUI 验收。
- 当前结论：**通过**。
- 发布状态：**正式发布**。
- 验收日期：2026-07-27。
- 自动化事实源：[verification.md](verification.md)。
- 需求事实源：[prd.md](prd.md)。
- 进度事实源：[progress.md](progress.md)。

本记录汇总 rc3 至 rc6 的分层证据。后续候选包只继承未受代码变化影响的证据；
发生相关实现变化时，对应证据立即失效并重新验证。

## 2. 最终候选对象

| 项目 | 内容 |
| --- | --- |
| 项目路径 | `E:\codex\QuickRec` |
| 分支 | `test` |
| 基线 HEAD | `197943c6cef924ccdc2649b2382689ed08d18b3a` |
| EXE | `E:\QRtest\QuickRec-v1.9.1-rc6-dist\QuickRec\QuickRec.exe` |
| EXE SHA256 | `33B7DB1EB96007D75BF933D5600EE813A03ED42390CAE3A93EAD0960B9C6C7D9` |
| EXE 大小/时间 | `7,099,051` 字节 / `2026-07-27 19:31:43` |
| FFmpeg SHA256 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| FFprobe SHA256 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |
| 分发目录 | 244 个文件，共 `428,261,683` 字节 |
| 隔离验收根目录 | `E:\QRtest\QuickRec-v1.9.1-acceptance` |
| 隔离运行目录 | `run-20260727-174322` |

rc1 至 rc5 均因后续代码修复失效，不得作为最终发布包；其中不受后续修复影响的
GUI 证据可按本记录中的依赖分析继承。

## 3. 环境保护与证据规则

1. 使用独立 APPDATA、LOCALAPPDATA、项目目录和视频目录。
2. 未修改或删除用户真实项目、素材索引、预览缓存和视频。
3. 失败、缺失、损坏、容量和中文空格路径样本均使用受控副本。
4. 每项结论区分实际 GUI、自动化 UI、文件系统、日志和继承回归证据。
5. 验收完成后通过真实托盘退出，确认无 QuickRec、FFmpeg 或 FFprobe 残留。
6. QuickRec Lite 工作区仅检查 Git 状态，不执行功能操作。

## 4. D8 验收结果

| 验收项 | 结论 | 证据与说明 |
| --- | --- | --- |
| D8.1 新项目预览闭环 | 通过 | rc3 实际项目页完成排队、生成、320×180 JPEG、元数据展示、缓存命中与单项刷新 |
| D8.2 v1.9 项目兼容 | 通过 | 既有项目无预览字段也可直接打开；项目文件和中央索引不写预览字段 |
| D8.3 状态与恢复 | 通过 | 未生成、排队、生成中、可用、失败、失效、文件缺失和待关联均有测试；缺失文件保留历史预览，恢复后可重新生成 |
| D8.4 刷新与批量重建 | 通过 | rc3 实际刷新显示“首帧预览已刷新”；批量重建、取消、统计和归档只读规则通过 |
| D8.5 文件与页面跳转 | 通过 | rc5 实际打开播放器、实际用资源管理器定位中文空格路径；项目与素材库往返、稳定 ID 定位通过 |
| D8.6 性能与容量 | 通过 | 0、1、20、50、200 条受控项目可打开；200 条切换约 240 ms；500 MiB LRU、单项失败隔离由自动化验证 |
| D8.7 DPI 与布局 | 通过 | 100%、125%、150% 自动化 UI 截图均为 `no_overlap=true`；rc4 实际窗口确认预览与操作底栏不重叠 |
| D8.8 录制回归 | 通过 | 候选链路实际生成 1920×1080、30 FPS、18.8 秒全屏视频；区域、窗口、四类音频和 60/120 FPS 继承 v1.9 正式验收，相关录制核心未修改 |
| D8.9 工作台与退出 | 通过 | rc6 从托盘打开工作台；真实托盘退出后主进程、FFmpeg、FFprobe 均结束，启动进程自然返回 0 |
| D8.10 Lite 隔离 | 通过 | `E:\codex\QuickRec-Lite` 工作区保持干净，未修改 |

## 5. 关键证据

### 5.1 最终候选启动与退出

- 工作台截图：
  `E:\QRtest\QuickRec-v1.9.1-acceptance\evidence\rc6-workbench-startup.png`
- 退出日志：
  `E:\QRtest\QuickRec-v1.9.1-acceptance\run-20260727-174322\videos\QuickRecDiagnostics\quickrec.log`
- 日志终态：
  - `2026-07-27 19:40:16,403` 预览协调器停止，活动任务为 0；
  - `2026-07-27 19:40:16,405` QuickRec 已退出。
- 进程检查：
  - `QuickRec.exe`：不存在；
  - `ffmpeg.exe`：不存在；
  - `ffprobe.exe`：不存在。

### 5.2 文件操作

- 打开目录：
  `E:\QRtest\QuickRec-v1.9.1-acceptance\evidence\rc5-open-directory-unicode-space.jpg`
- 打开文件：
  `E:\QRtest\QuickRec-v1.9.1-acceptance\evidence\rc5-open-file-player.jpg`
- 受控视频：
  `E:\QRtest\QuickRec-v1.9.1-acceptance\evidence\中文 空格\候选包样本.mp4`
- 视频 SHA256：
  `D316FEFDE7FC4F7F7E039662AEE0B403C9AC410009E4C21B302408FF7E7C74BA`
- FFprobe：H.264、640×360、30 FPS、2.0 秒。

rc6 相对 rc5 只修改托盘退出顺序；文件打开和目录参数实现没有变化，因此 rc5 的实际
GUI 证据可继承到 rc6。

### 5.3 布局与 DPI

- 实际布局截图：
  `E:\QRtest\QuickRec-v1.9.1-acceptance\evidence\rc4-project-buttons-fixed.jpg`
- 自动化 UI 截图：
  - `rc4-project-layout-100.png`
  - `rc4-project-layout-125.png`
  - `rc4-project-layout-150.png`
- 对应 JSON 均记录 `no_overlap=true`。

### 5.4 录制与数据隔离

- 实际录制：
  `E:\QRtest\QuickRec-v1.9.1-acceptance\run-20260727-174322\videos\QuickRec_20260727_174514.mp4`
- SHA256：
  `7FD319DE2AF3E0F1BD76CD201C2445C51C28D770D3DD8D855D731DCD59CCE7E1`
- 结果：1920×1080、30 FPS、18.8 秒、564 帧、无音频，实际采集约 29.997 FPS。
- 中央索引从 1 条增至 2 条，录制元数据与 FFprobe 一致。
- 预览协调器在录制开始时暂停新任务，保存完成后恢复。

## 6. 缺陷闭环

| 缺陷 | 结论 | 最终证据 |
| --- | --- | --- |
| BUG-191-01 单项刷新状态不结束 | 已关闭 | rc3 实际显示刷新成功终态 |
| BUG-191-02 延迟查询覆盖跳转目标 | 已关闭 | rc3 实际定位并保持项目返回上下文 |
| BUG-191-03 预览覆盖操作按钮 | 已关闭 | rc4 实际截图和三档自动化布局 |
| BUG-191-04 中文空格路径无法定位 | 已关闭 | rc5 资源管理器实际定位目标文件 |
| BUG-191-05 托盘退出后进程残留 | 已关闭 | rc6 真实托盘退出、进程清理和自然返回 0 |

## 7. 已知边界

- v1.9.1 不提供内嵌播放器。
- 首帧预览是可删除、可重建缓存，不是项目数据。
- 区域、窗口、四类音频和 60/120 FPS 使用 v1.9 正式验收证据继承；
  本轮没有修改对应录制核心。
- 本结论只授权进入发布收口，不等同于已经发布。

## 8. 最终判断

D8 关键链路已闭合，无发布阻塞项。QuickRec Full v1.9.1 已完成正式发布收口。
