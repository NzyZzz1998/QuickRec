# QuickRec Full v1.5

v1.5 是 QuickRec Full 在 v1.4.1 诊断导出版本之后的 **捕获体验与创作者工作台地基版**。

## 当前状态

- 产品线：QuickRec Full
- 目标版本：v1.5
- 发布状态：开发、自动化验证、硬件 smoke、独立打包和 D6.3 验收均已完成，正式发布
- 当前主线：移除自绘光标叠加风险，保留鼠标点击高亮；以录制历史 / 素材入库作为 Full 创作者工作台的第一步；WGC 等新捕获后端仅作为技术研究，不替换默认链路。

## 文档清单

- `prd.md`：v1.5 完整可开发 PRD。
- `dev_plan.md`：v1.5 开发计划，包含实施顺序、影响文件、测试命令、风险与回退。
- `progress.md`：v1.5 进度看板，按模块拆分 Vibe Coding 最小任务 checklist。
- `manual-verification.md`：D6.3 GUI、录制文件、历史 JSON、日志和原型验收记录。
- `bugfix-log.md`：发布前确认并关闭的缺陷记录。
- `capture-backend-spike.md`：WGC 等捕获后端研究结论，不进入本版运行时。
- `release-notes.md`：面向发布使用者的版本能力、证据、限制和回滚说明。
- `changelog.md`：面向维护者的结构化变更清单。

## 与历史版本关系

- v1.4 是稳定性与工程化基线。
- v1.4.1 是诊断导出能力补充版本。
- v1.5 不回退 v1.4.1 已完成的诊断导出能力，不改 Lite 范围，不直接实现完整创作者工作台。

## 注意事项

验收 EXE 位于 `E:\QRtest\QuickRec-v1.5-dist\QuickRec\QuickRec.exe`，SHA256 为 `C2BFECA3BA6204D3EE078F6A9D7E0E17389373CEB2747421868317D55B4D9FC4`。该产物已完成 D6.3 验收，正式发布资产为 `QuickRec-v1.5-win-x64.zip`。
