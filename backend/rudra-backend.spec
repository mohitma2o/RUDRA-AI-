# PyInstaller one-folder build for the local FastAPI backend.
from importlib.util import find_spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parent
datas = [(str(root / "rudra" / "config.json"), "rudra")]
binaries = []
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "edge_tts",
    "pyttsx3.drivers.sapi5",
]

for package in ("faster_whisper", "ctranslate2", "multipart"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

if find_spec("onnxruntime") is not None:
    package_datas, package_binaries, package_hiddenimports = collect_all("onnxruntime")
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

whisper_model = root / "backend" / "models" / "whisper-base"
if whisper_model.is_dir():
    datas.append((str(whisper_model), "backend/models/whisper-base"))

a = Analysis(
    [str(root / "backend" / "run.py")],
    pathex=[str(root / "backend"), str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "chromadb", "sentence_transformers", "easyocr", "cv2"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="rudra-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="rudra-backend",
)
