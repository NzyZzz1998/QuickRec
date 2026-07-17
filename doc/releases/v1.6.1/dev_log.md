# QuickRec Full v1.6.1 开发日志

> 版本：v1.6.1  
> 状态：正式发布
> 事实源：[prd.md](prd.md)、[dev_plan.md](dev_plan.md)、[progress.md](progress.md)  
> 记录边界：只记录实施批次、关键改动、验证摘要与未闭合风险。

## 2026-07-15 D0 基线

- 本轮目标：固定 Full/Lite/Git 基线，建立过程文档和测试先行入口。
- Full 起始 `master` HEAD：`83494cd51f6bd78885c528d6fc333fd07b101848`。
- v1.6 tag 指向：`ac8d151aababb5e7c37b3dcc646ae10c8593acf3`。
- 开发分支：`feature/v1.6.1-pending-ingestion`。
- Lite：`lite-master`，起始状态干净。
- 保护项：Full `README.md` 的既有换行状态不属于本轮实现，不做重写或回退。
- 下一步：建立隔离夹具并先写失败测试。

## 2026-07-15 D1-D5 核心实现

- 新增主待入库文件与视频目录降级标记，均使用 UTF-8 JSON 和原子替换。
- 新增待入库发现、合并、缺失检测、重新定位和仅移除记录服务。
- 新增统一入库协调器，正式索引失败时保持视频保存成功并持久化恢复上下文。
- 接入启动后台自动重试、结果条短时重试和素材库持久恢复入口。
- 素材库增加待入库置顶区、独立计数、状态详情和恢复操作。
- PyInstaller 明确纳入新增运行时模块，保留 FFmpeg 与 FFprobe。

## 2026-07-15 D6 自动化门禁

- 全量测试：374 passed、24 deselected、22 subtests passed。
- 全项目覆盖率：83.99%；待入库存储 89%、待入库服务 81%、入库协调器 85%。
- Packaging：12 passed。
- Ruff、项目配置范围内 mypy、compileall、UTF-8/乱码检查和 `git diff --check` 通过。
- QuickRec Lite 工作区保持干净。
- 下一步：独立打包并锁定 v1.6.1 候选产物，随后进入硬件与 GUI 验收。

## 2026-07-17 D7 验收收口

- 修复双音频 9 声道混音失败与回环设备误选问题，锁定 audiofix2 最终候选包。
- 修复后全量测试 376 passed、24 deselected、22 subtests passed；packaging 12 passed，静态门禁通过。
- 核心待入库链路、录制与音频、设置诊断、素材库、容量边界和三档 DPI 验收通过。
- 最终候选 EXE SHA256：`2CB447709769A8A986B7A48A63C98377803A002ED56892E57F0911661FA3E092`。
- 当前无发布阻塞；用户已授权完成 `master`、`v1.6.1` tag 与 GitHub Release 发布闭环。
