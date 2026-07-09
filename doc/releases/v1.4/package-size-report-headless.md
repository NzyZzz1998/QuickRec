# QuickRec 打包体积分析

- 分析目录：`E:\codex\QuickRec\dist\pkgsize-headless\QuickRec`

- 总体积：256.99 MB

- v1.4 稳定性约束：通过，package constraints ok

## Top 20 大文件
| 路径 | 体积 |
| --- | ---: |
| `_internal/ffmpeg/ffmpeg.exe` | 94.67 MB |
| `_internal/cv2/cv2.pyd` | 71.04 MB |
| `_internal/numpy.libs/libscipy_openblas64_-63c857e738469261263c764a36be9436.dll` | 19.47 MB |
| `_internal/PyQt5/Qt5/bin/Qt5Gui.dll` | 6.68 MB |
| `_internal/python312.dll` | 6.60 MB |
| `QuickRec.exe` | 6.09 MB |
| `_internal/PyQt5/Qt5/bin/Qt5Core.dll` | 5.74 MB |
| `_internal/PyQt5/Qt5/bin/Qt5Widgets.dll` | 5.24 MB |
| `_internal/libcrypto-3.dll` | 4.99 MB |
| `_internal/PyQt5/QtWidgets.pyd` | 4.91 MB |
| `_internal/numpy/_core/_multiarray_umath.cp312-win_amd64.pyd` | 3.54 MB |
| `_internal/PIL/_imaging.cp312-win_amd64.pyd` | 2.47 MB |
| `_internal/PyQt5/QtGui.pyd` | 2.38 MB |
| `_internal/PyQt5/QtCore.pyd` | 2.37 MB |
| `_internal/PIL/_imagingft.cp312-win_amd64.pyd` | 2.07 MB |
| `_internal/PyQt5/Qt5/plugins/platforms/qwindows.dll` | 1.41 MB |
| `_internal/base_library.zip` | 1.27 MB |
| `_internal/unicodedata.pyd` | 1.09 MB |
| `_internal/ucrtbase.dll` | 1011.45 KB |
| `_internal/libssl-3.dll` | 774.27 KB |

## Top 20 大目录
| 路径 | 体积 |
| --- | ---: |
| `_internal` | 250.90 MB |
| `_internal/ffmpeg` | 94.67 MB |
| `_internal/cv2` | 71.07 MB |
| `_internal/PyQt5` | 35.91 MB |
| `_internal/PyQt5/Qt5` | 26.15 MB |
| `_internal/numpy.libs` | 20.02 MB |
| `_internal/PyQt5/Qt5/bin` | 18.40 MB |
| `_internal/numpy` | 5.81 MB |
| `_internal/PyQt5/Qt5/translations` | 4.90 MB |
| `_internal/PIL` | 4.82 MB |
| `_internal/numpy/_core` | 3.60 MB |
| `_internal/PyQt5/Qt5/plugins` | 2.84 MB |
| `_internal/PyQt5/Qt5/plugins/platforms` | 2.13 MB |
| `_internal/numpy/random` | 1.83 MB |
| `_internal/PyQt5/Qt5/plugins/imageformats` | 449.97 KB |
| `_internal/pyaudio` | 294.50 KB |
| `_internal/numpy/fft` | 270.00 KB |
| `_internal/numpy-2.4.6.dist-info` | 207.19 KB |
| `_internal/PyQt5/Qt5/plugins/styles` | 140.98 KB |
| `_internal/numpy/linalg` | 109.50 KB |

## 组件体积
| 组件 | 体积 |
| --- | ---: |
| FFmpeg | 94.67 MB |
| OpenCV/cv2 | 71.07 MB |
| Qt/PyQt5 | 35.91 MB |
| NumPy | 25.83 MB |
| Python runtime | 13.69 MB |
| Other | 10.98 MB |
| PIL/Pillow | 4.82 MB |
| soundcard | 33.58 KB |

## headless OpenCV 实验结论

### 对比结果

| 项目 | 稳定产物 `dist\QuickRec` | headless 实验产物 `dist\pkgsize-headless\QuickRec` | 差异 |
| --- | ---: | ---: | ---: |
| 总体积 | 257.74 MB | 256.99 MB | -0.75 MB |
| OpenCV/cv2 | 71.38 MB | 71.07 MB | -0.31 MB |
| Other | 11.42 MB | 10.98 MB | -0.44 MB |

### 已验证项

- `opencv-python-headless==4.13.0.92` 可安装并导入 `cv2`。
- `dxcam` 在 headless 环境中可导入。
- 使用 headless 环境运行 `scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen` 通过。
- 生成输出：`E:\QRtest\QuickRec_20260705_122742.mp4`。
- 从输出视频抽帧检查通过：分辨率 `854x480`，RGB 均值 `[30.86, 33.29, 31.6]`，像素范围包含有效画面信息。
- 使用 headless 环境打包成功，产物目录：`dist\pkgsize-headless\QuickRec`。
- headless 打包产物启动冒烟通过：进程可启动并保持运行。
- v1.4 稳定性约束检查通过：FFmpeg 内置、cv2 保留、OpenCV videoio ffmpeg 未进入产物。

### 结论

`opencv-python-headless` 在当前 QuickRec 依赖组合下体积收益很小，约减少 `0.75MB`，不足以显著改善 257MB 级别的打包体积。由于 QuickRec 当前最大体积来源仍是 FFmpeg 和 `cv2.pyd` 本体，headless 替换不能作为 v1.4 主线的关键优化策略。

建议：

- v1.4 主线继续保留当前 `opencv-python`，避免临近发布引入依赖替换风险。
- headless OpenCV 可作为后续 lite 分支候选项，但只有在完整通过区域录制、窗口录制、系统音频、麦克风和混流回归后才应采用。
- 若后续目标是明显降低体积，应优先研究更小 FFmpeg 构建和 lite 分支功能依赖裁剪，而不是单独替换 headless OpenCV。
