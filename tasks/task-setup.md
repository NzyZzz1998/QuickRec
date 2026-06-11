# 任务：项目初始化和依赖安装

**说明**：创建项目目录结构，安装缺失的 Python 包。

## 前置依赖
- [x] Anaconda 已安装 (Python 3.12.8)
- [x] PyQt5 5.15.10 (已安装)
- [x] numpy 1.26.4 (已安装)

## 缺失依赖 (需安装)

### 1. 安装 mss
- [x] 命令：`pip install mss`
- [x] 验证：`python -c "import mss; print(mss.__version__)"` → 10.2.0

### 2. 安装 opencv-python
- [x] 命令：`pip install opencv-python`
- [x] 验证：`python -c "import cv2; print(cv2.__version__)"` → 4.13.0

### 3. 安装 keyboard
- [x] 命令：`pip install keyboard`
- [x] 验证：`python -c "import keyboard; print('ok')"` → ok

### 4. 安装 pystray
- [x] 命令：`pip install pystray`
- [x] 验证：`python -c "import pystray; print('ok')"` → ok

### 5. 安装 pyinstaller
- [x] 命令：`pip install pyinstaller`
- [x] 验证：`pyinstaller --version` → 6.20.0

### 6. 生成 requirements.txt
- [x] 运行：`pip freeze > requirements.txt`
- [x] 检查：确认包含所有依赖

## 项目目录创建
- [x] `QuickRec_dev/src/recorder/`
- [x] `QuickRec_dev/src/ui/`
- [x] `QuickRec_dev/src/utils/`
- [x] `QuickRec_dev/src/hotkey/`
- [x] `QuickRec_dev/tests/`

## 验收标准
- [x] 所有缺失包安装成功
- [x] `requirements.txt` 生成
- [x] 项目目录创建完成
