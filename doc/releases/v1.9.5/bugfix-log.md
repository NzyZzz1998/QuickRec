# QuickRec Full v1.9.5 缺陷修复记录

## BUG-195-01 录制工具栏动画后回落到屏幕中部

| 项目 | 内容 |
| --- | --- |
| 发现阶段 | D9 RC2 GUI 验收 |
| 严重度 | 发布阻塞 |
| 影响范围 | 全屏、区域、窗口录制工具栏 |
| 首次失败候选 | `E:\QRtest\QuickRec-v1.9.5-rc2-dist\QuickRec` |
| 修复候选 | `E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec` |
| 当前状态 | 已修复并完成三种模式定向复验 |

### 复现与证据

RC2 在 `2560×1440`、可用高度 `1392` 的单显示器环境中开始全屏录制后，
工具栏最终矩形为：

```text
left=959, top=672, width=334, height=48
```

`top=672` 位于屏幕垂直中部，不符合“实际录制屏幕中上安全区”的产品合同。
因此 RC2 立即失效，不再作为最终验收身份。

### 根因

开始录制时，工具栏先通过零延迟定时器移动到目标屏幕顶部安全区；随后
`_transition_to_content_width()` 的宽度动画仍使用动画开始前的旧几何位置。
动画结束时旧的 `y=672` 被重新写回，覆盖了已经完成的顶部定位。

根因不是屏幕探测、DPI 换算或窗口管理器随机行为，而是同一控件的定位与宽度
动画分别持有不同几何目标。

### 最小修复

- 在 `src/ui/toolbar.py` 中让宽度过渡可选择同时重算目标屏幕位置。
- 抽取统一的 `_target_position(width, height)`，定位与动画使用同一结果。
- 倒计时和正式录制进入紧凑宽度时都启用目标屏幕重新定位。
- 删除会与动画竞争的零延迟二次定位。
- 在 `tests/test_toolbar.py` 增加回归测试，证明宽度动画完成后仍保持顶部安全区。

### 自动回归

```text
tests/test_toolbar.py + tests/test_toolbar_placement.py：
24 passed

工具栏、主流程、工作台与 Packaging 定向回归：
102 passed, 13 deselected

最终全量：
1425 passed, 32 deselected, 72 subtests passed
```

Ruff、项目配置范围 Mypy、Compileall、Coverage、Packaging 和
`git diff --check` 均通过。

### RC3 定向复验

RC3 在同一显示环境中分别执行全屏、区域和窗口录制，三个模式最终矩形均为：

```text
left=1113, top=139, width=334, height=48
```

水平中心偏差为 `0 px`，`top=139` 与顶部安全区目标一致。三种录制均成功保存
60 FPS H.264 MP4，并写入隔离中央素材索引。

证据：

```text
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-K-toolbar-position.json
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-K-toolbar-fullscreen-top-safe-area.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-K-toolbar-region-top-safe-area.png
E:\QRtest\QuickRec-v1.9.5-rc3-acceptance\evidence\D9-K-toolbar-window-top-safe-area.png
```

结论：`BUG-195-01` 已关闭；RC3 取代 RC2 成为唯一有效候选包。
