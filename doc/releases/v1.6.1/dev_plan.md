# QuickRec Full v1.6.1 开发计划

> 版本：v1.6.1  
> 创建时间：2026-07-15  
> 当前状态：已确认，实施中  
> 产品线：QuickRec Full  
> 上游 IDEA：`IDEA-001`  
> IDEA 来源：[../../archive/ideas/mypm-idea-pool-post-v1.6-2026-07-15.md](../../archive/ideas/mypm-idea-pool-post-v1.6-2026-07-15.md)  
> PRD：[prd.md](prd.md)  
> Progress：[progress.md](progress.md)  
> 原型：[../../prototypes/product-prototype/full.html](../../prototypes/product-prototype/full.html)  
> 建议开发分支：`feature/v1.6.1-pending-ingestion`  
> 进入开发授权：已获得（2026-07-15）

## 1. 开发总览

### 1.1 版本目标

v1.6.1 是 v1.6 素材库的可靠性补丁。核心目标是：录制视频已经保存、正式素材索引写入失败时，持久记录待入库上下文，并在重启后提供一次自动重试和长期可发现的人工恢复入口。

本计划不重新定义 PRD，只把已确认需求转换为可执行开发顺序。

### 1.2 本次包含

| 范围 | 内容 |
| --- | --- |
| 待入库主存储 | `%APPDATA%\QuickRec\pending-recordings.json`、原子写入、损坏保护、200 条上限 |
| 降级标记 | `<video_dir>\QuickRecMetadata\Pending\<pending_id>.json` |
| 发现与合并 | 主文件 + 当前保存目录标记；导入/重建时扫描用户所选目录标记 |
| 入库协调 | 正式入库、失败降级、启动一次重试、手动重试、幂等清理 |
| 素材库 UI | 顶部待入库区、独立计数、详情、重试、重新定位、移除待处理记录 |
| 结果条 | 保留短时重试，并改为调用同一协调服务 |
| 日志 | 待入队、主存储失败、标记降级、自动/手动重试、清理和淘汰语义 |
| 工程拆分 | 最小提取录制后入库协调职责，不改录制核心 |
| 质量门禁 | 新增/修改模块进入 ruff、mypy、coverage 和 packaging 验证 |

### 1.3 本次不包含

| 范围 | 说明 |
| --- | --- |
| 其他失败来源 | 不把迁移、导入、重建、正式素材重新定位失败统一变成待入库任务 |
| 后台任务系统 | 不做周期轮询、无限重试、复杂恢复中心或常驻队列 |
| 素材管理扩张 | 不做搜索、筛选、标签、分类、缩略图和批量操作 |
| 创作者工作台 | 不做项目模型、剪辑、时间线和导出队列 |
| AI | 不做字幕、摘要、章节、标签、实时识别和 AI 参数推荐 |
| 数据平台 | 不引入 SQLite、云同步、账号和跨设备能力 |
| 捕获能力 | 不实现 WGC、120 FPS 或多显示器正式支持 |
| 大重构 | 不全面重写 `QuickRecApp` 或 `RecorderManager` |
| Lite | 不修改 `E:\codex\QuickRec-Lite` |

### 1.4 当前代码 Review

| 模块 | 当前事实 | v1.6.1 承接方式 |
| --- | --- | --- |
| `src/main.py` | `_handle_saved` 直接调用 `_save_material_item`，失败后只保留结果条短时重试 | 改为调用入库协调器；保留 UI 编排和通知职责 |
| `src/services/recording_library.py` | 已封装正式中央索引、媒体校验、重新定位和幂等相关基础 | 增加可复用预生成 ID/按路径查询的最小接口，不承担待入库存储 |
| `src/utils/recording_library_store.py` | 已有正式素材 schema v2、原子写入、备份、200 条规则 | 不改变正式 schema；仅复用路径规范化和数据安全模式 |
| `src/ui/material_library_dialog.py` | 单一正式素材表格和详情区 | 增加待入库数据源、顶部区段、独立操作和状态反馈 |
| `src/ui/toolbar.py` | 索引失败时显示“重试入库”，约 5 秒后结果条关闭 | 保留入口，信号接入同一协调器；不延长为持久 UI |
| `src/utils/media_metadata.py` | 已有源码/打包统一 FFprobe 路径和有效视频校验 | 待入库重新定位和重试必须复用，不复制解析逻辑 |
| `build_std.spec` | 已携带 `ffmpeg.exe`、`ffprobe.exe` 和 v1.6 服务模块 | 添加新增模块 hidden import 或验证自动收集结果 |
| `pyproject.toml` | 服务与素材库 UI 已纳入部分 mypy；历史入口仍有排除 | 新增模块全部纳入；只扩大本轮受影响范围 |
| Full 原型 | 已完成待入库区、独立计数、重试和重新定位演示 | 作为 UI 实现和验收事实源，不再扩充功能 |

### 1.5 关键实现原则

1. **视频优先**：MP4 保存成功后，任何正式索引或待入库存储失败都不能改写保存成功事实。
2. **先正式、后降级**：先尝试正式素材索引；失败后才创建待入库记录。
3. **双层持久化**：先写 APPDATA 主文件，失败后写视频目录单项标记。
4. **统一验证**：正式入库、重试和重新定位共用 v1.6 媒体校验服务。
5. **先验证、后提交**：路径或元数据验证失败时不修改持久记录。
6. **幂等优先**：`material_id`、`pending_id` 和规范化路径共同防止重复。
7. **UI 不写 JSON**：素材库窗口只调用服务，不直接读写待入库文件。
8. **最小拆分**：协调器只承接录制后入库，不进入录制、编码或音频职责。

## 2. PRD 对照与追踪

| PRD 章节 / 验收项 | 开发阶段 | 主要模块 | 完成证据 |
| --- | --- | --- | --- |
| 6.1 新录制失败入队 / V161-P1～P4 | D1-D3 | 待入库存储、入库协调器 | 单元测试、失败注入、日志 |
| 6.2 启动发现与重试 / V161-P5～P6 | D2-D3 | 发现合并、启动任务 | 重启集成测试、GUI 证据 |
| 6.3 手动重试 / V161-P7～P8 | D3-D5 | 协调器、结果条、素材库 | 幂等测试、GUI 证据 |
| 6.4 重新定位 / V161-F1～F3 | D3-D4 | 待入库服务、媒体校验、UI | 有效/损坏/取消测试 |
| 6.5 移除待处理 / V161-F4～F5 | D2-D4 | 待入库服务、UI | 文件保留和清理测试 |
| 7 UI 与交互 | D4 | 素材库、托盘文本、结果条 | UI 测试、三档 DPI 截图 |
| 8 数据设计 | D1-D2 | `PendingRecordingStore` | schema、原子写入、损坏保护测试 |
| 9 状态机 | D2-D3 | `PendingRecordingService`、协调器 | 状态转换测试 |
| 10 最小职责拆分 | D3-D5 | `MaterialIngestionCoordinator` | 架构边界测试 |
| 11 日志语义 | D1-D5 | 全链路 | `caplog`、打包日志取证 |
| 13.3 数量与发现范围 / V161-C1～C5 | D1-D4 | 存储、发现、UI | 200/201、双计数和目录范围测试 |
| 13.5 回归 | D6-D7 | 录制、音频、诊断、素材库 | 全量测试、硬件 smoke、GUI 验收 |
| 14 质量门禁 | D6 | 配置、测试、CI | ruff、mypy、coverage、packaging |

## 3. 文件与模块影响

### 3.1 建议新增文件

| 文件 | 作用 |
| --- | --- |
| `src/utils/pending_recording_store.py` | 待入库 schema、主文件与降级标记原子读写、损坏保护、容量淘汰 |
| `src/services/pending_recordings.py` | 发现、合并、状态转换、重新定位和清理 |
| `src/services/material_ingestion.py` | 正式入库、失败降级、启动重试和手动重试协调 |
| `tests/test_pending_recording_store.py` | 主文件、标记、损坏、合并、200/201 边界 |
| `tests/test_pending_recordings.py` | 发现范围、状态、重新定位和移除 |
| `tests/test_material_ingestion.py` | 新录制入库、自动/手动重试、幂等和双重失败 |

最终文件名可按现有命名风格微调，但“纯存储、待处理业务、入库协调”必须可独立测试。

### 3.2 预计修改文件

| 文件 | 改动范围 |
| --- | --- |
| `src/main.py` | 初始化协调器、转交保存事件、启动一次恢复、汇总通知、素材库依赖注入 |
| `src/services/recording_library.py` | 支持预生成 `material_id`、按 ID/规范路径幂等查询；不修改正式 schema |
| `src/ui/material_library_dialog.py` | 待入库区、独立计数、详情、重试、重新定位和移除待处理记录 |
| `src/ui/toolbar.py` | 结果条重试继续发出事件，成功/失败反馈与协调结果一致 |
| `src/ui/tray_icon.py` | 素材库入口按需要显示待入库数量，不破坏录制中菜单 |
| `src/services/__init__.py` | 暴露新增服务 |
| `src/utils/__init__.py` | 仅在项目现有导出风格需要时补充 |
| `build_std.spec` | 声明或验证新增服务与存储模块进入包 |
| `pyproject.toml` | 新增模块进入 ruff、mypy、coverage；不新增排除项 |
| `.github/workflows/ci.yml` | 如当前命令未覆盖新增门禁，则最小更新测试/类型检查命令 |
| `tests/test_main_workflow.py` | 保存成功、正式入库失败、待处理持久化和启动恢复接入测试 |
| `tests/test_material_library_dialog.py` | 待入库显示、独立计数、操作和空状态测试 |
| `tests/test_toolbar.py` | 结果条短时重试与同一协调器语义测试 |
| `tests/test_tray_icon.py` | 待入库数量与录制中菜单回归 |
| `tests/test_packaging_config.py` | 新增模块、FFprobe 和打包入口检查 |
| `doc/releases/v1.6.1/*` | progress、dev log、test cases、verification、manual verification、bugfix log、release notes |

### 3.3 明确不修改

- `src/recorder/screen_capturer.py`
- `src/recorder/video_encoder.py`
- `src/recorder/audio_capturer.py`
- `src/recorder/recorder_manager.py`，除非实施证明缺少已存在的录制元数据；需要改时必须先回报影响。
- QuickRec Lite 的任何代码、文档、CI、产物和 tag。
- v1.6 正式发布 tag、Release 和历史验收证据。

## 4. 实施顺序与门禁

```mermaid
flowchart LR
    D0["D0 基线与失败测试"] --> D1["D1 待入库存储"]
    D1 --> D2["D2 发现与状态服务"]
    D2 --> D3["D3 入库协调与重试"]
    D3 --> D4["D4 素材库 UI"]
    D4 --> D5["D5 主流程、日志与打包接入"]
    D5 --> D6["D6 自动化与静态门禁"]
    D6 --> D7["D7 独立打包与 GUI 验收"]
```

### D0：基线、受控样本与失败测试

**目标**：固定 v1.6 回滚点、工作区边界和可复现失败契约。

**任务**：

1. 记录 Full 分支、HEAD、tag、远端状态和未提交文档。
2. 确认 `v1.6` tag 指向和 QuickRec Lite 工作区干净。
3. 用户确认承接文档后创建 `feature/v1.6.1-pending-ingestion`。
4. 创建 `dev_log.md`、`bugfix-log.md`、`test-cases.md` 空骨架。
5. 准备正式索引不可写、APPDATA 不可写、视频目录不可写、主文件损坏、重复标记、缺失视频和 201 条记录夹具。
6. 先写会失败的存储、协调、UI 和主流程测试，不写实现绕过测试。

**门禁**：失败测试必须准确失败在“功能尚未存在”，而不是导入错误、夹具错误或真实用户权限污染。

**完成标准**：

- 受控样本不使用真实 `%APPDATA%\QuickRec`。
- 不修改真实用户视频和中央索引。
- 失败测试覆盖 V161-P1～P8、F1～F5、C1～C5 的关键契约。

### D1：待入库存储层

**目标**：完成独立 schema、主文件和降级标记的可靠存储。

**实施要点**：

1. 定义 `PendingRecordingItem`、加载结果和写入结果对象。
2. 实现 `%APPDATA%\QuickRec\pending-recordings.json` 路径解析。
3. 实现 `<video_dir>\QuickRecMetadata\Pending\<pending_id>.json` 路径解析。
4. 使用 UTF-8、同目录临时文件和原子替换。
5. 主文件损坏时保留原件并返回结构化错误，禁止空集合覆盖。
6. 单项标记损坏时跳过该项并记录日志，不阻断其他项。
7. 实现 200 条排序与第 201 条最旧元数据淘汰。
8. 淘汰和移除只删除待处理元数据，不操作 MP4。
9. 实现主记录和单项标记的独立清理。

**验证命令**：

```powershell
python -m pytest tests/test_pending_recording_store.py -q
python -m pytest tests/test_pending_recording_store.py --cov=src/utils/pending_recording_store --cov-branch --cov-report=term-missing
```

**完成标准**：原子写入失败不破坏旧数据；主文件与标记均可独立恢复；核心模块覆盖率不低于 80%。

### D2：发现、合并与待处理状态服务

**目标**：建立不依赖 UI 的待处理业务入口。

**实施要点**：

1. 启动加载主文件，只扫描当前保存目录标记。
2. 导入/重建所选目录时只扫描该目录标记，不递归、不全盘扫描。
3. 以 `pending_id` 为主、规范化绝对路径为辅合并重复记录。
4. 同时存在主记录和标记时保留较新状态、较大尝试次数和稳定素材 ID。
5. 文件不存在时转为 `missing`。
6. 实现运行时 `retrying`，持久状态只保存 `pending`、`retry_failed`、`missing`。
7. 重新定位复用 `probe_media`，先验证后提交。
8. 重新定位失败或保存失败时原记录不变，并保留恢复入口。
9. 移除待处理记录时清理主记录与标记，不删除视频。

**验证命令**：

```powershell
python -m pytest tests/test_pending_recordings.py tests/test_media_metadata.py -q
```

**完成标准**：发现范围符合 PRD；重复标记只显示一项；重新定位事务和移除语义通过测试。

### D3：入库协调、自动重试与幂等

**目标**：把正式索引和待入库恢复串成单一业务链路。

**实施要点**：

1. 新建 `MaterialIngestionCoordinator`。
2. 接收输出路径、录制元数据、诊断目录和预生成 `material_id`。
3. 正式索引成功时不创建待处理记录。
4. 正式索引失败时先写主待入库文件，失败后写降级标记。
5. 双重持久化失败时返回“视频成功、恢复记录未持久化”的结构化结果。
6. 正式服务增加按 `material_id` 和规范化路径的幂等检查。
7. 启动后异步对每条记录最多自动重试一次，不阻塞托盘出现。
8. 自动恢复成功项汇总为一条通知；失败项静默保留并写日志。
9. 结果条和素材库手动重试使用同一方法。
10. 正式写入成功后清理待处理记录；清理失败不回滚正式素材。
11. 下次发现残留标记时识别正式素材已存在并只执行清理。

**建议结果对象**：至少区分 `video_saved`、`formal_indexed`、`pending_persisted`、`already_indexed`、`error_code`、`user_message`。

**验证命令**：

```powershell
python -m pytest tests/test_material_ingestion.py tests/test_recording_library.py -q
```

**完成标准**：每次启动每条最多自动重试一次；重复点击不产生重复正式素材；双重失败不影响 MP4。

### D4：素材库待入库 UI

**目标**：在现有素材库中提供持久、明确且不混淆正式素材的恢复入口。

**实施要点**：

1. 构造待入库与正式素材的统一只读视图模型，保留数据来源类型。
2. 待入库区固定在正式素材上方，独立显示数量。
3. 正式素材分页和“加载更多”不计算待入库项。
4. 支持待入库、正在重试、重试失败、文件缺失状态。
5. 详情显示路径、模式、音频、已知媒体信息、尝试次数、最近时间和失败摘要。
6. 待入库操作：打开、打开目录、复制路径、重试、缺失时重新定位、移除待处理记录。
7. 移除确认文案明确“不删除视频文件”。
8. 正式素材保留 v1.6 原操作，不把“移除待处理”混成“从素材库移除”。
9. 待入库转正式素材后刷新列表、计数、选中态和详情。
10. 只有两类记录都为空时显示“暂无素材”。
11. 托盘素材库入口可显示待入库数量，但不得破坏录制中停止入口。

**验证命令**：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest tests/test_material_library_dialog.py tests/test_tray_icon.py tests/test_toolbar.py -q
```

**完成标准**：原型关键状态均有 UI 测试；关闭窗口不清理记录；正式素材行为无回退。

### D5：主流程、日志和打包接入

**目标**：将协调器接入真实录制完成链路，并固定打包可用性。

**实施要点**：

1. `QuickRecApp` 初始化待入库存储、服务和协调器。
2. `_handle_saved` 改为消费结构化入库结果。
3. 删除或收敛 `_save_material_item`、`_retry_material_item` 中重复业务规则。
4. 视频保存成功时始终保留成功通知；入库失败使用独立警告。
5. 托盘和日志就绪后调度一次启动恢复。
6. 素材库窗口注入正式服务和待处理协调入口。
7. 手动导入/目录重建选定目录时发现降级标记，但不改变其原有正式导入规则。
8. 按 PRD 增加稳定日志事件和错误代码。
9. 日志不输出完整环境变量或无关隐私。
10. `build_std.spec` 明确收集新增模块，并继续验证 FFprobe。

**验证命令**：

```powershell
python -m pytest tests/test_main_workflow.py tests/test_toolbar.py tests/test_tray_icon.py tests/test_packaging_config.py -q
python -m pytest -m packaging -q
```

**完成标准**：源码主流程和受控打包目录均可发现新增模块；视频成功与索引失败语义完全分离。

### D6：自动化、静态门禁与回归

**目标**：关闭自动化和工程质量门禁后再生成候选包。

**执行顺序**：

```powershell
python -m pytest tests/test_pending_recording_store.py tests/test_pending_recordings.py tests/test_material_ingestion.py -q
python -m pytest tests/test_recording_library.py tests/test_recording_library_store.py tests/test_material_library_dialog.py tests/test_main_workflow.py tests/test_toolbar.py tests/test_tray_icon.py -q
python -m pytest -q
python -m pytest -m packaging -q
python -m pytest --cov=src --cov-branch --cov-report=term-missing
python -m ruff check src tests
python -m mypy
python -m compileall -q src tests
git diff --check
```

**附加检查**：

- 新增核心模块单独覆盖率不低于 80%。
- `pyproject.toml` 不为新增模块添加 ruff、mypy 或 coverage 排除。
- UTF-8 中文和乱码检查通过。
- QuickRec Lite 工作区保持干净。

### D7：独立打包、硬件回归与 GUI 验收

**目标**：锁定新的 v1.6.1 候选产物并基于真实桌面完成验收。

**建议打包命令**：

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm `
  --distpath E:\QRtest\QuickRec-v1.6.1-dist `
  --workpath E:\QRtest\QuickRec-v1.6.1-build
```

**候选身份必须记录**：分支、HEAD、dirty 状态、EXE 路径、大小、修改时间、EXE SHA256、FFprobe SHA256。

**硬件与 GUI 验收**：

1. 全屏、区域、窗口录制各至少一次。
2. 无声、系统声音、麦克风和双音频回归。
3. 正式索引失败、主待入库成功。
4. APPDATA 不可写、降级标记成功。
5. 双重写入失败时 MP4 仍可播放。
6. 重启自动恢复成功和仍失败两种路径。
7. 手动重试、重复重试和结果条短时重试。
8. 文件缺失、重新定位有效/损坏/取消。
9. 移除待处理记录不删除视频。
10. 200/201 待入库边界与正式 200 条独立计数。
11. 100%、125%、150% DPI。
12. v1.4.1 诊断和 v1.6 素材库回归。

**停止点**：D7 通过后只允许进入发布收口建议；没有用户授权不得 commit、push、tag 或创建 Release。

## 5. 模块级任务与完成标准

### Task A：待入库数据安全

- 目标：任何写入失败都不损坏旧记录或视频。
- 涉及文件：`pending_recording_store.py`、对应测试。
- 完成标准：原子写入、损坏保留、双层存储、容量和清理测试全部通过。

### Task B：恢复发现与状态

- 目标：在规定目录范围内稳定发现、去重和维护待处理项。
- 涉及文件：`pending_recordings.py`、媒体校验、对应测试。
- 完成标准：启动、所选目录、缺失、重新定位和移除语义闭合。

### Task C：录制后入库协调

- 目标：把视频保存、正式入库和恢复持久化结果清晰分离。
- 涉及文件：`material_ingestion.py`、`recording_library.py`、对应测试。
- 完成标准：主路径、两级降级、自动/手动重试、幂等和清理全部通过。

### Task D：素材库恢复 UI

- 目标：用户能长期发现并处理待入库项。
- 涉及文件：`material_library_dialog.py`、托盘、工具栏和 UI 测试。
- 完成标准：待入库区、状态、操作、独立计数、空状态和 DPI 通过。

### Task E：主流程与打包

- 目标：源码和打包产物使用同一恢复链路。
- 涉及文件：`main.py`、`build_std.spec`、packaging 测试。
- 完成标准：真实录制失败降级可复现；包内模块、FFmpeg、FFprobe 完整。

## 6. 测试与验收策略

### 6.1 自动化层级

| 层级 | 范围 | 证据 |
| --- | --- | --- |
| 单元测试 | schema、路径、合并、状态、容量、错误代码 | 精确断言和临时目录 |
| 服务集成 | 正式索引 + 待入库 + 媒体校验 | 真实 JSON、真实受控 MP4、最少 mock |
| UI 测试 | 区段、计数、按钮、状态、取消、转正式 | Qt offscreen |
| 主流程测试 | 保存结果、通知、启动恢复、短时重试 | 信号和服务调用断言 |
| Packaging | 模块、FFprobe、构建清单 | `-m packaging` |
| 硬件 smoke | 真实桌面录制与可播放 MP4 | `hardware_smoke.py`、FFprobe |
| GUI 验收 | 打包 EXE、权限、重启、DPI | 截图、日志、JSON、哈希 |

### 6.2 受控失败注入

- 所有 APPDATA、ACL、占用和损坏测试使用 `E:\QRtest` 隔离目录。
- 不直接修改真实 `%APPDATA%\QuickRec`。
- 权限和依赖修改前后记录状态并恢复。
- 需要模拟包内依赖故障时复制锁定包到独立目录，不破坏原候选包。

### 6.3 发布阻塞

以下任一失败均阻塞发布：

- MP4 因待入库失败被删除、覆盖或误报保存失败。
- 重启后已持久化待入库项不可发现。
- 重试产生重复正式素材。
- 移除待处理记录删除实际视频。
- 主文件损坏被静默覆盖为空。
- 第 201 条淘汰删除实际视频。
- 打包产物缺少新增模块或 FFprobe。
- QuickRec Lite 被修改。

## 7. 开发日志约定

- 实现开始时创建 `doc/releases/v1.6.1/dev_log.md`。
- 缺陷统一记录到 `doc/releases/v1.6.1/bugfix-log.md`。
- 手动证据记录到 `manual-verification.md`，自动化汇总记录到 `verification.md`。
- `progress.md` 不记录代码排查、失败堆栈、逐次修复或命令流水。
- dev log 记录日期、任务 ID、关键改动、验证结果和未闭合风险。

## 8. 风险与回退

| 风险 | 触发条件 | 影响 | 处理与回退 |
| --- | --- | --- | --- |
| 主文件和标记状态分叉 | 一层写入或清理失败 | 重复显示或重复重试 | 合并去重；正式索引幂等；残留标记只清理不重复入库 |
| 启动重试阻塞 UI | 同步处理大量记录或 FFprobe 慢 | 托盘迟迟不出现 | UI 就绪后后台执行；每条一次；必要时限制单批调度 |
| 双重持久化失败 | APPDATA 和视频目录都不可写 | 无跨重启恢复证据 | 保留 MP4、短时重试、打开目录和明确日志；不伪造成功 |
| 待入库损坏覆盖 | 解析失败后直接保存空列表 | 用户丢失恢复记录 | 保留损坏原件；加载失败时禁止覆盖；修复后定向复验 |
| 重试重复入库 | 结果条、启动和素材库并发 | 正式素材重复 | 协调器锁、稳定 ID、规范路径检查和串行正式写入 |
| 清理失败 | 正式入库成功但待处理删除失败 | 下次再次发现 | 视为正式成功；下次幂等发现后继续清理 |
| UI 复杂度回流 | 窗口直接操作两套 JSON | 难测和状态不一致 | UI 仅依赖服务/协调器；架构测试禁止直接写文件 |
| 范围扩大 | 顺手统一迁移/重建失败队列 | 延期和回归 | 停止实施并返回 PRD；本版只处理新录制自动入库失败 |
| 证据失效 | 业务代码或候选包哈希变化 | 旧 GUI 证据不可继承 | 仅重测受影响链路并重新锁定产物 |

### 8.1 代码回退

- 以 v1.6 发布 tag 为代码回滚点。
- 不修改 v1.6 正式素材 schema，因此无需回滚中央索引。
- 回滚时保留待入库主文件和降级标记，等待重新升级恢复。

### 8.2 数据回退

- 禁止通过删除 `pending-recordings.json` 作为代码回退步骤。
- 禁止批量删除 `QuickRecMetadata\Pending`。
- 若新功能必须停用，可停止读取和重试，但保留数据与视频。

## 9. 开放问题

当前无阻塞性产品问题。以下属于实施选择，必须遵守既有契约：

1. UI 使用单表分段行还是两个表格：推荐单窗口内两个清晰区段，以测试可维护性和窄窗口表现为准。
2. 启动任务使用 Qt 线程还是现有后台任务封装：推荐复用 `_LibraryTask` 模式或等价受控 worker，不新增通用任务框架。
3. 模块最终命名可按项目风格调整，但不得合并回 `main.py` 或 UI 类。

## 10. 开发承接结论

- PRD 完整性：通过。
- 原型完整性：通过，浏览器关键交互已验证。
- 模块边界：可按增量方式实现，无需改录制核心。
- 当前阻塞：无。
- 下一步：从 D0 开始，严格按 `progress.md` 顺序执行，每完成一个最小任务同步状态。
