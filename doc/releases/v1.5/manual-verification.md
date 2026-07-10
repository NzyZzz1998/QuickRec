# QuickRec Full v1.5 D6.3 GUI 手动验收

## 追踪信息

- 当前状态：通过；应用侧人工验收与 V15-P1 原型复验均已完成，可进入发布收口。
- 目标版本：QuickRec Full v1.5。
- 上游来源：[prd.md](prd.md)、[dev_plan.md](dev_plan.md)、[progress.md](progress.md)。
- 当前事实源：本文件与 `progress.md`。
- 最后更新：2026-07-10。

## 验收对象

- 分支：`feature/v1.5-full-foundation`。
- HEAD：`a8a1af4f8922fb1c0919b50da9ce0b06b1dafa19`。
- 验收包：`E:\QRtest\QuickRec-v1.5-dist\QuickRec\QuickRec.exe`。
- SHA256：`C2BFECA3BA6204D3EE078F6A9D7E0E17389373CEB2747421868317D55B4D9FC4`。
- 临时保存目录：`E:\QRtest\v1.5-acceptance`。
- 日志：`E:\QRtest\v1.5-acceptance\QuickRecDiagnostics\quickrec.log`。
- 主历史：`E:\QRtest\v1.5-acceptance\QuickRecMetadata\recordings.json`。
- 50 条受控历史：`E:\QRtest\v1.5-acceptance\history-50\QuickRecMetadata\recordings.json`。

## 前置与恢复

- 已在验收前备份用户配置和两份历史 JSON 到 `E:\QRtest\v1.5-acceptance\_backup\`。
- 验收结束后已恢复用户配置：保存路径为 `E:/QRtest/pkg_audio`，音频源为 `both`。
- 主历史已恢复为 3 条，受控历史已恢复为 50 条；未修改 ACL。
- 原型 HTTP 服务仅用于加载静态原型，不属于应用运行、打包或发布依赖；发布收口时已停止。

## 已有实际证据

| ID     | 前置条件与操作                              | 预期结果                  | 实际结果                                                  | 证据                                                                                                              | 结论   |
| ------ | ------------------------------------ | --------------------- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---- |
| V15-A1 | 打包产物全屏录制后播放                          | 视频可播放，无 QuickRec 自绘光标 | 已播放且可解码                                               | `QuickRec_20260710_095332.mp4`、`evidence/V15-A1-fullscreen-frame.png`、`evidence/V15-A1-fullscreen-playback.jpg` | 通过   |
| V15-A2 | 打包产物区域录制后播放                          | 视频可播放，无 QuickRec 自绘光标 | 已播放且可解码                                               | `QuickRec_20260710_095518.mp4`、`evidence/V15-A2-region-frame.png`                                               | 通过   |
| V15-A3 | 打包产物窗口录制后播放                          | 视频可播放，无 QuickRec 自绘光标 | 已播放且可解码                                               | `QuickRec_20260710_095607.mp4`、`evidence/V15-A3-window-frame.png`、`evidence/V15-A3-window-playback.jpg`         | 通过   |
| V15-H1 | 录制完成后检查历史 JSON                       | 新记录写入顶部               | 日志确认写入成功，人工对照 UI 与 JSON 后确认新记录位于首项                         | `quickrec.log` 第 64-81 行、人工验收记录                                                                          | 通过   |
| V15-H2 | 写入 55 条受控记录后读取 JSON                  | 只保留最近 50 条            | 受控 JSON 为 50 条，首项 `controlled-54`，末项 `controlled-05`；人工确认 UI 恰好显示 50 项且顺序一致 | `history-50/QuickRecMetadata/recordings.json`、人工验收记录                                                       | 通过   |
| V15-H9 | 将临时目录中的 `QuickRecMetadata` 设为普通文件后录制 | MP4 保存，历史写入失败仅记日志     | MP4 已保存；日志记录 `recording history save failed`；无 ACL 改动 | `history-failure/QuickRec_20260710_100857.mp4`、`quickrec.log` 第 47-60 行                                         | 通过   |
| V15-S1 | 检查运行代码与 spike 文档                     | WGC 不进入默认链路，仍使用 dxcam | `screen_capturer.py` 使用 dxcam；spike 明确不接入 WGC         | `capture-backend-spike.md`、`src/recorder/screen_capturer.py`                                                    | 通过   |

## 补充自动化证据

| ID | 验证方式 | 实际结果 | 证据 | 结论 |
| --- | --- | --- | --- | --- |
| V15-H6 | 运行缺失文件状态的 UI 与历史加载目标测试 | 缺失文件被标记为 `missing`，窗口显示“文件已移动或删除” | `tests/test_recent_recordings_dialog.py::test_missing_record_is_rendered`、`tests/test_recording_history.py::test_load_history_marks_missing_file` | 通过（自动验证） |
| V15-H7 | 运行列表移除与 JSON 移除目标测试，并检查移除实现 | UI 与 JSON 均移除指定记录；实现只重写历史 JSON，不调用视频删除 | `tests/test_recent_recordings_dialog.py::test_remove_deletes_selected_record`、`tests/test_recording_history.py::test_remove_history_item_removes_from_json`、`src/utils/recording_history.py:184` | 通过（自动验证） |
| V15-P1 | 通过本地 HTTP 服务和无头 Edge 实际加载并操作原型 | 页面返回 200；最近录制入口、列表、空状态、缺失状态、复制反馈和移除控件可用 | `evidence/V15-P1-empty-state-fixed.png` | 通过 |

### V15-P1 直接自动验收记录

- 页面：`http://127.0.0.1:8766/full.html`，HTTP 状态 `200`，标题为 `QuickRec Full Prototype`。
- 入口：最近录制导航 1 个，点击后页面进入激活状态；素材导航 1 个，录制页包含“素材入库”说明。
- 列表：初始 3 条记录，其中 1 条显示“文件已移动或删除”。
- 控件：2 个“打开”、2 个“打开目录”、2 个“复制路径”、1 个“从列表移除”。
- 交互：复制后反馈为“已复制”；移除缺失记录后列表从 3 条变为 2 条，缺失记录变为 0 条。
- 录制模拟：开始后显示“正在录制项目素材”，再次点击停止后自动切换到最近录制页。
- 首次结果：页面主交互正常，但没有空状态，记录为 `BUG-V15-P1-001`。
- 修复复验：新增“演示空状态 / 恢复示例记录”切换；空状态显示“暂无录制记录”，空状态下可见记录为 0，恢复后重新显示 3 条记录。
- 回归结果：复制反馈仍为“已复制”，缺失记录仍可移除，页面脚本无运行错误。
- 截图：`evidence/V15-P1-auto-before.png`、`evidence/V15-P1-auto-after.png`、`evidence/V15-P1-auto-record.png`、`evidence/V15-P1-empty-state-fixed.png`。
- 结论：通过，`BUG-V15-P1-001` 已关闭。

## 人工补证结果

| ID     | 操作步骤                                                                  | 预期结果                                     | 证据要求                      | 结论          |
| ------ | --------------------------------------------------------------------- | ---------------------------------------- | ------------------------- | ----------- |
| V15-A4 | 启动验收包，开启“鼠标点击高亮”；全屏录制约 5 秒，使用真实鼠标完成至少 3 次点击；停止后播放并抽帧                  | 屏幕可见红色点击高亮；视频中没有红色高亮动画和自绘鼠标指针            | 录制时截图、MP4、至少 3 张关键帧       | 通过          |
| V15-R1 | 右键托盘图标，分别在空闲和录制中确认“最近录制”；完成录制后点击结果条“最近”                               | 两个入口均打开同一个最近录制窗口，可关闭并再次打开                | 两个入口截图、窗口截图               | 通过          |
| V15-H1 | 在最近录制窗口确认新录制位于首项，并对照 JSON 的文件名、时间、模式                                  | UI 与 JSON 一致                             | UI 截图、JSON 片段             | 通过          |
| V15-H2 | 将保存路径临时切换到 `history-50` 对应目录，打开最近录制窗口                                 | 恰好显示 50 项，顺序与 JSON 一致                    | 列表顶部/底部截图、JSON 片段         | 通过          |
| V15-H3 | 在有效记录上点击“打开”                                                          | 默认播放器打开对应 MP4                            | 播放器标题截图                   | 通过          |
| V15-H4 | 点击“打开所在目录”                                                            | 资源管理器进入对应目录                              | 资源管理器路径截图                 | 通过          |
| V15-H5 | 点击“复制路径”，读取剪贴板                                                        | 剪贴板为完整 MP4 路径，并显示成功反馈                    | 反馈截图、剪贴板文本                | 通过          |
| V15-H6 | 将一条测试 MP4 移到临时备份目录，刷新/重开窗口，完成后移回                                      | 显示“文件已移动或删除”，不误打开其他文件                    | 缺失状态截图、恢复后路径              | 通过（自动验证） |
| V15-H7 | 对受控缺失项执行“从列表移除”                                                       | 仅删除 JSON 索引，不删除实际视频                      | 移除前后截图、JSON 对比、MP4 仍存在    | 通过（自动验证） |
| V15-H8 | 切换到空测试保存目录后打开最近录制窗口                                                   | 显示明确空状态，无残留项或错误                          | 空状态截图                     | 通过          |
| V15-D1 | 打开托盘“设置”，确认诊断分组；依次复制、打开日志目录、导出诊断文件；修改一个普通设置并保存、重启后检查                  | 设置可开关；诊断操作均成功；导出文件存在且可读；设置保持             | 设置/诊断截图、导出文件路径和文本、重启后配置截图 | 通过          |
| V15-P1 | 在浏览器打开 `http://127.0.0.1:8766/full.html`；查看“最近录制”，切换空状态/缺失状态并使用模拟操作控件 | 页面可加载，入口、列表、空状态、缺失状态和控件均可展示，且不与 PRD/实现冲突 | 页面截图、操作后截图                | 通过 |

## 人工执行提示

1. 先备份 `%APPDATA%\QuickRec\config.json` 与当前保存目录下的 `QuickRecMetadata\recordings.json`。
2. 将验收保存目录临时设置为 `E:\QRtest\v1.5-acceptance`，完成后恢复原配置。
3. H6、H7、H8 只使用 `E:\QRtest\v1.5-acceptance` 内的测试文件；不要触碰用户真实视频。
4. 原型验证前，在项目目录运行：`python -m http.server 8766 --directory E:\codex\QuickRec\doc\prototypes\product-prototype`；完成后关闭该服务。
5. 任一待验证项失败时，记录操作、截图、日志尾部和文件路径；不要直接修改功能实现。

## 验证记录

- 验证人：用户人工验证 + Codex 补充自动验证。
- 验证时间：2026-07-10。
- 用户人工结果：V15-A4、V15-R1、V15-H1 至 V15-H5、V15-H8、V15-D1 通过；V15-H6、V15-H7 由目标自动化测试补证；V15-P1 首次因本地 HTTP 服务未启动无法打开，后续已完成自动复验。
- 补充验证结果：V15-H6、V15-H7 目标测试共 4 项通过；V15-P1 原型空状态修复后自动复验通过。
- 总体结论：通过。

## 发布阻塞标准

- V15-A4、V15-R1、V15-H1 至 V15-H8、V15-D1 已通过人工或补充自动验证。
- V15-P1 已完成空状态修复与复验；当前无发布阻塞项，发布操作已获得用户独立授权。
- 出现视频保存失败、最近录制窗口崩溃、历史失败导致录制失败，结论应改为未通过并进入 bugfix。

## 发布前最终复核

- 复核日期：2026-07-10。
- 锁定验收包：`E:\QRtest\QuickRec-v1.5-dist\QuickRec\QuickRec.exe`，大小 `6,810,432` 字节；完整目录 `270,442,336` 字节，共 `229` 个文件。
- SHA256 复核：`C2BFECA3BA6204D3EE078F6A9D7E0E17389373CEB2747421868317D55B4D9FC4`，与 D6.3 锁定值一致。
- 目标测试：`82 passed`；诊断与设置回归：`19 passed`；打包测试：`10 passed, 1 skipped`。跳过项为发布包未携带 `ffprobe` 时的编码格式断言，属于既有条件跳过，不影响 FFmpeg 运行能力检查。
- `ruff`、`mypy`、`compileall` 和 `git diff --check` 均通过。
- V15-P1 最终截图：`E:\QRtest\v1.5-acceptance\evidence\V15-P1-empty-state-fixed.png`。
- 当前发布判断：发布前验收与文档收口通过，v1.5 正式发布。
