# -*- mode: python -*-
block_cipher = None

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_all

proj_path = '.'

collected = []
collected_binaries = []
collected_hiddenimports = []
for package in ("faster_whisper", "chromadb", "sentence_transformers"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    collected.extend(pkg_datas)
    collected_binaries.extend(pkg_binaries)
    collected_hiddenimports.extend(pkg_hiddenimports)

datas = [
    ("config.json", "."),
    (".env.example", "."),
    ("tray_icon.ico", "."),
    ("models/rudra.onnx", "models"),
]

a = Analysis(
    ["main.py"],
    pathex=[proj_path],
    binaries=collected_binaries,
    datas=datas + collected,
    hiddenimports=collected_hiddenimports,
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
