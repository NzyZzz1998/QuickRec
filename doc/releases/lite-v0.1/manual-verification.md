# QuickRec Lite v0.1 候选包手动验收

## 1. 验收结论

- 验收阶段：D8 GUI/真实硬件验收
- 当前结论：**通过**
- 发布判断：**可进入本地发布授权**
- 待补证项：无
- 发布阻塞项：无

设备诊断确认 Windows 默认输入是 `麦克风 (HECATE GS03 GAMING SOUND CARD)`；Core Audio 报告 `mute=false`、主输入音量 `100%`。2026-08-12 重新录制真人语音后，麦克风样本平均约 -46.2 dB、峰值约 -26.4 dB，已形成明确语音活动。双音频样本同时包含 523 Hz 系统测试音和非测试音语音能量，两个音频源均得到客观证据。

## 2. 验收对象

| 项目 | 值 |
| --- | --- |
| 工作区 | `E:\codex\QuickRec-Lite` |
| 分支 | `lite-test` |
| 构建基线 HEAD | `11874bf3dbb8d4550dc4bd936438b5fafe687ebe` |
| 候选包 | `E:\QRtest\QuickRec-Lite-v0.1-rc2-dist\QuickRec-Lite` |
| EXE | `E:\QRtest\QuickRec-Lite-v0.1-rc2-dist\QuickRec-Lite\QuickRec-Lite.exe` |
| EXE SHA256 | `82F784C15182D2F731B74BAE574DF10760C8E72328860AC0E903E42EEAE3860B` |
| FFmpeg SHA256 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| ZIP SHA256 | `AA307EC1B7B95CBB4F516DECABFD420DD58A3E97B9624C6445F6086C6DCBDD34` |
| 证据根目录 | `E:\QRtest\QuickRec-Lite-v0.1-acceptance` |

RC1 曾因 frozen 启动缺少 `Qt` 导入而失败，已保留为失败证据。本文所有发布判断只使用修复后的 RC2，不混用 RC1。

## 3. 环境保护

- 所有迁移、配置、录制和故障注入均使用独立 APPDATA、LOCALAPPDATA 和输出目录。
- 旧 Full 配置只使用隔离副本；导入、默认、取消、损坏和写入失败场景均核对旧文件哈希。
- Full 源码应用在隔离环境启动；`E:\codex\QuickRec` 工作区保持干净。
- 开机启动测试结束后已恢复：`HKCU\Software\Microsoft\Windows\CurrentVersion\Run\QuickRec Lite` 不存在。
- 验收结束时不保留 Full 测试进程、FFmpeg 进程或录制会话目录。

## 4. D8 逐项结果

| ID | 结论 | 实际结果与证据 |
| --- | --- | --- |
| D8.1 | 通过 | Full `pythonw.exe` 与 `QuickRec-Lite.exe` 同时存活；UI Automation 同时识别 `QuickRec - 录屏工具` 和 `QuickRec Lite - 录屏工具`。截图：`dual-product\evidence\D8-full-lite-coexist.png`。 |
| D8.2 | 通过 | 第二个 Lite 实例退出，原实例继续运行，并显示“QuickRec Lite 应用已在运行”。截图：`rc2-gui\evidence\D8-second-instance.png`。 |
| D8.3 | 通过 | 迁移对话框仅导入 `save_path`、`audio_source=system`；快捷键、开机启动和未知字段未导入；旧文件 SHA256 保持 `6C83E1A123707B245D328BB1034CB4155BCAF3B09FDB767322DD1370C2976A65`。 |
| D8.4 | 通过 | “使用 Lite 默认设置”生成 `Videos\QuickRec Lite`、native、60 FPS、无声、Ctrl+Alt+R/S/P、不开机自启；旧文件不变。 |
| D8.5 | 通过 | 关闭迁移对话框后进程退出，不创建 Lite 配置目录，不修改旧配置。 |
| D8.6 | 通过 | 损坏旧配置不会生成半份 Lite 配置；写入目标被普通文件占用时停留在迁移窗口并显示失败。截图：`migration-corrupt\evidence\D8-corrupt-migration-feedback.png`、`migration-write-failure\evidence\D8-write-failure-feedback.png`。 |
| D8.7 | 通过 | 配置文件设为只读后，保存窗口保持打开、显示 replace 拒绝访问；配置哈希不变；勾选开机自启产生的注册表变更被回滚。恢复权限后可正常保存。 |
| D8.8 | 通过 | 将开始快捷键改为与停止相同后，保存被拒绝并提示三个快捷键不能重复；配置哈希与原绑定保持不变。 |
| D8.9 | 通过 | 无声录制生成 H.264 2560x1440 60 FPS MP4，无音频流。文件：`rc2-gui\recordings\QuickRec_20260811_015629.mp4`。 |
| D8.10 | 通过 | 系统声录制生成 AAC LC 48 kHz 立体声，平均响度 -24.1 dB、峰值 -20.8 dB；日志确认默认 HECATE loopback。文件：`audio\system\recordings\QuickRec_20260811_020935.mp4`。 |
| D8.11 | 通过 | 默认输入为 GS03，Windows 静音关闭且输入音量 100%；输出 AAC 48 kHz 立体声，真人样本平均约 -46.2 dB、峰值约 -26.4 dB，存在明确语音活动。文件：`audio\microphone-final\recordings\QuickRec_20260812_101358.mp4`。 |
| D8.12 | 通过 | 系统声和麦克风均初始化，两个输入经 `amix` 生成 AAC 48 kHz 立体声；输出平均约 -30.0 dB、峰值约 -22.0 dB。相对纯 523 Hz 测试音，混合输出存在显著非测试音能量，证明真人语音共同进入输出。文件：`audio\both-final\recordings\QuickRec_20260812_101525.mp4`。 |
| D8.13 | 通过 | 静态桌面约 10.91 秒，655 帧，H.264 2560x1440 60 FPS，可完整解码。文件：`stability-static\recordings\QuickRec_20260811_021621.mp4`。 |
| D8.14 | 通过 | 启动后约 750 ms 请求停止，得到 0.63 秒、38 帧可解码 MP4。文件：`stability-static\recordings\QuickRec_20260811_021702.mp4`。 |
| D8.15 | 通过 | 同一进程连续 5 次录制新增 5 个 MP4，全部 FFmpeg 解码退出码 0；无残留 FFmpeg 进程和 `session_*` 目录。 |
| D8.16 | 通过 | 托盘为 `QuickRec Lite - 录屏工具`，菜单仅含全屏录制、设置、打开保存文件夹和退出；结果条显示已保存/打开/关闭，通知标题为 QuickRec-Lite。截图：`rc2-settings\evidence\quickrec-tray-menu.png`、`rc2-gui\evidence\D8-result-bar.png`。 |

## 5. 最终音频证据

- 分析报告：`E:\QRtest\QuickRec-Lite-v0.1-acceptance\audio\final-audio-analysis.json`
- 麦克风样本 SHA256：`F4620B26581C60F6FD98B75134A54CAB1EF3F4C97B8051D994704623C90076BC`
- 双音频样本 SHA256：`90295FDD8C5527BCFD1B406EE33CE41137B859A99A25DA38650F2A3FB8CB30F7`
- 纯测试音非 523 Hz 能量比例中位数约 `0.00000279`；双音频样本约 `0.02137`、最大约 `0.09893`，证明混合结果不只是系统测试音。

## 6. 最终发布判断

D8 全部项目通过，配置、进程、开机启动项和临时会话均已恢复。RC2 可以进入本地发布授权；本文不授权或执行 commit、push、tag 与 GitHub Release。
