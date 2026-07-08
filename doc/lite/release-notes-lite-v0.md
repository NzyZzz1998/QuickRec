# QuickRec Lite v0 Release Notes

发布日期：2026-07-08

## 发布定位

QuickRec Lite v0 是从 QuickRec v1.4 稳定基线拆分出的轻量级录屏版本。Lite 不是 Full 的运行时模式或免费版，而是一条独立产品线，目标是保持低心智负担、少入口、少配置和稳定的一键全屏录制体验。

Lite v0 正式发布使用 PyInstaller 稳定包：

```text
dist/QuickRec/QuickRec.exe
```

## 主要变化

### 保留能力

- 保留全屏录制作为唯一用户可见录制模式。
- 固定原生分辨率输出。
- 固定 60fps 输出。
- 保留无声、系统声音、麦克风、系统声音 + 麦克风四种音频模式。
- 保留开始、暂停/恢复、停止三组快捷键。
- 保留保存路径、音频源、快捷键和开机自启设置。
- 保留 Toast 通知、工具栏结果条、打开文件和打开文件夹能力。

### 裁剪能力

- 移除区域录制用户入口。
- 移除窗口录制用户入口。
- 移除区域录制快捷键设置。
- 移除窗口录制快捷键设置。
- 移除画质和帧率设置，统一使用原生分辨率 + 60fps。
- 移除录制倒计时入口。
- 移除鼠标点击高亮入口和运行路径。
- 不提供 Full 创作者工作台能力，例如录制历史、素材管理、轻编辑、导出队列和质量诊断中心。

## 打包产物

- 打包命令：`python -m PyInstaller build_std.spec --clean --noconfirm`
- 打包目录：`dist/QuickRec`
- 可执行文件：`dist/QuickRec/QuickRec.exe`
- 产物总体积：`257.89 MB`
- 体积目标：低于 `200 MB`
- 发布判断：未低于 200MB，但体积目标不作为 Lite v0 发布阻断项。

主要体积来源：

- FFmpeg：`94.67 MB`
- OpenCV/cv2：`71.38 MB`
- Qt/PyQt5：`35.91 MB`
- NumPy：`25.83 MB`
- Python runtime：`13.69 MB`

详细体积报告见 `doc/lite/lite-v0-package-size-report.md`。

## 验证结果

- `python -m pytest -q`：`231 passed, 23 deselected, 18 subtests passed`
- `python -m compileall src scripts tests`：通过
- `python -m ruff check .`：通过
- `python -m mypy`：通过
- `python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen`：通过
- 设置窗口 Computer Use 验证：通过
- 源码应用全屏录制、暂停/恢复、停止、保存、Toast、结果条、打开文件和打开文件夹：通过
- 四种音频模式：通过
- PyInstaller 打包：通过
- 打包产物启动：通过
- 打包产物全屏录制：通过

打包产物验证输出：

```text
E:\QRtest\QuickRec_20260708_152150.mp4
```

输出元数据：

- 视频：H.264，`2560x1440`，60fps
- 音频：AAC，48000Hz

## 已知限制

- 当前仅支持主显示器全屏录制。
- 打包体积仍高于 200MB，主要受 FFmpeg、cv2、PyQt5 和 NumPy 影响。
- Lite v0 暂不删除底层区域/窗口录制代码，只移除用户可见入口，以降低从 v1.4 分支拆分时的回归风险。
- CI 无法覆盖真实桌面和真实音频设备，发布前仍依赖本地硬件验收。

## 后续方向

- 继续评估更小 FFmpeg 构建或安全压缩方案。
- 继续评估 OpenCV/cv2 替代或隔离方案，但不以破坏 dxcam 稳定捕获链路为代价。
- 在 Lite v0.1 中评估是否彻底删除或隔离区域/窗口录制底层代码。
- Full 分支继续保留复杂录制能力和创作者工作台规划。
