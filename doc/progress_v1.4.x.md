# QuickRec v1.4.x 诊断日志 / 错误导出能力进度看板

> 版本: v1.4.x  
> 创建时间: 2026-07-09  
> 状态: 通过 / 可发布  
> PRD: [PRD-diagnostic-export-v1.4.x.md](PRD-diagnostic-export-v1.4.x.md)  
> Dev Plan: [dev_plan_v1.4.x.md](dev_plan_v1.4.x.md)  

---

## 1. 总体状态

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| D0 文档与分支准备 | ✅ 完成 | 已在 Full `test` 派生分支进入实现 |
| D1 诊断基础设施 | ✅ 完成 | 配置、诊断模块、文件日志已完成 |
| D2 录制上下文接入 | ✅ 完成 | 已暴露录制、FFmpeg、音频、窗口、保存失败上下文 |
| D3 UI 入口接入 | ✅ 完成 | 设置页、托盘菜单、主入口回调已完成 |
| D4 测试与质量门槛 | ✅ 完成 | pytest、compileall、ruff、mypy、硬件 smoke 已通过 |
| D5 打包与发布前验证 | ✅ 完成 | 最终验收路径已统一为 `E:\codex\QuickRec-v14x-diagnostics`；打包产物 GUI 手动验收、录制回归、音频回归和 FFmpeg 缺失异常诊断均已通过 |

---

## 2. D0 文档与分支准备

- [x] 确认用户已通过 `doc/PRD-diagnostic-export-v1.4.x.md`
- [x] 确认用户已通过 `doc/dev_plan_v1.4.x.md`
- [x] 确认用户已通过 `doc/progress_v1.4.x.md`
- [x] 确认本功能目标版本为 Full v1.4.x 后续版本
- [x] 确认不进入 Lite v0 必做范围
- [x] 切换到 Full `test` 或基于 Full `test` 的开发分支
- [x] 检查工作区未提交改动，避免覆盖 Lite 文档
- [x] 确认本轮只实现诊断能力，不做云上传、自动修复、复杂诊断中心

---

## 3. D1 诊断基础设施

### D1.1 配置项

- [x] 在 `ConfigManager.defaults` 增加 `diagnostic_dir`
- [x] 在 `ConfigManager.defaults` 增加 `diagnostic_keep_days`
- [x] 实现默认诊断目录 `<save_path>/QuickRecDiagnostics`
- [x] 实现未自定义诊断目录时随保存路径变化
- [x] 实现已自定义诊断目录时不随保存路径变化
- [x] 旧配置缺少诊断字段时可正常加载
- [x] 配置保存失败不导致程序崩溃

### D1.2 诊断模块

- [x] 新增 `src/utils/diagnostics.py`
- [x] 定义诊断目录解析函数
- [x] 定义诊断目录创建函数
- [x] 定义诊断目录可写性检查
- [x] 定义诊断快照数据结构
- [x] 定义诊断文本格式化函数
- [x] 定义导出诊断文件函数
- [x] 定义打开诊断目录函数
- [x] 不可用字段统一输出 `unknown`
- [x] 导出文件使用 UTF-8 编码
- [x] 导出文件命名为 `diagnostic_YYYYMMDD_HHMMSS.txt`

### D1.3 文件日志

- [x] 设计文件日志初始化入口
- [x] 保留现有控制台日志行为
- [x] 新增 `quickrec.log`
- [x] 日志目录不存在时自动创建
- [x] 日志目录创建失败时 fallback，不阻塞启动
- [x] 记录 `diagnostic directory fallback`
- [x] 诊断导出时可读取最近 100 行日志

---

## 4. D2 录制上下文接入

### D2.1 录制状态

- [x] 诊断摘要包含当前 recorder state
- [x] 诊断摘要包含最近录制模式
- [x] 诊断摘要包含最近输出路径
- [x] 诊断摘要包含最近 session 目录
- [x] 诊断摘要包含最近保存结果
- [x] 录制状态不可用时显示 `unknown`

### D2.2 FFmpeg 上下文

- [x] 诊断摘要包含 FFmpeg 路径
- [x] 诊断摘要包含 FFmpeg 路径是否存在
- [x] 诊断摘要包含是否 frozen 打包运行
- [x] FFmpeg 缺失时记录最近失败原因
- [x] FFmpeg 启动失败时记录错误阶段
- [x] FFmpeg 编码失败时记录错误阶段

### D2.3 音频上下文

- [x] 诊断摘要包含配置中的 `audio_source`
- [x] 诊断摘要包含 requested_source
- [x] 诊断摘要包含 final_source
- [x] 诊断摘要包含 degraded
- [x] 诊断摘要包含降级 reason
- [x] 系统音频不可用时能体现在诊断文本
- [x] 麦克风不可用时能体现在诊断文本
- [x] 双音频降级时能体现在诊断文本

### D2.4 窗口捕获上下文

- [x] 诊断摘要包含 window hwnd
- [x] 诊断摘要包含 window title
- [x] 诊断摘要包含 capture mode
- [x] 诊断摘要包含 failure stage
- [x] 诊断摘要包含 failure reason
- [x] 诊断摘要包含 rect
- [x] 诊断摘要包含 foreground_result
- [x] 无窗口录制记录时字段显示 `unknown`

### D2.5 保存失败上下文

- [x] 最终化失败时记录最近错误
- [x] 文件移动失败时记录最近错误
- [x] 音频混流失败时记录最近错误
- [x] 诊断摘要包含保存路径
- [x] 诊断摘要包含最近失败 reason

---

## 5. D3 UI 入口接入

### D3.1 设置页诊断分组

- [x] 在设置页新增“诊断”分组
- [x] 新增诊断目录输入框
- [x] 新增诊断目录“浏览...”按钮
- [x] 新增“复制诊断信息”按钮
- [x] 新增“打开日志目录”按钮
- [x] 新增“导出诊断文件”按钮
- [x] 新增状态提示文本
- [x] 加载配置时显示诊断目录
- [x] 点击保存时保存诊断目录
- [x] 点击取消时不保存诊断目录改动
- [x] 选择目录为空时保持原值
- [x] 按钮布局不显著拉高设置窗口

### D3.2 托盘诊断菜单

- [x] 空闲菜单新增“复制诊断信息”
- [x] 空闲菜单新增“打开日志目录”
- [x] 空闲菜单新增“导出诊断文件”
- [x] 录制中菜单新增“复制诊断信息”
- [x] 录制中菜单新增“打开日志目录”
- [x] 录制中菜单新增“导出诊断文件”
- [x] 托盘信号桥新增复制诊断信号
- [x] 托盘信号桥新增打开日志目录信号
- [x] 托盘信号桥新增导出诊断文件信号
- [x] pystray 线程不直接操作 Qt 组件

### D3.3 主入口回调

- [x] `main.py` 初始化诊断管理器
- [x] 连接托盘复制诊断回调
- [x] 连接托盘打开日志目录回调
- [x] 连接托盘导出诊断文件回调
- [x] 连接设置页复制诊断回调
- [x] 连接设置页打开日志目录回调
- [x] 连接设置页导出诊断文件回调
- [x] 剪贴板写入成功时提示“诊断信息已复制”
- [x] 剪贴板写入失败时提示“复制失败，请导出诊断文件”
- [x] 打开目录成功时记录日志
- [x] 打开目录失败时提示“无法打开日志目录”
- [x] 导出成功时提示“诊断文件已导出”
- [x] 导出失败时提示“导出失败，请检查诊断目录权限”

---

## 6. D4 测试与质量门槛

### D4.1 自动化测试

- [x] 新增 `tests/test_diagnostics.py`
- [x] 测试默认诊断目录
- [x] 测试自定义诊断目录
- [x] 测试诊断目录创建成功
- [x] 测试诊断目录不可写失败
- [x] 测试诊断摘要包含应用环境
- [x] 测试诊断摘要包含配置摘要
- [x] 测试诊断摘要包含 FFmpeg 信息
- [x] 测试诊断摘要包含音频预检信息
- [x] 测试诊断摘要包含窗口诊断信息
- [x] 测试不可用字段显示 `unknown`
- [x] 测试导出文件 UTF-8 可读
- [x] 测试导出文件命名格式
- [x] 测试最近日志行读取

### D4.2 现有测试扩展

- [x] `tests/test_config.py` 覆盖诊断配置字段
- [x] `tests/test_settings_dialog.py` 覆盖诊断分组控件
- [x] `tests/test_settings_dialog.py` 覆盖诊断目录保存
- [x] `tests/test_tray_icon.py` 覆盖空闲菜单诊断入口
- [x] `tests/test_tray_icon.py` 覆盖录制中菜单诊断入口
- [x] `tests/test_main_workflow.py` 覆盖诊断回调连接
- [x] `tests/test_recorder_manager.py` 覆盖 FFmpeg 失败上下文
- [x] `tests/test_recorder_manager.py` 覆盖音频降级上下文
- [x] `tests/test_window_diagnostics.py` 覆盖窗口诊断摘要来源

### D4.3 质量命令

- [x] `python -m pytest -q`
- [x] `python -m compileall src scripts tests`
- [x] `python -m ruff check .`
- [x] `python -m mypy`
- [x] `python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen`

---

## 7. D5 打包与发布前验证

### D5.1 打包验证

- [x] 执行 `python -m PyInstaller build_std.spec --clean --noconfirm`
- [x] 启动 `dist\QuickRec\QuickRec.exe`
- [x] 统一最终验收路径为 `E:\codex\QuickRec-v14x-diagnostics\dist\QuickRec\QuickRec.exe`
- [x] 诊断日志目录生成并写入 `quickrec.log`
- [x] 打包产物托盘图标出现并可稳定打开菜单
- [x] 打包产物设置页可打开
- [x] 打包产物设置页显示“诊断”分组
- [x] 打包产物可复制诊断信息
- [x] 打包产物可打开日志目录
- [x] 打包产物可导出诊断文件
- [x] 打包产物修改诊断目录后重启仍保持

### D5.2 录制回归

- [x] 全屏录制开始 / 停止 / 保存正常
- [x] 区域录制开始 / 停止 / 保存正常
- [x] 窗口录制开始 / 停止 / 保存正常
- [x] 无声录制正常
- [x] 系统声音录制正常
- [x] 麦克风录制正常
- [x] 双音频录制正常
- [x] 暂停 / 恢复正常
- [x] 退出流程正常

### D5.3 异常场景验收

- [x] 模拟 FFmpeg 路径缺失，诊断信息包含错误阶段
- [ ] 模拟音频设备不可用，诊断信息包含降级信息
- [ ] 模拟保存路径不可写，诊断信息包含保存失败信息
- [ ] 模拟窗口捕获失败，诊断信息包含窗口诊断信息
- [ ] 模拟诊断目录不可写，UI 给出失败反馈且应用不崩溃

---

## 8. 发布前验收结论

| 验收项 | 结论 | 说明 |
| --- | --- | --- |
| 最终验收对象 | 通过 | 以 `E:\codex\QuickRec-v14x-diagnostics` 作为 v1.4.x Full 候选发布源；`E:\codex\QuickRec` 当前为 Lite 工作区，不作为本轮 Full 验收路径 |
| 打包产物启动 | 通过 | `dist\QuickRec\QuickRec.exe` 可启动，进程存活，日志写入成功 |
| 诊断日志落盘 | 通过 | 默认目录生成 `QuickRecDiagnostics\quickrec.log` |
| 全屏录制回归 | 通过 | 打包产物通过全局快捷键完成全屏录制并生成可解析 MP4 |
| 设置页诊断操作 | 通过 | 已手动确认设置页诊断分组、复制、打开目录、导出、自定义目录持久化 |
| 区域 / 窗口录制回归 | 通过 | 手动验收记录通过，日志显示区域/窗口录制均保存成功 |
| 系统声 / 麦克风 / 双音频回归 | 通过 | 手动验收记录通过，日志显示三类音频捕获、停止和保存成功 |
| 异常场景诊断上下文 | 通过 | 已完成 FFmpeg 缺失场景，诊断文件包含 `last_failure_reason: ffmpeg not found`、`exists: False` |
| 当前发布状态 | 通过 | 可进入最终发布收口 |

## 9. 完成定义

v1.4.x 诊断日志 / 错误导出能力只有满足以下条件后，才可进入发布收口：

- [x] PRD、dev plan、progress 均已确认
- [x] 复制诊断信息可用
- [x] 打开日志目录可用
- [x] 导出诊断文件可用
- [x] 诊断目录可配置
- [x] 典型异常信息进入诊断摘要
- [x] 默认自动化测试通过
- [x] ruff 通过
- [x] mypy 通过
- [x] compileall 通过
- [x] 本地硬件 smoke 通过
- [x] 打包产物主流程通过
- [x] 打包产物诊断功能通过
- [x] 不做云上传、不做自动修复、不做复杂诊断中心
