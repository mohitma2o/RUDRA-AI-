# -*- mode: python -*-
block_cipher = None

import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_all

proj_path = '.'

# ── Collect data/binaries/hiddenimports for complex packages ────────
collected = []
collected_binaries = []
collected_hiddenimports = []
for package in (
    "faster_whisper",
    "chromadb",
    "sentence_transformers",
    "openwakeword",
    "onnxruntime",
):
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
        collected.extend(pkg_datas)
        collected_binaries.extend(pkg_binaries)
        collected_hiddenimports.extend(pkg_hiddenimports)
    except Exception as exc:
        print(f"Warning: collect_all('{package}') failed: {exc}")

# ── Project data files ──────────────────────────────────────────────
datas = [
    ("config.json", "."),
    ("tray_icon.ico", "."),
    ("models/rudra.onnx", "models"),
]
# Include .env.example only if it exists (not required at runtime)
if os.path.exists(".env.example"):
    datas.append((".env.example", "."))

# ── Hidden imports PyInstaller commonly misses ──────────────────────
extra_hiddenimports = [
    "edge_tts",
    "pystray",
    "PIL",
    "PIL._tkinter_finder",
    "speech_recognition",
    "pyaudio",
    "psutil",
    "dotenv",
    "ollama",
    "numpy",
    "ctypes",
    "winsound",
    "asyncio",
    # Rudra's own modules (relative imports from main.py)
    "agent",
    "llm",
    "stt",
    "tts",
    "wakeword",
    "memory",
    "memory.scriptures",
    "skills",
    "skills.browser",
    "skills.files",
    "skills.system",
    "skills.vision",
]

a = Analysis(
    ["main.py"],
    pathex=[proj_path],
    binaries=collected_binaries,
    datas=datas + collected,
    hiddenimports=collected_hiddenimports + extra_hiddenimports,
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
    # Set to True during development to see errors; flip to False for release
    console=True,
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
