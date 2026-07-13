# QuickRec Full v1.6 开发计划

> 版本：v1.6
> 创建时间：2026-07-10
> 状态：D0-D6 已执行 / D7 GUI 手动验收待执行
> 产品线：QuickRec Full
> IDEA 来源：[../../archive/ideas/mypm-idea-pool-v1.6-2026-07-10.md](../../archive/ideas/mypm-idea-pool-v1.6-2026-07-10.md)
> PRD：[prd.md](prd.md)
> Progress：[progress.md](progress.md)
> 原型：[../../prototypes/product-prototype/full.html](../../prototypes/product-prototype/full.html)
> 建议开发分支：`feature/v1.6-material-library`

---

## 1. 开发总览

### 1.1 目标

v1.6 将 v1.5 的“最近录制”升级为跨保存路径的轻量素材库，完成三层能力：

- 产品主线：中央素材索引、稳定素材 ID、200 条历史和统一素材库入口。
- 数据可靠性：v1.5 历史迁移、备份恢复、手动导入、目录重建和重新定位。
- 工程支撑：抽取 `RecordingLibraryService`，扩大本轮 ruff、mypy 和 coverage 的真实覆盖。

本计划不重新定义 PRD，不实现完整工作台、AI、WGC、120 FPS 或多显示器正式支持。

### 1.2 本次包含

| 范围 | 内容 |
| --- | --- |
| D0 发布债 | CI 自启测试隔离、统一版本事实源、v1.5 发布事实收口 |
| 中央索引 | `%APPDATA%\QuickRec\recordings.json`、schema v2、200 条上限 |
| 迁移导入 | 当前路径首次迁移、其他目录手动导入、切换路径提示一次 |
| 数据恢复 | 原子写入、1 份有效备份、最多 5 份损坏归档 |
| 目录重建 | 当前层级 `QuickRec_*.mp4`、不递归、可取消、确认后提交 |
| 文件关联 | 单项重新定位、候选匹配人工确认、稳定 ID |
| 元数据 | 时长、分辨率、FPS、模式、音频、大小、状态 |
| 文件操作 | 从素材库移除、单个 MP4 移入 Windows 回收站 |
| UI | “素材库”统一入口、左列表右详情、加载更多、完整状态反馈 |
| 原型 | 更新现有 Full HTML 原型与说明 |
| 工程门禁 | 新增/修改模块 ruff、mypy；新增核心模块 coverage ≥80% |

### 1.3 本次不包含

| 范围 | 说明 |
| --- | --- |
| 数据库与云 | 不引入 SQLite、账号、云同步或跨设备索引 |
| 完整工作台 | 不做项目管理、内嵌预览、编辑、时间线和导出队列 |
| AI | 不实现模型、字幕、摘要、章节、标签或实时 AI |
| 捕获能力 | 不接入 WGC，不提高到 120 FPS，不做多显示器正式支持 |
| 通用媒体库 | 不扫描磁盘、不递归、不导入非 QuickRec 视频 |
| 高级素材管理 | 不做搜索、筛选、收藏、批量删除和缩略图分析 |
| 大重构 | 不全面重写 `QuickRecApp`、`RecorderManager` |
| Lite | 不修改 `E:\codex\QuickRec-Lite` |

### 1.4 当前代码 Review

| 模块 | 当前事实 | v1.6 承接方式 |
| --- | --- | --- |
| `src/utils/recording_history.py` | schema v1，按保存路径存储，最多 50 条，已有稳定 ID 和原子写入 | 保留为兼容输入；中央索引能力迁入新服务，不直接破坏旧解析 |
| `src/ui/recent_recordings_dialog.py` | 单表格、5 列、只读当前保存路径 | 升级为素材库窗口或由新窗口替代 |
| `src/main.py` | 保存回调直接调用历史工具 | 改为调用 `RecordingLibraryService`，只保留 UI 编排 |
| `src/recorder/recorder_manager.py` | 已能提供保存结果，但元数据上下文不完整 | 只补录制会话已知元数据，不加入素材库逻辑 |
| `src/config.py` | 配置位于 `%APPDATA%\QuickRec\config.json` | 复用应用数据根目录，不新增用户可见索引路径配置 |
| `src/ui/tray_icon.py` | 空闲/录制中菜单均有“最近录制” | 统一改名“素材库”，保留信号桥 |
| `src/ui/toolbar.py` | 结果条提供最近录制入口 | 统一改名并保持保存结果行为 |
| `build_std.spec` | 只携带 `ffmpeg.exe` | 增加 `ffprobe.exe` 和回收站依赖所需声明 |
| `pyproject.toml` | UI、main 等存在排除；mypy 仅覆盖部分文件 | 只纳入本轮新增/修改模块，避免一次清理全部旧债 |
| `doc/prototypes/product-prototype/full.html` | 已有 v1.5 最近录制模拟 | D1 更新为 v1.6 素材库完整状态 |

### 1.5 PRD 对照表

| PRD 需求 | 开发阶段 | 完成证据 |
| --- | --- | --- |
| D0 发布债收口 | D0 | 本地/CI 绿灯、版本一致、Git 状态记录 |
| M7 原型同步 | D1 | Full HTML 原型与说明评审通过 |
| M1 中央索引 | D2 | schema v2、200 条、原子写入和扩展保留测试 |
| M2 v1.5 迁移与导入 | D3 | 迁移、幂等、提示一次和旧索引不变测试 |
| M3 恢复、重建、重新定位 | D3-D4 | 损坏恢复、取消、候选确认、ID 保持测试 |
| M5 元数据 | D4 | 新录制字段、打包 `ffprobe` 和失败降级测试 |
| 回收站删除 | D4 | Windows 回收站与索引同步测试 |
| M4 素材库 UI | D5 | 双入口、列表详情、加载更多和状态测试 |
| M6 服务拆分 | D2-D5 | `RecordingLibraryService` 成为唯一业务入口 |
| M7 工程门禁 | D6 | ruff、mypy、coverage 和 CI 通过 |
| 发布前验收 | D7 | 打包、硬件 smoke、GUI 手动验收 |

## 2. 建议模块与文件

### 2.1 新增文件

| 文件 | 作用 |
| --- | --- |
| `src/services/__init__.py` | 服务层包声明 |
| `src/services/recording_library.py` | `RecordingLibraryService`，编排索引、迁移、恢复和文件操作 |
| `src/utils/recording_library_store.py` | schema v2 解析、原子写入、备份、损坏归档 |
| `src/utils/media_metadata.py` | `ffprobe` 路径解析、超时、结果转换和失败降级 |
| `src/utils/recycle_bin.py` | Windows 回收站单文件操作 |
| `src/ui/material_library_dialog.py` | 素材库窗口、后台任务状态和用户操作 |
| `tests/test_recording_library.py` | 服务主行为测试 |
| `tests/test_recording_library_store.py` | 存储、备份和恢复测试 |
| `tests/test_recording_library_migration.py` | schema v1 迁移、幂等和来源状态测试 |
| `tests/test_recording_library_scan.py` | 重建过滤、取消、候选和提交测试 |
| `tests/test_media_metadata.py` | `ffprobe` 成功、失败、超时和取消测试 |
| `tests/test_recycle_bin.py` | 回收站接口成功/失败测试 |
| `tests/test_material_library_dialog.py` | 素材库 UI 状态与交互测试 |

文件数量可以在实现时收敛，但必须保持“服务编排、纯存储、外部工具、UI”四类职责可独立测试。禁止为了减少文件再次把全部逻辑塞回 `main.py`。

### 2.2 修改文件

| 文件 | 修改范围 |
| --- | --- |
| `src/main.py` | 初始化服务、转交保存事件、打开素材库、反馈索引失败 |
| `src/recorder/recorder_manager.py` | 在保存结果中提供时长、宽高、FPS、模式和音频上下文 |
| `src/utils/recording_history.py` | 保留 schema v1 兼容读取；移除新记录主入口职责或提供适配层 |
| `src/ui/tray_icon.py` | “最近录制”改为“素材库” |
| `src/ui/toolbar.py` | 结果条入口改名并支持索引失败重试动作 |
| `src/ui/settings_dialog.py` | 保存路径切换后的旧索引一次性提示 |
| `src/config.py` | 统一应用数据根目录与版本事实引用，不新增索引路径设置 |
| `build_std.spec` | 打包 `ffprobe.exe` 与回收站依赖 |
| `requirements.txt` / `requirements-dev.txt` | 仅在确认回收站实现需要依赖时更新 |
| `pyproject.toml` | 纳入本轮模块的 ruff、mypy 和 coverage |
| `.github/workflows/ci.yml` | 保证开发分支/PR 路径运行完整门禁，不操作真实 HKCU |
| `tests/test_main_workflow.py` | 保存成功/索引失败、服务调用和入口测试 |
| `tests/test_settings_dialog.py` | 路径切换提示测试 |
| `tests/test_tray_icon.py` | 素材库菜单测试 |
| `tests/test_toolbar.py` | 素材库和重试入口测试 |
| `doc/prototypes/product-prototype/full.html` | v1.6 素材库高保真交互 |
| `doc/prototypes/product-prototype/prototype-design.md` | 页面、状态和 v1.6 对应关系 |

### 2.3 不建议移动或删除

- 不删除 v1.5 `recording_history.py`，直到迁移和回滚全部通过。
- 不移动 v1.5 release 文档和 tag。
- 不删除保存目录中的 `QuickRecMetadata\recordings.json`。
- 不清理用户视频、诊断目录或未知旁车文件。
- 不修改 QuickRec Lite。

## 3. 实施顺序

### D0：发布债、分支与受控样本

**目标**：在可信门禁上开始 v1.6，固定数据样本和回滚点。

**任务**：

1. 记录 `master` HEAD、`v1.5` tag 和工作区未提交内容。
2. 先提交或明确隔离已确认的 v1.6 PRD、计划和需求池。
3. 从最新 Full `master` 创建 `feature/v1.6-material-library`。
4. 修复开机自启测试，不允许测试修改真实 HKCU。
5. 建立单一版本事实源，供诊断、构建和文档读取。
6. 收口 v1.5 Release URL、资产 SHA 和当前事实入口。
7. 准备 schema v1 正常、重复、损坏、缺失、超过 200 条的受控样本。
8. 准备两个保存目录和符合/不符合 QuickRec 命名规则的视频。

**涉及文件**：

- `.github/workflows/ci.yml`
- `src/utils/autostart.py` 或现有自启实现
- `tests/test_v1_2.py`
- 版本事实源及其测试
- `doc/current.md`、v1.5 发布资料（只做事实收口）

**验证**：

```powershell
git status --short --branch
git tag --points-at HEAD
python -m pytest tests/test_v1_2.py -q
python -m compileall -q src tests
python -m ruff check src tests
python -m mypy
```

**完成标准**：

- 测试前后真实 HKCU 不变。
- 版本信息只有一个事实源。
- 样本与预期结果清单可重复使用。
- Lite 工作区无修改。

**回退**：D0 仅做门禁和事实收口；若 CI 调整不稳定，回退对应测试隔离提交，不进入 D2 数据开发。

### D1：Full 原型同步与交互冻结

**目标**：在实现 UI 前确认素材库信息架构和全部状态。

**实施要点**：

1. 将 Full 原型“最近录制”统一升级为“素材库”。
2. 合并重复的“最近录制/素材”概念，保留单一当前入口。
3. 实现左列表、右详情和窄窗口上下布局表达。
4. 表达默认 50 条、加载更多、200 条上限。
5. 表达迁移摘要、手动导入、重建进度、候选确认和取消。
6. 表达空、缺失、元数据不完整、恢复成功、恢复失败和写入失败。
7. 分离“从素材库移除”和“移入回收站”危险操作。
8. 更新 `prototype-design.md` 的 v1.6 页面和范围说明。

**验证**：

- 通过本地 HTTP 服务加载原型。
- 使用浏览器自动化点击所有状态入口。
- 检查桌面与窄窗口截图，无文本遮挡或状态死路。
- PRD 与原型逐项对照。

**完成标准**：原型评审通过后才能进入 D5 UI 实现；数据层 D2 可在原型评审期间并行准备纯逻辑测试。

### D2：中央索引模型、存储与服务边界

**目标**：建立 schema v2 中央索引、可靠写入和最小服务层。

**实施要点**：

1. 定义 schema v2 根结构和素材数据模型。
2. 实现 `%APPDATA%\QuickRec\recordings.json` 路径解析。
3. 实现 Windows 路径规范化与稳定素材 ID。
4. 实现按 `created_at` 排序和 200 条裁剪。
5. 保留未知 `extensions` 字段。
6. 实现同目录临时文件写入和原子替换。
7. 实现 1 份有效备份和最多 5 份损坏归档。
8. 实现单条损坏降级、整体损坏恢复和恢复失败结果。
9. 建立 `RecordingLibraryService`，避免 UI 或 main 直接操作 JSON。

**建议测试顺序**：先写纯逻辑失败测试，再实现最小通过代码。

**验证**：

```powershell
python -m pytest tests/test_recording_library_store.py tests/test_recording_library.py -q
python -m pytest tests/test_recording_library_store.py tests/test_recording_library.py --cov=src/services --cov=src/utils/recording_library_store --cov-report=term-missing
```

**完成标准**：原子写入失败不破坏旧索引；损坏恢复可追溯；重复写入不产生重复记录。

**回退**：服务未接主流程前可整体回退 D2；不得修改或删除旧 schema v1 文件。

### D3：v1.5 迁移、导入与目录重建事务

**目标**：安全承接旧数据，所有批量操作都可取消且确认前不写中央索引。

**实施要点**：

1. 使用现有 `recording_history.py` 解析 schema v1。
2. 保留旧 ID、创建时间和可靠字段，补充来源与导入时间。
3. 迁移前后计算旧索引哈希，证明未修改。
4. 实现首次只检查当前保存路径。
5. 实现每来源一次性提示状态和幂等迁移。
6. 实现手动导入旧目录；旧索引不可读时转入重建建议。
7. 实现非递归 `QuickRec_*.mp4` 扫描过滤。
8. 扫描只生成临时结果和摘要，确认后一次性提交。
9. 实现取消令牌，2 秒内停止调度新任务。
10. 目录候选超过 200 时按推断录制时间保留最近 200 条并提示。

**线程边界**：纯扫描和 `ffprobe` 在后台；索引最终提交由服务串行执行；Qt 主线程只更新 UI 状态。

**验证**：

```powershell
python -m pytest tests/test_recording_library_migration.py tests/test_recording_library_scan.py -q
```

**完成标准**：取消前后中央索引哈希一致；同来源重复迁移无新增；非 QuickRec 文件和子目录不被扫描。

**回退**：关闭迁移/导入入口，新录制仍可写中央索引；旧索引保持原样。

### D4：元数据、重新定位与回收站

**目标**：补齐基础素材信息和安全文件操作。

**实施要点**：

1. 明确 `ffprobe.exe` 来源、版本、许可证和运行路径。
2. 封装 `ffprobe` JSON 输出解析、超时、取消和错误上下文。
3. 新录制优先使用会话已知元数据，不重复启动 `ffprobe`。
4. 旧素材只在迁移/重建或用户触发时解析缺失字段。
5. 实现单项重新定位，重复路径时定位已有素材。
6. 实现文件名、大小、修改时间辅助候选；禁止自动改路径。
7. 重新定位后保留素材 ID 和原始时间。
8. 选择 Windows 回收站实现，禁止永久删除回退。
9. 回收站成功后更新索引；索引失败时下次加载识别为缺失。
10. 只处理选中 MP4，不处理诊断目录或未知旁车文件。

**验证**：

```powershell
python -m pytest tests/test_media_metadata.py tests/test_recycle_bin.py tests/test_recording_library.py -q
python -m pytest -m packaging -q
```

**完成标准**：开发环境和打包路径都能运行 `ffprobe`；回收站失败不永久删除；重新定位 ID 不变。

**回退**：元数据失败可降级为空字段；回收站能力不可靠时移除“删除视频文件”入口，但“从素材库移除”必须保留。

### D5：素材库 UI 与主流程接入

**目标**：完成用户可见闭环，同时保持录制保存优先。

**实施要点**：

1. 实现素材库窗口及 50 条初始加载。
2. 实现每次加载更多 50 条，最多 200 条。
3. 实现左列表、右详情和窄窗口布局。
4. 实现可用、缺失、元数据不完整、空、加载失败状态。
5. 实现打开、目录、复制、重新定位、移除和回收站操作。
6. 实现迁移摘要、导入/重建进度、取消和预览确认。
7. 托盘空闲/录制中菜单统一为“素材库”。
8. 结果条统一为“素材库”，索引失败时提供重试入库和打开目录。
9. 保存路径切换后检测旧索引，每目录只提示一次。
10. 主流程保存成功后把录制上下文交给服务；服务失败不改变录制成功状态。
11. 素材库已打开时增量刷新，不抢占用户选择。

**验证**：

```powershell
python -m pytest tests/test_material_library_dialog.py tests/test_main_workflow.py tests/test_settings_dialog.py tests/test_tray_icon.py tests/test_toolbar.py -q
```

**完成标准**：两个入口打开一致窗口；完整链路无死路；索引不可写时视频仍保存成功。

**回退**：UI 失败时可回退到只读素材列表，但不得发布缺少迁移/恢复入口的半成品；具体回退需在 bugfix 阶段依据失败范围决定。

### D6：质量门禁、日志与文档同步

**目标**：将新增数据能力纳入真实工程门禁，并保持文档事实一致。

**实施要点**：

1. 将 `src/services/**`、素材存储和媒体元数据工具纳入 ruff/mypy。
2. 将素材库核心逻辑纳入 coverage，新增核心模块不低于 80%。
3. UI 可测试纯逻辑不再因目录排除而完全失去覆盖。
4. 为迁移、恢复、重建、重新定位、回收站和 `ffprobe` 增加结构化日志。
5. 更新 PRD 状态、progress 和必要 dev log；bugfix 单独记录。
6. 更新 `doc/current.md`、README、release notes 和 changelog 的 v1.6 候选状态。
7. 检查所有正式文档为 UTF-8 中文，无旧路径和 Full/Lite 混线。

**验证**：

```powershell
python -m compileall -q src tests
python -m ruff check src tests
python -m mypy
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80
git diff --check
```

**完成标准**：CI 与本地结果一致；新增模块无静态检查排除逃逸；文档状态可追溯。

### D7：打包、硬件回归与 GUI 验收

**目标**：基于独立 v1.6 打包产物完成发布前证据闭环。

**实施顺序**：

1. 使用独立 `distpath` 和 `workpath` 打包，不覆盖 v1.5 稳定产物。
2. 记录分支、HEAD、EXE 路径、大小和 SHA256。
3. 验证打包内 `ffmpeg.exe`、`ffprobe.exe` 和回收站能力。
4. 运行全屏、区域、窗口硬件 smoke。
5. 回归无声、系统声、麦克风和双音频。
6. 使用受控 APPDATA 和两个保存目录执行迁移与跨路径验收。
7. 执行 200 条、加载更多、损坏恢复、取消和写入失败场景。
8. 执行重新定位、从素材库移除和回收站删除。
9. 检查 100%、150%、200% DPI 布局。
10. 自动验证 Full 原型；必要项目由用户手动补证。
11. 更新 `manual-verification.md`，只在 progress 写状态和结论。

**建议打包命令**：

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm `
  --distpath E:\QRtest\QuickRec-v1.6-dist `
  --workpath E:\QRtest\QuickRec-v1.6-build
```

**硬件 smoke**：

```powershell
python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode fullscreen
python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode area
python scripts\hardware_smoke.py --output-dir E:\QRtest --duration 3 --mode window
```

**完成标准**：PRD V16-D0-1 至 V16-Lite 全部有真实证据；存在人工待验证项时只能判定部分通过，不得进入发布收口。

## 4. 测试与验收策略

### 4.1 自动化层次

| 层次 | 重点 | 不允许的替代 |
| --- | --- | --- |
| 单元测试 | schema、去重、排序、裁剪、备份、迁移、取消 | 只测正常路径 |
| 服务测试 | 入库、恢复、重建、重新定位、删除状态同步 | 直接操作真实用户 APPDATA |
| UI 测试 | 列表详情、加载更多、反馈、按钮状态 | 只靠 HTML 原型 |
| 主流程测试 | 视频成功/索引失败、入口和保存上下文 | 把索引失败误作录制失败 |
| 打包测试 | `ffprobe`、回收站依赖和资源路径 | 用开发环境通过代替 |
| 硬件验收 | 三种模式、四种音频、DPI | 用 mock 代替真实录制 |

### 4.2 受控环境

- 所有迁移、损坏和权限测试必须使用临时 APPDATA。
- 回收站测试只处理专门生成的受控 MP4。
- 测试前备份用户配置，结束后恢复。
- 不修改真实旧索引、视频和 HKCU。
- QuickRec Lite 只检查 Git 状态，不运行或修改其业务文件。

### 4.3 验收文档

建议新增：

```text
doc/releases/v1.6/test-cases.md
doc/releases/v1.6/manual-verification.md
doc/releases/v1.6/bugfix-log.md
doc/releases/v1.6/dev_log.md
doc/releases/v1.6/release-notes.md
doc/releases/v1.6/changelog.md
```

- `progress.md` 只记录任务状态、阻塞、最近验证和下一步。
- `dev_log.md` 记录开发阶段、关键实现和技术决策。
- `bugfix-log.md` 记录真实缺陷、证据、最小修复和复验。

## 5. 风险与回退

| 风险 | 触发条件 | 处理 | 回退 |
| --- | --- | --- | --- |
| 迁移破坏旧索引 | 旧文件哈希变化 | 立即停止迁移，保留证据 | 回退迁移提交，旧索引继续由 v1.5 使用 |
| 中央索引半写入 | JSON 无法解析或数据截断 | 修复原子替换与备份顺序 | 从 `.bak` 恢复，损坏文件归档 |
| 取消后写入部分结果 | 扫描取消但项目数变化 | 修复事务提交边界 | 禁用导入入口，不影响新录制入库 |
| 重新定位误匹配 | 未经确认自动改路径 | 阻断发布 | 回退自动匹配，只保留手动选择 |
| 回收站实现永久删除 | 回收站失败后调用 unlink | 严重阻断 | 删除“视频文件删除”入口 |
| `ffprobe` 缺失 | 打包产物无法解析元数据 | 修复 spec 和资源路径 | 元数据降级不可代替依赖修复 |
| UI 卡顿 | 200 条或批量探测冻结主线程 | 转后台、限制并发 | 暂停重建入口，不回退中央索引 |
| 服务拆分扩大 | 大量无关核心文件被改 | 缩小到素材职责 | 回退无关重构提交 |
| Full/Lite 混线 | Lite 出现本轮改动 | 停止开发并隔离 | 只保留 Full 提交 |

## 6. 开发纪律

- 严格按 `progress.md` 顺序推进，每完成一个最小任务同步状态。
- 先写失败测试，再实现数据迁移、恢复、重新定位和删除逻辑。
- 每个阶段完成后运行对应测试，不把所有验证推到 D7。
- 不因实现方便改变 PRD 数据安全和取消语义。
- 不提前实现完整工作台、AI、搜索、缩略图或捕获后端升级。
- 不移动 `v1.5`、`v1.4.1` 或 Lite tag。
- 不修改 QuickRec Lite。
- 开发日志和 bugfix 不写入 progress 主体。

## 7. 当前开放技术项

以下项目必须在对应阶段记录决策，但不需要重新进入产品澄清：

| 项目 | 决策期限 | 判断标准 |
| --- | --- | --- |
| `RecordingLibraryService` 内部文件拆分 | D2 开始前 | 纯存储、编排、外部工具可独立测试 |
| Qt 后台任务机制 | D3 开始前 | 可取消、主线程不阻塞、窗口关闭可回收 |
| `ffprobe` 来源与版本 | D4 开始前 | 与 FFmpeg 版本兼容、许可证明确、可打包 |
| Windows 回收站实现 | D4 开始前 | 不永久删除、错误可诊断、PyInstaller 可用 |
| UI 窄窗口断点 | D1 原型评审 | 100%-200% DPI 无重叠，操作不丢失 |

## 8. 下一阶段入口

开发开始前应确认：

1. 本计划和 [progress.md](progress.md) 已通过。
2. 当前工作区未提交内容已盘点，v1.5 文档残留不混入业务提交。
3. 建议分支 `feature/v1.6-material-library` 已从正确 Full `master` 创建。
4. D0 先执行，D0 未通过不进入 D2-D5 主链路。
5. D1 原型与 D2 纯数据层可有限并行，但 D5 UI 必须等待原型冻结。
