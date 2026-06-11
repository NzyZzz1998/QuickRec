# QuickRec Bug 修复日志

> 创建时间: 2026-06-11
> 最后更新: 2026-06-11

## Bug 列表与修复

### Bug #1: pystray 回调线程安全问题 [严重]

**症状**: 托盘菜单操作（开始录制、设置、退出）可能导致程序崩溃或未定义行为

**根因**: `pystray.Icon.run_detached()` 在独立线程运行，所有回调（`_on_start`, `_on_settings`, `_on_exit`）都在 pystray 线程中执行。但 Qt 组件只能在主线程中操作。直接在 pystray 线程调用 `QApplication.quit()` 等操作会导致崩溃。

**另外**: `_on_exit` 中在 pystray 自身的回调内调用 `self._icon.stop()`，可能导致死锁。

**修复** (`src/ui/tray_icon.py`):
- 引入 `_SignalBridge(QObject)` 信号桥类，将 pystray 线程回调通过 `pyqtSignal` 转发到 Qt 主线程
- `_on_start/_on_settings/_on_exit` 只发信号，不做 Qt 操作
- 新增 `_handle_start/_handle_settings/_handle_exit` 在 Qt 主线程执行实际逻辑
- `_handle_exit` 使用 `QTimer.singleShot(0, self._stop_icon)` 延迟停止图标，避免死锁
- `_on_open_folder` 是纯 IO 操作（`webbrowser.open`），无需线程转发

---

### Bug #2: 暂停录制无法停止 [严重]

**症状**: 在暂停状态下无法停止录制，录制线程永远阻塞

**根因**: `RecorderManager.stop()` 的逻辑有两个问题：
1. 先设置 `self._state = STOPPING`，然后检查 `if self._state == PAUSED`——由于已经改为 STOPPING，这个条件永远为 False，暂停中的录制线程无法被唤醒
2. `_record_loop` 中暂停时用 `time.sleep(0.05)` 忙等待，浪费 CPU

**修复** (`src/recorder/recorder_manager.py`):
- 将 `_pause_event` 重命名为 `_resume_event`，语义反转：`set()` = 可录制，`clear()` = 暂停中
- 暂停时 `clear()` → 录制线程在 `_resume_event.wait(timeout=0.1)` 处阻塞
- 恢复时 `set()` → 唤醒录制线程继续
- 停止时同时 `set()` `_resume_event` 和 `_stop_event`，确保无论是否暂停都能唤醒线程退出
- `stop()` 中先保存 `was_paused` 状态再修改为 STOPPING

---

### Bug #3: keyboard 库需要管理员权限 [严重]

**症状**: 全局快捷键（Ctrl+Shift+R/S/P）完全不工作

**根因**: `keyboard` 库在 Windows 上需要管理员权限才能拦截全局按键。普通用户运行 exe 时，`add_hotkey()` 静默失败，快捷键不响应。

**修复** (`src/hotkey/hotkey_manager.py`):
- 完全替换为 `pynput` 库，使用 `pynput.keyboard.Listener` 监听全局按键
- `pynput` 不需要管理员权限即可工作
- 实现基于键集合匹配的热键检测：`_match_hotkey()` 检查当前按下的键集合是否匹配注册的快捷键
- 支持 Ctrl/Shift/Alt 左右键的兼容匹配
- `start_listening()` / `stop_listening()` 管理 Listener 的生命周期
- 配置保存后重新绑定快捷键时需要调用 `start_listening()`（在 `main.py` 中修复）

**相关修改**:
- `requirements.txt`: `keyboard` → `pynput`
- `build_std.spec`: hidden imports 中 `keyboard` → `pynput`, `pynput.keyboard`, `pynput.keyboard._win32`
- `main.py`: `_on_config_saved()` 末尾添加 `self._hotkey.start_listening()`
- `main.py`: `_on_exit()` 中 `unregister_all()` → `stop_listening()`

---

### Bug #4: 录制工具栏位置问题 [中等]

**症状**: 录制工具栏出现在屏幕左上角 (0,0)，遮挡其他内容

**根因**: `RecordingToolbar` 创建后没有设置初始窗口位置

**修复** (`src/ui/toolbar.py`):
- 在 `start_countdown()` 中添加定位逻辑：计算屏幕中心 x 坐标，将工具栏移动到屏幕顶部居中位置（距顶部 10px）

---

### Bug #5: 区域选择器无法操作 [严重]

**症状**: 点击"开始录制"后屏幕变灰，鼠标变十字，但无法拖选区域，也无法退出（ESC 键无效，鼠标点击无效）

**根因**: `Qt.Tool` 窗口标志与 `Qt.WA_TranslucentBackground` 在 Windows 11 上组合使用时，窗口被系统视为"点击穿透"覆盖层，无法接收任何输入事件（鼠标和键盘）。这是 PyQt5/Qt5 在 Windows 11 上的已知兼容性问题。

**修复** (`src/ui/area_selector.py`):
1. 移除 `Qt.Tool` 窗口标志，只保留 `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`
2. 添加 `Qt.StrongFocus` 焦点策略
3. `show_fullscreen()` 中添加 `self.raise_()` 提升到最顶层，然后 `activateWindow()` + `setFocus()`
4. 使用 `QDesktopWidget.geometry()` 覆盖所有屏幕
5. 添加右键点击取消选择的安全退出机制（防止用户再次被困住）

---

### Bug #6: 设置对话框点按钮导致退出

**症状**: 打开设置对话框后点击按钮会导致软件退出

**根因**: 与 Bug #1 相同的线程安全问题。pystray 托盘回调在独立线程执行，操作 Qt 组件（包括对话框）会导致未定义行为。修复 Bug #1 后此问题同时解决。

---

### Bug #7: __del__ 方法资源释放问题 [轻微]

**症状**: 程序退出时可能偶发异常日志（不影响功能）

**根因**: `screen_capturer.py` 和 `video_encoder.py` 的 `__del__` 方法直接调用 `close()`，在 Python 垃圾回收时访问的对象可能已被释放。

**修复**:
- `ScreenCapturer.__del__` 和 `VideoEncoder.__del__` 包裹 try-except，静默忽略回收阶段的异常

---

## 受影响文件

| 文件 | 修改内容 |
|------|---------|
| `src/ui/tray_icon.py` | 信号桥线程安全、延迟停止图标 |
| `src/recorder/recorder_manager.py` | 临时文件缓存方案（替代内存缓存），SAVING状态，帧写入/读取循环 |
| `src/recorder/screen_capturer.py` | mss→dxcam，__del__ 异常保护 |
| `src/hotkey/hotkey_manager.py` | keyboard → pynput 完全重写 |
| `src/ui/area_selector.py` | 移除 Qt.Tool、添加焦点策略、右键取消 |
| `src/ui/toolbar.py` | 添加初始屏幕位置 |
| `src/recorder/screen_capturer.py` | __del__ 异常保护 |
| `src/recorder/video_encoder.py` | __del__ 异常保护 |
| `src/main.py` | 快捷键监听重启、退出时停止监听 |
| `build_std.spec` | hidden imports 更新 |
| `requirements.txt` | keyboard → pynput |

## 打包命令

```bash
cd E:\CC_Learning\QuickRec_dev
D:\Work\Software\Python\Scripts\pyinstaller.exe build_std.spec --noconfirm
```

## 测试

- 58/66 单元测试通过（8个 test_config 失败是已有的 mock 路径问题，与本次修改无关）
- PyInstaller 打包成功

---

### Bug #8: 长时间录制视频时长严重偏短 [严重]

**症状**: 录制6分钟，生成的 MP4 视频只有约20秒；60fps 录制5分钟，视频约1分50秒但内容为倍速播放

**根因**: `_record_loop` 使用 `sleep(frame_interval - elapsed)` 控制帧率。当帧捕获+编码耗时超过 frame_interval 时，实际写入帧数远少于 fps * 秒数。由于 MP4 视频时长 = 帧数 / fps，帧数不足直接导致视频时长偏短/倍速。

即使改为绝对时间戳控制，`cv2.VideoWriter(mp4v)` 实时编码仍是瓶颈（~9ms/帧），加上截图（~22ms/帧），合计 ~31ms/帧仅达 ~32fps，60fps 配置下必然帧数不足。

**修复历程**:

1. **方案1**: 切换截图库从 mss 到 dxcam，帧捕获耗时从 ~30ms 降到 ~22ms，加上 `timeBeginPeriod(1)` 提升定时器精度。帧率从 21fps 提升到 ~32fps，但60fps仍不足。

2. **方案3（最终）**: 录制时帧以JPEG压缩写入临时文件（TLV格式：4字节长度+帧数据），停止后后台读取临时文件解码写入VideoWriter。内存占用始终MB级，录制循环仅约7ms/帧（截图5ms+压缩2ms+写盘0.1ms），可稳定60fps。取消了内存阈值回退逻辑和实时编码模式。

   改动文件：
   - `src/recorder/recorder_manager.py`: 完全重写。新增 SAVING 状态；`_record_loop` 改为截图→JPEG压缩→写临时文件；`_encode_loop` 从临时文件读帧→解压→写VideoWriter→删除临时文件；移除 deque 内存缓存、MAX_MEMORY、_realtime_mode
   - `src/main.py`: 新增 `_on_saved` 回调处理编码完成通知，`_on_stop_recording` 处理 SAVING 状态；退出时等待编码完成
   - `src/ui/toolbar.py`: 新增 `show_saving()` 方法显示"保存中..."状态

---

### Bug #9: 取消录制仍生成文件 [中等]

**症状**: 点击工具栏"取消"按钮后，保存目录中仍然出现 MP4 文件

**根因**: `_on_cancel_recording()` 调用的是 `self._recorder.stop()`，与"停止"按钮走同一条路径。`stop()` 关闭 VideoWriter 后文件已经写入磁盘，没有区分正常停止和取消两种场景。

**修复**:
- `RecorderManager.stop()` 新增 `cancel: bool = False` 参数
- 取消录制时 `stop(cancel=True)` 在关闭 encoder 后检查 `_output_path`，如果文件存在则 `os.remove()` 删除
- `_on_cancel_recording()` 改为调用 `self._recorder.stop(cancel=True)`
- 取消录制时显示"录制已取消"通知，而非"录制已保存"

---

### Bug #10: 多次连续录制失败 [中等]

**症状**: 连续录制3次（每次5秒）或停止后立即开始新录制时失败

**根因**: 与 Bug #8 相关——由于帧率控制问题，首次录制的视频内容异常，后续状态管理本身无逻辑错误。`stop()` 方法正确清理了 `_encoder` 和 `_capturer`（设为 None），`_start()` 重新创建新实例。

**修复**: Bug #8 修复后待重测验证。