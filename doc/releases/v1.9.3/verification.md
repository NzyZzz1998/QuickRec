# QuickRec Full v1.9.3 自动验证报告

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 验证版本 | QuickRec Full v1.9.3 RC3 |
| 验证日期 | 2026-07-29 |
| 项目路径 | `E:\codex\QuickRec` |
| 分支 | `master` |
| 基线 HEAD | `91ab91cba324658d9bfadb7016a31f8e4e380efb` |
| 基线 tag | `v1.9.2` |
| 发布源 | v1.9.3 正式提交；独立 v2.0 架构治理文件不属于本次发布 |
| 当前公开版本 | v1.9.3 |
| 自动验证结论 | 通过；D10 GUI 与真实媒体验收通过 |
| 发布结论 | 正式发布 |

RC3 由 v1.9.2 基线加本版正式差异构建，并作为 v1.9.3 发布资产锁定。任何
后续生产代码、依赖、PyInstaller 配置或版本号变化都必须进入新版本并重新验收。

RC1 在 GUI 验收中发现“删除后状态摘要残留已删除片段”问题。该问题已修复，
RC2 随后在分割验收中发现“状态摘要仍显示分割前片段”问题。两者均只保留为
历史验收证据，不再是有效发布候选。

## 2. 候选包身份

发布目录：

```text
E:\QRtest\QuickRec-v1.9.3-rc3-dist\QuickRec
```

| 对象 | 字节数 | SHA256 |
| --- | ---: | --- |
| `QuickRec.exe` | 7,319,931 | `94F51E274A32E35CC2E47AA9549BF37B41BE4DD034DDBA72A66309C58E1CC986` |
| `QuickRecCLI.exe` | 6,595,619 | `8E80AEB199D978944BED049668E0F49A840BE2455AA46CAA7318AE29A9DB0B09` |
| `ffmpeg.exe` | 99,264,000 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| `ffprobe.exe` | 99,066,368 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |
| 分发目录全部文件 | 503,644,198 | 不适用 |
| `QuickRec-v1.9.3-rc3-win-x64.zip` | 194,305,179 | `F062CD3A28245AF9FC275A6889EA39115B80A1D3D794B5E759176EB103726C6D` |

ZIP 路径：

```text
E:\QRtest\QuickRec-v1.9.3-rc3-win-x64.zip
```

包内已确认存在：

- `QuickRec.exe`；
- `QuickRecCLI.exe`；
- 共享 `_internal\ffmpeg\ffmpeg.exe`；
- 共享 `_internal\ffmpeg\ffprobe.exe`；
- `_internal\av\_core.pyd`；
- `_internal\av.libs\avcodec-*.dll`。

## 3. 包体积对比

| 对象 | v1.9.2 | v1.9.3 RC3 | 变化 |
| --- | ---: | ---: | ---: |
| 分发目录 | 496,962,245 B | 503,644,198 B | +6,681,953 B（约 +1.34%） |
| ZIP | 187,791,183 B | 194,305,179 B | +6,513,996 B（约 +3.47%） |

新增 CLI 与剪辑模块复用同一 `_internal`，没有复制 FFmpeg、FFprobe 或 PyAV
运行时。

## 4. 自动化测试

### 4.1 受影响链路

```text
231 passed, 8 deselected
```

覆盖：

- timeline schema v2 与 v1 延迟迁移；
- 裁剪、分割、全局波纹和轨道锁；
- 命令事务、保存、历史和回滚；
- PyQt 剪辑交互与窗口协调；
- 非零源入点播放与 PyAV；
- QuickRecCLI 合同、隔离和命令；
- 静态桌面捕获兜底；
- FFprobe 元数据与隐私路径清洗。

### 4.2 全量非硬件回归

```text
1031 passed, 30 deselected, 62 subtests passed
```

被标记为 `hardware` 或 `packaging` 的项目未混入该结果。

### 4.3 Packaging

```text
18 passed, 1043 deselected
```

覆盖双入口 spec、CI 基线媒体依赖准备、打包协议、媒体工具、PyAV 文件及
历史 packaging 合同。

## 5. 覆盖率

| 门禁 | 实际 | 要求 | 结论 |
| --- | ---: | ---: | --- |
| 项目总体 | 83.56% | ≥ 80% | 通过 |
| 剪辑核心 | 87.65% | ≥ 85% | 通过 |
| 剪辑 UI 协调 | 80.16% | ≥ 80% | 通过 |
| QuickRecCLI 核心 | 88.05% | ≥ 85% | 通过 |

覆盖率报告：

```text
E:\QRtest\quickrec-v193-coverage-rc3.json
```

## 6. 静态质量

| 检查 | 结果 |
| --- | --- |
| `python -m ruff check src tests scripts` | 通过 |
| `python -m mypy` | 通过，60 个源文件无问题 |
| `python -m compileall -q src tests scripts` | 通过 |
| `git diff --check` | 通过；仅有 Windows 换行转换提示 |
| UTF-8 严格读取与乱码扫描 | 通过 |
| Markdown 相对链接检查 | 通过 |

## 7. 冻结 CLI 验证

证据根目录：

```text
E:\QRtest\QuickRec-v1.9.3-rc3-cli
```

| 命令 | 结果 | 关键证据 |
| --- | --- | --- |
| `doctor --json` | 通过 | `frozen=true`，FFmpeg/FFprobe 可用，未初始化 GUI |
| `smoke --suite editing` | 通过 | schema v2、2 轨 4 片段；裁剪、分割、零副作用、播放计划和保存重载均通过 |
| `record --mode fullscreen --duration 3 --fps 60 --audio none` | 通过 | 生成 1920×1080、60 FPS、3.033333 秒 MP4，提交 182 帧 |
| `probe <video> --json` | 通过 | SHA256、时长、分辨率和 FPS 与录制报告一致 |
| `project validate <project>` | 通过 | 项目可用、1 项素材、包含时间线 |
| `timeline validate <project>` | 通过 | schema v2，2 轨、2 片段，可写且已持久化 |

真实冻结录制：

```text
文件: E:\QRtest\QuickRec-v1.9.3-rc3-cli\record-workspace\output\QuickRec_20260729_040139.mp4
大小: 141,937 B
SHA256: 8B2D6E1C04489A10B24BD6001CFFF7E5DC048095E5176F4A96FA1D5B2705EFF8
```

## 8. GUI 基础启动

使用隔离目录启动 RC3 `QuickRec.exe`，工作台、项目页和剪辑工作台均可打开。
RC3 能加载 schema v2、2 轨、3 片段、4.600 秒的受控时间线；通过工具栏在
3.410 秒执行分割后，时间线持久化为 4 个片段。

隔离目录：

```text
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance
```

分割后选择摘要截图：

```text
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-split-summary-refreshed.jpg
```

界面选中的新右片段为
`clip-7456a2a746b248769a5d9ca354bb775f`，摘要源范围为
`00:01.866–00:03.066`；项目 JSON 中对应片段的
`source_start_us=1866667`、`source_duration_us=1200000`，界面和文件一致。

同一 RC3 候选包继续完成以下定向 GUI 复验：

- 左右手柄内收和向外延长均能生成裁剪候选及全局波纹预览，取消无副作用；
- 精确输入 `0.100` 秒后可确认并持久化，撤销可恢复原范围；非法源入点
  `3.100` 秒在提交前被阻止；
- 工具栏、右键菜单和 `Ctrl+B` 三种分割入口可发现，工具栏与快捷键均完成
  真实分割；
- 轨道锁定后剪辑控件禁用，解除锁定后恢复；
- 受控交叉冲突项目中，跨越全局波纹区间的片段会阻止提交，“定位冲突”能
  准确选中冲突片段；取消后项目文件仍为 schema v2、3 轨、2 片段；
- 删除预览准确显示总时长 `4.600 -> 3.066` 及影响范围，取消后项目 JSON
  仍为 schema v2、2 轨、4 片段、总长 4.600 秒；
- 经操作时确认后执行最终全局波纹删除，界面选择和摘要立即清空；项目持久化
  为 schema v2、2 轨、3 片段、总长 `3.066667` 秒，冻结 CLI validate
  返回成功，受控源视频未被删除；
- 四个相邻片段从起点连续播放，并在 `4.600 / 4.600` 自动停止；
- 最大化和实际约 `962×672` 的最小窗口均未出现主要控件越界。

对应证据目录：

```text
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence
```

真实媒体门禁已补充覆盖非关键帧源入点、真实音频起点、分割接缝和长时音画
同步：30/60/120 FPS 视频边界均不超过 1 帧，AAC 非零起点误差 0 ms，分割
接缝误差 0 μs，30 秒绝对音画偏差 16 ms，10 分钟漂移增量 0 ms。源码与
frozen 环境共 16 项验证通过，详见 `playback-accuracy-spike.md`。

同一 RC3 还完成以下发布前回归：

- 保存失败、恢复后重试和放弃修改三条路径通过；
- 外部冲突的取消、恢复副本和重新加载三条路径通过；重新加载后本地新增轨道
  候选被放弃，项目完整恢复为外部版本的 schema v2、3 轨、2 片段；
- 缺失素材与重新定位通过；归档项目进入剪辑工作台后所有写操作禁用，播放与
  诊断入口保留，退出后已恢复为活跃状态；
- 非法关联组由时间线载入校验层拒绝；界面防御定向测试确认“关联异常”状态会
  禁用整组剪辑操作、保留属性和诊断入口，相关测试 5 passed，不通过篡改候选
  项目制造不可发布数据；
- schema v1/v2、v1.9.2 回滚只读、未知字段及其他 extensions 往返保留通过；
- 8+8 轨、100 片段、30 分钟项目可用，100 次混合剪辑压力测试通过；
- 区域录制输出 `1876×1080 / 30 FPS`，窗口录制输出
  `1122×632 / 30 FPS`，画面、中央索引和录制模式一致；
- 系统声音录制包含可验证的 AAC 48 kHz 双声道音频；
- GUI 全屏 60 FPS 输出为 `1920×1080 / 60 FPS / 无音频`，中央索引记录
  `fps=60.0`，测试后设置恢复为 `30 FPS / 无声`；
- 同一锁定 RC3 在单显示器 `2560×1440@300 Hz` 环境完成 120 FPS 能力检测、
  GUI 设置和真实全屏录制。输出为 `1920×1080 / 120 FPS / 121.283333 秒 /
  无音频`，共 `14554` 帧；结果条显示平均 `120.0 FPS`、最低单秒 `115 FPS`，
  性能日志记录平均 `119.963 FPS`、最低单秒 `115 FPS`、最大队列积压
  `85.900 ms`、丢弃 `5` 帧且 `stable=True`。FFprobe、抽帧、中央索引和
  日志一致，测试后设置恢复为 `30 FPS / 无声 / 不倒计时`；
- 设置持久化、诊断复制/目录/导出、单实例、隐藏和重新激活工作台通过；
- 托盘隐藏图标区只出现 1 个锁定候选包图标，双击后恢复同一工作台，进程仍为
  原 PID `28300` 且数量为 1；托盘右键菜单中的“退出 QuickRec”入口已真实
  展示。补证时同一锁定 RC3 进程 PID 为 `20772`，用户点击“退出 QuickRec”
  后，同路径进程数量由 1 降为 0，无残留进程，托盘显式退出通过。

新增主要证据：

```text
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-region-recording-frame.png
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-window-recording-frame.png
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-fullscreen-60fps-frame.png
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-stress-summary.json
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-conflict-impact-and-locate.png
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-conflict-located.png
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-archived-readonly.jpg
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-dpi-100-editor.png
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-120-disabled-60hz.png
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-delete-confirmed-ripple.png
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-external-reload-before.jpg
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-external-reload-success.jpg
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-external-reload-external-version.qrproj
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-confirmed-actions-summary.json
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-tray-overflow-before-double-click.jpg
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-tray-double-click-workbench.jpg
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-tray-explicit-exit-menu.jpg
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\evidence\D10-rc3-tray-explicit-exit-process.txt
E:\QRtest\QuickRec-v1.9.3-rc3-120fps-evidence\D10-rc3-gui-120-setting-saved.jpg
E:\QRtest\QuickRec-v1.9.3-rc3-120fps-evidence\D10-rc3-gui-120-recording-result.jpg
E:\QRtest\QuickRec-v1.9.3-rc3-120fps-evidence\D10-rc3-gui-120-ffprobe.json
E:\QRtest\QuickRec-v1.9.3-rc3-120fps-evidence\D10-rc3-gui-120-frame-5s.png
E:\QRtest\QuickRec-v1.9.3-rc3-120fps-evidence\D10-rc3-gui-120-recordings.json
E:\QRtest\QuickRec-v1.9.3-rc3-120fps-evidence\D10-rc3-gui-120-summary.json
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\recordings\QuickRec_20260729_060849.mp4
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\recordings\QuickRec_20260729_061518.mp4
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\recordings\QuickRec_20260729_062110.mp4
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\recordings\QuickRec_20260729_062549.mp4
E:\QRtest\QuickRec-v1.9.3-rc3-acceptance\recordings\QuickRec_20260729_094358.mp4
```

## 9. 历史与 Lite 边界

- v1.9.2 回滚点保持为 `91ab91c` / tag `v1.9.2`；
- 本轮没有移动、创建或覆盖 tag；
- `E:\codex\QuickRec-Lite` 当前分支为 `lite-master`；
- Lite HEAD 为 `cfaee3ed79284d5a184454021177f6ec9de97372`；
- Lite 工作区干净，未被本轮修改。

## 10. 已知限制

1. 发布目录名称保留 RC3 候选编号；其 GUI、CLI 和 ZIP 哈希已经锁定为 v1.9.3
   正式发布资产。
2. 完全静止桌面可能没有新的 DXGI 帧；当前会复用一次性静态首帧并按目标 FPS
   编码，因此输出不再是 0 帧。此时 DXCam 自身的更新 FPS 日志可能显示 0，
   不代表输出视频是 0 FPS。
3. 自动化 CLI 不替代托盘交互和 DPI 视觉验收；三种录制模式、四种音频模式、
   托盘双击恢复同一工作台与托盘显式退出均已通过。100%、125%、150% DPI
   已在真实 Windows 系统缩放下完成工作台、项目页和剪辑工作台检查，验收后
   已恢复为 100%。麦克风与双音频由锁定 frozen CLI 生成真实 MP4，并通过
   运行日志、FFprobe 和音量检测闭合输入链路；未以自动报告替代实际媒体证据。
4. 低刷新率保护已在历史 60 Hz 环境通过；真实 120 FPS 已在单显示器
   `2560×1440@300 Hz` 环境通过能力检测、GUI 录制、FFprobe、抽帧、索引和
   性能日志核对。当前证据只承诺 PRD 规定的单显示器 1080p120，不扩展为
   多显示器、4K 或更高帧率承诺。
5. PyInstaller 报告的 `pycparser.lextab`、`pycparser.yacctab` 和 `sip`
   hidden import 警告属于既有可选导入；实际双入口、PyAV 和媒体工具 smoke
   已通过。
6. v1.9.3 当前不包含正式导出、变速、转场、滤镜、AI 或 QuickRec Lite 改动。

## 11. 当前验证结论

D9 自动化、质量、CI、双入口打包和候选包锁定全部通过。D10 当前完成
`26/26`：真实 120 FPS GUI 与媒体链路、三种录制、四种音频、三档 DPI、
托盘与工作台回归均有锁定 RC3 证据。GUI 和 CLI 哈希复核一致；真实用户
素材索引与配置哈希未变化；QuickRec Lite 工作区干净。

当前结论：

```text
RC3 D10 通过
正式发布
```
