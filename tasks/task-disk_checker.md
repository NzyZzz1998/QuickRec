# 任务：磁盘空间检查模块 (disk_checker.py)

**模块**：`src/utils/disk_checker.py`
**说明**：检查目标磁盘是否有足够空间继续录制。

## 前置依赖
- [x] Python 3.12.8 (Anaconda 已安装)
- [x] numpy 1.26.4 (Anaconda 已安装)

## 子任务

### 1. 实现 DiskChecker 类
- [ ] 定义 `DiskChecker` 类
- [ ] 实现 `get_free_space(path)` 方法
- [ ] 实现 `estimate_size_per_minute(res, fps)` 方法
- [ ] 实现 `is_low_space(path, threshold_mb)` 方法

### 2. 空间估算逻辑
- [ ] 高画质(8000kbps) ≈ 60MB/分钟
- [ ] 中画质(4000kbps) ≈ 30MB/分钟
- [ ] 低画质(2000kbps) ≈ 15MB/分钟

### 3. 单元测试
- [ ] 测试返回的可用空间正确
- [ ] 测试估算大小误差在 ±20% 内
- [ ] 测试低空间判断正确

## 验收标准
- [ ] 能正确返回磁盘空间
- [ ] 估算值合理
- [ ] 所有单元测试通过
