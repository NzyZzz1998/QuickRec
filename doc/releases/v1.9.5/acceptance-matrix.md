# QuickRec Full v1.9.5 验收追溯矩阵

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 目标版本 | QuickRec Full v1.9.5 |
| 候选包 | `E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec` |
| GUI SHA256 | `705B227FE33F31D4EE650334D607CAAA919FC3D1B44C633CEA1E5B75B3B4A226` |
| 当前分支 | `test` |
| 发布前基线 | tag `v1.9.4` / `b3b8267e1950b8e2b9efc6d28d29b501189fd7af` |
| 审计日期 | 2026-07-31 |
| 总体结论 | 20/20 条 ACC 全部通过 |
| 发布判断 | 验收通过，可进入发布收口 |

本矩阵把 [prd.md](prd.md) 中 `ACC-195-01` 至 `ACC-195-20` 与当前代码、
自动化、候选包 GUI 和真实媒体证据逐条对应。自动化只能证明其实际覆盖的合同，
不能替代必须听音或观察的真实验收。

## 2. 证据身份

自动化与工程门禁：

```text
非硬件、非 Packaging：1425 passed, 32 deselected, 72 subtests passed
Packaging：20 passed, 1437 deselected
总体 Coverage：84.14%
v1.9.5 领域核心：95.24%
v1.9.5 UI 协调：97.75%
Ruff：通过
Mypy：83 个源文件通过
Compileall：通过
git diff --check：通过，仅有 LF/CRLF 转换提示
```

主要 GUI 与真实媒体证据：

```text
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\native-drag\evidence
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\temp-cleanup-cancel
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\interruption-recovery
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\audio-listening
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\mic-gs03-retest2-20260731
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\both-gs03-retest-20260731
```

详细过程见 [verification.md](verification.md) 和
[manual-verification.md](manual-verification.md)。

## 3. ACC 逐条结论

| 编号 | 验收合同 | 结论 | 直接证据 |
| --- | --- | --- | --- |
| ACC-195-01 | Space 契约 | 通过 | [test_timeline_shortcuts.py](../../../tests/test_timeline_shortcuts.py)、[test_timeline_playback_ui.py](../../../tests/test_timeline_playback_ui.py)；候选包 D9.1-D9.3 |
| ACC-195-02 | 解绑只清空 `link_group_id` | 通过 | [test_timeline_link_commands.py](../../../tests/test_timeline_link_commands.py)、[test_v195_d7_integration.py](../../../tests/test_v195_d7_integration.py)；D9.4 |
| ACC-195-03 | 解绑后独立编辑 | 通过 | [test_timeline_link_commands.py](../../../tests/test_timeline_link_commands.py)、[test_timeline_editing_ui.py](../../../tests/test_timeline_editing_ui.py)；D9.5-D9.7 |
| ACC-195-04 | 严格重新关联 | 通过 | [test_timeline_link_commands.py](../../../tests/test_timeline_link_commands.py)、[test_timeline_editor_d6_ui.py](../../../tests/test_timeline_editor_d6_ui.py)；D9.8 |
| ACC-195-05 | 普通删除保留空隙 | 通过 | [test_timeline_delete_commands.py](../../../tests/test_timeline_delete_commands.py)、[test_v195_d7_integration.py](../../../tests/test_v195_d7_integration.py)；D9.9、D9.26 |
| ACC-195-06 | 全局波纹删除 | 通过 | [test_timeline_delete_commands.py](../../../tests/test_timeline_delete_commands.py)、[test_timeline_editing_ui.py](../../../tests/test_timeline_editing_ui.py)；D9.10、D9.26 |
| ACC-195-07 | 拖放预览 | 通过 | [test_timeline_drag_interaction.py](../../../tests/test_timeline_drag_interaction.py)、[test_timeline_editor_d6_ui.py](../../../tests/test_timeline_editor_d6_ui.py)；原生 Qt 拖放截图 |
| ACC-195-08 | 条件性自动建轨 | 通过 | [test_timeline_drag_transaction.py](../../../tests/test_timeline_drag_transaction.py)、[test_timeline_commands.py](../../../tests/test_timeline_commands.py)；D9.14 |
| ACC-195-09 | 视频/音频各 8 轨上限 | 通过 | [test_timeline_drag_transaction.py](../../../tests/test_timeline_drag_transaction.py)、[test_timeline_editor_ui.py](../../../tests/test_timeline_editor_ui.py)；D9.15、D9.21 |
| ACC-195-10 | 项目编辑 FPS | 通过 | [test_project_editing_profile.py](../../../tests/test_project_editing_profile.py)、[test_timeline_editing_profile_integration.py](../../../tests/test_timeline_editing_profile_integration.py)；D9.18-D9.20 |
| ACC-195-11 | 帧与微秒统一换算 | 通过 | [test_timeline_frame_time.py](../../../tests/test_timeline_frame_time.py)、[test_timeline_snap.py](../../../tests/test_timeline_snap.py)；120 FPS 实测 |
| ACC-195-12 | 项目扩展兼容 | 通过 | [test_project_editing_profile.py](../../../tests/test_project_editing_profile.py)、[test_project_library.py](../../../tests/test_project_library.py)、[test_v195_d7_integration.py](../../../tests/test_v195_d7_integration.py) |
| ACC-195-13 | 只读、录制、保存、未知版本和缺失保护 | 通过 | [test_timeline_session.py](../../../tests/test_timeline_session.py)、[test_timeline_editing_ui.py](../../../tests/test_timeline_editing_ui.py)、[test_cli_commands.py](../../../tests/test_cli_commands.py) |
| ACC-195-14 | 保存失败零副作用 | 通过 | [test_timeline_link_commands.py](../../../tests/test_timeline_link_commands.py)、[test_timeline_delete_commands.py](../../../tests/test_timeline_delete_commands.py)、[test_timeline_drag_transaction.py](../../../tests/test_timeline_drag_transaction.py) |
| ACC-195-15 | 最高视频轨覆盖一致 | 通过 | [test_v195_d7_integration.py](../../../tests/test_v195_d7_integration.py)、[test_timeline_playback_ui.py](../../../tests/test_timeline_playback_ui.py)；D9.25 FFprobe/像素证据 |
| ACC-195-16 | 三种录制工具栏定位 | 通过 | [test_toolbar_placement.py](../../../tests/test_toolbar_placement.py)、[test_toolbar.py](../../../tests/test_toolbar.py)；D9.27 三种模式均为 `1113,139,334,48` |
| ACC-195-17 | 导出临时文件安全治理 | 通过 | [test_export_temp_cleanup.py](../../../tests/test_export_temp_cleanup.py)、[test_export_queue_service.py](../../../tests/test_export_queue_service.py)；D9.29 超时取消与启动中断恢复 |
| ACC-195-18 | 原型和候选包 GUI/真实媒体 | 通过 | 原型 239/239、三档视口、8+8 轨、100 片段、30 分钟、三档 DPI、三种录制和 H.264/AAC 通过；D9.24 的 GS03 麦克风与双音频真实听音通过 |
| ACC-195-19 | 工程质量门禁 | 通过 | 当前工作区最终预检：全量、Packaging、Coverage、Ruff、Mypy、Compileall、文档和差异检查全部通过 |
| ACC-195-20 | 向下编辑兼容说明 | 通过 | [README.md](../../../README.md)、[current.md](../../current.md)、[release-notes.md](release-notes.md) 均包含警告和 `.qrproj`/`.bak` 备份要求 |

## 4. 发布阻塞条件审计

PRD 第 31 节共有 21 条发布阻塞条件：

- 第 1-18、20、21 条已由原型确认、自动化、候选包 GUI、真实媒体、文档、
  tag 和 Lite 状态证据关闭。
- 第 19 条要求 v1.9.4 全功能无发布阻塞回归。录制、素材、项目、剪辑、导出、
  设置、诊断、CLI 以及无声、系统声音、麦克风和双音频均通过。
- 麦克风与双音频最终补证使用恢复后的默认 GS03；用户分别确认可听见口述，
  以及可同时听见系统测试音和口述。

因此发布阻塞审计结论为：**21 条发布阻塞条件全部关闭，无延期项**。

## 5. D9.24 最终补证闭合

D9.24 的两类真实听音均已完成：

1. 锁定 RC3 frozen CLI 使用 GS03 录制 10 秒麦克风样本，输出 H.264/AAC，
   平均 `-42.4 dB`、峰值 `-24.2 dB`，用户确认口述可听。
2. 同一候选包录制 10 秒系统声音+麦克风样本，输出 H.264/AAC，平均
   `-27.1 dB`、峰值 `-19.6 dB`，用户确认系统测试音和口述均可听。
3. 两类 MP4、提取 WAV、`record.json`、SHA256 和 FFprobe 结果均保存在
   第 2 节列出的两个最终补证目录。

早期静音样本继续保留在 `audio-listening` 目录作为过程证据，不改写历史；
最终结论以之后生成的 GS03 两组有效样本和用户听音确认为准。

## 6. 当前验收判断

```text
ACC：20/20 通过
D9：通过（31/31）
D10：18/18
自动化与工程门禁：全部通过
当前正式版本：v1.9.5
v1.9.5：正式发布
```

当前验收结论为：**通过，无延期项和发布阻塞**。发布收口已经获得用户授权，
正式版本以 `master`、annotated tag `v1.9.5` 和 GitHub Release 为准。
