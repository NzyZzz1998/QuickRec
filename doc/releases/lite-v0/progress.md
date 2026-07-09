# QuickRec Lite v0 总体进度

> 本文档作为 QuickRec Lite 产品线的独立总体进度跟踪，按 Lite v0 模块组织 Vibe Coding 最小可执行任务。每个模块对应一组 checklist，完成时勾选。完整需求见 `PRD-QuickRec-Lite.md`，实施步骤见 `implementation-plan-lite.md`。开发过程流水记录单独维护在 `development-log-lite.md`。

**最后更新**: 2026-07-08  
**当前阶段**: QuickRec Lite v0 手动验证完成 / 待打包与发布收口  
**当前分支口径**: `master` / `test` 仅用于 QuickRec Full；Lite 后续使用 `lite-master` / `lite-test`。当前已有 `lite` 分支为过渡分支。  
**当前里程碑**: Lite v0 已在 `lite-test` 完成首轮入口裁剪、配置收敛、自动化验证、硬件冒烟、设置窗口 Computer Use 验证和人工手动验证。下一步进入打包体积记录、README / release notes 与发布收口。

---

## 当前文档同步进度（2026-07-08）

- [x] 新增 Lite 独立文档目录 `doc/lite/`。
- [x] 新增 `doc/lite/PRD-QuickRec-Lite.md`。
- [x] 新增 `doc/lite/implementation-plan-lite.md`。
- [x] 主 PRD `doc/PRD-QuickRec.md` 已追加 Lite v0 摘要并链接 Lite PRD。
- [x] 明确 Lite v0 不是 Full 的免费版、低配模式或运行时功能开关。
- [x] 明确 Lite v0 只保留全屏录制作为用户可见录制模式。
- [x] 明确 Lite v0 固定原生分辨率和 60fps。
- [x] 明确 Lite v0 保留无声 / 系统声音 / 麦克风 / 两者都有四种音频模式。
- [x] 明确 Lite v0 移除区域录制、窗口录制、鼠标点击高亮和录制倒计时入口。
- [x] 明确 Lite v0 体积目标低于 200MB，但不作为发布阻断验收。
- [x] 新增 Lite 独立进度文档 `doc/lite/progress.md`。
- [x] 新增 Lite 独立开发日志 `doc/lite/development-log-lite.md`。
- [x] 创建或确认 `lite-master` / `lite-test` 分支。
- [x] 将 Lite v0 开发切换到 `lite-test`。

---

## 版本总览

| 版本 | 阶段 | 平台 | 状态 |
|------|------|------|------|
| Lite v0 | 轻量全屏录制基线 | Windows 10 / 11 | 手动验证完成 / 待打包 |
| Lite v0.1 | 体积与依赖继续收敛 | Windows 10 / 11 | 未开始 |
| Lite v1.0 | Lite 稳定发布线 | Windows 10 / 11 | 未开始 |

---

## Lite v0 总体进度概览

| 里程碑 | 模块 | 状态 | 完成度 |
|--------|------|------|--------|
| **LITE-0** | 分支与文档基线 | 已完成 | 10/10 |
| **LITE-1** | 配置默认值与旧配置兼容 | 已完成 | 15/15 |
| **LITE-2** | 设置窗口裁剪 | 已完成 | 18/18 |
| **LITE-3** | 托盘菜单和主入口裁剪 | 已完成 | 18/18 |
| **LITE-4** | 倒计时与鼠标高亮停用 | 已完成 | 10/10 |
| **LITE-5** | 全屏录制和四种音频模式回归 | 手动验证完成 | 20/22 |
| **LITE-6** | 自动化测试与质量门槛 | 已通过首轮门槛 | 18/20 |
| **LITE-7** | 打包与体积优化尝试 | 稳定包完成 / 体积未达标但不阻断 | 17/24 |
| **LITE-8** | README / release notes / 发布收口 | 文档完成 / 待合并 tag | 14/18 |

**Lite v0 总进度**: 140/155 任务完成。当前已完成源码应用快捷键录制、硬件冒烟、设置窗口 Computer Use 验证、四种音频模式验证、用户手动补验、PyInstaller 打包、打包产物验证、体积报告、README 和 release notes；仅剩 `lite-test` 合并到 `lite-master`、tag 和推送收口。

---

## 当前开发执行进度（2026-07-08）

- [x] 已从 v1.4 稳定基线创建 `lite-master`。
- [x] 已从 `lite-master` 创建并切换到 `lite-test`。
- [x] `src/config.py` 默认输出收敛为 `quality=native`、`fps=60`。
- [x] `src/recorder/recorder_manager.py` 实际录制启动链路强制使用原生分辨率和 60fps，避免旧配置继续降采样或 30fps 输出。
- [x] `src/ui/settings_dialog.py` 移除画质、帧率、区域录制快捷键、窗口录制快捷键、倒计时和鼠标高亮设置入口。
- [x] `src/ui/tray_icon.py` 空闲菜单仅保留全屏录制、设置、打开保存文件夹和退出。
- [x] `src/main.py` 只注册开始、停止、暂停/恢复三组快捷键。
- [x] `src/main.py` 旧配置 `show_countdown=true` 不再触发倒计时。
- [x] `src/main.py` 旧配置 `mouse_highlight=true` 不再启动鼠标点击高亮。
- [x] 自动化测试已更新并通过：`python -m pytest -q`。
- [x] 编译检查已通过：`python -m compileall src scripts tests`。
- [x] Ruff 已通过：`python -m ruff check .`。
- [x] mypy 已通过：`python -m mypy`。
- [x] 真实硬件冒烟：`python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen`。
- [x] 真实手动验证：无声 / 系统声音 / 麦克风 / 两者都有四种音频模式。
- [x] 真实手动验证：开始、暂停、恢复、停止、保存、Toast、结果条、打开文件、打开文件夹。
- [x] 打包产物生成与体积记录。

---

## LITE-0. 分支与文档基线

### 模块 0.1: Lite 分支策略

- [x] 0.1.1 确认当前过渡分支 `lite` 指向 v1.4 稳定基线。
- [x] 0.1.2 从当前 Lite 过渡基线创建 `lite-master`。
- [x] 0.1.3 从 `lite-master` 创建 `lite-test`。
- [x] 0.1.4 确认 `master` / `test` 仅作为 QuickRec Full 分支使用。
- [x] 0.1.5 确认 Lite v0 日常开发只进入 `lite-test`。
- [x] 0.1.6 确认 Lite v0 验收后再合并到 `lite-master`。

### 模块 0.2: Lite 文档基线

- [x] 0.2.1 Review `doc/lite/PRD-QuickRec-Lite.md`，确认需求无冲突。
- [x] 0.2.2 Review `doc/lite/implementation-plan-lite.md`，确认实施任务可执行。
- [x] 0.2.3 确认 `doc/lite/progress.md` 与 PRD / implementation plan 对齐。
- [x] 0.2.4 在 `doc/lite/development-log-lite.md` 记录分支创建结果。

---

## LITE-1. 配置默认值与旧配置兼容

### 模块 1.1: 固定 Lite 默认画面参数

- [x] 1.1.1 阅读 `src/config.py` 当前默认配置。
- [x] 1.1.2 将 Lite v0 默认 `fps` 固定为 `60`。
- [x] 1.1.3 将 Lite v0 默认 `quality` 固定为 `native`。
- [x] 1.1.4 确认旧配置中的 `fps=30` 不会改变 Lite v0 固定 60fps 行为。
- [x] 1.1.5 确认旧配置中的 `quality=high/medium/low` 不会导致 Lite v0 降采样。

### 模块 1.2: 音频和系统配置保留

- [x] 1.2.1 确认 `audio_source=none` 保留。
- [x] 1.2.2 确认 `audio_source=system` 保留。
- [x] 1.2.3 确认 `audio_source=microphone` 保留。
- [x] 1.2.4 确认 `audio_source=both` 保留。
- [x] 1.2.5 确认 `auto_start=false` 默认值保留。

### 模块 1.3: 裁剪项配置兼容

- [x] 1.3.1 确认 `show_countdown` 在 Lite v0 中等效固定关闭。
- [x] 1.3.2 确认 `mouse_highlight` 在 Lite v0 中等效固定关闭。
- [x] 1.3.3 确认旧配置包含 `shortcut_area` 时不影响 Lite v0 启动。
- [x] 1.3.4 确认旧配置包含 `shortcut_window` 时不影响 Lite v0 启动。
- [x] 1.3.5 补充或更新配置默认值测试。

---

## LITE-2. 设置窗口裁剪

### 模块 2.1: 移除画面相关设置

- [x] 2.1.1 阅读 `src/ui/settings_dialog.py` 当前控件结构。
- [x] 2.1.2 移除画质选择控件。
- [x] 2.1.3 移除帧率选择控件。
- [x] 2.1.4 保存设置时不写回非 `native` 画质。
- [x] 2.1.5 保存设置时不写回非 `60` 帧率。

### 模块 2.2: 移除被裁剪功能设置

- [x] 2.2.1 移除区域录制快捷键设置。
- [x] 2.2.2 移除窗口录制快捷键设置。
- [x] 2.2.3 移除录制倒计时设置。
- [x] 2.2.4 移除鼠标点击高亮设置。
- [x] 2.2.5 确认设置窗口不出现 Full 引流、升级提示或置灰入口。

### 模块 2.3: 保留 Lite 必要设置

- [x] 2.3.1 保留保存路径设置。
- [x] 2.3.2 保留音频源四模式选择。
- [x] 2.3.3 保留开始快捷键设置。
- [x] 2.3.4 保留停止快捷键设置。
- [x] 2.3.5 保留暂停/恢复快捷键设置。
- [x] 2.3.6 保留开机自启设置，默认关闭。
- [x] 2.3.7 补充设置窗口裁剪测试。
- [x] 2.3.8 验证设置保存和加载不回退。

---

## LITE-3. 托盘菜单和主入口裁剪

### 模块 3.1: 托盘空闲菜单裁剪

- [x] 3.1.1 阅读 `src/ui/tray_icon.py` 当前空闲菜单结构。
- [x] 3.1.2 保留全屏录制菜单项。
- [x] 3.1.3 保留设置菜单项。
- [x] 3.1.4 保留打开保存文件夹菜单项。
- [x] 3.1.5 保留退出菜单项。
- [x] 3.1.6 移除区域录制菜单项。
- [x] 3.1.7 移除窗口录制菜单项。

### 模块 3.2: 主入口与信号绑定裁剪

- [x] 3.2.1 阅读 `src/main.py` 中全屏 / 区域 / 窗口录制入口。
- [x] 3.2.2 保留全屏录制入口绑定。
- [x] 3.2.3 移除区域录制用户可触达入口。
- [x] 3.2.4 移除窗口录制用户可触达入口。
- [x] 3.2.5 保留录制中暂停/继续入口。
- [x] 3.2.6 保留录制中停止入口。

### 模块 3.3: 快捷键注册裁剪

- [x] 3.3.1 只注册开始全屏录制快捷键。
- [x] 3.3.2 只注册停止录制快捷键。
- [x] 3.3.3 只注册暂停/恢复快捷键。
- [x] 3.3.4 不注册区域录制快捷键。
- [x] 3.3.5 不注册窗口录制快捷键。

---

## LITE-4. 倒计时与鼠标高亮停用

### 模块 4.1: 倒计时运行路径停用

- [x] 4.1.1 阅读 `main.py` 中倒计时启动流程。
- [x] 4.1.2 点击开始录制后直接进入全屏录制流程。
- [x] 4.1.3 确认倒计时 UI 不会出现。
- [x] 4.1.4 确认旧配置 `show_countdown=true` 不会触发倒计时。
- [x] 4.1.5 保留底层倒计时代码，v0 不做大规模删除。

### 模块 4.2: 鼠标点击高亮停用

- [x] 4.2.1 阅读 `click_highlighter.py` 与启动调用路径。
- [x] 4.2.2 确认 Lite v0 不启动 ClickHighlighter。
- [x] 4.2.3 确认旧配置 `mouse_highlight=true` 不会触发高亮。
- [x] 4.2.4 保留底层点击高亮代码，v0 不做大规模删除。
- [x] 4.2.5 补充倒计时和鼠标高亮停用测试。

---

## LITE-5. 全屏录制和四种音频模式回归

### 模块 5.1: 全屏录制链路

- [x] 5.1.1 确认用户可见入口只调用全屏录制。
- [x] 5.1.2 确认全屏录制使用原生分辨率。
- [x] 5.1.3 确认全屏录制使用 60fps。
- [x] 5.1.4 确认 H.264 实时编码链路可用。
- [x] 5.1.5 确认输出 MP4 可播放。

### 模块 5.2: 录制控制流程

- [x] 5.2.1 验证开始录制。
- [x] 5.2.2 验证暂停录制。
- [x] 5.2.3 验证恢复录制。
- [x] 5.2.4 验证停止保存。
- [x] 5.2.5 验证 Toast 通知。
- [x] 5.2.6 验证工具栏结果条。
- [x] 5.2.7 验证打开文件。
- [x] 5.2.8 验证打开文件夹。

### 模块 5.3: 音频模式回归

- [x] 5.3.1 验证无声录制输出可播放。
- [x] 5.3.2 验证系统声音录制输出可播放并包含系统声音。
- [x] 5.3.3 验证麦克风录制输出可播放并包含麦克风声音。
- [x] 5.3.4 验证系统声音 + 麦克风录制输出可播放并包含混合音频。
- [ ] 5.3.5 验证音频设备不可用时降级路径不生成损坏文件。
- [ ] 5.3.6 补充或更新音频自检测试。
- [x] 5.3.7 执行本地硬件冒烟。
- [x] 5.3.8 在开发日志中记录手动验证结果。
- [ ] 5.3.9 若发现音频问题，记录失败日志和复测结果。

---

## LITE-6. 自动化测试与质量门槛

### 模块 6.1: 测试期望更新

- [x] 6.1.1 更新配置默认值测试。
- [x] 6.1.2 更新设置窗口控件测试。
- [x] 6.1.3 更新托盘菜单测试。
- [x] 6.1.4 更新快捷键注册测试。
- [x] 6.1.5 更新主流程测试。
- [ ] 6.1.6 更新打包配置测试。

### 模块 6.2: Lite 边界测试

- [x] 6.2.1 测试区域录制入口不可见。
- [x] 6.2.2 测试窗口录制入口不可见。
- [x] 6.2.3 测试区域快捷键不注册。
- [x] 6.2.4 测试窗口快捷键不注册。
- [x] 6.2.5 测试倒计时入口不可见。
- [x] 6.2.6 测试鼠标高亮入口不可见。
- [x] 6.2.7 测试固定 60fps 行为。
- [x] 6.2.8 测试固定原生分辨率行为。

### 模块 6.3: 质量门槛执行

- [x] 6.3.1 执行 `python -m compileall src scripts tests`。
- [x] 6.3.2 执行 `python -m ruff check .`。
- [x] 6.3.3 执行 `python -m mypy`。
- [x] 6.3.4 执行 `python -m pytest -q`。
- [x] 6.3.5 将验证结果记录到开发日志。
- [ ] 6.3.6 所有自动化门槛通过后进入打包阶段。

---

## LITE-7. 打包与体积优化尝试

### 模块 7.1: 打包基线

- [x] 7.1.1 使用稳定 PyInstaller 配置完成 Lite v0 初始打包。
- [x] 7.1.2 记录打包产物路径。
- [x] 7.1.3 记录打包产物总体积。
- [x] 7.1.4 验证打包产物可启动。
- [x] 7.1.5 验证打包产物可全屏录制。

### 模块 7.2: 体积报告

- [x] 7.2.1 新增 `doc/lite/lite-v0-package-size-report.md`。
- [x] 7.2.2 记录 FFmpeg 体积。
- [x] 7.2.3 记录 OpenCV / cv2 体积。
- [x] 7.2.4 记录 PyQt5 体积。
- [x] 7.2.5 记录 NumPy 体积。
- [x] 7.2.6 记录 Python runtime 体积。
- [x] 7.2.7 记录 Top 大文件和 Top 大目录。

### 模块 7.3: 体积优化尝试

- [ ] 7.3.1 尝试 PyInstaller excludes 继续收敛。
- [ ] 7.3.2 尝试更小 FFmpeg 构建或压缩方案。
- [ ] 7.3.3 尝试 OpenCV headless 或替代方案评估。
- [ ] 7.3.4 每个尝试后执行自动化测试。
- [ ] 7.3.5 每个尝试后执行全屏硬件冒烟。
- [ ] 7.3.6 每个尝试后验证四种音频模式。
- [ ] 7.3.7 记录每个尝试的体积变化。
- [ ] 7.3.8 记录每个尝试的回退原因或采用原因。
- [x] 7.3.9 未低于 200MB 时记录未达标原因。
- [x] 7.3.10 确认体积未达标不阻断 Lite v0 发布。
- [x] 7.3.11 不外置 FFmpeg。
- [x] 7.3.12 不破坏 dxcam / cv2 稳定捕获链路。

---

## LITE-8. README / release notes / 发布收口

### 模块 8.1: README 更新

- [x] 8.1.1 README 标明当前为 QuickRec Lite v0。
- [x] 8.1.2 README 说明 Lite v0 只保留全屏录制。
- [x] 8.1.3 README 说明固定原生分辨率和 60fps。
- [x] 8.1.4 README 说明保留四种音频模式。
- [x] 8.1.5 README 说明不包含区域录制、窗口录制、倒计时和鼠标高亮。
- [x] 8.1.6 README 说明体积目标和实际体积。

### 模块 8.2: release notes

- [x] 8.2.1 新增 `doc/lite/release-notes-lite-v0.md`。
- [x] 8.2.2 写入版本定位。
- [x] 8.2.3 写入保留能力。
- [x] 8.2.4 写入移除能力。
- [x] 8.2.5 写入已知限制。
- [x] 8.2.6 写入验证结果。
- [x] 8.2.7 写入打包产物路径和体积。
- [ ] 8.2.8 写入分支、commit、tag 信息。

### 模块 8.3: 发布分支与 tag

- [ ] 8.3.1 确认 `lite-test` 所有必须任务完成。
- [ ] 8.3.2 确认 `lite-test` 不包含 Full 非预期改动。
- [ ] 8.3.3 将 `lite-test` 合并到 `lite-master`。
- [ ] 8.3.4 准备 `lite-v0` tag。

---

## PRD 对照表

| PRD 编号 | PRD 能力 | Progress 模块 |
|---------|----------|----------------|
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
| LP1-LP6 / LP9 | Lite 设置项保留和收敛 | LITE-1, LITE-2 |
| LP7-LP8 | 倒计时/高亮设置移除 | LITE-2, LITE-4 |
| LQ1-LQ5 | 工程与发布能力 | LITE-6, LITE-7, LITE-8 |

---

## Lite v0 必须完成项

- [ ] `lite-master` / `lite-test` 分支策略确认完成。
- [ ] Lite v0 开发在 `lite-test` 上完成。
- [ ] 不修改 Full `master` / `test` 发布内容。
- [ ] 区域录制和窗口录制用户入口已移除。
- [ ] 区域录制和窗口录制快捷键设置已移除。
- [ ] 鼠标点击高亮入口和运行路径已停用。
- [ ] 录制倒计时入口和运行路径已停用。
- [ ] 设置窗口只展示 Lite v0 允许的设置项。
- [x] 托盘空闲菜单只展示全屏录制、设置、打开保存文件夹、退出。
- [ ] 全屏录制以原生分辨率和 60fps 输出。
- [ ] 无声、系统声音、麦克风、两者都有四种模式均通过真实验证。
- [x] 暂停、恢复、停止、保存流程通过真实验证。
- [x] Toast、结果条、打开文件、打开文件夹通过真实验证。
- [ ] 自动化质量门槛全部通过。
- [x] PyInstaller 打包成功。
- [x] 打包产物启动成功。
- [x] `doc/lite/lite-v0-package-size-report.md` 完成。
- [x] README 已更新 Lite v0 口径。
- [x] `doc/lite/release-notes-lite-v0.md` 完成。
- [ ] `lite-test` 合并到 `lite-master`。
- [ ] 准备 tag `lite-v0`。

---

## 明确不进入 Lite v0 的内容

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

## Lite v0 完成定义

Lite v0 只有在以下条件全部满足后才能进入 tag 准备：

- [ ] `doc/lite/PRD-QuickRec-Lite.md` 与实际实现一致。
- [ ] `doc/lite/implementation-plan-lite.md` 与实际执行结果无明显冲突。
- [ ] `doc/lite/progress.md` 中所有 Lite v0 必须项已完成。
- [ ] `doc/lite/development-log-lite.md` 已记录关键验证和打包结果。
- [ ] `python -m compileall src scripts tests` 通过。
- [ ] `python -m ruff check .` 通过。
- [ ] `python -m mypy` 通过。
- [ ] `python -m pytest -q` 通过。
- [ ] `python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen` 通过。
- [x] 打包产物完成全屏 + 四种音频模式手动验证。
- [x] 体积低于 200MB，或已记录未达标原因且确认不阻断发布。
- [ ] `lite-test` 合并到 `lite-master`。
- [ ] tag `lite-v0` 指向已验收提交。
