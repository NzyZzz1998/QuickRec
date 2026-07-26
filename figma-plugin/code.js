const PAGE_NAMES = [
  "QR 01 Full Product Flow",
];

const LEGACY_PAGE_NAMES = [
  "QR 00 Foundations & Components",
  "QR 02 Material Library States",
];

const UI_ATLAS_ITEMS = [
  "托盘菜单 / 空闲", "托盘菜单 / 录制中", "托盘菜单 / 暂停",
  "录制工具栏 / 倒计时", "录制工具栏 / 录制中", "录制工具栏 / 暂停",
  "录制工具栏 / 保存中", "录制结果 / 已入库", "录制结果 / 待重试入库",
  "区域选择 / 拖拽", "区域选择 / 确认", "区域选择 / 过小提示",
  "窗口选择器", "窗口绿色边框", "鼠标点击高亮",
  "设置 / 录制参数", "设置 / 快捷键", "设置 / 诊断",
  "素材库 / 默认", "素材库 / 空状态", "素材库 / 无结果", "素材库 / 查询异常",
  "素材库 / 待入库", "素材库 / 文件缺失", "素材库 / 批量任务",
  "确认 / 移除索引", "确认 / 移入回收站", "确认 / 导入旧目录", "确认 / 重建目录",
  "通知 / 保存成功", "通知 / 索引失败", "通知 / 窗口丢失", "磁盘空间警告",
];

function buttonContract(group, location, label, visible, trigger, frontend, backend, success, failure) {
  return { group, location, label, visible, trigger, frontend, backend, success, failure };
}

const BUTTON_SPECS = [
  buttonContract("托盘", "空闲菜单", "▶ 全屏录制", "RecorderState.IDLE", "TrayIcon._on_start_fullscreen → start_fullscreen_requested", "关闭菜单；通过 Qt 信号桥进入主线程；先执行磁盘空间检查；按配置显示倒计时或直接显示工具栏。", "QuickRecApp._on_start_fullscreen → RecorderWorkflow.start_fullscreen", "托盘切换为录制中菜单；工具栏计时开始；按配置启用非窗口模式点击高亮。", "空间不足时阻断或二次确认；启动失败则通知并关闭工具栏。"),
  buttonContract("托盘", "空闲菜单", "▢ 区域录制", "RecorderState.IDLE", "TrayIcon._on_start_region → start_region_requested", "关闭菜单并打开全屏半透明 AreaSelector；用户需完成拖拽和确认。", "QuickRecApp._on_start_region；确认后调用 RecorderWorkflow.start_region(region)", "进入倒计时/录制工具栏；中央索引记录 mode=region。", "取消选择不创建录制；选区小于 100×100 显示提示并退出；启动失败通知。"),
  buttonContract("托盘", "空闲菜单", "🖥 窗口录制", "RecorderState.IDLE", "TrayIcon._on_start_window → start_window_requested", "打开 WindowSelector 模态窗口；选择后恢复最小化窗口、置前台并短暂显示绿色边框。", "QuickRecApp._on_start_window → _on_window_selected → RecorderWorkflow.start_window(hwnd)", "开始窗口录制并隐藏绿色边框；中央索引记录 mode=window。", "目标关闭或无法取得区域时通知并回到空闲；取消不改变状态。"),
  buttonContract("托盘", "录制中菜单", "⏸ 暂停录制", "RecorderState.RECORDING", "TrayIcon._on_pause_resume → pause_resume_requested", "菜单文案切换为“▶ 继续录制”；工具栏指示灯变琥珀并显示继续按钮。", "QuickRecApp._on_pause_resume → RecorderWorkflow.pause", "编码会话保持但停止写入新画面；状态变为 PAUSED。", "非 RECORDING 状态忽略，不重复暂停。"),
  buttonContract("托盘", "暂停菜单", "▶ 继续录制", "RecorderState.PAUSED", "与暂停使用同一 pause_resume_requested 信号", "菜单恢复“⏸ 暂停录制”；工具栏指示灯恢复红色。", "QuickRecApp._on_pause_resume → RecorderWorkflow.resume", "继续向当前录制会话写入画面；计时继续增长。", "非 PAUSED 状态忽略；窗口仍最小化时可能再次进入暂停保护。"),
  buttonContract("托盘", "录制中/暂停菜单", "⏹ 停止录制", "RECORDING 或 PAUSED", "TrayIcon._on_stop → stop_requested", "工具栏立即进入“保存中...”并禁用录制控制。", "QuickRecApp._on_stop_recording → RecorderWorkflow.stop", "编码完成后生成 MP4、尝试素材入库并切换结果条。", "IDLE/SAVING 时忽略；保存失败通知并关闭工具栏。"),
  buttonContract("托盘", "全部菜单", "⚙ 设置", "应用运行中", "TrayIcon._on_settings → settings_requested", "暂停全局快捷键监听，打开 SettingsDialog 模态窗口。", "QuickRecApp._show_settings", "保存后重绑快捷键；保存路径变化触发旧历史发现；关闭后恢复监听。", "取消不写配置；诊断子操作失败只显示反馈，不强制关闭设置。"),
  buttonContract("托盘", "全部菜单", "素材库", "应用运行中", "TrayIcon._on_material_library → material_library_requested", "创建或复用单实例 MaterialLibraryDialog；重新加载索引并置前。", "QuickRecApp._show_material_library", "展示中央索引、待入库记录及保存路径迁移提示。", "索引加载失败显示非阻塞错误状态；不影响录制。"),
  buttonContract("托盘", "全部菜单", "📁 打开保存文件夹", "配置存在 save_path", "TrayIcon._on_open_folder", "调用系统资源管理器打开当前保存目录。", "os.startfile(save_path)", "资源管理器打开；QuickRec 状态不变。", "目录不存在或系统调用失败时写日志/保持应用运行。"),
  buttonContract("托盘", "诊断区", "复制诊断信息", "应用运行中", "TrayIcon._on_copy_diagnostic → copy_diagnostic_requested", "收集应用、配置、录制器、FFmpeg、音频、窗口及最近日志摘要并写入剪贴板。", "QuickRecApp._on_copy_diagnostic_info → _build_diagnostic_text", "系统通知“诊断信息已复制”。", "剪贴板不可用时通知“复制失败，请导出诊断文件”。"),
  buttonContract("托盘", "诊断区", "打开日志目录", "应用运行中", "TrayIcon._on_open_diagnostic_dir", "解析当前诊断目录并调用资源管理器。", "QuickRecApp._on_open_diagnostic_dir → diagnostics.open_diagnostic_dir", "目录被创建/打开，并记录成功日志。", "系统调用失败时通知“无法打开日志目录”。"),
  buttonContract("托盘", "诊断区", "导出诊断文件", "应用运行中", "TrayIcon._on_export_diagnostic", "生成 UTF-8 诊断快照文件到当前诊断目录。", "QuickRecApp._on_export_diagnostic_file → diagnostics.export_diagnostic_file", "通知导出成功并保留文件路径。", "目录不可写或写入失败时提示检查诊断目录权限。"),
  buttonContract("托盘", "菜单底部", "✕ 退出", "应用运行中", "TrayIcon._on_exit → exit_requested", "若正在录制先停止并等待最多 60 秒；清理叠加层、工具栏、快捷键和托盘。", "QuickRecApp._on_exit → RecorderWorkflow.stop/wait_until_idle → QApplication.quit", "编码信号处理完成后安全退出。", "等待超时写错误日志，但仍执行界面资源清理。"),

  buttonContract("录制工具栏", "录制/暂停态", "⏸ 暂停 / ▶ 继续", "录制时可用", "RecordingToolbar._on_pause 发 paused/resumed 信号", "按钮文案和指示灯随状态切换；计时暂停或恢复。", "QuickRecApp._on_pause_resume → RecorderWorkflow.pause/resume", "托盘菜单与工具栏状态同步。", "无效状态不执行；不会新建录制会话。"),
  buttonContract("录制工具栏", "录制/暂停态", "⏹ 停止", "录制或暂停时可用", "RecordingToolbar._on_stop 发 stopped 信号", "工具栏进入保存中，三个录制按钮禁用。", "QuickRecApp._on_stop_recording → RecorderWorkflow.stop", "生成 MP4 后显示结果条并执行素材入库。", "编码失败时通知保存失败并关闭工具栏。"),
  buttonContract("录制工具栏", "倒计时/录制态", "✕ 取消", "SAVING 之外可用", "RecordingToolbar._on_cancel 发 cancelled 信号", "立即关闭工具栏、停止点击高亮和窗口边框。", "QuickRecApp._on_cancel_recording → RecorderWorkflow.stop(cancel=True)", "通知“录制已取消”，托盘恢复空闲菜单。", "IDLE/SAVING 不再调用 cancel；已产生的临时会话由录制核心清理。"),
  buttonContract("录制结果条", "保存成功", "✓ 已保存", "output_path 非空", "RecordingToolbar._on_open_file 发 open_file_requested", "重置结果条 5 秒自动关闭计时。", "QuickRecApp._on_open_file → os.startfile(output_path)", "默认播放器打开 MP4。", "系统打开失败被捕获，结果条保持可用。"),
  buttonContract("录制结果条", "保存成功", "📂 打开", "output_path 非空", "RecordingToolbar._on_open_folder 发 open_folder_requested", "重置自动关闭计时。", "QuickRecApp._on_open_folder → explorer.exe /select,path", "资源管理器打开并选中新视频。", "文件不存在时降级打开父目录；异常不终止应用。"),
  buttonContract("录制结果条", "索引成功", "素材库", "index_ok=true", "RecordingToolbar._on_material_library", "重置自动关闭计时并打开/置前素材库。", "QuickRecApp._show_material_library", "最新录制出现在中央素材索引列表。", "索引窗口加载失败显示窗口内反馈，不改变视频保存结果。"),
  buttonContract("录制结果条", "索引失败", "重试入库", "index_ok=false 且 output_path 非空", "RecordingToolbar._on_material_library 发 retry_material_requested", "保持结果条可见并按结果更新按钮文案。", "QuickRecApp._retry_material_item → MaterialIngestionCoordinator.retry", "成功后通知并将按钮改为“素材库”，只保留一条正式记录。", "找不到待入库项或重试失败时通知并保留恢复上下文。"),
  buttonContract("录制结果条", "结果态", "✕ 关闭", "结果条显示中", "RecordingToolbar._on_close_result", "停止 5 秒自动关闭计时并关闭浮条。", "仅 UI 操作，无后端写入。", "结果文件与素材索引保持不变。", "无失败路径；再次录制会创建新工具栏。"),

  buttonContract("区域选择", "确认浮层", "▶ 开始录制", "选区宽高均 ≥100", "AreaSelector._on_start_recording 发 region_selected", "清除确认浮层、恢复箭头光标并关闭遮罩。", "QuickRecApp._on_region_selected → RecorderWorkflow.start_region", "进入倒计时或直接开始区域录制。", "实际启动失败时通知并关闭工具栏。"),
  buttonContract("区域选择", "确认浮层", "✕ 取消", "确认浮层显示", "AreaSelector._on_cancel 发 cancelled", "关闭遮罩和确认浮层。", "QuickRecApp._on_selection_cancelled", "回到录制前空闲状态，不创建文件。", "无后端失败；右键和 ESC 与此行为一致。"),
  buttonContract("窗口选择器", "底部", "刷新", "选择器打开", "WindowSelector._refresh", "清空列表并重新枚举当前可见顶层窗口；标注最小化窗口。", "Win32 EnumWindows/IsWindowVisible/IsIconic", "列表更新，当前选择可能被清除。", "单个窗口枚举异常被跳过，不关闭选择器。"),
  buttonContract("窗口选择器", "底部", "选择", "列表存在当前项", "WindowSelector._select；双击列表项同效", "最小化目标先恢复；发出 hwnd/title 并关闭对话框。", "QuickRecApp._on_window_selected → SetForegroundWindow → start_window", "目标置前、显示绿色边框并进入录制。", "未选中时无动作；目标失效时通知并回到空闲。"),
  buttonContract("窗口选择器", "底部", "取消", "选择器打开", "WindowSelector._cancel 发 cancelled", "关闭模态窗口。", "QuickRecApp._on_window_cancelled", "不改变 RecorderState。", "关闭窗口按钮与此行为一致。"),

  buttonContract("设置", "保存路径", "浏览...", "设置窗口打开", "SettingsDialog._browse_save_path", "打开系统目录选择器；确认后仅更新输入框，尚不持久化。", "QFileDialog.getExistingDirectory", "用户可继续修改并点击保存。", "取消目录选择保持原值。"),
  buttonContract("设置", "选项", "开机自启复选框", "设置窗口打开", "用户切换 QCheckBox", "只更新对话框临时状态。", "保存时调用 enable_autostart/disable_autostart 并写 config.auto_start", "下次系统登录按配置启动。", "注册表操作失败应保留应用可用并记录问题。"),
  buttonContract("设置", "选项", "录制倒计时复选框", "设置窗口打开", "QCheckBox.toggled", "启用/禁用秒数下拉框。", "保存时写 show_countdown 与 countdown_seconds", "后续三种录制在启动前显示倒计时。", "未保存直接取消时不改变现有配置。"),
  buttonContract("设置", "选项", "倒计时秒数", "录制倒计时已勾选", "QComboBox 选择 1–10 秒", "更新临时选项。", "保存时写 countdown_seconds=index+1", "后续倒计时使用新秒数。", "倒计时关闭时控件禁用且值不生效。"),
  buttonContract("设置", "选项", "鼠标点击高亮复选框", "设置窗口打开", "用户切换 QCheckBox", "更新临时选项。", "保存时写 mouse_highlight；录制时由 _update_highlight_state 判断", "全屏/区域录制期间显示桌面点击动画。", "窗口录制强制不启用；动画不写入视频帧。"),
  buttonContract("设置", "快捷键", "开始/停止/暂停/区域/窗口快捷键字段", "设置窗口打开", "点击 _ShortcutRecorder 后捕获键盘组合", "暂停全局快捷键监听；字段显示“按下快捷键...”并实时组合修饰键。", "保存后 ConfigManager 写入五个 shortcut_*，对话框关闭后重新注册", "新快捷键立即用于对应操作。", "Escape 取消录制；无效或冲突组合应保持原配置并提示。"),
  buttonContract("设置", "诊断目录", "浏览...", "设置窗口打开", "SettingsDialog._browse_diagnostic_dir", "打开目录选择器并更新诊断路径输入框。", "保存时 ConfigManager.update_diagnostic_dir", "诊断日志与导出文件改用自定义目录。", "取消选择保持原路径；空值不覆盖原配置。"),
  buttonContract("设置", "诊断", "复制诊断信息", "设置窗口打开", "发 copy_diagnostic_requested(path)", "按钮不关闭窗口；状态标签显示结果。", "QuickRecApp._on_copy_diagnostic_info", "剪贴板获得完整诊断文本，托盘和设置均反馈成功。", "失败时状态标签和托盘同时提示改用导出。"),
  buttonContract("设置", "诊断", "打开日志目录", "设置窗口打开", "发 open_diagnostic_dir_requested(path)", "设置窗口保持打开并显示实际目录。", "QuickRecApp._on_open_diagnostic_dir", "资源管理器打开日志目录。", "失败显示“无法打开日志目录”。"),
  buttonContract("设置", "诊断", "导出诊断文件", "设置窗口打开", "发 export_diagnostic_requested(path)", "设置窗口保持打开并显示导出文件路径。", "QuickRecApp._on_export_diagnostic_file", "生成可读 UTF-8 诊断文件。", "不可写时提示检查权限，不修改录制设置。"),
  buttonContract("设置", "底部", "保存", "设置窗口打开", "SettingsDialog._save_config", "读取全部控件；保存配置；发 config_saved；accept 关闭窗口。", "ConfigManager.save；开机自启注册表；QuickRecApp 关闭后重绑快捷键", "设置持久化，重启仍保持；保存路径变化触发旧历史发现。", "持久化异常应记录；不得留下快捷键监听停止状态。"),
  buttonContract("设置", "底部", "取消", "设置窗口打开", "SettingsDialog.reject", "关闭对话框，不读取控件值。", "无配置写入；QuickRecApp 恢复全局快捷键监听", "现有配置保持。", "无失败路径。"),

  buttonContract("素材库", "搜索行", "输入框清除 ×", "搜索框有文字", "QLineEdit 内置 clear button", "清空关键词并启动 150ms 防抖查询。", "MaterialQuerySession.apply(keyword='')", "列表保留其他筛选条件并刷新匹配数。", "查询失败保留上一次有效结果并显示错误。"),
  buttonContract("素材库", "搜索行", "重置条件", "任意查询条件非默认", "MaterialLibraryDialog._reset_query", "清空关键词；状态/模式/音频/时间/排序恢复默认；页数回到第一页。", "MaterialQuerySession.reset", "显示完整素材集合并清除选择。", "索引加载错误仍保留错误提示。"),
  buttonContract("素材库", "筛选行", "状态/模式/音频/时间/排序下拉框", "素材库打开", "currentIndexChanged → _on_query_control_changed", "组合条件按 AND 执行；正式素材先查询再按 50 条分页；待入库独立展示。", "MaterialQueryEngine.execute", "更新表格、匹配数、加载更多按钮和详情。", "执行异常保留上次结果，提示重置条件后重试。"),
  buttonContract("素材库", "工具栏", "导入旧目录", "无素材任务运行", "MaterialLibraryDialog._on_import", "选择旧保存目录；后台预览 v1.5 QuickRecMetadata/recordings.json；任务期间禁用导入/重建。", "RecordingLibraryService.preview_v1_history → commit_migration", "确认后批量写入中央索引并显示新增/重复/跳过数量。", "无旧索引时提示改用重建；取消或失败不改变中央索引。"),
  buttonContract("素材库", "工具栏", "重建目录", "无素材任务运行", "MaterialLibraryDialog._on_rebuild", "选择视频目录并后台扫描；显示进度文案；发现缺失记录候选时逐条询问。", "RecordingLibraryService.preview_directory/find_relink_candidates/commit_scan", "有效 MP4 入库，重复/损坏文件跳过，结果统计可见。", "取消、扫描失败或提交失败均保持原索引；关闭运行中窗口需二次确认。"),
  buttonContract("素材库", "表格底部", "加载更多 50 条", "匹配正式素材超过当前显示数且未达 200", "MaterialLibraryDialog._load_more", "当前查询条件不变，显示上限增加 50。", "MaterialQuerySession.load_more", "追加下一批且排序稳定；到末页隐藏按钮。", "不扫描文件系统；查询失败保持现有行。"),
  buttonContract("素材库", "窗口底部", "关闭", "素材库打开", "MaterialLibraryDialog._close_dialog", "停止查询防抖；页数与选择重置，但查询条件跨窗口保持。", "QDialog.close", "关闭后再次打开从第一页按原条件查询。", "后台任务运行时弹出取消任务确认，不能直接关闭。"),
  buttonContract("素材库", "详情操作", "打开", "已选择记录且按钮可用", "MaterialLibraryDialog._on_open", "调用默认播放器；窗口保持打开。", "os.startfile(item.file_path)", "视频文件被打开。", "路径缺失或系统调用失败时状态栏显示原因。"),
  buttonContract("素材库", "详情操作", "打开目录", "已选择记录", "MaterialLibraryDialog._on_open_dir", "打开正式记录 directory 或待入库文件父目录。", "os.startfile(directory)", "资源管理器进入正确目录。", "目录不存在时状态栏显示错误。"),
  buttonContract("素材库", "详情操作", "复制路径", "已选择记录", "MaterialLibraryDialog._on_copy", "写入完整 file_path 到系统剪贴板。", "QApplication.clipboard.setText", "状态栏显示“素材路径已复制”。", "剪贴板不可用时明确提示，不改变索引。"),
  buttonContract("素材库", "管理操作", "重新定位", "文件缺失、上次定位失败或允许纠正元数据", "MaterialLibraryDialog._on_relink", "打开仅 MP4 文件选择器；取消不变；先验证候选再提交。", "RecordingLibraryService.relink 或 PendingRecordingService.relink", "路径和元数据原子更新，重新加载后状态恢复可用。", "不存在/非 MP4/不可解析/保存失败时原记录不变且允许再次定位。"),
  buttonContract("素材库", "待入库操作", "重试入库", "选中 PendingRecordingItem 且协调器可用", "MaterialLibraryDialog._on_retry_pending", "临时显示 retrying 并刷新行；操作完成后 reload。", "MaterialIngestionCoordinator.retry", "成功转为正式素材并从待处理列表移除。", "失败显示错误并保留待处理记录；协调器缺失时提示重启。"),
  buttonContract("素材库", "待入库操作", "移除待处理记录", "选中待入库记录", "MaterialLibraryDialog._on_remove_pending → QMessageBox", "确认后只移除待处理索引；取消无变化。", "PendingRecordingService.remove", "列表刷新并提示视频文件已保留。", "删除索引失败时保留记录并显示错误。"),
  buttonContract("素材库", "正式素材操作", "从素材库移除", "选中正式素材", "MaterialLibraryDialog._on_remove → QMessageBox", "确认后移除中央索引记录；实际视频不删除。", "RecordingLibraryService.remove", "列表、计数和详情刷新；重启后记录不恢复。", "取消无变化；保存索引失败时记录保持并显示错误。"),
  buttonContract("素材库", "正式素材操作", "删除视频文件", "选中正式素材", "MaterialLibraryDialog._on_delete → QMessageBox", "确认文案明确实际文件进入 Windows 回收站；不清空回收站。", "RecordingLibraryService.recycle", "文件移入回收站并刷新索引。", "取消不变；回收失败时保留索引并显示错误，禁止永久删除降级。"),

  buttonContract("确认弹窗", "导入旧索引", "是 / 否", "预览成功", "QMessageBox.question", "是：提交整批迁移；否：关闭弹窗并提示取消。", "RecordingLibraryService.commit_migration", "只在提交成功后刷新素材库。", "失败不修改原历史文件和中央索引。"),
  buttonContract("确认弹窗", "目录重建", "是 / 否", "扫描完成且存在新增项", "QMessageBox.question", "是：提交扫描结果；否：保持索引不变。", "RecordingLibraryService.commit_scan", "显示重建完成并刷新列表。", "提交失败显示错误；单文件失败不阻断其他有效文件预览。"),
  buttonContract("确认弹窗", "重新定位候选", "是 / 否", "重建扫描发现候选", "逐条 QMessageBox.question", "是：接受候选路径；否：候选作为普通扫描项继续处理。", "RecordingLibraryService.relink", "成功候选不重复写入重建列表。", "定位失败不覆盖原记录。"),
  buttonContract("确认弹窗", "取消素材任务", "是 / 否", "导入/重建后台任务运行时关闭窗口", "MaterialLibraryDialog.closeEvent", "是：请求线程中断，完成后关闭；否：继续任务并保持窗口。", "_LibraryTask.requestInterruption", "取消后中央索引保持事务前状态。", "任务不响应时窗口保持打开并继续显示状态。"),
];

const COLLECTION_NAMES = ["QR Primitives", "QR Semantic"];
const COLORS = {
  canvas: "F2F2F2", surface: "FFFFFF", sidebar: "F8F8F8", line: "D7D7D7",
  text: "202020", muted: "626262", blue: "2563EB", blueSoft: "E8F0FE",
  green: "107C41", greenSoft: "E7F5EC", red: "C42B1C", redSoft: "FCE8E6",
  amber: "9A6A00", amberSoft: "FFF4CE", purple: "5B5FC7", purpleSoft: "EFEFFD",
};

let regularFont = { family: "Inter", style: "Regular" };
let mediumFont = { family: "Inter", style: "Medium" };
let boldFont = { family: "Inter", style: "Bold" };
let styles = {};

function rgb(hex) {
  const value = hex.replace("#", "");
  return {
    r: parseInt(value.slice(0, 2), 16) / 255,
    g: parseInt(value.slice(2, 4), 16) / 255,
    b: parseInt(value.slice(4, 6), 16) / 255,
  };
}

function solid(hex, opacity = 1) {
  return [{ type: "SOLID", color: rgb(hex), opacity }];
}

function setMeta(node, role) {
  node.setSharedPluginData("quickrec", "role", role);
  node.setSharedPluginData("quickrec", "generated", "true");
  return node;
}

function normalizeButtonLabel(label) {
  return label.replace(/[▶▢🖥⚙📁✕⏸⏹✓📂●○☑☐]/g, "").replace(/\s+/g, " ").trim();
}

function matchingButtonSpecs(label) {
  const normalized = normalizeButtonLabel(label);
  return BUTTON_SPECS.map((spec, index) => ({ spec, index })).filter(({ spec }) => {
    const candidate = normalizeButtonLabel(spec.label);
    return candidate === normalized || candidate.includes(normalized) || normalized.includes(candidate);
  });
}

function attachButtonContract(node, label) {
  const matches = matchingButtonSpecs(label);
  const contractIds = matches.map(({ index }) => "B-" + String(index + 1).padStart(3, "0"));
  node.name = "Button / " + label + (contractIds.length ? " / " + contractIds.join(", ") : "");
  node.setSharedPluginData("quickrec", "button-label", label);
  node.setSharedPluginData("quickrec", "contract-count", String(matches.length));
  node.setSharedPluginData("quickrec", "button-contract-ids", contractIds.join(","));
  if (matches.length) {
    const contractText = matches.map(({ spec, index }) => [
      `B-${String(index + 1).padStart(3, "0")}`,
      `[${spec.group} · ${spec.location}] ${spec.label}`,
      `显示条件：${spec.visible}`,
      `触发：${spec.trigger}`,
      `前端：${spec.frontend}`,
      `后端：${spec.backend}`,
      `成功：${spec.success}`,
      `失败/取消：${spec.failure}`,
    ].join("\n")).join("\n\n");
    node.setSharedPluginData("quickrec", "button-contract", contractText);
    if (node.type === "COMPONENT" || node.type === "COMPONENT_SET") node.description = contractText;
  }
  return node;
}

function applyAuto(frame, direction = "VERTICAL", gap = 0, padding = 0) {
  frame.layoutMode = direction;
  frame.primaryAxisSizingMode = "AUTO";
  frame.counterAxisSizingMode = "AUTO";
  frame.itemSpacing = gap;
  frame.paddingTop = padding;
  frame.paddingRight = padding;
  frame.paddingBottom = padding;
  frame.paddingLeft = padding;
}

function frame(name, direction = "VERTICAL", gap = 0, padding = 0) {
  const node = figma.createFrame();
  node.name = name;
  applyAuto(node, direction, gap, padding);
  node.fills = [];
  return setMeta(node, name);
}

function fixedFrame(name, width, height, fill = COLORS.surface, radius = 0) {
  const node = figma.createFrame();
  node.name = name;
  node.resize(width, height);
  node.fills = solid(fill);
  node.cornerRadius = radius;
  node.clipsContent = true;
  return setMeta(node, name);
}

function textNode(value, size = 14, color = COLORS.text, weight = "regular", width = null) {
  const node = figma.createText();
  node.fontName = weight === "bold" ? boldFont : weight === "medium" ? mediumFont : regularFont;
  node.characters = value;
  node.fontSize = size;
  node.fills = solid(color);
  node.lineHeight = { unit: "PIXELS", value: Math.round(size * 1.55) };
  node.letterSpacing = { unit: "PIXELS", value: 0 };
  if (width) {
    node.textAutoResize = "HEIGHT";
    node.resize(width, node.height);
  } else {
    node.textAutoResize = "WIDTH_AND_HEIGHT";
  }
  return setMeta(node, "text");
}

function sectionTitle(title, subtitle) {
  const wrap = frame(title, "VERTICAL", 6, 0);
  wrap.appendChild(textNode(title, 24, COLORS.text, "bold"));
  wrap.appendChild(textNode(subtitle, 13, COLORS.muted, "regular", 760));
  return wrap;
}

function card(name, width, padding = 20, gap = 14) {
  const node = frame(name, "VERTICAL", gap, padding);
  node.resize(width, node.height);
  node.counterAxisSizingMode = "FIXED";
  node.fills = solid(COLORS.surface);
  node.strokes = solid(COLORS.line);
  node.strokeWeight = 1;
  node.cornerRadius = 8;
  node.effects = [{ type: "DROP_SHADOW", color: { ...rgb("000000"), a: 0.08 }, offset: { x: 0, y: 2 }, radius: 8, spread: 0, visible: true, blendMode: "NORMAL" }];
  return node;
}

function pill(label, background = COLORS.blueSoft, foreground = COLORS.blue) {
  const node = frame("Status Chip / " + label, "HORIZONTAL", 0, 0);
  node.paddingTop = 5; node.paddingBottom = 5; node.paddingLeft = 9; node.paddingRight = 9;
  node.fills = solid(background);
  node.cornerRadius = 4;
  node.appendChild(textNode(label, 12, foreground, "medium"));
  return node;
}

function button(label, kind = "primary", width = null) {
  const node = frame("Button / " + kind, "HORIZONTAL", 8, 0);
  node.paddingTop = 9; node.paddingBottom = 9; node.paddingLeft = 14; node.paddingRight = 14;
  node.cornerRadius = 5;
  const scheme = kind === "primary"
    ? [COLORS.blue, COLORS.surface, COLORS.blue]
    : kind === "danger"
      ? [COLORS.surface, COLORS.red, COLORS.red]
      : [COLORS.surface, COLORS.text, COLORS.line];
  node.fills = solid(scheme[0]);
  node.strokes = solid(scheme[2]);
  node.appendChild(textNode(label, 13, scheme[1], "medium"));
  if (width) { node.resize(width, node.height); node.counterAxisSizingMode = "FIXED"; }
  return attachButtonContract(node, label);
}

function nativeButton(label, width = 70, tone = "default", contractLabel = null) {
  const node = frame("Native button / " + label, "HORIZONTAL", 0, 0);
  node.resize(width, 24); node.primaryAxisSizingMode = "FIXED"; node.counterAxisSizingMode = "FIXED";
  node.primaryAxisAlignItems = "CENTER"; node.counterAxisAlignItems = "CENTER";
  node.fills = solid("FAFAFA");
  node.strokes = solid(tone === "focus" ? "0078D4" : "B8B8B8");
  node.strokeWeight = tone === "focus" ? 1.5 : 1;
  node.cornerRadius = 3;
  node.appendChild(textNode(label, 11, tone === "danger" ? COLORS.red : COLORS.text, "regular"));
  return attachButtonContract(node, contractLabel || label);
}

function nativeField(value, width, options = {}) {
  const node = fixedFrame("Native field / " + value, width, options.height || 22, "FFFFFF", 1);
  node.strokes = solid("B7B7B7");
  addAbsolute(node, textNode(value, 10, options.placeholder ? COLORS.muted : COLORS.text, "regular", Math.max(20, width - (options.chevron ? 28 : 12))), 5, 2);
  if (options.chevron) addAbsolute(node, textNode("⌄", 10, COLORS.muted), width - 18, 2);
  if (options.clear) addAbsolute(node, textNode("×", 11, COLORS.muted, "medium"), width - 18, 1);
  if (options.contractLabel) attachButtonContract(node, options.contractLabel);
  return node;
}

function nativeCheckbox(label, checked, contractLabel = null) {
  const node = frame("Native checkbox / " + label, "HORIZONTAL", 5, 0);
  node.counterAxisAlignItems = "CENTER";
  const box = fixedFrame("Checkbox", 13, 13, checked ? "0078D4" : "FFFFFF", 2);
  box.strokes = solid(checked ? "0078D4" : "777777");
  if (checked) addAbsolute(box, textNode("✓", 9, "FFFFFF", "bold"), 2, -1);
  node.appendChild(box); node.appendChild(textNode(label, 10, COLORS.text));
  return attachButtonContract(node, contractLabel || label + "复选框");
}

function field(label, value, width = 240) {
  const wrap = frame("Field / " + label, "VERTICAL", 6, 0);
  wrap.appendChild(textNode(label, 12, COLORS.muted, "medium"));
  const box = frame("Input", "HORIZONTAL", 8, 0);
  box.resize(width, 38); box.primaryAxisSizingMode = "FIXED"; box.counterAxisSizingMode = "FIXED";
  box.paddingTop = 8; box.paddingBottom = 8; box.paddingLeft = 11; box.paddingRight = 11;
  box.fills = solid(COLORS.surface); box.strokes = solid(COLORS.line); box.cornerRadius = 5;
  box.appendChild(textNode(value, 13, value ? COLORS.text : COLORS.muted));
  wrap.appendChild(box);
  return wrap;
}

function navItem(label, active = false) {
  const node = frame("Navigation Item", "HORIZONTAL", 10, 0);
  node.resize(204, 40); node.primaryAxisSizingMode = "FIXED"; node.counterAxisSizingMode = "FIXED";
  node.paddingTop = 9; node.paddingBottom = 9; node.paddingLeft = 12; node.paddingRight = 12;
  node.fills = active ? solid(COLORS.blueSoft) : [];
  node.cornerRadius = 5;
  node.appendChild(textNode(active ? "●" : "○", 12, active ? COLORS.blue : COLORS.muted));
  node.appendChild(textNode(label, 13, active ? COLORS.blue : COLORS.text, active ? "medium" : "regular"));
  return node;
}

function componentFrom(node, name, description) {
  const component = figma.createComponent();
  component.name = name;
  component.description = description;
  component.resize(node.width, node.height);
  while (node.children.length) component.appendChild(node.children[0]);
  component.fills = node.fills;
  component.strokes = node.strokes;
  component.cornerRadius = node.cornerRadius;
  component.paddingTop = node.paddingTop;
  component.paddingRight = node.paddingRight;
  component.paddingBottom = node.paddingBottom;
  component.paddingLeft = node.paddingLeft;
  component.layoutMode = node.layoutMode;
  component.primaryAxisSizingMode = node.primaryAxisSizingMode;
  component.counterAxisSizingMode = node.counterAxisSizingMode;
  component.itemSpacing = node.itemSpacing;
  node.remove();
  return setMeta(component, name);
}

function materialRow(name, path, status, selected = false) {
  const row = frame("Material Row", "HORIZONTAL", 12, 0);
  row.resize(790, 62); row.primaryAxisSizingMode = "FIXED"; row.counterAxisSizingMode = "FIXED";
  row.paddingTop = 10; row.paddingBottom = 10; row.paddingLeft = 12; row.paddingRight = 12;
  row.fills = solid(selected ? COLORS.blueSoft : COLORS.surface);
  row.strokes = solid(COLORS.line);
  const meta = frame("Material meta", "VERTICAL", 2, 0);
  meta.resize(530, 42); meta.counterAxisSizingMode = "FIXED";
  meta.appendChild(textNode(name, 13, COLORS.text, "medium"));
  meta.appendChild(textNode(path, 11, COLORS.muted, "regular", 520));
  row.appendChild(meta);
  row.appendChild(pill(status, status === "文件缺失" ? COLORS.redSoft : status === "待入库" ? COLORS.amberSoft : COLORS.greenSoft, status === "文件缺失" ? COLORS.red : status === "待入库" ? COLORS.amber : COLORS.green));
  return row;
}

async function chooseFonts() {
  const candidates = ["Noto Sans SC", "Microsoft YaHei", "Segoe UI", "Inter"];
  const available = await figma.listAvailableFontsAsync();
  const names = new Set(available.map((item) => item.fontName.family));
  const family = candidates.find((name) => names.has(name)) || "Inter";
  regularFont = { family, style: "Regular" };
  mediumFont = available.some((item) => item.fontName.family === family && item.fontName.style === "Medium") ? { family, style: "Medium" } : regularFont;
  boldFont = available.some((item) => item.fontName.family === family && item.fontName.style === "Bold") ? { family, style: "Bold" } : mediumFont;
  await Promise.all([figma.loadFontAsync(regularFont), figma.loadFontAsync(mediumFont), figma.loadFontAsync(boldFont)]);
}

async function preparePages() {
  await figma.loadAllPagesAsync();
  const existing = new Map(figma.root.children.map((page) => [page.name, page]));
  const pages = [];
  for (const name of PAGE_NAMES) {
    let page = existing.get(name);
    if (!page) { page = figma.createPage(); page.name = name; }
    await page.loadAsync();
    await figma.setCurrentPageAsync(page);
    for (const child of [...page.children]) child.remove();
    page.backgrounds = solid(COLORS.canvas);
    pages.push(page);
  }
  for (const legacyName of LEGACY_PAGE_NAMES) {
    const legacyPage = existing.get(legacyName);
    if (!legacyPage) continue;
    await legacyPage.loadAsync();
    legacyPage.remove();
  }
  return pages;
}

async function resetQrFoundations() {
  const collections = await figma.variables.getLocalVariableCollectionsAsync();
  for (const collection of collections) {
    if (collection.name === "QR Primitives" || collection.name === "QR Semantic") collection.remove();
  }
  const localStyles = [
    ...(await figma.getLocalTextStylesAsync()),
    ...(await figma.getLocalEffectStylesAsync()),
    ...(await figma.getLocalPaintStylesAsync()),
  ];
  for (const style of localStyles) if (style.name.startsWith("QR/")) style.remove();

  const primitive = figma.variables.createVariableCollection("QR Primitives");
  const semantic = figma.variables.createVariableCollection("QR Semantic");
  const mode = primitive.defaultModeId;
  const primitiveVars = {};
  for (const [name, hex] of Object.entries(COLORS)) {
    const variable = figma.variables.createVariable("color/" + name, primitive, "COLOR");
    variable.setValueForMode(mode, { ...rgb(hex), a: 1 });
    primitiveVars[name] = variable;
  }
  const semanticMode = semantic.defaultModeId;
  const aliases = { "surface/default": "surface", "surface/canvas": "canvas", "text/primary": "text", "text/secondary": "muted", "action/primary": "blue", "status/success": "green", "status/danger": "red", "status/warning": "amber" };
  for (const [name, source] of Object.entries(aliases)) {
    const variable = figma.variables.createVariable(name, semantic, "COLOR");
    variable.setValueForMode(semanticMode, figma.variables.createVariableAlias(primitiveVars[source]));
  }
  for (const [name, value] of [["space/4", 4], ["space/8", 8], ["space/12", 12], ["space/16", 16], ["space/24", 24], ["radius/control", 5], ["radius/card", 8]]) {
    const variable = figma.variables.createVariable(name, primitive, "FLOAT");
    variable.setValueForMode(mode, value);
  }

  for (const [name, size, weight] of [["Display", 32, "bold"], ["Title", 24, "bold"], ["Heading", 18, "medium"], ["Body", 14, "regular"], ["Caption", 12, "regular"]]) {
    const style = figma.createTextStyle();
    style.name = "QR/Type/" + name;
    style.fontName = weight === "bold" ? boldFont : weight === "medium" ? mediumFont : regularFont;
    style.fontSize = size;
    style.lineHeight = { unit: "PIXELS", value: Math.round(size * 1.5) };
    styles[name] = style;
  }
  const shadow = figma.createEffectStyle();
  shadow.name = "QR/Effect/Card";
  shadow.effects = [{ type: "DROP_SHADOW", color: { ...rgb("000000"), a: 0.08 }, offset: { x: 0, y: 2 }, radius: 8, spread: 0, visible: true, blendMode: "NORMAL" }];
}

async function createVerifiedImage(base64, label) {
  const decoded = figma.base64Decode(base64);
  const signature = [137, 80, 78, 71, 13, 10, 26, 10];
  if (decoded.length < 24 || signature.some((value, index) => decoded[index] !== value)) throw new Error(label + " 不是有效 PNG");
  const image = figma.createImage(decoded);
  const stored = await image.getBytesAsync();
  if (stored.length !== decoded.length) throw new Error(label + " 写入后字节长度不一致");
  for (let index = 0; index < decoded.length; index += 1) {
    if (stored[index] !== decoded[index]) throw new Error(label + " 写入后字节校验失败");
  }
  return image;
}

function logo(image, size = 72) {
  const node = figma.createRectangle();
  node.name = "QR Mark";
  node.resize(size, size);
  node.fills = [{ type: "IMAGE", imageHash: image.hash, scaleMode: "FIT" }];
  return setMeta(node, "brand-mark");
}

function pageRoot(page, title, subtitle) {
  const root = frame("QR Page Root", "VERTICAL", 28, 40);
  root.resize(1440, root.height); root.counterAxisSizingMode = "FIXED";
  root.fills = solid(COLORS.canvas);
  root.appendChild(sectionTitle(title, subtitle));
  page.appendChild(root);
  root.x = 0; root.y = 0;
  return root;
}

function buildFoundations(page, image) {
  const root = pageRoot(page, "QR Full Design Foundations", "来自 QuickRec Full 当前代码、v1.7 PRD 与已验证桌面原型。适用于安静、紧凑、可扫描的 Windows 创作者工具。 ");
  const brand = card("Brand", 1360, 24, 18);
  const brandRow = frame("Brand row", "HORIZONTAL", 20, 0);
  brandRow.appendChild(logo(image, 72));
  const brandCopy = frame("Brand copy", "VERTICAL", 4, 0);
  brandCopy.appendChild(textNode("QuickRec Full", 28, COLORS.text, "bold"));
  brandCopy.appendChild(textNode("Capture · Organize · Continue", 13, COLORS.muted));
  brandRow.appendChild(brandCopy); brand.appendChild(brandRow); root.appendChild(brand);

  root.appendChild(sectionTitle("Color & Type", "中性色承载高密度信息；蓝、绿、红、琥珀分别用于操作、成功、危险和警告。"));
  const swatches = frame("Color tokens", "HORIZONTAL", 12, 0);
  for (const [name, hex] of Object.entries(COLORS)) {
    const item = frame("Swatch / " + name, "VERTICAL", 7, 10);
    item.fills = solid(COLORS.surface); item.strokes = solid(COLORS.line); item.cornerRadius = 6;
    const color = fixedFrame(name, 88, 52, hex, 4); item.appendChild(color);
    item.appendChild(textNode(name, 11, COLORS.text, "medium")); item.appendChild(textNode("#" + hex, 10, COLORS.muted));
    swatches.appendChild(item);
  }
  root.appendChild(swatches);
  const typeCard = card("Typography", 1360);
  for (const [label, size, weight] of [["Display / 32", 32, "bold"], ["Title / 24", 24, "bold"], ["Heading / 18", 18, "medium"], ["Body / 14", 14, "regular"], ["Caption / 12", 12, "regular"]]) typeCard.appendChild(textNode(label + "  素材发现与轻整理", size, COLORS.text, weight));
  root.appendChild(typeCard);

  root.appendChild(sectionTitle("Core Components", "重复运行时组件随目标 QR 页面重建，不在文件中累积重复副本。"));
  const components = frame("Components", "HORIZONTAL", 16, 0);
  const actions = card("Actions", 310);
  actions.appendChild(componentFrom(button("开始录制", "primary"), "QR/Button/Primary", "主要录制操作"));
  actions.appendChild(componentFrom(button("打开目录", "secondary"), "QR/Button/Secondary", "次要操作"));
  actions.appendChild(componentFrom(button("移入回收站", "danger"), "QR/Button/Danger", "危险文件操作"));
  components.appendChild(actions);
  const inputs = card("Inputs", 410);
  inputs.appendChild(componentFrom(field("搜索", "文件名或完整路径", 350), "QR/Search Field", "素材关键词搜索"));
  inputs.appendChild(componentFrom(field("筛选", "全部录制模式", 350), "QR/Select", "单选筛选控件"));
  components.appendChild(inputs);
  const states = card("States", 290);
  states.appendChild(componentFrom(pill("已入库", COLORS.greenSoft, COLORS.green), "QR/Status Chip/Indexed", "正式素材状态"));
  states.appendChild(componentFrom(pill("待入库", COLORS.amberSoft, COLORS.amber), "QR/Status Chip/Pending", "待恢复状态"));
  states.appendChild(componentFrom(pill("文件缺失", COLORS.redSoft, COLORS.red), "QR/Status Chip/Missing", "缺失文件状态"));
  components.appendChild(states);
  const navigation = card("Navigation", 310);
  navigation.appendChild(componentFrom(navItem("素材库", true), "QR/Navigation Item/Active", "当前导航项"));
  navigation.appendChild(componentFrom(navItem("诊断", false), "QR/Navigation Item/Default", "普通导航项"));
  components.appendChild(navigation);
  root.appendChild(components);
  const rowCard = card("Material Row component", 850);
  rowCard.appendChild(componentFrom(materialRow("QuickRec_20260721_101530.mp4", "E:\\Videos\\QuickRec", "已入库", true), "QR/Material Row", "素材列表行"));
  root.appendChild(rowCard);
}

function flowStep(index, title, detail, color = COLORS.blue) {
  const node = card("Flow / " + title, 230, 18, 10);
  const top = frame("Step header", "HORIZONTAL", 10, 0);
  top.appendChild(pill(String(index).padStart(2, "0"), color === COLORS.green ? COLORS.greenSoft : COLORS.blueSoft, color));
  top.appendChild(textNode(title, 15, COLORS.text, "medium"));
  node.appendChild(top); node.appendChild(textNode(detail, 12, COLORS.muted, "regular", 190));
  return node;
}

function windowPanel(title, width, subtitle = "当前产品界面") {
  const panel = card(title, width, 0, 0);
  const chrome = frame("Window chrome", "HORIZONTAL", 10, 12);
  chrome.resize(width, 48); chrome.primaryAxisSizingMode = "FIXED"; chrome.counterAxisSizingMode = "FIXED";
  chrome.fills = solid("F7F7F7"); chrome.strokes = solid(COLORS.line);
  chrome.appendChild(textNode(title, 13, COLORS.text, "medium"));
  const spacer = fixedFrame("spacer", Math.max(10, width - 220), 1, "F7F7F7"); chrome.appendChild(spacer);
  chrome.appendChild(textNode("—  □  ×", 12, COLORS.muted));
  panel.appendChild(chrome);
  if (subtitle) {
    const note = frame("Window note", "HORIZONTAL", 0, 12); note.resize(width, 42); note.primaryAxisSizingMode = "FIXED"; note.counterAxisSizingMode = "FIXED";
    note.fills = solid(COLORS.blueSoft); note.appendChild(textNode(subtitle, 11, COLORS.blue, "medium")); panel.appendChild(note);
  }
  return panel;
}

function menuMock(title, items, activeIndex = -1) {
  const panel = windowPanel(title, 300, "Windows 托盘右键菜单");
  const body = frame("Menu body", "VERTICAL", 0, 8); body.resize(300, body.height); body.counterAxisSizingMode = "FIXED";
  items.forEach((label, index) => {
    const row = frame("Menu item", "HORIZONTAL", 8, 9); row.resize(284, 36); row.primaryAxisSizingMode = "FIXED"; row.counterAxisSizingMode = "FIXED";
    row.fills = index === activeIndex ? solid(COLORS.blueSoft) : [];
    row.appendChild(textNode(label === "-" ? "────────────────" : label, 12, label === "-" ? COLORS.line : COLORS.text, index === activeIndex ? "medium" : "regular"));
    if (label !== "-") attachButtonContract(row, label);
    body.appendChild(row);
  });
  panel.appendChild(body); return panel;
}

function toolbarMock(title, timer, indicator, buttons, tone = COLORS.red) {
  const panel = frame("Recording toolbar / " + title, "VERTICAL", 6, 0);
  panel.appendChild(textNode(title, 12, COLORS.text, "medium"));
  const widths = { "倒计时": 290, "录制中": 318, "已暂停": 318, "保存中": 347, "结果 / 已入库": 412, "结果 / 索引失败": 412 };
  const bar = frame("Toolbar / actual 40px", "HORIZONTAL", 8, 0);
  bar.resize(widths[title] || 318, 40); bar.primaryAxisSizingMode = "FIXED"; bar.counterAxisSizingMode = "FIXED";
  bar.counterAxisAlignItems = "CENTER";
  bar.paddingTop = 5; bar.paddingBottom = 5; bar.paddingLeft = 10; bar.paddingRight = 10;
  bar.fills = solid("1A1A2E"); bar.cornerRadius = 0;
  bar.appendChild(textNode(indicator, 16, tone, "bold"));
  bar.appendChild(textNode(timer, 11, "ECF0F1", "regular"));
  buttons.forEach((label) => {
    const control = frame("Toolbar button", "HORIZONTAL", 0, 0);
    control.resize(70, 28); control.primaryAxisSizingMode = "FIXED"; control.counterAxisSizingMode = "FIXED";
    control.primaryAxisAlignItems = "CENTER"; control.counterAxisAlignItems = "CENTER";
    control.fills = []; control.strokes = solid("555555"); control.cornerRadius = 4;
    control.appendChild(textNode(label, 11, label.includes("取消") ? "E6A3A0" : "BDC3C7", "regular")); attachButtonContract(control, label); bar.appendChild(control);
  });
  panel.appendChild(bar); return panel;
}

function settingsMock() {
  const panel = fixedFrame("QuickRec 设置 / 440×447", 440, 447, "F0F0F0", 0);
  panel.strokes = solid("C8C8C8");
  const addLabel = (label, y) => addAbsolute(panel, textNode(label + "：", 10, COLORS.text, "regular", 72), 10, y + 2);
  const addRow = (label, value, y, options = {}) => {
    addLabel(label, y);
    const width = options.action ? 274 : 344;
    const fieldNode = nativeField(value, width, { chevron: options.chevron, contractLabel: options.contractLabel });
    addAbsolute(panel, fieldNode, 84, y);
    if (options.action) addAbsolute(panel, nativeButton(options.action, 70, "focus"), 358, y - 1);
  };
  addRow("保存路径", "E:\\Videos\\QuickRec", 12, { action: "浏览..." });
  addRow("画质", "原生（2560×1440）", 41, { chevron: true });
  addRow("帧率", "60", 69, { chevron: true });
  addRow("音频源", "两者都有", 97, { chevron: true });
  addLabel("选项", 125);
  addAbsolute(panel, nativeCheckbox("开机自启", false, "开机自启复选框"), 84, 127);
  addAbsolute(panel, nativeCheckbox("录制倒计时", true, "录制倒计时复选框"), 165, 127);
  addAbsolute(panel, nativeField("3 秒", 58, { chevron: true, contractLabel: "倒计时秒数" }), 262, 124);
  addAbsolute(panel, nativeCheckbox("鼠标点击高亮", true, "鼠标点击高亮复选框"), 333, 127);
  const shortcutRows = [["开始快捷键", "Ctrl+Shift+R"], ["停止快捷键", "Ctrl+Shift+S"], ["暂停快捷键", "Ctrl+Shift+P"], ["区域录制", "Ctrl+Shift+A"], ["窗口录制", "Ctrl+Shift+W"]];
  shortcutRows.forEach(([label, value], index) => addRow(label, value, 153 + index * 28, { contractLabel: "开始/停止/暂停/区域/窗口快捷键字段" }));

  const diagnostics = fixedFrame("诊断 / QGroupBox", 418, 99, "F0F0F0", 0);
  diagnostics.strokes = solid("D0D0D0");
  addAbsolute(diagnostics, textNode("诊断", 10, COLORS.text), 9, -3);
  const diagnosticPath = nativeField("E:\\Videos\\QuickRec\\QuickRecDiagnostics", 321);
  addAbsolute(diagnostics, diagnosticPath, 10, 19);
  addAbsolute(diagnostics, nativeButton("浏览...", 70, "default"), 338, 18);
  addAbsolute(diagnostics, nativeButton("复制诊断信息", 126), 10, 49);
  addAbsolute(diagnostics, nativeButton("打开日志目录", 126), 146, 49);
  addAbsolute(diagnostics, nativeButton("导出诊断文件", 126), 282, 49);
  addAbsolute(diagnostics, textNode("诊断状态在此处反馈，不关闭设置窗口", 9, COLORS.muted), 10, 78);
  addAbsolute(panel, diagnostics, 11, 297);

  addAbsolute(panel, nativeButton("保存", 78, "focus"), 264, 405);
  addAbsolute(panel, nativeButton("取消", 78), 350, 405);
  return panel;
}

function windowSelectorMock() {
  const panel = fixedFrame("选择录制窗口 / 460×340", 460, 340, "F0F0F0", 0);
  panel.strokes = solid("C8C8C8");
  const list = fixedFrame("QListWidget", 438, 289, "FFFFFF", 0); list.strokes = solid("8A8A8A");
  ["课程课件 - PowerPoint", "国宝 - 微信", "录制脚本 - Visual Studio Code", "文件资源管理器（最小化）"].forEach((label, index) => {
    const row = fixedFrame("Window option", 436, 30, index === 1 ? "E5F1FB" : "FFFFFF", 0);
    addAbsolute(row, textNode(label, 10, COLORS.text, index === 1 ? "medium" : "regular"), 6, 6);
    row.y = index * 30; list.appendChild(row);
  });
  addAbsolute(panel, list, 11, 11);
  addAbsolute(panel, nativeButton("刷新", 72, "focus"), 12, 307);
  addAbsolute(panel, nativeButton("选择", 73), 294, 307);
  addAbsolute(panel, nativeButton("取消", 72), 376, 307);
  return panel;
}

function areaSelectorMock(state) {
  const panel = frame("区域选择 / " + state, "VERTICAL", 6, 0);
  panel.appendChild(textNode("区域选择 / " + state, 12, COLORS.text, "medium"));
  const desktop = fixedFrame("AreaSelector / actual 900×520", 900, 520, "000000", 0);
  const isSmall = state === "过小提示";
  const selection = fixedFrame("Selection", isSmall ? 80 : state === "拖拽" ? 420 : 640, isSmall ? 70 : state === "拖拽" ? 240 : 350, "000000", 0);
  selection.x = isSmall ? 349 : state === "拖拽" ? 210 : 119;
  selection.y = isSmall ? 210 : state === "拖拽" ? 130 : 79;
  selection.strokes = solid("FFFFFF"); selection.strokeWeight = 2; selection.dashPattern = [8, 6]; desktop.appendChild(selection);
  const dimensions = textNode(isSmall ? "80 × 70" : state === "拖拽" ? "420 × 240" : "640 × 350", 13, "FFFFFF", "bold");
  dimensions.x = isSmall ? 358 : state === "拖拽" ? 372 : 399; dimensions.y = isSmall ? 186 : state === "拖拽" ? 105 : 50; desktop.appendChild(dimensions);
  if (state === "确认") {
    const confirm = fixedFrame("Selection confirm", 214, 45, "1A1A2E", 8); confirm.x = 332; confirm.y = 233;
    addAbsolute(confirm, nativeButton("▶ 开始录制", 100, "focus"), 12, 8);
    addAbsolute(confirm, nativeButton("✕ 取消", 80), 122, 8);
    desktop.appendChild(confirm);
  }
  if (isSmall) {
    const warning = fixedFrame("Minimum size warning", 176, 28, "000000", 4); warning.strokes = solid(COLORS.red);
    addAbsolute(warning, textNode("选区太小（最小 100×100）", 10, COLORS.red, "medium"), 11, 5);
    warning.x = 302; warning.y = 231; desktop.appendChild(warning);
  }
  panel.appendChild(desktop); return panel;
}

function overlayMock(title, type) {
  const panel = windowPanel(title, 520, "只在真实桌面显示；不额外写入视频帧");
  const desktop = fixedFrame("Overlay preview", 520, 270, "41464D", 0);
  if (type === "window") { const target = fixedFrame("Target window", 410, 190, "F5F5F5", 4); target.x = 55; target.y = 40; target.strokes = solid("00B578"); target.strokeWeight = 4; desktop.appendChild(target); addAbsolute(desktop, textNode("目标窗口绿色边框", 12, "00B578", "medium"), 160, 120); }
  else { const ring = figma.createEllipse(); ring.resize(66, 66); ring.x = 227; ring.y = 100; ring.fills = []; ring.strokes = solid(COLORS.red, 0.75); ring.strokeWeight = 5; desktop.appendChild(ring); addAbsolute(desktop, textNode("点击扩散动画", 12, COLORS.surface, "medium"), 210, 180); }
  panel.appendChild(desktop); return panel;
}

function dialogMock(title, message, primary, danger = false) {
  const panel = frame("确认弹窗 / " + title, "VERTICAL", 6, 0);
  panel.appendChild(textNode(title, 12, COLORS.text, "medium"));
  const isRemove = title === "从素材库移除";
  const isRecycle = title === "移入 Windows 回收站";
  const width = isRemove ? 205 : isRecycle ? 254 : 430;
  const height = isRemove || isRecycle ? 102 : 138;
  const box = fixedFrame("QMessageBox / " + title, width, height, "F4F4F4", 0); box.strokes = solid("C8C8C8");
  const icon = figma.createEllipse(); icon.resize(32, 32); icon.x = 10; icon.y = 11;
  icon.fills = solid(isRecycle || danger ? "FFC107" : "168CE5"); box.appendChild(icon);
  addAbsolute(box, textNode(isRecycle || danger ? "!" : "?", 18, "FFFFFF", "bold"), 22, 12);
  addAbsolute(box, textNode(message, isRemove || isRecycle ? 11 : 12, COLORS.text, "regular", width - 58), 50, 10);
  const divider = fixedFrame("Dialog divider", width, 1, "D8D8D8", 0); addAbsolute(box, divider, 0, isRemove || isRecycle ? 57 : 87);
  const buttonY = isRemove || isRecycle ? 67 : 101;
  addAbsolute(box, nativeButton(isRemove || isRecycle ? "Yes" : primary, 72, "focus", "是 / 否"), width - 166, buttonY);
  addAbsolute(box, nativeButton(isRemove || isRecycle ? "No" : "取消", 72, "default", "是 / 否"), width - 84, buttonY);
  panel.appendChild(box);
  return panel;
}

function notificationMock() {
  const panel = windowPanel("通知与失败反馈", 760, "系统通知、录制降级和磁盘空间边界");
  const body = frame("Notification body", "VERTICAL", 10, 16); body.resize(760, body.height); body.counterAxisSizingMode = "FIXED";
  [["✓", "录制已保存", "视频已保存并加入素材库", COLORS.greenSoft, COLORS.green], ["!", "录制已保存，但素材索引写入失败", "可在结果条重试入库并查看诊断日志", COLORS.amberSoft, COLORS.amber], ["!", "录制窗口已最小化", "录制已暂停；恢复窗口后点击继续", COLORS.amberSoft, COLORS.amber], ["×", "磁盘剩余空间严重不足", "低于 200 MB，无法开始录制", COLORS.redSoft, COLORS.red]].forEach(([icon, title, detail, bg, fg]) => { const item = frame("Notification", "HORIZONTAL", 12, 12); item.resize(728, 66); item.primaryAxisSizingMode = "FIXED"; item.counterAxisSizingMode = "FIXED"; item.fills = solid(bg); item.cornerRadius = 6; item.appendChild(textNode(icon, 18, fg, "bold")); const copy = frame("Notification copy", "VERTICAL", 2, 0); copy.appendChild(textNode(title, 13, COLORS.text, "medium")); copy.appendChild(textNode(detail, 11, COLORS.muted)); item.appendChild(copy); body.appendChild(item); });
  panel.appendChild(body); return panel;
}

function atlasSection(root, title, subtitle, items, sectionKey) {
  const band = frame(title + " / band", "VERTICAL", 16, 24);
  band.resize(5120, band.height); band.counterAxisSizingMode = "FIXED";
  band.fills = solid(COLORS.surface); band.strokes = solid(COLORS.line);
  band.appendChild(sectionTitle(title, subtitle));
  band.appendChild(localFlowLane(sectionKey));
  const prototypeHeading = frame(title + " / prototype heading", "HORIZONTAL", 10, 0);
  prototypeHeading.appendChild(pill("A · 可编辑原型", COLORS.purpleSoft, COLORS.purple));
  prototypeHeading.appendChild(textNode("已按当前 PyQt 运行截图校准真实尺寸、控件顺序、间距与状态文案；画布不再包含截图图层。", 13, COLORS.muted));
  band.appendChild(prototypeHeading);
  const row = frame(title + " / row", "HORIZONTAL", 18, 0);
  row.counterAxisAlignItems = "MIN";
  items.forEach((item) => row.appendChild(item));
  band.appendChild(row);
  band.appendChild(buildAssociatedContracts(sectionKey));
  root.appendChild(band);
}

function relationshipNode(title, detail, tone = "blue", width = 260) {
  const palette = tone === "green" ? [COLORS.greenSoft, COLORS.green] : tone === "amber" ? [COLORS.amberSoft, COLORS.amber] : tone === "purple" ? [COLORS.purpleSoft, COLORS.purple] : [COLORS.blueSoft, COLORS.blue];
  const node = frame("Flow node / " + title, "VERTICAL", 7, 14);
  node.resize(width, 112); node.primaryAxisSizingMode = "FIXED"; node.counterAxisSizingMode = "FIXED";
  node.fills = solid(palette[0]); node.strokes = solid(palette[1]); node.cornerRadius = 6;
  node.appendChild(textNode(title, 14, COLORS.text, "medium"));
  node.appendChild(textNode(detail, 11, COLORS.muted, "regular", width - 28));
  return node;
}

function relationshipArrow(label = "") {
  const wrap = frame("Flow arrow", "VERTICAL", 3, 0);
  wrap.resize(86, 58); wrap.primaryAxisSizingMode = "FIXED"; wrap.counterAxisSizingMode = "FIXED";
  if (label) wrap.appendChild(textNode(label, 10, COLORS.muted, "medium", 86));
  wrap.appendChild(textNode("────────→", 13, COLORS.blue, "medium"));
  return wrap;
}

function buildRelationshipMap() {
  const map = frame("QuickRec screen relationship map", "VERTICAL", 20, 28);
  map.resize(5120, map.height); map.counterAxisSizingMode = "FIXED";
  map.fills = solid("F7F9FC"); map.strokes = solid(COLORS.line);
  map.appendChild(sectionTitle("页面关系总览", "从托盘发起录制，经过选择与控制生成 MP4，再进入中央素材索引；设置、诊断和失败恢复围绕主链工作。"));
  const main = frame("Primary journey", "HORIZONTAL", 10, 0); main.counterAxisAlignItems = "CENTER";
  const primary = [
    ["托盘入口", "空闲、录制中、暂停三态", "blue"],
    ["录制模式", "全屏 / 区域 / 窗口", "blue"],
    ["选择与倒计时", "区域框选或窗口选择", "blue"],
    ["录制工具栏", "暂停、继续、停止、取消", "blue"],
    ["MP4 保存", "FFmpeg 编码完成", "green"],
    ["素材索引", "写入元数据或生成待入库项", "green"],
    ["素材库", "搜索、筛选、排序与详情", "green"],
    ["素材操作", "打开、定位、移除、回收站", "green"],
  ];
  primary.forEach((item, index) => { main.appendChild(relationshipNode(...item)); if (index < primary.length - 1) main.appendChild(relationshipArrow(index === 4 ? "入库" : "")); }); map.appendChild(main);
  const branches = frame("Supporting journeys", "HORIZONTAL", 18, 0);
  const settingsBranch = frame("Settings branch", "HORIZONTAL", 10, 0); settingsBranch.appendChild(relationshipNode("设置", "保存路径、画质、FPS、音频、快捷键", "purple", 320)); settingsBranch.appendChild(relationshipArrow("影响录制")); settingsBranch.appendChild(relationshipNode("录制模式与工具栏", "读取设置并建立录制会话", "blue", 320)); branches.appendChild(settingsBranch);
  const diagnosticBranch = frame("Diagnostic branch", "HORIZONTAL", 10, 0); diagnosticBranch.appendChild(relationshipNode("失败与异常", "启动、FFmpeg、音频、保存或索引失败", "amber", 320)); diagnosticBranch.appendChild(relationshipArrow("记录上下文")); diagnosticBranch.appendChild(relationshipNode("诊断", "复制信息、打开日志、导出文件", "purple", 320)); branches.appendChild(diagnosticBranch);
  const retryBranch = frame("Retry branch", "HORIZONTAL", 10, 0); retryBranch.appendChild(relationshipNode("索引写入失败", "视频已保存，不能误报录制失败", "amber", 320)); retryBranch.appendChild(relationshipArrow("短时恢复")); retryBranch.appendChild(relationshipNode("结果条 / 重试入库", "成功后进入素材库且不重复", "green", 320)); branches.appendChild(retryBranch); map.appendChild(branches);
  const legend = frame("Flow legend", "HORIZONTAL", 10, 0); legend.appendChild(pill("蓝色：录制交互", COLORS.blueSoft, COLORS.blue)); legend.appendChild(pill("绿色：保存与素材", COLORS.greenSoft, COLORS.green)); legend.appendChild(pill("紫色：设置与诊断", COLORS.purpleSoft, COLORS.purple)); legend.appendChild(pill("琥珀：异常与恢复", COLORS.amberSoft, COLORS.amber)); map.appendChild(legend);
  return map;
}

function contractLine(label, value, color = COLORS.text) {
  const line = frame("Contract / " + label, "HORIZONTAL", 8, 0);
  line.appendChild(textNode(label, 10, COLORS.muted, "medium", 88));
  line.appendChild(textNode(value, 10, color, "regular", 824));
  return line;
}

function buttonContractCard(spec, index) {
  const node = frame("Button contract / " + spec.label, "VERTICAL", 7, 16);
  const contractId = "B-" + String(index + 1).padStart(3, "0");
  node.resize(980, 420); node.primaryAxisSizingMode = "FIXED"; node.counterAxisSizingMode = "FIXED";
  node.fills = solid(COLORS.surface); node.strokes = solid(COLORS.line); node.cornerRadius = 6;
  const header = frame("Contract header", "HORIZONTAL", 8, 0);
  header.appendChild(pill(contractId, COLORS.blueSoft, COLORS.blue));
  header.appendChild(pill(spec.group, COLORS.purpleSoft, COLORS.purple));
  header.appendChild(textNode(spec.label, 14, COLORS.text, "medium", 660)); node.appendChild(header);
  node.appendChild(contractLine("所在界面", spec.location));
  node.appendChild(contractLine("显示条件", spec.visible));
  node.appendChild(contractLine("触发入口", spec.trigger, COLORS.blue));
  node.appendChild(contractLine("前端行为", spec.frontend));
  node.appendChild(contractLine("后端调用", spec.backend, COLORS.purple));
  node.appendChild(contractLine("成功结果", spec.success, COLORS.green));
  node.appendChild(contractLine("失败/取消", spec.failure, COLORS.red));
  node.setSharedPluginData("quickrec", "button-label", spec.label);
  node.setSharedPluginData("quickrec", "button-contract-ids", contractId);
  node.setSharedPluginData("quickrec", "button-contract", [
    `${contractId} [${spec.group} · ${spec.location}] ${spec.label}`,
    `显示条件：${spec.visible}`,
    `触发：${spec.trigger}`,
    `前端：${spec.frontend}`,
    `后端：${spec.backend}`,
    `成功：${spec.success}`,
    `失败/取消：${spec.failure}`,
  ].join("\n"));
  return node;
}

function contractSectionKey(spec) {
  if (spec.group === "托盘") return "01";
  if (spec.group === "区域选择" || spec.group === "窗口选择器") return "02";
  if (spec.group === "录制工具栏" || spec.group === "录制结果条") return "03";
  if (spec.group === "设置") return "04";
  if (spec.group === "确认弹窗") return "07";
  if (spec.group === "素材库") {
    if (["搜索行", "筛选行", "工具栏", "表格底部", "窗口底部", "详情操作"].includes(spec.location)) return "05";
    if (["管理操作", "待入库操作"].includes(spec.location)) return "06";
    if (spec.location === "正式素材操作") return "07";
  }
  throw new Error(`按钮契约未关联到原型分区：${spec.group} / ${spec.location} / ${spec.label}`);
}

function contractEntriesForSection(sectionKey) {
  return BUTTON_SPECS.map((spec, index) => ({ spec, index })).filter(({ spec }) => contractSectionKey(spec) === sectionKey);
}

function localFlowLane(sectionKey) {
  const flowBySection = {
    "01": [["托盘状态", "空闲 / 录制 / 暂停", "blue"], ["用户命令", "录制、设置、素材库、诊断或退出", "blue"], ["Qt 信号", "切回主线程执行", "purple"]],
    "02": [["模式入口", "区域录制或窗口录制", "blue"], ["选择目标", "拖拽选区或选择窗口", "blue"], ["确认结果", "开始录制或安全取消", "green"]],
    "03": [["录制会话", "倒计时、录制与暂停", "blue"], ["停止编码", "进入保存中状态", "blue"], ["保存结果", "打开文件、素材库或重试入库", "green"]],
    "04": [["设置窗口", "编辑录制参数与快捷键", "purple"], ["保存配置", "持久化并重绑快捷键", "blue"], ["诊断操作", "复制、打开目录或导出", "amber"]],
    "05": [["查询条件", "关键词与多条件 AND 组合", "green"], ["正式素材", "排序后按 50 条增量展示", "green"], ["详情操作", "打开、目录与复制路径", "blue"]],
    "06": [["异常记录", "待入库、文件缺失或查询失败", "amber"], ["恢复动作", "重试入库或重新定位", "blue"], ["状态刷新", "成功转正式素材，失败保留上下文", "green"]],
    "07": [["危险操作", "移除索引、回收站、迁移与重建", "amber"], ["确认弹窗", "确认或取消，先验证后提交", "purple"], ["事务结果", "刷新索引或保持原状态", "green"]],
  };
  const lane = frame(`Local flow / ${sectionKey}`, "HORIZONTAL", 10, 0);
  lane.counterAxisAlignItems = "CENTER";
  flowBySection[sectionKey].forEach((item, index) => {
    lane.appendChild(relationshipNode(item[0], item[1], item[2], 360));
    if (index < flowBySection[sectionKey].length - 1) lane.appendChild(relationshipArrow());
  });
  return lane;
}

function buildAssociatedContracts(sectionKey) {
  const entries = contractEntriesForSection(sectionKey);
  const board = frame(`Associated contracts / ${sectionKey}`, "VERTICAL", 16, 18);
  board.resize(5072, board.height); board.counterAxisSizingMode = "FIXED";
  board.fills = solid("F7F9FC"); board.strokes = solid(COLORS.line); board.cornerRadius = 6;
  const heading = frame("Associated contract heading", "HORIZONTAL", 10, 0);
  heading.appendChild(pill("B · 控件契约", COLORS.blueSoft, COLORS.blue));
  heading.appendChild(textNode(`与本区上方原型直接关联，共 ${entries.length} 项；按 B-xxx 编号在控件节点、卡片和前后端实现之间互查。`, 13, COLORS.text, "medium", 1150));
  board.appendChild(heading);
  for (let start = 0; start < entries.length; start += 5) {
    const row = frame(`Associated contracts / ${sectionKey} / ${start / 5 + 1}`, "HORIZONTAL", 16, 0);
    row.counterAxisAlignItems = "MIN";
    entries.slice(start, start + 5).forEach(({ spec, index }) => row.appendChild(buttonContractCard(spec, index)));
    board.appendChild(row);
  }
  return board;
}

function buildEmbeddedComponentRegistry(root) {
  const band = frame("08 · 可复用开发组件 / band", "VERTICAL", 16, 24);
  band.resize(5120, band.height); band.counterAxisSizingMode = "FIXED";
  band.fills = solid(COLORS.surface); band.strokes = solid(COLORS.line);
  band.appendChild(sectionTitle("08 · 可复用开发组件", "原 00 页中真正需要复用的组件已收敛到当前主画布；颜色变量和文字样式继续保存在 Figma 文件级资源中。"));
  const row = frame("Embedded component registry", "HORIZONTAL", 16, 0); row.counterAxisAlignItems = "MIN";
  const actions = card("Buttons", 430);
  actions.appendChild(componentFrom(button("开始录制", "primary"), "QR/Button/Primary", "主要录制操作"));
  actions.appendChild(componentFrom(button("打开目录", "secondary"), "QR/Button/Secondary", "次要操作"));
  actions.appendChild(componentFrom(button("移入回收站", "danger"), "QR/Button/Danger", "危险文件操作"));
  row.appendChild(actions);
  const inputs = card("Query controls", 520);
  inputs.appendChild(componentFrom(field("搜索", "文件名或完整路径", 450), "QR/Search Field", "素材关键词搜索"));
  inputs.appendChild(componentFrom(field("筛选", "全部录制模式", 450), "QR/Select", "单选筛选控件"));
  row.appendChild(inputs);
  const states = card("Status", 360);
  states.appendChild(componentFrom(pill("已入库", COLORS.greenSoft, COLORS.green), "QR/Status Chip/Indexed", "正式素材状态"));
  states.appendChild(componentFrom(pill("待入库", COLORS.amberSoft, COLORS.amber), "QR/Status Chip/Pending", "待恢复状态"));
  states.appendChild(componentFrom(pill("文件缺失", COLORS.redSoft, COLORS.red), "QR/Status Chip/Missing", "缺失文件状态"));
  row.appendChild(states);
  const material = card("Material row", 850);
  material.appendChild(componentFrom(materialRow("QuickRec_20260721_101530.mp4", "E:\\Videos\\QuickRec", "已入库", true), "QR/Material Row", "素材列表行"));
  row.appendChild(material);
  band.appendChild(row);
  root.appendChild(band);
}

function buildProductFlow(page, image) {
  const root = pageRoot(page, "QuickRec Full · Complete UI Atlas", "当前代码中的全部产品窗口、托盘入口、录制浮层、设置诊断、素材库状态与系统反馈集中在同一个大画布。历史 RecentRecordingsDialog 无当前入口，仅在页尾标注。 ");
  root.resize(5200, root.height); root.counterAxisSizingMode = "FIXED";
  const identity = frame("Atlas identity", "HORIZONTAL", 18, 0); identity.appendChild(logo(image, 64));
  const identityCopy = frame("Atlas copy", "VERTICAL", 4, 0); identityCopy.appendChild(textNode(`33 个界面状态 · ${BUTTON_SPECS.length} 项控件契约`, 20, COLORS.text, "bold")); identityCopy.appendChild(textNode("来源：src/ui、src/main.py、v1.4.1-v1.7 PRD 与当前 Full 原型。每项契约就近归入所属界面，不再使用独立总表。", 12, COLORS.muted)); identity.appendChild(identityCopy); root.appendChild(identity);
  root.appendChild(buildRelationshipMap());

  atlasSection(root, "01 · 托盘入口", "QuickRec 没有常驻主窗口；系统托盘是核心产品入口。", [
    menuMock("托盘 / 空闲", ["▶ 全屏录制", "▢ 区域录制", "🖥 窗口录制", "⚙ 设置", "素材库", "📁 打开保存文件夹", "-", "复制诊断信息", "打开日志目录", "导出诊断文件", "-", "✕ 退出"]),
    menuMock("托盘 / 录制中", ["⏸ 暂停录制", "⏹ 停止录制", "⚙ 设置", "素材库", "📁 打开保存文件夹", "-", "复制诊断信息", "打开日志目录", "导出诊断文件", "-", "✕ 退出"]),
    menuMock("托盘 / 已暂停", ["▶ 继续录制", "⏹ 停止录制", "⚙ 设置", "素材库", "📁 打开保存文件夹", "-", "复制诊断信息", "打开日志目录", "导出诊断文件", "-", "✕ 退出"], 0),
  ], "01");

  atlasSection(root, "02 · 录制选择与桌面叠加", "这些界面覆盖真实桌面；区域选区和窗口绿色边框用于确认捕获目标。", [areaSelectorMock("拖拽"), areaSelectorMock("确认"), areaSelectorMock("过小提示"), windowSelectorMock(), overlayMock("窗口录制目标高亮", "window"), overlayMock("鼠标点击高亮", "click")], "02");

  atlasSection(root, "03 · 录制工具栏全状态", "同一个置顶工具栏在倒计时、录制、暂停、编码与结果阶段切换。", [
    toolbarMock("倒计时", "3", "●", ["⏸ 暂停", "⏹ 停止", "✕ 取消"], COLORS.amber),
    toolbarMock("录制中", "00:42", "●", ["⏸ 暂停", "⏹ 停止", "✕ 取消"], COLORS.red),
    toolbarMock("已暂停", "00:42", "●", ["▶ 继续", "⏹ 停止", "✕ 取消"], COLORS.amber),
    toolbarMock("保存中", "保存中...", "●", ["暂停", "停止", "取消"], COLORS.blue),
    toolbarMock("结果 / 已入库", "84.6 MB", "✓", ["✓ 已保存", "📂 打开", "素材库", "✕ 关闭"], COLORS.green),
    toolbarMock("结果 / 索引失败", "84.6 MB", "✓", ["✓ 已保存", "📂 打开", "重试入库", "✕ 关闭"], COLORS.amber),
  ], "03");

  atlasSection(root, "04 · 设置、诊断与系统反馈", "设置页承载完整录制参数、五组快捷键和 v1.4.1 诊断能力。", [settingsMock(), notificationMock()], "04");

  atlasSection(root, "05 · 素材库主界面与查询状态", "中央索引跨保存路径；搜索命中文件名或完整路径，筛选条件与搜索按 AND 组合。", [libraryShell("素材库 / 默认", "default"), libraryShell("素材库 / 空状态", "empty"), libraryShell("素材库 / 无结果", "no-results")], "05");
  atlasSection(root, "06 · 素材库异常与恢复状态", "查询失败保留上一次有效结果；待入库和文件缺失提供恢复入口。", [libraryShell("素材库 / 查询异常", "error"), libraryShell("素材库 / 待入库与文件缺失", "recovery")], "06");

  atlasSection(root, "07 · 文件操作与迁移确认", "所有破坏性操作先确认；移除索引不删除视频，回收站操作处理实际文件。", [
    dialogMock("从素材库移除", "从素材库移除这条记录？视频文件不会被删除。", "确认移除"),
    dialogMock("移入 Windows 回收站", "将此视频移入 Windows 回收站？不会删除诊断日志或其他文件。", "移入回收站", true),
    dialogMock("导入旧目录", "已发现旧录制历史。确认后一次性写入中央素材库，原历史数据保持可恢复。", "确认导入"),
    dialogMock("重建目录", "扫描完成：成功 18 条、已存在 4 条、跳过 2 条、失败 1 条。确认后写入素材库。", "确认重建"),
    dialogMock("重新定位失败", "所选文件不可解析，原索引和缺失状态均未改变。可以重新选择文件。", "重新选择", true),
  ], "07");

  buildEmbeddedComponentRegistry(root);

  const boundary = card("产品边界与历史模块", 1360, 22, 10);
  boundary.appendChild(textNode("当前产品边界", 17, COLORS.text, "bold"));
  boundary.appendChild(textNode("文件/目录选择器、Windows 通知中心和回收站属于系统原生界面，QuickRec 只定义调用时机、文案和结果反馈。", 12, COLORS.muted, "regular", 1250));
  boundary.appendChild(pill("历史保留：RecentRecordingsDialog 当前无 main.py 产品入口", COLORS.amberSoft, COLORS.amber));
  boundary.appendChild(textNode("未来 Full 工作台、AI、剪辑与导出队列不属于当前实现，因此不混入现行窗口清单。", 12, COLORS.muted)); root.appendChild(boundary);
}

function addAbsolute(parent, child, x, y) { child.x = x; child.y = y; parent.appendChild(child); return child; }

function libraryShell(name, state = "default") {
  const shell = fixedFrame(name + " / 980×560", 980, 560, "F0F0F0", 0); shell.strokes = solid("B8B8B8");
  const hasRows = state === "default" || state === "error" || state === "recovery";
  const total = state === "recovery" ? 2 : hasRows ? 3 : 0;
  addAbsolute(shell, nativeField("搜索文件名或完整路径", 727, { placeholder: true, clear: true, contractLabel: "输入框清除 ×" }), 14, 14);
  addAbsolute(shell, textNode(`匹配 ${total} / 共 ${total} 条`, 10, COLORS.text), 751, 17);
  addAbsolute(shell, nativeButton("重置条件", 73, "focus"), 892, 13);
  const filterItems = [["全部状态", 125], ["全部模式", 125], ["全部音频", 125], ["全部时间", 125], ["录制时间：最新优先", 136]];
  let filterX = 14;
  filterItems.forEach(([label, width]) => {
    addAbsolute(shell, nativeField(label, width, { chevron: true, contractLabel: "状态/模式/音频/时间/排序下拉框" }), filterX, 47);
    filterX += width + 10;
  });
  const statusText = state === "empty" ? "暂无素材" : state === "no-results" ? "没有符合当前条件的素材，可点击“重置条件”恢复" : state === "error" ? "素材查询失败，已保留上一次有效结果；可重置条件后重试" : state === "recovery" ? "显示 2 / 2 条素材（待入库与文件缺失）" : "显示 3 / 3 条素材（共 3 条）";
  addAbsolute(shell, textNode(statusText, 10, state === "error" ? COLORS.red : COLORS.text), 14, 82);
  addAbsolute(shell, nativeButton("导入旧目录", 73), 807, 77);
  addAbsolute(shell, nativeButton("重建目录", 73), 892, 77);

  const table = fixedFrame("QTableWidget / materials", 536, 403, "FFFFFF", 0); table.strokes = solid("8A8A8A");
  const header = fixedFrame("Table header", 536, 25, "F4F4F4", 0);
  const columnX = [5, 198, 366, 424, 498, 526];
  ["文件", "时间", "时长", "分辨率", "大小", "状态"].forEach((label, index) => addAbsolute(header, textNode(label, 10, COLORS.text, "medium"), columnX[index], 4));
  table.appendChild(header);
  let rows = [];
  if (state === "default" || state === "error") rows = [
    ["课程录制 01.mp4", "2026-07-21T10:45:22+08:00", "00:08:42", "2560 × 1440", "80.7 MB", "可用"],
    ["QuickRec_20260721_104522.mp4", "2026-07-21T10:44:22+08:00", "00:02:02", "1920 × 1080", "29.8 MB", "可用"],
    ["区域演示.mp4", "2026-07-21T10:43:22+08:00", "00:00:49", "1280 × 720", "12.2 MB", "可用"],
  ];
  if (state === "recovery") rows = [
    ["待入库课程.mp4", "2026-07-21T10:46:22+08:00", "00:03:10", "1920 × 1080", "42.1 MB", "待入库"],
    ["已移动演示.mp4", "2026-07-21T10:40:11+08:00", "00:01:20", "1280 × 720", "18.4 MB", "文件缺失"],
  ];
  rows.forEach((values, rowIndex) => {
    const row = fixedFrame("Table row", 534, 30, rowIndex === 0 ? "E5F1FB" : "FFFFFF", 0); row.y = 25 + rowIndex * 30;
    values.forEach((value, index) => addAbsolute(row, textNode(value, 9, index === 5 && value !== "可用" ? COLORS.amber : COLORS.text, "regular", [187, 162, 54, 70, 54, 70][index]), columnX[index], 6));
    table.appendChild(row);
  });
  addAbsolute(shell, table, 14, 110);

  const detail = fixedFrame("Material detail panel", 402, 403, "F0F0F0", 0);
  const selected = rows.length > 0;
  const selectedName = selected ? rows[0][0] : "未选择素材";
  addAbsolute(detail, textNode(selectedName, 16, COLORS.text, "medium", 390), 0, 5);
  const detailValues = selected ? [
    ["录制时间", rows[0][1]], ["时长", rows[0][2]], ["画面", rows[0][3] + " · 60 FPS"],
    ["模式", state === "recovery" ? "全屏录制" : "窗口录制"], ["音频", "系统声音 + 麦克风"], ["大小", rows[0][4]],
    ["路径", state === "recovery" ? "E:\\Videos\\QuickRec\\待入库课程.mp4" : "E:\\Videos\\QuickRec\\课程录制 01.mp4"],
    ["诊断目录", "E:\\Videos\\QuickRec\\QuickRecDiagnostics"], ["来源", state === "recovery" ? "pending" : "recording"], ["失败原因", state === "recovery" ? "素材索引写入失败，等待重试" : "-"],
  ] : [["录制时间", "-"], ["时长", "-"], ["画面", "-"], ["模式", "-"], ["音频", "-"], ["大小", "-"], ["路径", "-"], ["诊断目录", "-"], ["来源", "-"], ["失败原因", "-"]];
  detailValues.forEach(([label, value], index) => {
    addAbsolute(detail, textNode(label, 10, COLORS.text, "regular", 66), 0, 34 + index * 19);
    addAbsolute(detail, textNode(value, 9, COLORS.text, "regular", 322), 70, 34 + index * 19);
  });
  const openButtons = [nativeButton("打开", 124), nativeButton("打开目录", 124), nativeButton("复制路径", 124)];
  openButtons.forEach((item, index) => { if (!selected) item.opacity = 0.45; addAbsolute(detail, item, index * 133, 230); });
  if (state === "recovery") {
    addAbsolute(detail, nativeButton("重新定位", 124), 0, 260);
    addAbsolute(detail, nativeButton("重试入库", 124), 133, 260);
    addAbsolute(detail, nativeButton("移除待处理记录", 124), 266, 260);
  } else {
    const relink = nativeButton("重新定位", 124); if (selected) relink.opacity = 0.45;
    const remove = nativeButton("从素材库移除", 124); const recycle = nativeButton("删除视频文件", 124, "danger");
    if (!selected) { relink.opacity = 0.45; remove.opacity = 0.45; recycle.opacity = 0.45; }
    addAbsolute(detail, relink, 0, 260); addAbsolute(detail, remove, 133, 260); addAbsolute(detail, recycle, 266, 260);
  }
  addAbsolute(shell, detail, 563, 110);
  if (state === "default" && total > 50) addAbsolute(shell, nativeButton("加载更多 50 条", 110), 14, 525);
  addAbsolute(shell, nativeButton("关闭", 73), 892, 525);
  return shell;
}

function buildMaterialStates(page) {
  const root = pageRoot(page, "Material Library · v1.7", "搜索字段为文件名或完整路径，二者任一命中即可；搜索与各筛选条件按 AND 组合。正式素材每页 50 条。 ");
  root.appendChild(libraryShell("Material Library / Default", "default"));
  root.appendChild(sectionTitle("Necessary States", "状态使用独立画板，便于开发与验收逐一对应。"));
  root.appendChild(libraryShell("Material Library / Empty", "empty"));
  root.appendChild(libraryShell("Material Library / No Results", "no-results"));
  root.appendChild(libraryShell("Material Library / Query Error", "error"));
}

async function buildAll(assets) {
  figma.ui.postMessage({ type: "status", message: "正在载入字体与页面…" });
  await chooseFonts();
  const pages = await preparePages();
  await resetQrFoundations();
  const image = await createVerifiedImage(assets.qrMarkBase64, "QuickRec 品牌标记");
  buildProductFlow(pages[0], image);
  await figma.setCurrentPageAsync(pages[0]);
  figma.viewport.scrollAndZoomIntoView(pages[0].children);
  return { pages: pages.length, collections: COLLECTION_NAMES.length, pageNames: PAGE_NAMES };
}

figma.showUI(__html__, { width: 420, height: 530, themeColors: true });
figma.ui.onmessage = async (message) => {
  if (message.type !== "build") return;
  try {
    const result = await buildAll(message.assets || {});
    figma.ui.postMessage({ type: "complete", message: `已生成 ${result.pages} 个 QR 页面，并保护所有非 QR 页面。` });
    figma.notify("QR Full v1.7 设计已更新");
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({ type: "error", message: detail });
    figma.notify("QR 设计生成失败：" + detail, { error: true });
  }
};
