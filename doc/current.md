# QuickRec Lite 当前事实入口

## 当前定位

- 产品线：QuickRec Lite
- 当前版本：Lite v0
- 当前分支：`lite-master`
- 当前标签：`lite-v0`
- 当前工作区：`E:\codex\QuickRec-Lite`
- 当前发布产物：`E:\codex\QuickRec-Lite\dist\QuickRec\QuickRec.exe`

`lite-v0` tag 固定指向 Lite v0 版本点 `c15940e feat: prepare QuickRec Lite v0`。本工作区后续 HEAD 可能包含 post-split 文档治理提交，但不得移动或重写 `lite-v0` tag。

## Lite v0.1 开发起点

截至 2026-08-11，`lite-test` 已安全快进到 `lite-master` 当前治理基线
`cfaee3e`，作为 Lite v0.1 的开发起点；`lite-v0` tag 仍固定指向
`c15940e`，未移动、覆盖或重写。

当前基线验证：

```text
pytest: 232 passed, 23 deselected, 18 subtests passed
coverage: 81.68%（门禁 80%）
ruff: 通过
mypy: 9 个配置源文件通过
compileall: 通过
最近远端 Lite CI: https://github.com/NzyZzz1998/QuickRec/actions/runs/30248077030
```

Lite v0.1 已确认的首要问题不是增加录制模式，而是 Full/Lite 运行身份仍然冲突：

- 配置仍写入 `%APPDATA%\QuickRec\config.json`；
- 临时录制目录仍使用 `%TEMP%\QuickRec`；
- PyInstaller 分发目录、可执行文件和进程仍命名为 `QuickRec`；
- 开机启动注册表项仍命名为 `QuickRec`；
- 托盘、通知标题、通知 `app_id` 和日志命名空间仍使用 Full 身份；
- Lite 尚无独立运行时版本事实源；
- 区域/窗口录制、倒计时和光标相关代码仍在运行图或打包边界中，仅用户入口不可见。

Lite v0.1 推荐保持单一产品主线：**Full/Lite 运行身份隔离**。支撑范围只允许
配置原子保存等稳定性能力白名单回迁、不可达代码治理，以及独立 CI/发布门禁；
继续排除工作台、素材库、项目、诊断中心、区域/窗口录制、120 FPS 和高刷能力。

当前状态为 **PRD 待确认、尚未修改业务代码**。配置迁移会接触既有
`%APPDATA%\QuickRec`，实现前必须先冻结“不移动、不删除 Full 数据，只对白名单
设置提供安全复制”的迁移合同。

## 当前范围

Lite v0 是 QuickRec 的第一个轻量化版本，当前只保留全屏录制、基础音频录制、托盘控制、设置页和打包发布链路。

区域录制、窗口录制、鼠标高亮、倒计时和 QuickRec Full v1.4.1 诊断导出能力不属于 Lite v0 当前范围。

## 当前版本文档

- PRD：`doc/releases/lite-v0/prd.md`
- 实施计划：`doc/releases/lite-v0/dev_plan.md`
- 进度：`doc/releases/lite-v0/progress.md`
- 测试用例：`doc/releases/lite-v0/test-cases.md`
- 发布说明：`doc/releases/lite-v0/release-notes.md`
- 开发日志：`doc/releases/lite-v0/development-log.md`

## 当前工程门禁

- CI：`.github/workflows/ci.yml`
- 测试触发：`lite-master` / `lite-test` push，以及目标为这两个分支的 Pull Request。
- 打包触发：`lite-master`、`lite-test` 和 `lite-v*` push。
- 打包门禁：Windows PyInstaller onedir 构建、`QuickRec.exe` 与内置 `ffmpeg.exe` 存在性和可执行性检查。

Lite v0 的可选体积实验已延期，不影响 `lite-v0` 作为当前基线版本点。

## Full 历史资料归属

QuickRec Lite 不维护 Full v1.x 历史 PRD、技术设计、验证资料、发布记录、v1.4.1 诊断导出文档或 Full Workbench 原型副本。

如需查看 Full 历史资料，请转到 `E:\codex\QuickRec`：

- 产品 PRD：`E:\codex\QuickRec\doc\product\PRD-QuickRec.md`
- 技术设计：`E:\codex\QuickRec\doc\technical\`
- 验证资料：`E:\codex\QuickRec\doc\verification\`
- v1.4 发布资料：`E:\codex\QuickRec\doc\releases\v1.4\`
- v1.4.1 诊断导出资料：`E:\codex\QuickRec\doc\releases\v1.4.1\`
- 原型资料：`E:\codex\QuickRec\doc\prototypes\`
