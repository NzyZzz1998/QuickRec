# QuickRec Full v1.6.1 自动验证记录

> 验证时间：2026-07-17
> 分支：`feature/v1.6.1-pending-ingestion`  
> 源码 HEAD：`8a1ee4710de70d5dd74c2478771a50a762b528ca`，工作区仅有验收文档更新
> 结论：自动化、候选包基础检查、核心降级链路、设置与诊断回归及 v1.6 素材库快速回归通过；其余 GUI 项以手动验收清单为准

## 1. 候选包身份

| 对象 | 路径 | 大小 | SHA256 |
| --- | --- | ---: | --- |
| QuickRec.exe | `E:\QRtest\QuickRec-v1.6.1-dist\QuickRec\QuickRec.exe` | 6,886,986 字节 | `505284D20663C73200C6322B609DD9E0D436FC6CAF624383A9D682B18A4D6B39` |
| ffprobe.exe | `E:\QRtest\QuickRec-v1.6.1-dist\QuickRec\_internal\ffmpeg\ffprobe.exe` | 99,066,368 字节 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |

构建命令：

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm `
  --distpath E:\QRtest\QuickRec-v1.6.1-dist `
  --workpath E:\QRtest\QuickRec-v1.6.1-build
```

身份原始记录：`E:\QRtest\QuickRec-v1.6.1-acceptance\build-identity.json`。

## 2. 自动化门禁

| 检查 | 结果 |
| --- | --- |
| 全量 pytest | 374 passed、24 deselected、22 subtests passed |
| 全项目 coverage | 83.99%，门禁 80% |
| 新增存储模块 | 89% |
| 新增待入库服务 | 81% |
| 新增入库协调器 | 85% |
| Packaging | 12 passed |
| Ruff | 通过 |
| Mypy | 通过，项目配置范围 15 个源文件 |
| Compileall | 通过 |
| `git diff --check` | 通过 |
| UTF-8 与乱码检查 | 通过 |
| QuickRec Lite | `lite-master` 工作区干净 |
| 非人工补充回归 | 93 passed；覆盖诊断、设置、迁移、恢复、重建、重新定位、回收站、素材库与待入库链路 |

## 3. 候选包基础检查

- 包内 FFmpeg 与 FFprobe 均存在。
- 包内 FFprobe 成功解析受控 H.264 MP4：640 × 360、25 FPS、1 秒。
- 受控视频：`E:\QRtest\QuickRec-v1.6.1-acceptance\controlled.mp4`。
- FFprobe 输出：`E:\QRtest\QuickRec-v1.6.1-acceptance\ffprobe-controlled.json`。
- 打包程序在隔离 APPDATA 下启动 4 秒保持运行，日志无启动异常。
- 启动证据：`E:\QRtest\QuickRec-v1.6.1-acceptance\packaged-startup.json`。

## 4. 硬件 Smoke

```powershell
python scripts\hardware_smoke.py `
  --output-dir E:\QRtest\QuickRec-v1.6.1-acceptance\hardware-smoke `
  --duration 3 --mode fullscreen
```

结果：`OK: video stream ok`。输出文件：

`E:\QRtest\QuickRec-v1.6.1-acceptance\hardware-smoke\QuickRec_20260715_144056.mp4`

## 5. 尚未覆盖

- 打包产物 GUI 下的正式索引失败、主待入库失败和双重失败链路。
- 已通过：主待入库记录、视频目录降级标记、双重写入失败保视频、重启自动恢复、故障未恢复时单次重试，以及普通启动下托盘素材库入口。
- 已通过：素材库待入库项置顶、独立计数、详情字段与手动重试；重试后正式索引仅新增一条且待入库清零。
- 已通过：缺失文件状态、取消重新定位、损坏 MP4 拒绝、中文空格路径有效 MP4 重新定位，以及仅移除待处理记录且保留视频。
- 已通过：待入库 200 条与正式素材 200 条独立展示，分批加载 50/100/150/200 正常；第 201 条只淘汰最旧元数据且保留 MP4。
- 已通过：当前系统 100% DPI 与长中文空格路径布局无关键裁切或乱码。
- 已通过：候选包全屏与区域录制、无声模式；区域样本为 1728×1080、30 FPS，索引模式与 FFprobe 一致。
- 待补证：窗口录制、三类有声模式、设置与诊断快速回归和 125%/150% DPI。
- v1.6 历史 GUI 证据可追溯：迁移、恢复、重建、重新定位、回收站、诊断和三档 DPI 在 v1.6 正式发布验收中通过；本轮以 93 项自动回归确认相关基础能力未出现已知回退，但仍保留 v1.6.1 候选包快速 GUI 抽查项。

## GUI 阶段证据（2026-07-16）

- 隔离根目录：`E:\QRtest\QuickRec-v1.6.1-acceptance`。
- 正式索引失败样本：`videos\QuickRec_20260716_172733.mp4` 与 `evidence\V161-P1-ffprobe.json`。
- 双重存储失败样本：`videos\QuickRec_20260716_173853.mp4` 与 `evidence\V161-P4-ffprobe.json`。
- 素材库截图：`evidence\V161-U1-material-library-normal-launch.png`。
- 日志：`videos\QuickRecDiagnostics\quickrec.log`。
- 手动重试样本：`videos\QuickRec_20260716_181537.mp4`；重试后正式索引 4 条、待入库 0 条，目标路径只出现一次；随后区域录制入库，当前正式索引为 5 条、待入库 0 条。
- 文件操作样本：待入库 ID `56735f5f03c14bfd8361de0ffddfc1dd`；损坏文件被拒绝，有效中文路径定位成功，最终仅移除待处理记录且视频保留。
- 容量边界：候选包 GUI 显示 200 条待入库与 200 条正式素材；容量夹具撤回后正式/待入库索引按备份哈希恢复。
- 窗口录制工具限制：自动化选择后目标 HWND 消失，候选包按设计安全取消且未生成错误文件；该项需人工选择稳定窗口补证。
- 验收环境说明：使用 Windows 隐藏启动参数会隐藏 Qt 顶层窗口；改为与用户一致的普通启动后，托盘素材库入口直接显示。该现象是验收启动方式干扰，不是候选包缺陷。
- 全屏、区域、窗口与四类音频的打包产物回归。
- 100%、125%、150% DPI。

以上必须按 [manual-verification.md](manual-verification.md) 完成后，才能判断是否可发布。

## 6. 音频阻塞修复候选（2026-07-16）

- 旧候选包因双音频混音失败而失效，不再用于音频复验。
- 根因：8 声道系统回环与 1 声道麦克风经 `amerge` 形成 AAC 不支持的 9 声道布局。
- 修复方式：单音源归一化为双声道；双音源各自转换为 48 kHz 立体声后使用 `amix`；回环设备优先按默认扬声器设备 ID 匹配。
- 自动验证：全量 376 passed、24 deselected、22 subtests passed；packaging 12 passed；ruff、mypy、compileall 和 diff 检查通过。
- 最终候选包：`E:\QRtest\QuickRec-v1.6.1-audiofix2-dist\QuickRec\QuickRec.exe`。
- 最终候选 SHA256：`2CB447709769A8A986B7A48A63C98377803A002ED56892E57F0911661FA3E092`。
- 定向样本：`E:\QRtest\QuickRec-v1.6.1-audiofix2-acceptance\videos\QuickRec_20260716_230446.mp4`，H.264 + 48 kHz 双声道 AAC，平均 `-21.1 dB`、峰值 `-6.2 dB`，日志无混音失败。
- 系统声音单模式定向样本：`E:\QRtest\QuickRec-v1.6.1-audiofix2-system-acceptance\videos\QuickRec_20260716_234947.mp4`，H.264 + 48 kHz 双声道 AAC，平均 `-24.1 dB`、峰值 `-20.8 dB`；日志选中默认 `HECATE G1500 BAR`，中央索引记录 `audio_source=system`。
- 当前结论：结构、设备选择、系统声音单模式、双音频非静音、索引一致性与用户听感均通过，BUG-161-01 已关闭；麦克风单独模式仍按验收清单补证。

## 7. 设置、诊断与素材库自动 GUI 回归（2026-07-17）

- 锁定候选包：`E:\QRtest\QuickRec-v1.6.1-audiofix2-dist\QuickRec\QuickRec.exe`，SHA256 为 `2CB447709769A8A986B7A48A63C98377803A002ED56892E57F0911661FA3E092`。
- 设置持久化：FPS 30 -> 60，保存并重启后仍为 60；验收后恢复为 30。
- 诊断入口：复制诊断信息、打开隔离日志目录、导出诊断文件均通过；导出文件 `diagnostic_20260717_171246.txt` 可按 UTF-8 读取。
- 目录重建：有效 QuickRec MP4 入库，损坏 MP4 失败且不阻断，非视频文件未入库。
- 重新定位：取消不修改记录，损坏 MP4 被拒绝且仍可重试，中文空格路径有效 MP4 成功并保留 2 秒、640 x 360、24 FPS 元数据。
- 文件操作：仅移除索引后 MP4 保留；移入回收站后原路径和索引移除，Windows 回收站中可核对同名文件及原始目录。
- 持久化：重启后重新定位记录仍存在，两条已移除记录未恢复，素材库共 14 条。
- 环境：候选包进程已停止，真实 `%APPDATA%\QuickRec` 文件哈希未变化，QuickRec Lite 工作区干净。
- 证据目录：`E:\QRtest\QuickRec-v1.6.1-acceptance\evidence\auto3`；机器可读汇总为 `verification-summary.json`。
