# 任务：文件命名模块 (file_namer.py)

**模块**：`src/utils/file_namer.py`
**说明**：生成录制文件的文件名。

## 前置依赖
- [x] Python 3.12.8 (Anaconda 已安装)

## 子任务

### 1. 实现 FileNamer 类
- [x] 定义 `FileNamer` 类
- [x] 实现 `generate(save_dir, prefix)` 方法

### 2. 命名规则
- [x] 基础格式：`QuickRec_YYYYMMDD_HHmmss.mp4`
- [x] 冲突检测：同一秒多次录制时自动追加序号
- [x] 冲突格式：`QuickRec_YYYYMMDD_HHmmss_001.mp4`

### 3. 目录处理
- [x] 目标目录不存在时自动创建

### 4. 单元测试
- [x] 测试文件名格式正确
- [x] 测试同一秒内重复录制的序号递增
- [x] 测试目录不存在时自动创建

## 验收标准
- [x] 生成的文件名符合格式
- [x] 同一秒内不冲突
- [x] 所有单元测试通过 (5/5)
