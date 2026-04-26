# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for BACnet Explorer standalone desktop app.

Build:
    pyinstaller bacnet_explorer.spec

Output:  dist/BACnet Explorer/BACnet Explorer.exe   (directory bundle)
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["bacnet_explorer/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the static web UI
        ("bacnet_explorer/static", "bacnet_explorer/static"),
    ],
    hiddenimports=[
        # bacpypes3 uses importlib-based plugin loading — include all sub-packages
        "bacpypes3",
        "bacpypes3.apdu",
        "bacpypes3.app",
        "bacpypes3.appservice",
        "bacpypes3.basetypes",
        "bacpypes3.comm",
        "bacpypes3.constructeddata",
        "bacpypes3.debugging",
        "bacpypes3.errors",
        "bacpypes3.ipv4",
        "bacpypes3.ipv4.service",
        "bacpypes3.local",
        "bacpypes3.local.device",
        "bacpypes3.local.object",
        "bacpypes3.netservice",
        "bacpypes3.object",
        "bacpypes3.pdu",
        "bacpypes3.primitivedata",
        "bacpypes3.service",
        "bacpypes3.service.cov",
        "bacpypes3.service.device",
        "bacpypes3.service.object",
        "bacpypes3.vendor",
        # ifaddr for interface enumeration
        "ifaddr",
        # colorama for Windows ANSI colour support
        "colorama",
        "colorama.initialise",
        # pywebview backends (Windows uses EdgeWebView2 via clr/pythonnet)
        "webview",
        "webview.platforms",
        "webview.platforms.winforms",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,      # directory mode (faster startup, easier to update)
    name="BACnet Explorer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,              # no black console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="bacnet_explorer/static/icon.ico",   # uncomment when you add an icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BACnet Explorer",
)
