# QuickRec Full v1.5 Bugfix Log

## BUG-V15-P1-001 原型缺少最近录制空状态

- 状态：已修复并复验通过。
- 发现阶段：D6.3 GUI / 原型验收。
- 影响范围：仅 `doc/prototypes/product-prototype/full.html` 的原型表达，不影响当前录制、历史 JSON 或最近录制窗口实现。
- 现象：原型可通过本地 HTTP 正常加载，最近录制入口、列表、缺失记录、复制路径反馈和从列表移除均可操作，但页面没有“暂无录制记录”或等价空状态。
- 证据：
  - `E:\QRtest\v1.5-acceptance\evidence\V15-P1-prototype.png`
  - `E:\QRtest\v1.5-acceptance\evidence\V15-P1-prototype-missing-state.png`
  - `E:\QRtest\v1.5-acceptance\evidence\V15-P1-auto-before.png`
  - `E:\QRtest\v1.5-acceptance\evidence\V15-P1-auto-after.png`
  - `E:\QRtest\v1.5-acceptance\evidence\V15-P1-auto-record.png`
  - Playwright 结果：`status=200`、`recentActive=true`、`missingBefore=1`、`copyTextAfter100ms=已复制`、`emptyStatePresent=false`。
- 根因：原型只包含静态示例列表和缺失记录移除逻辑，没有空状态节点或状态切换入口；现有 `.row { display: flex; }` 还会覆盖元素的 `hidden` 展示行为。
- 修复：新增“演示空状态 / 恢复示例记录”按钮与空状态节点，并为 `.row[hidden]` 明确设置 `display: none`；不修改业务代码。
- 复验证据：`E:\QRtest\v1.5-acceptance\evidence\V15-P1-empty-state-fixed.png`。
- 复验结果：HTTP 200；空状态可见、记录数为 0；恢复后显示 3 条记录；复制与移除交互通过；页面脚本无运行错误。
- 发布影响：阻塞已解除，V15-P1 与 D6.3 均可标记通过。
