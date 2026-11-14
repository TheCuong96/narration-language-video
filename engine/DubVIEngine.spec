# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for DubVIEngine (Tauri sidecar).

Build (from engine/):
  pip install -r requirements-base.txt pyinstaller
  pyinstaller DubVIEngine.spec

Use onedir (not onefile): onefile unpacks ~1GB into %TEMP%\\_MEI* on every
launch and often leaves orphans when the process is force-killed. Onedir
ships the extracted tree next to the exe so no TEMP extract is needed.

Bundle FFmpeg separately into resources/bin for the Tauri installer —
do not rely on system PATH in production.
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files
from pathlib import Path
import hashlib
import json

block_cipher = None

datas = []
binaries = []
hiddenimports = [
    "requests",
    "urllib3",
    "certifi",
    "dubvi.providers.ollama",
    "dubvi.providers.fallback",
    "edge_tts",
    "deep_translator",
    "faster_whisper",
    "ctranslate2",
    "tokenizers",
    "huggingface_hub",
    "onnxruntime",
    "av",
    # setuptools/pkg_resources (PyInstaller pyi_rth_pkgres) needs these at runtime
    "appdirs",
    "packaging",
    "jaraco",
    "jaraco.text",
    "jaraco.functools",
    "jaraco.context",
    "more_itertools",
    "platformdirs",
]

# Collect heavier packages when available
for pkg in ("requests", "urllib3", "certifi", "edge_tts", "faster_whisper", "ctranslate2"):
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

# Offline XTTS (coqui-tts) — PyInstaller's import scan alone misses what it
# needs at runtime:
#  - torchcodec: coqui raises ImportError on torch>=2.9 without it, and
#    transformers reads its dist-info (importlib.metadata) → needs collect_all.
#  - TTS: configs/__init__.py does os.listdir() on its own folder.
#  - inflect: typeguard @typechecked calls inspect.getsource().
#  - gruut*/ko_speech_tools: language data files read at import time.
for pkg in (
    "TTS",
    "torchcodec",
    "inflect",
    "gruut",
    "gruut_ipa",
    "gruut_lang_en",
    "gruut_lang_de",
    "gruut_lang_es",
    "gruut_lang_fr",
    "ko_speech_tools",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    # Top-level entry with absolute imports — do NOT use dubvi/__main__.py
    # (relative imports break when PyInstaller runs it as a bare script).
    ["run_engine.py"],
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
        # NOT matplotlib: coqui-tts imports it at module level (vocoder utils).
        "tkinter",
    ],
    # Keep .py next to the bytecode for packages that read their own source
    # files at runtime (os.listdir / inspect.getsource).
    module_collection_mode={
        "TTS": "pyz+py",
        "inflect": "pyz+py",
    },
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# torch wheels can contain license trees deeper than Windows MAX_PATH, even
# in a normal checkout. Preserve every notice at a short, unique destination
# and ship an index mapping its original path to the bundled location.
license_index = []
short_datas = []
for dest, source, kind in a.datas:
    original = dest.replace("\\", "/")
    if ".dist-info/licenses/" in original:
        package = original.split(".dist-info/", 1)[0].split("/")[-1]
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()[:16]
        dest = f"third_party_licenses/{package}/{digest}_{Path(original).name}"
        license_index.append({"original": original, "bundled": dest})
    short_datas.append((dest, source, kind))
if license_index:
    index_path = Path("build") / "license-paths.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(license_index, indent=2), encoding="utf-8")
    short_datas.append(("third_party_licenses/license-paths.json", str(index_path.resolve()), "DATA"))
a.datas = short_datas

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DubVIEngine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name="DubVIEngine",
)
