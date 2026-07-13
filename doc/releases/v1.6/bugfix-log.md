# QuickRec Full v1.6 Bugfix Log

## BUG-V16-D0-001 开机自启测试操作真实用户注册表

- 状态：已修复，待 CI 复验。
- 发现阶段：D0 发布债收口。
- 影响：本地或 CI 测试会直接创建、查询和删除 HKCU Run 中的 `QuickRec`，并且 Run 键缺失时 `enable_autostart()` 可能失败。
- 根因：历史测试未隔离 `winreg`；生产实现使用只打开现有键的 `OpenKey`。
- 最小修复：测试完全 mock `winreg`；生产开启逻辑使用 `CreateKeyEx`。
- 自动验证：`tests/test_v1_2.py` 26 passed。
- 人工证据：测试前后 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\QuickRec` 均不存在。
- 回归范围：设置页开机自启开关仍需在打包 GUI 验收中验证。

## BUG-V16-D0-002 诊断报告固化旧版本号

- 状态：已修复。
- 发现阶段：D0 发布债收口。
- 影响：v1.5 及后续版本的诊断文本仍显示 `v1.4.x`，排查证据不可信。
- 根因：`src/main.py` 直接写死版本字符串，测试未约束当前产品版本。
- 最小修复：新增 `src/version.py` 单一事实源，诊断报告读取 `APP_VERSION`。
- 自动验证：新增当前版本断言；`tests/test_main_workflow.py tests/test_diagnostics.py` 25 passed。

## BUG-V16-D5-001 素材刷新后抢占当前选择

- 状态：已修复。
- 发现阶段：D5 素材库 UI 测试。
- 影响：新录制插入列表顶部后，表格仍保留原行号，详情会跳到新素材，打断用户查看。
- 根因：刷新时只重建行，没有按稳定素材 ID 恢复选择。
- 最小修复：刷新前记录选中素材 ID，重建列表后按 ID 恢复行选择。
- 自动验证：`test_reload_keeps_current_selection_when_new_record_arrives` 通过。

## BUG-V16-D5-002 结果条保留旧按钮字段引用

- 状态：已修复。
- 发现阶段：D5 入口统一与静态检查。
- 影响：结果条从“最近录制”迁移到“素材库”后，录制态按钮切换仍引用已删除的 `_btn_recent`，特定状态恢复可能抛出属性错误。
- 根因：入口重命名时遗漏内部隐藏逻辑。
- 最小修复：统一改为 `_btn_material`，并增加素材库与重试入库信号测试。
- 自动验证：`tests/test_toolbar.py` 全部通过。

## BUG-V16-D6-001 ffprobe 就位后旧编码格式测试暴露无效参数

- 状态：已修复。
- 发现阶段：D6 packaging 标记测试。
- 影响：v1.6 加入 `ffprobe.exe` 后，过去被跳过的 H.264 格式断言开始执行，但因测试命令无效而返回空输出。
- 根因：旧测试使用 `-show_entries codec_name`，ffprobe 要求写为 `-show_entries stream=codec_name`；编码产物本身是有效 H.264。
- 证据：同一受控 MP4 使用旧参数返回码 1 和 `No match for section 'codec_name'`，使用正确参数返回码 0 和 `codec_name=h264`。
- 最小修复：修正测试参数并显式断言 ffprobe 返回码，不修改 `VideoEncoder`。

## BUG-V16-D7-001 打包产物重建与重新定位无法解析有效 MP4 元数据

- 状态：已修复并通过新候选包定向复验。
- 发现阶段：D7 第二批 GUI 验收。
- 严重度：发布阻塞。
- 复现：使用锁定包在素材库点击“重建目录”，选择包含两个有效 H.264 MP4 的受控目录；或对缺失记录重新定位到同一有效 MP4。
- 预期：有效视频进入可用状态，并写入时长、分辨率和 FPS。
- 实际：有效视频均显示“元数据不完整”，时长、分辨率和 FPS 为空。
- 交叉证据：包内 `ffprobe.exe` 单独解析两个文件均返回 H.264、852x480、30 FPS、3.1 秒。
- 证据：`E:\QRtest\QuickRec-v1.6-acceptance\second-batch\evidence\A4-rebuild-result.jpg`、`B1-valid-relink.jpg`、`B-file-actions.json`。
- 根因状态：待定位；现象指向打包运行时 `probe_media` 的 ffprobe 路径解析、启动或超时链路，不能仅依据现象直接定根因。
- 最小修复建议：记录实际 ffprobe 路径、返回码、stderr 和超时上下文；确保打包环境重建和重新定位使用包内 ffprobe；增加锁定包级受控视频测试。
- 回归要求：目录重建与重新定位分别使用有效视频验证完整元数据，并保留 GUI、日志和 FFprobe 对照证据。
- 根因：无控制台的 Windows 打包进程使用系统默认 GBK 解码 `subprocess.run(text=True)` 输出；FFprobe 返回的 UTF-8 JSON 包含中文路径时，读取线程发生 `UnicodeDecodeError`，进程返回码仍为 0，但 `stdout` 变为 `None`，随后被统一降级为元数据不完整。
- 修复：FFprobe 调用显式使用 UTF-8 严格解码、参数数组和统一的源码/冻结环境定位逻辑；分别记录不存在、启动失败、超时、非零返回、JSON 损坏及字段缺失。
- 自动验证：受影响测试 84 passed；全量测试 339 passed、24 deselected、22 subtests passed；packaging 12 passed；coverage 83.65%；ruff、mypy、compileall 通过。
- 新候选：`E:\QRtest\QuickRec-v1.6-bugfix-dist\QuickRec\QuickRec.exe`，SHA256 `69D092DDAF48757D4941429AB10D74072EE2E0B9ED07783CA43BE9D7C8F3551F`。
- 定向复验：扫描 3 个 MP4，2 个有效文件以 `3 秒 / 852 × 480 / 30 FPS` 入库，1 个损坏 MP4 失败；非视频未扫描。证据：`E:\QRtest\QuickRec-v1.6-bugfix-acceptance\evidence\11-rebuild-preview-2.jpg`、`12-rebuild-success.jpg`。

## BUG-V16-D7-002 重新定位接受不可解析 MP4 并禁用再次定位

- 状态：已修复并通过新候选包定向复验。
- 发现阶段：D7 第二批 GUI 验收。
- 严重度：重要缺陷，当前按发布阻塞处理。
- 复现：对缺失素材点击“重新定位”，选择扩展名为 `.mp4` 但内容不可解析的受控文件。
- 预期：显示失败反馈，原索引路径与缺失状态保持不变，用户仍可重新选择。
- 实际：程序更新索引路径和文件名，将状态改为“元数据不完整”，并禁用“重新定位”按钮。
- 影响：用户可能把缺失记录错误绑定到损坏文件，且无法在同一界面直接纠正。
- 证据：`E:\QRtest\QuickRec-v1.6-acceptance\second-batch\evidence\B1-invalid-relink-accepted.jpg`。
- 根因状态：已确认服务层只校验文件存在和 `.mp4` 扩展名，`probe_media` 失败仍写入新路径并返回成功。
- 最小修复建议：重新定位时将元数据解析失败视为操作失败，不修改原记录；保留可重试状态和中文错误反馈。
- 根因：旧实现只检查文件存在和 `.mp4` 扩展名，并在确认媒体可解析前修改索引路径；探测失败仍作为“元数据不完整”的成功结果提交，导致原记录被污染且恢复入口禁用。
- 修复：重新定位改为“先验证，后提交”；探测失败保持原索引、原缺失状态和重新定位入口；成功后一次性更新路径及完整元数据，索引保存失败时回滚内存状态。手动导入和目录重建复用同一媒体验证服务。
- 定向复验：损坏 MP4 被拒绝，原路径不变且仍可重新定位；随后选择中文空格路径中的有效 MP4 成功，重启后路径及 `3 秒 / 852 × 480 / 30 FPS` 保持。证据：`E:\QRtest\QuickRec-v1.6-bugfix-acceptance\evidence\21-relink-corrupt-rejected.jpg`、`22-relink-valid-success.jpg`、`40-restart-persistence.jpg`。

## GAP-V16-D7-003 重试入库缺少持久恢复入口

- 状态：已确认延后，不阻塞 v1.6；进入后续版本候选池。
- 证据：现有失败恢复只存在于录制结果条的“重试入库”，结果条 5 秒自动关闭后没有素材库或托盘中的持久待处理入口。
- 当前验证：故障存在时可重复触发失败并保留视频；故障恢复发生在结果条关闭后，无法通过 GUI 完成成功重试闭环。
- 后续建议：复用素材库，持久记录“视频已保存、索引待重试”的待处理项，并提供重试入口；不新增复杂恢复中心。
- 产品决策：v1.6 保留当前短时结果条重试能力；结果条超时后的持久恢复入口作为后续版本优化，本版不改动。

## BUG-V16-D7-004 无有效备份时目录重建无法提交

- 状态：已修复并通过 Bugfix2/3 打包产物定向复验。
- 严重度：发布阻塞。
- 复现：中央索引损坏且不存在有效 `.bak`，素材库提示加载失败；目录重建预览可识别有效视频，但确认后仍返回原 JSON 解析错误。
- 根因：`commit_scan()` 在用户确认后仍强制要求旧索引加载成功，导致不可读索引永远无法被已验证扫描结果替换。
- 修复：仅在用户已确认的目录重建提交中，保留损坏归档后使用已验证扫描结果原子替换不可读索引；正常索引仍执行合并和去重。
- 自动测试：新增无备份损坏索引重建失败测试；修复后目录扫描测试 8 passed，全量 340 passed。
- GUI 证据：`E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\evidence\50-no-backup-load-failure.jpg`、`54-bugfix2-rebuild-preview.jpg`、`55-no-backup-rebuild-one-item.jpg`。

## BUG-V16-D7-005 空素材状态残留上一条详情

- 状态：已修复并通过 Bugfix3 打包产物定向复验。
- 严重度：一般缺陷，不涉及索引或视频数据丢失。
- 复现：素材库只剩一条记录时执行“从素材库移除”，列表显示“暂无素材”，但右侧仍残留上一条素材的时间、画面和路径。
- 根因：无选中项分支只重置标题，没有清空详情字段。
- 修复：无选中项时统一把时间、时长、画面、模式、音频、大小、路径、诊断目录和来源重置为 `-`。
- GUI 证据：`E:\QRtest\QuickRec-v1.6-bugfix-acceptance\remaining\evidence\58-bugfix3-zero-state.jpg`。
- 回归要求：验证取消、重复路径、损坏文件和有效文件四条链路；失败前后中央索引哈希或目标记录字段应保持一致。
