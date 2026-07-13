# QuickRec Full 当前事实入口

## 当前定位

- 产品线：QuickRec Full
- 当前版本：v1.5
- 当前发布分支：`master`
- 当前标签：`v1.5`
- 当前工作区：`E:\codex\QuickRec`
- 验收产物：`E:\QRtest\QuickRec-v1.5-dist\QuickRec\QuickRec.exe`
- 验收产物 SHA256：`C2BFECA3BA6204D3EE078F6A9D7E0E17389373CEB2747421868317D55B4D9FC4`
- GitHub Release 资产：`QuickRec-v1.5-win-x64.zip`
- GitHub Release：[QuickRec Full v1.5](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.5)
- 发布 ZIP SHA256：`4B7F1F15DCFBDA8AA988B712D101FDA37682FEAF33749FAB701337C6E07C04B4`

`v1.4.1` tag 固定指向诊断导出发布提交 `16c7dce feat(v1.4.x): add diagnostic export workflow`。本工作区当前 `master` 后续 HEAD 可能包含 post-split 文档治理提交，但不得移动或重写 `v1.4.1` tag。

## 当前发布状态

v1.5 已完成开发、自动化验证、全屏硬件 smoke、独立打包和 D6.3 GUI/原型验收，当前无发布阻塞项，作为 QuickRec Full 当前正式版本发布。

v1.6 轻量素材库基础版当前位于 `feature/v1.6-material-library`。中央索引、迁移恢复、素材库 UI、会话元数据和回收站接口已完成实现；自动化、独立打包、硬件 smoke 和 D7 GUI 手动验收均已通过，当前无发布阻塞，正在执行正式发布收口。在 `v1.6` tag 和 GitHub Release 创建完成前，v1.5 仍是远端正式版本。

v1.4.1 在 v1.4 稳定性与工程化基线之上新增诊断导出能力，仍是当前明确的代码与发布包回滚点。

## 当前版本文档

- PRD：`doc/releases/v1.5/prd.md`
- 实施计划：`doc/releases/v1.5/dev_plan.md`
- 进度：`doc/releases/v1.5/progress.md`
- 手动验收：`doc/releases/v1.5/manual-verification.md`
- Bugfix：`doc/releases/v1.5/bugfix-log.md`
- 捕获后端研究：`doc/releases/v1.5/capture-backend-spike.md`
- 发布说明：`doc/releases/v1.5/release-notes.md`
- 变更日志：`doc/releases/v1.5/changelog.md`

## 当前开发版本文档

- v1.6 PRD：`doc/releases/v1.6/prd.md`
- v1.6 实施计划：`doc/releases/v1.6/dev_plan.md`
- v1.6 进度：`doc/releases/v1.6/progress.md`
- v1.6 测试用例：`doc/releases/v1.6/test-cases.md`
- v1.6 开发日志：`doc/releases/v1.6/dev_log.md`
- v1.6 缺陷记录：`doc/releases/v1.6/bugfix-log.md`
- v1.6 发布说明：`doc/releases/v1.6/release-notes.md`
- v1.6 变更日志：`doc/releases/v1.6/changelog.md`
- v1.6 验证汇总：`doc/releases/v1.6/verification.md`
- v1.6 GUI 手动验收：`doc/releases/v1.6/manual-verification.md`

## 历史与支撑文档

- 产品总 PRD：`doc/product/PRD-QuickRec.md`
- v1.4 历史发布资料：`doc/releases/v1.4/`
- 技术设计与历史实施计划：`doc/technical/`
- 历史测试用例：`doc/verification/`
- 原型资料：`doc/prototypes/`
- 历史想法池和日志归档：`doc/archive/`

QuickRec Lite 已拆分到 `E:\codex\QuickRec-Lite`，不属于 Full 当前工作区范围。
