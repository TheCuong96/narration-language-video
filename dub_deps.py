#!/usr/bin/env python3
"""
Dependency checker / installer for dub-vi.

Checks:
  - Python 3.10+
  - FFmpeg + ffprobe on PATH (auto-install via winget on Windows if missing)
  - pip packages: faster-whisper, edge-tts, deep-translator
  - Optional CUDA libs on Windows (nvidia-cublas-cu12, nvidia-cudnn-cu12)
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_PY = (3, 10)

PIP_REQUIRED = [
    ("faster_whisper", "faster-whisper>=1.1.0"),
    ("edge_tts", "edge-tts>=6.1.0"),
    ("deep_translator", "deep-translator>=1.11.4"),
]

PIP_CUDA_OPTIONAL = [
    ("nvidia.cublas", "nvidia-cublas-cu12"),
    ("nvidia.cudnn", "nvidia-cudnn-cu12"),
]

TOOLS_DIR = Path(__file__).resolve().parent
REQUIREMENTS_FILE = TOOLS_DIR / "requirements-dub.txt"


def _ok(msg: str) -> None:
    print(f"  [OK]  {msg}", flush=True)


def _warn(msg: str) -> None:
    print(f"  [..]  {msg}", flush=True)


def _fail(msg: str) -> None:
    print(f"  [!!]  {msg}", flush=True)


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, **kwargs)


def which(name: str) -> str | None:
    return shutil.which(name)


def check_python() -> bool:
    v = sys.version_info
    if (v.major, v.minor) < REQUIRED_PY:
        _fail(
            f"Python {REQUIRED_PY[0]}.{REQUIRED_PY[1]}+ required, found "
            f"{v.major}.{v.minor}.{v.micro}"
        )
        return False
    _ok(f"Python {v.major}.{v.minor}.{v.micro}")
    return True


def check_ffmpeg() -> bool:
    ffmpeg = which("ffmpeg")
    ffprobe = which("ffprobe")
    if ffmpeg and ffprobe:
        try:
            out = subprocess.check_output(
                ["ffmpeg", "-version"], text=True, stderr=subprocess.STDOUT
            )
            first = out.splitlines()[0] if out else "ffmpeg"
            _ok(f"FFmpeg: {first}")
        except Exception:
            _ok(f"FFmpeg at {ffmpeg}")
        return True
    missing = []
    if not ffmpeg:
        missing.append("ffmpeg")
    if not ffprobe:
        missing.append("ffprobe")
    _fail(f"Missing on PATH: {', '.join(missing)}")
    return False


def install_ffmpeg_windows() -> bool:
    """Try winget to install FFmpeg. Returns True if now available."""
    winget = which("winget")
    if not winget:
        _fail("winget not found — install FFmpeg manually: https://ffmpeg.org/download.html")
        _fail("Or: winget install --id Gyan.FFmpeg -e")
        return False

    candidates = [
        ["winget", "install", "--id", "Gyan.FFmpeg", "-e", "--accept-package-agreements", "--accept-source-agreements"],
        ["winget", "install", "--id", "yt-dlp.FFmpeg", "-e", "--accept-package-agreements", "--accept-source-agreements"],
    ]
    for cmd in candidates:
        _warn(f"Installing FFmpeg via: {' '.join(cmd)}")
        try:
            r = _run(cmd)
            if r.returncode == 0:
                # New PATH may not be in this process — tell user / try refresh
                if check_ffmpeg():
                    return True
                _warn(
                    "FFmpeg installed but not yet on PATH in this terminal. "
                    "Close & reopen terminal, then run again."
                )
                return False
        except Exception as e:
            _warn(f"winget failed: {e}")
    return False


def module_available(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def pip_install(packages: list[str]) -> bool:
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *packages]
    _warn(f"pip install {' '.join(packages)}")
    r = _run(cmd)
    return r.returncode == 0


def check_pip_packages(auto_install: bool) -> bool:
    missing_pkgs: list[str] = []
    for mod, pkg in PIP_REQUIRED:
        if module_available(mod):
            _ok(f"Python package: {pkg.split('>=')[0]}")
        else:
            _fail(f"Missing package: {pkg}")
            missing_pkgs.append(pkg)

    if missing_pkgs:
        if not auto_install:
            _fail(f"Run: pip install {' '.join(missing_pkgs)}")
            return False
        if REQUIREMENTS_FILE.exists():
            ok = pip_install(["-r", str(REQUIREMENTS_FILE)])
        else:
            ok = pip_install(missing_pkgs)
        if not ok:
            _fail("pip install failed")
            return False
        # re-check
        still = [pkg for mod, pkg in PIP_REQUIRED if not module_available(mod)]
        if still:
            _fail(f"Still missing after install: {', '.join(still)}")
            return False
        for mod, pkg in PIP_REQUIRED:
            _ok(f"Installed: {pkg.split('>=')[0]}")
    return True


def check_cuda_optional(auto_install: bool, prefer_gpu: bool) -> None:
    """Best-effort CUDA libs for faster-whisper on Windows. Never fails the run."""
    if not prefer_gpu:
        _warn("GPU skipped (--cpu). Whisper will use CPU.")
        return

    # Detect nvidia-smi
    if which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            _ok(f"NVIDIA GPU: {out.splitlines()[0]}")
        except Exception:
            _ok("nvidia-smi present")
    else:
        _warn("No nvidia-smi — will try CUDA anyway, fallback to CPU if needed")

    if sys.platform != "win32":
        return

    missing = [pkg for mod, pkg in PIP_CUDA_OPTIONAL if not module_available(mod)]
    if not missing:
        _ok("CUDA pip libs (cublas/cudnn)")
        return

    _warn(f"Optional CUDA libs missing: {', '.join(missing)}")
    if auto_install:
        if pip_install(missing):
            _ok("Installed CUDA pip libs")
        else:
            _warn("Could not install CUDA libs — tool may fall back to CPU")


def ensure_deps(
    *,
    auto_install: bool = True,
    install_ffmpeg: bool = True,
    prefer_gpu: bool = True,
    quiet_header: bool = False,
) -> bool:
    """
    Verify runtime dependencies. Optionally install missing ones.
    Returns True if ready to run dub-vi.
    """
    if not quiet_header:
        print("\n=== dub-vi dependency check ===", flush=True)

    ok = True
    if not check_python():
        ok = False

    if not check_ffmpeg():
        if auto_install and install_ffmpeg and sys.platform == "win32":
            if not install_ffmpeg_windows():
                ok = False
        else:
            ok = False

    if not check_pip_packages(auto_install=auto_install):
        ok = False

    check_cuda_optional(auto_install=auto_install, prefer_gpu=prefer_gpu)

    if ok:
        print("=== All required dependencies ready ===\n", flush=True)
    else:
        print("=== Dependency check FAILED — fix items above, then retry ===\n", flush=True)
    return ok


def add_nvidia_dll_dirs() -> None:
    """Make pip-installed CUDA wheels discoverable on Windows."""
    if sys.platform != "win32":
        return
    import site

    roots: list[str] = []
    try:
        roots.extend(site.getsitepackages())
    except Exception:
        pass
    try:
        roots.append(site.getusersitepackages())
    except Exception:
        pass
    for root in roots:
        for rel in (
            Path("nvidia") / "cublas" / "bin",
            Path("nvidia") / "cudnn" / "bin",
            Path("nvidia") / "cuda_runtime" / "bin",
            Path("ctranslate2"),
        ):
            p = Path(root) / rel
            if p.is_dir():
                os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(str(p))
                    except OSError:
                        pass


if __name__ == "__main__":
    auto = "--no-install" not in sys.argv
    raise SystemExit(0 if ensure_deps(auto_install=auto) else 1)
