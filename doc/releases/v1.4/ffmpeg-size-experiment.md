# v1.4 FFmpeg 体积专项实验

## 实验目标

在不外置 FFmpeg、不破坏 H.264 编码、AAC 编码和音频混流能力的前提下，评估是否存在可用于 QuickRec v1.4 的更小 FFmpeg 方案。

## 当前稳定基线

| 项目 | 数值 |
| --- | ---: |
| 当前内置 FFmpeg | `ffmpeg\ffmpeg.exe` |
| FFmpeg 版本 | `8.0.1-essentials_build-www.gyan.dev` |
| FFmpeg 文件体积 | 94.67 MB |
| 稳定产物总体积 | 257.74 MB |

当前稳定版本已验证：

- 包含 `libx264`。
- 包含 `aac`。
- 支持 QuickRec 当前全屏录制链路。
- 支持项目现有音频混流命令。

## 第三方构建候选对比

| 候选 | 来源 | 压缩包体积 | 解压体积 | 运行所需体积 | `libx264` | `aac` | 结论 |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| BtbN GPL static | GitHub BtbN latest | 159.76 MB | 423.15 MB | 136.77 MB | 支持 | 支持 | 比当前 FFmpeg 更大，不采用 |
| BtbN GPL shared | GitHub BtbN latest | 75.99 MB | 199.36 MB | 168.13 MB | 支持 | 支持 | exe 较小但依赖 DLL 后更大，不采用 |
| gyan essentials latest | gyan.dev release essentials | 104.64 MB | 303.83 MB | 97.18 MB | 支持 | 支持 | 比当前 FFmpeg 更大，不采用 |

结论：常见可信 Windows 构建中，没有找到比当前 `8.0.1 essentials` 更小且更适合 QuickRec 的直接替换项。

## UPX 压缩实验

| 项目 | 数值 |
| --- | ---: |
| UPX 版本 | `5.2.0` |
| 压缩前 FFmpeg | 94.67 MB |
| 压缩后 FFmpeg | 24.67 MB |
| 压缩比例 | 26.05% |
| UPX 实验产物总体积 | 187.74 MB |
| 相比稳定产物减少 | 70.00 MB |

已验证：

- UPX 压缩后的 `ffmpeg.exe` 可正常启动。
- `libx264` 编码器存在。
- `aac` 编码器存在。
- 使用 UPX FFmpeg 执行全屏硬件冒烟通过，输出 `E:\QRtest\QuickRec_20260705_123925.mp4`。
- 使用 UPX FFmpeg 生成 H.264 测试视频通过。
- 使用 UPX FFmpeg 生成 WAV 音频通过。
- 使用项目同款 `[1:a][2:a]amerge=inputs=2[a]` + AAC 混流命令通过。
- 替换实验产物 `_internal\ffmpeg\ffmpeg.exe` 后，`dist\pkgsize-upx\QuickRec` 启动冒烟通过。
- `scripts\package_size_report.py --check` 约束检查通过。

标准验证命令：

```powershell
python scripts\ffmpeg_capability_check.py --ffmpeg ffmpeg\ffmpeg.exe --output-dir E:\QRtest\ffmpeg-stable-capability
python scripts\ffmpeg_capability_check.py --ffmpeg experiments\ffmpeg-upx\ffmpeg.exe --output-dir E:\QRtest\ffmpeg-upx-capability
python scripts\package_size_report.py --dist dist\pkgsize-upx\QuickRec --top 20 --check
```

## 风险

| 风险 | 说明 | v1.4 建议 |
| --- | --- | --- |
| 杀软误报 | UPX 压缩可执行文件可能被部分安全软件重点扫描或误报 | 发布前必须在目标环境复验 |
| 启动开销 | UPX 解压会增加首次启动 FFmpeg 子进程的成本 | 需要 10 秒、1 分钟、连续录制回归 |
| 长录制稳定性 | 当前仅完成短时冒烟和合成混流 | 不应仅凭 3 秒冒烟直接替换主线 |
| 可维护性 | 后续更新 FFmpeg 时需要重新压缩、记录版本与校验结果 | 需要脚本化压缩流程 |
| 供应链 | UPX 来自 GitHub 官方 release，仍需记录下载版本和来源 | 若采用，需固定版本和校验哈希 |

## 结论

UPX 是目前唯一能让 v1.4 产物明显低于 200MB 的方案：实验产物从 `257.74MB` 降到 `187.74MB`。

但它属于发布风险更高的二进制压缩策略，不建议直接替换 v1.4 稳定主线。建议作为候选优化保留在 `experiment/v1.4-package-size` 分支，并在完成以下回归后再决定是否合入：

- 全屏录制 10 秒、1 分钟回归。
- 区域录制回归。
- 窗口录制回归。
- 系统音频回归。
- 麦克风回归。
- 双音频混流回归。
- 打包产物连续录制 3 次回归。
- 安全软件误报检查。
