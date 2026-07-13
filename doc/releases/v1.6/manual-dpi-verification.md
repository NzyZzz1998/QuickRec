# QuickRec Full v1.6 DPI 专项手动验收

> 用途：补齐 D7 最后一组人工视觉证据。
>
> 当前状态：通过（用户于 2026-07-13 完成三档 DPI 全部人工验证）。
>
> 验收范围：100%、125%、150% 显示缩放下的素材库主窗口、重新定位文件选择器、移除索引确认框和回收站确认框。
> 安全原则：所有确认框均选择“否”或“取消”，不删除视频、不修改索引、不触碰真实用户数据。

## 1. 锁定验收对象

本轮只能使用以下候选包：

| 项目 | 锁定值 |
| --- | --- |
| 产品 | QuickRec Full v1.6 |
| 分支 | `feature/v1.6-material-library` |
| 构建时 HEAD | `73ad5a778ff6e27a399d016f4ebb749ddc78438b` 加当前未提交 Bugfix 工作区 |
| EXE | `E:\QRtest\QuickRec-v1.6-bugfix3-dist\QuickRec\QuickRec.exe` |
| EXE 大小 | `6,859,907` 字节 |
| EXE SHA256 | `F1C8F2F971D5DD62067955B939D5DB9293C13DA930D1DFC653007F59596392E8` |
| 隔离 APPDATA | `E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\AppDataRoaming` |
| 隔离中央索引 | `E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\AppDataRoaming\QuickRec\recordings.json` |
| 受控视频 | `E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\one-item 中文 空格\QuickRec_20260712_100001.mp4` |
| 证据目录 | `E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\evidence\dpi-manual` |

开始前在 PowerShell 执行：

```powershell
$Exe = 'E:\QRtest\QuickRec-v1.6-bugfix3-dist\QuickRec\QuickRec.exe'
$ExpectedHash = 'F1C8F2F971D5DD62067955B939D5DB9293C13DA930D1DFC653007F59596392E8'
$ActualHash = (Get-FileHash $Exe -Algorithm SHA256).Hash
$ActualHash
if ($ActualHash -ne $ExpectedHash) {
    throw 'EXE SHA256 不一致，停止验收。'
}

Get-Process QuickRec -ErrorAction SilentlyContinue | Stop-Process -Force
New-Item -ItemType Directory -Force `
    'E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\evidence\dpi-manual' | Out-Null
```

只有输出哈希与锁定值完全一致时才能继续。哈希不一致时，不得换用其他 EXE，也不得沿用本轮证据。

## 2. 验收前保护

### 2.1 记录 Windows 当前缩放

1. 打开 Windows“设置”。
2. 进入“系统” -> “屏幕”。
3. 记录“缩放”当前值和主显示器。
4. 如果连接了多个显示器，后续始终在同一台主显示器上操作 QuickRec。

原始状态填写：

| 项目   | 验收前值 |
| ---- | ---- |
| 主显示器 |      |
| 原始缩放 | 100  |
| 分辨率  | 2k   |

### 2.2 记录受控文件和索引

```powershell
$Root = 'E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining'
$Video = Join-Path $Root 'one-item 中文 空格\QuickRec_20260712_100001.mp4'
$Index = Join-Path $Root 'AppDataRoaming\QuickRec\recordings.json'

Get-Item $Video | Select-Object FullName, Length, LastWriteTime
Get-FileHash $Video -Algorithm SHA256
Get-Item $Index | Select-Object FullName, Length, LastWriteTime
Get-FileHash $Index -Algorithm SHA256
```

把输出保留在 PowerShell 窗口中。验收结束后需要再次核对。
![[Pasted image 20260713182457.png]]

## 3. 启动方式

每次修改显示缩放后，都应先结束 QuickRec，再用同一个 PowerShell 窗口重新启动：

```powershell
Get-Process QuickRec -ErrorAction SilentlyContinue | Stop-Process -Force

$env:APPDATA = 'E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\AppDataRoaming'
& 'E:\QRtest\QuickRec-v1.6-bugfix3-dist\QuickRec\QuickRec.exe'
```

启动后，从系统托盘右键 QuickRec 图标，点击“素材库”。不要从其他 QuickRec 工作区或旧版本启动。

## 4. 每档 DPI 的完整操作

100%、125%、150% 必须分别完整执行本节。每档至少保留 4 张截图。

### 4.1 切换缩放并冷启动

1. 退出 QuickRec。
2. 打开 Windows“设置” -> “系统” -> “屏幕”。
3. 将缩放设为本轮目标值。
4. 等待桌面完成缩放刷新。
5. 使用第 3 节命令冷启动锁定 EXE。
6. 打开托盘菜单，确认“素材库”菜单可见且文字完整。
7. 打开素材库并最大程度保持窗口完整显示在主显示器内。

主窗口检查：

- [ ] 标题“素材库”完整显示。
- [ ] 左侧列表、右侧详情和底部操作区均可见。
- [ ] 文件名、中文路径和状态文字无乱码。
- [ ] 长路径不会遮挡右侧按钮。
- [ ] 按钮文字无截断、重叠或异常换行。
- [ ] 窗口可以移动、缩放、关闭并再次打开。
- [ ] 鼠标点击区域与按钮视觉位置一致。

截图：`DPI-<缩放>-01-material-library.png`

### 4.2 “从素材库移除”确认框

1. 在列表中选中现有受控素材。
2. 点击“从素材库移除”。
3. 不要确认移除，先检查弹窗。

检查项：

- [ ] 标题“从素材库移除”完整显示。
- [ ] 正文完整显示“视频文件不会被删除”。
- [ ] “是”和“否”按钮完整可见，无重叠。
- [ ] 弹窗位于可视区域内，没有超出屏幕。
- [ ] 按钮点击区域与视觉位置一致。
- [ ] 点击“否”后弹窗关闭，素材记录仍存在。

弹窗出现时截图：`DPI-<缩放>-02-remove-confirm.png`

### 4.3 “删除视频文件”回收站确认框

1. 保持同一素材处于选中状态。
2. 点击“删除视频文件”。
3. 不要确认删除，先检查弹窗。

检查项：

- [ ] 标题“删除视频文件”完整显示。
- [ ] 正文完整显示“移入 Windows 回收站”。
- [ ] 正文完整显示“不会删除诊断日志或其他文件”。
- [ ] “是”和“否”按钮完整可见，无重叠。
- [ ] 弹窗位于可视区域内，没有超出屏幕。
- [ ] 点击“否”后弹窗关闭，视频和索引记录均仍存在。

弹窗出现时截图：`DPI-<缩放>-03-recycle-confirm.png`

### 4.4 “重新定位素材”文件选择器

“重新定位”只在文件缺失或元数据不完整时可用。使用以下安全流程制造临时缺失状态。

1. 退出 QuickRec。
2. 在 PowerShell 中临时移动受控视频：

```powershell
$Root = 'E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining'
$Video = Join-Path $Root 'one-item 中文 空格\QuickRec_20260712_100001.mp4'
$TemporaryVideo = Join-Path $Root 'one-item 中文 空格\QuickRec_20260712_100001.relink-test.mp4'

Move-Item -LiteralPath $Video -Destination $TemporaryVideo
```

3. 使用第 3 节命令重新启动 QuickRec。
4. 打开素材库，选中显示为“文件缺失”的记录。
5. 点击“重新定位”。
6. 不选择文件，只检查文件选择器，然后点击“取消”。

检查项：

- [ ] “重新定位”按钮可点击。
- [ ] 文件选择器标题“重新定位素材”完整显示。
- [ ] 地址栏、文件列表、文件名输入框和文件类型区域完整可见。
- [ ] “打开”和“取消”按钮完整可见且可点击。
- [ ] 中文和空格路径显示正常。
- [ ] 文件选择器未超出可视区域。
- [ ] 点击“取消”后，原索引路径保持不变。
- [ ] 取消后仍可再次点击“重新定位”。

文件选择器出现时截图：`DPI-<缩放>-04-relink-dialog.png`

7. 退出 QuickRec并立即恢复受控视频原路径：

```powershell
$Root = 'E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining'
$Video = Join-Path $Root 'one-item 中文 空格\QuickRec_20260712_100001.mp4'
$TemporaryVideo = Join-Path $Root 'one-item 中文 空格\QuickRec_20260712_100001.relink-test.mp4'

if ((Test-Path -LiteralPath $TemporaryVideo) -and -not (Test-Path -LiteralPath $Video)) {
    Move-Item -LiteralPath $TemporaryVideo -Destination $Video
}
```

8. 再次启动 QuickRec，打开素材库，确认记录恢复为可用状态。

## 5. 三档执行顺序

按以下顺序执行，不要跳档：

| 顺序 | Windows 缩放 | 必做截图 | 结果 |
| --- | --- | --- | --- |
| 1 | 100% | 主窗口、移除确认框、回收站确认框、重新定位文件选择器 | 待填写 |
| 2 | 125% | 主窗口、移除确认框、回收站确认框、重新定位文件选择器 | 待填写 |
| 3 | 150% | 主窗口、移除确认框、回收站确认框、重新定位文件选择器 | 待填写 |

截图应保存到：

```text
E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\evidence\dpi-manual
```

建议最终文件清单：

```text
DPI-100-01-material-library.png
DPI-100-02-remove-confirm.png
DPI-100-03-recycle-confirm.png
DPI-100-04-relink-dialog.png
DPI-125-01-material-library.png
DPI-125-02-remove-confirm.png
DPI-125-03-recycle-confirm.png
DPI-125-04-relink-dialog.png
DPI-150-01-material-library.png
DPI-150-02-remove-confirm.png
DPI-150-03-recycle-confirm.png
DPI-150-04-relink-dialog.png
```

## 6. 逐项结果记录

每项结论只能填写：`通过`、`部分通过`、`未通过`、`待验证`。

| 缩放 | 素材库主窗口 | 移除确认框 | 回收站确认框 | 重新定位选择器 | 总结论 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| 100% | 通过 | 通过 | 通过 | 通过 | 通过 | 用户按本文步骤手动确认 |
| 125% | 通过 | 通过 | 通过 | 通过 | 通过 | 用户按本文步骤手动确认 |
| 150% | 通过 | 通过 | 通过 | 通过 | 通过 | 用户按本文步骤手动确认 |

如发现问题，记录以下信息：

| 字段 | 内容 |
| --- | --- |
| 缩放比例 |  |
| 操作入口 |  |
| 复现步骤 |  |
| 预期结果 |  |
| 实际结果 |  |
| 是否仍可完成操作 |  |
| 截图路径 |  |
| 严重度 | 一般缺陷 / 重要缺陷 / 发布阻塞 |

判定建议：

- 仅有轻微视觉差异、但文字完整且操作可完成：一般缺陷，可记录后评估是否延后。
- 关键文字被截断、按钮难以辨认或需要改变窗口大小才能操作：重要缺陷。
- 弹窗按钮不可点击、弹窗超出屏幕、无法取消或可能误删文件：发布阻塞。

## 7. 验收后恢复

1. 退出所有 QuickRec 进程。
2. 确认临时 `.relink-test.mp4` 已恢复为原文件名。
3. 将 Windows 显示缩放恢复为验收前记录值。
4. 不清空 Windows 回收站。
5. 不删除验收截图和日志。
6. 重新核对视频和隔离索引：

```powershell
Get-Process QuickRec -ErrorAction SilentlyContinue | Stop-Process -Force

$Root = 'E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining'
$Video = Join-Path $Root 'one-item 中文 空格\QuickRec_20260712_100001.mp4'
$TemporaryVideo = Join-Path $Root 'one-item 中文 空格\QuickRec_20260712_100001.relink-test.mp4'
$Index = Join-Path $Root 'AppDataRoaming\QuickRec\recordings.json'

if ((Test-Path -LiteralPath $TemporaryVideo) -and -not (Test-Path -LiteralPath $Video)) {
    Move-Item -LiteralPath $TemporaryVideo -Destination $Video
}

Get-Item $Video | Select-Object FullName, Length, LastWriteTime
Get-FileHash $Video -Algorithm SHA256
Get-Item $Index | Select-Object FullName, Length, LastWriteTime
Get-FileHash $Index -Algorithm SHA256
Get-Process QuickRec -ErrorAction SilentlyContinue
```

恢复完成检查：

- [x] Windows 缩放已由用户确认恢复。
- [x] QuickRec 进程已全部停止。
- [x] 受控 MP4 已恢复原路径。
- [x] `.relink-test.mp4` 不再存在。
- [x] 隔离中央索引仍存在。
- [x] 真实 `%APPDATA%\QuickRec` 未被用于本轮受控验收。
- [x] QuickRec Lite 工作区保持干净。

## 8. 验收完成后的反馈格式

执行完成后，可直接回复：

```text
QuickRec Full v1.6 DPI 专项手动验收已完成。

- 100%：通过 / 部分通过 / 未通过
- 125%：通过 / 部分通过 / 未通过
- 150%：通过 / 部分通过 / 未通过
- Windows 缩放已恢复：是 / 否
- 受控视频已恢复：是 / 否
- QuickRec 进程已停止：是 / 否
- 截图目录：E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\evidence\dpi-manual
- 发现问题：无 / 简述问题
```

## 9. 实际验收结论（2026-07-13）

- 100%、125%、150% 下的素材库主窗口、移除索引确认框、回收站确认框和重新定位文件选择器均由用户手动确认通过。
- 用户未报告文字截断、控件重叠、弹窗越界、按钮不可点击或误操作风险。
- 本次结论依据用户明确的手动验收确认；未额外提供新截图文件路径，不虚构截图证据。
- 收尾检查确认锁定 EXE SHA256 仍为 `F1C8F2F971D5DD62067955B939D5DB9293C13DA930D1DFC653007F59596392E8`。
- 收尾检查确认 QuickRec 进程为 0、受控 MP4 位于原路径、临时 `.relink-test.mp4` 不存在、隔离中央索引存在、QuickRec Lite 工作区干净。

专项结论：**通过**。D7 的人工补证已经闭合，可以进入发布收口确认点。本轮未执行 commit、push、tag 或 GitHub Release。
