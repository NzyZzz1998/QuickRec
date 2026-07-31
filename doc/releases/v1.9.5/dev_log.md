# QuickRec Full v1.9.5 开发日志

## 2026-07-30 D0 实现基线

### 本轮目标

- 固定 v1.9.5 实现事实源和回滚点。
- 确认 Full、Lite 与独立 v2.0 文档边界。
- 新跑 v1.9.4 全量非硬件基线。

### 当前身份

```text
工作区：E:\codex\QuickRec
分支：test
HEAD：b3b8267e1950b8e2b9efc6d28d29b501189fd7af
回滚 tag：v1.9.4
Lite：E:\codex\QuickRec-Lite / lite-master / 工作区干净
```

### 验证

```powershell
python -m pytest -m "not hardware and not packaging" -q
```

结果：

```text
1238 passed, 32 deselected, 66 subtests passed in 38.55s
```

### 边界

- 本版实现只修改 QuickRec Full。
- v2.0 架构与贡献归属治理文档属于独立未跟踪内容。
- 不移动 `v1.9.4` 或任何历史 tag。
- D1 三项治理分别执行测试先行，不与产品主线混写。

## 2026-07-30 D1 Space 焦点契约

### RED

在 `tests/test_timeline_playback_ui.py` 增加画布、文本输入、按钮、菜单和
模态弹窗五类焦点场景。首次运行结果：

```text
1 failed, 13 passed
```

失败项证明时间线画布获得焦点时，Space 尚未路由到播放命令；其余原生控件没有误触发
播放。

### GREEN

- 新增 `TimelineShortcutRouter`，仅接管剪辑工作台时间线画布中的无修饰 Space；
- 输入框、按钮、列表、菜单和弹窗继续接收 Qt 原生按键；
- Space 与播放按钮统一调用 `TimelineEditorWindow._toggle_playback()`；
- 自动重复 Space 被消费但不会重复切换状态；
- 窗口 `shutdown()` 时显式移除应用事件过滤器。

定向验证：

```powershell
python -m pytest tests/test_timeline_playback_ui.py -q
```

结果：

```text
14 passed in 0.78s
```

## 2026-07-30 D1 录制工具栏目标屏幕定位

### RED

先增加纯逻辑坐标和工具栏目标屏幕接入测试。初次运行分别证明：

- `ui.toolbar_placement` 尚不存在；
- `RecordingToolbar` 尚不接受明确目标屏幕。

### GREEN

- 新增纯函数 `select_target_screen_index()`：
  - 全屏按当前 DXGI 输出索引映射；
  - 区域和窗口按最大相交面积选择；
  - 元数据缺失、越界或无交集时回退主屏；
- 新增 `calculate_toolbar_position()`，在目标屏幕可用区域水平居中，并使用 10% 中上
  安全区和 8 像素可见边距；
- `RecordingToolbar` 保存目标屏幕并使用 `availableGeometry()`；
- 全屏、区域和窗口入口分别把输出索引或目标矩形传入同一 `_show_toolbar()`；
- 三档测试数据使用 Qt 逻辑坐标，未混入物理像素换算。

定向验证：

```powershell
python -m pytest tests/test_toolbar_placement.py tests/test_toolbar.py tests/test_main_workflow.py -q
```

结果：

```text
81 passed in 0.80s
```

## 2026-07-30 D1 导出临时文件治理

### RED

先增加 attempt 精确归属、活跃任务保护、提交事务保护、删除失败诊断、启动中断恢复及
成功/取消终态清理测试。首次运行因 `exporting.temp_cleanup` 不存在而在收集阶段失败。

### GREEN

- 新增 `ExportTempArtifactOwner`，同时绑定 `job_id`、`attempt_id` 和输出目录；
- 只识别当前已知的 `.part.mp4` 与 `.filter.txt` 精确文件名；
- 活跃 attempt 和存在提交事务的 attempt 整体跳过；
- 其他 attempt、相似文件名、用户文件和未知类型均不会删除；
- 队列初始化在事务恢复之后清理原活动状态的中断 attempt；
- 成功和受控取消在任务落终态前清理；
- 每次结果写入结构化报告和不含完整路径的日志；清理失败不改变导出成功事实。

验证：

```text
导出相关：208 passed, 1082 deselected
D1 组合回归：124 passed
Ruff：通过
Mypy（4 个新增/受影响核心模块）：通过
git diff --check：通过（仅既有 LF/CRLF 提示）
```

### 独立回退边界

- Space 治理集中在 `TimelineShortcutRouter` 与窗口单点接入；
- 工具栏治理集中在纯几何模块、三种入口目标参数和工具栏定位；
- 导出治理集中在 attempt 归属模块及队列初始化/终态钩子；
- 三项均未修改 timeline schema、编辑 FPS、关联语义或智能拖放。

## 2026-07-30 D2 统一快捷键与焦点路由

### 实现

- 将 Space、左右、Shift+左右、Ctrl+B、Delete、Shift+Delete、Ctrl+L、
  Ctrl+Z、Ctrl+Y 和 Esc 固定映射为语义命令；
- 快捷键只在剪辑窗口或时间线画布焦点下接管，输入、按钮、列表、菜单和模态弹窗保留
  Qt 原生行为；
- 结构命令统一检查项目可用性、录制、待保存、只读、选择和素材健康状态，并返回明确
  禁用原因；
- 播放、撤销、重做、分割、普通删除及片段菜单统一调用同一分发入口；
- `Delete` 改为删除并保留空隙，`Shift+Delete` 保留全局波纹删除；
- 素材缺失时禁止分割，但保留安全删除能力；
- 非导航快捷键禁止自动重复，逐帧和逐秒导航允许按住连续触发；
- 补齐播放、分割、删除、撤销和重做的正式快捷键提示与可访问名称。

### 验证

```powershell
python -m pytest tests/test_timeline_shortcuts.py tests/test_timeline_playback_ui.py tests/test_timeline_editor_window.py tests/test_timeline_editing_ui.py -q
python -m ruff check src/ui/timeline_shortcut_router.py src/ui/timeline_editor_window.py tests/test_timeline_shortcuts.py tests/test_timeline_playback_ui.py tests/test_timeline_editor_window.py tests/test_timeline_editing_ui.py
python -m mypy src/ui/timeline_shortcut_router.py src/ui/timeline_editor_window.py
```

结果：

```text
定向测试：60 passed
Ruff：通过
Mypy：通过
```

## 2026-07-30 D3 项目编辑 FPS 与帧时间

### 实现

- 新增项目级 `quickrec.editing` 扩展，保持项目根 schema v1 和 timeline schema v2；
- 新项目一次性继承有效录制 FPS，旧项目按首个稳定视频素材证据推导，无法推导时使用
  30 FPS；
- 只查看旧项目不写盘，第一次成功结构编辑时与时间线变更原子保存；
- 30、60、120 FPS 严格校验，未知扩展字段往返保留，未知版本进入只读保护；
- 空时间线允许显式修改 FPS，已有片段后永久锁定；保存失败不改变内存有效值；
- 建立整数有理数帧/微秒换算、`HH:MM:SS:FF` 和总帧号严格解析；
- 左右键按项目 FPS 逐帧导航，Shift+左右精确移动一秒，播放中导航先暂停；
- 空时间线在 60 秒默认可视范围内导航，不产生项目写入；
- 剪辑工作台显示项目编辑 FPS、时间码/总帧输入和跳转入口；
- 时间线标尺使用项目帧索引生成刻度，120 FPS 使用三位帧号并预留稳定输入宽度。

### 验证

由于多个 PyQt 测试文件共享同一进程时触发 Windows Qt 原生访问冲突，GUI 文件按进程
隔离执行；各文件独立通过。

```text
非 UI 与服务回归：163 passed
快捷键与导航：27 passed
时间线画布与编辑窗口：22 passed
剪辑交互 UI：14 passed
播放 UI：14 passed
合计：240 passed
Ruff：通过
Mypy（8 个 D3 受影响生产模块）：通过
Compileall：通过
```

## 2026-07-30 D4 解绑、重新关联与双删除

### RED

- 先增加普通删除候选测试，首次运行因命令服务不存在 `preview_delete_clip()` 失败；
- 增加损坏关联组、严格候选过滤、陈旧候选、保存失败、解绑后独立移动/裁剪/分割和
  单侧波纹预检测试；
- 测试夹具扩充轨道后暴露一处按列表下标锁轨的脆弱写法，已改为按 `track_id`
  定位，不涉及产品行为。

### GREEN

- 解绑候选只清空合法一视频一音频关联组双方的 `link_group_id`，完整保留片段身份、
  素材身份、轨道、时间位置、源范围、扩展和未知字段；
- 重关联候选严格要求异类轨道、同一素材、相同时间与源范围、媒体存在且双方未关联，
  并以轨道距离、轨道顺序和片段 ID 稳定排序；
- 重关联提交生成新关联 ID，并通过时间线指纹拒绝陈旧候选；
- 普通删除接入纯候选与原子提交模型，保留空隙；全局波纹删除继续使用独立候选，
  两种命令和影响摘要保持可区分；
- 解绑后的移动、裁剪、分割和普通删除只处理选中片段；单侧波纹删除仍执行全局冲突
  预检；
- 保存失败时内存、项目文件和 Undo/Redo 历史均保持最后一次成功状态。

### 验证

```powershell
python -m pytest tests/test_timeline_link_commands.py tests/test_timeline_delete_commands.py tests/test_timeline_commands.py tests/test_timeline_edit_commands.py tests/test_timeline_schema_v2.py tests/test_timeline_session.py -q
python -m ruff check src/services/timeline_edit_service.py src/services/timeline_commands.py tests/test_timeline_link_commands.py tests/test_timeline_delete_commands.py
python -m mypy src/services/timeline_edit_service.py src/services/timeline_commands.py
python -m compileall -q src/services/timeline_edit_service.py src/services/timeline_commands.py
git diff --check
```

结果：

```text
D4 定向与兼容回归：84 passed
Ruff：通过
Mypy：通过
Compileall：通过
git diff --check：通过（仅既有 LF/CRLF 提示）
```

## 2026-07-30 D5 智能拖放、吸附与自动建轨

### RED

- 新增帧边界、片段左右边缘、播放头、稳定优先级、像素阈值和 Alt 关闭吸附测试，
  首次因 `timeline_snap` 不存在而收集失败；
- 新增拖动生命周期、事务 ID、陈旧候选、取消和重复取消测试，首次因
  `timeline_drag_interaction` 不存在而收集失败；
- 新增视频、独立音频、内嵌音频、显式锁定轨、类型冲突、条件建轨、8 轨上限、
  原子保存、撤销、保存失败和 100 片段性能测试，首次因
  `timeline_drag_transaction` 不存在而收集失败。

### GREEN

- 新增纯 `TimelineSnapService` 合同：先比较距离，同距按播放头、片段边缘、帧网格
  稳定决胜；阈值由 DPI 无关逻辑像素换算，Alt 只关闭本次吸附；
- 新增纯拖动事务候选：包含事务 ID、素材流类型、原始/最终时间、目标轨、吸附来源、
  冲突原因、自动建轨计划和完整候选时间线；
- 有空闲兼容轨时稳定选用既有轨；所有兼容轨冲突或无未锁定兼容轨时才自动建轨；
- 新视频轨插入视频区顶部，新音频轨追加到音频区末尾，视频和音频分别执行 8 轨上限；
- 含内嵌音频的视频一次生成关联双片段，独立音频只生成未关联音频片段；
- 拖动候选保持纯内存，陈旧候选在提交前拒绝；
- 自动轨和片段通过一次项目保存、一个历史项提交，撤销一次完整移除，保存失败不留下
  空轨、片段或历史副作用；
- 100 片段候选计算和 200 次吸附采样均低于发布性能门槛。

### 验证

```powershell
python -m pytest tests/test_timeline_snap.py tests/test_timeline_drag_transaction.py tests/test_timeline_drag_interaction.py tests/test_timeline_commands.py tests/test_timeline_edit_commands.py tests/test_timeline_link_commands.py tests/test_timeline_delete_commands.py tests/test_timeline_session.py -q
python -m ruff check src/services/timeline_snap.py src/services/timeline_drag_transaction.py src/ui/timeline_drag_interaction.py src/services/timeline_commands.py tests/test_timeline_snap.py tests/test_timeline_drag_transaction.py tests/test_timeline_drag_interaction.py
python -m mypy src/services/timeline_snap.py src/services/timeline_drag_transaction.py src/ui/timeline_drag_interaction.py src/services/timeline_commands.py
python -m compileall -q src/services/timeline_snap.py src/services/timeline_drag_transaction.py src/ui/timeline_drag_interaction.py src/services/timeline_commands.py
git diff --check
```

结果：

```text
D5 定向与兼容回归：92 passed
Ruff：通过
Mypy：通过
Compileall：通过
git diff --check：通过（仅既有 LF/CRLF 提示）
```

## 2026-07-30 D6 剪辑工作台 UI 与状态整合

### RED

- 新增 D6 界面合同测试，首次因缺少严格重新关联候选弹窗而在测试收集阶段失败；
- 新增解绑/重新关联、普通删除/波纹删除、智能拖放提交、自动建轨占位、冲突反馈、
  中文文案、工具提示、可访问名称和 960×640 布局测试；
- 动态扫描发现片段检查器和影响确认框保留了历史乱码文本，若不处理会直接进入用户
  可见界面。

### GREEN

- 工具栏与 `Ctrl+L` 统一接入关联命令：已关联片段显示“解绑音视频”，未关联片段
  打开严格候选弹窗；无候选、素材缺失、轨道锁定和保存失败均提供明确反馈；
- 片段画布、选择摘要和检查器统一显示“已关联/未关联”，解绑成功后当前片段保持
  选中，重新关联使用新关联 ID 且不移动或裁剪片段；
- `Delete` 统一执行普通删除影响确认并保留空隙，`Shift+Delete` 和独立次级按钮
  保持全局波纹删除，两个入口、文案和结果可区分；
- 画布拖放由 D5 纯候选驱动，拖动期间展示帧级时间码、目标轨轮廓、吸附来源、
  关联音视频落点、自动建轨占位和冲突原因；松开后只提交同一候选一次；
- Esc 可取消拖放或裁剪临时状态，UI 不直接修改 timeline 或项目 JSON；
- 片段检查器和影响确认框恢复为可读简体中文，并补齐重新关联候选详情、工具提示和
  可访问名称；
- 轨道管理拆到独立紧凑行，避免新增关联/波纹按钮后在 960×640 下挤出可操作区域；
- 默认最大化仍由单实例协调器负责，最小尺寸保持 960×640。

### 验证

Qt 测试按文件使用独立进程，规避 Windows 下多个 PyQt 测试文件共享进程时的既有
原生访问冲突：

```text
TimelineEditorWindow：8 passed
剪辑交互 UI：14 passed
编辑窗口 UI：22 passed
播放 UI：14 passed
D6 新增合同：7 passed
合计：65 passed
Ruff：通过
Mypy（6 个 D6 生产模块）：通过
Compileall：通过
git diff --check：通过（仅既有 LF/CRLF 提示）
```

## 2026-07-30 D7 持久化、播放、导出、CLI 与兼容

### RED

- 新增 CLI 编辑合同测试，首次因 `project validate` 和 `timeline validate`
  未输出编辑配置、解绑片段及关联组信息而得到 2 个失败；
- 新增跨服务集成测试，覆盖新命令落盘、项目备份、重启恢复、自动轨顺序、
  普通删除与波纹删除导出差异、失败保存后的 ExportPlan、未关联播放查询和
  帧级微秒入口；
- 跨服务测试在生产代码修改前全部通过，证明保存、播放和导出核心语义已经由
  D3-D5 的实现正确闭合。

### GREEN

- `QuickRecCLI project validate` 新增只读编辑配置报告：是否存在、schema、
  状态、编辑 FPS、锁定状态、只读状态和安全错误摘要；
- `QuickRecCLI timeline validate` 新增已关联片段数、未关联片段数、关联组数，
  并把未来编辑配置版本稳定报告为只读，不改写项目文件；
- 新 CLI 字段直接复用 `resolve_project_editing_profile`，避免命令行与 GUI
  产生第二套兼容判断；
- 集成测试确认新命令成功后可跨进程恢复，其他项目扩展和未知字段往返保留，
  且 `.bak` 可读取；
- 集成测试确认普通删除保留空隙并维持导出总时长，全局波纹删除移动后续片段并
  缩短导出总时长；
- 保存失败时内存、历史和磁盘保持最后成功状态，ExportPlan 不会读取未提交候选；
- 未关联视频与音频继续按各自轨道参与播放，最高有效视频轨覆盖规则保持不变。

### 验证

```powershell
python -m pytest tests/test_project_save_coordinator.py tests/test_project_store.py tests/test_timeline_history.py tests/test_timeline_commands.py tests/test_timeline_link_commands.py tests/test_timeline_delete_commands.py tests/test_timeline_drag_transaction.py tests/test_project_editing_profile.py tests/test_timeline_editing_profile_integration.py tests/test_timeline_query.py tests/test_timeline_media_runtime.py tests/test_export_plan_builder.py tests/test_cli_commands.py tests/test_cli_contracts.py tests/test_cli_main.py tests/test_v195_d7_integration.py -q
python -m ruff check src/cli/commands.py tests/test_cli_commands.py tests/test_v195_d7_integration.py
python -m mypy src/cli/commands.py src/services/timeline_commands.py src/services/timeline_query.py src/exporting/plan_builder.py
git diff --check
```

结果：

```text
D7 定向与集成回归：200 passed
CLI 新增合同：13 passed
D7 新增跨服务集成：4 passed
Ruff：通过
Mypy：通过
git diff --check：通过（仅既有 LF/CRLF 提示）
```

## 2026-07-31 D8 自动化、质量与候选包

### 最终源码门禁

- 将单一应用版本事实源从 v1.9.4 更新为 v1.9.5，并先用失败测试固定候选身份；
- 默认非硬件、非 Packaging 测试 `1424 passed, 32 deselected, 72 subtests passed`；
- 仅排除硬件、包含 Packaging 的测试 `1444 passed, 12 deselected, 72 subtests passed`；
- Packaging 单独验证 `20 passed, 1436 deselected`；
- 总体 Coverage 为 84.14%，v1.9.5 领域核心 95.24%，UI 协调 97.75%；
- Ruff、83 个源文件 Mypy、Compileall 和 `git diff --check` 均通过；
- 原型 239 个交互合同及三个视口自动验证通过。

### 候选包

- 首次候选自报 v1.9.4，未锁定为 D9 对象；
- 修正版本事实源后生成独立 RC2，不覆盖 v1.9.4 稳定产物；
- RC2 frozen `doctor --json` 自报 QuickRec Full v1.9.5、Python 3.12.8、
  FFmpeg/FFprobe 8.0.1、PyAV 18.0.0；
- frozen editing smoke、项目校验、时间线校验均通过；
- 使用已验收的 8 路音频项目执行 6 秒真实 export smoke，输出
  H.264/AAC、640×360、30 FPS，FFprobe 和原子提交通过。

候选身份和完整哈希记录在 `verification.md`。D9 只能使用
`E:\QRtest\QuickRec-v1.9.5-rc2-dist\QuickRec`。

## 2026-07-31 D9 工具栏阻塞修复与 RC3

- RC2 真实全屏录制发现工具栏在宽度动画后回落到屏幕垂直中部，RC2 随即失效；
- 新增失败测试固定“动画完成后仍保持目标屏幕顶部安全区”合同；
- 统一工具栏位置计算和宽度动画的目标几何，移除竞争性的零延迟二次定位；
- 生成 RC3，并在全屏、区域和窗口三种模式下实测工具栏均为
  `left=1113, top=139, width=334, height=48`；
- 三种模式均成功保存 60 FPS H.264 MP4，并写入隔离中央素材索引；
- RC3 全量回归为 `1425 passed, 32 deselected, 72 subtests passed`，
  Packaging 为 `20 passed`，Coverage 仍为 84.14%；
- RC3 frozen doctor、editing smoke 和真实 export smoke 通过。

当前唯一有效候选身份为
`E:\QRtest\QuickRec-v1.9.5-rc3-dist\QuickRec`。缺陷根因、修复和证据记录在
`bugfix-log.md`，D9 完整状态记录在 `manual-verification.md`。

## 2026-07-31 D9 原生拖放、DPI 与恢复补证

- 使用真实 Windows 指针路径触发 RC3 的 Qt 原生拖放，确认有效拖入、锁定轨
  拒绝、条件性自动建轨和拖出画布取消；
- 有效拖入后隔离项目由 3 轨/4 片段更新为 4 轨/5 片段并自动保存；
- 锁定轨拒绝和拖出取消均保持项目数据零修改；
- 在 Windows 系统级 125% 和 150% 下分别重启同一 RC3，检查工作台最小窗口、
  项目页、剪辑工作台和项目删除确认框，完成后恢复系统原始 100%；
- frozen CLI 通过极短超时完成真实取消路径，退出码为 5，归属临时文件清理，
  非归属哨兵保留；
- 构造持久化运行任务后启动真实 RC3，队列将任务恢复为 `interrupted`，清理
  归属 `.part` 和滤镜脚本，保留非归属哨兵；
- D9 当前完成度更新为 30/31，仅剩麦克风与双音频样本真实听音。

## 2026-07-31 D9 音频设备补证

- 使用锁定 RC3 frozen CLI 分别执行麦克风和系统声音+麦克风录制；
- 双音频模式同时初始化系统 loopback 与麦克风，输出为 AAC 2 声道 48 kHz，
  系统测试音平均 `-41.7 dB`、峰值 `-35.9 dB`；
- 原默认 GS03 和临时默认 G1500 均能被 PyAudio 与 QuickRec 初始化，但实际
  麦克风样本分别接近静音和数字静音，不能作为真人听音通过证据；
- Windows 端点级别复核为 GS03 100、G1500 92，均未静音，排除软件静音和
  端点增益过低；
- 测试后恢复原默认 GS03，关闭声音设置，并停止所有 QuickRec/CLI 进程；
- 本轮没有修改业务代码；D9 保持 30/31，剩余项归类为真实设备环境待验证。

## 2026-07-31 D9 GS03 最终听音补证

- 在默认输入恢复为 HECATE GS03 后，使用同一锁定 RC3 frozen CLI 重新执行
  10 秒麦克风录制；输出 H.264/AAC，平均 `-42.4 dB`、峰值 `-24.2 dB`，
  用户确认可以听见口述；
- 同一候选包执行 10 秒系统声音+麦克风录制，系统端播放受控测试音并同时
  口述；输出 H.264/AAC，平均 `-27.1 dB`、峰值 `-19.6 dB`，用户确认两类
  声音均可听；
- 麦克风 MP4 SHA256 为
  `1E2755AFAFB1B6746357CFA1D45F69E896C864F626925F097196A96D9BFC4766`；
- 双音频 MP4 SHA256 为
  `DCE037E2ACC33BBE7900DE873F770DAB6570D4602FDF5F714DED8F687D03AEF9`；
- 早期静音样本保留为过程证据，不改写历史；最终有效样本、提取 WAV 和
  `record.json` 分别保存在 `mic-gs03-retest2-20260731` 与
  `both-gs03-retest-20260731`；
- 本轮没有修改业务代码；D9 更新为 31/31，ACC 更新为 20/20，当前无延期项
  和发布阻塞。
