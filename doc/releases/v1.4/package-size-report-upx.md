# QuickRec 打包体积分析

- 分析目录：`E:\codex\QuickRec\dist\pkgsize-upx\QuickRec`

- 总体积：187.89 MB

- v1.4 稳定性约束：通过，package constraints ok

## Top 20 大文件
| 路径 | 体积 |
| --- | ---: |
| `_internal/cv2/cv2.pyd` | 71.35 MB |
| `_internal/ffmpeg/ffmpeg.exe` | 24.67 MB |
| `_internal/numpy.libs/libscipy_openblas64_-63c857e738469261263c764a36be9436.dll` | 19.47 MB |
| `_internal/PyQt5/Qt5/bin/Qt5Gui.dll` | 6.68 MB |
| `_internal/python312.dll` | 6.60 MB |
| `QuickRec.exe` | 6.47 MB |
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
| `_internal` | 181.42 MB |
| `_internal/cv2` | 71.38 MB |
| `_internal/PyQt5` | 35.91 MB |
| `_internal/PyQt5/Qt5` | 26.15 MB |
| `_internal/ffmpeg` | 24.67 MB |
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
| `_internal/numpy-2.4.6.dist-info` | 207.10 KB |
| `_internal/PyQt5/Qt5/plugins/styles` | 140.98 KB |
| `_internal/numpy/linalg` | 109.50 KB |

## 组件体积
| 组件 | 体积 |
| --- | ---: |
| OpenCV/cv2 | 71.38 MB |
| Qt/PyQt5 | 35.91 MB |
| NumPy | 25.83 MB |
| FFmpeg | 24.67 MB |
| Python runtime | 13.69 MB |
| Other | 11.57 MB |
| PIL/Pillow | 4.82 MB |
| soundcard | 33.58 KB |

## v1.4 UPX FFmpeg 体积实验结论

- UPX 实验产物体积为 `187.89MB`。
- 相比稳定产物 `257.89MB`，减少约 `70.00MB`，主要收益来自 FFmpeg 从 `94.67MB` 降至 `24.67MB`。
- 实验包仍保留 cv2、PyQt5、NumPy 和项目内置 FFmpeg，录制链路与稳定包保持一致。
- 该方案仅作为后续候选优化继续回归；v1.4 正式发布继续使用未压缩 FFmpeg 的稳定包。
- 合入主线前仍需完成区域录制、窗口录制、真实音频混流和杀软误报验证。
