# QuickRec Full v1.9 自动验证与发布包记录

## 1. 验证结论

- 当前阶段：D7 自动化门禁、D8 GUI 验收与发布收口均通过。
- 总体结论：**R8 验收包验证通过，并作为 v1.9 正式发布包**。
- 正式发布状态：**已发布**。
- 验证日期：2026-07-26 至 2026-07-27。

## 2. 源码身份

| 项目 | 内容 |
| --- | --- |
| 项目路径 | `E:\codex\QuickRec` |
| 发布分支 | `master` |
| 历史实施分支 | 本地 `feature/v1.9-project-workspace`，未单独推送远端 |
| 基线 HEAD | `57dbc524a31526e5f4ff64b305169c329a200c69` |
| 基线 tag | `v1.8` |
| v1.9 功能提交 | `42192cf27c7f95a817cf6f34085b47dba8d65fe8` |
| CI 修复提交 | `31ef3807be5580561d848d283d2e58dfc58fdad9` |
| 发布标签 | `v1.9` |
| 应用版本 | `v1.9` |
| Lite 状态 | `E:\codex\QuickRec-Lite` 保持干净，未修改 |

R8 由 v1.9 最终业务源生成，并在发布提交前完成身份锁定。R0-R6 均为失效候选。R7 因录制页“全屏录制”仍带主按钮角色而失效；其未受视觉修复影响的录制、音频、设置、诊断和 120 FPS 证据继续继承。最终锁定的 R8 EXE 已提升为正式发布包。

## 3. 自动化与质量门禁

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 全量测试与覆盖率 | `python -m pytest --cov=src --cov-report=term --cov-fail-under=80 -q` | `642 passed, 25 deselected, 52 subtests passed` |
| 总体覆盖率 | 同上 | `85.76%` |
| 项目模块定向回归 | 项目存储、服务、查询、UI、录制、恢复、删除与主流程联合测试 | `151 passed` |
| 项目模块覆盖率 | 项目服务、删除、录制、项目页和对话框 | `84.60%` |
| Packaging | `python -m pytest -m packaging -q` | `13 passed, 654 deselected` |
| Ruff | `python -m ruff check src tests scripts` | 通过 |
| Mypy | `python -m mypy` | 通过，检查 30 个源文件 |
| Compileall | `python -m compileall -q src tests scripts` | 通过 |
| 差异格式 | `git diff --check` | 通过 |

## 4. 性能样本

测试文件：`tests/test_project_performance.py`。

| 场景 | 门槛 | 本机结果 | 结论 |
| --- | --- | --- | --- |
| 100 个项目首次展示 | `< 1 秒` | `0.27 秒` | 通过 |
| 打开 200 条素材引用项目 | `< 1 秒` | `0.02 秒` | 通过 |
| 普通项目重命名反馈 | `< 500 ms` | `0.02 秒` | 通过 |
| 慢速项目回收站操作 | 不阻塞 UI | 后台线程执行，入口调用 `< 0.1 秒` | 通过 |

以上为受控本地 SSD 夹具，不替代 D8 的真实 GUI 与长路径验收。

## 5. 原型回归

原型：`doc/releases/v1.9/prototype/index.html`。

自动验证结果：`PASS`。

- 一级导航共 5 页。
- 录制页 3 个模式保持平级且无默认选中态。
- 项目素材选择器包含可用、已加入、缺失和不可用状态。
- 项目内全屏、区域、窗口录制入口均存在。
- 删除确认默认不勾选视频，共享和不确定素材被禁用。
- 960×640 下项目页和删除入口可滚动访问。
- 浏览器控制台与页面脚本无错误。

## 6. Windows 回收站验证

使用 `E:\QRtest` 下新建的受控临时项目文件执行真实 `send2trash` 验证：

- 返回结果：`ok=True`。
- 操作后原路径不存在。
- 未操作用户项目、素材或视频。
- 静态扫描未发现项目文件或视频的永久删除路径。
- `project_store.py` 中的 `unlink` 仅用于原子写临时文件和超过上限的损坏归档副本。

## 7. 候选包

R8 打包命令：

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm `
  --distpath E:\QRtest\QuickRec-v1.9-dist-r8 `
  --workpath E:\QRtest\QuickRec-v1.9-build-r8
```

| 对象 | 路径 | 大小 | SHA256 |
| --- | --- | ---: | --- |
| EXE | `E:\QRtest\QuickRec-v1.9-dist-r8\QuickRec\QuickRec.exe` | `7,047,836` 字节 | `CFE6BC6D4FC342039A0B410B4CF80FC9A34BAD47908F671AE9161FC63F7A9D47` |
| FFmpeg | `E:\QRtest\QuickRec-v1.9-dist-r8\QuickRec\_internal\ffmpeg\ffmpeg.exe` | `99,264,000` 字节 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| FFprobe | `E:\QRtest\QuickRec-v1.9-dist-r8\QuickRec\_internal\ffmpeg\ffprobe.exe` | `99,066,368` 字节 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |

- FFprobe 版本：`8.0.1-essentials_build-www.gyan.dev`。
- 分发目录文件数：`244`。
- 分发目录总大小：`428,210,468` 字节。
- 基础启动与 GUI：使用隔离 APPDATA 启动，托盘、五页工作台和项目空状态可用。
- 包内 FFprobe 已直接解析继承的 R7 录制文件，结果为 H.264、`1920×1080`、`30 FPS`、`3.433333` 秒。
- PyInstaller 归档已确认包含：
  - `services.project_deletion`
  - `services.project_library`
  - `services.project_query`
  - `services.project_recording`
  - `ui.project_dialogs`
  - `ui.project_page`
  - `utils.project_store`
  - `send2trash.win`

## 8. R7 真实录制与恢复验证

证据根目录：

```text
E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-20260727-003500
```

- 连续执行 3 次全局快捷键全屏录制，均一次停止并完成保存。
- 另执行 1 次中央素材索引被占用时的录制，MP4 正常保存，待入库记录成功持久化。
- 解除占用并重启后，启动重试结果为 `scanned=1 succeeded=1 failed=0 missing=0`。
- 中央素材记录由 3 条增至 4 条，待入库记录由 1 条归零。
- 四个 MP4 均由包内 FFprobe 成功解析，输出为 H.264、`1920×1080`、`30 FPS`。
- 每次停止日志均出现 `DXCamera asynchronous stop requested`，采集资源释放线程在 `4-10 ms` 内结束。
- 真实 `%APPDATA%\QuickRec\config.json` 和 `recordings.json` 的验收后 SHA256 与验收前一致。
- 当前源码硬件 smoke：
  - `E:\QRtest\QuickRec-v1.9-hardware-smoke-r7\QuickRec_20260727_004200.mp4`
  - `E:\QRtest\QuickRec-v1.9-hardware-smoke-r7-repeat\QuickRec_20260727_004224.mp4`
  - 两次均返回 `OK: video stream ok`；测试脚本默认目标为 `15 FPS`。

## 9. D8 最终判断

自动化、性能、原型、packaging、基础启动、依赖封装和全部 GUI 发布阻塞链路均通过。R8 关闭了录制页视觉回退，并在受控隔离环境完成三条真实回收站路径：

- 仅删除项目：项目文件和项目索引移除，视频及中央素材索引保留。
- 删除独占视频：独占视频和项目文件进入 Windows 回收站，共享素材不受影响。
- 部分失败：首个素材成功回收，第二个被占用素材失败后停止，项目文件和项目索引保留，UI 与日志展示真实进度。

R8 证据目录：`E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-recycle-20260727-094500`。

三档 DPI 证据位于 `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-delete-20260727-005000\Evidence`：

- 100% 为本机原生 Windows 缩放，`GetDpiForSystem()` 返回 `96`。
- 125% 和 150% 使用同一锁定 R7 EXE 与隔离数据，通过 `QT_SCALE_FACTOR=1.25/1.5` 验证项目页、删除确认、素材选择和缺失恢复状态。
- 两档分别生成 `project-page-*`、`delete-dialog-*`、`material-selector-*`、`project-missing-*` 截图；受控项目文件已恢复。

四类音频证据：

- 无声样本仅含 H.264 视频流。
- 系统声音、麦克风和双音频样本均含 `48 kHz / 2ch AAC`，FFmpeg 响度检测确认不是空音频流。
- 系统声音受控 `997 Hz` 测试音检测幅度为 `0.353472`；麦克风受控 `733 Hz` 响应幅度为 `0.000947`。
- 双音频日志同时记录两路设备初始化、两个临时音频轨和独立时间对齐。
- 结构化证据为 `E:\QRtest\QuickRec-v1.9-acceptance\d8-r7-audio-20260727-013200\Evidence\D8-23-audio-verification.json`。

补充自动回归：

- 使用当前 v1.9 工作区运行设置、配置、托盘、快捷键、主流程、120 FPS 能力服务和自检对话框定向测试，共 `116 passed`。
- 覆盖配置候选写入失败不改变内存和磁盘、设置保存失败保持窗口与脏状态、托盘菜单与退出回调、全局快捷键桥接、120 FPS 自检候选值和取消行为。
- 候选包中的设置保存失败 GUI 取证和 120 FPS 真实自检均已完成；平均 `119.586 FPS`，最低连续一秒 `117 FPS`。
- 最终复核时 R8 EXE SHA256 为 `CFE6BC6D4FC342039A0B410B4CF80FC9A34BAD47908F671AE9161FC63F7A9D47`；真实 `%APPDATA%\QuickRec\config.json` 与 `recordings.json` 哈希保持不变。
- D8 结论：通过，无发布阻塞；R8 已完成发布收口并提升为 v1.9 正式发布包。
