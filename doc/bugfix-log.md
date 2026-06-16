# QuickRec Bug 修复日志

> 创建时间: 2026-06-11
> 最后更新: 2026-06-16

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
| `src/recorder/recorder_manager.py` | 临时文件缓存方案、SAVING状态、帧写入/读取循环、画质缩放 |
| `src/recorder/screen_capturer.py` | mss→dxcam、__del__ 异常保护 |
| `src/hotkey/hotkey_manager.py` | 完全重写：字符串标识符键匹配、VK映射、防重复触发 |
| `src/ui/area_selector.py` | 移除 Qt.Tool、添加焦点策略、右键取消 |
| `src/ui/toolbar.py` | 添加初始屏幕位置 |
| `src/ui/settings_dialog.py` | _ShortcutRecorder 可录制快捷键、画质选项改中文+新增native(2K)档位 |
| `src/recorder/video_encoder.py` | __del__ 异常保护 |
| `src/config.py` | 新增 QUALITY_SIZES 画质→分辨率映射表 |
| `src/main.py` | 快捷键监听重启、退出时停止监听、延迟重绑定、编码完成日志 |
| `src/ui/toolbar.py` | 屏幕居中定位、延迟定位修复 |
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

---

### Bug #11: 全局快捷键完全不工作 [严重]

**症状**: 所有快捷键（Ctrl+Shift+R/S/P）均不响应，T5.1-T5.6 全部失败

**根因**: pynput 在修饰键按下时报告的 `KeyCode` 对象与 `KeyCode.from_char()` 创建的对象不一致。当 Ctrl 或 Shift 被按住时，后续普通键的 `KeyCode.char` 可能为 `None` 或控制字符，导致 `_key_to_id` 返回的键标识符与注册解析的快捷键字符串无法匹配。原来的实现直接比较 `KeyCode`/`Key` 对象，在修饰键组合场景下永远匹配失败。

**修复** (`src/hotkey/hotkey_manager.py`):
- 完全重写键匹配机制：将所有 pynput 键对象统一转换为字符串标识符（如 'ctrl', 'shift', 'r'），用 `frozenset` 集合进行精确匹配
- 新增 `_VK_MAP` Windows 虚拟键码映射表，确保 R/S/P 等字母键在修饰键按下时也能正确识别
- `_key_to_id()` 方法：将 pynput Key/KeyCode 统一转为字符串标识符，优先用 `char` 属性，回退到 `vk` 映射
- `_match_hotkey` 改为精确集合匹配：`parsed == self._current_keys`（当前按键集合必须完全等于注册组合）
- 新增 `_triggered` 防重复触发集合：按键按住时仅触发一次，释放后清除

---

### Bug #12: 画质设置不影响视频分辨率 [中等]

**症状**: 无论选择高/中/低画质，视频始终以显示器原始分辨率（2K/1440p）输出

**根因**: `ScreenCapturer` 始终以显示器原始分辨率截图，`VideoEncoder` 直接使用截图尺寸作为帧尺寸，从未根据画质设置进行缩放。`_record_loop` 写入 JPEG 时也是原始分辨率帧。

**修复**:
- `src/config.py`: 新增 `QUALITY_SIZES` 映射表，将画质字符串映射到目标分辨率。新增 "native"（原始分辨率，即2K）档位
- `src/recorder/recorder_manager.py`: 新增 `_get_target_size()` 方法，根据画质配置获取目标分辨率；`_start()` 中计算 `_encode_size`；`_encode_loop()` 在解压后用 `cv2.resize()` 将帧缩放到目标尺寸再编码
- `src/ui/settings_dialog.py`: 画质选项改为中文显示（原生(2K)/高(1080p)/中(720p)/低(480p)），使用 `addItem(text, data)` 存储 config 值

---

### Bug #13: 快捷键设置无法修改 [中等]

**症状**: 设置对话框中快捷键显示为只读 QLabel，用户无法修改快捷键组合

**修复** (`src/ui/settings_dialog.py`):
- 新增 `_ShortcutRecorder(QLabel)` 可点击录制快捷键的控件
- 点击后进入录制模式，显示"按下快捷键..."提示
- 按下修饰键+普通键组合时自动识别并显示（如 `Ctrl+Shift+R`）
- 按 Escape 取消录制，恢复原值
- 失去焦点时自动取消录制
- 保存时读取标签文本作为快捷键值

### Bug #13b: 设置对话框中快捷键录制与全局快捷键冲突 [严重]

**症状**: 打开设置对话框按键录制自定义快捷键时，程序直接退出

**根因**: `pynput` 全局键盘监听器与 `_ShortcutRecorder` 同时捕获按键，pynput 捕获到 Ctrl+Shift+R/S 后触发了全局快捷键回调（开始录制/停止录制），导致非预期行为。此外，全局监听器拦截了按键事件，`_ShortcutRecorder` 的 `keyPressEvent` 可能无法正常工作。

**修复** (`src/main.py`):
- `_show_settings()` 打开设置对话框前先调用 `self._hotkey.stop_listening()` 暂停全局快捷键监听
- 对话框关闭后（无论保存或取消）重新调用 `self._hotkey.start_listening()`
- 保存配置时 `_on_config_saved()` 已包含 `stop_listening()` + `unregister_all()` + 重新注册 + `start_listening()` 的完整流程
- 取消时仅重启监听（配置未变，只需 `start_listening()`）

### Bug #14: QChar 导入错误导致设置对话框崩溃 [严重]

**症状**: 在设置对话框中点击快捷键录制控件后按任意键，程序崩溃闪退

**根因**: `src/ui/settings_dialog.py` 中误导入了 `from PyQt5.QtCore import QChar`。QChar 是 Qt C++ 类，PyQt5 的 Python 绑定中未暴露此类型，导致 `ImportError`。实际代码使用的是 Python 内置的 `chr()` 函数，不需要 QChar 导入。

**修复** (`src/ui/settings_dialog.py`):
- 删除 `from PyQt5.QtCore import QChar` 导入行
- 第96行 `ch = chr(key)` 使用的 `chr()` 是 Python 内置函数，无需任何导入

### Bug #15: 修改快捷键后不生效，再次修改导致闪退 [严重]

**症状**: 在设置对话框中修改快捷键并保存后，新快捷键无响应；再次打开设置对话框修改快捷键时程序崩溃

**根因**: `_on_config_saved` 在 Qt 信号回调中直接操作 pynput：先 `stop_listening()` 停止监听器，然后 `unregister_all()` + 重新注册 + `start_listening()`。此时 `_ShortcutRecorder` 仍然持有 `grabKeyboard()`，pynput 的新 Listener 启动与 Qt 键盘抓取冲突导致崩溃。此外，在对话框生命周期内重启 pynput 监听器会与 `_ShortcutRecorder` 的按键捕获产生竞争。

**修复** (`src/main.py`):
- 新增 `_config_saved_pending` 标志位
- `_on_config_saved_pend()` 只设置标志，不直接操作 pynput
- `_show_settings()` 在对话框关闭后统一处理：如果配置已保存，执行 `unregister_all()` + `_setup_hotkeys()` 重绑定；无论保存或取消，最后统一调用 `start_listening()` 重启监听
- 这确保 pynput 操作始终在对话框关闭（键盘抓取释放）后执行，避免冲突

### Bug #16: 录制工具栏位置偏左未居中 [轻微]

**症状**: 录制工具栏出现在屏幕顶部但整体偏左，没有水平居中

**根因**: `start_countdown()` 中使用 `self.width()` 计算居中位置，但此时 Qt 布局尚未完成计算，`self.width()` 返回的是初始/不正确的宽度值（可能为0或偏小），导致 `screen_center_x - width//2` 计算结果偏左。

**修复** (`src/ui/toolbar.py`):
- 将定位逻辑提取为 `center_on_screen()` 方法
- 使用 `QTimer.singleShot(0, self.center_on_screen)` 延迟执行定位，确保在 Qt 事件循环完成布局计算后再获取 `self.width()`，返回正确的窗口宽度

### Bug #17: 点击停止后工具栏显示"保存中"但一直不消失 [严重]

**症状**: T7.5 测试未通过 — 点击工具栏"停止"按钮后，工具栏显示"保存中..."状态，但编码完成后工具栏不会自动消失，通知也不会弹出来

**根因**: `_on_saved` 回调在编码线程（Python threading.Thread）中被调用，原实现使用 `QTimer.singleShot(0, lambda: self._handle_saved(output_path))` 将调用转发到主线程。但 `QTimer.singleShot` 从非 Qt 线程（原生 Python 线程）调用时，PyQt5 无法可靠地将定时器事件投递到主线程事件循环，导致回调永远不会在主线程执行，工具栏一直停留在"保存中..."状态。

**修复** (`src/main.py`):
- 新增 `_SavedBridge(QObject)` 信号桥类，包含 `saved = pyqtSignal(str)` 信号
- `_on_saved` 回调改为 `self._saved_bridge.saved.emit(output_path)`，通过 PyQt5 信号槽机制安全转发到主线程
- `_SavedBridge.saved` 信号连接到 `_handle_saved` 槽函数
- PyQt5 的 `pyqtSignal.emit()` 从非 Qt 线程调用时自动使用 `Qt.QueuedConnection`，确保信号在主线程事件循环中被正确处理
- 与 Bug #1 (pystray 线程安全) 和 Bug #15 (pynput 线程冲突) 采用相同的设计模式：信号桥转发

### Bug #18: 录制期间 GUI 冻结，快捷键和托盘菜单均不响应 [严重]

**症状**: 使用快捷键开始录制后，所有操作（快捷键、托盘右键菜单、停止按钮）均无响应。按快捷键开始录制后录制工具栏可能不出现。录制中退出程序导致临时文件被占用、视频未生成。

**根因**: 三个问题叠加：
1. **忙等待循环占满 CPU 和 GIL**：`_record_loop` 中 `while time.time() < next_time: pass` 是忙等待，每帧约33ms中几乎全程空转占满一个 CPU 核心，Python GIL 被录制线程持续持有，主线程（Qt GUI + pynput）无法获得 GIL 执行事件处理
2. **dxcam 在主线程初始化**：`ScreenCapturer.__init__` 中调用 `dxcam.create()` 和 `camera.start()`，这是较慢的 DirectX 初始化操作，在主线程中执行会短暂冻结 GUI
3. **`stop()` 中 `join(timeout=5.0)` 阻塞主线程**：停止录制时主线程冻结最多5秒

**修复** (`src/recorder/recorder_manager.py`):
- 移除忙等待循环：将 `while time.time() < next_time: pass` 替换为 `time.sleep(max(wait - 0.001, 0.001))`，释放 GIL 让主线程可以运行
- `stop()` 改为非阻塞：只设置停止事件和 STOPPING 状态，立即返回；`join`、文件清理、编码启动逻辑移到 `_stop_and_encode()` 后台线程
- 新增 STOPPING 状态判断：防止重复调用 stop
- 新增 `wait_until_idle(timeout)` 方法：用于退出时等待所有后台操作完成

**修复** (`src/recorder/screen_capturer.py`):
- `ScreenCapturer.__init__` 不再创建和启动 dxcam，改为延迟初始化
- 新增 `start()` 方法，在录制线程中调用 `dxcam.create()` 和 `camera.start()`
- `_record_loop` 开头调用 `self._capturer.start()` 在录制线程中初始化 dxcam

**修复** (`src/main.py`):
- `_on_stop_recording`: 停止后直接显示"保存中..."，不依赖阻塞返回值
- `_on_cancel_recording`: 增加 IDLE 和 SAVING 状态判断
- `_on_exit`: 使用 `wait_until_idle(timeout=60)` 确保编码完成后退出

### Bug #19: 快捷键触发录制后 GUI 冻结、工具栏不出现 [严重]

**症状**: 使用快捷键 Ctrl+Shift+R 开始录制后，录制工具栏不出现，程序完全无响应只能强制退出。但通过托盘菜单开始录制一切正常。

**根因**: pynput 的键盘监听回调在其独立线程中执行。QTimer.singleShot 从非 Qt 线程调用不可靠（Bug #17）的同一类问题 —— pynput 回调直接操作 Qt UI 组件（创建 toolbar、调用 show/close 等）违反了 Qt 的线程安全规则，导致 GUI 事件循环死锁。与 Bug #1（pystray 线程安全）和 Bug #17（编码线程回调）属于同一类问题。

**修复** (`src/main.py`):
- 新增 `_HotkeyBridge(QObject)` 信号桥类，包含 `start_requested`、`stop_requested`、`pause_requested` 三个信号
- 快捷键回调不再直接调用 `_on_start_recording` 等方法，改为 emit 信号
- 信号通过 `pyqtSignal` 的 QueuedConnection 机制安全转发到 Qt 主线程执行
- 与 `_SavedBridge`（Bug #17）和 `_SignalBridge`（Bug #1）采用相同的设计模式

---

## v1.1 Bug 修复

### Bug #20: 点击"区域录制"菜单或快捷键无响应 [严重]

**症状**: 右键托盘点击"区域录制"或按 Ctrl+Shift+A 快捷键，没有任何反应，不出区域选择器遮罩

**根因**: `main.py` 中 `_on_start_region()` 方法将 `AreaSelector` 创建为局部变量 `selector`，方法返回后 Python 垃圾回收器立即回收该对象，导致 QWidget 被销毁，遮罩窗口无法显示

**修复** (`src/main.py`):
- 将 `selector` 保存为实例属性 `self._area_selector`，防止垃圾回收
- 在 `_on_region_selected` 和 `_on_selection_cancelled` 中将 `self._area_selector = None` 清理引用

### Bug #21: _get_ffmpeg_path 开发环境下路径计算错误 [中等]

**症状**: 开发环境下 FFmpeg 路径搜索失败，`_get_ffmpeg_path()` 返回空字符串，音频混合功能不可用

**根因**: `_get_ffmpeg_path()` 中开发环境路径使用 `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`，但 `__file__` 位于 `src/recorder/recorder_manager.py`，两层 dirname 只到 `src/` 目录，而非项目根目录。因此搜索路径为 `src/ffmpeg/ffmpeg.exe` 而非项目根目录的 `ffmpeg/ffmpeg.exe`

**修复** (`src/recorder/recorder_manager.py`):
- 开发环境路径从两层 `os.path.dirname` 改为三层，确保到达项目根目录
- 修复后路径：`E:\CC_Learning\QuickRec_dev\ffmpeg\ffmpeg.exe`

### Bug #22: 结果条关闭触发"录制已取消"通知 [中等]

**症状**: 录制完成后的结果条（"✓ 已保存 | 📂 打开 | ✕ 关闭"）自动关闭或点击"✕ 关闭"时，额外弹出"录制已取消"通知

**根因**: 结果条的 `_on_close_result()` 和 `_on_auto_close()` 方法 emit `cancelled` 信号，而 `cancelled` 连接到 `_on_cancel_recording()`，其中调用 `self._tray.show_notification("录制已取消")` 和 `self._recorder.stop(cancel=True)`。结果条关闭只是正常结束展示，不应触发取消逻辑。

**修复** (`src/ui/toolbar.py`):
- `_on_close_result()` 改为直接 `self.close()`，不再 emit `cancelled`
- `_on_auto_close()` 改为直接 `self.close()`，不再 emit `cancelled`
- 保持 `_on_cancel()`（真正取消录制时）仍然 emit `cancelled`

### Bug #23: 区域录制画质缩放导致视频变形 [中等]

**症状**: 区域录制时画质设为"高(1080p)"，选区的视频比例与实际选区比例不一致，画面被拉伸变形

**根因**: `_get_target_size()` 对全屏和区域录制返回相同的目标分辨率（如 1920x1080），导致非 16:9 的选区被强制缩放到 16:9。例如选区 800x600(4:3) 被拉伸到 1920x1080(16:9)。

**修复** (`src/recorder/recorder_manager.py`):
- `_get_target_size()` 方法增加区域录制判断
- 区域录制时根据选区宽高比计算目标尺寸，保持宽高比不变
- 以目标分辨率做上限，按比例缩放，确保偶数宽高（编码要求）
- 例：选区 800x600(4:3) + 画质 high → 1440x1080(4:3) 而非 1920x1080(16:9)

**受影响文件**:
- `src/ui/toolbar.py` — 结果条关闭方式修复
- `src/recorder/recorder_manager.py` — 区域录制画质缩放保持宽高比
- `src/main.py` — AreaSelector 保存为实例属性防止 GC

### Bug #24: 系统声音录制停止时程序崩溃 (0xC0000005) [严重]

**症状**: 音频源设为"系统声音"或"两者都有"，录制停止后程序崩溃，退出码 0xC0000005（访问冲突）。日志显示系统声音初始化成功（48000Hz, 2ch），但停止录制后进程直接崩溃

**根因**: 两个问题叠加：

1. **PyAudio 实例跨实例索引不匹配**：`_find_wasapi_loopback()` 创建临时 `pyaudiowpatch.PyAudio()` 实例发现 loopback 设备索引，然后 `pa.terminate()` 销毁实例。`_start_system()` 创建新的 `PyAudio()` 实例，用旧实例的设备索引 `open()` 流——不同实例间设备索引不通用，导致 C 层访问无效内存，引发 0xC0000005

2. **资源释放顺序错误**：`stop()` 方法先关闭音频流（`stop_stream()`/`close()`），再关闭 WAV 文件。如果 `_capture_loop` 线程正在 `writeframes()` 时流被关闭，WAV 文件处于不一致状态。此外，`_capture_loop` 中 `stream.read()` 在流关闭后抛出未捕获的异常导致线程崩溃

**修复** (`src/recorder/audio_capturer.py`):

1. `_find_wasapi_loopback()` 改为接受 `pa` 参数，使用同一 PyAudio 实例发现设备和打开流，避免跨实例索引问题。同时改进设备查找逻辑：先查找默认输出设备对应的 loopback，再 fallback 到任意 loopback 设备

2. `_start_system()` 不再单独创建临时 PyAudio 实例，而是先创建 `self._pa_wp = pawp.PyAudio()`，然后调用 `_find_wasapi_loopback(self._pa_wp)` 在同一实例上查找设备

3. `stop()` 改变资源释放顺序：先 `_is_recording.clear()` + 等待线程结束 → 关闭 WAV 文件（确保数据刷盘） → 关闭音频流 → 终止 PyAudio。WAV 在流之前关闭，避免线程写入已关闭流的数据

4. `_capture_loop()` 增加错误处理：捕获 `OSError`（流已关闭）时直接跳出循环；连续读取错误超过阈值时停止捕获；不再因单次错误崩溃

**后续发现**: 上述修复后，`pyaudiowpatch` 的 WASAPI loopback `stream.read()` 仍然无限阻塞（进程直接挂起，无异常）。`get_default_wasapi_loopback()` 发现设备正常，`pa.open()` 打开流正常，但 `read()` 调用后永不返回。最终**将 pyaudiowpatch 替换为 soundcard 库**。

**最终修复** (`src/recorder/audio_capturer.py`):
- 系统声音捕获从 pyaudiowpatch 迁移到 soundcard（WASAPI loopback via MediaFoundation）
- `soundcard` 的 `rec.record(numframes=N)` 非阻塞、准确返回 N 帧 float32 numpy 数组
- 支持手动管理 recorder 生命周期（`__enter__`/`__exit__`），适配长时录制线程
- 麦克风仍使用 pyaudio（代码不变）
- 更新 `requirements.txt` 添加 soundcard，`build_std.spec` 添加 hiddenimports
- 测试验证：系统声音 3 秒录制 → WAV 3.0s；BOTH 模式 3 秒 → 双文件各 3.0s

---

### Bug #25: 结果条"📂 打开"未选中文件 [中等]

**症状**: T5.4 — 点击结果条"📂 打开"按钮，文件管理器打开了正确的目录，但没有选中（高亮）刚录制的视频文件。

**根因**: `main.py` 的 `_on_open_folder()` 使用 `os.startfile(os.path.dirname(path))`，只能打开目录，无法定位到具体文件。tray_icon.py 的 Toast 通知里已用 `explorer.exe /select,` 正确实现，但结果条按钮回调未复用。

**修复** (`src/main.py`):
- `_on_open_folder()` 改用 `subprocess.run(["explorer.exe", f"/select,{path}"])` 打开文件夹并选中文件
- 先 `os.path.normpath()` 规范化路径（explorer 需要 Windows 反斜杠）
- 文件不存在时降级为 `os.startfile(dirname)` 仅打开目录
- 补充 `import subprocess`

---

### Bug #26: 结果条点击按钮后不再自动关闭 [中等]

**症状**: T5.6 — 结果条本应在录制停止后 5 秒自动关闭。但只要点过任意按钮（如"已保存"/"📂 打开"），自动关闭定时器被永久停掉，结果条会一直停留，需手动关闭。

**根因**: `toolbar.py` 的 `_on_open_file()` / `_on_open_folder()` 在触发动作前调用 `self._auto_close_timer.stop()`，意图是"用户在操作时不要关闭"，但只 stop 不重启，导致定时器再也不触发。

**修复** (`src/ui/toolbar.py`):
- 语义改为"无操作 5 秒后关闭"：任何交互都**重置** 5 秒倒计时，而非停掉
- 新增 `_restart_auto_close()`：result 模式下 `_auto_close_timer.start(5000)`
- `_on_open_file` / `_on_open_folder` 末尾调用 `_restart_auto_close()` 而非 `stop()`
- `mousePressEvent`（拖拽）在 result 模式下也重置倒计时
- "✕ 关闭"按钮仍直接 `close()`，行为不变

---

### Bug #27: Toast 通知"打开文件夹"按钮缺失/无效，且 winotify 始终降级 [中等]

**症状**: T6.3/T6.4 — Toast 通知里应有"打开文件夹"按钮，但按钮从未出现，点击也无反应。实际看到的通知样式是 pystray 纯文本通知，并非 winotify Toast。

**根因**: 三个问题叠加：
1. **构造参数名错误**：`Notification(..., body=msg)`，但 winotify 1.1.0 的构造签名是 `Notification(app_id, title, msg='', ...)`，参数名是 `msg` 不是 `body`。`body=` 直接抛 `TypeError`，被 `except` 捕获后**每次都降级到 pystray**——所以 T6.1/T6.2 看到的"通知"其实是降级版，winotify 从未成功执行。
2. **add_actions 传参错误**：`add_actions([label, launch])` 传了一个 list，但签名是 `add_actions(label: str, launch='')` 两个独立参数。即便构造成功，按钮文字也会变成 list 字符串、launch 为空。
3. **launch 非合法 URI**：winotify 的 action 固定用 `activationType="protocol"`，launch 必须是 URI。`explorer.exe /select,path` 是命令行而非协议 URI，点击不会打开。

**修复** (`src/ui/tray_icon.py`):
- `body=msg` → `msg=msg`，winotify 路径才能真正执行
- `add_actions(label=action_label, launch=launch_uri)` 正确传两个参数
- launch 改用 `pathlib.Path(folder).as_uri()` 生成 `file:///` 目录 URI（自动处理空格/反斜杠），点击用资源管理器打开视频所在目录
- 受协议激活限制，Toast 按钮只能"打开目录"无法"选中文件"（这正是 T6.4 预期）；选中文件的能力由结果条"📂 打开"按钮承担（见 [Bug #25]）
- 验证：toast 正确生成 `<action activationType="protocol" content="打开文件夹" arguments="file:///..." />`

---

### Bug #28: 打包后找不到 FFmpeg（datas 落入 _internal 与查找路径不符）[严重]

**症状**: 开发环境音频混合正常，但打包后 `_get_ffmpeg_path()` 返回空，系统声音/麦克风录制无法混合音频。

**根因**: 两个配合问题：
1. `build_std.spec` 的 `datas=[]` 为空，ffmpeg.exe 根本没打进包。
2. 加入 `datas=[('ffmpeg/ffmpeg.exe', 'ffmpeg')]` 后，PyInstaller 6.x onedir 模式把数据文件放到 `dist/QuickRec/_internal/ffmpeg/ffmpeg.exe`，而 `_get_ffmpeg_path()` 只在 `sys.executable` 同级目录（`dist/QuickRec/ffmpeg/`）查找——路径不符，仍找不到。

**修复**:
- `build_std.spec`：`datas` 添加 `('ffmpeg/ffmpeg.exe', 'ffmpeg')`；hiddenimports 补 `pyaudio`（麦克风捕获，之前遗漏）
- `recorder_manager.py` `_get_ffmpeg_path()`：frozen 分支优先用 `sys._MEIPASS`（onedir 下指向 `_internal`）拼接 `ffmpeg/ffmpeg.exe`，再 fallback 到 `sys.executable` 同级目录
- 验证：重新打包后 `_internal/ffmpeg/ffmpeg.exe` 就位，exe 启动无崩溃

---

## v1.2 Bug 修复

### Bug #29: 窗口选择器列出过多系统窗口且缺少正常窗口 [中等]

**症状**: T2.2 — 窗口选择器列表显示大量系统浮动窗口，同时 Chrome、Edge、Excel 等正常窗口被过滤掉

**根因**: 三个问题叠加：

1. `_SYSTEM_WINDOW_CLASSES` 黑名单仅包含 9 种系统窗口类名，大量低层级控件和后台窗口未被过滤
2. `WS_EX_TOOLWINDOW` 过滤将无任务栏图标的浮动工具窗口过滤掉（正确），但 `ApplicationFrameWindow` 和 `Windows.UI.Core.CoreWindow` 被加入黑名单导致 UWP 应用窗口（如 Windows 设置）也被过滤
3. 最小化窗口（Chrome/Edge 最小化到任务栏后 `WS_MINIMIZE` 标志置位）被直接过滤掉，用户无法选择最小化但想录制的窗口

**修复** (`src/ui/window_selector.py`):
- 大幅扩充 `_SYSTEM_WINDOW_CLASSES` 黑名单：新增系统控件类名（`Button`, `ComboBox`, `Edit`, `Static` 等）和后台窗口（`SearchUI`, `TaskManagerWindow` 等）
- 从黑名单中移除 `ApplicationFrameWindow` 和 `Windows.UI.Core.CoreWindow`——有标题的 UWP 窗口用户可能需要录制
- 最小化窗口不再过滤，改为在列表中显示"(最小化)"标注
- 选中最小化窗口时，`_on_window_selected()` 会调用 `ShowWindow(SW_RESTORE)` 恢复窗口

### Bug #30: 选择窗口后程序崩溃 (0xC0000409) [严重]

**症状**: T2.6 — 在窗口选择器中选中一个窗口后程序直接崩溃，退出码 0xC0000409 (STATUS_STACK_BUFFER_OVERRUN)

**根因**: 窗口枚举回调 `_enum_callback` 中使用 `ctypes.wintypes.RECT()` 获取窗口位置，但 `ctypes.wintypes` 是子模块，`import ctypes` 不会自动加载它。在 `WNDENUMPROC` 回调中第一次访问 `ctypes.wintypes.RECT()` 时触发 `AttributeError: module 'ctypes' has no attribute 'wintypes'`。ctypes 回调中抛出的异常会导致进程直接终止（0xC0000409），而非被 Python 异常机制捕获。

此外还有以下次要问题加强崩溃风险：

1. **dxcam 每帧重建实例**：`_record_loop` 中窗口模式下每帧调用 `ScreenCapturer.update_region()`，每次都执行 dxcam 完整重建流程
2. **camera 释放后状态不一致**：`update_region()` 失败后 `_started` 仍为 True

**修复** (`src/recorder/screen_capturer.py`):
- 新增 `_last_dxcam_region` 缓存字段：`update_region()` 先比较新 region 与缓存值，相同则跳过重建，避免静止窗口下每帧创建/销毁 dxcam
- `start()` 方法初始化 `_last_dxcam_region = self._dxcam_region`
- `update_region()` 重建失败时将 `_camera = None` 和 `_started = False`，防止后续 `capture_frame()` 在坏状态上调用
- 重建失败时先尝试 `release()` 残留 camera 实例

**修复** (`src/recorder/recorder_manager.py`):
- `_record_loop` 窗口位置更新从每帧改为 200ms 间隔：新增 `last_window_update` 时间戳变量，仅当 `now - last_window_update >= 0.2` 时才调用 `_get_window_rect` 和 `update_region`
- `capture_frame()` 返回 None 时检查 `_started` 状态：若 `_started=False`（camera 已失效）则 `break` 终止录制循环，避免无限 `continue` 空转

### Bug #31: 选中窗口后目标窗口不自动前置 [中等]

**症状**: 用户选择窗口录制后，目标窗口停留在后台，录制区域实际为背景内容而非用户期望的窗口画面

**根因**: `_on_window_selected()` 中只创建了 `WindowHighlighter` 高亮边框，没有将目标窗口提到前台。Windows 多窗口环境下，后台窗口的内容可能被遮挡，dxcam 截取的是屏幕像素（非窗口渲染），导致录制内容非预期。

**修复** (`src/main.py`):
- `_on_window_selected()` 中在创建高亮边框前，调用 `user32.ShowWindow(hwnd, 9)` (SW_RESTORE) 恢复最小化窗口，然后 `user32.SetForegroundWindow(hwnd)` 将目标窗口提到前台
- 确保录制开始时目标窗口可见且在最前面

### Bug #32: ctypes.wintypes 子模块未显式导入导致崩溃 [严重]

**症状**: 选择窗口后程序立即崩溃，退出码 0xC0000409 (STATUS_STACK_BUFFER_OVERRUN)

**根因**: `ctypes.wintypes` 是 `ctypes` 的子模块，`import ctypes` 不会自动加载它。三处代码使用了 `ctypes.wintypes.RECT()` 但未显式导入：

1. `src/ui/window_selector.py` — EnumWindows 回调中使用
2. `src/ui/window_highlighter.py` — `_update_position()` 中使用
3. `src/recorder/recorder_manager.py` — `_get_window_rect()` 中使用

当这些代码首次访问 `ctypes.wintypes.RECT()` 时，Python 尝试属性查找触发 `AttributeError`。在 ctypes 的 WNDENUMPROC 回调中抛出异常会导致进程直接终止（0xC0000409），而非被 Python 异常机制捕获。

**修复**: 在三个文件顶部添加 `import ctypes.wintypes`，确保子模块在使用前已加载。

### Bug #33: Qt 属性名拼写错误导致 WindowHighlighter/ClickHighlighter 崩溃 [严重]

**症状**: 选择窗口后创建 `WindowHighlighter` 时崩溃，`AttributeError: type object 'Qt' has no attribute 'WA_TransparentForMouseInput'`

**根因**: PyQt5 中鼠标穿透属性名是 `Qt.WA_TransparentForMouseEvents`（复数 Events），代码中误写为 `Qt.WA_TransparentForMouseInput`（不存在）。

**修复** (`src/ui/window_highlighter.py`, `src/ui/click_highlighter.py`):
- `Qt.WA_TransparentForMouseInput` → `Qt.WA_TransparentForMouseEvents`

### Bug #34: QRect 方法缺少括号导致窗口录制 region 参数错误 [严重]

**症状**: `start_window()` 调用时 `TypeError: unsupported operand type(s) for +: 'builtin_function_or_method' and 'int'`

**根因**: `QRect` 的 `left()` 和 `top()` 是方法而非属性，`rect.left` 返回方法引用而非整数值。两处代码使用了 `rect.left` / `rect.top` 而非 `rect.left()` / `rect.top()`：

1. `start_window()` 中构建 region 参数
2. `_record_loop()` 中窗口位置更新调用 `update_region`

**修复** (`src/recorder/recorder_manager.py`):
- `start_window()`: `rect.left` → `rect.left()`，`rect.top` → `rect.top()`
- `_record_loop()`: 同上

### Bug #38: 最大化/最小化窗口录制视频损坏 [严重]

**症状**: T2.12 — 选择最大化窗口录制时生成无法播放的 MP4 文件（错误码 0xC00D36C4）；选择最小化窗口恢复后录制的视频同样损坏

**根因**: `_get_window_rect` 使用 `GetWindowRect` 获取窗口位置，该 API 返回包含边框阴影的坐标。最大化窗口返回 `(-8, -8, 2568, 1400)`，导致：

1. **负坐标**: dxcam 的 region 参数不支持负坐标，传入后行为未定义
2. **超出屏幕尺寸**: 2576×1408 超出实际屏幕分辨率 2560×1440，dxcam 抛出 `ValueError: Invalid Region`

**修复** (`src/recorder/recorder_manager.py`):
- `_get_window_rect()` 改用 `GetClientRect` + `ClientToScreen`，获取纯客户区屏幕坐标，不含边框阴影
- 最大化窗口客户区为 `(0, 0, 2560, 1392)`，完美对应屏幕范围，无需额外裁剪
- `start_window()` 和 `_record_loop()` 删除冗余的屏幕范围裁剪逻辑

### Bug #39: 非倒计时模式录制不显示工具栏 [严重]

**症状**: T2.9 — 未开启录制倒计时时，窗口录制、全屏录制、区域录制的工具栏均不出现

**根因**: 三种录制模式的非倒计时分支直接调用 `_do_start_xxx()` 但没有先调用 `_show_toolbar()` 创建工具栏。`_do_start_xxx()` 中 `self._toolbar` 为 None，导致录制指示灯和计时器均不显示。

**修复** (`src/main.py`):
- 三种录制模式（全屏/区域/窗口）的非倒计时分支都加上 `self._show_toolbar()` 调用
- 保持与倒计时模式一致的工具栏创建时机

### Bug #37: 窗口丢失/最小化导致崩溃 (0xC0000409) [严重]

**症状**: T2.16/T2.17 — 关闭或最小化录制目标窗口后程序崩溃（退出码 0xC0000409），无任何提示弹窗。非最大化窗口最小化后有提示但不置顶。

**根因**：多层问题叠加：

1. **dxcam 未释放导致崩溃**：录制循环 break 后 `self._capturer`（dxcam 实例）仍在运行。dxcam 内部的 DirectX GPU 线程未释放，后续任何操作（包括 Qt 事件循环处理）触发访问已失效的 GPU 资源，导致栈缓冲区溢出（0xC0000409）。
2. **QMessageBox 在托盘应用中不显示**：系统托盘应用没有可见的父窗口，`QMessageBox` 弹窗可能被系统隐藏或遮挡，用户看不到任何提示。
3. **录制循环 break 后录制器状态不一致**：原来的 break 只退出循环，不设 PAUSED 状态、不刷盘、不保存帧数。

**修复** (`src/recorder/recorder_manager.py`):
- 录制循环 break 后立即释放 dxcam：`self._capturer.close(); self._capturer = None`
- 窗口丢失（关闭/最小化）后，在 break 之前：
  1. 保存 `frames_written` 到 `_total_frames`
  2. 刷盘 `fh.flush()`
  3. 设置 `_state = PAUSED` 和 `_pause_start`
  4. `clear()` `_resume_event` 使暂停条件生效
  5. 区分关闭 vs 最小化（`IsWindow` + `IsIconic`），emit 对应 reason
- `_get_window_rect()` 增加 `IsWindowVisible` 和 `IsIconic` 检查，窗口不可见或最小化时返回 None

**修复** (`src/main.py`):
- `_on_window_lost()` 改用托盘通知（`show_notification`）替代 `QMessageBox` 模态对话框：
  - **窗口关闭**：自动停止录制并保存
  - **窗口最小化**：暂停录制，托盘通知用户恢复窗口后可继续
- 弹窗前先 `hide_highlight()` 停止 WindowHighlighter 定时器，避免 Win32 API 访问已关闭的 hwnd
- 整体 try-except 包裹，防止异常崩溃

### Bug #41: 窗口录制功能延期 [功能决策]

**症状**: 窗口录制功能（T2.x）存在多种难以稳定修复的问题：
- 窗口关闭/最小化后无法可靠弹窗提示用户（QMessageBox 在托盘应用中不显示）
- 最大化窗口 GetWindowRect 返回含边框阴影的负坐标，导致 dxcam 崩溃
- 窗口位置跟随延迟大，录制内容容易包含其他窗口
- dxcam 资源释放的跨线程问题

**决策**: 将窗口录制功能整体延期（注释保留代码，不删除），v1.2 版本仅保留全屏录制和区域录制。

**修改** (多个文件):
- `src/main.py`: 注释掉 _WindowBridge/_WindowLostBridge 信号桥、窗口选择器/高亮器导入和实例、所有窗口录制方法、信号连接、快捷键注册、窗口高亮清理
- `src/recorder/recorder_manager.py`: 注释掉 RecordMode.WINDOW、start_window()、_get_window_rect()、_get_window_title()、_WindowLostBridge、窗口相关字段、录制循环中的窗口跟踪逻辑
- `src/ui/tray_icon.py`: 注释掉"🖥 窗口录制"菜单项（此前已完成）
- `src/ui/settings_dialog.py`: 注释掉窗口录制快捷键设置行
- `tests/test_v1_2.py`: 注释掉 TestRecordModeWindow、TestRecorderManagerWindow、TestWindowHighlighter 测试类
- 单元测试从 32 项降至 26 项，全部通过

### Bug #42: 停止录制后鼠标点击高亮仍在显示 [T5.5]

**症状**: 录制停止后，编码临时文件过程中鼠标点击高亮动画依旧存在，视频保存完成后动画才消失

**根因**: `_on_stop_recording()` 中未调用 `_click_highlighter.stop()`，高亮停止操作仅在 `_handle_saved()`（编码完成回调）和 `_on_cancel_recording()` 中执行。录制停止后进入 SAVING 状态期间，pynput 鼠标监听器仍在运行。

**修复** (`src/main.py`):
- `_on_stop_recording()` 中立即调用 `self._click_highlighter.stop()`
- `_handle_saved()` 中的 `self._click_highlighter.stop()` 保留作为安全兜底

### Bug #43: 倒计时显示布局不佳 [T6.2]

**症状**: 倒计时数字（36px 字体）在 40px 高度的工具栏中显示被裁切，布局不美观

**根因**: 工具栏固定高度 40px，无法容纳 36px 的大号字体

**修复** (`src/ui/toolbar.py`):
- 工具栏高度从 40px 增加到 56px
- 倒计时数字字体从 36px 调整为 28px，在 56px 高度中居中显示更协调

### Bug #44: QSpinBox 秒数显示为符号而非数字 [T6.10/T6.11]

**症状**: 设置对话框中倒计时秒数 QSpinBox 显示乱码符号，无法准确选择秒数

**根因**: Qt Fusion 样式在 Windows 11 某些 DPI 缩放下，QSpinBox 内部 QLineEdit 渲染异常，数字部分被替换为乱码符号（如 `<<秒` 而非 `1 秒`），属于 Qt 渲染 bug

**修复** (`src/ui/settings_dialog.py`):
- 将 QSpinBox 替换为 QComboBox（下拉选择秒数），彻底避免 QSpinBox 的渲染 bug
- 选项：1 秒 ~ 10 秒，默认 3 秒（index=2）
- 加载：`currentIndex = countdown_seconds - 1`
- 保存：`countdown_seconds = currentIndex + 1`

**修复** (`src/main.py`):
- 应用启动时设置 `QApplication.setStyle("Fusion")`，使用跨平台一致的 Fusion 样式

### Bug #46: 倒计时期间 ESC 键无效 [T6.7]

**症状**: 倒计时显示期间按 ESC 键无法取消倒计时

**根因**: 工具栏使用 `Qt.Tool` flag，该类型的窗口在 Windows 上不接收键盘焦点，ESC 按键事件无法到达 `keyPressEvent`

**修复** (`src/ui/toolbar.py`):
- 倒计时模式下去掉 `Qt.Tool` flag（仅用 `FramelessWindowHint | WindowStaysOnTopHint`），使窗口可获取键盘焦点
- 倒计时结束后恢复 `Qt.Tool` flag（不出现在任务栏）
- `_show_countdown_ui()` 和 `_countdown_tick()` 中调用 `self.setFocus()` 确保焦点

### Bug #47: 倒计时期间 Ctrl+Shift+R 重新开始倒计时而非取消 [T6.8]

**症状**: 倒计时期间按 Ctrl+Shift+R（开始录制快捷键），又触发了新的倒计时流程

**根因**: 倒计时期间 `recorder.get_state()` 仍为 `IDLE`（录制尚未开始），所以快捷键的 `start_requested` 信号走到 `_on_start_fullscreen()`，重新创建工具栏开始倒计时

**修复** (`src/main.py`):
- `_on_start_fullscreen()` 中增加倒计时检查：如果正在倒计时，取消倒计时、隐藏工具栏、return
- `_on_start_region()` 中已有的倒计时取消逻辑补充 `self._hide_toolbar()` 和 `return`
- 所有取消倒计时路径均调用 `self._hotkey.set_esc_callback(None)` 清除全局 ESC 回调

### Bug #48: 倒计时期间全局 ESC 键无效 [T6.7 二次修复]

**症状**: 去掉 Qt.Tool flag 后 ESC 仅在工具栏有焦点时有效，其他窗口抢走焦点后 ESC 失效

**根因**: Qt 窗口键盘焦点不可靠，用户倒计时期间可能在操作其他窗口

**修复** (`src/hotkey/hotkey_manager.py`):
- 新增 `set_esc_callback(callback)` 方法，在 pynput 全局键盘监听中检测 ESC 单键
- `_on_press()` 中检测 `key_id == 'esc'` 时调用回调

**修复** (`src/main.py`):
- 倒计时开始时设置 `self._hotkey.set_esc_callback(self._on_countdown_esc)`
- 新增 `_on_countdown_esc()` 方法：取消倒计时、隐藏工具栏、清除 ESC 回调
- 倒计时结束（`_do_start_fullscreen`/`_do_start_region`）时清除 ESC 回调
- Ctrl+Shift+R 取消倒计时路径也清除 ESC 回调

### Bug #49: 托盘"打开保存文件夹"路径错误

**症状**: 右键托盘图标点击"打开保存文件夹"，打开的路径与设置中的保存路径不一致

**根因**: 配置中 `save_path` 使用正斜杠（如 `E:/QRtest`），`explorer.exe` 对正斜杠路径处理异常

**修复** (`src/ui/tray_icon.py`):
- `_on_open_folder()` 中用 `os.path.normpath()` 统一路径分隔符为反斜杠后再传给 `explorer.exe`