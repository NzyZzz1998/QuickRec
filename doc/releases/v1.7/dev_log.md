# QuickRec Full v1.7 开发日志

> 状态：实施中
> 事实源：[prd.md](prd.md)、[dev_plan.md](dev_plan.md)、[progress.md](progress.md)
> 记录边界：只记录实施批次、关键改动、验证摘要和未闭合风险。

## 2026-07-18 D0 开发基线

- v1.6.1 已完成 `master`、annotated tag、GitHub Release 和发布资产闭环。
- v1.6.1 tag 指向 `cf5cec8e44b3a2b74a247cb94c0206ade7e8c13a`。
- v1.7 `test` 分支已合入 v1.6.1 正式发布文档提交，合并前 v1.7 PRD/原型提交为 `fcad0e0`。
- QuickRec Lite 工作区保持干净。
- v1.7 PRD 与原型已确认，用户授权继续开发。
- 下一步：建立查询与会话状态失败测试，再实现纯查询模块。

## 2026-07-18 D1-D4 查询主链路

- 新增 `services.material_query`，统一正式素材与待入库素材的搜索、筛选、稳定排序、时间范围和分页前查询。
- 新增 `services.material_query_session`，负责进程内条件、正式素材可见数量、条件变化重置和查询异常保留。
- 素材库增加搜索框、四类筛选、六项排序、匹配计数、重置入口和 150 ms 防抖。
- 现有打开、重建、导入、重定位、移除、回收站和待入库重试继续使用原服务，通过统一 `reload()` 保持查询条件刷新。
- 补充 0/1/49/50/51/199/200 条分页边界、未知枚举、非法时间、空元数据、隐私日志与 UI 异常保留测试。

## 2026-07-18 D5 工程门禁与候选包

- 查询与会话模块定向覆盖率 89.80%，全项目覆盖率 84.54%。
- 全量测试 398 passed、24 deselected、40 subtests passed；packaging 12 passed、410 deselected。
- Ruff、Mypy、Compileall 与 `git diff --check` 通过。
- PyInstaller 显式收集两个新增服务模块，独立候选包构建成功。
- 候选 EXE：`E:\QRtest\QuickRec-v1.7-candidate-dist\QuickRec\QuickRec.exe`。
- EXE SHA256：`3009ABC7B3FA54917B516756D36A35F867353301838E01CC054F48381A53BE74`。
- 包内 FFmpeg 已生成中文与空格路径样本，FFprobe 成功解析 320×240、30 FPS、1 秒视频。
- 隔离 APPDATA 基础启动通过；下一步进入 D6 GUI、DPI 与录制回归验收。
