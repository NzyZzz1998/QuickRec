# 任务：录制工具栏更新 (toolbar.py) — v1.1

**模块**：`src/ui/toolbar.py`（更新）
**说明**：编码完成后显示结果条，支持打开文件夹和自动关闭。基于 v1.0 工具栏扩展。

## 前置依赖
- [x] recorder_manager.py 录制完成回调

## 子任务

### 1. 结果条模式
- [x] 新增信号：`open_folder_requested`、`open_file_requested`
- [x] 新增状态字段：`_result_mode: bool`、`_auto_close_timer: QTimer`、`_output_path: str`
- [x] 实现 `show_result(output_path, file_size_str)` 方法：切换到结果条 UI
- [x] 结果条布局：`✓ 时长 | 已保存 | 📂 打开 | ✕ 关闭`
- [x] "已保存" 按钮：emit `open_file_requested` 信号
- [x] "📂 打开" 按钮：emit `open_folder_requested` 信号
- [x] "✕ 关闭" 按钮：关闭工具栏
- [x] 计时器标签保持显示最终录制时长
- [x] 指示灯从红色改为绿色 ✓

### 2. 自动关闭定时器
- [x] 进入结果条模式时启动 5 秒 QTimer
- [x] 5 秒后自动关闭工具栏
- [x] 用户点击任何按钮时停止定时器
- [x] 关闭前 emit `cancelled` 信号通知 main.py

### 3. 状态切换逻辑
- [x] 录制中状态：原有 UI（暂停/停止/取消按钮）
- [x] 保存中状态：`show_saving()` 已有（v1.0）
- [x] 结果条状态：新增 `show_result()` 模式
- [x] 重置：Hide 后下次录制时从录制状态开始

### 4. 打开文件夹集成
- [x] "已保存" 按钮点击 → `open_file_requested` 信号
- [x] "📂 打开" 按钮点击 → `open_folder_requested` 信号
- [x] main.py 连接信号：`open_file_requested` → `os.startfile(path)`，`open_folder_requested` → `os.startfile(dirname)`

## 验收标准
- [ ] 编码完成后工具栏切换到结果条模式（绿色 ✓ 图标 + 最终时长）
- [ ] "已保存" 按钮可打开视频文件
- [ ] "📂 打开" 按钮可打开文件夹并选中文件
- [ ] "✕ 关闭" 按钮关闭工具栏
- [ ] 5 秒后自动关闭
- [ ] 点击任何按钮后停止自动关闭定时器