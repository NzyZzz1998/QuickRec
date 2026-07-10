# QuickRec Full v1.5 开发计划

> 版本：v1.5
> 创建时间：2026-07-10
> 状态：已完成
> 产品线：QuickRec Full
> PRD：[prd.md](prd.md)
> Progress：[progress.md](progress.md)
> 原型：[../../prototypes/product-prototype/full.html](../../prototypes/product-prototype/full.html)
> 建议开发分支：`feature/v1.5-full-foundation`

---

## 1. 开发总览

### 1.1 目标

v1.5 是 QuickRec Full 从“单次录制工具”向“创作者工作台”演进的地基版本。本次只做三件事：

- 移除录制输出链路中的自绘光标叠加，降低鼠标比例异常、闪现和维护风险。
- 增加“最近录制 / 素材入库”最小闭环，让录制结果在应用内可查看、打开、定位、复制路径和移除无效记录。
- 对 WGC / 新捕获后端做技术 spike，形成后续是否进入正式 PRD 的依据，不替换默认 dxcam 链路。

### 1.2 本次不变范围

| 范围 | 说明 |
| --- | --- |
| Lite 产品线 | 不修改 `E:\codex\QuickRec-Lite`，不把 v1.5 能力同步到 Lite |
| 默认捕获链路 | 不把 WGC 设为默认，不新增用户可见后端切换 |
| 完整工作台 | 不做项目库、剪辑、导出队列、模板、复杂素材库 |
| 诊断能力 | 不回退 v1.4.1 诊断导出，不扩展成复杂诊断中心 |
| 存储形态 | 不引入 SQLite、云同步、账号、多设备同步 |
| 鼠标点击高亮 | 保留屏幕叠加层能力，但不写入视频帧 |

### 1.3 现有项目脉络 Review

| 模块 | 当前状态 | 与本次关系 |
| --- | --- | --- |
| `src/main.py` | 应用装配、托盘回调、设置页、录制保存完成处理集中在入口类 | 需要在保存完成后写入最近录制记录，并接入最近录制窗口 |
| `src/recorder/recorder_manager.py` | 录制核心、帧处理、音频混流、保存回调 | 需要停止调用自绘光标叠加，并提供录制结果上下文 |
| `src/recorder/cursor_overlay.py` | 自绘光标工具 | 本次不再进入录制输出链路，可保留为历史代码或后续删除候选 |
| `src/ui/click_highlighter.py` | 鼠标点击高亮屏幕叠加层 | 需要保留，不写入编码帧 |
| `src/ui/tray_icon.py` | 托盘菜单和 pystray 到 Qt 的信号桥 | 需要新增“最近录制”菜单项 |
| `src/ui/toolbar.py` | 悬浮录制控制条和保存结果条 | 保存结果条需要新增“查看最近录制”入口 |
| `src/config.py` | 保存路径、诊断目录、录制配置 | 最近录制默认随保存路径写入，无需新增用户可见配置 |
| `src/utils/diagnostics.py` | v1.4.1 诊断导出工具 | 最近录制可记录诊断目录路径，但不扩展诊断中心 |
| `tests/test_recorder_manager.py` | 录制核心行为测试 | 需要覆盖不再自绘光标 |
| `tests/test_tray_icon.py` | 托盘菜单测试 | 需要覆盖最近录制入口 |
| `tests/test_main_workflow.py` | 主流程与回调测试 | 需要覆盖保存后写入历史和打开最近录制 |
| `tests/test_cursor_overlay.py` | 自绘光标工具测试 | 需要调整定位，避免把自绘光标视为输出链路必需能力 |

### 1.4 模块映射

| PRD 模块 | 开发阶段 | 验收重点 |
| --- | --- | --- |
| M1 自绘光标收口 | D1 | 全屏、区域、窗口录制输出不再写入自绘光标 |
| M2 录制历史 / 素材入库 | D2 | 写入、读取、保留 50 条、缺失文件状态、移除记录 |
| M3 最近录制 UI | D3 | 托盘入口、结果条入口、打开文件/目录、复制路径、空状态 |
| M4 WGC / 新捕获后端 spike | D4 | 输出研究记录，不影响默认 dxcam |
| M5 Full 原型同步 | D5 | 原型已包含最近录制入口，开发完成后再做一致性核对 |
| 验收与发布前验证 | D6 | 自动化、硬件 smoke、GUI 手动验收、回归录制和音频 |

---

## 2. 实施阶段

### D0：文档与分支准备

**目标**：确认 v1.5 需求、计划、任务看板和工作区边界，避免混入 Lite 或 v1.4.1 tag。

**详细步骤**：

1. 从 Full `master` 派生 `feature/v1.5-full-foundation`。
2. 确认 `doc/releases/v1.5/prd.md` 为需求基线。
3. 确认 `doc/releases/v1.5/dev_plan.md` 和 `doc/releases/v1.5/progress.md` 已通过。
4. 检查工作区状态，确认没有业务代码改动被带入承接提交。
5. 确认 `v1.4.1` tag 不移动，Lite 工作区不参与本轮开发。

**验证**：

```powershell
git status --short --branch
git tag --points-at HEAD
```

### D1：自绘光标收口

**目标**：录制输出帧不再主动叠加自绘光标，同时保留鼠标点击高亮屏幕叠加层。

**建议修改文件**：

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `src/recorder/recorder_manager.py` | 修改 | `_prepare_frame_for_encoding` 不再调用 `draw_cursor` |
| `src/recorder/cursor_overlay.py` | 评估 | 可保留历史工具，但不应由录制输出链路调用 |
| `tests/test_recorder_manager.py` | 修改 | 覆盖全屏/区域/窗口均不叠加自绘光标 |
| `tests/test_cursor_overlay.py` | 评估 | 若保留工具测试，应明确它不是输出链路验收依据 |
| `tests/test_settings_dialog.py` | 回归 | 鼠标点击高亮设置仍存在 |

**详细步骤**：

1. 定位所有 `draw_cursor` 调用点。
2. 从编码帧准备链路移除自绘光标调用。
3. 保留窗口录制已有“不叠加光标”的行为。
4. 确认 `click_highlighter` 仍由 UI 叠加层控制，不进入视频帧。
5. 更新或新增测试，证明输出帧不会因光标位置变化而改变。

**验证命令**：

```powershell
python -m pytest tests/test_recorder_manager.py tests/test_settings_dialog.py -q
```

**回退方式**：

- 若移除后导致帧尺寸、颜色格式或编码异常，只回退 `_prepare_frame_for_encoding` 相关改动，不影响最近录制模块。

### D2：录制历史 / 素材入库基础设施

**目标**：建立本地 JSON 历史记录能力，录制成功后可生成可管理素材记录。

**建议新增文件**：

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `src/utils/recording_history.py` | 新增 | 最近录制记录读写、裁剪、缺失检查、移除 |
| `tests/test_recording_history.py` | 新增 | 纯逻辑测试，不依赖真实录制 |

**建议数据文件**：

```text
<save_path>\QuickRecMetadata\recordings.json
```

**核心字段**：

| 字段 | 说明 |
| --- | --- |
| `schema_version` | v1.5 固定为 1 |
| `max_items` | 默认 50 |
| `items` | 最近录制记录，按 `created_at` 倒序 |
| `id` | 本地唯一 ID |
| `file_path` | 录制文件绝对路径 |
| `file_name` | 录制文件名 |
| `directory` | 文件所在目录 |
| `mode` | `fullscreen` / `region` / `window` |
| `audio_source` | `none` / `system` / `mic` / `both` |
| `created_at` | ISO 时间 |
| `duration_sec` | 可为空 |
| `file_size_bytes` | 可为空 |
| `status` | `available` / `missing` |
| `diagnostic_dir` | 可为空 |

**详细步骤**：

1. 实现历史文件路径解析：随当前保存路径定位到 `QuickRecMetadata\recordings.json`。
2. 实现缺失文件加载为空列表。
3. 实现 JSON 解析失败降级：记录日志，不影响录制保存。
4. 实现新增记录：插入到列表顶部，按时间倒序保留 50 条。
5. 实现原子写入：临时文件写入后替换，降低半写入风险。
6. 实现打开列表时检查文件是否存在，更新 `status`。
7. 实现按 `id` 从列表移除。
8. 记录必要日志：保存、保存失败、加载、加载失败、裁剪、移除、文件缺失。

**验证命令**：

```powershell
python -m pytest tests/test_recording_history.py -q
```

**回退方式**：

- 若历史写入失败影响录制保存，立即改为捕获异常并只记录日志；录制保存成功优先级高于历史记录完整性。

### D3：最近录制 UI 与主流程接入

**目标**：用户可从托盘菜单和录制结果条打开最近录制列表，并完成常用操作。

**建议新增文件**：

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `src/ui/recent_recordings_dialog.py` | 新增 | 最近录制轻量窗口 |
| `tests/test_recent_recordings_dialog.py` | 新增 | UI 行为测试，尽量避免真实文件打开 |

**建议修改文件**：

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `src/main.py` | 修改 | 保存成功后写入历史；新增打开最近录制回调 |
| `src/ui/tray_icon.py` | 修改 | 托盘空闲/录制中菜单新增“最近录制” |
| `src/ui/toolbar.py` | 修改 | 保存结果条新增“最近录制”入口 |
| `tests/test_main_workflow.py` | 修改 | 覆盖回调和历史写入降级 |
| `tests/test_tray_icon.py` | 修改 | 覆盖菜单项和信号桥 |

**详细步骤**：

1. 在 `main.py` 的保存完成处理里，视频保存成功后写入历史记录。
2. 写入失败时只记录日志和诊断上下文，不改变“录制已保存”结果。
3. 托盘菜单新增“最近录制”，通过信号桥回到 Qt 主线程。
4. 保存结果条新增“最近录制”入口；入口只打开列表，不阻塞结果条关闭。
5. 新增最近录制窗口：
   - 显示文件名、模式、时间、大小、状态。
   - 支持打开文件。
   - 支持打开目录。
   - 支持复制路径。
   - 支持从列表移除。
   - 支持空状态。
   - 支持文件缺失状态。
6. 所有文件打开和目录打开失败均提示，不导致 UI 崩溃。

**验证命令**：

```powershell
python -m pytest tests/test_main_workflow.py tests/test_tray_icon.py tests/test_recent_recordings_dialog.py -q
```

**回退方式**：

- 若最近录制窗口不稳定，可先保留历史写入和托盘入口关闭，阻断发布直到 UI 修复；不回退 v1.4.1 诊断能力。

### D4：WGC / 新捕获后端 spike

**目标**：输出技术研究记录，判断后续是否值得进入独立 PRD。

**建议新增文件**：

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `doc/releases/v1.5/capture-backend-spike.md` | 新增 | WGC / 新捕获后端研究记录 |

**研究问题**：

1. 是否能原生捕获光标。
2. 是否能改善窗口录制移动、缩放、DPI、最大化场景。
3. 是否与 PyInstaller、Windows 权限、音频混流链路兼容。
4. 是否能与现有 dxcam 链路并存。
5. 是否适合作为 v1.6 或更后版本的独立 PRD。

**约束**：

- 本阶段不替换默认 dxcam。
- 本阶段不新增用户可见后端切换。
- 如需试验代码，必须与主录制链路隔离。

**验证**：

```powershell
rg -n "WGC|Windows Graphics Capture|dxcam|cursor" doc/releases/v1.5
```

### D5：原型与文档同步

**目标**：确保 PRD、原型、计划和进度口径一致。

**已完成基础**：

- `doc/prototypes/product-prototype/full.html` 已包含“最近录制”入口和模拟交互。
- `doc/prototypes/product-prototype/prototype-design.md` 已补充 v1.5 对应关系。

**详细步骤**：

1. 实现完成后对照 UI 原型检查入口和交互名称。
2. 若实现中因技术原因调整文案或入口位置，更新 PRD 的验收说明或原型说明。
3. 不把原型里的 Full 工作台完整页面当作 v1.5 必做范围。

**验证命令**：

```powershell
rg -n "最近录制|素材入库|v1.5|自绘光标|WGC" doc/releases/v1.5 doc/prototypes/product-prototype
```

### D6：测试、打包与发布前验收

**目标**：确认 v1.5 不破坏 v1.4.1 稳定录制、诊断导出和打包能力。

**自动化验证命令**：

```powershell
python -m pytest tests/test_recording_history.py tests/test_recent_recordings_dialog.py tests/test_tray_icon.py tests/test_main_workflow.py tests/test_recorder_manager.py -q
python -m pytest tests/test_diagnostics.py tests/test_settings_dialog.py -q
python -m compileall src scripts tests
python -m ruff check .
python -m mypy
```

**硬件 smoke**：

```powershell
python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen
```

**手动验收范围**：

| 编号 | 场景 | 结论要求 |
| --- | --- | --- |
| V15-A1 | 全屏录制 3 秒并播放 | 无自绘光标写入，视频可播放 |
| V15-A2 | 区域录制 3 秒并播放 | 无自绘光标写入，视频可播放 |
| V15-A3 | 窗口录制 3 秒并播放 | 无自绘光标写入，视频可播放 |
| V15-A4 | 鼠标点击高亮 | 屏幕可见高亮，视频不额外写入高亮动画 |
| V15-H1 | 录制成功写入历史 | 最近录制列表出现新记录 |
| V15-H2 | 超过 50 条裁剪 | 只保留最近 50 条 |
| V15-H3 | 打开文件 | 默认播放器打开 MP4 |
| V15-H4 | 打开目录 | 资源管理器定位到文件目录 |
| V15-H5 | 复制路径 | 剪贴板包含文件路径 |
| V15-H6 | 文件缺失 | UI 显示文件已移动或删除 |
| V15-H7 | 从列表移除 | JSON 和 UI 中均移除该记录 |
| V15-H8 | 空状态 | 显示暂无录制记录 |
| V15-H9 | 历史写入失败 | 视频仍保存成功，日志记录失败 |
| V15-S1 | WGC spike | 有研究记录，dxcam 默认链路不受影响 |
| V15-P1 | 原型同步 | Full 原型包含最近录制 / 素材入库入口 |

---

## 3. 风险与回退

| 风险 | 等级 | 处理策略 | 回退方式 |
| --- | --- | --- | --- |
| 自绘光标移除影响帧处理 | 中 | 只改输出帧准备链路，保留尺寸缩放逻辑 | 回退 `_prepare_frame_for_encoding` 的光标相关改动 |
| 历史写入阻塞保存 | 高 | 写入失败必须捕获并降级为日志 | 保留视频保存，禁用历史写入入口 |
| JSON 半写入或损坏 | 中 | 临时文件 + 原子替换；解析失败降级 | 忽略损坏文件并显示加载失败 |
| 最近录制 UI 误扩成工作台 | 中 | 只做最近列表和四个操作 | 延后项目库、剪辑、导出队列 |
| WGC spike 影响主链路 | 高 | spike 与默认链路隔离 | 删除试验接入，仅保留研究文档 |
| Lite 范围被误改 | 高 | 开发只在 Full 工作区进行 | 回退 Lite 相关改动 |

---

## 4. 开发纪律

- 每完成 `progress.md` 中一个最小任务，应同步更新对应 checkbox。
- `progress.md` 只记录状态，不写开发日志、bug 修复流水或排查过程。
- 如实现中发现真实 bug，写入独立 bugfix/dev-log，不写入 progress 主体。
- 不新增需求，不扩展完整工作台，不改 Lite 范围。
- 自动化通过后再进入打包和 GUI 手动验收。
