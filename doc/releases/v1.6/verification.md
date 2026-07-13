# QuickRec Full v1.6 验证汇总

> 当前结论：通过。实现类发布阻塞均已关闭，持久重试入口已确认延后，三档 DPI 人工补证已通过。

## 1. 验收对象

- 分支：`feature/v1.6-material-library`
- 构建时 HEAD：`73ad5a778ff6e27a399d016f4ebb749ddc78438b`
- EXE：`E:\QRtest\QuickRec-v1.6-bugfix3-dist\QuickRec\QuickRec.exe`
- SHA256：`F1C8F2F971D5DD62067955B939D5DB9293C13DA930D1DFC653007F59596392E8`
- 隔离环境：`E:\QRtest\QuickRec-v1.6-bugfix-acceptance`
- 旧候选 SHA256 `3D50ACCDE7D6CF06579A4AE5AEBE92D3A0B605C633D5AEC9D65B783842424C85` 已因代码变化失效，仅用于追溯第二批失败证据。

## 2. 已有自动化证据

| 检查 | 结果 |
| --- | --- |
| 全量测试 | 333 passed，24 deselected，22 subtests passed |
| Packaging | 12 passed |
| Coverage | 83.01% |
| Ruff | 通过 |
| Mypy | 通过 |
| Compileall | 通过 |
| git diff --check | 通过 |
| 全屏硬件 smoke | `OK: video stream ok` |

## 3. D7 第一批结果

| 范围 | 结论 | 说明 |
| --- | --- | --- |
| D7-A GUI 基础链路 | 通过 | 素材库、设置和诊断通过；结果条入口由用户手动补证通过 |
| D7-B 区域录制 | 通过 | 画面、尺寸、索引和 FFprobe 一致 |
| D7-B 窗口录制 | 通过 | 仅录制所选资源管理器窗口，索引和 FFprobe 一致 |
| D7-C 无声 | 通过 | 无音频流，索引为 `none` |
| D7-C 系统声 | 通过 | AAC 双声道且存在受控测试音 |
| D7-C 麦克风 | 通过 | 单声道结构已验证；用户手动补测确认语音可听 |
| D7-C 双音频 | 通过 | 三声道合流结构已验证；用户手动补测确认系统声和麦克风均可听 |
| 元数据抽样 | 通过 | 路径、宽高、FPS、大小、模式、音频和状态一致；时长误差均小于 0.5 秒 |
| v1.4.1 诊断回归 | 通过 | 复制、打开目录、导出文件均成功 |
| QuickRec Lite | 通过 | 工作区干净，未修改 |

## 4. 证据索引

- 预检身份：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\00-preflight-identity.json`
- 区域关键帧：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\D7-B-region-frame.png`
- 窗口关键帧：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\D7-B-window-frame.png`
- 元数据对照：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\D7-first-batch-metadata.json`
- 音量分析：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\D7-first-batch-audio-volume.txt`
- 日志副本：`E:\QRtest\QuickRec-v1.6-acceptance\evidence\D7-first-batch-quickrec.log`
- 诊断导出：`E:\QRtest\QuickRec-v1.6-acceptance\diagnostics\diagnostic_20260711_021434.txt`
- 中央索引：`E:\QRtest\QuickRec-v1.6-acceptance\AppDataRoaming\QuickRec\recordings.json`

## 5. 发布阻塞与剩余补证

- 目录重建和重新定位的两个实现阻塞已修复并通过新候选包定向复验。
- 持久重试入口已确认延后至后续版本，不再列为 v1.6 发布阻塞。
- 手动导入已补证通过。
- 无备份恢复、回收站失败和 0/1 条边界已由 Bugfix3 候选包补证通过。
- 三档 DPI 下素材库主窗口、重新定位、移除索引和回收站确认框已由用户手动确认通过。

## 6. D7 第二批原始结果

以下表格保留修复前锁定候选包的原始验收结论；目录重建和重新定位的修复后结果见第 8 节。

| 范围 | 结论 | 说明 |
| --- | --- | --- |
| 历史迁移与幂等 | 通过 | 首次迁移 2 条，旧索引不变；二次启动数量和哈希不变 |
| 备份恢复 | 通过 | 损坏主索引从有效备份恢复并保留损坏归档 |
| 目录重建 | 未通过 | 有效 MP4 和损坏伪 MP4 均进入元数据不完整状态 |
| 重新定位 | 未通过 | 损坏 MP4 被接受；有效 MP4 也无法获得元数据 |
| 仅移除索引 | 通过 | 只删除记录，不删除视频；取消无副作用 |
| Windows 回收站 | 通过 | 文件进入 E 盘回收站，索引同步移除，取消无副作用 |
| 索引失败降级 | 通过 | 视频保存成功、FFprobe 可解析、索引失败独立记录 |
| 重试入库 | 待验证 | 多次点击发生在故障仍存在时，恢复后结果条已超时 |
| 200 条与分页 | 通过 | 201 裁剪为 200，50/100/150/200 加载正确 |
| 100%/125%/150% DPI | 部分通过 | 三档冷启动主界面可操作，确认弹窗未逐档全量重复 |

第二批证据根目录：`E:\QRtest\QuickRec-v1.6-acceptance\second-batch\evidence`。

## 7. 当前发布判断

当前为**通过**。D7 第一批核心录制和 GUI 链路已通过，目录重建和重新定位两项发布阻塞已在新候选包关闭；结果条超时后的持久重试入口已确认延后，不再阻塞 v1.6；三档 DPI 人工补证已通过。v1.6 可以进入发布收口确认点。

## 8. Bugfix 自动验证与定向复验

- Bugfix1 候选目录已在最终候选锁定后清理，以下 SHA256 和证据目录继续用于历史追溯。
- SHA256：`69D092DDAF48757D4941429AB10D74072EE2E0B9ED07783CA43BE9D7C8F3551F`
- 自动验证：受影响回归 84 passed；全量 339 passed、24 deselected、22 subtests passed；packaging 12 passed；coverage 83.65%；ruff、mypy、compileall 通过。
- 目录重建：通过，2 个有效 MP4 完整入库，1 个损坏 MP4 被拒绝。
- 重新定位：通过，损坏文件不修改原索引，失败后可继续定位；有效文件更新完整元数据并经重启保持。
- 手动导入：通过，有效文件 1 条入库，损坏 MP4 与非视频共 2 条跳过。
- 证据目录：`E:\QRtest\QuickRec-v1.6-bugfix-acceptance\evidence`。

## 9. Bugfix3 剩余边界复验

- 最终候选：`E:\QRtest\QuickRec-v1.6-bugfix3-dist\QuickRec\QuickRec.exe`
- SHA256：`F1C8F2F971D5DD62067955B939D5DB9293C13DA930D1DFC653007F59596392E8`
- 无备份损坏恢复：通过；损坏索引可由确认后的目录重建替换，原损坏文件已归档。
- 0/1 条边界：通过；空状态详情已完全清空。
- 回收站失败：通过；锁定文件触发 `WinError 32`，视频和索引均保留。
- DPI：用户于 2026-07-13 完成 100%、125%、150% 下四类界面人工验证，全部通过；详见 `manual-dpi-verification.md`。
- 证据目录：`E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\evidence`。

## 10. 最终发布前判断（2026-07-13）

- D7 总体结论：通过。
- 发布阻塞：无。
- 已知限制：结果条超时后的持久“重试入库”入口延后到后续版本，不阻塞 v1.6。
- 环境恢复：QuickRec 进程已停止，受控视频与隔离索引存在，临时重定位文件不存在，QuickRec Lite 工作区干净。
- 下一阶段：可以进入发布收口；用户已于后续步骤授权执行 commit、push、tag 和 GitHub Release。

## 11. 正式发布包复核（2026-07-13）

- 发布源提交：`c2c9b27147c96ee01518651fa6d3578c4615d8ce`。
- 正式 EXE：`E:\QRtest\QuickRec-v1.6-release-dist\QuickRec\QuickRec.exe`。
- EXE SHA256：`99D7309E8C3BA3F46F7322D9CD79E1126F1C4DD333E1F581B9110EEA26406290`。
- 发布 ZIP：`E:\QRtest\QuickRec-v1.6-win-x64.zip`。
- ZIP SHA256：`30F002F8E085220E86C37B1EC672A47739560A80488743A4D6EDE1DB9FED6C69`。
- 包内 FFmpeg、FFprobe 存在；FFprobe 可解析最终 smoke 视频。
- 隔离基础启动保持运行 4 秒，结果通过。
- 最终全屏硬件 smoke：`OK: video stream ok`，证据文件 `E:\QRtest\QuickRec-v1.6-release-smoke\QuickRec_20260713_190501.mp4`。
- 全量测试 340 passed，coverage 83.75%，packaging 12 passed；ruff、mypy、compileall 通过。
