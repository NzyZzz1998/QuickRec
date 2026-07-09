# QuickRec Changelog

## v1.4.x - 2026-07-09

### Added

- 新增 Full 版本诊断日志 / 错误导出能力。
- 设置页新增“诊断”分组，支持诊断目录配置。
- 托盘菜单和设置页新增“复制诊断信息”“打开日志目录”“导出诊断文件”。
- 新增本地文件日志 `quickrec.log`，默认位于视频保存路径下的 `QuickRecDiagnostics` 目录。
- 新增 UTF-8 诊断导出文件 `diagnostic_YYYYMMDD_HHMMSS.txt`。
- 诊断摘要覆盖应用环境、配置、录制状态、FFmpeg、音频、窗口诊断、错误和最近日志。

### Fixed

- 修复带 UTF-8 BOM 的历史配置文件会导致启动时回退默认配置的问题。

### Verified

- 自动化测试、ruff、compileall、packaging 测试通过。
- 打包产物 GUI 手动验收通过。
- 全屏、区域、窗口录制回归通过。
- 系统声、麦克风、双音频录制回归通过。
- FFmpeg 缺失异常诊断场景通过。

### Scope

- 不做云上传。
- 不做复杂诊断中心。
- 不做自动修复。
- 不改变 Lite v0 范围。

## v1.4 - 2026-07-05

- 稳定性与工程化大型优化版本。
- 强化 FFmpeg、cv2、音频预检、窗口录制、退出流程、临时目录清理和打包验证。
- 详见 `doc/release-notes-v1.4.md`。
