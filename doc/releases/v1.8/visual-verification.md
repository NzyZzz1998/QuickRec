# QuickRec Full v1.8 视觉实现核对

## 1. 核对对象

- 原型事实源：`doc/releases/v1.8/prototype/index.html`
- 原型规范：`doc/releases/v1.8/prototype/prototype-design.md`
- 实现范围：工作台四页、录制结果状态、素材空/缺失状态、区域选择器、窗口选择器、倒计时及录制工具栏。
- 实现截图脚本：`scripts/capture_v18_ui_implementation.py`
- 最终截图根目录：`E:\QRtest\QuickRec-v1.8-dpi-r11-20260725-windows`
- 截图环境：Windows Qt 平台插件，分别设置 100%、125%、150% Qt 缩放。
- 证据边界：脚本只构造受控索引和界面状态；其中示例文件用于视觉核对，不作为视频可播放或录制链路证据。

## 2. 逐页核对

| 界面 | 主要证据 | 结论 | 与原型的差异及处理 |
| --- | --- | --- | --- |
| 录制页 | `dpi-100/workbench-recording-100.png` | 通过 | 三类录制模式、参数摘要、状态区与设置入口已落地；使用原生 PyQt 控件，不复制浏览器表现。 |
| 录制成功 | `dpi-100/workbench-recording-result-100.png` | 通过 | 工作台来源在页内展示文件、大小、入库状态及后续操作，不重复弹出结果条。 |
| 录制失败 | `dpi-100/workbench-recording-failure-100.png` | 通过 | 使用红色错误语义并保留诊断引导；不伪造输出文件。 |
| 素材库 | `dpi-100/workbench-materials-100.png` | 通过 | 搜索、筛选、排序、列表、详情和素材操作均并入工作台。 |
| 素材空状态 | `dpi-100/workbench-materials-empty-100.png` | 通过 | 保留克制的空状态文案，不引入与本版范围无关的素材预览。 |
| 素材缺失状态 | `dpi-100/workbench-materials-missing-100.png` | 通过 | 详情明确显示“文件已移动或删除”，打开禁用，重新定位保留。 |
| 设置页 | `dpi-100/workbench-settings-100.png` | 通过 | 录制参数、行为、快捷键和显式保存均可见；底栏与滚动内容分离。 |
| 设置最小尺寸 | `dpi-100/workbench-settings-min-100.png` | 通过 | 960×640 下保存栏不覆盖字段，超出内容通过独立滚动区访问。 |
| 诊断页 | `dpi-100/workbench-diagnostics-100.png` | 通过 | 诊断目录、复制、打开目录、导出及显式保存独立成页。 |
| 窗口选择器 | `dpi-100/window-selector-100.png` | 通过 | 标题、说明、列表、数量和操作区纵向排列，未复现原型早期横向挤压。 |
| 区域选择器 | `dpi-100/area-selector-100.png` | 通过 | 遮罩、选区确认、取消和底部操作提示保持独立浮层。 |
| 录制工具栏 | `dpi-100/toolbar-recording-100.png` | 通过 | 状态灯、计时、暂停、停止和取消采用统一深色样式。 |
| 暂停工具栏 | `dpi-100/toolbar-paused-100.png` | 通过 | 暂停状态使用黄色语义，继续操作保持原位置。 |
| 倒计时 | `dpi-100/toolbar-countdown-100.png` | 通过 | 与录制工具栏复用同一外壳和宽度过渡。 |
| 保存中 | `dpi-100/toolbar-saving-100.png` | 通过 | 保存状态明确，录制操作禁用。 |
| 结果条 | `dpi-100/toolbar-result-100.png` | 通过 | 文件大小及全部操作完整显示；截图在 180ms 宽度动画结束后采集。 |
| 120 FPS 检测中 | `dpi-125/self-test-running-125.png` | 通过 | `42%` 使用常规数字字形并保持居中。 |
| 120 FPS 检测通过/失败 | `dpi-150/self-test-passed-150.png`、`self-test-failed-150.png` | 通过 | 终态使用矢量符号，状态文案和操作按钮完整。 |
| 120 FPS 快速校验 | `dpi-150/dialog-120-readiness-150.png` | 通过 | 重新检测、改用 60 FPS和取消的动作层级完整。 |
| 性能告警结果 | `dpi-150/workbench-recording-performance-warning-150.png` | 通过 | 视频保存成功与未稳定达到 120 FPS 分开表达，不误报保存失败。 |
| 未保存设置确认 | `dpi-150/dialog-unsaved-settings-150.png` | 通过 | “保存 / 放弃 / 取消”完整且无重叠。 |
| 回收站确认 | `dpi-150/dialog-recycle-bin-150.png` | 通过 | “是 / 否”中文按钮完整，危险操作语义明确。 |

## 3. DPI 核对

| 缩放 | 证据目录 | 结论 |
| --- | --- | --- |
| 100% | `E:\QRtest\QuickRec-v1.8-dpi-r11-20260725-windows\dpi-100` | 四页、最小设置页、关键弹窗和全部浮动状态无裁切、重叠或不可读文本。 |
| 125% | `E:\QRtest\QuickRec-v1.8-dpi-r11-20260725-windows\dpi-125` | 设置页启用滚动且固定底栏完整；按钮、百分比和状态文字完整。 |
| 150% | `E:\QRtest\QuickRec-v1.8-dpi-r11-20260725-windows\dpi-150` | 录制卡、素材详情、工具栏、选择器和确认框均保持可读。 |

## 4. 组件与实现约束

- 设计令牌和统一样式位于 `src/ui/design_system.py`。
- 图标由确定性 `QPainter` 线性路径生成，不依赖被打包配置排除的 `QtSvg`。
- 全局中文界面优先使用 `Microsoft YaHei UI`，英文和数字回退到 `Segoe UI`。
- 浮动工具栏按内容自然宽度切换，并以中心为锚点执行 180ms `OutCubic` 过渡。
- 素材操作采用稳定两列布局；危险操作使用红色语义且文案明确为“移入回收站”。
- 长保存路径在录制摘要中压缩显示，完整路径保留在工具提示中。
- 设置页在 960×640 下将表单放入独立滚动区，保存底栏始终位于内容区底部且不覆盖表单。

## 5. 尚未闭合

- D7.13 仅完成现有未保存、素材操作和区域选择确认的视觉统一。
- 120 FPS 自检弹窗的运行、通过和失败状态已纳入三档截图；真实取消清理和查看诊断业务链路仍以候选包 GUI 验收为准。
- 磁盘空间系统弹窗仍沿用现有原生 `QMessageBox`，其业务语义和阻断规则未改变。
- 本文是自动视觉核对，不替代候选包的真实托盘、录制、系统弹窗和硬件 GUI 验收。
