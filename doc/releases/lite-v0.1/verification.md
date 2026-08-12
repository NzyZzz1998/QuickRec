# QuickRec Lite v0.1 验证报告

## 1. 当前结论

- 自动化、静态检查、Packaging、源码硬件 smoke：通过
- RC2 GUI 与候选包验收：通过
- 发布阻塞：无
- 发布状态：已完成

## 2. 自动化门禁

| 检查 | 结果 |
| --- | --- |
| 全量非硬件/非 Packaging 测试 | `231 passed, 11 deselected` |
| 总体覆盖率 | `81.14%`，门禁 80% |
| 身份/迁移/配置/帧调度核心覆盖率 | `90%`，门禁 85% |
| UI/快捷键/录制协调覆盖率 | `88%`，门禁 80% |
| Packaging tests | `7 passed, 235 deselected` |
| Ruff | 通过 |
| Mypy | 18 个源文件通过 |
| Compileall | 通过 |
| `git diff --check` | 通过；仅有 Windows 行尾转换提示 |
| UTF-8/乱码检查 | 通过；项目文本严格 UTF-8，未发现替换字符或常见乱码模式 |

## 3. 候选包身份

| 产物 | 大小 | SHA256 |
| --- | ---: | --- |
| `QuickRec-Lite.exe` | 6,779,986 B | `82F784C15182D2F731B74BAE574DF10760C8E72328860AC0E903E42EEAE3860B` |
| `ffmpeg.exe` | 99,264,000 B | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| `QuickRec-Lite-v0.1-win-x64.zip` | 101,860,386 B | `AA307EC1B7B95CBB4F516DECABFD420DD58A3E97B9624C6445F6086C6DCBDD34` |

- 固定 FFmpeg：`8.0.1-essentials_build-www.gyan.dev`
- 展开包体积：270,411,890 B（257.88 MB）
- `release-manifest.json`：`E:\QRtest\QuickRec-Lite-v0.1-rc2-dist\release-manifest.json`
- 包内扫描：不存在已删除的区域/窗口录制专属运行模块。

## 4. 硬件与候选包验证

- 源码硬件 smoke：`OK: video stream ok`，实测捕获约 59.87 FPS，输出 137 帧。
- 无声录制：通过。
- 系统声音：通过，AAC 48 kHz 立体声且非静音。
- 麦克风：默认设备确认为 GS03，Core Audio 静音关闭、输入音量 100%；真人样本平均约 -46.2 dB、峰值约 -26.4 dB，设备、编码和内容链路通过。
- 双音频：双设备、双输入和 `amix` 链路通过；频谱同时包含 523 Hz 系统测试音和显著非测试音语音能量。
- 静态桌面：通过。
- 1 秒内快速停止：通过。
- 同一进程连续 5 次：通过，无编码进程和临时会话残留。
- Full/Lite 同机共存与 Lite 单实例：通过。
- 配置迁移、原子保存、注册表回滚和快捷键冲突：通过。

完整操作和证据路径见 `manual-verification.md`。

## 5. 发布判断

RC2 候选包验收通过，所有发布阻塞项关闭。`lite-v0.1` tag、最终 manifest 与发布提交 `408c376` 一致；候选二进制和 ZIP 哈希未改变，GitHub Release 已发布，tag CI 通过。
