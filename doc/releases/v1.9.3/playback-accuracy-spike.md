# QuickRec Full v1.9.3 非零源入点播放准确性技术门禁

## 1. 结论

结论：**通过**。

当前 PyAV 播放链路在受控 H.264/AAC 样本、中文与空格路径、源码环境和真实
PyInstaller frozen 环境中均达到 v1.9.3 的裁剪、分割与连续播放门槛，可以进入
timeline schema v2 和剪辑领域实现。

本结论仅覆盖 v1.9.3 D1 技术门禁，不替代 D6 生产时间线复验、D9 候选包验证或
D10 GUI 验收。

## 2. 验证对象

| 项目 | 内容 |
| --- | --- |
| 分支 | `master` |
| 基线 HEAD | `91ab91cba324658d9bfadb7016a31f8e4e380efb` |
| 正式回滚点 | tag `v1.9.2` |
| Python | 3.12.8 |
| 系统 | Windows 11，64 位 |
| 媒体生成器 | `scripts/generate_v193_editing_media.py` |
| 门禁脚本 | `scripts/v193_playback_accuracy_spike.py` |
| 自动测试 | `tests/test_v193_playback_accuracy.py` |
| 证据目录 | `E:\QRtest\QuickRec-v1.9.3-playback-spike` |

## 3. 受控媒体

生成器使用项目自带 FFmpeg 生成以下样本：

1. 30 秒、640×360、30 FPS、H.264/AAC，画面包含连续帧号与时间码；
2. 6 秒、640×360、60 FPS、H.264/AAC；
3. 6 秒、640×360、120 FPS、H.264/AAC；
4. 6 秒、640×360、30 FPS、无声 H.264；
5. 10 分钟、320×180、30 FPS、H.264/AAC；
6. 与 30 FPS 样本字节一致的中文和空格路径副本。

AAC 边界样本每秒在正负固定电平间切换，可量化目标点前采样、接缝重叠和间隙。
完整生成命令、FFprobe 输出、文件大小和 SHA256 位于：

```text
E:\QRtest\QuickRec-v1.9.3-playback-spike\media\media-manifest.json
SHA256:
7E215D02EF8C19926E0E6EAC5BAE004006B961751ED1B0DD922EDE1244C6A0B4
```

## 4. 先失败后修复

### 4.1 AAC 非零源入点

初始失败证据：

- 在 1 秒目标点执行 backward seek；
- 返回块均值为 `-0.150084`；
- 目标点前负采样占比为 `46.67%`。

根因：

`_AvAudioDecoder` 从目标点之前的关键位置开始解码，但 `_fill()` 无条件接收整个
重采样帧，同时把逻辑游标直接设置为目标时间，导致目标点之前的 AAC 采样被当成
目标点之后内容。

修复：

- 保留 seek 目标时间；
- 依据重采样帧 `pts/time_base` 丢弃目标点前的完整帧；
- 对跨越目标点的帧进行采样级裁切；
- 时间戳缺失时明确失败，不静默返回错误音频。

### 4.2 分割点重复视频帧

初始失败证据：

- 左片段最后一帧区间为 `[966667, 1000000)` 微秒；
- 右片段从 `1000000` 微秒开始；
- 解码器仍返回左片段最后一帧，形成一帧重复。

根因：

视频帧命中判断使用闭区间 `target <= frame_end`，把相邻帧共同边界归给前一帧。

修复：

统一使用半开区间 `[frame_start, frame_end)`。分割点现在返回右侧第一帧，接缝
间隔为 `0` 微秒且画面不重复。

### 4.3 解码资源释放

初始失败证据：

容器关闭后对象仍持有 decode 迭代器与 stream 引用，45 个编解码线程在对象销毁前
保持存活。

修复：

`release()` 同步清空迭代器、stream、resampler、图像和音频缓存引用。源码与 frozen
环境中释放后线程增量和子进程增量均为 `0`。

## 5. 精确指标

| 检查项 | 源码环境 | Frozen 环境 | 门槛 | 结论 |
| --- | ---: | ---: | ---: | --- |
| 30 FPS 非关键帧 seek | 0.51 帧 / 74.43 ms | 0.51 帧 / 83.49 ms | ≤1 帧且 ≤500 ms | 通过 |
| 60 FPS 非关键帧 seek | 0.51 帧 / 141.74 ms | 0.51 帧 / 165.34 ms | ≤1 帧且 ≤500 ms | 通过 |
| 120 FPS 非关键帧 seek | 0.51 帧 / 277.19 ms | 0.51 帧 / 309.29 ms | ≤1 帧且 ≤500 ms | 通过 |
| 中文与空格路径 | 0.51 帧 / 74.02 ms | 0.51 帧 / 81.18 ms | ≤1 帧且 ≤500 ms | 通过 |
| AAC 非零入点 | 0 ms | 0 ms | ≤20 ms | 通过 |
| 连续视频分割接缝 | 0 μs，无重复帧 | 0 μs，无重复帧 | ≤1 源帧 | 通过 |
| 30 秒音画绝对偏差 | 末端 16 ms | 末端 16 ms | ≤40 ms | 通过 |
| 10 分钟音画漂移增量 | 0 ms | 0 ms | ≤20 ms | 通过 |
| Backend seek | 65.83 ms | 69.19 ms | ≤500 ms | 通过 |
| Backend pause | 0.005 ms | 0.004 ms | ≤200 ms | 通过 |
| Backend release | 1.90 ms | 1.90 ms | ≤2000 ms | 通过 |
| 释放后线程/子进程增量 | 0 / 0 | 0 / 0 | 0 / 0 | 通过 |
| 无声 H.264 | 1 视频流、0 音频流 | 相同 | 可解析且无音频流 | 通过 |

## 6. 自动测试

```text
python -m pytest \
  tests/test_v193_playback_accuracy.py \
  tests/test_pyav_playback_backend.py \
  tests/test_playback_backend_integration.py -q

16 passed
```

其中包含真实 FFmpeg 生成媒体，覆盖：

- 非关键帧 seek；
- 精确帧边界不重复；
- AAC 目标点前采样裁切；
- 非零 `source_start_us` 播放计划；
- 既有 PyAV 后端与集成回归。

## 7. 源码与 Frozen 证据

### 源码

```text
报告：
E:\QRtest\QuickRec-v1.9.3-playback-spike\source-report.json
SHA256:
6977473AB208BB6B6B558DB1E6B75C1733CA87A5F67DC518D410A2543B53BD84
```

### Frozen

```text
EXE：
E:\QRtest\QuickRec-v1.9.3-playback-spike\frozen-dist\
QuickRecV193PlaybackSpike\QuickRecV193PlaybackSpike.exe
大小：5,212,171 bytes
SHA256:
1E0D1D295188312559F6FB038AC44CF132761A0EC54B9F670B0A4A6E4AB80248

报告：
E:\QRtest\QuickRec-v1.9.3-playback-spike\frozen-report.json
SHA256:
494163EB11F2616C4A7A2DCEAA61DCD48C1B86F1305407023E39CFE8C058DC1A
```

两个报告引用相同 manifest，检查项全部为 `passed=true`。

## 8. 后续边界

1. D2-D5 可以开始实现，但不得把本报告当作 GUI 验收。
2. D6 必须使用正式时间线、裁剪和分割结果重新执行同一协议。
3. D9 必须在最终 `QuickRec.exe` 与 `QuickRecCLI.exe` 候选包环境复验。
4. D10 仍需真实播放、听音、窗口切换和退出操作证据。
5. 其他编码格式不是 v1.9.3 正式承诺；正式门槛仍是 QuickRec 自身生成的
   H.264/AAC MP4。
