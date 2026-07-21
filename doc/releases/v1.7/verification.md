# QuickRec Full v1.7 自动验证记录

## 1. 当前结论

- 验证阶段：开发完成后的候选包自动验证。
- 当前结论：**自动验证与 D6 GUI 技术验收通过**。
- 发布状态：无技术发布阻塞，用户已授权进入正式发布收口。
- 验证日期：2026-07-21。
- 分支：`test`。
- 开发基线：`v1.6.1` / `cf5cec8e44b3a2b74a247cb94c0206ade7e8c13a`。

## 2. 自动化结果

| 检查 | 结果 | 证据摘要 |
| --- | --- | --- |
| 查询核心定向测试 | 通过 | 关键词、筛选、六项排序、时间、空值、稳定次序、分区与性能通过 |
| 会话与边界测试 | 通过 | 0/1/49/50/51/199/200 条、条件分页重置、异常保留与重开状态通过 |
| 素材库 UI 与主流程 | 通过 | 56 passed，18 subtests passed |
| 全量 pytest | 通过 | 401 passed，24 deselected，40 subtests passed |
| Packaging | 通过 | 12 passed，413 deselected |
| 新核心覆盖率 | 通过 | 查询与会话模块 89.80%，门槛 80% |
| 全项目覆盖率 | 通过 | 84.54%，门槛 80% |
| Ruff | 通过 | `All checks passed!` |
| Mypy | 通过 | 17 个源文件无问题 |
| Compileall | 通过 | `src`、`tests` 编译通过 |
| git diff --check | 通过 | 无空白错误；仅 Git 行尾转换提示 |

## 3. 候选包身份

当前候选目录：

`E:\QRtest\QuickRec-v1.7-candidate-fix1-dist\QuickRec`

构建命令：

```powershell
python -m PyInstaller build_std.spec --clean --noconfirm `
  --distpath E:\QRtest\QuickRec-v1.7-candidate-fix1-dist `
  --workpath E:\QRtest\QuickRec-v1.7-candidate-fix1-build
```

| 文件 | 大小 | SHA256 |
| --- | ---: | --- |
| `QuickRec.exe` | 6,900,431 字节 | `8966985B6E1EBCEDC27499404BF8467133EFCC9C6A827898D8904CE137E15AF2` |
| `_internal\ffmpeg\ffmpeg.exe` | 99,264,000 字节 | `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D` |
| `_internal\ffmpeg\ffprobe.exe` | 99,066,368 字节 | `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D` |

构建时间：2026-07-19 20:07:20。旧候选包因 BUG-V17-001 与 BUG-V17-002 修复而失效。

## 4. 候选包基础检查

- 包内 `ffmpeg.exe`、`ffprobe.exe` 均存在。
- 包内 FFprobe 版本为 `8.0.1-essentials_build-www.gyan.dev`。
- 包内 FFmpeg 已生成中文与空格路径的 1 秒受控 MP4。
- 包内 FFprobe 解析结果：320×240、30 FPS、时长 1.000 秒。
- 受控样本：`E:\QRtest\QuickRec-v1.7-candidate-evidence\v1.7 package 中文 sample.mp4`。
- 候选程序已在隔离 APPDATA 下启动并保持运行 5 秒，随后只停止该次启动进程。
- 隔离 APPDATA：`E:\QRtest\QuickRec-v1.7-candidate-evidence\appdata`。

## 5. GUI 验收状态

- 待入库与正式素材分区、待入库不分页已使用真实候选包和受控夹具完成。
- 查询异常保留上一次结果与索引加载失败已完成定向验证。
- 真实 Windows 100%/125%/150% DPI 均已完成，Qt 隔离缩放证据仅作补充。
- D6 技术验收已闭合；2026-07-21 已取得用户发布收口授权。

## 6. 2026-07-19 GUI 定向复验

- 受控索引 60 条，文件名和中文路径搜索、跨类别 AND、六项排序、加载更多、无结果和同进程条件恢复通过。
- `Ctrl+A` 文本编辑与区域录制全局快捷键冲突已修复；新候选包实测只选择搜索文本。
- 素材库打开时录制完成后的即时刷新已修复；计数从 61 自动更新到 62。
- 录制文件：`E:\QRtest\QuickRec-v1.7-acceptance\recordings\QuickRec_20260719_201127.mp4`。
- FFprobe：H.264、1920×1080、30 FPS、时长 16.966667 秒、无音频流。
- 缺陷详情见 [bugfix-log.md](bugfix-log.md)。

## 7. 2026-07-19 GUI 补充验收

- 容量边界：0、1、49、50、51、199、200 条均完成 GUI 验证；第 201 条入库后索引仍为 200 条，最旧测试视频文件未被删除。
- 会话：应用完全重启后恢复空关键词、全部筛选和最新优先；同进程重开继续保留查询条件。
- 隐私：对验收日志检索查询词、路径夹具和组合条件，未发现查询参数进入日志。
- 素材操作：仅移除索引后 UI 与 JSON 同步由 200 变为 199，原视频保持存在。
- 三类录制：全屏、区域、窗口均生成可解析 H.264 MP4，并以正确 `mode` 写入中央索引。
- 四类音频：无声无音轨；系统声、麦克风、双音频均生成 AAC 音轨并以正确 `audio_source` 入库。系统声受控信号平均 -31.3 dB；麦克风独立录制平均 -73.0 dB，并结合用户第一批人工补证判定通过。
- 窗口录制抽帧显示所选资源管理器窗口，不是全屏替代；目标窗口失效时程序安全取消且不生成错误文件。
- DPI：100%、125% 与 150% 均在真实 Windows 缩放下通过；125% 候选窗口 `GetDpiForWindow=120`，150% 候选窗口 `GetDpiForWindow=144`。主界面、长路径、重新定位对话框和移除确认框均无关键裁切或重叠，操作均取消且索引哈希保持不变。
- 150% 证据：`E:\QRtest\QuickRec-v1.7-acceptance\evidence\manual-final\V17-D3-150pct-material-library.jpg`、`V17-D3-150pct-material-details.jpg`、`V17-D3-150pct-relocate-dialog.jpg`、`V17-D3-150pct-remove-confirm.jpg`、`V17-D3-150pct-window-dpi.json`。
- 环境恢复：QuickRec 进程已全部停止；真实配置和索引哈希恢复为验收前值；QuickRec Lite 未修改。
- 待入库启动恢复：在独立 `APPDATA` 中构造的有效待入库记录启动后自动重试成功，由待入库转入正式索引；该结果不替代待入库分区 GUI 验收。

## 8. 2026-07-20 至 2026-07-21 GUI 收口验收

- D6.7：使用 55 条待入库与 8 条正式素材夹具完成独立分区、独立计数和待入库不分页验证；重新定位并重试后待入库减少 1 条，正式素材增加 1 条，无重复记录。
- D6.11：查询异常保留上次结果的定向测试为 `2 passed`；索引加载失败时候选包显示明确错误并禁用不安全的查询操作。
- D6.16 诊断：复制诊断信息、打开日志目录和导出诊断文件均通过；导出文件位于 `E:\QRtest\QuickRec-v1.7-acceptance\ops-final\diagnostics\diagnostic_20260720_001914.txt`。
- D6.16 素材操作：打开文件、打开目录、复制路径、重新定位、仅移除索引、目录重建统计及待入库重试均通过。
- 回收站定向复验：2026-07-21 在隔离 `APPDATA` 下选择受控素材并确认“删除视频文件”；GUI 由 1 条变为 0 条，原视频路径消失，另一受控视频保持存在，`recordings.json` 由 1 条变为 0 条。
- 回收站日志明确记录 `file moved to recycle bin` 与 `material recycled and index removed`；未清空回收站，未操作用户真实素材。
- 一次素材库不可见由验收启动命令误用隐藏窗口参数造成；正常可见方式重启后复验通过，不记为产品缺陷。
- 结论：D6.7、D6.11、D6.16 均通过；D6.18 用户正式发布收口授权已完成。
