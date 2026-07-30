# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for DubVIEngine.exe (Tauri sidecar).

Build (from engine/):
  pip install -r requirements-base.txt pyinstaller
  pyinstaller DubVIEngine.spec

Bundle FFmpeg separately into resources/bin for the Tauri installer —
do not rely on system PATH in production.
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

datas = []
binaries = []
hiddenimports = [
    "edge_tts",
    "deep_translator",
    "faster_whisper",
    "ctranslate2",
    "tokenizers",
    "huggingface_hub",
    "onnxruntime",
    "av",
]

# Collect heavier packages when available
for pkg in ("edge_tts", "faster_whisper", "ctranslate2"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

try:
    datas += collect_data_files("edge_tts")
except Exception:
    pass

a = Analysis(
    ["dubvi/__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "nvidia",
        "tensorboard",
        "matplotlib",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="DubVIEngine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
