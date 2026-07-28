# QuickRec Full v1.9.2 受控媒体夹具

## 1. 边界

仓库不提交大体积 MP4、播放 DLL 或候选分发包。本目录只保存：

- 媒体样本的来源、格式和 SHA256；
- 可重复生成命令；
- 与时间线 schema 相关的小型 JSON fixture。

真实媒体默认生成到被 Git 忽略的：

```text
E:\codex\QuickRec\build\v1.9.2-playback-spike\
```

发布候选和 GUI 验收证据后续存放到 `E:\QRtest` 的独立 v1.9.2 目录，不覆盖历史版本证据。

## 2. 既有 QuickRec 样本

以下文件来自既有受控验收目录，只读复用，不修改：

| 文件 | 时长 | 视频 | 音频 | SHA256 |
| --- | ---: | --- | --- | --- |
| `E:\QRtest\pkg_audio\QuickRec_20260719_203053.mp4` | 33.967 秒 | H.264，1920×1080，30 FPS | AAC，48 kHz，2 ch | `BC3787B5647687766C1E955E20033FD767F339C92317EF9642F789C1D379CC0C` |
| `E:\QRtest\pkg_audio\QuickRec_20260719_211720.mp4` | 20.400 秒 | H.264，1440×1080，30 FPS | AAC，48 kHz，2 ch | `6C23FBC7EFD1D3644820BDDBDCB968BCC33344B9F2B893985224A4CB00764834` |
| `E:\QRtest\pkg_audio\QuickRec_20260719_212217.mp4` | 16.967 秒 | H.264，1122×632，30 FPS | AAC，48 kHz，2 ch | `6CEBC84368A840479C5F290714FF01D65BE234376BEB410AA18381E667A3759B` |
| `E:\QRtest\pkg_audio\QuickRec_20260719_212407.mp4` | 26.433 秒 | H.264，1920×1080，30 FPS | AAC，48 kHz，2 ch | `412D3A52C54E9CC7A3C3DF6751BFD1425D3C02A78C172C75DB2396F95C1A7A14` |
| `E:\QRtest\pkg_audio\QuickRec_20260719_212546.mp4` | 6.333 秒 | H.264，1920×1080，30 FPS | AAC，48 kHz，2 ch | `0527A26625966EC1856F42D8D66E0FE7195D335A686D5A890890CAC81B3C2127` |

## 3. D1 生成样本

D1 已在忽略的本地目录生成：

1. `sample-a-30s.mp4`：可辨识测试画面与 440 Hz 音频。
2. `sample-b-30s.mp4`：不同可辨识画面与 660 Hz 音频。
3. `sample-c-30s.mp4`、`sample-d-30s.mp4`：四音源混合补充样本。
4. `sample-silent-30s.mp4`：无音频流。
5. `中文 空格 样本.mp4`：中文和空格路径样本。
6. `sample-long-10m.mp4`：低复杂度 10 分钟样本。
7. `sample-corrupt.mp4`：损坏伪 MP4，只用于失败路径。

生成参数、文件身份和 FFmpeg/FFprobe 摘要记录在 D1 JSON 报告与
`playback-backend-spike.md` 中。媒体不提交仓库。

## 4. D2 时间线 JSON 夹具

| 文件 | 用途 |
| --- | --- |
| `project_timeline_missing.json` | v1.9/v1.9.1 无时间线项目，无感返回内存空时间线 |
| `project_timeline_v1_normal.json` | schema v1、关联音视频和未知字段往返 |
| `project_timeline_v1_corrupt.json` | 项目有效但时间线同轨重叠，验证错误隔离 |
| `project_timeline_v99_unknown.json` | 未知新版本只读与原始扩展保留 |

## 5. 数据保护

- 不修改本表列出的既有 MP4。
- 不使用用户真实项目或中央索引作为测试夹具。
- 不把测试媒体写入 `%APPDATA%\QuickRec`。
- 损坏、缺失、权限和后端失败测试只使用受控目录。
- 任何失败注入结束后恢复依赖、权限、进程和音频设备状态。
