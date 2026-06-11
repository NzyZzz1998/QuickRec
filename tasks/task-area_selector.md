# 任务：区域选择模块 (area_selector.py)

**模块**：`src/ui/area_selector.py`
**说明**：全屏遮罩 + 矩形区域选择。

## 前置依赖
- [x] PyQt5 5.15.10 (Anaconda 已安装)

## 子任务

### 1. 实现 AreaSelector 类 (QWidget)
- [x] 继承 QWidget
- [x] 全屏半透明遮罩 (黑色，透明度 50%)
- [x] 透明区域为选中录制区域
- [x] 支持鼠标拖拽选择

### 2. 交互逻辑
- [x] 鼠标按下：记录起点
- [x] 鼠标拖拽：实时绘制矩形，显示尺寸标签
- [x] 鼠标松开：发送 region_selected 信号
- [x] ESC 键：发送 cancelled 信号

### 3. 显示信息
- [x] 矩形边框高亮
- [x] 尺寸标签实时更新 (如 "1280 x 720")
- [x] 最小区域限制 (100x100)

### 4. 信号定义
- [x] `region_selected(x, y, w, h)`
- [x] `cancelled()`

## 验收标准
- [x] 全屏遮罩正常显示
- [x] 拖拽绘制矩形正确
- [x] 尺寸标签实时更新
- [x] ESC 取消正常