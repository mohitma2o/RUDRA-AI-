# -*- mode: python -*-
block_cipher = None

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

proj_path = '.'

a = Analysis(
    ["main.py"],
    pathex=[proj_path],
    binaries=[],
    datas=[
        ("config.json", "."),
        (".env.example", "."),
        ("tray_icon.ico", "."),
        ("models/rudra_openwakeword.bin", "models"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Rudra",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="tray_icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="Rudra",
)
