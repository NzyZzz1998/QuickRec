# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'mss',
        'cv2',
        'keyboard',
        'pystray',
        'PIL',
        'six',
        'config',
        'utils',
        'utils.file_namer',
        'utils.disk_checker',
        'recorder',
        'recorder.screen_capturer',
        'recorder.video_encoder',
        'recorder.recorder_manager',
        'ui',
        'ui.area_selector',
        'ui.toolbar',
        'ui.settings_dialog',
        'ui.tray_icon',
        'hotkey',
        'hotkey.hotkey_manager',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['src/rthook_dllpath.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# === Anaconda-specific DLL collection ===
conda_bin = os.path.join(r'D:\Work\Software\Anaconda', 'Library', 'bin')

# Qt5 core DLLs (conda naming: Qt5##_conda.dll)
for dll in ['Qt5Core_conda.dll', 'Qt5Gui_conda.dll', 'Qt5Widgets_conda.dll',
            'Qt5Svg_conda.dll', 'Qt5Network_conda.dll']:
    path = os.path.join(conda_bin, dll)
    if os.path.exists(path):
        a.binaries.append((dll, path, 'BINARY'))

# Pillow / PIL dependency DLLs
#放到 _internal/ 根目录和 _internal/PIL/ 子目录（_imaging.pyd 只搜索自身目录）
pil_dlls = ['libpng16.dll', 'libjpeg.dll', 'zlib.dll', 'openjp2.dll',
            'lcms2.dll', 'tiff.dll', 'libwebp.dll', 'libwebpmux.dll',
            'libwebpdemux.dll', 'liblzma.dll', 'LIBBZ2.dll', 'libexpat.dll',
            'ffi.dll', 'zstd.dll']
for dll in pil_dlls:
    path = os.path.join(conda_bin, dll)
    if os.path.exists(path):
        a.binaries.append((dll, path, 'BINARY'))
        # 也放到 PIL/ 子目录，让 _imaging.pyd 能找到
        a.binaries.append((os.path.join('PIL', dll), path, 'BINARY'))

# Qt5 plugins
conda_plugins = os.path.join(r'D:\Work\Software\Anaconda', 'Library', 'plugins')
for plugin_type in ['platforms', 'styles', 'imageformats']:
    plugin_dir = os.path.join(conda_plugins, plugin_type)
    if os.path.isdir(plugin_dir):
        for f in os.listdir(plugin_dir):
            if f.endswith('.dll'):
                a.binaries.append((
                    os.path.join(plugin_type, f),
                    os.path.join(plugin_dir, f),
                    'BINARY'
                ))

# Collect PIL and pystray data files
from PyInstaller.utils.hooks import collect_data_files

for pkg in ['PIL', 'pystray']:
    for src_path, dest_prefix in collect_data_files(pkg):
        dest_name = os.path.join(dest_prefix, os.path.basename(src_path))
        a.datas.append((dest_name, src_path, 'DATA'))

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='QuickRec',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='QuickRec',
)