# QuickRec Full v1.9.1 自动验证与候选包记录

## 1. 当前结论

- 当前阶段：D7 自动化与候选包锁定完成，D8 GUI 验收通过。
- 当前结论：**通过**。
- 发布状态：**rc6 验收通过并作为 v1.9.1 正式发布包**。
- 验证日期：2026-07-27。

## 2. 源码身份

| 项目 | 内容 |
| --- | --- |
| 项目路径 | `E:\codex\QuickRec` |
| 发布分支 | `master`，由 `test` 集成 |
| 基线 HEAD | `197943c6cef924ccdc2649b2382689ed08d18b3a` |
| 当前正式版本 | `v1.9.1` |
| 应用版本 | `v1.9.1` |
| 工作区 | v1.9.1 正式发布源 |
| Lite 状态 | `E:\codex\QuickRec-Lite` 未修改 |

## 3. 自动化与质量门禁

| 检查 | 结果 |
| --- | --- |
| 项目标准测试门禁 | `714 passed, 26 deselected, 52 subtests passed` |
| 总体覆盖率 | `85.89%`，高于 80% 门槛 |
| Packaging | `14 passed, 726 deselected` |
| 托盘退出定向测试 | `51 passed` |
| Ruff | 通过 |
| Mypy | 通过，检查 34 个源文件 |
| Compileall | 通过 |
| 差异格式 | `git diff --check` 通过 |
| UTF-8 与乱码 | v1.9.1 文档检查通过 |

硬件标记测试由真实桌面录制证据承接，不纳入标准单元测试门禁；项目配置默认排除
`hardware` 和 `packaging`，其中 packaging 已单独执行。

## 4. 最终候选包身份

打包目录：

```text
E:\QRtest\QuickRec-v1.9.1-rc6-dist\QuickRec
```

| 对象 | 大小 | SHA256 |
| --- | ---: | --- |
| `QuickRec.exe` | `7,099,051` 字节 | `33B7DB1EB96007D75BF933D5600EE813A03ED42390CAE3A93EAD0960B9C6C7D9` |
| `ffmpeg.exe` | `99,264,000` 字节 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| `ffprobe.exe` | `99,066,368` 字节 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |

- EXE 修改时间：2026-07-27 19:31:43。
- 分发目录：244 个文件，共 428,261,683 字节。
- FFmpeg 与 FFprobe 版本：8.0.1。
- rc1 至 rc5 均因后续修复失效，不得作为最终发布包。

## 5. 媒体工具与受控素材

候选包内 FFprobe 已重新解析中文和空格路径样本：

```text
E:\QRtest\QuickRec-v1.9.1-acceptance\evidence\中文 空格\候选包样本.mp4
```

| 项目 | 结果 |
| --- | --- |
| 视频 | H.264、640×360、30 FPS、2.0 秒 |
| 视频 SHA256 | `D316FEFDE7FC4F7F7E039662AEE0B403C9AC410009E4C21B302408FF7E7C74BA` |
| JPEG | 320×180、7,777 字节 |
| JPEG SHA256 | `6B47F74F67A7EAE1F3851BC0FE967C9043754A16F3115EBC871D979CC2BCF234` |

## 6. 真实录制证据

隔离环境：

```text
E:\QRtest\QuickRec-v1.9.1-acceptance\run-20260727-174322
```

| 项目 | 结果 |
| --- | --- |
| 输出文件 | `videos\QuickRec_20260727_174514.mp4` |
| 视频 | H.264、1920×1080、30 FPS、18.8 秒、564 帧、无音频 |
| 文件大小 | 607,332 字节 |
| SHA256 | `7FD319DE2AF3E0F1BD76CD201C2445C51C28D770D3DD8D855D731DCD59CCE7E1` |
| 实际采集 FPS | 约 29.997 |
| 中央索引 | 从 1 条增至 2 条，新增元数据与 FFprobe 一致 |
| 预览协调 | 录制请求时暂停新任务，保存完成后恢复 |

录制核心在后续 rc 之间未变化，因此该候选链路证据可继承到 rc6。

## 7. GUI 与布局证据

- rc3：首帧生成、缓存命中、单项刷新、批量重建、文件缺失恢复、项目与素材库往返、
  0/1/20/50/200 条容量项目。
- rc4：修复预览覆盖操作按钮；实际截图和 100%/125%/150% 自动化 UI
  结构指标均通过。
- rc5：实际打开中文空格路径所在目录并选中素材；实际调用系统播放器打开视频。
- rc6：从托盘打开最终候选工作台；从真实托盘菜单退出后进程自然结束。

关键截图：

```text
E:\QRtest\QuickRec-v1.9.1-acceptance\evidence\rc4-project-buttons-fixed.jpg
E:\QRtest\QuickRec-v1.9.1-acceptance\evidence\rc5-open-directory-unicode-space.jpg
E:\QRtest\QuickRec-v1.9.1-acceptance\evidence\rc5-open-file-player.jpg
E:\QRtest\QuickRec-v1.9.1-acceptance\evidence\rc6-workbench-startup.png
```

## 8. 最终退出清理

rc6 真实托盘退出时间：2026-07-27 19:40:16。

- 日志记录 `thumbnail coordinator shutdown: active=0`。
- 日志记录 `QuickRec 已退出`。
- `QuickRec.exe`、`ffmpeg.exe`、`ffprobe.exe` 均不存在。
- 启动 rc6 的验收进程自然返回退出码 0。

该证据关闭 BUG-191-05，不再存在退出残留发布阻塞。

## 9. 验证边界

- 三种录制模式、四种音频及 60/120 FPS 继承 v1.9 正式验收；
  v1.9.1 未修改对应捕获和音频核心。
- 500 MiB LRU、损坏缓存、并发、取消与失败隔离以自动化和受控集成验证为主。
- QuickRec Lite 不进入本轮功能测试，仅验证工作区未修改。

## 10. 最终判断

自动化、静态检查、打包、媒体工具、真实录制、项目预览、文件操作、DPI 布局和退出清理
均已闭合。rc6 是 v1.9.1 正式发布包的唯一构建来源。
