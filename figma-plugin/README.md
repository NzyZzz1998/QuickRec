# QR Full v1.7 Figma Development Plugin

这是 QuickRec 项目内的本地 Figma Development Plugin，用于在 Figma Desktop 中生成可编辑的 QR 产品设计。它不调用 Figma MCP，也不消耗 Starter MCP 配额。

## 页面范围

插件只维护一个页面：

1. `QR 01 Full Product Flow`

插件会清空并重建名称完全匹配的 `QR 01 Full Product Flow`。旧的 `QR 00 Foundations & Components` 和 `QR 02 Material Library States` 会按精确名称删除；其内容已经合并进 QR 01。其他页面不会被删除或修改。

## 生成内容

- QuickRec 原始变量与语义变量；
- 中文桌面端文字样式和阴影样式；
- Button、Search Field、Select、Status Chip、Navigation Item、Material Row 核心组件；
- 托盘录制、视频保存、中央索引、素材查询与文件操作产品链路；
- v1.7 素材搜索、筛选、排序、待入库与正式素材状态；
- 空状态、无结果、查询异常、文件缺失和信息不完整状态；
- QuickRec 静态 PNG 品牌标记，写入 Figma 后逐字节校验。
- 按当前 PyQt 运行界面尺寸重建的全可编辑原型；Figma 画布不嵌入运行截图。

其中 `QR 01 Full Product Flow` 是完整 UI Atlas 大画布，集中包含：

- 空闲、录制中和暂停三种托盘菜单；
- 区域选择拖拽、确认、过小提示，以及窗口选择与目标高亮；
- 倒计时、录制中、暂停、保存中、保存成功和索引失败六种工具栏状态；
- 完整设置、快捷键、诊断操作和反馈；
- 素材库默认、空状态、无结果、查询异常、待入库和文件缺失状态；
- 重新定位、仅移除索引、移入回收站、导入旧目录和目录重建确认；
- 保存成功、索引失败、窗口丢失和磁盘空间不足等系统反馈。

画布顶部提供页面关系总览：主链覆盖“托盘入口 → 录制模式 → 选择/倒计时 → 录制工具栏 → MP4 保存 → 素材索引 → 素材库 → 素材操作”；设置、诊断和索引失败重试作为支线与主链关联。各界面分区统一使用 5120px 栅格、24px 内边距、18px 组内间距和顶部对齐。

按钮交互契约不再集中放在画布最前面。每个产品分区都按“局部流程 → 可编辑原型 → 本区控件契约”排列，使说明与对应窗口保持在同一视觉上下文。当前共覆盖 57 个按钮或可点击控制入口，每项均注明所在界面、显示条件、事件入口、前端状态变化、后端调用、成功结果及失败/取消语义。

设置页、素材库、窗口选择器、区域选择、工具栏和确认弹窗已经使用运行截图完成一次深度校准；对应可编辑稿采用 440×447、980×560、460×340、900×520、40px 工具栏高度及 Windows 原生确认框比例。截图只作为本轮校准输入，不写入生成后的 Figma 页面。

每条契约使用稳定的 `B-xxx` 编号。编号与完整契约同时写入对应 Figma 控件节点的 `quickrec/button-contract-ids` 和 `quickrec/button-contract` Shared Plugin Data；选中控件即可反查同区契约卡。普通 Frame 不依赖 Figma 组件描述能力，避免运行时兼容问题。

`RecentRecordingsDialog` 仅作为历史保留模块标注，因为当前 `main.py` 已没有产品入口；系统文件选择器、通知中心和 Windows 回收站则作为原生系统边界说明。

## 构建与验证

```powershell
powershell -ExecutionPolicy Bypass -File "E:\codex\QuickRec\figma-plugin\build.ps1"
powershell -ExecutionPolicy Bypass -File "E:\codex\QuickRec\figma-plugin\test-plugin.ps1"
```

构建会生成确定性的 `assets\quickrec-mark.png`，并以 Base64 嵌入 `ui.html`。验证覆盖页面数量、非 QR 页面保护、JavaScript 语法、品牌 PNG 格式与哈希、截图零嵌入、关键原型尺寸、UTF-8/乱码和 `git diff --check`。

## Figma Desktop 导入

1. 运行上面的构建和验证命令。
2. 使用 Figma Desktop 打开目标 Design 文件。
3. 选择 `Plugins > Development > Import plugin from manifest...`。
4. 选择 `E:\codex\QuickRec\figma-plugin\manifest.json`。
5. 运行 `Plugins > Development > QR Full v1.7 Design Builder`。
6. 点击“生成 / 更新 QR 设计”。

插件可重复运行；再次运行只更新一个 QR 页面、两个 QR 变量集合和 `QR/` 前缀样式，不产生重复内容。

## Starter 边界

- 插件只生成一个 QR 页面，低于 Starter 的三页限制。
- 本地变量、样式和组件可在当前文件内编辑和复用。
- Starter 不能将这些内容发布为跨文件团队 Library。
