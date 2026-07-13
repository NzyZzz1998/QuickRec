# QuickRec Full v1.6 开发日志

> 本文记录开发阶段、关键实现、技术决策和验证结果。任务完成状态以 [progress.md](progress.md) 为准，真实缺陷以 [bugfix-log.md](bugfix-log.md) 为准。

## 2026-07-10 D0 发布债与开发基线

### 本轮目标

- 建立 v1.6 功能分支。
- 隔离开机自启测试对真实 HKCU 的影响。
- 建立单一版本事实源。
- 固定 v1.5 发布事实和 v1.6 迁移测试夹具。

### 关键实现

- 从 Full `master` 创建 `feature/v1.6-material-library`。
- 自启测试改为 mock `winreg`，测试前后真实 HKCU 均无 `QuickRec` 项。
- `enable_autostart()` 改用 `CreateKeyEx`，允许 Run 键不存在时安全创建。
- 新增 `src/version.py`，诊断报告从统一 `APP_VERSION` 读取版本。
- 补充 v1.5 GitHub Release 地址和 ZIP SHA256。
- 新增 `tests/fixtures/v1_6/` schema v1 迁移样本。

### 验证

- `tests/test_v1_2.py`：26 passed。
- `tests/test_main_workflow.py tests/test_diagnostics.py`：25 passed。
- `compileall`：通过。
- `ruff`：通过。
- `mypy`：通过。

### 待完成

- 创建动态 201 条、双保存目录和 MP4 扫描样本的测试工厂。
- 完成 D0 全量回归与 Git 状态收口。

## 2026-07-10 D2-D5 素材库主链路

### 关键实现

- 新增 schema v2 中央素材索引、200 条上限、路径去重、原子写入、有效备份和损坏归档恢复。
- 新增 `RecordingLibraryService`，统一承接新增、迁移、导入、重建、重新定位、移除和回收站操作。
- v1.5 旧索引迁移拆分为预览与提交，旧文件保持不变；首次启动迁移在后台执行。
- 目录重建使用 `QThread`，只扫描当前层级 `QuickRec_*.mp4`，关闭窗口可请求取消。
- 引入与现有 FFmpeg 同源同版本的 `ffprobe.exe`，新增媒体元数据结构化降级。
- `RecorderManager` 提供会话已知时长、输出宽高、FPS、模式和音频，新录制入库不重复执行 `ffprobe`。
- 托盘和结果条入口统一为“素材库”；索引写入失败不影响 MP4 保存成功，并提供结果条重试。
- 素材库实现列表详情、50 条增量加载、状态反馈、重新定位、仅移除索引和移入回收站。

### 自动化验证

- 相关模块测试：131 passed。
- 全量测试：329 passed，24 deselected，22 subtests passed。
- 全量 coverage：82.57%；新增 `media_metadata` 定向 coverage：83.15%。
- ruff：通过，新素材库 UI 已纳入检查。
- mypy：通过，共检查 15 个源文件。

### 当前边界

- `v1.5` 仍是正式发布版，v1.6 尚未打包和手动验收。
- QuickRec Lite 未修改。
- WGC、120 FPS、完整工作台和 AI 不在本版范围。
