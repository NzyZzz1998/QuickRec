"use strict";

const contract = (
  title,
  trigger,
  action,
  success,
  failure,
  disabled,
) => ({ title, trigger, action, success, failure, disabled });

const contracts = {
  "nav.record": contract(
    "导航：录制",
    "工作台已打开，且设置页没有未处理的更改。",
    "切换到录制页；同一进程内记录当前页面。",
    "显示录制模式、当前配置、120 FPS 能力和最近结果。",
    "页面构建失败时保留原页面并写入诊断日志。",
    "设置存在未保存更改时先显示“保存 / 放弃 / 取消”对话框。",
  ),
  "nav.library": contract(
    "导航：素材库",
    "工作台已打开，且没有阻塞页面切换的未保存设置。",
    "切换到嵌入式素材库并刷新中央索引和待入库记录。",
    "展示跨保存路径素材、查询条件和详情；保持同进程查询状态。",
    "索引读取失败时展示错误状态，不影响录制能力。",
    "设置有未保存更改时先要求用户决策；后台素材任务运行时仍可查看但限制冲突操作。",
  ),
  "nav.settings": contract(
    "导航：设置",
    "应用未退出；录制中允许查看，但影响当前会话的控件只读。",
    "打开嵌入式设置页，并从正式配置创建独立草稿。",
    "显示保存路径、画质、FPS、音频、录制行为和快捷键。",
    "配置读取异常时使用安全默认值并提示查看诊断。",
    "录制中禁用画质、FPS、音频和保存路径等会影响当前录制的选项。",
  ),
  "nav.diagnostics": contract(
    "导航：诊断",
    "工作台已打开，诊断服务可初始化。",
    "切换到诊断页并读取当前目录、最近事件和 120 FPS 检测摘要。",
    "用户可复制、打开目录或导出本地诊断文件。",
    "诊断目录不可写时展示原因和恢复建议，不关闭工作台。",
    "设置页存在未保存更改时先显示决策对话框。",
  ),
  "top.more": contract(
    "更多工作台操作",
    "工作台处于可交互状态。",
    "打开紧凑菜单，提供打开保存目录和隐藏工作台。",
    "用户完成对应系统操作；隐藏工作台后应用继续驻留托盘。",
    "系统目录打开失败时显示非阻塞反馈。",
    "录制保存阶段可隐藏工作台，但不允许退出应用或改变编码状态。",
  ),
  "record.open-settings": contract(
    "打开录制设置",
    "工作台处于空闲状态。",
    "切换到设置页，并定位到录制输出分组。",
    "用户可修改下一次录制使用的画质、FPS、音频和保存路径。",
    "页面切换失败时留在录制页并写日志。",
    "录制中仍可打开设置页，但会影响当前会话的字段为只读。",
  ),
  "record.quick-start": contract(
    "快速开始全屏录制",
    "应用空闲，保存目录可写，磁盘空间达标；若设置为 120 FPS，还需有效能力缓存和快速校验。",
    "执行磁盘、FFmpeg、目录和 120 FPS 快速校验；通过后隐藏工作台并进入倒计时或直接录制。",
    "显示浮动录制工具栏；停止后恢复工作台并显示保存与入库结果。",
    "校验失败时不启动录制，明确提供重新检测、改用 60 FPS或取消。",
    "录制、自检或保存进行中禁用；磁盘低于 200 MB 时禁用。",
  ),
  "record.fullscreen": contract(
    "开始全屏录制",
    "应用空闲，单显示器环境可用，保存与编码前置检查通过。",
    "使用当前有效画质、FPS和音频配置启动全屏捕获；工作台来源会先隐藏工作台。",
    "浮动工具栏进入计时；视频保存后恢复工作台并尝试加入素材库。",
    "捕获或编码启动失败时恢复工作台，保留错误上下文并提示查看诊断。",
    "正在录制、自检、保存或磁盘严重不足时禁用。",
  ),
  "record.region": contract(
    "选择区域录制",
    "应用空闲，保存路径和 FFmpeg 可用。",
    "隐藏工作台并显示全屏半透明区域选择器；选择范围需至少 100×100。",
    "确认后进入倒计时/工具栏，以最高 60 FPS录制所选区域。",
    "取消或选区过小时恢复工作台且不创建文件；启动失败显示原因。",
    "录制、自检或保存进行中禁用；全局 120 设置不会让本次区域录制超过 60 FPS。",
  ),
  "record.window": contract(
    "选择窗口录制",
    "应用空闲且系统存在可录制顶层窗口。",
    "打开窗口选择器；选择后置前目标、短暂显示绿色边框并启动捕获。",
    "工具栏显示窗口录制状态；停止后生成对应窗口内容的 MP4 并入库。",
    "目标失效或无法取得区域时恢复工作台并通知；取消不创建文件。",
    "录制、自检或保存进行中禁用；最高 60 FPS，当前版本不录制窗口光标。",
  ),
  "record.capability-check": contract(
    "开始 120 FPS 能力检测",
    "未录制、单显示器刷新率至少 119Hz、保存目录可写且 FFmpeg 可用。",
    "打开检测对话框；确认后用真实 dxcam 和 libx264 superfast 执行约 5 秒自检。",
    "全部硬门禁通过后写入能力缓存，并在设置草稿中允许选择 120 FPS。",
    "显示失败阶段、平均/最低 FPS或编码问题，并提供诊断与重新检测。",
    "录制、保存或另一次检测进行中禁用；多显示器或刷新率不足时禁用并显示原因。",
  ),
  "record.open-file": contract(
    "打开最近录制",
    "最近结果存在且文件仍可访问。",
    "调用 Windows 默认播放器打开对应 MP4。",
    "播放器打开目标文件，工作台保持可用。",
    "文件缺失或系统调用失败时显示反馈，并允许打开所在目录或素材库。",
    "没有最近结果或文件路径为空时禁用。",
  ),
  "record.open-folder": contract(
    "打开最近录制目录",
    "最近结果包含有效输出路径。",
    "调用资源管理器并选中新生成的视频；文件缺失时降级打开父目录。",
    "资源管理器进入正确目录，工作台保持可用。",
    "目录不存在或系统调用失败时显示明确错误。",
    "结果路径为空时禁用。",
  ),
  "record.open-library": contract(
    "在素材库查看",
    "最近录制已有输出路径；索引成功或存在待入库记录。",
    "切换到素材库页，并定位到最新正式素材或待入库记录。",
    "详情展示路径、时长、分辨率、FPS、模式和入库状态。",
    "索引加载失败时进入素材库错误状态，但视频保存结果保持成功。",
    "既无正式索引也无待入库上下文时禁用。",
  ),
  "library.search": contract(
    "搜索素材",
    "素材索引已加载。",
    "输入关键词后约 150ms 防抖；文件名或完整路径任一包含关键词即命中，再与筛选条件按 AND 组合。",
    "列表、匹配数、分页和详情同步更新；输入内容在同一进程内跨窗口保持。",
    "查询异常时保留上一次有效结果，并提供重置和重试。",
    "索引加载失败或后台恢复尚未完成时禁用。",
  ),
  "library.reset": contract(
    "重置查询条件",
    "至少一个搜索、筛选或排序条件偏离默认值。",
    "清空关键词，恢复全部状态/模式/音频/时间筛选和默认排序，回到第一页。",
    "展示完整可查询素材集合并更新匹配数。",
    "索引异常时仍保留错误提示，不伪造空结果。",
    "全部条件已经是默认值时可保持可用但不产生额外写入。",
  ),
  "library.import": contract(
    "导入旧目录",
    "没有其他素材任务运行。",
    "选择旧保存目录，后台预览 v1.5 QuickRecMetadata/recordings.json；预览完成后请求确认。",
    "提交后显示新增、重复、跳过和失败数量；原历史文件保持不变。",
    "目录无旧索引时提示改用重建；取消或提交失败不改变中央索引。",
    "导入/重建任务运行中禁用。",
  ),
  "library.rebuild": contract(
    "重建目录",
    "没有其他素材任务运行，用户可选择受控视频目录。",
    "后台扫描 MP4并用 FFprobe 验证；生成成功、已存在、跳过和失败统计后等待确认。",
    "有效视频批量写入中央索引；损坏文件不影响其他文件，重复项不新增。",
    "取消、扫描或提交失败时保留原索引；错误原因进入状态区和日志。",
    "已有素材任务运行时禁用；目录选择取消后不执行。",
  ),
  "library.filter-status": contract(
    "按状态筛选",
    "中央索引和待入库列表已加载。",
    "选择全部、可用、待入库、入库失败、文件缺失或信息不完整。",
    "与关键词和其他筛选按 AND 组合，更新列表和匹配数。",
    "查询失败时保持上一次结果与当前选择，显示重试入口。",
    "索引加载错误时禁用。",
  ),
  "library.filter-mode": contract(
    "按录制模式筛选",
    "素材查询服务可用。",
    "选择全部、全屏、区域、窗口或未知模式。",
    "只显示同时满足关键词和其他筛选的素材。",
    "查询失败时保留上次有效结果。",
    "索引加载失败时禁用。",
  ),
  "library.filter-audio": contract(
    "按音频模式筛选",
    "素材查询服务可用。",
    "选择全部、无声、系统声音、麦克风、双音频或未知。",
    "列表和总数按组合条件更新。",
    "查询失败时保留上次有效结果并记录上下文。",
    "索引加载失败时禁用。",
  ),
  "library.filter-time": contract(
    "按录制时间筛选",
    "素材包含可判断的录制时间。",
    "选择全部、今天、最近 7 天或最近 30 天。",
    "按本地时区计算范围并更新结果。",
    "时间字段异常的记录按未知处理，不导致整个查询失败。",
    "索引加载失败时禁用。",
  ),
  "library.sort": contract(
    "素材排序",
    "素材查询结果已生成。",
    "按录制时间、时长或文件大小排序；稳定排序确保翻页不跳变。",
    "列表按选择顺序更新，当前查询状态保留。",
    "排序字段缺失时按既定空值规则放置并保留记录。",
    "索引加载失败时禁用。",
  ),
  "library.notice-dismiss": contract(
    "关闭素材通知",
    "素材库当前显示迁移、待入库或恢复结果通知。",
    "仅隐藏本次通知，不删除素材、待处理记录或日志。",
    "页面恢复紧凑布局，相关状态仍可在列表中找到。",
    "无后端操作，不存在数据失败路径。",
    "没有可见通知时不显示。",
  ),
  "library.row": contract(
    "选择素材记录",
    "列表中存在可见记录。",
    "选中对应行并在右侧加载完整详情和允许操作。",
    "详情与当前行的路径、状态和元数据一致。",
    "记录在读取期间变化时刷新列表并提示重新选择。",
    "加载或错误状态下无记录可选。",
  ),
  "library.empty-reset": contract(
    "空状态：重置条件",
    "当前无匹配结果但素材索引可读取。",
    "恢复默认查询条件并回到第一页。",
    "若库中有素材则重新展示；没有素材则保持真正空状态。",
    "查询失败时切换为错误状态，不把错误误报为空。",
    "真正空库且条件已默认时仍可点击，但结果不变。",
  ),
  "library.empty-record": contract(
    "空状态：开始录制",
    "工作台空闲且没有未保存设置。",
    "切换到录制页，默认聚焦全屏录制入口。",
    "用户可立即开始首次录制。",
    "页面切换失败时保留空状态并写日志。",
    "正在录制或保存时禁用。",
  ),
  "library.error-diagnostics": contract(
    "查询错误：查看诊断",
    "素材索引加载或查询失败。",
    "切换到诊断页并聚焦最近错误事件。",
    "展示错误阶段和可导出的本地诊断信息。",
    "诊断页自身失败时保留原错误并提示打开日志目录。",
    "无错误上下文时仍可打开诊断页。",
  ),
  "library.error-retry": contract(
    "查询错误：重新加载",
    "没有冲突的后台素材任务。",
    "重新读取中央索引、备份和待入库记录。",
    "恢复后显示最新列表并清除错误状态。",
    "再次失败时保留上一次有效结果和错误原因。",
    "素材任务运行中禁用，避免并发写入。",
  ),
  "library.previous-page": contract(
    "上一页",
    "当前查询结果位于第 2 页或之后。",
    "保留全部查询条件，切换到前一页并更新详情选择。",
    "页码、行和总数一致，无重复或遗漏。",
    "页数据变化时将页码夹取到有效范围。",
    "第一页或无结果时禁用。",
  ),
  "library.next-page": contract(
    "下一页",
    "当前查询结果仍有下一页。",
    "保留查询条件并加载下一批结果。",
    "稳定顺序展示后续记录，页码和总数同步。",
    "加载失败时保留当前页并提示重试。",
    "末页或无结果时禁用。",
  ),
  "library.open": contract(
    "打开素材",
    "已选择且文件存在。",
    "调用默认播放器打开 MP4，素材库保持打开。",
    "对应视频开始播放。",
    "文件缺失或系统调用失败时显示原因并启用重新定位。",
    "未选择、文件缺失或待入库路径无效时禁用。",
  ),
  "library.open-folder": contract(
    "打开素材目录",
    "已选择素材且父目录存在。",
    "调用资源管理器打开目录并尽量选中视频。",
    "资源管理器定位到正确路径。",
    "目录不可访问时显示状态反馈。",
    "未选择记录时禁用。",
  ),
  "library.copy-path": contract(
    "复制素材路径",
    "已选择记录且包含路径。",
    "将完整路径写入系统剪贴板。",
    "显示“素材路径已复制”反馈。",
    "剪贴板不可用时明确提示，不修改索引。",
    "未选择或路径为空时禁用。",
  ),
  "library.relink": contract(
    "重新定位素材",
    "文件缺失、上次定位失败，或信息不完整且允许用户纠正。",
    "选择候选 MP4；先验证存在性、类型和 FFprobe 元数据，再原子提交路径与元数据。",
    "状态恢复可用，重启后新路径和元数据保持。",
    "取消不改变记录；损坏、非 MP4或保存失败时原记录不变且仍可重试。",
    "正常可用且元数据完整的记录禁用。",
  ),
  "library.remove-index": contract(
    "从素材库移除",
    "已选择正式素材记录。",
    "显示确认；确认后仅删除中央索引记录。",
    "列表、计数和分页刷新，原视频文件仍存在。",
    "取消不变；索引保存失败时记录保持并显示原因。",
    "待入库记录或未选择记录时禁用。",
  ),
  "library.recycle": contract(
    "移入 Windows 回收站",
    "已选择正式素材且实际文件存在。",
    "显示明确的文件操作确认；确认后通过系统回收站 API移动文件。",
    "文件进入回收站，素材列表和状态同步更新。",
    "取消不变；回收失败时保留文件与索引，禁止降级为永久删除。",
    "文件缺失、未选择或系统回收站不可用时禁用。",
  ),
  "settings.save-path": contract(
    "保存路径",
    "设置页已创建配置草稿。",
    "只读显示当前草稿路径；由“浏览”按钮修改。",
    "保存成功后下一次录制和 120 FPS 自检使用新目录。",
    "路径不可写时保存失败并保留草稿与窗口。",
    "录制、自检或保存进行中只读。",
  ),
  "settings.browse-save-path": contract(
    "浏览保存路径",
    "设置页空闲。",
    "打开系统目录选择器；确认后只更新草稿和脏状态。",
    "输入框显示新路径，等待用户显式保存。",
    "取消选择保持原草稿；系统对话框失败时显示反馈。",
    "录制、自检或配置保存进行中禁用。",
  ),
  "settings.quality": contract(
    "画质",
    "设置草稿可编辑。",
    "选择原生、1080p、720p或480p。",
    "保存后下一次录制按对应尺寸策略输出。",
    "无效值不写入正式配置并显示错误。",
    "录制、自检或保存进行中禁用。",
  ),
  "settings.fps": contract(
    "帧率",
    "设置草稿可编辑；120 FPS 还要求单显示器刷新率达标。",
    "选择30、60或120 FPS；首次选择120时先打开能力检测。",
    "30/60直接进入草稿；120检测通过后自动进入草稿，仍需保存。",
    "检测失败或取消时保留当前有效 FPS。",
    "录制、自检或保存进行中禁用；刷新率不足或多显示器时禁用120选项。",
  ),
  "settings.audio": contract(
    "音频源",
    "系统音频和麦克风设备状态可读取。",
    "选择无声、系统声音、麦克风或双音频并写入草稿。",
    "保存后下一次录制按所选模式初始化音频。",
    "设备初始化失败时录制启动反馈指出具体音频源。",
    "录制或配置保存进行中禁用。",
  ),
  "settings.capability-check": contract(
    "设置页：120 FPS 检测",
    "与录制页能力检测相同，且设置草稿尚未保存。",
    "打开约5秒自检对话框并禁止相关编码选项。",
    "通过后自动选择120 FPS草稿并展示有效缓存。",
    "失败时保留原FPS草稿，提供诊断和重试。",
    "录制、保存或检测进行中禁用。",
  ),
  "settings.autostart": contract(
    "开机自启",
    "设置草稿可编辑。",
    "切换草稿值；真正的注册表写入只在点击保存时执行。",
    "配置文件和注册表状态同时成功后显示保存成功。",
    "注册表失败时不写配置；配置落盘失败时回滚注册表并保持窗口。",
    "配置保存进行中禁用。",
  ),
  "settings.countdown-seconds": contract(
    "倒计时秒数",
    "录制倒计时已启用。",
    "选择1至10秒并更新草稿。",
    "保存后所有录制入口使用新倒计时。",
    "无效值不写入配置。",
    "倒计时关闭、录制或配置保存进行中禁用。",
  ),
  "settings.countdown": contract(
    "录制倒计时",
    "设置草稿可编辑。",
    "启用或关闭倒计时，并同步倒计时秒数控件可用性。",
    "保存后工作台、托盘和快捷键入口统一遵循该配置。",
    "保存失败时正式配置不变。",
    "录制或配置保存进行中禁用。",
  ),
  "settings.click-highlight": contract(
    "鼠标点击高亮",
    "设置草稿可编辑。",
    "切换桌面实时点击反馈。",
    "保存后全屏/区域录制期间可显示提示，但不写入视频帧。",
    "高亮初始化失败时记录日志，不影响视频保存。",
    "窗口录制不会启用；录制或配置保存进行中禁用。",
  ),
  "settings.shortcut-start": contract(
    "开始录制快捷键",
    "设置草稿可编辑且全局快捷键监听临时暂停。",
    "点击后捕获新组合键并进行格式与冲突校验。",
    "保存后重新注册并立即用于全屏录制。",
    "Escape取消；无效或冲突组合保留原值并提示。",
    "录制或配置保存进行中禁用。",
  ),
  "settings.shortcut-stop": contract(
    "停止录制快捷键",
    "设置草稿可编辑。",
    "捕获并校验新的停止组合键。",
    "保存后录制/暂停态可使用新快捷键停止。",
    "无效或冲突时保留原值。",
    "录制或配置保存进行中禁用。",
  ),
  "settings.shortcut-pause": contract(
    "暂停/继续快捷键",
    "设置草稿可编辑。",
    "捕获新的暂停/继续组合键并校验冲突。",
    "保存后录制状态切换统一使用该组合。",
    "无效或冲突时保留原值并反馈。",
    "录制或配置保存进行中禁用。",
  ),
  "settings.shortcut-region": contract(
    "区域录制快捷键",
    "设置草稿可编辑。",
    "捕获区域选择入口组合键。",
    "保存后空闲时可直接打开区域选择器。",
    "无效、冲突或注册失败时保留原值。",
    "录制或配置保存进行中禁用。",
  ),
  "settings.shortcut-window": contract(
    "窗口录制快捷键",
    "设置草稿可编辑。",
    "捕获窗口选择入口组合键。",
    "保存后空闲时可直接打开窗口选择器。",
    "无效、冲突或注册失败时保留原值。",
    "录制或配置保存进行中禁用。",
  ),
  "settings.discard": contract(
    "放弃设置更改",
    "设置草稿与正式配置不一致。",
    "重新从正式配置加载全部控件并清除脏状态。",
    "页面恢复到最后一次成功保存的值。",
    "重新加载失败时保留当前草稿并提示查看诊断。",
    "没有未保存更改时禁用。",
  ),
  "settings.save": contract(
    "保存设置",
    "设置草稿有效且没有录制/自检冲突。",
    "先处理可回滚系统副作用，再用同目录临时文件、fsync和原子替换保存候选配置。",
    "正式内存和文件同时更新，脏状态清除并显示成功反馈。",
    "任何阶段失败都保留窗口与输入，不发成功信号；副作用已改变时自动回滚。",
    "草稿无变化、录制/自检或另一保存进行中禁用。",
  ),
  "diagnostics.path": contract(
    "诊断目录",
    "诊断页已加载当前配置。",
    "只读显示实际日志和导出目录。",
    "与配置中有效诊断目录一致。",
    "路径解析失败时显示默认目录和错误提示。",
    "录制不影响查看；修改需使用“更改目录”。",
  ),
  "diagnostics.browse": contract(
    "更改诊断目录",
    "诊断页可编辑且无配置保存进行中。",
    "打开目录选择器，将新路径写入诊断设置草稿。",
    "显式保存后新日志和导出文件使用该目录。",
    "取消不变；目录不可写时保存失败并保留草稿。",
    "配置保存进行中禁用。",
  ),
  "diagnostics.copy": contract(
    "复制诊断信息",
    "诊断服务可读取应用、录制、FFmpeg、音频和最近日志摘要。",
    "在本地生成诊断文本并写入剪贴板。",
    "显示“诊断信息已复制”，不创建新文件。",
    "剪贴板不可用时提示改用导出。",
    "诊断构建进行中短暂禁用。",
  ),
  "diagnostics.open-dir": contract(
    "打开日志目录",
    "有效诊断目录可解析。",
    "创建缺失目录并调用资源管理器打开。",
    "资源管理器显示实际日志目录。",
    "系统调用失败时显示错误，不修改配置。",
    "路径无效且无法创建时禁用。",
  ),
  "diagnostics.export": contract(
    "导出诊断文件",
    "诊断目录可写。",
    "生成UTF-8本地诊断快照，包含最近录制和120 FPS检测摘要。",
    "显示导出文件路径，文件可直接阅读。",
    "写入失败时说明目录权限或磁盘问题。",
    "已有导出任务进行中或目录不可写时禁用。",
  ),
  "diagnostics.capability-check": contract(
    "诊断页：重新检测 120 FPS",
    "与其他能力检测入口共用同一前置条件。",
    "启动真实约5秒自检并在诊断页展示阶段结果。",
    "通过后更新缓存、时间、环境、平均和最低 FPS。",
    "失败时保留失败阶段与原因，允许再次检测。",
    "录制、保存或检测进行中禁用。",
  ),
  "diagnostics.refresh-events": contract(
    "刷新诊断事件",
    "诊断目录可读取。",
    "重新加载最近有限条事件摘要。",
    "列表显示最新录制、保存、入库和检测阶段。",
    "日志不可读时保留现有列表并显示原因。",
    "读取进行中短暂禁用。",
  ),
  "floating.area-start": contract(
    "区域选择：开始录制",
    "选区宽高均至少100像素，前置录制检查已通过。",
    "关闭遮罩，恢复普通光标并将选区坐标交给录制工作流。",
    "进入倒计时或浮动录制工具栏。",
    "录制启动失败时关闭遮罩、恢复工作台并提示原因。",
    "选区过小或录制状态不再空闲时禁用。",
  ),
  "floating.area-cancel": contract(
    "区域选择：取消",
    "区域选择器显示中。",
    "关闭遮罩和确认操作，不创建录制会话。",
    "工作台来源恢复工作台；托盘/快捷键来源回到空闲。",
    "无后端写入，不存在数据失败路径。",
    "选择器关闭后不显示；Esc和右键行为相同。",
  ),
  "floating.window-close": contract(
    "关闭窗口选择器",
    "窗口选择器已打开。",
    "按取消语义关闭选择器。",
    "不改变录制状态；工作台来源恢复工作台。",
    "无后端失败路径。",
    "选择器关闭后不可用。",
  ),
  "floating.window-row": contract(
    "选择目标窗口",
    "枚举结果中窗口仍有效。",
    "将该行设为当前目标；双击时可等同确认选择。",
    "选中态明确，确认按钮可用。",
    "窗口已关闭时刷新列表并提示目标失效。",
    "最小化但可恢复的窗口可选；QuickRec自身窗口和不可见窗口不展示。",
  ),
  "floating.window-refresh": contract(
    "刷新窗口列表",
    "选择器已打开。",
    "重新枚举当前可见顶层窗口，标注最小化状态。",
    "列表更新并清理已失效选择。",
    "单个窗口读取失败时跳过，不关闭选择器。",
    "枚举进行中短暂禁用。",
  ),
  "floating.window-cancel": contract(
    "窗口选择：取消",
    "窗口选择器显示中。",
    "关闭选择器，不创建录制会话。",
    "恢复此前来源界面。",
    "无数据失败路径。",
    "选择器关闭后不可用。",
  ),
  "floating.window-select": contract(
    "窗口选择：确认",
    "列表有一个仍有效的当前项。",
    "恢复最小化目标、置前并短暂显示绿色边框，然后启动窗口捕获。",
    "进入倒计时或录制工具栏，索引模式记为window。",
    "目标失效或启动失败时恢复工作台并提示。",
    "未选中、窗口失效或应用非空闲时禁用。",
  ),
  "floating.countdown-cancel": contract(
    "倒计时：取消",
    "倒计时尚未结束。",
    "停止倒计时并取消本次录制启动。",
    "工作台来源恢复工作台，其他来源回到托盘空闲。",
    "不创建输出或索引。",
    "倒计时结束后不可用；Esc行为相同。",
  ),
  "floating.pause": contract(
    "暂停录制",
    "录制状态为RECORDING。",
    "暂停向当前编码会话写入新画面，工具栏和托盘切换为暂停态。",
    "计时停止增长并显示“继续”。",
    "状态无效时忽略并记录调试信息。",
    "非录制态、保存中或取消中禁用。",
  ),
  "floating.resume": contract(
    "继续录制",
    "录制状态为PAUSED。",
    "恢复当前会话画面写入，工具栏和托盘返回录制态。",
    "计时继续增长，输出仍为同一文件。",
    "目标窗口仍不可用时保持暂停并提示。",
    "非暂停态或保存中禁用。",
  ),
  "floating.stop": contract(
    "停止录制",
    "录制状态为RECORDING或PAUSED。",
    "停止捕获并进入保存状态，等待编码和音频混合结束。",
    "生成可播放MP4，随后独立尝试素材入库并显示结果。",
    "保存失败时显示明确错误；索引失败不能改写视频保存成功。",
    "空闲、保存或取消中禁用。",
  ),
  "floating.cancel": contract(
    "取消录制",
    "倒计时、录制或暂停中且尚未进入不可逆保存阶段。",
    "停止本次会话并清理临时输出、点击高亮和窗口边框。",
    "通知“录制已取消”，不产生正式视频和素材记录。",
    "清理失败写诊断日志，但应用仍恢复空闲。",
    "保存阶段禁用，避免破坏正在完成的输出。",
  ),
  "floating.saving-disabled": contract(
    "保存中状态",
    "录制已经停止且编码/音频混合尚未结束。",
    "仅显示进度，不接受用户命令。",
    "完成后切换为保存结果或失败反馈。",
    "超时或编码失败时进入明确错误状态并保留诊断。",
    "始终禁用，防止重复停止、取消或启动录制。",
  ),
  "floating.result-open": contract(
    "结果条：打开视频",
    "视频保存成功且文件存在。",
    "调用默认播放器打开新视频，并重置结果条自动关闭计时。",
    "播放器打开目标MP4。",
    "打开失败时结果条保持可用并提示打开目录。",
    "输出路径为空或文件缺失时禁用。",
  ),
  "floating.result-folder": contract(
    "结果条：打开目录",
    "结果条包含输出路径。",
    "打开资源管理器并定位输出文件。",
    "用户可直接看到已保存视频。",
    "文件缺失时降级打开父目录；目录失败时提示。",
    "无输出路径时禁用。",
  ),
  "floating.result-library": contract(
    "结果条：素材库",
    "视频已成功加入中央索引。",
    "打开同一个工作台并切换到素材库页，定位最新记录。",
    "结果条关闭，素材详情显示新录制。",
    "素材库加载失败时保留视频成功事实并显示索引错误。",
    "索引失败时该按钮替换为“重试入库”。",
  ),
  "floating.result-close": contract(
    "关闭结果条",
    "保存结果条可见。",
    "停止自动关闭计时并隐藏结果条。",
    "视频和素材索引保持不变。",
    "无后端操作，不存在数据失败路径。",
    "结果条不可见时不可用。",
  ),
  "floating.retry-index": contract(
    "结果条：重试入库",
    "视频已保存但素材索引写入失败，短时待入库上下文仍存在。",
    "再次执行元数据解析和中央索引事务写入。",
    "成功后按钮改为“素材库”，只生成一条正式记录。",
    "失败时保持恢复上下文、文件和明确反馈。",
    "正在重试或输出文件已丢失时禁用；持久恢复入口延后后续版本。",
  ),
  "modal.cancel": contract(
    "对话框：取消",
    "确认、自检或未保存设置对话框已显示。",
    "关闭对话框并保持触发前状态。",
    "不写配置、不改索引、不启动录制。",
    "无后端失败路径。",
    "不可取消的保存提交阶段不提供。",
  ),
  "modal.capability-start": contract(
    "自检：开始检测",
    "单显示器刷新率达标、未录制、目录可写、FFmpeg可用。",
    "锁定相关控件并执行约5秒真实捕获与编码自检。",
    "门禁通过后写能力缓存并更新设置草稿。",
    "失败显示具体阶段和诊断入口，不保存120 FPS。",
    "检测进行中禁用；条件不足时不显示。",
  ),
  "modal.save": contract(
    "未保存更改：保存",
    "离开设置页时草稿有效且存在更改。",
    "执行与设置页“保存更改”相同的事务保存；成功后继续原导航。",
    "配置成功后进入目标页面。",
    "失败时停留设置页和对话框上下文，不丢输入。",
    "保存进行中禁用。",
  ),
  "modal.discard": contract(
    "未保存更改：放弃",
    "离开设置页时存在未保存更改。",
    "丢弃草稿、恢复正式配置，再继续原导航。",
    "目标页面打开，正式配置保持不变。",
    "正式配置重新读取失败时不离开设置页。",
    "没有脏状态时不显示。",
  ),
  "modal.rebuild-confirm": contract(
    "确认重建目录",
    "目录扫描预览完成且至少有可提交结果。",
    "提交有效视频、重复和失败统计到中央索引事务。",
    "索引更新并刷新素材库。",
    "提交失败时原索引保持不变并显示原因。",
    "任务取消或仍在扫描时禁用。",
  ),
  "modal.remove-confirm": contract(
    "确认移除素材索引",
    "选择了正式素材。",
    "只移除索引记录，不操作实际视频。",
    "列表与计数更新，原文件保留。",
    "保存索引失败时记录仍存在。",
    "未选择或待入库记录时不显示。",
  ),
  "modal.recycle-confirm": contract(
    "确认移入回收站",
    "选择了存在的正式素材文件。",
    "通过Windows回收站处理实际文件，并更新索引。",
    "文件可从回收站恢复，列表同步刷新。",
    "回收失败时保留文件和索引，不永久删除。",
    "文件缺失或系统回收站不可用时禁用。",
  ),
  "modal.quick-60": contract(
    "快速校验失败：改用60 FPS",
    "用户主动开始120 FPS录制，但快速校验失败。",
    "仅本次使用60 FPS，不修改保存的120 FPS配置。",
    "录制按60 FPS正常开始，并显示本次降级说明。",
    "60 FPS前置检查仍失败时不启动并显示原因。",
    "保存目录、FFmpeg或磁盘硬条件不满足时禁用。",
  ),
  "modal.redetect": contract(
    "快速校验失败：重新检测",
    "120 FPS缓存失效或环境发生变化。",
    "返回约5秒能力检测流程。",
    "通过后继续120 FPS启动流程。",
    "失败时保留原有效配置并提供60 FPS或取消。",
    "录制/保存进行中禁用。",
  ),
};

const pageMeta = {
  record: ["录制", "选择模式并开始一次新的屏幕录制。"],
  library: ["素材库", "跨保存路径查询、整理和恢复本地录制素材。"],
  settings: ["设置", "显式保存录制参数、行为和快捷键。"],
  diagnostics: ["诊断", "复制、打开或导出本地排查信息。"],
};

const workbenchBody = document.querySelector(".workbench-body");
const pageTitle = document.getElementById("pageTitle");
const pageSubtitle = document.getElementById("pageSubtitle");
const prototypeState = document.getElementById("prototypeState");
const floatingState = document.getElementById("floatingState");
const floatingStage = document.getElementById("floatingStage");
const toolbarTransitionShell = document.getElementById("toolbarTransitionShell");
const playFloatingDemoButton = document.getElementById("playFloatingDemo");
const modalLayer = document.getElementById("modalLayer");
const flowLayer = document.getElementById("flowLayer");
const inspector = document.getElementById("contractInspector");
const urlParams = new URLSearchParams(window.location.search);
let currentPage = "record";
let settingsDirty = true;
let pendingNavigation = null;
let capabilityPassed = false;
let contractCounter = 0;
let floatingDemoTimers = [];
let floatingDemoRunning = false;

if (urlParams.get("embed") === "1") {
  document.body.classList.add("embed");
}

function selectContract(element) {
  const spec = contracts[element.dataset.contract];
  if (!spec) {
    console.error("缺少交互契约", element.dataset.contract, element);
    return;
  }
  document.querySelectorAll(".contract-selected").forEach((node) => node.classList.remove("contract-selected"));
  element.classList.add("contract-selected");
  document.getElementById("contractTitle").textContent = spec.title;
  document.getElementById("contractTrigger").textContent = spec.trigger;
  document.getElementById("contractAction").textContent = spec.action;
  document.getElementById("contractSuccess").textContent = spec.success;
  document.getElementById("contractFailure").textContent = spec.failure;
  document.getElementById("contractDisabled").textContent = spec.disabled;
}

function registerContractElement(element) {
  if (element.dataset.contractRegistered === "true") {
    return;
  }
  const key = element.dataset.contract;
  if (!contracts[key]) {
    throw new Error(`原型控件缺少交互契约：${key}`);
  }
  contractCounter += 1;
  element.dataset.contractIndex = String(contractCounter);
  element.dataset.contractRegistered = "true";
  element.addEventListener("click", (event) => {
    selectContract(element);
    if (workbenchBody.classList.contains("show-contracts")) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  });
  element.addEventListener("focus", () => selectContract(element));
}

document.querySelectorAll("[data-contract]").forEach(registerContractElement);

function updateDirtyState(dirty) {
  settingsDirty = dirty;
  document.getElementById("dirtyIndicator").hidden = !dirty;
  document.getElementById("discardSettings").disabled = !dirty;
  document.getElementById("saveSettings").disabled = !dirty;
}

function routeTo(page, options = {}) {
  if (
    currentPage === "settings"
    && page !== "settings"
    && settingsDirty
    && !options.force
  ) {
    pendingNavigation = page;
    showUnsavedDialog();
    return;
  }

  currentPage = page;
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.page === page);
  });
  document.querySelectorAll("[data-page-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.pagePanel === page);
  });
  pageTitle.textContent = pageMeta[page][0];
  pageSubtitle.textContent = pageMeta[page][1];
}

document.querySelectorAll("[data-page]").forEach((button) => {
  button.addEventListener("click", () => routeTo(button.dataset.page));
});

document.querySelectorAll("[data-page-target]").forEach((button) => {
  button.addEventListener("click", () => routeTo(button.dataset.pageTarget));
});

function showToast(title, detail, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast is-${type}`;
  const icon = type === "success" ? "i-check" : type === "warning" ? "i-alert" : "i-info";
  toast.innerHTML = `
    <svg><use href="#${icon}"></use></svg>
    <div class="toast-copy"><strong>${title}</strong><span>${detail}</span></div>
    <button type="button" aria-label="关闭通知">×</button>
  `;
  toast.querySelector("button").addEventListener("click", () => toast.remove());
  document.getElementById("toastStack").appendChild(toast);
  window.setTimeout(() => toast.remove(), 4200);
}

function closeModal() {
  modalLayer.hidden = true;
  document.getElementById("modalActions").replaceChildren();
}

function showModal({ title, text, detail = "", icon = "info", actions }) {
  document.getElementById("modalTitle").textContent = title;
  document.getElementById("modalText").textContent = text;
  const detailNode = document.getElementById("modalDetail");
  detailNode.textContent = detail;
  detailNode.hidden = !detail;
  const modalIcon = document.getElementById("modalIcon");
  modalIcon.className = `modal-icon${icon === "warning" ? " is-warning" : icon === "danger" ? " is-danger" : ""}`;
  modalIcon.innerHTML = `<svg><use href="#${icon === "warning" || icon === "danger" ? "i-alert" : "i-info"}"></use></svg>`;
  const actionHost = document.getElementById("modalActions");
  actionHost.replaceChildren();
  actions.forEach((action) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `button ${action.kind || "button-secondary"}`;
    button.textContent = action.label;
    button.dataset.contract = action.contract;
    registerContractElement(button);
    button.addEventListener("click", action.onClick);
    actionHost.appendChild(button);
  });
  modalLayer.hidden = false;
}

function showUnsavedDialog() {
  showModal({
    title: "保存设置更改？",
    text: "当前页面包含尚未保存的更改。选择保存后继续、放弃更改，或取消并留在设置页。",
    icon: "warning",
    actions: [
      { label: "取消", contract: "modal.cancel", onClick: () => { pendingNavigation = null; closeModal(); } },
      {
        label: "放弃",
        contract: "modal.discard",
        onClick: () => {
          updateDirtyState(false);
          const target = pendingNavigation;
          pendingNavigation = null;
          closeModal();
          routeTo(target, { force: true });
        },
      },
      {
        label: "保存并继续",
        kind: "button-primary",
        contract: "modal.save",
        onClick: () => {
          updateDirtyState(false);
          const target = pendingNavigation;
          pendingNavigation = null;
          closeModal();
          showToast("设置已保存", "新配置将在下一次录制中生效。", "success");
          routeTo(target, { force: true });
        },
      },
    ],
  });
}

function showCapabilityDialog() {
  showModal({
    title: "检测 120 FPS 录制能力",
    text: "QuickRec 将在当前保存目录执行约 5 秒真实捕获与编码。检测期间不能开始录制或修改相关编码设置。",
    detail: "门禁：平均 ≥114 FPS；任意连续 1 秒 ≥108 FPS；编码队列无持续堆积；输出可解析。",
    actions: [
      { label: "取消", contract: "modal.cancel", onClick: closeModal },
      {
        label: "开始检测",
        kind: "button-primary",
        contract: "modal.capability-start",
        onClick: () => {
          closeModal();
          showToast("正在检测 120 FPS", "阶段 1/3：初始化真实桌面捕获。");
          window.setTimeout(() => {
            if (prototypeState.value === "error") {
              showToast("检测未通过", "连续 1 秒最低帧率为 104 FPS，请查看诊断后重试。", "warning");
              return;
            }
            capabilityPassed = true;
            document.querySelectorAll("#capabilityBadge").forEach((node) => {
              node.className = "badge badge-success";
              node.textContent = "检测通过";
            });
            document.getElementById("capabilityCacheText").textContent = "当前环境有效";
            document.getElementById("fpsSelect").value = "120 FPS（需要检测）";
            updateDirtyState(true);
            showToast("120 FPS 检测通过", "平均 118.6 FPS，最低 112.4 FPS；保存设置后生效。", "success");
          }, 1050);
        },
      },
    ],
  });
}

["runCapabilityCheck", "settingsCapabilityCheck", "diagnosticCapabilityCheck"].forEach((id) => {
  document.getElementById(id).addEventListener("click", showCapabilityDialog);
});

document.getElementById("fpsSelect").addEventListener("change", (event) => {
  updateDirtyState(true);
  if (event.target.value.startsWith("120") && !capabilityPassed) {
    event.target.value = "60 FPS";
    showCapabilityDialog();
  }
});

document.querySelectorAll('[data-page-panel="settings"] input, [data-page-panel="settings"] select').forEach((control) => {
  control.addEventListener("change", () => updateDirtyState(true));
});

document.getElementById("saveSettings").addEventListener("click", () => {
  if (prototypeState.value === "error") {
    showToast("设置保存失败", "正式配置保持不变，请检查配置目录权限后重试。", "warning");
    return;
  }
  updateDirtyState(false);
  showToast("设置已保存", "配置文件与系统副作用已成功提交。", "success");
});

document.getElementById("discardSettings").addEventListener("click", () => {
  updateDirtyState(false);
  document.getElementById("fpsSelect").value = "60 FPS";
  showToast("已放弃更改", "页面已恢复到最后一次成功保存的配置。");
});

const toolbarWidths = {
  countdown: 330,
  toolbar: 500,
  paused: 500,
  saving: 430,
  result: 640,
  "result-failed": 690,
};

function toolbarWidthFor(kind) {
  const viewportLimit = Math.max(280, window.innerWidth - 32);
  return Math.min(toolbarWidths[kind], viewportLimit);
}

function showFloating(kind) {
  const toolbarKind = Object.hasOwn(toolbarWidths, kind);

  if (!kind || kind === "none") {
    floatingStage.hidden = true;
    toolbarTransitionShell.hidden = true;
    document.querySelectorAll("[data-floating-view]").forEach((view) => view.classList.remove("is-visible"));
    floatingState.value = "none";
    return;
  }

  floatingStage.hidden = false;
  toolbarTransitionShell.hidden = !toolbarKind;

  if (toolbarKind) {
    toolbarTransitionShell.style.width = `${toolbarWidthFor(kind)}px`;
  }

  document.querySelectorAll("[data-floating-view]").forEach((view) => {
    view.classList.toggle("is-visible", view.dataset.floatingView === kind);
  });
  floatingState.value = kind;
}

function stopFloatingDemo() {
  floatingDemoTimers.forEach((timer) => window.clearTimeout(timer));
  floatingDemoTimers = [];
  floatingDemoRunning = false;
  playFloatingDemoButton.textContent = "播放浮动动画";
  playFloatingDemoButton.setAttribute("aria-pressed", "false");
}

function playFloatingDemo() {
  stopFloatingDemo();
  floatingDemoRunning = true;
  playFloatingDemoButton.textContent = "停止浮动动画";
  playFloatingDemoButton.setAttribute("aria-pressed", "true");

  const sequence = [
    { kind: "countdown", duration: 950 },
    { kind: "toolbar", duration: 1500 },
    { kind: "paused", duration: 1100 },
    { kind: "toolbar", duration: 900 },
    { kind: "saving", duration: 1200 },
    { kind: "result", duration: 1800 },
    { kind: "result-failed", duration: 1800 },
  ];

  let elapsed = 0;
  sequence.forEach(({ kind, duration }) => {
    const timer = window.setTimeout(() => showFloating(kind), elapsed);
    floatingDemoTimers.push(timer);
    elapsed += duration;
  });

  floatingDemoTimers.push(
    window.setTimeout(() => {
      floatingDemoRunning = false;
      floatingDemoTimers = [];
      playFloatingDemoButton.textContent = "再次播放浮动动画";
      playFloatingDemoButton.setAttribute("aria-pressed", "false");
    }, elapsed),
  );
}

floatingState.addEventListener("change", () => {
  stopFloatingDemo();
  showFloating(floatingState.value);
});

playFloatingDemoButton.addEventListener("click", () => {
  if (floatingDemoRunning) {
    stopFloatingDemo();
    return;
  }
  playFloatingDemo();
});

window.addEventListener("resize", () => {
  if (Object.hasOwn(toolbarWidths, floatingState.value)) {
    toolbarTransitionShell.style.width = `${toolbarWidthFor(floatingState.value)}px`;
  }
});

document.getElementById("quickRecordButton").addEventListener("click", () => showFloating("countdown"));
document.querySelector('[data-contract="record.fullscreen"]').addEventListener("click", () => showFloating("countdown"));
document.querySelector('[data-contract="record.region"]').addEventListener("click", () => showFloating("area"));
document.querySelector('[data-contract="record.window"]').addEventListener("click", () => showFloating("window"));

document.querySelector('[data-contract="floating.area-start"]').addEventListener("click", () => showFloating("countdown"));
document.querySelector('[data-contract="floating.area-cancel"]').addEventListener("click", () => {
  showFloating("none");
  showToast("已取消区域选择", "没有创建录制文件。");
});
document.querySelectorAll('[data-contract="floating.window-cancel"], [data-contract="floating.window-close"]').forEach((button) => {
  button.addEventListener("click", () => showFloating("none"));
});
document.querySelector('[data-contract="floating.window-select"]').addEventListener("click", () => showFloating("countdown"));
document.querySelector('[data-contract="floating.window-refresh"]').addEventListener("click", () => {
  showToast("窗口列表已刷新", "发现 3 个可录制窗口。");
});
document.querySelectorAll(".window-list-item").forEach((row) => {
  row.addEventListener("click", () => {
    document.querySelectorAll(".window-list-item").forEach((item) => item.classList.remove("is-selected"));
    row.classList.add("is-selected");
    const selectedTitle = row.querySelector("strong").textContent.trim();
    document.querySelector(".window-selection-hint").textContent = `已选择：${selectedTitle}`;
  });
});
document.querySelector('[data-contract="floating.countdown-cancel"]').addEventListener("click", () => showFloating("none"));
document.querySelector('[data-contract="floating.pause"]').addEventListener("click", () => showFloating("paused"));
document.querySelector('[data-contract="floating.resume"]').addEventListener("click", () => showFloating("toolbar"));
document.querySelectorAll('[data-contract="floating.stop"]').forEach((button) => {
  button.addEventListener("click", () => {
    showFloating("saving");
    window.setTimeout(() => showFloating("result"), 850);
  });
});
document.querySelectorAll('[data-contract="floating.cancel"]').forEach((button) => {
  button.addEventListener("click", () => {
    showFloating("none");
    showToast("录制已取消", "临时会话已清理，没有生成正式视频。");
  });
});
document.querySelector('[data-contract="floating.result-library"]').addEventListener("click", () => {
  showFloating("none");
  routeTo("library", { force: true });
});
document.querySelector('[data-contract="floating.retry-index"]').addEventListener("click", () => {
  showFloating("result");
  showToast("素材入库成功", "已创建 1 条中央索引记录。", "success");
});
document.querySelectorAll('[data-contract="floating.result-close"]').forEach((button) => {
  button.addEventListener("click", () => showFloating("none"));
});
document.querySelectorAll('[data-contract="floating.result-open"], [data-contract="floating.result-folder"]').forEach((button) => {
  button.addEventListener("click", () => showToast("系统操作已触发", "实际应用将调用默认播放器或资源管理器。"));
});

function setLibraryDisplay(mode) {
  const table = document.getElementById("materialTableWrap");
  const empty = document.getElementById("libraryEmptyState");
  const error = document.getElementById("libraryErrorState");
  const notice = document.getElementById("libraryNotice");
  const relink = document.getElementById("relinkButton");
  const status = document.getElementById("detailStatus");

  table.hidden = mode === "empty" || mode === "error";
  empty.hidden = mode !== "empty";
  error.hidden = mode !== "error";
  notice.hidden = mode !== "index-failed";
  relink.disabled = mode !== "missing";
  status.className = `badge ${mode === "missing" ? "badge-danger" : "badge-success"}`;
  status.textContent = mode === "missing" ? "文件缺失" : "可用";
}

function applyPrototypeState(state) {
  const panel = document.getElementById("recordStatusPanel");
  const title = document.getElementById("recordStatusTitle");
  const text = document.getElementById("recordStatusText");
  panel.className = "record-status-panel";
  document.querySelectorAll(".mode-action, #quickRecordButton").forEach((button) => { button.disabled = false; });
  setLibraryDisplay("default");

  if (state === "recording") {
    routeTo("record", { force: true });
    panel.classList.add("is-recording");
    title.textContent = "正在录制";
    text.textContent = "00:42 · 全屏录制 · 1920×1080 · 60 FPS";
    document.querySelectorAll(".mode-action, #quickRecordButton").forEach((button) => { button.disabled = true; });
    showFloating("toolbar");
  } else if (state === "success") {
    routeTo("record", { force: true });
    panel.classList.add("is-success");
    title.textContent = "录制已保存并加入素材库";
    text.textContent = "QuickRec_20260723_214512.mp4 · 84.6 MB";
  } else if (state === "index-failed") {
    routeTo("record", { force: true });
    panel.classList.add("is-warning");
    title.textContent = "视频已保存，素材入库失败";
    text.textContent = "文件可正常播放；可在结果条重试或打开诊断页。";
    setLibraryDisplay("index-failed");
  } else if (state === "empty" || state === "error" || state === "missing") {
    routeTo("library", { force: true });
    setLibraryDisplay(state);
  } else {
    title.textContent = "准备就绪";
    text.textContent = "1080p · 60 FPS · 系统声音 + 麦克风";
  }
}

prototypeState.addEventListener("change", () => applyPrototypeState(prototypeState.value));

document.getElementById("materialSearch").addEventListener("input", (event) => {
  const hasQuery = event.target.value.trim().length > 0;
  const noMatch = event.target.value.includes("不存在");
  document.getElementById("materialResultCount").textContent = noMatch ? "匹配 0 / 共 3 条" : hasQuery ? "匹配 1 / 共 3 条" : "匹配 3 / 共 3 条";
  setLibraryDisplay(noMatch ? "empty" : "default");
});

document.getElementById("resetFilters").addEventListener("click", () => {
  document.getElementById("materialSearch").value = "";
  document.getElementById("materialResultCount").textContent = "匹配 3 / 共 3 条";
  setLibraryDisplay("default");
});
document.querySelector('[data-contract="library.empty-reset"]').addEventListener("click", () => {
  document.getElementById("resetFilters").click();
});
document.querySelector('[data-contract="library.error-retry"]').addEventListener("click", () => {
  setLibraryDisplay("default");
  showToast("素材索引已恢复", "已从有效备份读取 3 条记录。", "success");
});
document.querySelector('[data-contract="library.notice-dismiss"]').addEventListener("click", () => {
  document.getElementById("libraryNotice").hidden = true;
});
document.querySelectorAll("#materialRows tr").forEach((row) => {
  row.addEventListener("click", () => {
    document.querySelectorAll("#materialRows tr").forEach((item) => item.classList.remove("is-selected"));
    row.classList.add("is-selected");
    const missing = row.textContent.includes("文件缺失");
    setLibraryDisplay(missing ? "missing" : "default");
  });
});

document.getElementById("rebuildDirectory").addEventListener("click", () => {
  showModal({
    title: "确认重建目录",
    text: "扫描完成：成功 18 条、已存在 4 条、跳过 2 条、失败 1 条。确认后写入中央素材索引。",
    icon: "warning",
    actions: [
      { label: "取消", contract: "modal.cancel", onClick: closeModal },
      {
        label: "确认重建",
        kind: "button-primary",
        contract: "modal.rebuild-confirm",
        onClick: () => {
          closeModal();
          showToast("目录重建完成", "新增 18 条素材，损坏文件已跳过。", "success");
        },
      },
    ],
  });
});

document.querySelector('[data-contract="library.remove-index"]').addEventListener("click", () => {
  showModal({
    title: "从素材库移除？",
    text: "这只会删除素材索引记录，实际视频文件仍保留在原目录。",
    icon: "warning",
    actions: [
      { label: "取消", contract: "modal.cancel", onClick: closeModal },
      {
        label: "确认移除",
        kind: "button-primary",
        contract: "modal.remove-confirm",
        onClick: () => {
          closeModal();
          showToast("已从素材库移除", "视频文件未被删除。", "success");
        },
      },
    ],
  });
});

document.querySelector('[data-contract="library.recycle"]').addEventListener("click", () => {
  showModal({
    title: "移入 Windows 回收站？",
    text: "该操作会处理实际视频文件，但仍可从 Windows 回收站恢复。不会清空回收站。",
    icon: "danger",
    actions: [
      { label: "取消", contract: "modal.cancel", onClick: closeModal },
      {
        label: "移入回收站",
        kind: "button-primary",
        contract: "modal.recycle-confirm",
        onClick: () => {
          closeModal();
          showToast("视频已移入回收站", "素材列表和索引状态已同步。", "success");
        },
      },
    ],
  });
});

document.querySelector('[data-contract="library.relink"]').addEventListener("click", () => {
  showToast("等待选择新文件", "实际应用会先用 FFprobe 验证候选，再提交路径。");
});
document.querySelectorAll('[data-contract="library.open"], [data-contract="library.open-folder"], [data-contract="library.copy-path"]').forEach((button) => {
  button.addEventListener("click", () => showToast("操作成功", "对应系统操作已触发。", "success"));
});

document.querySelectorAll('[data-contract="diagnostics.copy"], [data-contract="diagnostics.open-dir"], [data-contract="diagnostics.export"], [data-contract="diagnostics.refresh-events"]').forEach((button) => {
  button.addEventListener("click", () => {
    const labels = {
      "diagnostics.copy": ["诊断信息已复制", "本地诊断摘要已写入剪贴板。"],
      "diagnostics.open-dir": ["日志目录已打开", "资源管理器已定位到 QuickRecDiagnostics。"],
      "diagnostics.export": ["诊断文件已导出", "已生成 UTF-8 本地诊断快照。"],
      "diagnostics.refresh-events": ["诊断事件已刷新", "最近事件列表已更新。"],
    };
    const copy = labels[button.dataset.contract];
    showToast(copy[0], copy[1], "success");
  });
});

document.querySelector('[data-contract="top.more"]').addEventListener("click", () => {
  showModal({
    title: "更多工作台操作",
    text: "工作台关闭或隐藏后，QuickRec 仍在系统托盘运行。只有托盘“退出 QuickRec”会结束应用。",
    actions: [
      { label: "取消", contract: "modal.cancel", onClick: closeModal },
      {
        label: "打开保存目录",
        contract: "record.open-folder",
        onClick: () => {
          closeModal();
          showToast("保存目录已打开", "资源管理器已定位到 E:\\Videos\\QuickRec。");
        },
      },
    ],
  });
});

document.getElementById("toggleAnnotations").addEventListener("click", (event) => {
  workbenchBody.classList.toggle("show-contracts");
  event.currentTarget.classList.toggle("is-active", workbenchBody.classList.contains("show-contracts"));
  if (workbenchBody.classList.contains("show-contracts")) {
    const first = document.querySelector('[data-contract="record.fullscreen"]');
    selectContract(first);
  }
});
document.getElementById("closeInspector").addEventListener("click", () => {
  workbenchBody.classList.remove("show-contracts");
  document.getElementById("toggleAnnotations").classList.remove("is-active");
});

document.getElementById("showFlow").addEventListener("click", () => {
  flowLayer.hidden = false;
});
document.getElementById("closeFlow").addEventListener("click", () => {
  flowLayer.hidden = true;
});

modalLayer.addEventListener("click", (event) => {
  if (event.target === modalLayer) {
    closeModal();
  }
});
flowLayer.addEventListener("click", (event) => {
  if (event.target === flowLayer) {
    flowLayer.hidden = true;
  }
});

const initialState = Array.from(prototypeState.options).some(
  (option) => option.value === urlParams.get("state"),
)
  ? urlParams.get("state")
  : "default";
const initialPage = Object.hasOwn(pageMeta, urlParams.get("page"))
  ? urlParams.get("page")
  : "record";
const initialFloating = Array.from(floatingState.options).some(
  (option) => option.value === urlParams.get("floating"),
)
  ? urlParams.get("floating")
  : "none";

prototypeState.value = initialState;
applyPrototypeState(initialState);
routeTo(initialPage, { force: true });
showFloating(initialFloating);
updateDirtyState(initialPage === "settings");
