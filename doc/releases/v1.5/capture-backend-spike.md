# QuickRec Full v1.5 WGC / 新捕获后端 Spike

> 版本：v1.5
> 状态：研究记录 / 不替换默认链路
> 结论口径：本文件只作为后续捕获后端升级的证据材料，不作为 v1.5 默认实现范围。

## 1. 研究目标

本次 spike 只回答一个问题：QuickRec Full 是否值得在后续版本研究 Windows Graphics Capture（WGC）或其他新捕获后端，用于改善窗口录制、DPI 场景和光标捕获体验。

本次不做：

- 不替换当前默认 dxcam 捕获链路。
- 不新增用户可见的捕获后端切换开关。
- 不改动 v1.5 的录制主链路。
- 不把 WGC 能力纳入 v1.5 发布阻断验收。

## 2. 官方能力线索

Microsoft Learn 中 `Windows.Graphics.Capture.GraphicsCaptureSession` 提供捕获会话能力，包含 `StartCapture()`、`IsSupported()`、`IsBorderRequired`、`IncludeSecondaryWindows` 等属性和方法。

其中 `IsCursorCaptureEnabled` 用于指定捕获内容是否包含光标。Microsoft Learn 中文文档同时标注该属性在 Windows 10 version 2004 / SDK 19041 中加入。

参考来源：

- [GraphicsCaptureSession Class - Microsoft Learn](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture.graphicscapturesession)
- [GraphicsCaptureSession.IsCursorCaptureEnabled Property - Microsoft Learn](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture.graphicscapturesession.iscursorcaptureenabled)
- [Windows 10 Build 19041 API changes - Microsoft Learn](https://learn.microsoft.com/en-us/windows/uwp/whats-new/windows-10-build-19041-api-diff)

## 3. 初步判断

| 问题 | 初步判断 | 证据强度 |
| --- | --- | --- |
| 是否可能原生捕获光标 | 有潜力，WGC 暴露 `IsCursorCaptureEnabled` | 中 |
| 是否可能改善窗口录制 | 有潜力，WGC 是系统级窗口/屏幕捕获能力 | 中 |
| 是否能直接替换 dxcam | 不建议直接替换，需要验证性能、依赖、打包和权限 | 低 |
| 是否适合 v1.5 默认接入 | 不适合，本轮只做研究记录 | 高 |
| 是否值得进入 v1.6+ 独立 PRD | 值得继续验证 | 中 |

## 4. 后续验证清单

如果进入后续 spike 分支，建议至少验证：

- Windows 10 2004 以下系统的降级策略。
- Python 侧调用 WinRT / WGC 的依赖体积和 PyInstaller 兼容性。
- 全屏、区域、窗口三种模式的帧率稳定性。
- 4K / 高 DPI / 缩放 150% / 最大化窗口场景。
- 窗口移动、窗口遮挡、最小化、关闭时的行为。
- 原生光标捕获的尺寸、DPI 和多显示器一致性。
- 与当前 FFmpeg pipe、音频混流、诊断导出、最近录制历史的边界关系。

## 5. 风险

| 风险 | 说明 | 处理建议 |
| --- | --- | --- |
| 系统版本门槛 | `IsCursorCaptureEnabled` 依赖较新的 Windows API | 后续 PRD 必须定义最低系统版本和降级策略 |
| 依赖体积 | Python 调用 WinRT 可能引入新的运行时依赖 | 先做独立分支体积实验 |
| 打包风险 | PyInstaller 对 WinRT 相关依赖可能需要额外 hook | 先做最小 demo 打包验证 |
| 主链路回归 | 捕获链路替换会影响所有录制模式 | 后续只能以可回滚后端适配层推进 |
| 体验不确定 | 原生光标捕获不等于所有场景都显示一致 | 必须做 4K/DPI/多显示器人工验收 |

## 6. 结论

v1.5 不接入 WGC，不替换 dxcam，不开放后端切换。

后续建议将 WGC / 新捕获后端作为 v1.6 或更后版本的独立 `/idea -> /prd` 候选，先做最小 demo 与打包验证，再决定是否进入正式实现。
