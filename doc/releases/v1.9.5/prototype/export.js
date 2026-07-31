"use strict";

const exportContracts = {
  "nav.exports": contract(
    "导航：导出",
    "工作台已打开，且设置页没有未处理的更改。",
    "切换到导出页，读取本地持久队列、当前工作线程和最近任务。",
    "展示任务状态、进度、不可变计划、尝试记录和恢复操作。",
    "队列文件损坏时进入恢复状态；未知版本只读展示，不启动任务。",
    "设置有未保存更改时先要求决策；队列恢复未完成时禁用新建任务。",
    "取消页面切换时保留当前页面和队列状态。",
    "导航只读取队列，不修改任务、项目或输出文件。",
  ),
  "timeline.export": contract(
    "从剪辑工作台导出",
    "项目已成功保存、timeline schema v2 可读、当前没有待解决的外部冲突。",
    "打开导出配置，并从当前已保存项目生成候选 ExportPlan。",
    "用户完成预检后将不可变计划加入持久队列；剪辑工作台继续可用。",
    "项目只读、时间线损坏或保存失败时阻止创建并提供恢复入口。",
    "项目未保存、未知时间线版本、已有保存冲突或未完成任务达到 20 个时禁用。",
    "关闭配置时不创建任务，也不修改项目。",
    "读取项目与素材指纹；只有最终加入队列时写队列文件。",
  ),
  "exports.open-folder": contract(
    "打开默认导出目录",
    "默认导出目录已配置。",
    "调用 Windows 资源管理器打开目录；目录尚不存在时先安全创建。",
    "资源管理器定位到正确目录，工作台保持可用。",
    "目录不可创建或系统调用失败时显示错误并保留队列。",
    "队列未知版本不影响打开目录；路径为空时禁用。",
  ),
  "exports.clean-history": contract(
    "清理已完成历史",
    "队列中存在成功、失败或已取消的终态任务。",
    "显示确认范围，只删除超过保留期的终态任务记录与已知临时文件。",
    "列表和计数刷新；正式输出、项目与中央素材记录不受影响。",
    "部分清理失败时保留失败记录并给出逐项结果。",
    "运行、排队、校验、验证或提交中的任务永不参与清理。",
    "取消时不删除任何记录或文件。",
    "只修改导出队列历史和任务专属临时目录。",
  ),
  "exports.new": contract(
    "新建导出任务",
    "至少存在一个已保存且可导出的项目；未完成任务少于 20 个。",
    "打开导出配置；默认使用当前项目和上次有效输出目录。",
    "进入输出设置，尚不冻结计划或创建正式文件。",
    "项目校验失败时显示原因并提供打开项目或诊断入口。",
    "队列只读、恢复中、未完成任务达到上限或正在录制时禁用。",
    "关闭配置不写队列、不创建临时文件。",
    "只有确认加入队列后才写入持久任务。",
  ),
  "exports.health-action": contract(
    "处理队列健康状态",
    "检测到队列损坏、未知版本、恢复结果或任务上限。",
    "打开与当前状态对应的恢复报告或只读说明。",
    "用户可确认自动备份、恢复结果和仍需手动处理的任务。",
    "恢复失败时保留原队列副本并禁止启动任务。",
    "队列健康时隐藏；未知版本不提供覆盖写入。",
  ),
  "exports.refresh": contract(
    "刷新导出队列",
    "导出页已打开。",
    "重新读取队列文件和当前执行器快照，不中断运行任务。",
    "任务状态、进度、计数和详情同步更新。",
    "读取失败时保留上一次有效视图并显示健康提示。",
    "原子提交的极短窗口内可暂时禁用。",
  ),
  "exports.filter-all": contract(
    "筛选：全部任务",
    "队列已加载。",
    "显示所有可读任务并保持稳定的创建时间倒序。",
    "列表与计数更新，当前选择在结果中时继续保留。",
    "筛选失败时保留原列表。",
    "队列不可读时禁用。",
  ),
  "exports.filter-unfinished": contract(
    "筛选：进行中",
    "队列已加载。",
    "只显示排队、校验、运行、验证、提交和中断待处理任务。",
    "快速定位占用未完成任务上限的记录。",
    "筛选失败时保留原列表。",
    "队列不可读时禁用。",
  ),
  "exports.filter-failed": contract(
    "筛选：需处理",
    "队列已加载。",
    "显示失败、中断、入库失败和疑似停滞任务。",
    "用户可逐项查看原因、诊断和重试入口。",
    "筛选失败时保留原列表。",
    "队列不可读时禁用。",
  ),
  "exports.filter-finished": contract(
    "筛选：已完成",
    "队列已加载。",
    "显示成功与已取消任务。",
    "用户可打开输出或检查历史尝试。",
    "筛选失败时保留原列表。",
    "队列不可读时禁用。",
  ),
  "exports.select-job": contract(
    "选择导出任务",
    "任务仍存在于当前筛选结果。",
    "切换右侧详情，读取该任务的计划摘要、进度、尝试和可用操作。",
    "详情与所选 task_id 一致；不会影响执行顺序。",
    "任务刚被其他状态刷新移除时提示并选择下一项。",
    "队列加载失败时禁用。",
    "无需取消；选择操作不写队列。",
    "只改变界面选择状态。",
  ),
  "exports.view-plan": contract(
    "查看不可变 ExportPlan",
    "任务包含可读的计划快照。",
    "打开只读计划摘要，展示画布、轨道、片段、素材指纹和输出规则。",
    "用户可核对任务究竟导出哪一版项目。",
    "计划损坏时展示校验失败，不尝试运行任务。",
    "旧任务没有计划或队列未知版本时禁用。",
  ),
  "exports.copy-diagnostic": contract(
    "复制任务诊断摘要",
    "任务详情可读。",
    "复制脱敏的 task_id、阶段、退出码、FFmpeg 摘要和尝试记录。",
    "剪贴板写入成功并显示反馈。",
    "剪贴板不可用时显示错误，不改变任务。",
    "队列详情尚未加载时禁用。",
    "关闭反馈不影响任务。",
    "不复制完整素材路径、环境变量或硬件序列号。",
  ),
  "exports.pause-queue": contract(
    "完成当前任务后暂停队列",
    "工作线程正在运行，且队列尚未处于暂停状态。",
    "写入暂停意图；当前任务继续安全完成，后续任务保持排队。",
    "状态栏显示“将在当前任务后暂停”，应用重启后仍保留。",
    "写入队列失败时保持原执行策略并显示错误。",
    "提交阶段不可立即暂停；无运行任务时改为立即暂停。",
    "再次点击可撤销暂停意图。",
    "修改队列调度标志，不修改项目或输出。",
  ),
  "exports.cancel": contract(
    "取消导出任务",
    "任务处于排队、校验、运行、验证或可取消的停滞状态。",
    "显示确认；运行任务向 FFmpeg 发送终止并等待清理，排队任务直接转为已取消。",
    "任务进入已取消；临时文件清理；已有正式输出绝不删除。",
    "终止或清理失败时进入需处理状态并保留诊断。",
    "原子提交已开始或任务已处于终态时禁用。",
    "取消确认对话框时任务继续原状态。",
    "修改任务状态与任务临时文件，不修改项目。",
  ),
  "exports.open-diagnostics": contract(
    "查看导出诊断",
    "任务具有日志或失败上下文。",
    "切换到诊断页并定位该 task_id 的最近事件。",
    "展示预检、FFmpeg、FFprobe、提交和入库阶段摘要。",
    "诊断读取失败时保留导出详情并提示打开日志目录。",
    "没有诊断上下文时禁用。",
  ),
  "exports.primary-action": contract(
    "任务主操作",
    "任务状态决定当前主操作：成功时打开文件，失败/中断时重试，运行时打开输出目录。",
    "执行当前状态唯一最重要的恢复或结果动作。",
    "操作成功后刷新任务详情并给出反馈。",
    "系统调用或重试校验失败时保留当前任务与输出。",
    "验证或原子提交阶段禁用冲突操作。",
  ),
  "exports.empty-project": contract(
    "从空队列打开项目",
    "当前没有导出任务。",
    "切换到项目页，用户可打开时间线并从剪辑工作台创建任务。",
    "进入项目页，不创建空任务。",
    "项目索引不可读时展示项目恢复状态。",
    "设置存在未保存更改时先要求决策。",
  ),
  "export-config.close": contract(
    "关闭导出配置",
    "导出配置对话框已打开。",
    "关闭当前配置；若尚未加入队列，丢弃候选参数。",
    "返回来源工作台，项目和队列保持不变。",
    "关闭界面失败时仍不写队列。",
    "计划正在持久化的短暂提交阶段禁用。",
  ),
  "export-config.resolution": contract(
    "选择输出分辨率",
    "导出配置处于编辑步骤。",
    "选择跟随项目、1080p、720p或自定义偶数画布。",
    "重新计算画面适配、预计大小和 120 FPS 兼容性。",
    "超出 3840×2160 或奇数尺寸时显示字段错误。",
    "预检或提交步骤只读。",
  ),
  "export-config.fps": contract(
    "选择输出帧率",
    "导出配置处于编辑步骤。",
    "选择 30、60 或 120 FPS，并更新编码负载和空间估算。",
    "合法组合进入预检；120 FPS 明确限制最高 1920×1080。",
    "选择 4K120 时阻止预检并提示改用1080p120或4K60。",
    "预检或提交步骤只读。",
  ),
  "export-config.fit": contract(
    "选择画面适配规则",
    "输出画布已确定。",
    "选择保持比例补黑边或裁切填满；同一规则写入 ExportPlan。",
    "预检摘要展示最终规则，预览和正式导出使用同一语义。",
    "非法画布尺寸时保持原选择并提示。",
    "预检或提交步骤只读。",
  ),
  "export-config.codec": contract(
    "查看固定编码配置",
    "导出配置已打开。",
    "展示 v1.9.4 固定的 MP4/H.264/AAC 配置。",
    "用户明确知道输出兼容性与编码基线。",
    "依赖不可用时由预检显示失败。",
    "固定只读；本版不开放高级编码参数。",
  ),
  "export-config.custom-width": contract(
    "自定义画布宽度",
    "分辨率选择为自定义。",
    "输入 320–3840 范围内的偶数宽度。",
    "尺寸合法后更新输出摘要与空间估算。",
    "奇数、越界或空值时阻止预检并就地提示。",
    "非自定义模式或预检中禁用。",
  ),
  "export-config.custom-height": contract(
    "自定义画布高度",
    "分辨率选择为自定义。",
    "输入 240–2160 范围内的偶数高度。",
    "尺寸合法后更新输出摘要与空间估算。",
    "奇数、越界或空值时阻止预检并就地提示。",
    "非自定义模式或预检中禁用。",
  ),
  "export-config.output-dir": contract(
    "查看输出目录",
    "导出配置已打开。",
    "展示正式输出与任务临时文件所在目录。",
    "预检核对目录可写、同磁盘原子提交和磁盘空间。",
    "目录不存在时尝试安全创建；失败则阻止加入队列。",
    "文本框只读，必须通过浏览按钮修改。",
  ),
  "export-config.browse-output": contract(
    "选择输出目录",
    "导出配置处于编辑步骤。",
    "打开 Windows 目录选择器；确认后更新目录、默认文件名和空间估算。",
    "新目录通过可写性和同磁盘规则后用于本次任务。",
    "取消保持原目录；不可写时显示原因。",
    "预检、提交或正在录制时禁用。",
  ),
  "export-config.filename": contract(
    "编辑输出文件名",
    "导出配置处于编辑步骤。",
    "输入 Windows 合法 MP4 文件名；自动补全 .mp4。",
    "实时显示名称可用、冲突避让或覆盖确认要求。",
    "保留字符、空名称或路径过长时阻止预检。",
    "预检或提交步骤只读。",
  ),
  "export-config.check-name": contract(
    "检查输出名称",
    "输出目录与文件名均有效。",
    "检查同名正式文件与预留任务；默认计算安全后缀。",
    "显示可用名称或“(2)”等安全避让结果。",
    "目录不可访问时显示错误，不创建文件。",
    "预检或提交步骤禁用。",
  ),
  "export-config.overwrite": contract(
    "允许覆盖同名文件",
    "用户明确勾选，且目标为普通文件。",
    "仅为本次任务启用可恢复覆盖事务；加入队列前再次确认。",
    "旧文件先安全备份，FFprobe 通过且原子提交成功后才清理备份。",
    "备份、提交或恢复任一步失败时保留可恢复上下文。",
    "目录不可写、目标不是普通文件或队列未知版本时禁用。",
    "取消勾选恢复安全后缀策略。",
    "可能替换同名正式输出，因此必须二次确认并可恢复。",
  ),
  "export-config.add-library": contract(
    "成功后加入中央素材库",
    "导出结果已通过 FFprobe 并完成原子提交。",
    "任务成功后调用素材入库服务写入中央索引。",
    "入库成功后任务详情可跳转素材库。",
    "入库失败时任务仍是导出成功，并提供独立重试。",
    "中央索引只读时可取消勾选后继续导出。",
    "取消勾选时只生成输出文件。",
    "只在导出成功后写中央素材索引。",
  ),
  "export-config.add-project": contract(
    "同时加入当前项目",
    "“加入中央素材库”已启用，当前项目可写且导出成功。",
    "中央入库成功后创建项目素材引用，不复制视频。",
    "项目页出现新素材；时间线不自动添加片段。",
    "项目保存失败时保留中央素材，并在任务详情提供重试。",
    "未启用中央入库、项目只读或项目外部冲突时禁用。",
    "取消勾选不改变当前项目。",
    "导出成功后可能写项目引用，但不修改时间线。",
  ),
  "export-config.cancel": contract(
    "取消导出配置",
    "配置或预检步骤尚未提交任务。",
    "关闭对话框并丢弃候选 ExportPlan。",
    "返回来源页面，不创建任务或临时文件。",
    "关闭失败也不得写入队列。",
    "任务持久化已开始时禁用。",
  ),
  "export-config.back": contract(
    "返回修改导出设置",
    "预检已完成但任务尚未加入队列。",
    "回到设置步骤，保留已输入字段，废弃当前预检结论。",
    "用户可调整参数并重新预检。",
    "界面恢复失败时保留预检页，不写队列。",
    "任务已提交后禁用。",
  ),
  "export-config.preflight": contract(
    "开始预检或加入队列",
    "配置字段有效；预检页通过或只有用户可接受的警告。",
    "设置页执行预检；通过后冻结 ExportPlan，再次点击将其原子写入队列。",
    "任务获得稳定 task_id 并显示排队位置。",
    "硬失败阻止提交；写队列失败不创建半任务。",
    "存在字段错误、缺失素材、磁盘不足或 20 个未完成任务时禁用。",
    "预检阶段可返回修改或取消。",
    "加入队列时写不可变计划与素材指纹，不写项目。",
  ),
  "export-config.use-safe-name": contract(
    "改用安全文件名",
    "发现同名文件或预留任务。",
    "关闭覆盖选项并采用下一个可用后缀名称。",
    "旧文件保持不变，任务按安全名称加入队列。",
    "重新检查时仍冲突则继续递增后缀。",
    "无法访问输出目录时禁用。",
  ),
  "export-config.confirm-overwrite": contract(
    "确认覆盖现有文件",
    "用户已启用覆盖，并在第二次确认中核对目标文件。",
    "写入可恢复覆盖意图和旧文件备份规则，然后加入队列。",
    "执行时只有新输出验证通过后才替换旧文件。",
    "任何阶段失败都尝试恢复旧文件并保留诊断。",
    "目标变化、不可备份或队列写入失败时禁用。",
    "取消确认返回预检页，任务不创建。",
    "可能替换真实文件，属于高风险操作。",
  ),
  "export-config.queue": contract(
    "确认加入导出队列",
    "预检通过，且不需要或已完成覆盖确认。",
    "原子保存任务、ExportPlan和素材指纹。",
    "显示 task_id 和排队位置；工作线程按顺序执行。",
    "写入失败时保留配置和预检结果，方便重试。",
    "队列只读、恢复中或达到上限时禁用。",
  ),
  "exports.exit-demo": contract(
    "运行任务时退出 QuickRec",
    "存在运行或排队任务，用户从托盘选择退出。",
    "显示等待当前任务、立即中断并退出、取消退出三个选择。",
    "选择等待时当前任务完成后退出；选择中断时安全终止并标记 interrupted。",
    "终止失败时保持应用运行并提供诊断。",
    "原子提交阶段禁用立即中断，只允许等待或取消。",
    "取消退出后应用和任务继续原状态。",
    "可能改变运行任务状态，不删除正式输出。",
  ),
};

Object.assign(contracts, exportContracts);
pageMeta.exports = ["导出", "创建、监控并恢复项目的本地 MP4 导出任务。"];

document.querySelectorAll("[data-contract]").forEach((element) => {
  if (!element.dataset.contractRegistered && exportContracts[element.dataset.contract]) {
    registerContractElement(element);
  }
});

const exportConfigLayer = document.getElementById("exportConfigLayer");
const exportDefaultState = document.getElementById("exportDefaultState");
const exportEmptyState = document.getElementById("exportEmptyState");
const exportHealthBanner = document.getElementById("exportHealthBanner");
const newExportButtons = document.querySelectorAll('[data-contract="exports.new"]');
const exportStateControl = document.getElementById("prototypeState");
let exportConfigStep = "config";
let exportPreflightMode = "pass";
let currentExportDetailState = "running";

const exportStateDetails = {
  queued: {
    title: "产品发布演示",
    subtitle: "冻结于 14:34:52 · 排队第 1 位 · 4 个片段",
    badge: "排队中",
    badgeClass: "is-neutral",
    stageTitle: "等待当前任务完成",
    stageText: "任务计划已经持久化；继续编辑项目不会改变本次导出。",
    value: "0%",
    progress: 0,
    elapsed: "等待 00:47",
    eta: "预计 05:42 后开始",
    speed: "工作线程繁忙",
    cardClass: "",
    primary: "查看计划",
  },
  validating: {
    title: "产品发布演示",
    subtitle: "开始执行 · 正在重新核对素材指纹",
    badge: "校验中",
    badgeClass: "",
    stageTitle: "执行前校验",
    stageText: "检查素材身份、FFmpeg、输出目录和磁盘空间。",
    value: "8%",
    progress: 8,
    elapsed: "已用 00:03",
    eta: "预计剩余 00:05",
    speed: "尚未启动编码",
    cardClass: "",
    primary: "打开输出目录",
  },
  running: {
    title: "录屏教程：素材库入门",
    subtitle: "冻结于 14:28:12 · 项目 timeline schema v2 · 6 个片段",
    badge: "正在导出",
    badgeClass: "",
    stageTitle: "正在编码视频与混合 4 路音频",
    stageText: "FFmpeg 正常输出；队列无持续停滞。",
    value: "42%",
    progress: 42,
    elapsed: "已用 02:17",
    eta: "预计剩余 03:18",
    speed: "0.72× 实时速度",
    cardClass: "",
    primary: "打开输出目录",
  },
  stalled: {
    title: "录屏教程：素材库入门",
    subtitle: "进度 45 秒未变化 · FFmpeg 进程仍存活",
    badge: "疑似停滞",
    badgeClass: "is-warning",
    stageTitle: "导出进度暂未更新",
    stageText: "QuickRec 正在观察进程与输出增长，不会立即判定失败。",
    value: "42%",
    progress: 42,
    elapsed: "已用 03:02",
    eta: "预计时间暂不可用",
    speed: "等待 15 秒后再次判断",
    cardClass: "is-warning",
    primary: "查看诊断",
  },
  verifying: {
    title: "录屏教程：素材库入门",
    subtitle: "临时输出已完成 · 尚未提交正式文件",
    badge: "验证中",
    badgeClass: "",
    stageTitle: "使用 FFprobe 验证临时输出",
    stageText: "核对视频流、音频流、时长、分辨率和可解析性。",
    value: "96%",
    progress: 96,
    elapsed: "已用 05:34",
    eta: "预计剩余 00:08",
    speed: "正式文件尚未替换",
    cardClass: "",
    primary: "请稍候",
    disablePrimary: true,
  },
  committing: {
    title: "录屏教程：素材库入门",
    subtitle: "验证已通过 · 正在执行同磁盘原子提交",
    badge: "提交中",
    badgeClass: "",
    stageTitle: "提交正式输出",
    stageText: "当前不可取消；若应用异常退出，启动时优先恢复覆盖事务。",
    value: "99%",
    progress: 99,
    elapsed: "已用 05:42",
    eta: "预计剩余数秒",
    speed: "正在同步文件状态",
    cardClass: "",
    primary: "请稍候",
    disablePrimary: true,
    disableCancel: true,
  },
  succeeded: {
    title: "QuickRec v1.9.3 回顾",
    subtitle: "完成于 14:12:34 · 输出已验证并加入中央素材库",
    badge: "导出成功",
    badgeClass: "is-success",
    stageTitle: "输出已安全提交",
    stageText: "QuickRec-v1.9.3-回顾.mp4 · 128 MB · H.264/AAC",
    value: "100%",
    progress: 100,
    elapsed: "总用时 04:51",
    eta: "输出时长 00:58",
    speed: "已加入素材库",
    cardClass: "is-success",
    primary: "打开输出文件",
    disableCancel: true,
  },
  failed: {
    title: "诊断导出说明",
    subtitle: "失败于 14:26:18 · 正式输出未创建",
    badge: "导出失败",
    badgeClass: "is-danger",
    stageTitle: "素材指纹与任务快照不一致",
    stageText: "源文件在排队期间被覆盖。请重新定位或创建新任务。",
    value: "失败",
    progress: 68,
    elapsed: "尝试 1 · 01:43",
    eta: "错误码 EXPORT_SOURCE_CHANGED",
    speed: "临时文件已清理",
    cardClass: "is-danger",
    primary: "重新校验并重试",
    disableCancel: true,
  },
  cancelled: {
    title: "产品发布演示",
    subtitle: "用户于 14:40:08 取消 · 正式输出未创建",
    badge: "已取消",
    badgeClass: "is-neutral",
    stageTitle: "任务已安全取消",
    stageText: "FFmpeg 已退出，任务临时文件已清理。",
    value: "取消",
    progress: 0,
    elapsed: "总用时 00:18",
    eta: "可从原计划重试",
    speed: "项目未改变",
    cardClass: "",
    primary: "重新创建任务",
    disableCancel: true,
  },
  interrupted: {
    title: "窗口录制教程",
    subtitle: "应用上次退出时中断 · 可基于原计划重试",
    badge: "已中断",
    badgeClass: "is-warning",
    stageTitle: "任务未完成",
    stageText: "正式输出未提交；残留临时文件已在启动恢复中隔离。",
    value: "中断",
    progress: 64,
    elapsed: "上次运行 03:27",
    eta: "重试将从头开始",
    speed: "原计划保持只读",
    cardClass: "is-warning",
    primary: "重新校验并重试",
    disableCancel: true,
  },
  "ingest-failed": {
    title: "录屏教程：素材库入门",
    subtitle: "导出成功 · 中央素材入库尚未完成",
    badge: "入库失败",
    badgeClass: "is-warning",
    stageTitle: "MP4 已成功导出",
    stageText: "正式文件可正常播放；中央索引暂时不可写。",
    value: "100%",
    progress: 100,
    elapsed: "总用时 05:47",
    eta: "输出文件安全",
    speed: "等待重试入库",
    cardClass: "is-warning",
    primary: "重试加入素材库",
    disableCancel: true,
  },
};

function setExportConfigStep(step) {
  exportConfigStep = step;
  document.querySelectorAll("[data-export-config-view]").forEach((view) => {
    view.hidden = view.dataset.exportConfigView !== step;
  });
  document.querySelectorAll("[data-export-step-indicator]").forEach((indicator) => {
    const order = { config: 0, preflight: 1, queued: 2 };
    indicator.classList.toggle("is-active", order[indicator.dataset.exportStepIndicator] <= order[step]);
  });
  const cancelButton = document.getElementById("cancelExportConfig");
  const backButton = document.getElementById("backExportConfig");
  const nextButton = document.getElementById("nextExportConfig");
  cancelButton.hidden = step === "queued";
  backButton.hidden = step !== "preflight";
  if (step === "config") {
    nextButton.hidden = false;
    nextButton.textContent = "开始预检";
    nextButton.dataset.contract = "export-config.preflight";
    nextButton.disabled = false;
    document.getElementById("exportConfigStatus").textContent = "配置不会写入项目文件；只有加入队列后才持久化任务。";
  } else if (step === "preflight") {
    nextButton.hidden = false;
    nextButton.textContent = exportPreflightMode === "failed" ? "预检未通过" : "加入导出队列";
    nextButton.dataset.contract = "export-config.queue";
    nextButton.disabled = exportPreflightMode === "failed";
    document.getElementById("exportConfigStatus").textContent = exportPreflightMode === "warning"
      ? "存在非阻塞警告；加入队列即表示接受当前输出风险。"
      : "加入队列后计划冻结；后续项目编辑不会改变该任务。";
  } else {
    nextButton.hidden = false;
    nextButton.textContent = "查看导出队列";
    nextButton.dataset.contract = "nav.exports";
    nextButton.disabled = false;
    document.getElementById("exportConfigStatus").textContent = "任务已持久化；关闭对话框不会取消任务。";
  }
}

function openExportConfig(step = "config") {
  exportConfigLayer.hidden = false;
  setExportConfigStep(step);
}

function closeExportConfig() {
  exportConfigLayer.hidden = true;
}

function setPreflightMode(mode) {
  exportPreflightMode = mode;
  const summary = document.getElementById("exportPreflightSummary");
  const icon = document.getElementById("exportPreflightIcon");
  const title = document.getElementById("exportPreflightTitle");
  const text = document.getElementById("exportPreflightText");
  const list = document.getElementById("exportPreflightList");
  const rows = Array.from(list.children);
  summary.className = "export-preflight-summary";
  icon.className = "export-preflight-icon";
  const rowDefaults = [
    ["项目与时间线", "最后成功保存版本可读；timeline schema v2。"],
    ["素材与指纹", "4 个素材存在、可解析且指纹匹配。"],
    ["FFmpeg / FFprobe", "包内依赖可执行；版本信息已写入计划。"],
    ["输出规则", "1920×1080 · 60 FPS · 目标路径可写。"],
    ["磁盘空间", "预计峰值 1.6 GB；当前可用 186 GB。"],
  ];
  rows.forEach((row, index) => {
    row.className = "is-success";
    row.querySelector("strong").textContent = rowDefaults[index][0];
    row.querySelector("small").textContent = rowDefaults[index][1];
    row.querySelector("b").textContent = "通过";
  });

  if (mode === "warning") {
    summary.classList.add("is-warning");
    icon.classList.add("is-warning");
    icon.innerHTML = '<svg><use href="#i-alert"></use></svg>';
    title.textContent = "预检通过，但存在可接受警告";
    text.textContent = "预计剩余空间较低；导出期间请避免写入同一磁盘。";
    list.lastElementChild.className = "is-warning";
    list.lastElementChild.querySelector("small").textContent = "预计峰值 1.6 GB；当前可用 2.4 GB。";
    list.lastElementChild.querySelector("b").textContent = "警告";
  } else if (mode === "failed") {
    summary.classList.add("is-danger");
    icon.classList.add("is-danger");
    icon.innerHTML = '<svg><use href="#i-alert"></use></svg>';
    title.textContent = "预检未通过，不能加入队列";
    text.textContent = "素材“窗口选择流程.mp4”缺失，且没有可验证的重新定位结果。";
    const sourceRow = list.children[1];
    sourceRow.className = "is-danger";
    sourceRow.querySelector("small").textContent = "1 个素材缺失；任务不能用黑场静默替代。";
    sourceRow.querySelector("b").textContent = "失败";
  } else {
    summary.className = "export-preflight-summary";
    icon.className = "export-preflight-icon is-success";
    icon.innerHTML = '<svg><use href="#i-check"></use></svg>';
    title.textContent = "预检通过，可以加入队列";
    text.textContent = "ExportPlan 已冻结；正式输出尚未创建。";
  }
  setExportConfigStep("preflight");
}

function setCapacityState(mode) {
  const card = document.getElementById("exportCapacityCard");
  const title = document.getElementById("exportCapacityTitle");
  const text = document.getElementById("exportCapacityText");
  const badge = document.getElementById("exportCapacityBadge");
  card.className = "export-capacity-card";
  badge.className = "badge badge-success";
  if (mode === "notice") {
    title.textContent = "空间可用，建议关注";
    text.textContent = "预计峰值 1.6 GB；E: 可用 8.2 GB。可继续导出。";
    badge.textContent = "提示";
  } else if (mode === "warning") {
    card.classList.add("is-warning");
    title.textContent = "空间接近预估下限";
    text.textContent = "预计峰值 1.6 GB；E: 可用 2.4 GB。导出可能因其他写入失败。";
    badge.className = "badge badge-warning";
    badge.textContent = "需确认";
  } else if (mode === "blocked") {
    card.classList.add("is-danger");
    title.textContent = "磁盘空间不足";
    text.textContent = "预计峰值 1.6 GB；E: 仅可用 980 MB。必须更换目录或释放空间。";
    badge.className = "badge badge-danger";
    badge.textContent = "已阻止";
  } else {
    title.textContent = "空间充足";
    text.textContent = "预计输出 480 MB，临时空间上限 1.6 GB；E: 可用 186 GB。";
    badge.textContent = "可继续";
  }
}

function setExportDetailState(state) {
  const config = exportStateDetails[state] || exportStateDetails.running;
  currentExportDetailState = state;
  document.getElementById("exportDetailTitle").textContent = config.title;
  document.getElementById("exportDetailSubtitle").textContent = config.subtitle;
  const badge = document.getElementById("exportStatusBadge");
  badge.textContent = config.badge;
  badge.className = `export-status-badge ${config.badgeClass}`.trim();
  const stageCard = document.getElementById("exportStageCard");
  stageCard.className = `export-stage-card ${config.cardClass}`.trim();
  document.getElementById("exportStageTitle").textContent = config.stageTitle;
  document.getElementById("exportStageText").textContent = config.stageText;
  document.getElementById("exportProgressValue").textContent = config.value;
  document.getElementById("exportProgressBar").style.width = `${config.progress}%`;
  document.getElementById("exportElapsed").textContent = config.elapsed;
  document.getElementById("exportEta").textContent = config.eta;
  document.getElementById("exportSpeed").textContent = config.speed;
  const primary = document.getElementById("primaryExportAction");
  const cancel = document.getElementById("cancelExportTask");
  primary.textContent = config.primary;
  primary.disabled = Boolean(config.disablePrimary);
  cancel.disabled = Boolean(config.disableCancel);
}

function resetExportPage() {
  exportDefaultState.hidden = false;
  exportEmptyState.hidden = true;
  exportHealthBanner.hidden = true;
  exportHealthBanner.className = "export-health-banner";
  document.getElementById("newExportTask").disabled = false;
  document.querySelector(".export-nav-count").textContent = "3";
  document.getElementById("exportQueueSummary").textContent = "1 个运行 · 2 个等待";
  document.getElementById("exportLimitUsage").textContent = "当前 3 / 20";
  setExportDetailState("running");
}

function showExitPrompt() {
  showModal({
    title: "导出仍在进行，如何退出？",
    text: "当前任务正在编码。你可以等待当前任务完成后退出，或安全中断任务并立即退出。",
    detail: "原子提交阶段不能立即中断。排队任务会保留，并在下次启动时继续等待。",
    icon: "warning",
    wide: true,
    actions: [
      { label: "取消退出", contract: "modal.cancel", onClick: closeModal },
      {
        label: "中断任务并退出",
        kind: "button-danger-quiet",
        contract: "exports.exit-demo",
        onClick: () => {
          closeModal();
          setExportDetailState("interrupted");
          showToast("任务已安全中断", "下次启动可从原计划重新校验并重试。", "warning");
        },
      },
      {
        label: "完成当前任务后退出",
        kind: "button-primary",
        contract: "exports.exit-demo",
        onClick: () => {
          closeModal();
          showToast("已安排退出", "当前任务完成后 QuickRec 将退出，排队任务保留。", "success");
        },
      },
    ],
  });
}

function showOverwriteConfirmation() {
  showModal({
    title: "确认覆盖现有文件？",
    text: "目标“录屏教程-素材库入门.mp4”已经存在。QuickRec 会先备份旧文件，再验证并提交新输出。",
    detail: "覆盖失败或应用异常退出时，启动恢复会优先恢复旧文件。仍建议使用安全后缀避免替换。",
    icon: "danger",
    wide: true,
    actions: [
      { label: "取消", contract: "modal.cancel", onClick: closeModal },
      {
        label: "改用安全名称",
        contract: "export-config.use-safe-name",
        onClick: () => {
          document.getElementById("allowExportOverwrite").checked = false;
          document.getElementById("exportFilename").value = "录屏教程-素材库入门 (2).mp4";
          closeModal();
          queueExportTask();
        },
      },
      {
        label: "确认覆盖并加入队列",
        kind: "button-primary",
        contract: "export-config.confirm-overwrite",
        onClick: () => {
          closeModal();
          queueExportTask();
        },
      },
    ],
  });
}

function queueExportTask() {
  setExportConfigStep("queued");
  document.getElementById("exportQueueSummary").textContent = "1 个运行 · 3 个等待";
  document.getElementById("exportLimitUsage").textContent = "当前 4 / 20";
  document.querySelector(".export-nav-count").textContent = "4";
}

function applyExportPrototypeState(state) {
  if (!state.startsWith("export-")) {
    return;
  }
  closeModal();
  routeTo("exports", { force: true });
  closeExportConfig();
  resetExportPage();
  const mode = state.slice("export-".length);

  if (mode === "empty") {
    exportDefaultState.hidden = true;
    exportEmptyState.hidden = false;
    document.querySelector(".export-nav-count").textContent = "0";
    document.getElementById("exportQueueSummary").textContent = "暂无任务";
  } else if (mode.startsWith("preflight-")) {
    openExportConfig("preflight");
    setPreflightMode(mode.replace("preflight-", ""));
  } else if (mode.startsWith("disk-")) {
    openExportConfig("config");
    setCapacityState(mode.replace("disk-", ""));
    if (mode === "disk-blocked") {
      document.getElementById("nextExportConfig").disabled = true;
    }
  } else if (mode === "conflict-safe") {
    openExportConfig("config");
    document.getElementById("exportFilename").value = "录屏教程-素材库入门 (2).mp4";
    document.getElementById("exportFilenameHint").textContent = "检测到同名文件，已选择下一个可用安全名称；旧文件不会被覆盖。";
  } else if (mode === "overwrite") {
    openExportConfig("preflight");
    setPreflightMode("pass");
    document.getElementById("allowExportOverwrite").checked = true;
    window.setTimeout(showOverwriteConfirmation, 0);
  } else if (mode === "exit-prompt") {
    setExportDetailState("running");
    window.setTimeout(showExitPrompt, 0);
  } else if (mode === "limit") {
    exportHealthBanner.hidden = false;
    exportHealthBanner.classList.add("is-danger");
    document.getElementById("exportHealthTitle").textContent = "未完成任务已达到 20 个";
    document.getElementById("exportHealthText").textContent = "请完成、取消或处理现有任务后再创建新任务。正式输出不会因淘汰队列而删除。";
    document.getElementById("newExportTask").disabled = true;
    document.getElementById("exportLimitUsage").textContent = "当前 20 / 20";
  } else if (mode === "queue-corrupt") {
    exportHealthBanner.hidden = false;
    document.getElementById("exportHealthTitle").textContent = "队列文件损坏，已从有效备份恢复";
    document.getElementById("exportHealthText").textContent = "原损坏文件已隔离；2 个运行态任务被映射为“已中断”，等待用户重试。";
    setExportDetailState("interrupted");
  } else if (mode === "queue-unknown") {
    exportHealthBanner.hidden = false;
    exportHealthBanner.classList.add("is-danger");
    document.getElementById("exportHealthTitle").textContent = "队列版本高于当前应用";
    document.getElementById("exportHealthText").textContent = "任务仅以只读方式展示；QuickRec 不会覆盖该队列或启动其中任务。";
    document.getElementById("newExportTask").disabled = true;
    document.getElementById("pauseExportQueue").disabled = true;
    document.getElementById("cancelExportTask").disabled = true;
  } else {
    setExportDetailState(mode);
  }
}

newExportButtons.forEach((button) => button.addEventListener("click", () => {
  setCapacityState("ok");
  setPreflightMode("pass");
  openExportConfig("config");
}));

document.getElementById("exportFromTimeline").addEventListener("click", () => {
  setCapacityState("ok");
  setPreflightMode("pass");
  openExportConfig("config");
});

document.getElementById("closeExportConfig").addEventListener("click", closeExportConfig);
document.getElementById("cancelExportConfig").addEventListener("click", closeExportConfig);
exportConfigLayer.addEventListener("click", (event) => {
  if (event.target === exportConfigLayer && exportConfigStep !== "queued") {
    closeExportConfig();
  }
});

document.getElementById("backExportConfig").addEventListener("click", () => setExportConfigStep("config"));
document.getElementById("nextExportConfig").addEventListener("click", () => {
  if (exportConfigStep === "config") {
    setPreflightMode("pass");
  } else if (exportConfigStep === "preflight") {
    if (document.getElementById("allowExportOverwrite").checked) {
      showOverwriteConfirmation();
    } else {
      queueExportTask();
    }
  } else {
    closeExportConfig();
    routeTo("exports", { force: true });
    setExportDetailState("queued");
  }
});

document.getElementById("exportResolution").addEventListener("change", (event) => {
  document.getElementById("exportCustomSize").hidden = event.target.value !== "custom";
  if (event.target.value === "source" && document.getElementById("exportFps").value.startsWith("120")) {
    document.getElementById("exportFpsHint").textContent = "2560×1440 不支持 120 FPS，请选择 1080p 或将帧率改为 60。";
    document.getElementById("nextExportConfig").disabled = true;
  } else {
    document.getElementById("exportFpsHint").textContent = "120 FPS 仅允许最高 1920×1080。";
    document.getElementById("nextExportConfig").disabled = false;
  }
});

document.getElementById("exportFps").addEventListener("change", () => {
  document.getElementById("exportResolution").dispatchEvent(new Event("change"));
});

document.getElementById("exportAddLibrary").addEventListener("change", (event) => {
  const addProject = document.getElementById("exportAddProject");
  addProject.disabled = !event.target.checked;
  if (!event.target.checked) {
    addProject.checked = false;
  }
});

document.getElementById("checkExportName").addEventListener("click", () => {
  const input = document.getElementById("exportFilename");
  const hint = document.getElementById("exportFilenameHint");
  if (input.value.includes("冲突")) {
    input.value = "录屏教程-素材库入门 (2).mp4";
    hint.textContent = "检测到同名文件，已采用安全后缀；旧文件保持不变。";
    showToast("已选择安全文件名", input.value, "success");
  } else {
    hint.textContent = "名称可用；队列提交时仍会再次检查冲突。";
    showToast("文件名可用", "正式输出尚未创建。", "success");
  }
});

document.getElementById("refreshExportQueue").addEventListener("click", () => {
  showToast("导出队列已刷新", "任务状态与工作线程快照已同步。", "success");
});

document.querySelectorAll("[data-export-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-export-filter]").forEach((item) => item.classList.toggle("is-active", item === button));
    const filter = button.dataset.exportFilter;
    document.querySelectorAll(".export-job-card").forEach((card) => {
      const job = card.dataset.exportJob;
      const visible = filter === "all"
        || (filter === "unfinished" && ["running", "queued", "interrupted"].includes(job))
        || (filter === "failed" && ["failed", "interrupted"].includes(job))
        || (filter === "finished" && job === "succeeded");
      card.hidden = !visible;
    });
  });
});

document.querySelectorAll(".export-job-card").forEach((card) => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".export-job-card").forEach((item) => item.classList.toggle("is-selected", item === card));
    setExportDetailState(card.dataset.exportJob);
  });
});

document.getElementById("viewExportPlan").addEventListener("click", () => {
  showModal({
    title: "不可变 ExportPlan",
    text: "该任务始终导出 14:28:12 冻结的项目状态，不读取后续编辑。",
    detail: "schema=1 · timeline_schema=2 · canvas=1920x1080@60 · clips=6 · audio_tracks=4 · fit=contain-black · video=libx264/crf20/veryfast · audio=aac/48k/stereo/192k",
    wide: true,
    actions: [{ label: "关闭", contract: "modal.cancel", onClick: closeModal }],
  });
});

document.getElementById("copyExportDiagnostic").addEventListener("click", () => {
  showToast("诊断摘要已复制", "已省略完整素材路径和环境变量。", "success");
});

document.getElementById("openExportFolder").addEventListener("click", () => {
  showToast("已打开导出目录", "E:\\Videos\\QuickRec\\Exports", "success");
});

document.getElementById("cleanExportHistory").addEventListener("click", () => {
  showModal({
    title: "清理已完成导出历史？",
    text: "将删除 7 条超过保留期的终态记录和对应临时目录，不删除任何正式 MP4。",
    icon: "warning",
    actions: [
      { label: "取消", contract: "modal.cancel", onClick: closeModal },
      {
        label: "确认清理",
        kind: "button-primary",
        contract: "exports.clean-history",
        onClick: () => {
          closeModal();
          showToast("历史已清理", "7 条记录已移除，正式输出保持不变。", "success");
        },
      },
    ],
  });
});

document.getElementById("pauseExportQueue").addEventListener("click", (event) => {
  const active = event.currentTarget.dataset.pauseScheduled === "true";
  event.currentTarget.dataset.pauseScheduled = String(!active);
  event.currentTarget.textContent = active ? "完成当前任务后暂停" : "取消暂停安排";
  showToast(
    active ? "已取消暂停安排" : "队列将在当前任务后暂停",
    active ? "后续排队任务将继续自动运行。" : "当前任务不会被中断。",
    active ? "info" : "success",
  );
});

document.getElementById("cancelExportTask").addEventListener("click", () => {
  showModal({
    title: "取消当前导出任务？",
    text: "QuickRec 将安全终止 FFmpeg 并清理任务临时文件。已存在的正式输出不会被删除。",
    icon: "warning",
    actions: [
      { label: "继续导出", contract: "modal.cancel", onClick: closeModal },
      {
        label: "确认取消",
        kind: "button-danger-quiet",
        contract: "exports.cancel",
        onClick: () => {
          closeModal();
          setExportDetailState("cancelled");
          showToast("任务已取消", "正式文件与项目未发生变化。", "success");
        },
      },
    ],
  });
});

document.getElementById("openExportDiagnostics").addEventListener("click", () => {
  routeTo("diagnostics", { force: true });
  showToast("已定位导出诊断", "显示当前 task_id 的最近导出事件。", "success");
});

document.getElementById("primaryExportAction").addEventListener("click", () => {
  if (["failed", "interrupted"].includes(currentExportDetailState)) {
    setExportDetailState("validating");
    showToast("已重新加入执行", "先重新校验素材指纹，再启动 FFmpeg。", "success");
  } else if (currentExportDetailState === "ingest-failed") {
    setExportDetailState("succeeded");
    showToast("素材入库成功", "导出结果已加入中央素材库。", "success");
  } else if (currentExportDetailState === "succeeded") {
    showToast("正在打开输出", "QuickRec-v1.9.3-回顾.mp4", "success");
  } else {
    showToast("已打开输出目录", "运行中只展示临时进度，不打开未验证文件。", "info");
  }
});

document.getElementById("exportHealthAction").addEventListener("click", () => {
  showModal({
    title: "导出队列恢复报告",
    text: document.getElementById("exportHealthText").textContent,
    detail: "恢复过程不会覆盖未知版本队列；原文件和自动备份保留在本地诊断目录。",
    actions: [{ label: "关闭", contract: "modal.cancel", onClick: closeModal }],
  });
});

document.getElementById("toggleAnnotations").addEventListener("click", () => {
  if (currentPage === "exports" && workbenchBody.classList.contains("show-contracts")) {
    selectContract(document.querySelector('[data-contract="exports.new"]'));
  }
});

exportStateControl.addEventListener("change", () => applyExportPrototypeState(exportStateControl.value));

const exportUrlParams = new URLSearchParams(window.location.search);
if (exportUrlParams.get("page") === "exports") {
  routeTo("exports", { force: true });
}
if ((exportUrlParams.get("state") || "").startsWith("export-")) {
  applyExportPrototypeState(exportUrlParams.get("state"));
}
