# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('ffmpeg/ffmpeg.exe', 'ffmpeg'),
    ],
    hiddenimports=[
        'dxcam',
        'comtypes',
        'comtypes.client',
        'comtypes.server',
        'cv2',
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._win32',
        'pynput.mouse',
        'pynput.mouse._win32',
        'pystray',
        'PIL',
        'six',
        'config',
        'utils',
        'utils.file_namer',
        'utils.disk_checker',
        'utils.autostart',
        'recorder',
        'recorder.screen_capturer',
        'recorder.video_encoder',
        'recorder.recorder_manager',
        'recorder.audio_capturer',
        'ui',
        'ui.area_selector',
        'ui.toolbar',
        'ui.settings_dialog',
        'ui.tray_icon',
        'ui.window_selector',
        'ui.window_highlighter',
        'ui.click_highlighter',
        'hotkey',
        'hotkey.hotkey_manager',
        'winotify',
        'soundcard',
        'soundcard.mediafoundation',
        'pyaudio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Qt modules not used by QuickRec
        'PyQt5.QtBluetooth',
        'PyQt5.QtDesigner',
        'PyQt5.QtHelp',
        'PyQt5.QtLocation',
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtNetwork',
        'PyQt5.QtNetworkAuth',
        'PyQt5.QtNfc',
        'PyQt5.QtOpenGL',
        'PyQt5.QtQml',
        'PyQt5.QtQuick',
        'PyQt5.QtQuickWidgets',
        'PyQt5.QtRemoteObjects',
        'PyQt5.QtSensors',
        'PyQt5.QtSerialPort',
        'PyQt5.QtSql',
        'PyQt5.QtSvg',
        'PyQt5.QtTest',
        'PyQt5.QtWebChannel',
        'PyQt5.QtWebEngine',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebSockets',
        'PyQt5.QtXml',
        'PyQt5.QtXmlPatterns',
        # Standard library modules not needed
        'tkinter',
        'unittest',
        'test',
        'tests',
        'lib2to3',
        'xmlrpc',
        'pydoc',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# 从 Analysis 结果中移除不需要的 Qt DLL 和 ANGLE 软件渲染库
_QT_EXCLUDE_DLLS = {
    'Qt5Quick', 'Qt5Qml', 'Qt5QmlModels', 'Qt5Network', 'Qt5DBus',
    'Qt5Svg', 'Qt5WebSockets', 'Qt5OpenGL', 'Qt5Multimedia',
    'Qt5MultimediaWidgets', 'Qt5Bluetooth', 'Qt5Designer', 'Qt5Help',
    'Qt5Location', 'Qt5Nfc', 'Qt5Sensors', 'Qt5SerialPort', 'Qt5Sql',
    'Qt5Test', 'Qt5WebChannel', 'Qt5WebEngine', 'Qt5WebEngineCore',
    'Qt5WebEngineWidgets', 'Qt5Xml', 'Qt5XmlPatterns', 'Qt5RemoteObjects',
}
_ANGLE_DLLS = {
    'opengl32sw', 'd3dcompiler_47', 'libGLESv2', 'libEGL',
}
# OpenCV 自带的 ffmpeg DLL（与我们的 ffmpeg.exe 重复）
_CV2_EXCLUDE = {
    'opencv_videoio_ffmpeg',
}
# PIL 不需要的编解码器（pystray 只用 Image/ImageDraw，不需要 AVIF/WebP）
_PIL_EXCLUDE = {
    '_avif.', '_webp.', '_imagingtk.',
}
# Qt 插件排除（不需要的图片格式和平台插件）
_QT_PLUGIN_EXCLUDE = {
    'qsvg', 'qwebp', 'qtiff', 'qicns', 'qico', 'qtga', 'qwbmp',
    'qwebgl', 'qminimal',
}

def _should_exclude(name):
    """判断二进制/数据文件是否应排除"""
    bn = name.lower()
    # Qt 排除的 DLL
    for qt in _QT_EXCLUDE_DLLS:
        if qt.lower() in bn:
            return True
    # ANGLE 软件渲染
    for ang in _ANGLE_DLLS:
        if ang.lower() in bn:
            return True
    # OpenCV ffmpeg DLL
    for cv in _CV2_EXCLUDE:
        if cv.lower() in bn:
            return True
    # PIL 不需要的编解码器
    for pil in _PIL_EXCLUDE:
        if pil.lower() in bn:
            return True
    # Qt 不需要的插件
    for qt_plug in _QT_PLUGIN_EXCLUDE:
        if qt_plug.lower() in bn:
            return True
    return False

a.binaries = [b for b in a.binaries if not _should_exclude(b[0])]
a.datas = [d for d in a.datas if not _should_exclude(d[0])]

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