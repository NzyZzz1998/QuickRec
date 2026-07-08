# QuickRec Lite v0 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 QuickRec v1.4 稳定发布基线，推进 QuickRec Lite v0。Lite v0 只保留全屏录制作为用户可见录制模式，固定原生分辨率与 60fps，保留无声 / 系统声音 / 麦克风 / 两者都有四种音频模式，沿用现有轻量窗口与托盘入口，移除区域录制、窗口录制、鼠标点击高亮、录制倒计时和相关设置入口。体积目标低于 200MB，但不作为发布阻断项。

**Architecture:** 沿用 QuickRec v1.4 架构。`main.py` 继续作为应用装配入口，`ConfigManager` 负责配置默认值与持久化，`RecorderManager` / `RecordingWorkflow` 负责录制生命周期，`ScreenCapturer` + `VideoEncoder` + `AudioCapturer` 负责捕获、编码和音频混流，`tray_icon.py` / `settings_dialog.py` / `toolbar.py` 承接用户入口与录制反馈。Lite v0 不重写核心录制架构，优先裁剪用户可见入口和设置项。

**Tech Stack:** Python 3.12 / PyQt5 / dxcam / OpenCV / FFmpeg / soundcard / pyaudio / pystray / pynput / winotify / PyInstaller / pytest / ruff / mypy

**项目路径:** `E:\codex\QuickRec\`

---

## 当前实施口径（2026-07-08）

本实施计划以 [PRD-QuickRec-Lite.md](PRD-QuickRec-Lite.md) 为需求基线。后续如需变更 Lite v0 范围，必须先更新 PRD，再更新本实施计划。

### 分支策略

QuickRec 后续按 Full 与 Lite 两条产品线拆分分支：

| 分支 | 用途 |
|------|------|
| `master` | QuickRec Full 正式主线 |
| `test` | QuickRec Full 测试 / 开发线 |
| `lite-master` | QuickRec Lite 正式主线 |
| `lite-test` | QuickRec Lite 测试 / 开发线 |

当前已有 `lite` 分支仅作为过渡分支使用。Lite v0 开发目标分支为 `lite-test`，验收通过后合并到 `lite-master`。本计划不要求立即执行分支调整；分支创建与过渡作为 Task LITE-0 的第一步。

### 当前实施边界

- Lite v0 只做用户可见能力裁剪和轻量发布收口，不改 Full 的 `master` / `test` 发布内容。
- Lite v0 不删除区域录制和窗口录制底层代码，只移除入口、快捷键配置和用户可见路径。
- Lite v0 固定原生分辨率和 60fps，不暴露画质和帧率设置。
- Lite v0 保留四种音频模式，不为了轻量化移除系统声、麦克风或双音频。
- Lite v0 移除鼠标点击高亮和录制倒计时。
- Lite v0 允许尝试体积优化，但低于 200MB 不是阻断验收。
- README 与 release notes 在发布收口阶段更新。

---

## 0. 通用项目结构与架构约束

### 0.1 当前 v1.4 到 Lite v0 的差异基线

| 模块 | 当前 v1.4 状态 | Lite v0 目标 | 处理方式 |
|------|----------------|--------------|----------|
| 全屏录制 | 已完成 | 保留 | 回归验证 |
| 区域录制 | 已完成 | 用户入口移除 | 不删底层代码 |
| 窗口录制 | 已完成 | 用户入口移除 | 不删底层代码 |
| 音频 | 四模式 | 保留四模式 | 回归验证 |
| 画质 | 原生 / 高 / 中 / 低 | 固定原生 | UI 隐藏或固定配置 |
| 帧率 | 30 / 60 | 固定 60 | UI 隐藏或固定配置 |
| 倒计时 | 可选 | 移除 | UI 与运行路径收敛 |
| 鼠标高亮 | 可选 | 移除 | UI 与运行路径收敛 |
| 托盘 | 全屏 / 区域 / 窗口 | 只保留全屏录制 | 菜单裁剪 |
| 快捷键 | 开始 / 停止 / 暂停 / 区域 / 窗口 | 开始 / 停止 / 暂停 | 设置项裁剪 |
| 打包体积 | v1.4 稳定包约 257.89MB | 目标低于 200MB | 优化尝试，不阻断 |

### 0.2 架构约束

- `ConfigManager` 仍是配置默认值、读写和旧配置兼容入口。
- `main.py` 仍是托盘、快捷键、设置、录制流程的应用装配入口。
- `RecorderManager` / `RecordingWorkflow` 仍承接录制状态流，不为了 Lite v0 重写核心录制生命周期。
- `ScreenCapturer`、`VideoEncoder`、`AudioCapturer` 的稳定链路优先保留。
- `tray_icon.py`、`settings_dialog.py`、`main.py` 是 Lite v0 用户入口裁剪重点。
- `area_selector.py`、`window_selector.py`、`window_highlighter.py`、窗口录制相关 recorder 代码 v0 暂不删除。
- 不新增 Full 工作台、历史、素材、轻编辑、导出队列、质量诊断中心等能力。
- 不使用外置 FFmpeg 作为体积优化方案；发布产物仍应是单目录可运行形态。

### 0.3 验证约束

每个会影响用户入口、配置、录制状态或打包依赖的任务都必须至少完成对应自动化测试或手动验证说明。发布前必须执行：

```powershell
python -m compileall src scripts tests
python -m ruff check .
python -m mypy
python -m pytest -q
```

真实录制能力必须通过打包产物手动验证，覆盖全屏 + 无声、全屏 + 系统声音、全屏 + 麦克风、全屏 + 两者都有。

---

## 1. Lite v0 实施计划

### Task LITE-0: 建立 Lite 分支与文档基线

**Files:**
- No code change
- Verify: `doc/lite/PRD-QuickRec-Lite.md`
- Verify/Create: `doc/lite/implementation-plan-lite.md`

- [ ] **Step 1: 创建 Lite 正式分支**

从当前 v1.4 / `lite` 过渡基线创建 `lite-master`。该分支作为 QuickRec Lite 正式主线，不直接承接日常开发。

建议命令：

```powershell
git switch lite
git branch lite-master
```

如果远端已有同名分支，先检查远端指向，不得强制覆盖。

- [ ] **Step 2: 创建 Lite 测试分支**

从 `lite-master` 创建 `lite-test`，后续 Lite v0 开发在 `lite-test` 上进行。

```powershell
git switch lite-master
git switch -c lite-test
```

- [ ] **Step 3: 明确 Full / Lite 分支隔离**

记录并遵守：

```text
master/test      -> QuickRec Full
lite-master/lite-test -> QuickRec Lite
```

Lite v0 期间不得把裁剪入口、Lite 文案、Lite 打包设置直接推入 Full 的 `master` / `test`。

- [ ] **Step 4: 验证分支基线**

确认 `lite-master`、`lite-test` 起点均来自 v1.4 稳定基线。

```powershell
git log --oneline -5
git branch --show-current
```

预期：`lite-test` 当前 HEAD 包含 v1.4 稳定发布内容和 Lite PRD / implementation plan 文档。

---

### Task LITE-1: 收敛配置默认值与旧配置兼容

**Files:**
- Modify: `src/config.py`
- Modify/Test: `tests/test_v1_2.py`
- Modify/Test: `tests/test_main_workflow.py`
- Modify/Test if needed: `tests/test_recorder_manager.py`

- [ ] **Step 1: 固定 Lite 默认帧率**

将 Lite v0 默认帧率固定为 `60`。如果仍保留底层 `fps` 配置项，应在 Lite UI 中隐藏该配置，运行路径使用固定值或默认值 `60`。

实现要求：

- 新配置默认 `fps=60`。
- 旧配置中存在 `fps=30` 时，Lite v0 是否强制覆盖为 60 需要在实现中保持一致；推荐运行时以 Lite 固定值为准，避免旧配置改变 Lite 行为。

- [ ] **Step 2: 固定 Lite 默认画质**

将 Lite v0 默认画质固定为 `native`。设置窗口不再暴露原生 / 高 / 中 / 低选择。

预期：

- 全屏录制使用主显示器原生分辨率。
- 不因旧配置中的 `quality=high/medium/low` 导致 Lite v0 降采样。

- [ ] **Step 3: 保留音频源四模式**

确认 `audio_source` 仍支持：

```text
none / system / microphone / both
```

不得为了 Lite v0 体积或简化移除系统声、麦克风或双音频模式。

- [ ] **Step 4: 固定倒计时与鼠标高亮为关闭**

Lite v0 不再暴露倒计时和鼠标高亮。配置层可以保留字段以兼容旧配置，但运行路径必须等效于：

```text
show_countdown = false
mouse_highlight = false
```

- [ ] **Step 5: 保留开机自启默认关闭**

`auto_start` 保留，默认值仍为 `false`。设置窗口继续允许用户开启或关闭。

- [ ] **Step 6: 更新配置测试**

更新或新增测试，覆盖：

- Lite 默认 `fps=60`。
- Lite 默认 `quality=native`。
- 音频四模式仍可保存和读取。
- 旧配置缺字段时仍能合并默认值。
- 旧配置包含区域/窗口快捷键时不影响 Lite v0 可用性。

- [ ] **Step 7: 验证**

```powershell
python -m pytest tests/test_v1_2.py tests/test_main_workflow.py -q
```

---

### Task LITE-2: 裁剪设置窗口

**Files:**
- Modify: `src/ui/settings_dialog.py`
- Modify/Test: `tests/test_main_workflow.py`
- Modify/Test if exists: settings dialog related tests

- [ ] **Step 1: 移除画质选择控件**

设置窗口不再展示画质选择。不得出现：

```text
原生 / 高 / 中 / 低
```

如果底层仍保留 `quality` 字段，保存设置时不要将隐藏控件的旧值写回为非 `native`。

- [ ] **Step 2: 移除帧率选择控件**

设置窗口不再展示 30 / 60 帧率选择。Lite v0 固定 60fps。

- [ ] **Step 3: 移除区域录制快捷键设置**

设置窗口不再展示区域录制快捷键，也不再允许用户修改 `shortcut_area`。

- [ ] **Step 4: 移除窗口录制快捷键设置**

设置窗口不再展示窗口录制快捷键，也不再允许用户修改 `shortcut_window`。

- [ ] **Step 5: 移除录制倒计时设置**

设置窗口不再展示倒计时开关或倒计时秒数。

- [ ] **Step 6: 移除鼠标高亮设置**

设置窗口不再展示鼠标点击高亮开关。

- [ ] **Step 7: 保留 Lite v0 设置项**

设置窗口必须保留：

- 保存路径。
- 音频源四模式。
- 开始 / 停止 / 暂停快捷键。
- 开机自启。
- 保存 / 取消。

- [ ] **Step 8: 验证设置保存与加载**

验证：

- 打开设置窗口不报错。
- 保存路径可修改。
- 音频源可修改。
- 开始 / 停止 / 暂停快捷键可修改。
- 开机自启状态可保存。
- 不再出现区域、窗口、画质、帧率、倒计时、鼠标高亮入口。

建议测试命令：

```powershell
python -m pytest tests/test_main_workflow.py -q
```

---

### Task LITE-3: 裁剪托盘菜单和主入口

**Files:**
- Modify: `src/ui/tray_icon.py`
- Modify: `src/main.py`
- Modify/Test: `tests/test_main_workflow.py`
- Modify/Test: `tests/test_hotkey_manager.py`

- [ ] **Step 1: 托盘空闲菜单只保留全屏录制**

空闲托盘菜单应只提供：

```text
全屏录制
设置
打开保存文件夹
退出
```

不得展示区域录制和窗口录制。

- [ ] **Step 2: 移除区域录制入口绑定**

`main.py` 不再从托盘、主窗口或快捷键暴露区域录制入口。底层 `_on_start_region` 等代码可以暂时保留，但不得成为 Lite v0 用户可触达路径。

- [ ] **Step 3: 移除窗口录制入口绑定**

`main.py` 不再从托盘、主窗口或快捷键暴露窗口录制入口。底层窗口选择和窗口录制代码可以暂时保留。

- [ ] **Step 4: 保留录制中菜单**

录制中托盘菜单继续保留：

```text
暂停/继续
停止录制
退出
```

不得因为裁剪区域/窗口入口影响录制中状态切换。

- [ ] **Step 5: 裁剪快捷键注册**

全局快捷键只注册：

```text
shortcut_start
shortcut_stop
shortcut_pause
```

不注册区域录制快捷键和窗口录制快捷键。

- [ ] **Step 6: 验证**

自动化测试覆盖：

- 空闲菜单不包含区域录制。
- 空闲菜单不包含窗口录制。
- 开始 / 停止 / 暂停快捷键仍有效。
- 区域 / 窗口快捷键不会触发录制。

建议测试命令：

```powershell
python -m pytest tests/test_hotkey_manager.py tests/test_main_workflow.py -q
```

---

### Task LITE-4: 停用倒计时与鼠标高亮运行路径

**Files:**
- Modify: `src/main.py`
- Modify if needed: `src/ui/click_highlighter.py`
- Modify/Test: `tests/test_main_workflow.py`
- Modify/Test: `tests/test_v1_2.py`

- [ ] **Step 1: 开始录制不进入倒计时流程**

Lite v0 点击开始录制后直接进入全屏录制流程，不再进入倒计时工具栏状态。

如果倒计时代码保留，应确保 Lite v0 没有用户入口和运行路径会调用它。

- [ ] **Step 2: 不启动 ClickHighlighter**

Lite v0 不启动鼠标点击高亮监听器。即使旧配置中 `mouse_highlight=true`，运行时也不得启用点击高亮。

- [ ] **Step 3: 保留底层文件**

不要在 v0 中删除 `click_highlighter.py` 或倒计时相关工具栏底层代码，避免大规模删除引入风险。后续 Lite v0.1 再评估删除或隔离。

- [ ] **Step 4: 验证直接录制**

验证：

- 点击全屏录制后不会显示倒计时。
- 不会启动鼠标点击高亮效果。
- 全屏录制仍可开始、暂停、恢复、停止。

建议测试命令：

```powershell
python -m pytest tests/test_main_workflow.py tests/test_v1_2.py -q
```

---

### Task LITE-5: 全屏录制和四种音频模式回归

**Files:**
- Modify if needed: `src/recorder/recorder_manager.py`
- Modify if needed: `src/recorder/audio_preflight.py`
- Modify if needed: `src/recorder/audio_capturer.py`
- Modify/Test: `tests/test_recorder_manager.py`
- Modify/Test: `tests/test_audio_preflight.py`
- Verify: `scripts/hardware_smoke.py`

- [ ] **Step 1: 确认全屏录制入口只走 fullscreen**

Lite v0 用户可见入口只能调用全屏录制。区域和窗口录制底层能力可以存在，但不应被 UI 或快捷键触发。

- [ ] **Step 2: 确认原生分辨率与 60fps**

录制配置应满足：

```text
quality = native
fps = 60
```

如果 `ScreenCapturer` 仍存在 `target_fps=60`，需要确认与 Lite 固定 60fps 的设计一致。

- [ ] **Step 3: 回归无声录制**

验证无声模式输出 MP4 可播放，包含视频流。

- [ ] **Step 4: 回归系统声音录制**

验证系统声音模式输出 MP4 可播放，并包含系统音频。

- [ ] **Step 5: 回归麦克风录制**

验证麦克风模式输出 MP4 可播放，并包含麦克风声音。

- [ ] **Step 6: 回归双音频录制**

验证系统声音 + 麦克风模式输出 MP4 可播放，并包含混合音频。

- [ ] **Step 7: 回归暂停/恢复/停止保存**

验证暂停期间画面停止推进，恢复后继续录制，停止后 Toast 和结果条出现。

- [ ] **Step 8: 自动化验证**

```powershell
python -m pytest tests/test_recorder_manager.py tests/test_audio_preflight.py -q
```

- [ ] **Step 9: 本地硬件冒烟**

```powershell
python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen
```

如果脚本暂不支持音频模式参数，手动使用打包产物覆盖四种音频模式。

---

### Task LITE-6: 更新自动化测试与质量门槛

**Files:**
- Modify: `tests/test_main_workflow.py`
- Modify: `tests/test_hotkey_manager.py`
- Modify: `tests/test_recorder_manager.py`
- Modify: `tests/test_v1_2.py`
- Modify if needed: `tests/test_packaging_config.py`
- Modify if needed: `pyproject.toml`

- [ ] **Step 1: 更新入口裁剪测试**

测试应表达 Lite v0 产品边界：

- 不再要求托盘有区域录制入口。
- 不再要求托盘有窗口录制入口。
- 不再要求设置窗口有区域 / 窗口快捷键。
- 不再要求设置窗口有倒计时和鼠标高亮。

- [ ] **Step 2: 更新配置默认值测试**

覆盖：

- `fps=60`。
- `quality=native`。
- `audio_source` 四模式可用。
- `auto_start=false`。
- 旧配置兼容。

- [ ] **Step 3: 更新主流程测试**

覆盖：

- Lite 全屏录制入口可用。
- 区域 / 窗口入口不可触达。
- 开始 / 暂停 / 停止状态流不回退。
- 保存完成事件和结果条不回退。

- [ ] **Step 4: 更新打包配置测试**

如果 Lite v0 修改 `build_std.spec` 或新增 Lite 打包 spec，应补充测试确认：

- FFmpeg 仍被包含。
- 必要音频依赖仍被包含。
- 不需要的入口依赖被排除时不会破坏启动。

- [ ] **Step 5: 执行质量门槛**

```powershell
python -m compileall src scripts tests
python -m ruff check .
python -m mypy
python -m pytest -q
```

所有命令通过后才进入打包收口。

---

### Task LITE-7: 打包与体积优化尝试

**Files:**
- Modify if needed: `build_std.spec`
- Modify if needed: `requirements.txt`
- Modify if needed: `scripts/package_size_report.py`
- Add: `doc/lite/lite-v0-package-size-report.md`

- [ ] **Step 1: 建立 Lite v0 打包基线**

先使用稳定方案打包，记录未优化前体积。

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm
```

- [ ] **Step 2: 生成体积报告**

新增 `doc/lite/lite-v0-package-size-report.md`，记录：

- 产物路径。
- 总体积。
- FFmpeg 体积。
- OpenCV / cv2 体积。
- PyQt5 体积。
- NumPy / Python runtime 体积。
- 其他主要依赖体积。

- [ ] **Step 3: 尝试 PyInstaller excludes**

评估是否可以继续排除 Lite v0 不需要的 Qt 模块、插件、PIL 编解码器或历史功能相关资源。

每次变更必须记录：

- 改动内容。
- 体积变化。
- 自动化测试结果。
- 打包启动结果。

- [ ] **Step 4: 尝试 FFmpeg 体积方案**

允许尝试更小 FFmpeg 构建或 FFmpeg 压缩方案，但不得外置 FFmpeg。必须记录：

- 方案来源。
- 体积变化。
- H.264 编码结果。
- 四种音频模式混流结果。
- 杀软误报或启动风险。

- [ ] **Step 5: 尝试 OpenCV / headless 方案**

允许评估 `opencv-python-headless` 或 dxcam 处理器替代方案。必须先确认不会复现 v1.4 中移除 cv2 导致 dxcam 捕获失败的问题。

- [ ] **Step 6: 每次体积尝试后回归**

每个体积优化尝试后至少执行：

```powershell
python -m pytest -q
python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen
```

并手动验证四种音频模式。

- [ ] **Step 7: 体积目标处理**

如果低于 200MB：

- 记录达成方案。
- 将该方案作为 Lite v0 发布候选。

如果未低于 200MB：

- 不阻断 Lite v0 发布。
- 在 `doc/lite/lite-v0-package-size-report.md` 中记录未达标原因和下一步方案。

---

### Task LITE-8: README、release notes 与发布收口

**Files:**
- Modify: `README.md`
- Add: `doc/lite/release-notes-lite-v0.md`
- Modify: `doc/lite/implementation-plan-lite.md` if final status needs update

- [ ] **Step 1: 更新 README**

README 需要说明 Lite v0：

- 当前分支 / 版本定位。
- 只保留全屏录制。
- 固定原生分辨率和 60fps。
- 保留四种音频模式。
- 不包含区域录制、窗口录制、倒计时和鼠标高亮。
- 打包体积目标与实际结果。
- 运行、测试、打包命令。

- [ ] **Step 2: 编写 release notes**

新增 `doc/lite/release-notes-lite-v0.md`，包含：

- 版本定位。
- 新增 / 保留能力。
- 移除 / 不包含能力。
- 已知限制。
- 验证结果。
- 打包产物路径和体积。
- 分支、commit、tag 信息。

- [ ] **Step 3: 发布前完整验证**

执行：

```powershell
python -m compileall src scripts tests
python -m ruff check .
python -m mypy
python -m pytest -q
python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen
```

手动验证：

- 全屏 + 无声。
- 全屏 + 系统声音。
- 全屏 + 麦克风。
- 全屏 + 两者都有。
- 暂停 / 恢复 / 停止。
- Toast 和结果条。
- 打开文件 / 打开文件夹。

- [ ] **Step 4: lite-test 合并 lite-master**

验收通过后，将 `lite-test` 合并到 `lite-master`。不得合并到 Full 的 `master` 或 `test`。

推荐流程：

```powershell
git switch lite-master
git merge --no-ff lite-test
```

- [ ] **Step 5: 准备 Lite v0 tag**

tag 建议命名：

```text
lite-v0
```

如果已有同名 tag，必须先确认是否需要覆盖，不得默认强制更新。

---

## 2. PRD 对照表

| PRD 编号 | PRD 能力 | 实施任务 |
|---------|----------|----------|
| LF1 | 全屏录制 | LITE-3, LITE-5 |
| LF2 | 区域录制移除入口 | LITE-2, LITE-3, LITE-6 |
| LF3 | 窗口录制移除入口 | LITE-2, LITE-3, LITE-6 |
| LF4-LF7 | 四种音频模式 | LITE-1, LITE-5 |
| LF8 | 开始/暂停/恢复/停止 | LITE-3, LITE-5 |
| LF9 | 鼠标点击高亮移除 | LITE-2, LITE-4, LITE-6 |
| LF10 | 倒计时移除 | LITE-2, LITE-4, LITE-6 |
| LE1 | H.264 实时编码 | LITE-5, LITE-7 |
| LS1-LS7 | 保存和输出 | LITE-5, LITE-8 |
| LK1-LK4 | 开始/暂停/停止快捷键 | LITE-2, LITE-3, LITE-6 |
| LK5-LK6 | 区域/窗口快捷键移除 | LITE-2, LITE-3, LITE-6 |
| LP1 | 保存路径设置 | LITE-2, LITE-5 |
| LP2 | 固定原生分辨率 | LITE-1, LITE-2, LITE-5 |
| LP3 | 固定 60fps | LITE-1, LITE-2, LITE-5 |
| LP4 | 音频源选择 | LITE-1, LITE-2, LITE-5 |
| LP5 | 快捷键设置收敛 | LITE-2, LITE-3 |
| LP6 | 开机自启 | LITE-1, LITE-2, LITE-8 |
| LP7-LP8 | 倒计时/高亮设置移除 | LITE-2, LITE-4 |
| LP9 | 磁盘空间预警 | LITE-5 |
| LQ1-LQ5 | 工程与发布能力 | LITE-6, LITE-7, LITE-8 |

---

## 3. Lite v0 必须完成项

- [ ] 创建或确认 `lite-master` / `lite-test` 分支策略。
- [ ] Lite v0 开发在 `lite-test` 上完成。
- [ ] 不修改 Full `master` / `test` 发布内容。
- [ ] 设置窗口只保留 Lite v0 设置项。
- [ ] 托盘和主入口只保留全屏录制。
- [ ] 开始 / 停止 / 暂停快捷键可用。
- [ ] 区域录制入口不可见。
- [ ] 窗口录制入口不可见。
- [ ] 区域 / 窗口快捷键设置不可见。
- [ ] 鼠标点击高亮不可见且不启动。
- [ ] 倒计时不可见且不进入运行路径。
- [ ] 全屏录制固定原生分辨率。
- [ ] 全屏录制固定 60fps。
- [ ] 四种音频模式可用。
- [ ] Toast 和结果条可用。
- [ ] 自动化质量门槛通过。
- [ ] 打包产物可启动。
- [ ] 打包产物完成真实手动录制验收。
- [ ] 体积报告完成。
- [ ] README 和 release notes 更新。

---

## 4. 明确不进入 Lite v0 的内容

- 区域录制用户入口。
- 窗口录制用户入口。
- 区域录制快捷键设置。
- 窗口录制快捷键设置。
- 鼠标点击高亮。
- 录制倒计时。
- 90fps / 120fps / 144fps 等高帧率实验。
- 多显示器选择。
- 录制历史。
- 项目素材管理。
- 轻编辑。
- 导出队列。
- 质量诊断中心。
- 模板与预设。
- Full 创作者工作台。
- 为了体积目标外置 FFmpeg。
- 为了体积目标破坏 dxcam / cv2 稳定捕获链路。

---

## 5. 风险控制与回退要求

| 风险 | 必须执行的回退或处理 |
|------|----------------------|
| Lite 改动误入 Full `master` / `test` | 停止合并，回到分支策略检查，只允许 Lite 改动进入 `lite-test` / `lite-master` |
| 固定 60fps 导致低性能机器压力过高 | v0 记录为已知限制，不临时恢复帧率设置；后续版本再评估降档策略 |
| 固定原生分辨率导致 4K 机器压力过高 | v0 记录为已知限制，不临时恢复画质设置；后续根据反馈评估 |
| 旧配置中的 30fps / 非原生画质影响 Lite 行为 | 在配置读取或运行路径中强制 Lite 固定值 |
| 移除入口时误删底层区域/窗口代码 | 回退删除，只保留入口裁剪 |
| 倒计时仍被运行路径触发 | 回到 `main.py` 启动流程，确保 Lite 开始录制直接进入全屏 |
| 鼠标高亮仍启动监听 | 回到启动流程和配置读取，确保 Lite 不启动 ClickHighlighter |
| 音频双路混流失败生成不可播放文件 | 恢复 v1.4 音频自检与降级策略，阻断发布直到输出可播放 |
| 体积优化破坏 dxcam 捕获 | 回退该优化，恢复稳定依赖 |
| FFmpeg 压缩或替换导致播放/杀软问题 | 回退到稳定 FFmpeg，记录为未采用方案 |
| 未低于 200MB | 不阻断发布，但必须记录原因、尝试项和后续方案 |
| 测试仍要求区域/窗口入口存在 | 更新测试表达 Lite v0 PRD，不保留 Full 入口期望 |
| README / release notes 与实际能力不一致 | 发布前阻断，先修文档再 tag |

---

## 6. Lite v0 完成定义

Lite v0 只有在以下条件全部满足后才能进入 tag 准备：

- [ ] `doc/lite/PRD-QuickRec-Lite.md` 与实际实现一致。
- [ ] `doc/lite/implementation-plan-lite.md` 与实际执行结果无明显冲突。
- [ ] `lite-test` 完成本计划所有必须任务。
- [ ] 区域录制和窗口录制用户入口已移除。
- [ ] 区域录制和窗口录制快捷键设置已移除。
- [ ] 鼠标点击高亮入口和运行路径已停用。
- [ ] 录制倒计时入口和运行路径已停用。
- [ ] 设置窗口只展示 Lite v0 允许的设置项。
- [ ] 托盘空闲菜单只展示全屏录制、设置、打开保存文件夹、退出。
- [ ] 全屏录制以原生分辨率和 60fps 输出。
- [ ] 无声、系统声音、麦克风、两者都有四种模式均通过真实验证。
- [ ] 暂停、恢复、停止、保存流程通过真实验证。
- [ ] Toast、结果条、打开文件、打开文件夹通过真实验证。
- [ ] `python -m compileall src scripts tests` 通过。
- [ ] `python -m ruff check .` 通过。
- [ ] `python -m mypy` 通过。
- [ ] `python -m pytest -q` 通过。
- [ ] `python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen` 通过。
- [ ] PyInstaller 打包成功。
- [ ] 打包产物启动成功。
- [ ] `doc/lite/lite-v0-package-size-report.md` 完成。
- [ ] README 已更新 Lite v0 口径。
- [ ] `doc/lite/release-notes-lite-v0.md` 完成。
- [ ] 体积低于 200MB，或已记录未达标原因且确认不阻断发布。
- [ ] `lite-test` 合并到 `lite-master`。
- [ ] 准备 tag `lite-v0`，且 tag 指向已验收提交。
