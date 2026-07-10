# QuickRec Full v1.5 进度看板

> 版本：v1.5
> 创建时间：2026-07-10
> 状态：v1.5 正式发布
> PRD：[prd.md](prd.md)
> Dev Plan：[dev_plan.md](dev_plan.md)
> 原型：[../../prototypes/product-prototype/full.html](../../prototypes/product-prototype/full.html)

---

## 1. 总体状态

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| D0 文档与分支准备 | ✅ 完成 | 已创建 `feature/v1.5-full-foundation` 并确认 Full 边界 |
| D1 自绘光标收口 | ✅ 完成 | 输出帧不再调用自绘光标叠加，目标测试已通过 |
| D2 录制历史 / 素材入库基础设施 | ✅ 完成 | 本地 JSON 历史记录、50 条保留、缺失状态测试已通过 |
| D3 最近录制 UI 与主流程接入 | ✅ 完成 | 托盘入口、结果条入口、最近录制窗口测试已通过 |
| D4 WGC / 新捕获后端 spike | ✅ 完成 | 已输出研究记录，不替换默认 dxcam |
| D5 原型与文档同步 | ✅ 完成 | 原型和 v1.5 文档口径检查已通过 |
| D6 测试、打包与发布前验收 | ✅ 完成 | D6.1 自动化、D6.2 硬件 smoke、D6.3 GUI 与原型验收均已通过 |

当前发布判断：**D6.3 与发布前收口均已通过，v1.5 正式发布。** 详见 [manual-verification.md](manual-verification.md) 与 [release-notes.md](release-notes.md)。

---

## 2. D0 文档与分支准备

- [x] 确认 `doc/releases/v1.5/prd.md` 已作为需求基线。
- [x] 确认 `doc/releases/v1.5/dev_plan.md` 已通过。
- [x] 确认 `doc/releases/v1.5/progress.md` 已通过。
- [x] 确认本轮只修改 QuickRec Full，不修改 QuickRec Lite。
- [x] 确认 `v1.4.1` tag 不移动。
- [x] 从 Full `master` 派生或确认开发分支。
- [x] 检查工作区状态，记录开发前未提交文件。
- [x] 确认不新增完整工作台、剪辑、导出队列、云同步、数据库。

---

## 3. D1 自绘光标收口

### D1.1 调用链确认

- [x] 搜索 `draw_cursor` 所有调用点。
- [x] 确认录制输出链路中的调用位置。
- [x] 确认窗口录制当前已不叠加自绘光标。
- [x] 确认鼠标点击高亮由 `click_highlighter` 屏幕叠加层负责。

### D1.2 输出链路修改

- [x] 修改 `src/recorder/recorder_manager.py`，编码帧不再叠加自绘光标。
- [x] 保留全屏、区域、窗口的帧尺寸缩放逻辑。
- [x] 保留鼠标点击高亮设置和运行逻辑。
- [x] 确认录制输出帧不依赖 `cursor_overlay.py`。
- [x] 确认移除自绘光标后不会改变保存成功回调。

### D1.3 测试

- [x] 更新 `tests/test_recorder_manager.py`，覆盖不再调用自绘光标。
- [x] 调整 `tests/test_cursor_overlay.py` 定位，避免把自绘光标视为输出链路必需能力。
- [x] 回归 `tests/test_settings_dialog.py`，确认鼠标点击高亮设置仍存在。
- [x] 运行 `python -m pytest tests/test_recorder_manager.py tests/test_settings_dialog.py -q`。

---

## 4. D2 录制历史 / 素材入库基础设施

### D2.1 数据模型

- [x] 新增 `src/utils/recording_history.py`。
- [x] 定义历史文件路径：`<save_path>\QuickRecMetadata\recordings.json`。
- [x] 定义 `schema_version`。
- [x] 定义 `max_items` 默认值 50。
- [x] 定义记录字段：`id`、`file_path`、`file_name`、`directory`、`mode`、`audio_source`、`created_at`。
- [x] 定义可选字段：`duration_sec`、`file_size_bytes`、`diagnostic_dir`。
- [x] 定义 `status`：`available` / `missing`。

### D2.2 读写能力

- [x] 历史文件不存在时返回空列表。
- [x] JSON 解析失败时返回可处理结果，不影响录制。
- [x] 写入前创建 `QuickRecMetadata` 目录。
- [x] 新记录插入列表顶部。
- [x] 超过 50 条时自动裁剪。
- [x] 写入使用临时文件 + 原子替换。
- [x] 写入失败只记录日志，不影响视频保存。
- [x] 加载时检查文件是否存在并更新状态。
- [x] 支持按 `id` 从列表移除。

### D2.3 日志

- [x] 记录 `recording history saved`。
- [x] 记录 `recording history save failed`。
- [x] 记录 `recording history loaded`。
- [x] 记录 `recording history load failed`。
- [x] 记录 `recording history pruned`。
- [x] 记录 `recording history item removed`。
- [x] 记录 `recording file missing`。

### D2.4 测试

- [x] 新增 `tests/test_recording_history.py`。
- [x] 测试空历史加载。
- [x] 测试新增记录。
- [x] 测试保留最近 50 条。
- [x] 测试文件缺失状态。
- [x] 测试从列表移除。
- [x] 测试 JSON 损坏降级。
- [x] 测试写入失败不抛出到调用方。
- [x] 运行 `python -m pytest tests/test_recording_history.py -q`。

---

## 5. D3 最近录制 UI 与主流程接入

### D3.1 主流程接入

- [x] 在 `src/main.py` 初始化最近录制服务。
- [x] 在录制保存成功后写入历史记录。
- [x] 写入历史失败时保留“录制已保存”结果。
- [x] 写入历史失败时记录日志和诊断上下文。
- [x] 新增打开最近录制窗口回调。
- [x] 确认保存失败时不写入成功历史记录。

### D3.2 托盘入口

- [x] `src/ui/tray_icon.py` 空闲菜单新增“最近录制”。
- [x] `src/ui/tray_icon.py` 录制中菜单新增“最近录制”。
- [x] 新增 pystray 到 Qt 的信号桥。
- [x] 新增主入口 callback 绑定。
- [x] 更新 `tests/test_tray_icon.py` 覆盖菜单项和信号桥。

### D3.3 结果条入口

- [x] `src/ui/toolbar.py` 保存结果条新增“最近录制”入口。
- [x] 入口点击后通知主入口打开最近录制窗口。
- [x] 保持现有已保存、打开、关闭行为不回退。
- [x] 结果条布局不明显溢出或遮挡。

### D3.4 最近录制窗口

- [x] 新增 `src/ui/recent_recordings_dialog.py`。
- [x] 显示文件名、录制模式、创建时间、文件大小、状态。
- [x] 支持打开文件。
- [x] 支持打开目录。
- [x] 支持复制路径。
- [x] 支持从列表移除。
- [x] 文件不存在时显示“文件已移动或删除”。
- [x] 无记录时显示“暂无录制记录”。
- [x] 打开文件失败时给出非阻塞反馈。
- [x] 打开目录失败时给出非阻塞反馈。
- [x] 复制路径成功时给出反馈。

### D3.5 UI 测试

- [x] 新增或扩展 `tests/test_recent_recordings_dialog.py`。
- [x] 覆盖空状态。
- [x] 覆盖正常记录显示。
- [x] 覆盖缺失记录显示。
- [x] 覆盖复制路径。
- [x] 覆盖从列表移除。
- [x] 扩展 `tests/test_main_workflow.py` 覆盖保存后写入历史。
- [x] 运行 `python -m pytest tests/test_main_workflow.py tests/test_tray_icon.py tests/test_recent_recordings_dialog.py -q`。

---

## 6. D4 WGC / 新捕获后端 spike

- [x] 新增 `doc/releases/v1.5/capture-backend-spike.md`。
- [x] 记录 WGC 是否可能原生捕获光标。
- [x] 记录 WGC 对窗口录制移动、缩放、DPI、最大化场景的潜在价值。
- [x] 记录 PyInstaller 兼容风险。
- [x] 记录与现有 dxcam 并存的可行性。
- [x] 明确本轮不替换默认 dxcam。
- [x] 明确本轮不新增用户可见后端切换。
- [x] 给出是否进入后续 PRD 的建议。

---

## 7. D5 原型与文档同步

- [x] 确认 `doc/prototypes/product-prototype/full.html` 包含“最近录制”入口。
- [x] 确认原型包含最近录制列表、复制路径、打开目录、从列表移除模拟交互。
- [x] 确认 `doc/prototypes/product-prototype/prototype-design.md` 包含 v1.5 对应关系。
- [x] 如实现文案与原型不一致，更新原型说明或 PRD 验收口径。
- [x] 确认原型中的完整工作台能力不进入 v1.5 必做范围。
- [x] 运行 `rg -n "最近录制|素材入库|v1.5|自绘光标|WGC" doc/releases/v1.5 doc/prototypes/product-prototype`。

---

## 8. D6 测试、打包与发布前验收

### D6.1 自动化测试

- [x] `python -m pytest tests/test_recording_history.py tests/test_recent_recordings_dialog.py tests/test_tray_icon.py tests/test_main_workflow.py tests/test_recorder_manager.py -q`
- [x] `python -m pytest tests/test_diagnostics.py tests/test_settings_dialog.py -q`
- [x] `python -m compileall src scripts tests`
- [x] `python -m ruff check .`
- [x] `python -m mypy`

### D6.2 硬件 smoke

- [x] `python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen`

### D6.3 GUI 手动验收

- [x] V15-A1 全屏录制 3 秒，视频可播放，未写入自绘光标。
- [x] V15-A2 区域录制 3 秒，视频可播放，未写入自绘光标。
- [x] V15-A3 窗口录制 3 秒，视频可播放，未写入自绘光标。
- [x] V15-A4 鼠标点击高亮屏幕可见，视频不额外写入高亮动画。
- [x] V15-H1 录制成功后最近录制列表出现新记录。
- [x] V15-H2 超过 50 条后只保留最近 50 条。
- [x] V15-H3 可打开录制文件。
- [x] V15-H4 可打开文件所在目录。
- [x] V15-H5 可复制录制路径。
- [x] V15-H6 文件被移动或删除后显示缺失状态。
- [x] V15-H7 可从列表移除无效记录。
- [x] V15-H8 无记录时显示空状态。
- [x] V15-H9 历史写入失败时视频仍保存成功。
- [x] V15-S1 WGC spike 有研究记录，默认 dxcam 不受影响。
- [x] V15-P1 Full 原型包含最近录制 / 素材入库入口。

---

## 9. 当前阻塞与边界

当前阻塞：无。`BUG-V15-P1-001` 已修复并复验通过；详情见 [manual-verification.md](manual-verification.md) 与 [bugfix-log.md](bugfix-log.md)。

最近验证：用户人工确认 V15-A4、最近录制两个入口、V15-H1 至 V15-H5、V15-H8、设置与诊断回归通过；H6/H7 的 4 项目标测试通过；V15-P1 空状态修复后自动复验通过，原有交互无回归。

下一步：保持 v1.5 稳定线，新增需求重新进入 `/idea -> /prd`，修复类变更按独立补丁版本验收。

边界提醒：

- 不改 Lite。
- 不新增完整工作台。
- 不新增数据库。
- 不替换默认捕获后端。
- 不移动 v1.4.1 tag。
- progress 只记录状态，不记录开发日志或排查流水。
