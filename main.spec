# -*- mode: python ; coding: utf-8 -*-
# 文件夹打包（启动快、兼容性好）：
#   uv run pyinstaller main.spec --noconfirm
#   → dist/mstsc-manager/mstsc-manager.exe（依赖放在 dist/mstsc-manager/mstsc-manager-lib/）

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/icon.ico', 'assets'), ('assets/icon.png', 'assets')],
    hiddenimports=['mstsc_manager'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 本项目只用 QtWidgets/QtGui/QtCore，其余 Qt 模块全部排除，体积从 ~400MB 降到 ~80MB
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineQuick', 'PySide6.QtWebChannel',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQuickControls2',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
        'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.Qt3DCore', 'PySide6.Qt3DRender',
        'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras',
        'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtPositioning', 'PySide6.QtSensors', 'PySide6.QtLocation',
        'PySide6.QtSerialPort', 'PySide6.QtSerialBus', 'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtXml',
        'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtUiTools', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
        'PySide6.QtNetworkAuth', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml', 'PySide6.QtStateMachine',
        'PySide6.QtSvg', 'PySide6.QtSvgWidgets', 'PySide6.QtTextToSpeech', 'PySide6.QtSpatialAudio',
        'PySide6.QtHttpServer', 'PySide6.QtWebSockets', 'PySide6.QtWebView', 'PySide6.QtGraphs', 'PySide6.QtGraphsWidgets',
        'PySide6.QtConcurrent', 'PySide6.QtPrintSupport', 'PySide6.QtDBus', 'PySide6.QtAsyncio',
        'tkinter', 'matplotlib', 'IPython', 'pytest', 'numpy',
    ],
    noarchive=False,
    optimize=0,
)

# PySide6 的 hook 会把一批本项目用不到的 Qt 运行库/插件一起带进来（Quick/Qml/Pdf/软件 OpenGL/各种图片格式等），
# 这里按路径前缀过滤掉。只保留 Widgets 程序必需的：Qt6Core/Gui/Widgets、qwindows 平台插件、qico 图标解码、样式。
_DROP_PREFIXES = (
    'PySide6/Qt6Quick', 'PySide6/Qt6Qml', 'PySide6/Qt6Pdf', 'PySide6/Qt6OpenGL', 'PySide6/Qt6Svg',
    'PySide6/Qt6Network', 'PySide6/QtNetwork', 'PySide6/Qt6VirtualKeyboard', 'PySide6/opengl32sw',
    'PySide6/translations/',
    'PySide6/plugins/platforms/qdirect2d', 'PySide6/plugins/platforms/qminimal', 'PySide6/plugins/platforms/qoffscreen',
    'PySide6/plugins/imageformats/qgif', 'PySide6/plugins/imageformats/qicns', 'PySide6/plugins/imageformats/qjpeg',
    'PySide6/plugins/imageformats/qpdf', 'PySide6/plugins/imageformats/qsvg', 'PySide6/plugins/imageformats/qtga',
    'PySide6/plugins/imageformats/qtiff', 'PySide6/plugins/imageformats/qwbmp', 'PySide6/plugins/imageformats/qwebp',
    'PySide6/plugins/iconengines/', 'PySide6/plugins/generic/', 'PySide6/plugins/networkinformation/',
    'PySide6/plugins/platforminputcontexts/', 'PySide6/plugins/tls/',
)


def _keep(entry):
    name = entry[0].replace('\\', '/')
    return not name.startswith(_DROP_PREFIXES)


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='mstsc-manager',
    icon='assets/icon.ico',
    contents_directory='mstsc-manager-lib',   # 依赖目录名（PyInstaller 6 默认 _internal）
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                  # Qt DLL 压缩后易出问题
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='mstsc-manager',
    strip=False,
    upx=False,
    upx_exclude=[],
)
