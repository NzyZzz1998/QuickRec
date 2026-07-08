# QuickRec Lite 开发日志

> 本文档用于记录 QuickRec Lite 产品线的开发过程、验证结果、问题处理、打包记录和发布收口。总体进度和 Vibe Coding 最小任务请维护在 `progress.md`，不要把开发流水写入 progress。

**最后更新**: 2026-07-08  
**当前阶段**: Lite v0 手动验证完成 / 待打包与发布收口  
**关联文档**:
- `PRD-QuickRec-Lite.md`
- `implementation-plan-lite.md`
- `progress.md`

---

## 2026-07-08 文档基线建立

### 已完成

- 新增 Lite 独立文档目录 `doc/lite/`。
- 新增 Lite v0 PRD：`PRD-QuickRec-Lite.md`。
- 新增 Lite v0 实施计划：`implementation-plan-lite.md`。
- 新增 Lite v0 进度文档：`progress.md`。
- 新增 Lite 开发日志：`development-log-lite.md`。
- 主 PRD `doc/PRD-QuickRec.md` 已追加 Lite v0 摘要，并指向 `doc/lite/PRD-QuickRec-Lite.md`。

### 当前决策

- QuickRec Full 分支：`master` / `test`。
- QuickRec Lite 分支：`lite-master` / `lite-test`。
- 当前已有 `lite` 分支仅作为过渡分支。
- Lite v0 开发目标分支为 `lite-test`。
- Lite v0 只保留全屏录制作为用户可见录制模式。
- Lite v0 固定原生分辨率和 60fps。
- Lite v0 保留无声 / 系统声音 / 麦克风 / 两者都有四种音频模式。
- Lite v0 移除区域录制、窗口录制、鼠标点击高亮、录制倒计时和相关快捷键设置。
- Lite v0 体积目标低于 200MB，但不作为发布阻断验收。

### 待记录

- [x] `lite-master` / `lite-test` 实际创建结果。
- [x] Lite v0 首轮代码裁剪提交。
- [x] 自动化测试结果。
- [x] 手动硬件验收结果。
- [ ] 打包体积报告。
- [ ] release notes 与 tag 信息。

---

## 2026-07-08 Lite v0 首轮代码裁剪

### 已完成

- 已创建 `lite-master`，并从 `lite-master` 创建 `lite-test` 作为 Lite v0 开发分支。
- `src/config.py` 默认值已收敛为 `quality=native`、`fps=60`。
- `src/recorder/recorder_manager.py` 实际录制启动链路已强制使用原生分辨率和 60fps，避免旧配置中的 `quality=high/medium/low` 或 `fps=30` 继续影响 Lite v0 输出。
- `src/ui/settings_dialog.py` 已移除画质、帧率、区域录制快捷键、窗口录制快捷键、录制倒计时和鼠标点击高亮设置入口。
- `src/ui/settings_dialog.py` 保留保存路径、音频源四模式、开始快捷键、停止快捷键、暂停/恢复快捷键和开机自启。
- `src/ui/tray_icon.py` 空闲菜单已裁剪为全屏录制、设置、打开保存文件夹和退出。
- `src/main.py` 只注册开始、停止、暂停/恢复三组快捷键。
- `src/main.py` 旧配置 `show_countdown=true` 不再触发倒计时。
- `src/main.py` 旧配置 `mouse_highlight=true` 不再启动鼠标点击高亮。
- 自动化测试已同步 Lite v0 入口与配置预期。

### 自动化验证

- `python -m pytest -q`：通过，231 passed，23 deselected，18 subtests passed。
- `python -m compileall src scripts tests`：通过。
- `python -m ruff check .`：通过。
- `python -m mypy`：通过。

### 当前停止点

- 当前已推进到手动验证前阶段。
- 真实硬件冒烟已通过：`python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen`，输出 `E:\QRtest\QuickRec_20260708_133603.mp4`，约 59.11 FPS。
- 无声 / 系统声音 / 麦克风 / 两者都有四种音频模式已通过录制引擎验证。
- 尚未进行 PyInstaller 打包和体积报告记录。

---

## 2026-07-08 Lite v0 测试用例与 Computer Use 验证

### 已完成

- 新增 Lite v0 独立测试用例文档：`doc/lite/lite-v0-test-cases.md`。
- 使用 Computer Use 捕获并检查 `QuickRec Lite 设置` 窗口。
- 设置窗口保留项验证通过：保存路径、音频源、开机自启、开始快捷键、停止快捷键、暂停快捷键、保存、取消。
- 设置窗口裁剪项验证通过：未出现画质、帧率、区域录制、窗口录制、录制倒计时、鼠标点击高亮。

### 验证补充

- 用户已完成托盘图标和托盘菜单目视验证。
- 四种音频模式已完成真实设备路径验证，均生成可解析 MP4。
- 打包产物和体积报告已完成。

---

## 2026-07-08 Lite v0 手动验证推进

### 已完成

- 四种音频模式录制引擎验证通过：
  - `none`：生成 MP4，包含视频流，无音频流。
  - `system`：生成 MP4，包含视频流和 AAC 音频流。
  - `microphone`：生成 MP4，包含视频流和 AAC 音频流。
  - `both`：生成 MP4，包含视频流和 AAC 音频流。
- 源码应用 `src/main.py` 启动通过。
- 使用 Computer Use 发送全局快捷键完成真实用户路径验证：
  - `Ctrl+Q` 触发开始录制。
  - `Ctrl+E` 触发停止录制。
  - 输出文件：`E:\QRtest\QuickRec_20260708_135040.mp4`。
- 输出文件元数据验证通过：
  - 视频：H.264，`2560x1440`，60 fps。
  - 音频：AAC，48000 Hz。
- 当前用户旧配置仍包含 `quality=high`、`mouse_highlight=true`，实测输出仍按 Lite v0 收敛为原生分辨率和 60fps。

### 用户补验结果

- 用户确认剩余手动验证项已全部完成。
- 系统托盘右键菜单通过目视验证。
- 暂停/恢复、工具栏结果条、打开文件、打开文件夹和播放器目视播放通过用户手动验证。

### 未完成项

- PyInstaller 打包和体积报告已完成。

---

## 2026-07-08 Lite v0 打包与产物验证

### 已完成

- 执行打包命令：`python -m PyInstaller build_std.spec --clean --noconfirm`。
- 打包产物路径：`dist/QuickRec/QuickRec.exe`。
- 打包体积报告：`doc/lite/lite-v0-package-size-report.md`。
- 产物总体积：`257.89 MB`。
- 打包约束检查通过：内置 FFmpeg、保留 cv2、排除 OpenCV 自带视频 IO FFmpeg 插件、未包含测试资源。
- 打包产物启动通过。
- 打包产物快捷键录制通过：
  - `Ctrl+Q` 触发开始录制。
  - `Ctrl+E` 触发停止保存。
  - 输出文件：`E:\QRtest\QuickRec_20260708_152150.mp4`。
- 输出元数据验证通过：
  - 视频：H.264，`2560x1440`，60fps。
  - 音频：AAC，48000Hz。

### 发布判断

- Lite v0 稳定包体积未低于 200MB。
- 未达标主要原因：FFmpeg、OpenCV/cv2、PyQt5、NumPy 和 Python runtime 仍是主要体积来源。
- 体积目标不作为 Lite v0 阻断项，本次以稳定捕获链路和内置 FFmpeg 可用性优先。
