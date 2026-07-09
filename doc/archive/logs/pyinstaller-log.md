# QuickRec PyInstaller 打包问题排查日志

> 创建时间: 2026-06-12
> 最后更新: 2026-06-11

## 问题现象

QuickRec.exe 双击运行后弹窗报错：**"Failed to execute script 'main'"**

## 根本原因

**Anaconda 环境下 PyInstaller 打包的 DLL 路径问题**。Anaconda 将 Qt5 和 Pillow 的依赖 DLL 放在 `Library/bin/` 目录下（并使用 `_conda.dll` 命名约定），而 PyInstaller 的标准 hooks 找不到这些 DLL，导致打包后运行时 DLL 加载失败。

## 最终解决方案

**使用标准 CPython 替代 Anaconda 进行打包。** 在 `D:\Work\Software\Python` 安装标准 Python 3.12.8，在其中安装依赖后打包，彻底解决 Anaconda DLL 命名和路径不兼容问题。

## 排查过程

### 第1轮：添加 hidden imports + 开启 console

**修改**：
- `console=False` → `console=True`
- 添加所有项目模块到 hiddenimports (config, utils.*, recorder.*, ui.*, hotkey.*)
- 额外添加 `six`

**结果**：打包成功，运行报错：
```
ImportError: DLL load failed while importing QtWidgets: 找不到指定的模块。
```
**分析**：Anaconda 的 PyQt5 Qt5 DLL 不在 PyQt5 包目录内，而在 `Library/bin/` 下。

---

### 第2轮：手动添加 Qt5 DLL 和 plugins

**修改**：在 build.spec 中手动收集 Qt5 DLL 和 plugins

**结果**：QtWidgets 错误解决，但新错误：
```
ImportError: DLL load failed while importing _imaging: 找不到指定的模块。
```
**分析**：Pillow 的 `_imaging.pyd` 也依赖 Anaconda DLL。

---

### 第3轮：使用 collect_all

**修改**：用 `collect_all()` 自动收集 PyQt5/PIL/mss/pystray 所有文件

**结果**：打包失败，`ValueError: not enough values to unpack (expected 3, got 2)`
**分析**：`collect_all()` 返回 2-tuple，PyInstaller EXE 需要 3-tuple。

---

### 第4轮：手动添加 DLL + collect_data_files

**修改**：手动添加 DLL（3-tuple），`collect_data_files()` 收集数据

**结果**：打包失败，同样的 2-tuple/3-tuple 不兼容。
**分析**：`collect_data_files()` 返回 `(source, dest_prefix)` 2-tuple。

---

### 第5轮：改用 onedir 模式 + runtime hook + main.py 添加 DLL 路径

**修改**：
1. 从 onefile 改为 onedir (COLLECT) 模式
2. 手动添加所有 Anaconda DLL（Qt5、Pillow 依赖）
3. 正确转换 `collect_data_files()` 的 2-tuple 为 3-tuple
4. 添加 `rthook_dllpath.py` runtime hook 设置 DLL 搜索路径
5. 在 `main.py` 最顶部用 `os.add_dll_directory()` 添加 `_internal` 目录

**结果**：打包成功，但运行仍然报错：
```
ImportError: DLL load failed while importing _imaging: 找不到指定的模块。
```
**分析**：`os.add_dll_directory()` 和 PATH 设置都没有在模块导入前生效。

---

### 第6轮：PIL DLL 放到 PIL 子目录 + runtime hook 增加 PIL 目录

**修改**：
1. `build.spec` 中为每个 PIL 依赖 DLL 添加两份拷贝：`_internal/` 和 `_internal/PIL/`
2. `rthook_dllpath.py` 增加 `_internal/PIL/` 目录到搜索路径

**结果**：仍然失败，同样的 `_imaging` 错误。

**分析**：Windows 上 `.pyd` 通过 PyInstaller 的 `pyimod02_importers` 加载时，DLL 搜索机制与标准 Python 不同，即使 DLL 在同目录也不行。

---

### 第7轮：延迟导入 PIL + ctypes 预加载

**修改**：
1. `tray_icon.py` 中 `from PIL import Image, ImageDraw` 改为方法内按需导入
2. 在导入前用 `ctypes.CDLL()` 预加载所有 PIL 依赖 DLL

**结果**：程序启动通过了模块导入关卡，但在 `show()` 调用 `_create_icon_image()` 时仍然报 `DLL load failed while importing _imaging`。

**分析**：ctypes 预加载 DLL 对 PyInstaller 的模块加载机制同样无效。

---

### 第8轮（最终方案）：改用标准 CPython 打包

**核心诊断**：在标准 Python 环境下，用 `os.add_dll_directory()` + PATH 就能成功导入 PIL，但在 PyInstaller 打包环境中无效。问题根源在 Anaconda 的 DLL 布局与 PyInstaller 不兼容。

**修改**：
1. 安装标准 CPython 3.12.8 到 `D:\Work\Software\Python`
2. 在标准 Python 中安装所有依赖（PyQt5, mss, opencv-python, keyboard, pystray, pyinstaller）
3. 使用新的 `build_std.spec`（移除所有 Anaconda DLL hack，无 runtime hook，无手动 DLL 收集）
4. 还原 `main.py`（移除 DLL 路径 hack）和 `tray_icon.py`（恢复模块级 PIL 导入）

**结果**：✅ 打包成功，QuickRec.exe 正常启动并运行！

**关键发现**：标准 Python 的 Pillow 包（pip 安装）自包含所有依赖 DLL，不需要像 Anaconda 那样从 `Library/bin/` 外部加载。PyInstaller 的标准 hooks 对标准 Python 包工作正常。

---

## 当前状态

### ✅ 已解决
- 问题根因：Anaconda 环境与 PyInstaller 不兼容
- 解决方案：使用标准 CPython 3.12.8 打包
- QuickRec.exe 可正常启动运行

### 涉及的文件
- `build_std.spec` — 新的 PyInstaller 打包配置（干净，无 Anaconda hack）
- `build.spec` — 旧的 Anaconda 打包配置（保留参考，不再使用）
- `src/main.py` — 已还原（移除 DLL 路径 hack）
- `src/ui/tray_icon.py` — 已还原（恢复模块级 PIL 导入）
- `src/rthook_dllpath.py` — 不再需要（保留参考）
- `doc/pyinstaller-log.md` — 本日志文件

## 打包命令

```bash
# 使用标准 Python 的 PyInstaller
cd E:\CC_Learning\QuickRec_dev
D:\Work\Software\Python\Scripts\pyinstaller.exe build_std.spec --noconfirm
```

## 后续事项
- [ ] 将 `console=True` 改为 `console=False`（确认功能正常后）
- [ ] 考虑从 onedir 切换回 onefile 模式
- [ ] 清理不再需要的 `build.spec`、`rthook_dllpath.py`
- [ ] 更新 `requirements.txt`