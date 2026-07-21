# QuickRec Full 当前事实入口

## 当前定位

- 产品线：QuickRec Full
- 当前正式版本：v1.7
- 当前发布分支：`master`
- 当前标签：`v1.7`
- 当前工作区：`E:\codex\QuickRec`
- v1.6 tag 提交：`ac8d151aababb5e7c37b3dcc646ae10c8593acf3`
- v1.6.1 功能实现提交：`8a1ee4710de70d5dd74c2478771a50a762b528ca`
- v1.6 本地历史展开包：已清理，可从 GitHub Release 重新下载
- GitHub Release 资产：`QuickRec-v1.6-win-x64.zip`
- GitHub Release：[QuickRec Full v1.6](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.6)
- 发布 ZIP SHA256：`30F002F8E085220E86C37B1EC672A47739560A80488743A4D6EDE1DB9FED6C69`
- v1.6.1 发布资产：`QuickRec-v1.6.1-win-x64.zip`
- v1.6.1 Release：[QuickRec Full v1.6.1](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.6.1)
- v1.6.1 ZIP SHA256：`CE72D690DD46950C46CDEE2F3999B6F64E6DC0362B20CAC21FC53A34FCE197CF`
- v1.6.1 锁定 EXE SHA256：`2CB447709769A8A986B7A48A63C98377803A002ED56892E57F0911661FA3E092`
- v1.6.1 验收证据：`E:\QRtest\QuickRec-v1.6.1-acceptance`
- v1.7 当前状态：正式发布
- v1.7 候选 EXE：`E:\QRtest\QuickRec-v1.7-candidate-fix1-dist\QuickRec\QuickRec.exe`
- v1.7 EXE SHA256：`8966985B6E1EBCEDC27499404BF8467133EFCC9C6A827898D8904CE137E15AF2`
- v1.7 发布资产：`QuickRec-v1.7-win-x64.zip`
- v1.7 Release：[QuickRec Full v1.7](https://github.com/NzyZzz1998/QuickRec/releases/tag/v1.7)
- v1.7 ZIP SHA256：`0C200C549D1E4ED495BC381298E1A3157B1534526337899DB9ED9C655A37E963`
- v1.7 验收证据：`E:\QRtest\QuickRec-v1.7-acceptance`

`v1.4.1` tag 固定指向诊断导出发布提交 `16c7dce feat(v1.4.x): add diagnostic export workflow`。本工作区当前 `master` 后续 HEAD 可能包含 post-split 文档治理提交，但不得移动或重写 `v1.4.1` tag。

## 当前发布状态

v1.6 轻量素材库基础版已完成开发、自动化验证、独立打包、硬件 smoke 和 D7 GUI 手动验收，作为 v1.6.1 的直接代码与发布包回滚点保留。

v1.6.1 已完成开发、自动化门禁、独立打包与 GUI 手动验收，作为 v1.7 的直接回滚点保留。

v1.7 已完成素材搜索、筛选、排序、待入库分区和异常降级能力，自动化与 D6 GUI 技术验收通过，现作为 QuickRec Full 当前正式版本发布。

v1.6 tag 是 v1.6.1 的直接代码回滚点；回滚不会删除待入库主文件、降级标记或视频文件。

v1.5 与 v1.4.1 继续作为历史稳定发布点保留，其中 v1.4.1 固定承载诊断导出发布成果。

## 当前版本文档

- PRD：`doc/releases/v1.6.1/prd.md`
- 实施计划：`doc/releases/v1.6.1/dev_plan.md`
- 进度：`doc/releases/v1.6.1/progress.md`
- 测试用例：`doc/releases/v1.6.1/test-cases.md`
- 手动验收：`doc/releases/v1.6.1/manual-verification.md`
- 验证汇总：`doc/releases/v1.6.1/verification.md`
- Bugfix：`doc/releases/v1.6.1/bugfix-log.md`
- 发布说明：`doc/releases/v1.6.1/release-notes.md`
- 变更日志：`doc/releases/v1.6.1/changelog.md`

## v1.7 当前版本文档

- PRD：`doc/releases/v1.7/prd.md`
- 实施计划：`doc/releases/v1.7/dev_plan.md`
- 进度：`doc/releases/v1.7/progress.md`
- 手动验收：`doc/releases/v1.7/manual-verification.md`
- 验证汇总：`doc/releases/v1.7/verification.md`
- Bugfix：`doc/releases/v1.7/bugfix-log.md`
- 发布说明：`doc/releases/v1.7/release-notes.md`
- 变更日志：`doc/releases/v1.7/changelog.md`

## 当前版本过程记录

- 开发日志：`doc/releases/v1.6.1/dev_log.md`

v1.6 正式发布资料继续保留在 `doc/releases/v1.6/`，作为直接回滚依据。

## 历史与支撑文档

- 产品总 PRD：`doc/product/PRD-QuickRec.md`
- v1.4 历史发布资料：`doc/releases/v1.4/`
- 技术设计与历史实施计划：`doc/technical/`
- 历史测试用例：`doc/verification/`
- 原型资料：`doc/prototypes/`
- 历史想法池和日志归档：`doc/archive/`

QuickRec Lite 已拆分到 `E:\codex\QuickRec-Lite`，不属于 Full 当前工作区范围。
