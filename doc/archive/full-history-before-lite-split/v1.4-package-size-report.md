# QuickRec 打包体积分析

- 分析目录：`E:\codex\QuickRec\dist\QuickRec`

- 总体积：257.89 MB

- v1.4 稳定性约束：通过，package constraints ok

## Top 20 大文件
| 路径 | 体积 |
| --- | ---: |
| `_internal/ffmpeg/ffmpeg.exe` | 94.67 MB |
| `_internal/cv2/cv2.pyd` | 71.35 MB |
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
| `_internal` | 251.42 MB |
| `_internal/ffmpeg` | 94.67 MB |
| `_internal/cv2` | 71.38 MB |
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
| `_internal/numpy-2.4.6.dist-info` | 207.10 KB |
| `_internal/PyQt5/Qt5/plugins/styles` | 140.98 KB |
| `_internal/numpy/linalg` | 109.50 KB |

## 组件体积
| 组件 | 体积 |
| --- | ---: |
| FFmpeg | 94.67 MB |
| OpenCV/cv2 | 71.38 MB |
| Qt/PyQt5 | 35.91 MB |
| NumPy | 25.83 MB |
| Python runtime | 13.69 MB |
| Other | 11.57 MB |
| PIL/Pillow | 4.82 MB |
| soundcard | 33.58 KB |

## v1.4 打包体积优化结论

- 稳定产物体积为 `257.89MB`。
- 主要体积来源仍是 FFmpeg、OpenCV/cv2、Qt/PyQt5 和 NumPy。
- v1.4 正式发布候选使用当前稳定包，保留原始 FFmpeg 与 cv2，优先保证录制稳定性。
- UPX FFmpeg 实验产物可降至 `187.89MB`，但因仍需完整区域/窗口/真实音频/杀软误报回归，暂不合入 v1.4 正式发布。
