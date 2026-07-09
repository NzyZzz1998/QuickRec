# QuickRec v1.4 Release Notes

发布日期：2026-07-05

## 发布定位

v1.4 是一次稳定性与工程化大型优化版本，不以新增用户入口为目标，重点是让 v1.3 已有录制能力更可靠、可测试、可发布。

v1.4 正式发布使用稳定包：

```text
dist/QuickRec/QuickRec.exe
```

UPX FFmpeg 体积实验包仅作为后续优化候选，不进入 v1.4 正式发布。

## 主要变化

### 稳定性

- 修复并强化 FFmpeg 路径、启动、编码失败和混流失败处理。
- 保留 cv2，避免 dxcam 默认捕获链路出现 0 帧或无法播放问题。
- 增加音频预检与降级策略，降低系统声音、麦克风、双音频不可用时生成损坏文件的风险。
- 增强临时目录清理、退出流程、系统计时器配对和磁盘空间监控。

### 窗口录制

- 窗口移动时冻结最后稳定帧，停止移动后继续更新，避免移动期间画面漂移和区域重建抖动。
- 普通窗口、最大化窗口、最小化/恢复、关闭窗口路径完成回归。
- 窗口录制暂不叠加鼠标，避免后期贴图导致比例异常、大鼠标闪现和 DPI 误差。
- 后续版本将单独评估能原生捕获光标的捕获链路。

### 工程化

- 增加本地硬件冒烟脚本：`scripts/hardware_smoke.py`。
- 增加 FFmpeg 能力检查脚本：`scripts/ffmpeg_capability_check.py`。
- 增加打包体积分析脚本：`scripts/package_size_report.py`。
- 补充窗口诊断、音频预检、架构边界、硬件冒烟、体积报告等自动化测试。
- 更新 PRD、技术设计、开发计划、进度、测试用例和产品原型文档。

### 打包体积

- v1.4 稳定包体积：`257.89MB`。
- 主要体积来源：FFmpeg、OpenCV/cv2、PyQt5、NumPy、Python runtime。
- UPX FFmpeg 实验包体积：`187.89MB`。
- UPX 实验仍需区域录制、窗口录制、真实音频混流和杀软误报回归，因此暂不合入正式发布。

## 验证结果

- `python -m pytest -q`：`230 passed, 23 deselected, 18 subtests passed`
- `python -m ruff check .`：通过
- `python -m mypy`：通过
- `python -m compileall src scripts tests`：通过
- 稳定包启动冒烟：通过
- 本地硬件冒烟：通过

硬件冒烟命令：

```powershell
python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen
```

本次手动硬件冒烟输出：

```text
E:\QRtest\QuickRec_20260705_165730.mp4
```

## 已知限制

- 窗口录制暂不录制鼠标。
- 窗口移动期间采用冻结画面策略，不是真正实时跟随。
- 游戏全屏、UWP、DWM 自定义渲染窗口仍可能不可录制。
- 当前仅支持主显示器录制。
- 编码参数暂未开放高级配置。
- CI 无法覆盖真实桌面和真实音频设备，发布前仍需本地手动验收。

## 后续方向

- 评估 Windows Graphics Capture 等能原生捕获光标的捕获后端。
- 继续推进 Lite / Full 分支规划。
- Lite 方向优先减少依赖和体积。
- Full 方向面向创作者工作台，规划素材管理、轻编辑、导出队列和质量诊断中心。

---

## v1.4.x 诊断导出能力补充

发布日期：2026-07-09

### 发布定位

v1.4.x 是 Full 版本在 v1.4 稳定性收口后的诊断能力补充，不改变 Lite 范围，不扩展为复杂诊断中心，重点提升录制失败、音频异常、FFmpeg 异常、保存失败和窗口捕获异常时的本地排查效率。

### 新增能力

- 设置页新增“诊断”分组，支持配置诊断目录。
- 托盘菜单和设置页均支持复制诊断信息、打开日志目录、导出诊断文件。
- 默认在视频保存路径下生成 `QuickRecDiagnostics` 目录，并写入 `quickrec.log`。
- 诊断文件使用 UTF-8 文本格式，命名为 `diagnostic_YYYYMMDD_HHMMSS.txt`。
- 诊断摘要包含应用环境、配置摘要、录制状态、FFmpeg 路径、音频预检、窗口诊断、最近错误和最近日志。
- 兼容带 UTF-8 BOM 的历史配置文件，避免启动时回退默认配置。

### 验收结果

- `python -m pytest tests/test_config.py tests/test_diagnostics.py tests/test_settings_dialog.py tests/test_main_workflow.py -q`：`45 passed`
- `python -m ruff check src\config.py tests\test_config.py`：通过
- `python -m compileall src tests`：通过
- `python -m pytest -m packaging -q`：`10 passed, 1 skipped`
- 打包产物 GUI 手动验收：通过
- 全屏、区域、窗口录制回归：通过
- 系统声、麦克风、双音频录制回归：通过
- FFmpeg 缺失异常诊断：通过

关键验收证据：

```text
E:\QRtest\pkg_audio\QuickRecDiagnostics\diagnostic_20260709_142944.txt
E:\QRtest\pkg_audio\QuickRecDiagnostics\quickrec.log
```

### 已知限制

- 当前诊断信息仅保存在本地，不做云上传。
- 当前不做自动修复、不做独立诊断中心。
- 当前无需脱敏，用户导出前应自行确认是否包含本机路径、窗口标题等本地上下文。
- CI 仍无法覆盖真实桌面、真实托盘交互和真实音频设备，发布前仍依赖本地手动验收。
