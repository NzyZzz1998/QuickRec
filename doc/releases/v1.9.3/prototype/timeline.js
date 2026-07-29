"use strict";

(() => {
  const timelineContracts = {
    "timeline.view-materials": contract(
      "项目二级页：素材",
      "已打开有效项目，且没有尚未处理的时间线保存失败。",
      "停止当前播放并切换到 v1.9.1 项目素材视图；保留当前项目和素材选择。",
      "展示静态首帧、素材详情和项目素材管理操作。",
      "项目不可读时进入项目恢复状态，不把时间线显示为空。",
      "没有有效项目或外部冲突尚未处理时禁用。",
      "取消保存失败处理时留在时间线。",
      "二级视图切换只改变同进程页面状态，不写项目文件。",
    ),
    "timeline.view-timeline": contract(
      "进入独立剪辑工作台",
      "已打开有效项目；非空时间线首次打开默认进入此视图。",
      "读取 extensions[\"quickrec.timeline\"]，打开默认最大化的独立顶级窗口并恢复轨道、片段和上次成功保存状态。",
      "剪辑工作台与主工作台同时存在；展示项目素材区、预览、播放控制、轨道和片段，不自动开始播放。",
      "数据损坏或版本未知时进入只读恢复状态，保留原项目文件。",
      "没有有效项目、项目缺失或恢复事务进行中时禁用。",
      "关闭或返回主工作台时停止播放，但保留项目与同进程剪辑上下文。",
      "两个窗口共享项目模型；只读时间线扩展块，明确结构操作成功后才原子写回项目文件。",
    ),
    "timeline.focus-mode": contract(
      "切换专注时间线",
      "时间线页面已加载；该操作不要求项目可写。",
      "在“素材与预览 + 时间线”和“仅时间线”两种编辑布局之间切换。",
      "专注模式隐藏上方素材与预览区，轨道画布获得完整剩余高度；再次点击恢复。",
      "纯界面操作没有后端失败路径，布局异常时恢复标准编辑布局。",
      "不在时间线页面时不可见；时间线只读或播放失败时仍可使用。",
      "再次点击即取消专注模式，不改变播放头、选择、缩放或未保存命令。",
      "只保留同进程界面状态，不写项目文件、素材索引或用户配置。",
    ),
    "timeline.preview-maximize": contract(
      "放大或恢复视频预览",
      "剪辑工作台已打开；该操作不要求项目可写或播放后端已启动。",
      "在“可调预览 + 时间线”和“预览占满剩余工作区”两种布局之间切换。",
      "放大后完整保留视频宽高比、播放控制和素材区；再次点击恢复上次分栏高度。",
      "纯界面操作没有后端失败路径，布局异常时恢复默认分栏。",
      "专注时间线时不可见；项目只读、素材缺失或播放失败时仍可使用。",
      "再次点击即恢复，不改变播放头、素材选择、播放状态或项目内容。",
      "只保留同进程界面状态，不写项目文件、素材索引或用户配置。",
    ),
    "timeline.resize-panels": contract(
      "调整视频预览与时间线高度",
      "剪辑工作台处于标准布局，预览区和时间线都可见。",
      "拖动分隔条、使用方向键或 Home/End 调整预览高度；双击恢复当前窗口尺寸对应的默认值。",
      "视频始终完整自适应显示，时间线保留最低可操作高度，分隔条同步更新辅助功能数值。",
      "窗口空间不足或尺寸计算异常时把高度限制在安全范围，不产生页面滚动或内容覆盖。",
      "专注时间线、放大预览或工作台未打开时不可用。",
      "拖动中按 Esc 恢复拖动前高度；双击可随时恢复默认分栏。",
      "仅保留同进程布局状态，不修改项目、素材、播放状态或用户配置。",
    ),
    "timeline.exit-workbench": contract(
      "返回项目工作台",
      "剪辑工作台已打开；当前时间线没有未解决的保存失败。",
      "停止播放并把主工作台切到当前项目的素材视图；剪辑窗口转入后台。",
      "项目选择和时间线编辑状态保留，用户可再次进入剪辑工作台继续编辑。",
      "保存失败或项目冲突未处理时阻止离开，并保留当前剪辑窗口。",
      "保存事务进行中或存在必须处理的冲突时禁用。",
      "取消离开后继续停留在剪辑工作台，播放保持暂停。",
      "不关闭 QuickRec，不释放项目模型；只切换两个顶级窗口的前后台状态。",
    ),
    "timeline.open-material-workbench": contract(
      "打开素材工作台",
      "主工作台实例仍在运行，剪辑工作台已打开。",
      "激活主工作台并切到全局素材库；剪辑工作台保持实例和项目上下文。",
      "用户可管理或录制新素材，返回剪辑窗口后轨道、播放头和选择保持。",
      "主工作台激活失败时保留剪辑窗口并显示诊断入口。",
      "应用正在退出或主工作台重建期间禁用。",
      "关闭素材工作台不会关闭剪辑窗口或 QuickRec。",
      "两个窗口共享协调器和中央素材索引，不复制项目或媒体数据。",
    ),
    "timeline.start-recording": contract(
      "从剪辑工作台发起录制",
      "未播放、未保存、没有录制任务，主工作台录制能力可用。",
      "激活主工作台录制页并进入模式选择；剪辑工作台保持实例但暂时退到后台。",
      "开始捕获前按现有规则隐藏 QuickRec 自身窗口；保存完成后可恢复剪辑上下文并刷新素材。",
      "录制启动失败时恢复剪辑窗口并显示失败原因，不修改时间线。",
      "播放中、保存中、已有录制任务或项目冲突时禁用。",
      "取消模式选择或倒计时后恢复剪辑工作台，不创建文件。",
      "复用 QuickRecApp 与 RecorderManager 现有录制链路，不建立第二套录制状态机。",
    ),
    "timeline.close-workbench": contract(
      "关闭剪辑工作台",
      "剪辑工作台已打开；当前没有未解决的保存失败。",
      "停止播放并隐藏独立剪辑窗口，主工作台和托盘继续运行。",
      "再次从项目进入剪辑时恢复已保存时间线和同进程界面状态。",
      "保存失败、资源释放失败或项目冲突未处理时保持窗口并显示原因。",
      "保存事务或关闭资源事务执行中禁用。",
      "取消关闭后保留当前窗口、项目和播放头。",
      "只关闭剪辑顶级窗口，不退出 QuickRec、不删除项目或素材。",
    ),
    "timeline.state-action": contract(
      "时间线状态处理",
      "时间线显示保存、播放、缺失、冲突或版本异常。",
      "按当前状态进入重新定位、重试保存、重新加载、备份恢复或诊断链路。",
      "处理成功后恢复可编辑时间线或明确只读结果。",
      "失败时保留最后一次成功保存的数据和错误上下文。",
      "状态没有恢复动作、处理进行中或项目不可读时禁用。",
      "取消后保持当前安全状态，不覆盖项目。",
      "只有验证和保存全部成功后才更新时间线或素材路径。",
    ),
    "timeline.material-collapse": contract(
      "折叠或展开项目素材区",
      "时间线页面已加载。",
      "在紧凑图标宽度和完整素材列表之间切换，为轨道或预览释放横向空间。",
      "图标方向、素材区宽度和预览宽度同步变化。",
      "纯界面操作，无后端失败路径。",
      "始终可用。",
      "再次点击恢复上一种宽度。",
      "只修改同进程界面状态，不写项目文件。",
    ),
    "timeline.material-search": contract(
      "搜索项目素材",
      "项目素材引用已加载。",
      "按文件名或最后已知完整路径进行包含匹配，输入时即时更新可见素材。",
      "显示匹配数量；缺失素材仍可被搜索并进入恢复操作。",
      "查询异常时保留上一组可见结果，不修改项目。",
      "项目不可读或正在切换项目时禁用。",
      "清空输入恢复全部项目素材。",
      "只查询当前项目引用，不查询或修改中央素材库。",
    ),
    "timeline.material-clear": contract(
      "清空素材搜索",
      "搜索框存在关键词。",
      "清空关键词并恢复当前项目全部素材。",
      "列表和匹配数量立即恢复。",
      "纯界面操作，无后端失败路径。",
      "搜索框为空时禁用。",
      "无需确认。",
      "不写任何业务数据。",
    ),
    "timeline.material-select": contract(
      "选择项目素材",
      "素材引用可读取；文件缺失时仍允许选择。",
      "高亮素材并更新预览摘要；不改变时间线。",
      "后续“加入时间线”或拖动操作明确作用于当前素材。",
      "素材状态变化时刷新为最新状态并保留项目上下文。",
      "项目不可读时无素材可选。",
      "选择其他素材只替换当前选择。",
      "只改变界面选择状态。",
    ),
    "timeline.material-add": contract(
      "把素材加入时间线",
      "素材可解析、项目可写、同类轨道存在且没有冲突保存事务。",
      "视频片段追加到最早可用视频轨；若 MP4 含音频，同时创建关联音频片段。",
      "选中新片段、移动播放头并原子保存；音视频片段共享 link_group_id。",
      "轨道已满、落点冲突、格式不支持或保存失败时不保留任何新片段。",
      "素材缺失、项目只读/归档、格式不支持或保存进行中时禁用。",
      "按钮提交前无需二次确认；失败等同于取消且不修改项目。",
      "成功时只新增稳定片段引用，不复制、移动或修改原视频。",
    ),
    "timeline.material-relink": contract(
      "重新定位缺失素材",
      "素材引用存在但文件缺失。",
      "进入现有重新定位流程；先验证候选文件，再更新素材路径和媒体元数据。",
      "全部引用同一 material_id 的片段恢复，片段身份和时间位置不变。",
      "候选不可解析、ID不匹配或保存失败时保持原缺失状态。",
      "素材正常、项目不可读或另一次重新定位进行中时禁用。",
      "取消文件选择不修改素材或时间线。",
      "成功时更新素材路径和可再生缓存，不创建新 clip_id。",
    ),
    "timeline.material-open": contract(
      "打开所选项目素材",
      "所选素材文件存在、是普通文件且仍可访问。",
      "使用 Windows 默认播放器打开真实视频，时间线项目和播放头保持不变。",
      "系统播放器打开正确文件，QuickRec 工作台继续可用。",
      "文件缺失、无默认关联或系统调用失败时显示恢复建议。",
      "素材缺失、路径无效或没有选中素材时禁用。",
      "关闭系统播放器不影响项目和时间线。",
      "只触发系统打开操作，不修改项目、素材或时间线。",
    ),
    "timeline.material-folder": contract(
      "打开所选素材目录",
      "所选素材路径或父目录可访问。",
      "调用资源管理器并选中源视频；文件缺失时不伪造成功。",
      "资源管理器进入正确目录，项目上下文保持。",
      "目录不存在或系统调用失败时显示明确原因。",
      "文件和父目录都不可访问或没有选中素材时禁用。",
      "关闭资源管理器不影响 QuickRec。",
      "不修改任何业务数据。",
    ),
    "timeline.open-material-view": contract(
      "在素材视图管理全部素材",
      "当前项目有效。",
      "暂停播放并切换到项目“素材”二级页。",
      "保持当前项目，并尽量选中当前时间线素材。",
      "目标素材已被项目移除时仍进入素材页并显示最新列表。",
      "没有有效项目时禁用。",
      "取消保存失败处理时留在时间线。",
      "只切换视图，不修改项目。",
    ),
    "timeline.preview-retry": contract(
      "重试播放",
      "播放后端、解码或素材状态出现可恢复错误。",
      "释放失败运行时，重新初始化后端并定位到当前播放头。",
      "画面、时钟和音频状态恢复；不重建时间线数据。",
      "再次失败时保留错误占位，并允许查看诊断或重新定位素材。",
      "没有错误、项目损坏或重试进行中时隐藏或禁用。",
      "取消重试保持暂停和错误占位。",
      "只重建播放运行时，不写项目文件。",
    ),
    "timeline.preview-diagnostics": contract(
      "查看播放诊断",
      "存在播放、解码、音频或保存错误上下文。",
      "停止播放，打开诊断一级页并定位时间线最近错误摘要。",
      "用户可复制或导出本地诊断信息，再返回原项目。",
      "诊断页不可用时保留原错误并提示日志目录。",
      "无错误上下文时仍可打开诊断页，但不伪造错误。",
      "返回项目时恢复项目和二级视图，不自动恢复播放。",
      "导航本身不修改项目或媒体文件。",
    ),
    "timeline.play": contract(
      "播放时间线",
      "时间线非空、项目可读、播放后端可用，且当前未播放。",
      "预加载当前活动片段，启动统一时钟并按最高视频轨和固定音频混合规则播放。",
      "图标切换为暂停，播放头、当前时间、画面和音频保持同步。",
      "后端、素材或音频失败时显示具体阶段；音频不可用需用户决定是否无声继续。",
      "空时间线、项目损坏、后端不可用或切换项目时禁用。",
      "暂停不修改播放头；关闭工作台或切换项目会停止并释放资源。",
      "播放是只读操作，不写项目、素材或缓存。",
    ),
    "timeline.seek": contract(
      "拖动播放位置",
      "时间线已加载，播放后端支持随机寻址。",
      "拖动期间更新候选时间；松开后统一定位视频和音频并刷新播放头。",
      "当前时间、预览画面和轨道播放头同步。",
      "寻址失败时回到最后有效位置并显示重试入口。",
      "后端整体失去响应或项目不可读时禁用。",
      "取消拖动保留原位置。",
      "只改变瞬时播放位置，不写项目文件。",
    ),
    "timeline.undo": contract(
      "撤销时间线操作",
      "存在可撤销的结构命令，项目可写且没有保存事务。",
      "恢复上一轨道/片段状态并执行一次原子保存。",
      "轨道、片段、总时长和重做按钮同步更新。",
      "保存失败时回滚到撤销前状态，错误上下文可重试。",
      "无历史、只读、冲突或保存中时禁用。",
      "不弹确认；再次撤销处理更早命令。",
      "成功会修改项目时间线扩展块，撤销栈本身不持久化。",
    ),
    "timeline.redo": contract(
      "重做时间线操作",
      "存在被撤销命令，项目可写且没有保存事务。",
      "恢复下一状态并执行一次原子保存。",
      "轨道、片段、总时长和撤销按钮同步更新。",
      "保存失败时保持重做前状态。",
      "无重做历史、只读、冲突或保存中时禁用。",
      "不弹确认。",
      "成功会修改项目时间线扩展块。",
    ),
    "timeline.add-video-track": contract(
      "新增视频轨",
      "视频轨少于 8 条，项目可写。",
      "在视频轨最顶部创建空轨并进入名称编辑；新轨层级最高。",
      "保存成功后轨道可接收视频片段，覆盖规则立即使用新顺序。",
      "保存失败时不保留新轨。",
      "达到 8 条、只读、冲突或保存中时禁用。",
      "取消名称编辑使用默认名称。",
      "成功新增稳定 track_id，不创建素材或片段。",
    ),
    "timeline.add-audio-track": contract(
      "新增音频轨",
      "音频轨少于 8 条，项目可写。",
      "在音频轨末尾创建空轨并进入名称编辑。",
      "保存成功后轨道可接收关联音频片段。",
      "保存失败时不保留新轨。",
      "达到 8 条、只读、冲突或保存中时禁用。",
      "取消名称编辑使用默认名称。",
      "成功新增稳定 track_id，不改变音频增益策略。",
    ),
    "timeline.zoom-out": contract(
      "缩小时间线",
      "当前缩放高于最小值。",
      "降低每秒像素宽度，保持播放头对应时间不变。",
      "标尺、片段和滚动位置同步重算。",
      "纯界面操作，无后端失败路径。",
      "达到最小缩放时禁用。",
      "无需确认。",
      "不写项目文件。",
    ),
    "timeline.zoom-in": contract(
      "放大时间线",
      "当前缩放低于最大值。",
      "提高每秒像素宽度，保持播放头对应时间不变。",
      "标尺、片段和滚动位置同步重算。",
      "纯界面操作，无后端失败路径。",
      "达到最大缩放时禁用。",
      "无需确认。",
      "不写项目文件。",
    ),
    "timeline.fit": contract(
      "适配完整时间线",
      "时间线页面已加载。",
      "计算当前可用宽度并一次展示全部片段。",
      "缩放标签与滚动位置同步；空时间线使用默认范围。",
      "纯界面操作，无后端失败路径。",
      "始终可用。",
      "无需确认。",
      "不写项目文件。",
    ),
    "timeline.ruler-seek": contract(
      "在时间标尺跳转",
      "时间线已加载。",
      "点击位置换算为微秒并移动播放头；播放中则从新位置继续。",
      "当前时间、预览和轨道播放线同步。",
      "寻址失败时保留最后有效位置并显示反馈。",
      "项目不可读或播放后端失去响应时禁用。",
      "点击标尺外不产生操作。",
      "不写项目文件。",
    ),
    "timeline.track-reorder": contract(
      "调整轨道顺序",
      "项目可写，目标和来源轨道类型相同。",
      "拖动轨道头改变同类轨道 order；视频轨顺序决定画面覆盖。",
      "松开后形成一个撤销命令并原子保存。",
      "跨类型、无效落点或保存失败时恢复原顺序。",
      "项目只读、冲突、保存中或只有一条同类轨道时禁用。",
      "取消拖动不修改顺序。",
      "只修改轨道 order，不改变片段时间和素材。",
    ),
    "timeline.track-rename": contract(
      "重命名轨道",
      "项目可写且轨道存在。",
      "打开就近编辑框；空名称提交时恢复“视频 N / 音频 N”默认名称。",
      "新名称随时间线原子保存并保持 track_id 不变。",
      "保存失败时恢复旧名称。",
      "只读、冲突或保存中时禁用。",
      "取消编辑保留旧名称。",
      "只修改轨道 name。",
    ),
    "timeline.track-delete": contract(
      "删除轨道",
      "项目可写且删除后仍满足至少一条视频轨和一条音频轨。",
      "空轨直接确认；含片段轨显示片段与关联组数量后要求二次确认。",
      "确认后以一个可撤销命令删除轨道及其片段并原子保存。",
      "保存失败时轨道和片段全部恢复。",
      "最后一条同类型轨、只读、冲突或保存中时禁用。",
      "取消确认不修改轨道和片段。",
      "不删除项目素材、中央素材或真实视频。",
    ),
    "timeline.track-lock": contract(
      "锁定或解锁轨道",
      "项目可写、轨道存在且没有待处理保存或外部冲突。",
      "切换轨道 locked 状态；锁定后禁止新增、移动、裁剪、分割和删除该轨片段。",
      "形成一条可撤销命令并原子保存；锁定图标、轨道底纹和状态文字同步更新。",
      "保存失败时恢复原锁定状态；全局波纹需要移动锁定轨片段时整次剪辑不提交。",
      "只读、冲突、保存中或轨道状态未知时禁用。",
      "再次点击恢复原状态；保存前失败等同取消。",
      "只修改 timeline schema v2 的 TimelineTrack.locked，不修改素材或媒体文件。",
    ),
    "timeline.inspector-toggle": contract(
      "打开片段属性检查器",
      "已选中一个有效片段或合法关联音视频组。",
      "在剪辑区右侧打开检查器，载入时间线起点、源入点、源出点、有效时长和关联状态。",
      "数值与当前正式模型一致；打开检查器不会改变时间线或停止播放。",
      "片段状态在载入期间变化时刷新为最新值并提示，不保留陈旧输入。",
      "没有选择、项目恢复中或片段关联异常时禁用。",
      "关闭检查器或按 Esc 放弃尚未应用的输入。",
      "只读取选中片段；点击“应用”前不写项目文件。",
    ),
    "timeline.inspector-close": contract(
      "关闭片段属性检查器",
      "片段属性检查器已打开。",
      "关闭检查器并丢弃尚未应用的候选输入。",
      "轨道、片段、播放头和正式源范围保持不变。",
      "纯界面操作，无后端失败路径。",
      "检查器关闭时不可见。",
      "等同片段属性中的“取消”。",
      "不写项目文件或撤销栈。",
    ),
    "timeline.trim-handle-in": contract(
      "拖动源入点裁剪手柄",
      "片段或关联组已选中、轨道未锁定、项目可写且播放已暂停。",
      "拖动左手柄预览新的 source_start_us 和有效时长；按素材帧边界归一化。",
      "松开后展示全局波纹影响预览；确认后关联音视频原子更新并保存。",
      "越界、短于最小时长、关联异常、锁定冲突或保存失败时恢复操作前状态。",
      "项目只读、播放中、保存中、素材缺失或轨道锁定时禁用。",
      "拖动中按 Esc 或在影响预览中取消，恢复原源范围和片段视觉。",
      "只修改时间线片段源范围；不改原始媒体，整次拖动最多产生一条历史记录。",
    ),
    "timeline.trim-handle-out": contract(
      "拖动源出点裁剪手柄",
      "片段或关联组已选中、轨道未锁定、项目可写且播放已暂停。",
      "拖动右手柄预览新的 source_duration_us；缩短或延长会计算全局波纹。",
      "确认后关联音视频同步更新，所有未锁定轨后续片段按影响量移动并原子保存。",
      "超过素材时长、短于最小时长、区间交叉、锁定冲突或保存失败时零副作用。",
      "项目只读、播放中、保存中、素材缺失或轨道锁定时禁用。",
      "拖动中按 Esc 或取消影响预览，恢复原源范围和全部片段位置。",
      "不修改媒体文件；候选模型校验完成前不修改正式时间线。",
    ),
    "timeline.trim-source-in": contract(
      "精确输入源入点",
      "片段属性检查器打开且选中片段允许裁剪。",
      "解析 HH:MM:SS.mmm，实时校验范围并计算有效时长与全局波纹影响。",
      "合法输入启用“应用”；帧率可信时显示归一化后的合法帧位置。",
      "格式错误、负数、入点不小于出点或片段过短时就近显示原因。",
      "项目只读、轨道锁定、关联异常或保存中时输入只读。",
      "按 Esc 或“取消”恢复已保存值。",
      "输入本身只形成候选，不写项目。",
    ),
    "timeline.trim-source-out": contract(
      "精确输入源出点",
      "片段属性检查器打开且选中片段允许裁剪。",
      "解析 HH:MM:SS.mmm，校验素材总时长并计算新的片段时长。",
      "合法变化更新波纹影响摘要并启用“应用”。",
      "格式错误、超过素材时长、不大于入点或片段过短时就近显示原因。",
      "项目只读、轨道锁定、关联异常或保存中时输入只读。",
      "按 Esc 或“取消”恢复已保存值。",
      "输入阶段不修改项目、素材或播放计划。",
    ),
    "timeline.trim-apply": contract(
      "应用精确裁剪",
      "源范围有合法变化，影响预检已完成且没有区间或锁定冲突。",
      "打开全局波纹影响确认；确认后提交一个关联音视频原子命令。",
      "保存成功后刷新片段、播放计划、检查器和撤销栈。",
      "冲突时确认禁用；保存失败时模型、历史和项目文件保持操作前状态。",
      "输入未变化、格式无效、预检中、项目只读或保存中时禁用。",
      "在影响预览或检查器中取消均不提交。",
      "更新 schema v2 片段源范围和未锁定轨后续位置，不修改原视频。",
    ),
    "timeline.trim-cancel": contract(
      "取消精确裁剪",
      "片段属性检查器已打开。",
      "恢复当前正式源范围并关闭检查器。",
      "时间线、播放计划、项目文件和撤销栈完全不变。",
      "纯界面操作，无后端失败路径。",
      "检查器关闭时不可见。",
      "无需二次确认。",
      "丢弃候选输入，不写业务数据。",
    ),
    "timeline.split": contract(
      "在播放头处分割",
      "已选片段或关联组；播放暂停；播放头位于有效内部且两侧满足最小时长。",
      "左片段保留原 clip_id，右片段生成新 clip_id；关联音视频原子分割。",
      "选中右片段，播放头和滚动保持；分割不改变总时长也不触发波纹移动。",
      "边界过近、轨道锁定、素材缺失、关联异常或保存失败时不产生新片段。",
      "无选择、播放中、只读、保存中或播放头不在片段内部时禁用并说明原因。",
      "快捷键或按钮在校验失败时只显示原因，不弹出多余确认。",
      "只写 timeline schema v2；右侧关联组获得新 link_group_id，不修改原媒体。",
    ),
    "timeline.ripple-delete": contract(
      "删除片段并执行全局波纹",
      "已选片段或合法关联组，项目可写，影响预检可完成。",
      "展示删除半开区间、总时长变化、受影响轨道/片段及冲突；用户确认后提交。",
      "关联片段移除，所有未锁定轨后续片段同步前移；项目素材和真实视频保留。",
      "区间交叉、锁定轨需移动、保存失败或素材关系异常时确认禁用且正式状态不变。",
      "无选择、只读、保存中或影响仍在计算时禁用。",
      "取消按钮始终位于最右侧；取消后时间线和选择保持。",
      "形成一条可撤销命令并原子保存，不删除项目素材、中央索引或媒体文件。",
    ),
    "timeline.ripple-confirm": contract(
      "确认全局波纹操作",
      "影响预检完成且不存在区间交叉、轨道锁定或数据冲突。",
      "重新校验候选后，以单条命令执行裁剪或删除、全局移动和原子保存。",
      "成功后一次刷新画布、播放计划、检查器与撤销栈。",
      "保存或二次校验失败时正式状态零变化，并提供恢复或诊断入口。",
      "计算中或存在任一冲突时禁用。",
      "提交前可用最右侧“取消”退出。",
      "只更新项目时间线扩展和备份；不改媒体文件。",
    ),
    "timeline.ripple-locate": contract(
      "定位波纹冲突",
      "影响预览发现锁定轨道或区间交叉冲突。",
      "关闭影响预览并选中首个冲突片段，滚动到对应轨道。",
      "冲突片段和轨道锁定状态获得明确高亮。",
      "冲突对象已变化时重新预检并显示最新结果。",
      "没有冲突时不显示。",
      "只定位，不解除锁定或提交剪辑。",
      "纯查询和界面定位，不写项目。",
    ),
    "timeline.clip": contract(
      "时间线片段",
      "片段和来源素材引用存在。",
      "单击选择；双击跳到起点；拖动可调整时间或移动到同类型轨道。",
      "有效落点松开后形成一次命令、原子保存，并保持稳定 clip_id。",
      "同轨重叠、跨类型、越界或保存失败时恢复原位置并显示原因。",
      "项目只读、冲突、保存中或来源格式不支持时禁止拖动。",
      "按 Esc 或在无效位置松开时取消拖动。",
      "只修改片段轨道与时间；关联音视频按 link_group_id 同步移动。",
    ),
  };

  Object.assign(contracts, timelineContracts);

  const workspace = document.getElementById("timelineWorkspace");
  const workbench = document.getElementById("workbench");
  const projectsPanel = document.querySelector('[data-page-panel="projects"]');
  const projectLayout = document.getElementById("projectDefaultState");
  const projectDetail = document.querySelector(".project-detail-pane");
  const projectViewButtons = document.querySelectorAll("[data-project-view]");
  const materialSearch = document.getElementById("timelineMaterialSearch");
  const materialClear = document.getElementById("clearTimelineMaterialSearch");
  const materialCount = document.getElementById("timelineMaterialCount");
  const materialRailToggle = document.getElementById("collapseTimelineMaterials");
  const playButton = document.getElementById("timelinePlayPause");
  const seek = document.getElementById("timelineSeek");
  const currentTime = document.getElementById("timelineCurrentTime");
  const playheadMarker = document.getElementById("timelinePlayheadMarker");
  const saveIndicator = document.getElementById("timelineSaveIndicator");
  const grid = document.getElementById("timelineGrid");
  const zoomLabel = document.getElementById("timelineZoomLabel");
  const stateBanner = document.getElementById("timelineStateBanner");
  const previewPlaceholder = document.getElementById("timelinePreviewPlaceholder");
  const previewImage = document.getElementById("timelinePreviewImage");
  const previewBadge = document.querySelector(".timeline-preview-badge");
  const audioState = document.getElementById("timelineAudioState");
  const stateAction = document.getElementById("timelineStateAction");
  const focusButton = document.getElementById("toggleTimelineFocus");
  const previewMaximizeButton = document.getElementById("toggleTimelinePreviewMaximize");
  const previewZone = document.querySelector(".timeline-preview-zone");
  const splitter = document.getElementById("timelineSplitter");
  const timelineEditor = document.querySelector(".timeline-editor");
  const timelineTitlebar = document.querySelector(".timeline-window-titlebar");
  const timelineCommandbar = document.querySelector(".timeline-window-commandbar");
  const exitTimelineButton = document.getElementById("exitTimelineWorkspace");
  const materialWorkbenchButton = document.getElementById("openMaterialWorkbench");
  const recordFromTimelineButton = document.getElementById("recordFromTimeline");
  const closeTimelineButton = document.getElementById("closeTimelineWorkspace");
  const splitButton = document.getElementById("splitClipAtPlayhead");
  const deleteClipButton = document.getElementById("deleteTimelineClip");
  const inspectorToggle = document.getElementById("toggleClipInspector");
  const clipInspector = document.getElementById("clipInspector");
  const closeInspectorButton = document.getElementById("closeClipInspector");
  const trimSourceIn = document.getElementById("trimSourceIn");
  const trimSourceOut = document.getElementById("trimSourceOut");
  const applyTrimButton = document.getElementById("applyTrimValues");
  const cancelTrimButton = document.getElementById("cancelTrimValues");
  const timelineClipDetail = document.getElementById("timelineClipDetail");
  let projectView = "timeline";
  let playing = false;
  let playbackTimer = null;
  let zoom = 100;
  let draggedClip = null;
  let currentTimelineState = "default";
  let previewSize = null;
  let splitterPointerId = null;
  let splitterStartY = 0;
  let splitterStartSize = 0;
  let trimGesture = null;
  let selectedClipBeforeEdit = null;

  function formatTime(milliseconds) {
    const safe = Math.max(0, Math.round(milliseconds));
    const hours = Math.floor(safe / 3600000);
    const minutes = Math.floor((safe % 3600000) / 60000);
    const seconds = Math.floor((safe % 60000) / 1000);
    const millis = safe % 1000;
    return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":")
      + `.${String(millis).padStart(3, "0")}`;
  }

  function parseTime(text) {
    const matched = /^(\d{2}):([0-5]\d):([0-5]\d)\.(\d{3})$/.exec(text.trim());
    if (!matched) return null;
    const [, hours, minutes, seconds, millis] = matched;
    return (((Number(hours) * 60 + Number(minutes)) * 60 + Number(seconds)) * 1000) + Number(millis);
  }

  function getSelectedClip() {
    return document.querySelector(".timeline-clip.is-selected");
  }

  function clipStartMs(clip) {
    return (Number(clip.dataset.start || 0) / 100) * Number(seek.max);
  }

  function clipDurationMs(clip) {
    return (Number(clip.dataset.duration || 0) / 100) * Number(seek.max);
  }

  function linkedClipFor(clip) {
    const pairs = {
      "clip-v2": "clip-a2",
      "clip-a2": "clip-v2",
      "clip-v2-r": "clip-a2-r",
      "clip-a2-r": "clip-v2-r",
      "clip-v1-a": "clip-a1",
      "clip-a1": "clip-v1-a",
    };
    return pairs[clip?.dataset.clipId]
      ? document.querySelector(`[data-clip-id="${pairs[clip.dataset.clipId]}"]`)
      : null;
  }

  function isClipLocked(clip) {
    return clip?.closest(".timeline-track-row")?.dataset.locked === "true";
  }

  function setTrackLockVisual(row, locked) {
    const lockButton = row.querySelector(".track-lock");
    const nameButton = row.querySelector(".track-name");
    const status = row.querySelector(".track-status");
    row.dataset.locked = locked ? "true" : "false";
    row.classList.toggle("is-locked", locked);
    lockButton.setAttribute("aria-pressed", locked ? "true" : "false");
    lockButton.setAttribute("aria-label", `${locked ? "解锁" : "锁定"}${nameButton.textContent.trim()}`);
    lockButton.title = locked ? "解锁轨道" : "锁定轨道";
    lockButton.querySelector("use").setAttribute("href", locked ? "#i-lock" : "#i-unlock");
    status.dataset.previousText = status.dataset.previousText || status.textContent;
    status.textContent = locked ? "已锁定" : status.dataset.previousText;
  }

  function updateEditControls() {
    const clip = getSelectedClip();
    const editable = Boolean(clip)
      && !playing
      && !isClipLocked(clip)
      && !workspace.classList.contains("is-readonly")
      && !["saving", "save-failed", "save-rollback", "conflict", "corrupt", "unknown"].includes(currentTimelineState);
    const start = clip ? clipStartMs(clip) : 0;
    const end = clip ? start + clipDurationMs(clip) : 0;
    const playhead = Number(seek.value);
    splitButton.disabled = !editable || playhead <= start + 34 || playhead >= end - 34;
    deleteClipButton.disabled = !editable;
    inspectorToggle.disabled = !editable;
    if (clip && isClipLocked(clip)) {
      splitButton.title = "轨道已锁定，不能分割";
      deleteClipButton.title = "轨道已锁定，不能删除片段";
      inspectorToggle.title = "轨道已锁定，不能编辑片段属性";
    } else {
      splitButton.title = "在播放头处分割 Ctrl+B";
      deleteClipButton.title = "删除片段 Delete";
      inspectorToggle.title = "打开片段属性";
    }
  }

  function updatePlayhead(value) {
    const normalized = Math.max(0, Math.min(Number(seek.max), Number(value)));
    seek.value = String(normalized);
    currentTime.textContent = formatTime(normalized);
    const percent = (normalized / Number(seek.max)) * 100;
    playheadMarker.style.left = `${percent}%`;
    document.querySelectorAll(".timeline-playhead-line").forEach((line) => {
      line.style.left = `${percent}%`;
    });
    updateEditControls();
  }

  function stopPlayback() {
    playing = false;
    if (playbackTimer) {
      window.clearInterval(playbackTimer);
      playbackTimer = null;
    }
    playButton.innerHTML = '<svg><use href="#i-play"></use></svg>';
    playButton.setAttribute("aria-label", "播放时间线");
    playButton.title = "播放时间线";
    updateEditControls();
  }

  function syncTimelineShell() {
    const projectsActive = projectsPanel.classList.contains("is-active");
    const timelineWindowActive = projectsActive && projectView === "timeline";
    workbench.classList.toggle("timeline-editing-shell", timelineWindowActive);
    document.body.classList.toggle("timeline-window-open", timelineWindowActive);
    if (timelineWindowActive) {
      const prototypeToolbar = document.querySelector(".prototype-toolbar");
      const top = prototypeToolbar ? prototypeToolbar.getBoundingClientRect().bottom : 0;
      document.documentElement.style.setProperty("--timeline-window-top", `${Math.max(0, Math.round(top))}px`);
      window.requestAnimationFrame(() => setPreviewSize(previewSize ?? defaultPreviewSize()));
    }
  }

  function defaultPreviewSize() {
    if (!workspace.clientHeight) return window.innerWidth <= 980 ? 220 : 366;
    const bounds = previewSizeBounds();
    const preferred = Math.round(bounds.availableHeight * 0.68);
    return Math.max(bounds.minimum, Math.min(bounds.maximum, preferred));
  }

  function outerHeight(element) {
    if (!element || element.hidden || window.getComputedStyle(element).display === "none") return 0;
    const style = window.getComputedStyle(element);
    return element.offsetHeight + Number.parseFloat(style.marginTop || "0") + Number.parseFloat(style.marginBottom || "0");
  }

  function previewSizeBounds() {
    const previewMinimum = Number.parseFloat(window.getComputedStyle(previewZone).minHeight || "180");
    const editorStyle = window.getComputedStyle(timelineEditor);
    const editorMinimum = Number.parseFloat(editorStyle.minHeight || "260");
    const fixedHeight = outerHeight(timelineTitlebar)
      + outerHeight(timelineCommandbar)
      + outerHeight(stateBanner)
      + outerHeight(splitter)
      + Number.parseFloat(editorStyle.marginTop || "0")
      + Number.parseFloat(editorStyle.marginBottom || "0");
    const availableHeight = Math.max(previewMinimum + editorMinimum, workspace.clientHeight - fixedHeight);
    const maximum = Math.max(previewMinimum, availableHeight - editorMinimum);
    return {
      minimum: Math.round(previewMinimum),
      maximum: Math.round(maximum),
      availableHeight: Math.round(availableHeight),
    };
  }

  function setPreviewSize(value) {
    if (!Number.isFinite(Number(value)) || !workspace.clientHeight) return;
    const bounds = previewSizeBounds();
    previewSize = Math.max(bounds.minimum, Math.min(bounds.maximum, Math.round(Number(value))));
    workspace.style.setProperty("--timeline-preview-size", `${previewSize}px`);
    splitter.setAttribute("aria-valuemin", String(bounds.minimum));
    splitter.setAttribute("aria-valuemax", String(bounds.maximum));
    splitter.setAttribute("aria-valuenow", String(previewSize));
    splitter.title = `预览高度 ${previewSize}px；拖动调整，双击恢复默认`;
  }

  function setPreviewMaximized(maximized, announce = true) {
    workspace.classList.toggle("preview-maximized", maximized);
    previewMaximizeButton.classList.toggle("is-active", maximized);
    previewMaximizeButton.setAttribute("aria-pressed", maximized ? "true" : "false");
    previewMaximizeButton.setAttribute("aria-label", maximized ? "恢复视频预览分栏" : "放大视频预览");
    previewMaximizeButton.title = maximized ? "恢复视频预览分栏" : "放大视频预览";
    previewMaximizeButton.querySelector("use").setAttribute("href", maximized ? "#i-timeline" : "#i-fit");
    if (!maximized) window.requestAnimationFrame(() => setPreviewSize(previewSize ?? defaultPreviewSize()));
    if (announce) {
      showToast(
        maximized ? "视频预览已放大" : "已恢复预览与时间线分栏",
        maximized
          ? "预览占满剩余工作区并保持完整宽高比；再次点击右上角按钮即可恢复。"
          : `已恢复上次预览高度 ${previewSize ?? defaultPreviewSize()}px，仍可拖动分隔条调整。`,
      );
    }
  }

  function startPlayback() {
    if (workspace.classList.contains("is-empty") || currentTimelineState === "corrupt" || currentTimelineState === "unknown") {
      showToast("无法开始播放", "时间线为空或当前项目需要先完成恢复。", "warning");
      return;
    }
    playing = true;
    playButton.innerHTML = '<svg><use href="#i-pause"></use></svg>';
    playButton.setAttribute("aria-label", "暂停时间线");
    playButton.title = "暂停时间线";
    updateEditControls();
    if (Number(seek.value) >= Number(seek.max)) updatePlayhead(0);
    playbackTimer = window.setInterval(() => {
      const next = Number(seek.value) + 80;
      if (next >= Number(seek.max)) {
        updatePlayhead(Number(seek.max));
        stopPlayback();
        return;
      }
      updatePlayhead(next);
    }, 80);
  }

  function setProjectView(view) {
    projectView = view;
    stopPlayback();
    const timelineActive = view === "timeline";
    projectDetail.classList.toggle("timeline-mode", timelineActive);
    projectLayout.classList.toggle("timeline-active", timelineActive);
    projectViewButtons.forEach((button) => {
      const active = button.dataset.projectView === view;
      button.classList.toggle("is-active", active);
      if (button.getAttribute("role") === "tab") {
        button.setAttribute("aria-selected", active ? "true" : "false");
      }
    });
    document.getElementById("pageSubtitle").textContent = timelineActive
      ? "在项目内编排视频与音频轨道，并完成最小播放闭环。"
      : "管理项目素材引用、静态首帧和文件恢复状态。";
    syncTimelineShell();
  }

  function setSaveIndicator(mode, text) {
    saveIndicator.className = `timeline-save-indicator${mode === "saving" ? " is-saving" : mode === "error" ? " is-error" : ""}`;
    saveIndicator.querySelector("span").textContent = text;
  }

  function simulateSave(successText = "时间线已自动保存") {
    setSaveIndicator("saving", "正在保存…");
    window.setTimeout(() => {
      if (currentTimelineState === "save-failed") {
        setSaveIndicator("error", "保存失败，已回滚");
        showToast("时间线保存失败", "界面和内存已恢复到操作前状态。", "warning");
        return;
      }
      setSaveIndicator("ready", "已自动保存");
      showToast(successText, "project.qrproj 已原子写入，并保留上一份有效备份。", "success");
    }, 480);
  }

  function applyClipGeometry() {
    document.querySelectorAll(".timeline-clip").forEach((clip) => {
      clip.style.left = `${Number(clip.dataset.start || 0)}%`;
      clip.style.width = `${Number(clip.dataset.duration || 10)}%`;
    });
  }

  function updateMaterialFilter() {
    const query = materialSearch.value.trim().toLocaleLowerCase("zh-CN");
    let visible = 0;
    document.querySelectorAll(".timeline-material-card").forEach((card) => {
      const matched = !query || card.dataset.searchText.toLocaleLowerCase("zh-CN").includes(query);
      card.classList.toggle("is-filtered", !matched);
      if (matched) visible += 1;
    });
    materialCount.textContent = query ? `匹配 ${visible} / 共 4 个` : "3 个可用 · 1 个缺失";
    materialClear.disabled = !query;
  }

  function selectClip(clip) {
    document.querySelectorAll(".timeline-clip").forEach((node) => node.classList.toggle("is-selected", node === clip));
    const label = clip.querySelector("strong")?.textContent || "未命名片段";
    const summary = document.getElementById("timelineClipSummary");
    summary.querySelector("strong").textContent = label;
    summary.querySelector(".badge").textContent = clip.closest(".timeline-track-row")?.querySelector(".track-name")?.textContent || "片段";
    const sourceStart = Number(clip.dataset.sourceStartMs || 0);
    const sourceEnd = Number(clip.dataset.sourceEndMs || sourceStart + clipDurationMs(clip));
    timelineClipDetail.textContent = clip.classList.contains("clip-audio")
      ? `源 ${formatTime(sourceStart)}–${formatTime(sourceEnd)} · 关联音视频原子编辑`
      : `源 ${formatTime(sourceStart)}–${formatTime(sourceEnd)} · 双击跳到起点`;
    if (!clipInspector.hidden) loadInspectorFromClip(clip);
    updateEditControls();
  }

  function loadInspectorFromClip(clip) {
    if (!clip) return;
    selectedClipBeforeEdit = clip;
    const sourceStart = Number(clip.dataset.sourceStartMs || 0);
    const sourceEnd = Number(clip.dataset.sourceEndMs || sourceStart + clipDurationMs(clip));
    const materialDuration = Number(clip.dataset.materialDurationMs || Math.max(sourceEnd, Number(seek.max)));
    trimSourceIn.value = formatTime(sourceStart);
    trimSourceOut.value = formatTime(sourceEnd);
    trimSourceIn.dataset.originalValue = trimSourceIn.value;
    trimSourceOut.dataset.originalValue = trimSourceOut.value;
    trimSourceOut.dataset.materialDurationMs = String(materialDuration);
    document.getElementById("inspectorTimelineStart").textContent = formatTime(clipStartMs(clip));
    document.getElementById("inspectorDuration").textContent = formatTime(sourceEnd - sourceStart);
    document.querySelector(".clip-inspector > header span").textContent =
      `${clip.querySelector("strong")?.textContent || "未命名片段"} · ${clip.closest(".timeline-track-row")?.querySelector(".track-name")?.textContent || "轨道"}`;
    document.getElementById("inspectorRippleImpact").querySelector("span").textContent =
      "当前无变化；修改后将预检全部未锁定轨道。";
    [trimSourceIn, trimSourceOut].forEach((input) => {
      input.closest(".inspector-field").classList.remove("has-error");
    });
    applyTrimButton.disabled = true;
  }

  function setInspectorOpen(open) {
    const clip = getSelectedClip();
    if (open && !clip) {
      showToast("请先选择片段", "片段属性只作用于当前选中片段或关联音视频组。", "warning");
      return;
    }
    clipInspector.hidden = !open;
    inspectorToggle.setAttribute("aria-expanded", open ? "true" : "false");
    inspectorToggle.classList.toggle("is-active", open);
    if (open) {
      loadInspectorFromClip(clip);
      trimSourceIn.focus();
    }
  }

  function validateInspector() {
    const clip = selectedClipBeforeEdit || getSelectedClip();
    if (!clip) return null;
    const sourceIn = parseTime(trimSourceIn.value);
    const sourceOut = parseTime(trimSourceOut.value);
    const materialDuration = Number(trimSourceOut.dataset.materialDurationMs || 0);
    const inField = trimSourceIn.closest(".inspector-field");
    const outField = trimSourceOut.closest(".inspector-field");
    inField.classList.toggle("has-error", sourceIn === null || sourceIn < 0);
    outField.classList.toggle(
      "has-error",
      sourceOut === null
        || sourceOut > materialDuration
        || (sourceIn !== null && sourceOut <= sourceIn)
        || (sourceIn !== null && sourceOut - sourceIn < 34),
    );
    document.getElementById("trimSourceInError").textContent =
      sourceIn === null ? "请输入 HH:MM:SS.mmm" : "按素材帧边界归一化";
    if (sourceOut === null) {
      document.getElementById("trimSourceOutError").textContent = "请输入 HH:MM:SS.mmm";
    } else if (sourceOut > materialDuration) {
      document.getElementById("trimSourceOutError").textContent = `不得超过素材总时长 ${formatTime(materialDuration)}`;
    } else if (sourceIn !== null && sourceOut <= sourceIn) {
      document.getElementById("trimSourceOutError").textContent = "源出点必须晚于源入点";
    } else if (sourceIn !== null && sourceOut - sourceIn < 34) {
      document.getElementById("trimSourceOutError").textContent = "视频片段至少保留一个完整帧";
    } else {
      document.getElementById("trimSourceOutError").textContent = `不得超过素材总时长 ${formatTime(materialDuration)}`;
    }
    const valid = sourceIn !== null
      && sourceOut !== null
      && sourceIn >= 0
      && sourceOut <= materialDuration
      && sourceOut > sourceIn
      && sourceOut - sourceIn >= 34;
    const changed = valid
      && (trimSourceIn.value !== trimSourceIn.dataset.originalValue
        || trimSourceOut.value !== trimSourceOut.dataset.originalValue);
    applyTrimButton.disabled = !changed || isClipLocked(clip);
    if (valid) {
      const oldDuration = Number(clip.dataset.sourceEndMs || 0) - Number(clip.dataset.sourceStartMs || 0);
      const newDuration = sourceOut - sourceIn;
      const delta = newDuration - oldDuration;
      document.getElementById("inspectorDuration").textContent = formatTime(newDuration);
      document.getElementById("inspectorRippleImpact").querySelector("span").textContent = delta === 0
        ? "源范围变化但时长不变；关联音视频同步更新，不移动后续片段。"
        : `总时长${delta > 0 ? "增加" : "减少"} ${formatTime(Math.abs(delta))}；应用前检查全部未锁定轨道。`;
    }
    return valid ? { clip, sourceIn, sourceOut } : null;
  }

  function rippleTargets(clip) {
    return [clip, linkedClipFor(clip)].filter(Boolean);
  }

  function calculateRippleImpact(clip, operation, newDurationMs = null) {
    const targets = rippleTargets(clip);
    const targetSet = new Set(targets);
    const timelineStart = Math.round(clipStartMs(clip));
    const oldDuration = Math.round(clipDurationMs(clip));
    const oldEnd = timelineStart + oldDuration;
    const nextDuration = operation === "delete" ? 0 : Number(newDurationMs);
    const delta = Math.round(nextDuration - oldDuration);
    const rangeStart = operation === "delete"
      ? timelineStart
      : delta < 0 ? timelineStart + nextDuration : oldEnd;
    const rangeEnd = operation === "delete" || delta < 0 ? oldEnd : oldEnd;
    const moveFrom = operation === "delete" || delta < 0 ? rangeEnd : oldEnd;
    const affected = [];
    const conflicts = [];
    const affectedTracks = new Set();

    document.querySelectorAll(".timeline-clip").forEach((other) => {
      if (targetSet.has(other)) return;
      const start = Math.round(clipStartMs(other));
      const end = start + Math.round(clipDurationMs(other));
      const row = other.closest(".timeline-track-row");
      const trackName = row.querySelector(".track-name")?.textContent.trim() || "未命名轨道";
      const clipName = other.querySelector("strong")?.textContent.trim() || "未命名片段";
      const intersectsDeletedRange = delta < 0 && start < rangeEnd && end > rangeStart;
      const crossesInsertPoint = delta > 0 && start < oldEnd && end > oldEnd;
      if (intersectsDeletedRange || crossesInsertPoint) {
        conflicts.push({
          clip: other,
          row,
          label: `${trackName} / ${clipName} 跨越${delta < 0 ? "删除区间" : "插入点"}`,
        });
        return;
      }
      if (start >= moveFrom && delta !== 0) {
        if (row.dataset.locked === "true") {
          conflicts.push({
            clip: other,
            row,
            label: `${trackName} 已锁定，${clipName} 不能随全局波纹移动`,
          });
          return;
        }
        affected.push(other);
        affectedTracks.add(row.dataset.trackId);
      }
    });

    return {
      operation,
      targets,
      delta,
      rangeStart,
      rangeEnd,
      moveFrom,
      affected,
      affectedTrackCount: affectedTracks.size,
      conflicts,
      oldDuration,
      nextDuration,
      timelineStart,
    };
  }

  function rippleImpactMarkup(impact) {
    const operationLabel = impact.operation === "delete"
      ? "删除片段并波纹"
      : impact.delta < 0 ? "缩短片段并波纹" : impact.delta > 0 ? "延长片段并波纹" : "更新源范围";
    const totalAfter = Math.max(0, Number(seek.max) + impact.delta);
    const conflictItems = impact.conflicts
      .map((item) => `<li>${item.label}</li>`)
      .join("");
    return `
      <div class="ripple-impact-grid">
        <div><span>操作</span><strong>${operationLabel}</strong></div>
        <div><span>${impact.delta > 0 ? "插入点" : "删除区间"}</span><strong>${impact.delta > 0 ? formatTime(impact.moveFrom) : `${formatTime(impact.rangeStart)}–${formatTime(impact.rangeEnd)}`}</strong></div>
        <div><span>总时长</span><strong>${formatTime(Number(seek.max))} → ${formatTime(totalAfter)}</strong></div>
        <div><span>受影响轨道</span><strong>${impact.affectedTrackCount} 条</strong></div>
        <div><span>移动片段</span><strong>${impact.affected.length} 个</strong></div>
        <div><span>关联操作目标</span><strong>${impact.targets.length} 个</strong></div>
      </div>
      ${impact.conflicts.length
        ? `<ul class="ripple-conflict-list">${conflictItems}</ul>`
        : '<div class="modal-detail">预检通过：没有区间交叉或锁定冲突。提交前会再次校验。</div>'}
    `;
  }

  function restoreTrimPreview() {
    if (!trimGesture) return;
    const { clip, linked, originalDuration, originalLinkedDuration } = trimGesture;
    clip.style.width = `${originalDuration}%`;
    clip.classList.remove("is-trimming", "is-trim-invalid");
    if (linked) {
      linked.style.width = `${originalLinkedDuration}%`;
      linked.classList.remove("is-trimming", "is-trim-invalid");
    }
    trimGesture = null;
  }

  function openRipplePreview(impact, onConfirm) {
    const hasConflict = impact.conflicts.length > 0;
    showModal({
      title: hasConflict ? "全局波纹存在冲突" : "确认全局波纹影响",
      text: hasConflict
        ? "当前候选不能安全提交。请先处理锁定轨道或区间交叉，再重新执行。"
        : "系统已在候选模型中计算全部轨道；确认后才会形成一条命令并原子保存。",
      detailHtml: rippleImpactMarkup(impact),
      icon: hasConflict ? "danger" : "warning",
      wide: true,
      actions: [
        ...(hasConflict
          ? [{
              label: "定位首个冲突",
              contract: "timeline.ripple-locate",
              onClick: () => {
                const first = impact.conflicts[0];
                closeModal();
                restoreTrimPreview();
                selectClip(first.clip);
                first.row.scrollIntoView({ block: "nearest", inline: "nearest" });
                showToast("已定位波纹冲突", first.label, "warning");
              },
            }]
          : []),
        {
          label: impact.operation === "delete" ? "从时间线删除并波纹" : "确认并应用",
          kind: "button-primary",
          contract: "timeline.ripple-confirm",
          onClick: () => {
            if (hasConflict) return;
            closeModal();
            onConfirm();
          },
        },
        {
          label: "取消",
          contract: "modal.cancel",
          onClick: () => {
            closeModal();
            restoreTrimPreview();
            showToast("已取消剪辑", "项目、时间线、播放计划和撤销栈均未改变。");
          },
        },
      ],
      afterOpen: () => {
        const confirm = document.querySelector('#modalActions [data-contract="timeline.ripple-confirm"]');
        if (confirm) confirm.disabled = hasConflict;
      },
    });
  }

  function shiftRippleFollowers(impact) {
    if (impact.delta === 0) return;
    const shiftPercent = (impact.delta / Number(seek.max)) * 100;
    impact.affected.forEach((clip) => {
      clip.dataset.start = String(Number(clip.dataset.start || 0) + shiftPercent);
    });
  }

  function rescaleClipPercentages(oldDuration, newDuration) {
    if (oldDuration === newDuration || newDuration <= 0) return;
    document.querySelectorAll(".timeline-clip").forEach((clip) => {
      const absoluteStart = (Number(clip.dataset.start || 0) / 100) * oldDuration;
      const absoluteDuration = (Number(clip.dataset.duration || 0) / 100) * oldDuration;
      clip.dataset.start = String((absoluteStart / newDuration) * 100);
      clip.dataset.duration = String((absoluteDuration / newDuration) * 100);
    });
  }

  function applyTrim(clip, sourceIn, sourceOut, impact) {
    const oldTimelineDuration = Number(seek.max);
    const newDuration = sourceOut - sourceIn;
    const newDurationPercent = (newDuration / oldTimelineDuration) * 100;
    rippleTargets(clip).forEach((target) => {
      target.dataset.sourceStartMs = String(sourceIn);
      target.dataset.sourceEndMs = String(sourceOut);
      target.dataset.duration = String(newDurationPercent);
      target.style.width = `${newDurationPercent}%`;
      const detail = target.querySelector(".clip-copy small");
      if (detail) detail.textContent = `${formatTime(sourceIn)} · ${Math.round(newDuration / 1000)} 秒`;
      target.classList.remove("is-trimming", "is-trim-invalid");
    });
    shiftRippleFollowers(impact);
    const newTimelineDuration = Math.max(1000, oldTimelineDuration + impact.delta);
    rescaleClipPercentages(oldTimelineDuration, newTimelineDuration);
    seek.max = String(newTimelineDuration);
    document.querySelector(".timeline-duration").textContent = formatTime(Number(seek.max));
    applyClipGeometry();
    trimGesture = null;
    setInspectorOpen(false);
    selectClip(clip);
    document.getElementById("timelineUndo").disabled = false;
    simulateSave("裁剪和全局波纹已自动保存");
  }

  function deleteWithRipple(clip, impact) {
    const oldTimelineDuration = Number(seek.max);
    shiftRippleFollowers(impact);
    rippleTargets(clip).forEach((target) => target.remove());
    const newTimelineDuration = Math.max(1000, oldTimelineDuration + impact.delta);
    rescaleClipPercentages(oldTimelineDuration, newTimelineDuration);
    seek.max = String(newTimelineDuration);
    document.querySelector(".timeline-duration").textContent = formatTime(Number(seek.max));
    applyClipGeometry();
    setInspectorOpen(false);
    const fallback = document.querySelector(".timeline-clip");
    if (fallback) selectClip(fallback);
    document.getElementById("timelineUndo").disabled = false;
    simulateSave("片段删除和全局波纹已自动保存");
  }

  function setPreviewError(title, text, show = true) {
    previewPlaceholder.hidden = !show;
    previewImage.hidden = show;
    previewBadge.hidden = show;
    document.getElementById("timelinePreviewPlaceholderTitle").textContent = title;
    document.getElementById("timelinePreviewPlaceholderText").textContent = text;
  }

  function resetTimelineVisualState() {
    stopPlayback();
    workspace.classList.remove("is-readonly", "is-empty");
    stateBanner.hidden = true;
    stateBanner.className = "timeline-state-banner";
    setPreviewError("", "", false);
    audioState.className = "timeline-audio-state";
    audioState.innerHTML = '<svg><use href="#i-audio"></use></svg>音频正常';
    document.querySelectorAll(".timeline-clip").forEach((clip) => clip.classList.remove("is-missing", "is-error"));
    document.querySelectorAll(".timeline-track-row").forEach((row) => setTrackLockVisual(row, false));
    setInspectorOpen(false);
    setSaveIndicator("ready", "已自动保存");
    playButton.disabled = false;
    updateEditControls();
  }

  function showTimelineBanner(title, text, action, kind = "warning") {
    stateBanner.hidden = false;
    stateBanner.className = `timeline-state-banner${kind === "danger" ? " is-danger" : kind === "info" ? " is-info" : ""}`;
    document.getElementById("timelineStateTitle").textContent = title;
    document.getElementById("timelineStateText").textContent = text;
    stateAction.textContent = action;
  }

  function applyTimelineState(state) {
    currentTimelineState = state;
    setProjectView("timeline");
    resetTimelineVisualState();

    if (state === "playing") {
      startPlayback();
    } else if (state === "buffering") {
      showTimelineBanner("正在准备播放", "正在预加载当前视频和两路音频；播放头暂不推进。", "取消播放", "info");
      playButton.disabled = true;
    } else if (state === "missing") {
      const clip = document.querySelector('[data-clip-id="clip-v1-b"]');
      clip.classList.add("is-missing");
      selectClip(clip);
      setPreviewError("素材文件缺失", "片段身份和时间位置已保留。重新定位成功后所有同素材片段自动恢复。");
      showTimelineBanner("时间线包含缺失素材", "窗口选择流程.mp4 已移动或删除，播放到该片段时显示错误占位。", "重新定位", "danger");
    } else if (state === "decode-error") {
      const clip = document.querySelector('[data-clip-id="clip-v2"]');
      clip.classList.add("is-error");
      selectClip(clip);
      setPreviewError("最高视频轨解码失败", "按固定规则不露出下层画面；其他片段与播放时钟继续。");
      showTimelineBanner("片段解码失败", "项目数据保持完整，可重试播放或查看本地诊断。", "重试播放", "danger");
    } else if (state === "audio-unavailable") {
      audioState.className = "timeline-audio-state is-warning";
      audioState.innerHTML = '<svg><use href="#i-alert"></use></svg>无声预览';
      showTimelineBanner("音频设备不可用", "请选择无声继续或取消播放；本项目会话内不重复弹窗。", "无声继续");
    } else if (state === "saving") {
      setSaveIndicator("saving", "正在保存…");
      showTimelineBanner("正在原子保存时间线", "结构操作暂时锁定；播放、页面关闭和项目切换等待事务结束。", "等待保存", "info");
      workspace.classList.add("is-readonly");
      playButton.disabled = true;
    } else if (state === "save-failed") {
      setSaveIndicator("error", "保存失败，已回滚");
      showTimelineBanner("时间线保存失败", "本次操作未生效，界面已回到最后一次成功保存状态。", "重新保存", "danger");
    } else if (state === "readonly") {
      workspace.classList.add("is-readonly");
      showTimelineBanner("项目已归档，时间线为只读", "可以查看和播放；恢复项目后才能调整轨道或片段。", "恢复项目");
    } else if (state === "corrupt") {
      workspace.classList.add("is-readonly");
      playButton.disabled = true;
      setPreviewError("时间线数据损坏", "项目其他数据保持可读。可查看原始数据或从有效备份恢复。");
      showTimelineBanner("时间线扩展块无法解析", "QuickRec 不会静默创建空时间线或覆盖原项目文件。", "查看备份", "danger");
    } else if (state === "unknown") {
      workspace.classList.add("is-readonly");
      playButton.disabled = true;
      setPreviewError("时间线版本高于当前支持范围", "当前版本只读保留未知扩展，升级 QuickRec 后再继续编辑。");
      showTimelineBanner("未知时间线版本", "项目可以查看但不能编辑，未知字段会原样保留。", "查看详情");
    } else if (state === "conflict") {
      workspace.classList.add("is-readonly");
      showTimelineBanner("项目文件已在外部修改", "暂停播放并停止写入。重新加载前不会覆盖外部版本。", "重新加载", "danger");
    } else if (state === "empty") {
      workspace.classList.add("is-empty");
      playButton.disabled = true;
      updatePlayhead(0);
      showTimelineBanner("时间线为空", "从项目素材区选择素材并加入，系统会按默认规则建立视频和关联音频片段。", "查看素材");
    } else if (state === "trimming") {
      const clip = document.querySelector('[data-clip-id="clip-v2"]');
      selectClip(clip);
      setInspectorOpen(true);
      clip.classList.add("is-trimming");
      trimSourceOut.value = "00:00:29.000";
      validateInspector();
      showTimelineBanner("正在预览裁剪候选", "正式数据尚未改变；应用前仍需完成全局波纹影响预检。", "取消候选", "info");
    } else if (state === "ripple-preview") {
      const clip = document.querySelector('[data-clip-id="clip-v2"]');
      selectClip(clip);
      const impact = calculateRippleImpact(clip, "trim", 17000);
      openRipplePreview(impact, () => applyTrim(clip, 12000, 29000, impact));
    } else if (state === "ripple-conflict") {
      const clip = document.querySelector('[data-clip-id="clip-v2"]');
      const lockedRow = document.querySelector('[data-track-id="video-1"]');
      setTrackLockVisual(lockedRow, true);
      selectClip(clip);
      const impact = calculateRippleImpact(clip, "delete");
      openRipplePreview(impact, () => deleteWithRipple(clip, impact));
    } else if (state === "track-locked") {
      const row = document.querySelector('[data-track-id="video-2"]');
      setTrackLockVisual(row, true);
      selectClip(row.querySelector(".timeline-clip"));
      showTimelineBanner("视频 2 已锁定", "该轨片段不能移动、裁剪、分割或删除；全局波纹也不会越过锁定约束。", "查看锁定规则", "info");
    } else if (state === "save-rollback") {
      setSaveIndicator("error", "保存失败，已回滚");
      workspace.classList.add("is-readonly");
      showTimelineBanner(
        "剪辑保存失败，正式状态已回滚",
        "模型、项目文件、撤销栈和播放计划保持操作前状态；可重试同一候选或打开诊断。",
        "重试保存",
        "danger",
      );
    }
    window.requestAnimationFrame(() => setPreviewSize(previewSize ?? defaultPreviewSize()));
  }

  function registerNewContracts(root = document) {
    root.querySelectorAll("[data-contract]").forEach((element) => {
      if (element.dataset.contractIndex) return;
      registerContractElement(element);
    });
  }

  registerNewContracts();

  inspectorToggle.addEventListener("click", () => setInspectorOpen(clipInspector.hidden));
  closeInspectorButton.addEventListener("click", () => setInspectorOpen(false));
  cancelTrimButton.addEventListener("click", () => setInspectorOpen(false));
  [trimSourceIn, trimSourceOut].forEach((input) => {
    input.addEventListener("input", validateInspector);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !applyTrimButton.disabled) {
        event.preventDefault();
        applyTrimButton.click();
      } else if (event.key === "Escape") {
        event.preventDefault();
        setInspectorOpen(false);
      }
    });
  });
  applyTrimButton.addEventListener("click", () => {
    const candidate = validateInspector();
    if (!candidate) return;
    const nextDuration = candidate.sourceOut - candidate.sourceIn;
    const impact = calculateRippleImpact(candidate.clip, "trim", nextDuration);
    openRipplePreview(impact, () => applyTrim(candidate.clip, candidate.sourceIn, candidate.sourceOut, impact));
  });

  deleteClipButton.addEventListener("click", () => {
    const clip = getSelectedClip();
    if (!clip || isClipLocked(clip)) {
      showToast("无法删除片段", "请先选择未锁定轨道上的有效片段。", "warning");
      return;
    }
    const impact = calculateRippleImpact(clip, "delete");
    openRipplePreview(impact, () => deleteWithRipple(clip, impact));
  });

  splitButton.addEventListener("click", () => {
    const clip = getSelectedClip();
    if (!clip || isClipLocked(clip) || playing) {
      showToast("当前位置不能分割", "请选择未锁定轨道上的片段并先暂停播放。", "warning");
      return;
    }
    const start = clipStartMs(clip);
    const duration = clipDurationMs(clip);
    const end = start + duration;
    const splitAt = Number(seek.value);
    if (splitAt <= start + 34 || splitAt >= end - 34) {
      showToast("播放头太靠近片段边界", "分割后的左右片段都必须至少保留一个完整帧。", "warning");
      return;
    }
    const linked = linkedClipFor(clip);
    const targets = [clip, linked].filter(Boolean);
    const rightClips = [];
    targets.forEach((target) => {
      const targetStart = clipStartMs(target);
      const targetDuration = clipDurationMs(target);
      const targetEnd = targetStart + targetDuration;
      const splitOffset = splitAt - targetStart;
      const leftPercent = (splitOffset / Number(seek.max)) * 100;
      const rightPercent = ((targetEnd - splitAt) / Number(seek.max)) * 100;
      const right = target.cloneNode(true);
      right.dataset.clipId = `${target.dataset.clipId}-r`;
      right.dataset.start = String((splitAt / Number(seek.max)) * 100);
      right.dataset.duration = String(rightPercent);
      const oldSourceStart = Number(target.dataset.sourceStartMs || 0);
      const oldSourceEnd = Number(target.dataset.sourceEndMs || oldSourceStart + targetDuration);
      const rightSourceStart = oldSourceStart + splitOffset;
      right.dataset.sourceStartMs = String(rightSourceStart);
      right.dataset.sourceEndMs = String(oldSourceEnd);
      target.dataset.duration = String(leftPercent);
      target.dataset.sourceEndMs = String(rightSourceStart);
      const leftDetail = target.querySelector(".clip-copy small");
      const rightDetail = right.querySelector(".clip-copy small");
      if (leftDetail) leftDetail.textContent = `${formatTime(oldSourceStart)} · ${Math.max(1, Math.round(splitOffset / 1000))} 秒`;
      if (rightDetail) rightDetail.textContent = `${formatTime(rightSourceStart)} · ${Math.max(1, Math.round((targetEnd - splitAt) / 1000))} 秒`;
      right.querySelectorAll("[data-contract-registered], [data-contract-index]").forEach((node) => {
        delete node.dataset.contractRegistered;
        delete node.dataset.contractIndex;
      });
      delete right.dataset.contractRegistered;
      delete right.dataset.contractIndex;
      right.classList.remove("is-selected");
      right.classList.add("is-split-right");
      target.classList.add("is-split-left");
      target.after(right);
      registerContractElement(right);
      attachClipEvents(right);
      attachTrimHandleEvents(right);
      registerNewContracts(right);
      rightClips.push(right);
    });
    applyClipGeometry();
    const selectedRight = rightClips.find((node) => node.classList.contains("clip-video")) || rightClips[0];
    if (selectedRight) selectClip(selectedRight);
    document.getElementById("timelineUndo").disabled = false;
    simulateSave("片段和关联音频已在播放头处分割");
    showToast(
      "分割完成",
      "左片段保留原 clip_id，右片段获得新 clip_id；播放头与时间线总时长保持不变。",
      "success",
    );
  });

  projectViewButtons.forEach((button) => {
    button.addEventListener("click", () => setProjectView(button.dataset.projectView));
  });

  materialRailToggle.addEventListener("click", () => {
    workspace.classList.toggle("materials-collapsed");
    const collapsed = workspace.classList.contains("materials-collapsed");
    materialRailToggle.setAttribute("aria-label", collapsed ? "展开项目素材区" : "折叠项目素材区");
    materialRailToggle.title = collapsed ? "展开项目素材区" : "折叠项目素材区";
  });

  previewMaximizeButton.addEventListener("click", () => {
    setPreviewMaximized(!workspace.classList.contains("preview-maximized"));
  });

  splitter.addEventListener("pointerdown", (event) => {
    if (
      event.button !== 0
      || workspace.classList.contains("preview-maximized")
      || workspace.classList.contains("timeline-focus-mode")
    ) return;
    splitterPointerId = event.pointerId;
    splitterStartY = event.clientY;
    splitterStartSize = previewSize ?? previewZone.getBoundingClientRect().height;
    splitter.focus();
    splitter.setPointerCapture(event.pointerId);
    splitter.classList.add("is-dragging");
    event.preventDefault();
  });

  splitter.addEventListener("pointermove", (event) => {
    if (event.pointerId !== splitterPointerId) return;
    setPreviewSize(splitterStartSize + event.clientY - splitterStartY);
  });

  splitter.addEventListener("pointerup", (event) => {
    if (event.pointerId !== splitterPointerId) return;
    splitter.releasePointerCapture(event.pointerId);
    splitterPointerId = null;
    splitter.classList.remove("is-dragging");
  });

  splitter.addEventListener("pointercancel", (event) => {
    if (event.pointerId !== splitterPointerId) return;
    setPreviewSize(splitterStartSize);
    splitterPointerId = null;
    splitter.classList.remove("is-dragging");
  });

  splitter.addEventListener("dblclick", () => {
    setPreviewSize(defaultPreviewSize());
    showToast("已恢复默认分栏", `视频预览高度已恢复为 ${previewSize}px。`);
  });

  splitter.addEventListener("keydown", (event) => {
    const bounds = previewSizeBounds();
    const current = previewSize ?? previewZone.getBoundingClientRect().height;
    let next = null;
    if (event.key === "ArrowUp") next = current - 16;
    else if (event.key === "ArrowDown") next = current + 16;
    else if (event.key === "PageUp") next = current - 48;
    else if (event.key === "PageDown") next = current + 48;
    else if (event.key === "Home") next = bounds.minimum;
    else if (event.key === "End") next = bounds.maximum;
    else if (event.key === "Escape" && splitterPointerId !== null) {
      next = splitterStartSize;
      if (splitter.hasPointerCapture(splitterPointerId)) splitter.releasePointerCapture(splitterPointerId);
      splitterPointerId = null;
      splitter.classList.remove("is-dragging");
    }
    if (next === null) return;
    event.preventDefault();
    setPreviewSize(next);
  });

  focusButton.addEventListener("click", () => {
    if (workspace.classList.contains("preview-maximized")) setPreviewMaximized(false, false);
    workspace.classList.toggle("timeline-focus-mode");
    const focused = workspace.classList.contains("timeline-focus-mode");
    focusButton.classList.toggle("is-active", focused);
    focusButton.querySelector("span").textContent = focused ? "显示预览" : "专注时间线";
    focusButton.querySelector("use").setAttribute("href", focused ? "#i-monitor" : "#i-timeline");
    focusButton.setAttribute("aria-pressed", focused ? "true" : "false");
    showToast(
      focused ? "已进入专注时间线" : "已恢复素材与预览",
      focused ? "项目素材与播放器已收起，轨道画布使用完整编辑高度。" : "素材、播放器与时间线重新并排参与当前编辑流程。",
    );
  });

  exitTimelineButton.addEventListener("click", () => {
    stopPlayback();
    setProjectView("materials");
    routeTo("projects", { force: true });
    showToast("已返回项目工作台", "剪辑状态已保留，可再次进入剪辑工作台继续。");
  });

  materialWorkbenchButton.addEventListener("click", () => {
    stopPlayback();
    routeTo("library", { force: true });
    showToast("素材工作台已激活", "剪辑工作台仍在后台保留当前项目、播放头和选择。");
  });

  recordFromTimelineButton.addEventListener("click", () => {
    stopPlayback();
    routeTo("record", { force: true });
    document.getElementById("chooseRecordMode").click();
    showToast("已打开录制工作台", "选择录制模式后，捕获前会隐藏 QuickRec 自身窗口；剪辑上下文保持。");
  });

  closeTimelineButton.addEventListener("click", () => {
    stopPlayback();
    setProjectView("materials");
    routeTo("projects", { force: true });
    showToast("剪辑工作台已关闭", "主工作台与托盘继续运行，项目和素材没有改变。");
  });

  materialSearch.addEventListener("input", updateMaterialFilter);
  materialClear.addEventListener("click", () => {
    materialSearch.value = "";
    updateMaterialFilter();
    materialSearch.focus();
  });

  document.querySelectorAll(".timeline-material-select").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest(".timeline-material-card");
      document.querySelectorAll(".timeline-material-card").forEach((node) => node.classList.toggle("is-selected", node === card));
      const missing = card.dataset.timelineMaterial === "missing";
      document.getElementById("timelineMaterialSelection").textContent = `已选：${card.querySelector("strong").textContent}`;
      document.getElementById("timelineMaterialOpen").disabled = missing;
      document.getElementById("timelineMaterialFolder").disabled = missing;
      document.getElementById("timelineMaterialRelink").disabled = !missing;
      if (missing) {
        showToast("素材文件缺失", "可使用右侧重新定位按钮恢复全部关联片段。", "warning");
      }
    });
  });

  document.getElementById("timelineMaterialOpen").addEventListener("click", () => {
    showToast("已调用默认播放器", "正式应用将打开当前项目素材的真实视频文件。", "success");
  });
  document.getElementById("timelineMaterialFolder").addEventListener("click", () => {
    showToast("已打开素材目录", "资源管理器会定位并选中当前视频文件。", "success");
  });
  document.getElementById("timelineMaterialRelink").addEventListener("click", () => applyTimelineState("missing"));

  document.querySelectorAll(".timeline-material-add").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest(".timeline-material-card");
      if (card.dataset.timelineMaterial === "missing") {
        applyTimelineState("missing");
        return;
      }
      const existing = document.querySelector('[data-clip-id="clip-demo-added"]');
      if (existing) {
        selectClip(existing);
        showToast("素材已在演示时间线中", "原型不会重复创建同一演示片段。");
        return;
      }
      const lane = document.querySelector('[data-track-id="video-1"] .timeline-lane');
      const clip = document.createElement("button");
      clip.type = "button";
      clip.className = "timeline-clip clip-video clip-blue";
      clip.dataset.clipId = "clip-demo-added";
      clip.dataset.start = "92";
      clip.dataset.duration = "8";
      clip.dataset.contract = "timeline.clip";
      clip.draggable = true;
      clip.innerHTML = '<span class="clip-grip"><svg><use href="#i-grip"></use></svg></span><span class="clip-copy"><strong>新加入素材</strong><small>追加到最早可用位置</small></span>';
      lane.appendChild(clip);
      registerContractElement(clip);
      attachClipEvents(clip);
      applyClipGeometry();
      selectClip(clip);
      document.getElementById("timelineUndo").disabled = false;
      simulateSave("素材已加入时间线");
    });
  });

  playButton.addEventListener("click", () => {
    if (playing) stopPlayback();
    else startPlayback();
  });
  seek.addEventListener("input", () => updatePlayhead(Number(seek.value)));

  document.getElementById("timelineRuler").addEventListener("click", (event) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const percent = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    updatePlayhead(percent * Number(seek.max));
  });

  document.getElementById("timelineZoomOut").addEventListener("click", () => {
    zoom = Math.max(60, zoom - 20);
    grid.style.setProperty("--timeline-grid-width", `${Math.round(920 * zoom / 100)}px`);
    zoomLabel.textContent = `${zoom}%`;
    document.getElementById("timelineZoomOut").disabled = zoom === 60;
    document.getElementById("timelineZoomIn").disabled = false;
  });
  document.getElementById("timelineZoomIn").addEventListener("click", () => {
    zoom = Math.min(160, zoom + 20);
    grid.style.setProperty("--timeline-grid-width", `${Math.round(920 * zoom / 100)}px`);
    zoomLabel.textContent = `${zoom}%`;
    document.getElementById("timelineZoomIn").disabled = zoom === 160;
    document.getElementById("timelineZoomOut").disabled = false;
  });
  document.getElementById("timelineFit").addEventListener("click", () => {
    const available = Math.max(680, document.getElementById("timelineScroll").clientWidth - 148);
    zoom = Math.max(60, Math.min(160, Math.round((available / 920) * 100 / 20) * 20));
    grid.style.setProperty("--timeline-grid-width", `${available}px`);
    zoomLabel.textContent = "适配";
    document.getElementById("timelineScroll").scrollLeft = 0;
  });

  function createTrack(kind) {
    const current = document.querySelectorAll(`.timeline-track-row[data-track-kind="${kind}"]`).length;
    if (current >= 8) {
      showToast("已达到轨道上限", `${kind === "video" ? "视频" : "音频"}轨最多 8 条。`, "warning");
      return;
    }
    const row = document.createElement("div");
    row.className = "timeline-track-row";
    row.dataset.trackId = `${kind}-${Date.now()}`;
    row.dataset.trackKind = kind;
    row.dataset.locked = "false";
    const label = `${kind === "video" ? "视频" : "音频"} ${current + 1}`;
    row.innerHTML = `
      <div class="timeline-track-header">
        <button type="button" class="track-grip" aria-label="调整${label}轨道顺序" title="调整轨道顺序" data-contract="timeline.track-reorder"><svg><use href="#i-grip"></use></svg></button>
        <span class="track-kind-icon${kind === "audio" ? " is-audio" : ""}"><svg><use href="#i-${kind}"></use></svg></span>
        <button type="button" class="track-name" data-contract="timeline.track-rename">${label}</button>
        <span class="track-status">${kind === "video" ? "空轨" : "固定增益"}</span>
        <button type="button" class="track-lock" aria-label="锁定${label}" title="锁定轨道" aria-pressed="false" data-contract="timeline.track-lock"><svg><use href="#i-unlock"></use></svg></button>
        <button type="button" class="track-delete" aria-label="删除${label}" title="删除轨道" data-contract="timeline.track-delete"><svg><use href="#i-trash"></use></svg></button>
      </div>
      <div class="timeline-lane ${kind}-lane"><i class="timeline-playhead-line" style="left:${(Number(seek.value) / Number(seek.max)) * 100}%"></i></div>
    `;
    grid.appendChild(row);
    registerNewContracts(row);
    attachTrackEvents(row);
    attachLaneEvents(row.querySelector(".timeline-lane"));
    simulateSave(`${label}已创建`);
  }

  document.getElementById("addVideoTrack").addEventListener("click", () => createTrack("video"));
  document.getElementById("addAudioTrack").addEventListener("click", () => createTrack("audio"));

  document.getElementById("timelineUndo").addEventListener("click", () => {
    const demo = document.querySelector('[data-clip-id="clip-demo-added"]');
    if (demo) demo.remove();
    document.getElementById("timelineUndo").disabled = true;
    document.getElementById("timelineRedo").disabled = false;
    simulateSave("已撤销最近一次时间线操作");
  });
  document.getElementById("timelineRedo").addEventListener("click", () => {
    document.getElementById("timelineRedo").disabled = true;
    document.getElementById("timelineUndo").disabled = false;
    showToast("已重做时间线操作", "原型恢复命令状态；正式实现需原子保存。", "success");
  });

  function attachTrackEvents(row) {
    const nameButton = row.querySelector(".track-name");
    const lockButton = row.querySelector(".track-lock");
    const deleteButton = row.querySelector(".track-delete");
    lockButton.addEventListener("click", () => {
      if (workspace.classList.contains("is-readonly")) {
        showToast("当前项目不可编辑", "只读、冲突或保存处理中不能修改轨道锁定状态。", "warning");
        return;
      }
      const locked = row.dataset.locked !== "true";
      setTrackLockVisual(row, locked);
      if (locked && row.querySelector(".timeline-clip.is-selected")) setInspectorOpen(false);
      updateEditControls();
      document.getElementById("timelineUndo").disabled = false;
      simulateSave(`${nameButton.textContent.trim()}已${locked ? "锁定" : "解锁"}`);
    });
    nameButton.addEventListener("click", () => {
      const oldName = nameButton.textContent.trim();
      showModal({
        title: "重命名轨道",
        text: "名称仅用于识别轨道；轨道身份和片段引用保持不变。",
        detailHtml: `<label class="field"><span>轨道名称</span><input id="timelineTrackNameInput" type="text" value="${oldName}" data-contract="timeline.track-rename"></label>`,
        actions: [
          { label: "取消", contract: "modal.cancel", onClick: closeModal },
          {
            label: "保存名称",
            kind: "button-primary",
            contract: "timeline.track-rename",
            onClick: () => {
              const value = document.getElementById("timelineTrackNameInput").value.trim();
              nameButton.textContent = value || (row.dataset.trackKind === "video" ? "视频轨" : "音频轨");
              closeModal();
              simulateSave("轨道名称已保存");
            },
          },
        ],
      });
    });
    deleteButton.addEventListener("click", () => {
      const clipCount = row.querySelectorAll(".timeline-clip").length;
      const sameKindCount = document.querySelectorAll(`.timeline-track-row[data-track-kind="${row.dataset.trackKind}"]`).length;
      if (sameKindCount <= 1) {
        showToast("不能删除最后一条同类型轨道", "时间线至少保留 1 条视频轨和 1 条音频轨。", "warning");
        return;
      }
      showModal({
        title: `删除${nameButton.textContent.trim()}？`,
        text: clipCount
          ? `该轨道包含 ${clipCount} 个片段。确认后轨道和片段作为一个可撤销命令移除。`
          : "该轨道为空。删除不会影响项目素材或真实视频。",
        icon: "warning",
        actions: [
          { label: "取消", contract: "modal.cancel", onClick: closeModal },
          {
            label: "删除轨道",
            kind: "button-primary",
            contract: "timeline.track-delete",
            onClick: () => {
              row.remove();
              closeModal();
              simulateSave("轨道已删除");
            },
          },
        ],
      });
    });
  }

  function clipsOverlap(candidate, lane, ignoredClip) {
    const start = Number(candidate.start);
    const end = start + Number(candidate.duration);
    return [...lane.querySelectorAll(".timeline-clip")].some((clip) => {
      if (clip === ignoredClip) return false;
      const clipStart = Number(clip.dataset.start);
      const clipEnd = clipStart + Number(clip.dataset.duration);
      return start < clipEnd && end > clipStart;
    });
  }

  function attachLaneEvents(lane) {
    lane.addEventListener("dragover", (event) => {
      if (!draggedClip) return;
      const draggedKind = draggedClip.classList.contains("clip-audio") ? "audio" : "video";
      const targetKind = lane.classList.contains("audio-lane") ? "audio" : "video";
      const targetLocked = lane.closest(".timeline-track-row")?.dataset.locked === "true";
      lane.classList.toggle("is-drop-target", draggedKind === targetKind && !targetLocked);
      lane.classList.toggle("is-drop-invalid", draggedKind !== targetKind || targetLocked);
      if (draggedKind === targetKind && !targetLocked) event.preventDefault();
    });
    lane.addEventListener("dragleave", () => lane.classList.remove("is-drop-target", "is-drop-invalid"));
    lane.addEventListener("drop", (event) => {
      event.preventDefault();
      lane.classList.remove("is-drop-target", "is-drop-invalid");
      if (!draggedClip) return;
      if (lane.closest(".timeline-track-row")?.dataset.locked === "true") {
        showToast("目标轨道已锁定", "解锁轨道后才能移动片段。", "warning");
        return;
      }
      const bounds = lane.getBoundingClientRect();
      const duration = Number(draggedClip.dataset.duration);
      const proposed = Math.max(0, Math.min(100 - duration, ((event.clientX - bounds.left) / bounds.width) * 100));
      if (clipsOverlap({ start: proposed, duration }, lane, draggedClip)) {
        showToast("该轨道位置存在重叠", "同一轨道不允许片段重叠，原位置保持不变。", "warning");
        return;
      }
      const oldLane = draggedClip.parentElement;
      lane.appendChild(draggedClip);
      draggedClip.dataset.start = proposed.toFixed(2);
      applyClipGeometry();
      if (draggedClip.dataset.clipId === "clip-v2") {
        const linked = document.querySelector('[data-clip-id="clip-a2"]');
        linked.dataset.start = draggedClip.dataset.start;
        applyClipGeometry();
      }
      selectClip(draggedClip);
      simulateSave(oldLane === lane ? "片段时间位置已保存" : "片段轨道和时间位置已保存");
    });
  }

  function attachTrimHandleEvents(clip) {
    clip.querySelectorAll(".clip-trim-handle").forEach((handle) => {
      handle.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) return;
        if (playing || isClipLocked(clip) || workspace.classList.contains("is-readonly")) {
          showToast(
            "当前不能裁剪",
            playing ? "请先暂停播放。" : isClipLocked(clip) ? "请先解锁轨道。" : "当前项目不可编辑。",
            "warning",
          );
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        selectClip(clip);
        const linked = linkedClipFor(clip);
        const sourceStart = Number(clip.dataset.sourceStartMs || 0);
        const sourceEnd = Number(clip.dataset.sourceEndMs || sourceStart + clipDurationMs(clip));
        trimGesture = {
          clip,
          linked,
          handle,
          edge: handle.dataset.trimEdge,
          pointerId: event.pointerId,
          startX: event.clientX,
          laneWidth: clip.parentElement.getBoundingClientRect().width,
          sourceStart,
          sourceEnd,
          materialDuration: Number(clip.dataset.materialDurationMs || sourceEnd),
          originalDuration: Number(clip.dataset.duration),
          originalLinkedDuration: linked ? Number(linked.dataset.duration) : null,
          candidateSourceStart: sourceStart,
          candidateSourceEnd: sourceEnd,
          valid: true,
        };
        clip.draggable = false;
        clip.classList.add("is-trimming");
        if (linked) linked.classList.add("is-trimming");
        handle.setPointerCapture(event.pointerId);
      });
      handle.addEventListener("pointermove", (event) => {
        if (!trimGesture || trimGesture.handle !== handle || trimGesture.pointerId !== event.pointerId) return;
        const deltaMs = ((event.clientX - trimGesture.startX) / trimGesture.laneWidth) * Number(seek.max);
        let sourceStart = trimGesture.sourceStart;
        let sourceEnd = trimGesture.sourceEnd;
        if (trimGesture.edge === "in") sourceStart += deltaMs;
        else sourceEnd += deltaMs;
        const duration = sourceEnd - sourceStart;
        const valid = sourceStart >= 0
          && sourceEnd <= trimGesture.materialDuration
          && sourceEnd > sourceStart
          && duration >= 34;
        trimGesture.candidateSourceStart = Math.max(0, Math.round(sourceStart));
        trimGesture.candidateSourceEnd = Math.min(trimGesture.materialDuration, Math.round(sourceEnd));
        trimGesture.valid = valid;
        const safeDuration = Math.max(34, trimGesture.candidateSourceEnd - trimGesture.candidateSourceStart);
        const durationPercent = (safeDuration / Number(seek.max)) * 100;
        clip.style.width = `${durationPercent}%`;
        clip.classList.toggle("is-trim-invalid", !valid);
        if (trimGesture.linked) {
          trimGesture.linked.style.width = `${durationPercent}%`;
          trimGesture.linked.classList.toggle("is-trim-invalid", !valid);
        }
        document.getElementById("timelineFooterStatus").textContent = valid
          ? `裁剪候选：${formatTime(trimGesture.candidateSourceStart)}–${formatTime(trimGesture.candidateSourceEnd)} · 松开后预检全局波纹`
          : "裁剪候选无效：已超出素材范围或短于最小时长";
      });
      handle.addEventListener("pointerup", (event) => {
        if (!trimGesture || trimGesture.handle !== handle || trimGesture.pointerId !== event.pointerId) return;
        handle.releasePointerCapture(event.pointerId);
        clip.draggable = true;
        const gesture = trimGesture;
        document.getElementById("timelineFooterStatus").textContent =
          `schema v2 · 时间单位：微秒 · 撤销历史 1 / 50 · 总时长 ${formatTime(Number(seek.max))}`;
        if (!gesture.valid) {
          restoreTrimPreview();
          if (gesture.linked) {
            gesture.linked.style.width = `${gesture.originalLinkedDuration}%`;
            gesture.linked.classList.remove("is-trimming", "is-trim-invalid");
          }
          showToast("裁剪范围无效", "源范围必须位于素材内部，并至少保留一个完整视频帧。", "warning");
          return;
        }
        const nextDuration = gesture.candidateSourceEnd - gesture.candidateSourceStart;
        const impact = calculateRippleImpact(clip, "trim", nextDuration);
        openRipplePreview(
          impact,
          () => applyTrim(clip, gesture.candidateSourceStart, gesture.candidateSourceEnd, impact),
        );
      });
      handle.addEventListener("pointercancel", () => {
        if (!trimGesture || trimGesture.handle !== handle) return;
        clip.draggable = true;
        restoreTrimPreview();
      });
    });
  }

  function attachClipEvents(clip) {
    clip.addEventListener("click", () => selectClip(clip));
    clip.addEventListener("dblclick", () => {
      updatePlayhead((Number(clip.dataset.start) / 100) * Number(seek.max));
      showToast("播放头已定位", "双击片段只跳转到片段起点，不打开剪辑器。");
    });
    clip.addEventListener("dragstart", (event) => {
      if (trimGesture || isClipLocked(clip) || playing) {
        event.preventDefault();
        if (isClipLocked(clip)) showToast("轨道已锁定", "解锁轨道后才能移动片段。", "warning");
        return;
      }
      draggedClip = clip;
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", clip.dataset.clipId);
    });
    clip.addEventListener("dragend", () => {
      draggedClip = null;
      document.querySelectorAll(".timeline-lane").forEach((lane) => lane.classList.remove("is-drop-target", "is-drop-invalid"));
    });
  }

  document.querySelectorAll(".timeline-track-row").forEach(attachTrackEvents);
  document.querySelectorAll(".timeline-lane").forEach(attachLaneEvents);
  document.querySelectorAll(".timeline-clip").forEach(attachClipEvents);
  document.querySelectorAll(".timeline-clip").forEach(attachTrimHandleEvents);

  stateAction.addEventListener("click", () => {
    if (currentTimelineState === "missing") {
      showToast("等待选择新文件", "正式应用会先验证候选媒体，再恢复全部关联片段。");
    } else if (currentTimelineState === "decode-error" || currentTimelineState === "save-failed") {
      applyTimelineState("default");
      showToast("重试成功", "时间线恢复到最后一次有效状态。", "success");
    } else if (currentTimelineState === "audio-unavailable") {
      audioState.className = "timeline-audio-state is-warning";
      audioState.innerHTML = '<svg><use href="#i-alert"></use></svg>无声预览';
      stateBanner.hidden = true;
      startPlayback();
    } else if (currentTimelineState === "empty") {
      setProjectView("materials");
    } else if (["corrupt", "unknown", "conflict", "readonly"].includes(currentTimelineState)) {
      showToast("已进入安全恢复链路", "原型保持项目只读；正式实现需完成备份或版本验证。", "warning");
    } else {
      applyTimelineState("default");
    }
  });

  document.getElementById("retryTimelinePlayback").addEventListener("click", () => {
    applyTimelineState("default");
    showToast("播放运行时已重建", "已定位到原播放头，项目数据未改变。", "success");
  });
  document.querySelector('[data-contract="timeline.preview-diagnostics"]').addEventListener("click", () => {
    stopPlayback();
    routeTo("diagnostics", { force: true });
    showToast("已打开诊断页", "返回项目时会恢复时间线视图，但不会自动继续播放。");
  });

  document.getElementById("prototypeState").addEventListener("change", (event) => {
    if (event.target.value.startsWith("timeline-")) {
      routeTo("projects", { force: true });
      applyTimelineState(event.target.value.replace("timeline-", ""));
      return;
    }
    if (currentTimelineState !== "default") {
      currentTimelineState = "default";
      resetTimelineVisualState();
    }
  });

  document.addEventListener("keydown", (event) => {
    const editing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
    if (editing || projectView !== "timeline") return;
    if (event.code === "Space") {
      event.preventDefault();
      playButton.click();
    } else if (event.ctrlKey && event.key.toLocaleLowerCase("en-US") === "z") {
      event.preventDefault();
      document.getElementById("timelineUndo").click();
    } else if (event.ctrlKey && event.key.toLocaleLowerCase("en-US") === "y") {
      event.preventDefault();
      document.getElementById("timelineRedo").click();
    } else if (event.ctrlKey && event.key.toLocaleLowerCase("en-US") === "b") {
      event.preventDefault();
      splitButton.click();
    } else if (event.key === "Delete") {
      event.preventDefault();
      deleteClipButton.click();
    } else if (event.key === "Escape" && !clipInspector.hidden) {
      event.preventDefault();
      setInspectorOpen(false);
    }
  });

  applyClipGeometry();
  updatePlayhead(Number(seek.value));
  document.getElementById("timelineFit").click();

  new MutationObserver(syncTimelineShell).observe(projectsPanel, {
    attributes: true,
    attributeFilter: ["class"],
  });
  window.addEventListener("resize", syncTimelineShell);

  const requestedPage = new URLSearchParams(window.location.search).get("page");
  if (!requestedPage || requestedPage === "projects" || requestedPage === "timeline") {
    routeTo("projects", { force: true });
    setProjectView("timeline");
  }
})();
