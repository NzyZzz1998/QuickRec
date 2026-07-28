# QuickRec Full v1.9.2 播放后端技术 Spike

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 目标版本 | QuickRec Full v1.9.2 |
| 验证阶段 | D1 播放后端技术门禁 |
| 验证日期 | 2026-07-28 |
| 实施分支 | `test` |
| 实施基线 | `402c2c6` / tag `v1.9.1` |
| 最终结论 | 选定 PyAV 18.0.0 |
| 生产依赖状态 | D1 仅锁定方案，生产依赖在 D7 接入 |
| QuickRec Lite | 未修改 |

## 2. 决策摘要

v1.9.2 选择 **PyAV 18.0.0 + Qt 图像表面 + QuickRec 既有
PyAudio 输出链路** 作为唯一生产播放方案。

选择原因：

1. PyAV 是三个候选中唯一同时通过源码环境和最小 PyInstaller
   冻结环境硬门槛的方案。
2. PyAV 可以由 QuickRec 自己控制活动视频轨选择、四路音频固定混合、
   单调时钟、跳转和资源释放，符合本版固定规则。
3. libmpv 的单素材播放性能合格，但多源固定视频覆盖和四路独立音频混合
   仍需要额外合成图或多实例同步，不能作为当前架构的完整后端。
4. Qt Multimedia 5.15.2 在当前 Windows/PyQt5 基线下未能可靠进入
   可播放状态，且资源释放检查存在残留线程。

该结论不代表立即修改生产依赖。D2-D6 继续使用纯模型、命令和后端
Protocol；到 D7 时只接入 PyAV，不把 libmpv 或 Qt Multimedia 加入正式包。

## 3. 候选、来源与许可证

| 候选 | 固定版本 | 来源 | 许可证与分发边界 |
| --- | --- | --- | --- |
| PyAV | 18.0.0 | PyPI 官方 wheel、PyAV 官方文档 | PyAV 为 BSD 3-Clause；wheel 内 FFmpeg 运行时报告为 LGPL v3+ |
| python-mpv | 1.0.8 | PyPI | Python 绑定；最终义务仍取决于 libmpv 构建 |
| libmpv | v0.41.0-724-g71ebd0840 | SourceForge Windows 构建 | 仅确认 `-Dlibmpv=true`，未闭合 LGPL-only 分发证据 |
| Qt Multimedia | Qt 5.15.2 / PyQt5 5.15.11 | PyPI 与 Qt 官方接口 | 沿用项目现有 PyQt5 GPL/商业授权边界 |

参考资料：

- PyAV 安装与二进制 wheel：
  <https://pyav.org/docs/develop/overview/installation.html>
- mpv 手册：<https://mpv.io/manual/stable/>
- libmpv 示例：
  <https://github.com/mpv-player/mpv-examples/blob/master/libmpv/README.md>
- Qt `QMediaPlayer`：
  <https://doc.qt.io/qt-6/qmediaplayer.html>
- SourceForge libmpv 构建：
  <https://sourceforge.net/projects/mpv-player-windows/files/libmpv/>

正式分发时必须随包提供 PyAV、FFmpeg 及其启用组件对应的许可证与
notice，并保留可替换的动态库边界。D9 必须再次核对最终 wheel、DLL
清单和许可证，不能仅沿用本报告结论。libmpv 和 Qt Multimedia 均不进入
本版正式依赖，因此不承担其新增分发集成。

## 4. 统一验证协议

三个候选使用相同受控输入与硬门槛：

- H.264/AAC 30 秒样本；
- H.264 无声 30 秒样本；
- 中文和空格路径；
- 两个连续片段；
- 两条重叠视频轨的固定顶层选择；
- 四个独立音频源固定等增益混合；
- 缺失素材与损坏素材；
- 10 分钟 H.264/AAC 样本；
- 播放准备、随机跳转、暂停、音画偏差、长时漂移；
- 页面切换、项目关闭与应用退出后的线程和子进程；
- 等价 frozen 环境与最小 PyInstaller 包。

| 指标 | 硬门槛 |
| --- | --- |
| 首次播放准备 | 不超过 1500 ms |
| 随机跳转 | 不超过 500 ms |
| 暂停响应 | 不超过 200 ms |
| 音画绝对偏差 | 不超过 40 ms |
| 10 分钟漂移增量 | 不超过 20 ms |
| 资源释放 | 无新增残留线程和媒体子进程 |

CPU 与内存只作为诊断数据，不作为单独淘汰条件。

## 5. 测试样本与证据

受控媒体位于忽略的本地目录：

```text
E:\codex\QuickRec\build\v1.9.2-playback-spike
```

核心样本：

```text
sample-a-30s.mp4
sample-b-30s.mp4
sample-c-30s.mp4
sample-d-30s.mp4
sample-silent-30s.mp4
sample-long-10m.mp4
中文 空格 样本.mp4
sample-corrupt.mp4
```

样本清单和既有 QuickRec 媒体登记见
`tests/fixtures/v1_9_2/README.md`。统一脚本为
`scripts/playback_backend_spike.py`，脚本测试为
`tests/test_playback_backend_spike.py`。

## 6. 验证结果

### 6.1 总表

| 候选 | 源码环境 | Frozen/最小包 | 固定顶层视频 | 四路音频混合 | 资源释放 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| PyAV 18.0.0 | 通过 | 通过 | 通过 | 通过 | 通过 | 选定 |
| libmpv | 单路通过 | 未继续 | 未通过 | 未通过 | 通过 | 淘汰 |
| Qt Multimedia | 未通过 | 未继续 | 未进入 | 未进入 | 未通过 | 淘汰 |

### 6.2 PyAV 源码环境

证据：`build\v1.9.2-playback-spike\pyav-report.json`

| 指标 | 实际值 | 结论 |
| --- | --- | --- |
| 播放准备 | 5.71 ms | 通过 |
| 最慢随机跳转 | 34.55 ms | 通过 |
| 暂停响应 | 1.94 ms | 通过 |
| 起始音画偏差 | 0 ms | 通过 |
| 10 分钟漂移增量 | 0 ms | 通过 |
| 无声 H.264 | 900 视频帧、0 音频帧 | 通过 |
| 中文与空格路径 | 全部启动低于 6 ms | 通过 |
| 四路音频混合 | 48 kHz、双声道、有限值 | 通过 |
| 真实音频输出 | 默认设备成功写入 12000 帧 | 通过 |
| 固定顶层视频 | 只解码最高活动视频轨 | 通过 |
| 缺失与损坏素材 | 明确拒绝 | 通过 |
| 资源释放 | 线程增量 0、子进程增量 0 | 通过 |

### 6.3 PyAV Frozen 环境

证据：

```text
build\v1.9.2-playback-spike\pyav-frozen-report.json
build\v1.9.2-playback-spike\pyinstaller-dist\PlaybackSpikePyAV
```

| 指标 | 实际值 | 结论 |
| --- | --- | --- |
| 播放准备 | 4.54 ms | 通过 |
| 最慢随机跳转 | 35.09 ms | 通过 |
| 暂停响应 | 2.32 ms | 通过 |
| 起始音画偏差 | 0 ms | 通过 |
| 10 分钟漂移增量 | 0 ms | 通过 |
| 固定顶层视频 | 通过 | 通过 |
| 四路音频混合和真实输出 | 通过 | 通过 |
| 资源释放 | 线程增量 0、子进程增量 0 | 通过 |

最小冻结包身份：

| 项目 | 数值 |
| --- | --- |
| 文件数 | 179 |
| 分发目录大小 | 119,560,597 bytes（约 114.02 MiB） |
| EXE 大小 | 4,551,234 bytes |
| EXE SHA256 | `14C8BAE686C32A77BAE765AA73C572155232F8533BE6CF387B8CEC7887001499` |

该体积是独立 spike 包，不是 v1.9.2 最终包。主要增量来自 PyAV wheel
携带的 FFmpeg 动态库、OpenBLAS 和编解码组件。D9 必须记录正式包增量，
但体积不改变本轮后端结论。

### 6.4 libmpv

证据：

```text
build\v1.9.2-playback-spike\libmpv-report.json
build\v1.9.2-playback-spike\libmpv\libmpv-2.dll
```

单素材指标：

| 指标 | 实际值 | 结论 |
| --- | --- | --- |
| 播放准备 | 19.72 ms | 通过 |
| 最慢随机跳转 | 42.44 ms | 通过 |
| 暂停响应 | 0.13 ms | 通过 |
| 音画偏差 | 0 ms | 通过 |
| 资源释放 | 无子进程残留 | 通过 |

淘汰原因：

1. 当前单实例探针不能证明多源情况下的固定顶层视频规则。
2. 四个独立时间线音频源需要自定义滤镜图或多实例同步。
3. 若再为多轨规则建立第二套合成层，libmpv 的一体化播放器优势消失。
4. `libmpv-2.dll` 单文件为 117,549,568 bytes，分发许可证证据仍需额外闭合。

DLL SHA256：

```text
02FA97CBDB32A651ADDBB0EAFCDC8446E3B4CB7A09DA83518DAC4FBF8D62FD81
```

### 6.5 Qt Multimedia

证据：`build\v1.9.2-playback-spike\qt-report.json`

淘汰原因：

1. 当前 Windows/PyQt5 5.15.2 环境无法在门禁时间内稳定进入可播放状态。
2. 失败后存在 6 个相对基线新增线程，未满足资源释放要求。
3. 单路基线尚未通过，不再继续多轨和 frozen 验证。

## 7. 实施约束

后续生产实现必须遵守：

1. 时间线模型、命令和运行时通过 Protocol 与 PyAV 适配器隔离。
2. 使用 QuickRec 单调媒体时钟，不让多个播放器实例各自决定时间。
3. 每个时刻只解码最高活动视频轨；顶层失败时显示错误占位，不露出下层。
4. 活动音频源按固定衰减混合并进行安全限幅。
5. PyAV 容器打开期间完成 stream/codec 元数据快照；容器关闭后不保留
   `Stream` 或 `CodecContext` 对象。
6. 解码时显式选择视频流和音频流，不依赖模糊的全容器遍历。
7. 素材缺失、损坏、无音频和设备不可用必须是可区分状态。
8. 适配器释放必须幂等，项目切换、页面关闭和退出均执行同一释放路径。
9. D7 才允许将 PyAV 加入 `requirements.txt` 和 `build_std.spec`。
10. D9 对最终包重新执行真实媒体、许可证、DLL、体积和 SHA256 验证。

## 8. 已知风险

| 风险 | 等级 | 处理 |
| --- | --- | --- |
| 软件解码与四路音频混合增加 CPU 占用 | 中 | D7 记录 CPU/内存，D10 使用真实项目复验 |
| PyAV wheel 增加包体积 | 中 | D9 比较 v1.9.1 与候选包，不在 D1 盲目裁剪 |
| Qt 图像上传可能成为高分辨率瓶颈 | 中 | 使用单视频源、帧率节流和真实 GUI 指标验证 |
| 音频设备切换或不可用 | 中 | 允许无声预览，并提供明确提示 |
| FFmpeg 组件许可证清单遗漏 | 高 | D9 将许可证和动态库清单设为 packaging 门禁 |

## 9. 最终门禁结论

**D1 通过。**

- 唯一选定后端：PyAV 18.0.0。
- Qt 负责最终图像表面，PyAudio 负责固定混合后的音频输出。
- libmpv 和 Qt Multimedia 不进入 v1.9.2 生产依赖。
- 源码与 frozen 结果一致。
- 许可证、体积、失败原因和后续打包义务已记录。
- 可以进入 D2 时间线模型与 schema 实现。
