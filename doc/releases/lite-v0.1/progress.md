# QuickRec Lite v0.1 总体进度

> 本文件只记录状态、最小任务和验收结论。开发过程、排障细节和 Bugfix 流水不得写入本文。

## 当前状态

- 版本：QuickRec Lite v0.1
- 当前阶段：正式发布收口
- 总体状态：RC2 候选包验收通过，正式发布已授权
- 开发分支：`lite-test`
- 稳定版本：`lite-v0.1`
- 进入开发授权：已获得
- Full 影响：禁止修改
- 最近验证：231 passed；总体 coverage 81.14%，核心模块 90%，协调模块 88%；Packaging 7 passed；Ruff/Mypy/Compileall 与硬件 smoke 通过
- 发布阻塞：无

## 里程碑总览

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| D0 | PRD、原型、计划与基线 | 已完成 |
| D1 | 独立身份与版本事实源 | 已完成 |
| D2 | 原子配置、迁移与快捷键事务 | 已完成 |
| D3 | 音频稳定性白名单回迁 | 已完成 |
| D4 | 捕获、停止、帧调度与磁盘估算 | 已完成 |
| D5 | 不可达代码分阶段删除 | 已完成 |
| D6 | 依赖、CI、manifest 与打包 | 已完成 |
| D7 | 自动化与候选包验证 | 已完成 |
| D8 | GUI/硬件验收与文档收口 | 已完成 |

## D0 PRD、原型与基线

- [x] D0.1 读取 Lite v0 当前事实源和 v0.1 需求池。
- [x] D0.2 固化 v0.1 正式 PRD。
- [x] D0.3 输出迁移、设置、重复实例和主界面高保真原型。
- [x] D0.4 验证桌面视口无横向溢出。
- [x] D0.5 验证窄视口无横向溢出。
- [x] D0.6 验证关键交互和控制台错误。
- [x] D0.7 输出 dev plan。
- [x] D0.8 输出 progress 最小任务清单。
- [x] D0.9 记录基线自动化结果。
- [x] D0.10 确认 QuickRec Full 不属于修改范围。

## D1 独立身份与版本事实源

- [x] D1.1 为产品身份常量补失败测试。
- [x] D1.2 新增 `src/version.py`，定义 `APP_VERSION = "v0.1"`。
- [x] D1.3 新增 Lite 产品 ID、显示名、目录和注册表常量。
- [x] D1.4 配置路径切换到 `%APPDATA%\QuickRec-Lite`。
- [x] D1.5 临时目录切换到 `%TEMP%\QuickRec-Lite`。
- [x] D1.6 默认输出切换到 `Videos\QuickRec Lite`。
- [x] D1.7 开机启动项改为 `QuickRec Lite`。
- [x] D1.8 托盘、通知、窗口标题和 App ID 使用 Lite 身份。
- [x] D1.9 接入 `QuickRec.Lite` 单实例保护。
- [x] D1.10 第二 Lite 实例提示并退出。
- [x] D1.11 验证 Full/Lite 产品 ID 不冲突。
- [x] D1.12 PyInstaller EXE 与目录改为 `QuickRec-Lite`。
- [x] D1.13 运行 D1 受影响测试（26 passed，5 deselected）。

## D2 原子配置、迁移与快捷键事务

- [x] D2.1 为原子保存成功与各失败阶段补测试。
- [x] D2.2 实现结构化 `ConfigSaveResult`。
- [x] D2.3 实现同目录临时文件、flush、fsync、replace。
- [x] D2.4 保存失败保持旧文件与内存配置。
- [x] D2.5 正式配置移除区域/窗口/倒计时/高亮字段。
- [x] D2.6 实现迁移触发条件。
- [x] D2.7 只迁移 `save_path` 和 `audio_source`。
- [x] D2.8 无效字段独立回退并形成反馈。
- [x] D2.9 实现导入、默认、关闭取消三条路径。
- [x] D2.10 迁移写入失败可重试且零副作用。
- [x] D2.11 新配置存在时迁移幂等跳过。
- [x] D2.12 实现迁移 PyQt 对话框。
- [x] D2.13 设置页使用候选配置事务。
- [x] D2.14 配置失败时回滚开机启动项。
- [x] D2.15 默认快捷键更新为 Ctrl+Alt+R/S/P。
- [x] D2.16 快捷键冲突保留原有效绑定。
- [x] D2.17 运行 D2 受影响测试（28 passed）。

## D3 音频稳定性

- [x] D3.1 为默认设备 ID 匹配补失败测试。
- [x] D3.2 实现设备 ID 优先、名称受控回退。
- [x] D3.3 为双音频命令补失败测试。
- [x] D3.4 将 `amerge` 替换为立体声 `amix`。
- [x] D3.5 对齐系统声与麦克风共同起点。
- [x] D3.6 记录音频初始化和混合语义日志。
- [x] D3.7 自动化验证四种模式合同（58 passed）。
- [x] D3.8 候选包真实四音频通过。

## D4 捕获与帧交付

- [x] D4.1 为目标帧调度补失败测试。
- [x] D4.2 新增纯函数帧调度模块。
- [x] D4.3 捕获循环移除追帧后的额外提交。
- [x] D4.4 实现静态桌面最后有效帧回退。
- [x] D4.5 实现非阻塞停止请求和有限等待。
- [x] D4.6 验证相机、线程和编码管道释放。
- [x] D4.7 磁盘估算感知 FPS。
- [x] D4.8 运行 D4 受影响测试（85 passed，8 deselected）。

## D5 不可达代码治理

- [x] D5.1 建立区域/窗口能力不可达测试。
- [x] D5.2 删除 main/tray/hotkey 专属桥接。
- [x] D5.3 删除区域/窗口/倒计时/点击高亮专属 UI 引用。
- [x] D5.4 从 spec 移除专属 hidden imports。
- [x] D5.5 使用 `rg` 确认无运行时引用。
- [x] D5.6 删除专属模块和过期测试。
- [x] D5.7 删除不再使用的配置键。
- [x] D5.8 运行全量测试和 packaging 静态检查（215 passed，8 deselected，12 subtests passed）。

## D6 发布工程

- [x] D6.1 精确锁定运行依赖。
- [x] D6.2 精确锁定开发门禁工具。
- [x] D6.3 CI 使用固定 FFmpeg 来源与哈希。
- [x] D6.4 packaging smoke 检查 Lite EXE 名称。
- [x] D6.5 packaging smoke 检查 FFmpeg 版本、哈希和可执行性。
- [x] D6.6 新增 release manifest 生成脚本。
- [x] D6.7 manifest 包含版本、commit、环境、依赖和哈希。
- [x] D6.8 扩大 Ruff/Mypy/coverage 到受影响模块。
- [x] D6.9 保持总体 coverage 不低于 80%（81.14%）。
- [x] D6.10 记录包体积，不设 200 MB 阻断（257.88 MB）。

## D7 自动化与候选包

- [x] D7.1 全量 pytest 通过（231 passed，11 deselected）。
- [x] D7.2 总 coverage 不低于 80%（81.14%）。
- [x] D7.3 新增核心模块 coverage 不低于 85%（90%）。
- [x] D7.4 受影响协调/UI coverage 不低于 80%（88%）。
- [x] D7.5 Ruff 通过。
- [x] D7.6 Mypy 通过（18 个源文件）。
- [x] D7.7 Compileall 通过。
- [x] D7.8 `git diff --check` 通过。
- [x] D7.9 UTF-8 与乱码检查通过。
- [x] D7.10 Packaging tests 通过（7 passed，235 deselected）。
- [x] D7.11 生成独立 v0.1 RC2 候选包。
- [x] D7.12 锁定 EXE、FFmpeg、ZIP 和 manifest 哈希。
- [x] D7.13 包内无专属区域/窗口 UI 模块。
- [x] D7.14 Full 工作区保持未修改。

## D8 GUI/硬件验收与文档收口

- [x] D8.1 Full 与 Lite 同时启动。
- [x] D8.2 第二 Lite 实例提示并退出。
- [x] D8.3 迁移导入成功且旧文件哈希不变。
- [x] D8.4 使用默认设置成功且旧文件不变。
- [x] D8.5 关闭迁移对话框零写入并取消启动。
- [x] D8.6 损坏旧配置和新配置写入失败反馈正确。
- [x] D8.7 设置保存失败保持窗口并回滚。
- [x] D8.8 快捷键冲突保留原绑定。
- [x] D8.9 全屏无声录制通过。
- [x] D8.10 全屏系统声录制通过。
- [x] D8.11 全屏麦克风录制通过。
- [x] D8.12 全屏双音频录制通过。
- [x] D8.13 静态桌面录制通过。
- [x] D8.14 快速停止通过。
- [x] D8.15 连续五次录制通过。
- [x] D8.16 托盘、通知、结果条和版本身份正确。
- [x] D8.17 更新 manual verification 与 verification。
- [x] D8.18 更新 README、current、release notes 和 package report。
- [x] D8.19 所有发布阻塞项关闭。
- [x] D8.20 获得正式发布授权，进入提交、分支、tag 与 Release 收口。

## 当前下一步

完成提交、同步 `lite-test` / `lite-master`、创建 `lite-v0.1` tag 和 GitHub Release，并复核远端发布身份。
