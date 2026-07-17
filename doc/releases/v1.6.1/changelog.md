# QuickRec Full v1.6.1 变更日志

> 状态：正式发布（2026-07-18）
> 基线：QuickRec Full v1.6
> 回滚点：`v1.6` tag（`ac8d151aababb5e7c37b3dcc646ae10c8593acf3`）

## 新增

- 新增待入库持久化：视频保存成功但中央素材索引写入失败时，保留可恢复上下文。
- 新增启动单次自动重试与成功恢复汇总提示。
- 素材库新增待入库置顶区域、独立计数、失败详情、手动重试、重新定位和仅移除待处理记录。
- 新增 APPDATA 主待入库文件不可写时的视频目录降级标记。
- 待入库容量独立限制为 200 条；淘汰最旧恢复元数据时不删除实际视频。

## 修复

- 修复 8 声道系统回环与单声道麦克风经 `amerge` 形成 9 声道布局、导致 AAC 混音失败的问题。
- 双音源改为分别归一化为 48 kHz 立体声后使用 `amix` 混合。
- 修复回环设备仅按通用名称前缀匹配时可能选错设备的问题，优先按默认扬声器设备 ID 和完整名称匹配。

## 工程与兼容性

- 新增待入库存储、服务、协调器与素材库 UI 测试。
- 新模块纳入 PyInstaller、packaging、ruff、mypy 和 coverage 门禁。
- 保持 v1.6 正式中央索引 schema 兼容；回滚到 v1.6 不删除待入库主文件、降级标记或视频文件。
- QuickRec Lite 未纳入本次变更。

## 验证

- 修复后全量测试：376 passed、24 deselected、22 subtests passed。
- Packaging：12 passed；ruff、mypy、compileall、UTF-8/乱码检查和 `git diff --check` 通过。
- 锁定候选包 GUI 手动验收通过；EXE SHA256：`2CB447709769A8A986B7A48A63C98377803A002ED56892E57F0911661FA3E092`。
- 发布资产 `QuickRec-v1.6.1-win-x64.zip` SHA256：`CE72D690DD46950C46CDEE2F3999B6F64E6DC0362B20CAC21FC53A34FCE197CF`。
