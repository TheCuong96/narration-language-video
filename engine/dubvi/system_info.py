"""Paths, disk space, GPU detection, technical logging."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .models import DeviceInfo


def appdata_root() -> Path:
    """%LOCALAPPDATA%/DubVI on Windows; ~/.local/share/DubVI elsewhere."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "DubVI"
    return Path.home() / ".local" / "share" / "DubVI"


def logs_dir() -> Path:
    d = appdata_root() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def jobs_dir() -> Path:
    d = appdata_root() / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def job_dir(job_id: str) -> Path:
    d = jobs_dir() / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def setup_logging(job_id: str | None = None) -> Path:
    """Technical logs under %LOCALAPPDATA%/DubVI/logs. Returns log file path."""
    log_path = logs_dir() / (f"job-{job_id}.log" if job_id else "engine.log")
    root = logging.getLogger("dubvi")
    root.setLevel(logging.DEBUG)
    # Avoid duplicate handlers when CLI re-enters
    if not any(
        isinstance(h, RotatingFileHandler)
        and getattr(h, "baseFilename", None) == str(log_path)
        for h in root.handlers
    ):
        fh = RotatingFileHandler(
            log_path,
            maxBytes=5_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        fh.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(fh)
    return log_path


def get_logger(name: str = "dubvi") -> logging.Logger:
    return logging.getLogger(name)


def free_disk_bytes(path: Path) -> int:
    """Free bytes on the volume containing path (creates parents if needed)."""
    target = path if path.exists() else path.parent
    target.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(str(target))
    return int(usage.free)


def estimate_work_bytes(video: Path) -> int:
    """
    Rough upper bound for temp/cache for one video.
    FLAC extract ~ video_audio_size; segments + fitted + narration ~ 1.5–3× audio.
    Use 2× file size + 500MB headroom.
    """
    size = video.stat().st_size if video.is_file() else 0
    return size * 2 + 500 * 1024 * 1024


def ensure_disk_space(video: Path, work_root: Path, output_dir: Path) -> None:
    from .models import ErrorCode

    needed = estimate_work_bytes(video)
    for p in (work_root, output_dir):
        free = free_disk_bytes(p)
        if free < needed:
            need_gb = needed / (1024**3)
            free_gb = free / (1024**3)
            if need_gb >= 1 or free_gb >= 1:
                msg = (
                    f"Cần ít nhất {need_gb:.1f} GB nhưng ổ đĩa chỉ còn {free_gb:.1f} GB "
                    f"({p})."
                )
            else:
                msg = (
                    f"Cần ít nhất {needed // (1024**2)} MB nhưng ổ đĩa chỉ còn "
                    f"{free // (1024**2)} MB ({p})."
                )
            raise EngineError(ErrorCode.DISK_SPACE_LOW, msg)


class EngineError(Exception):
    def __init__(self, code: "ErrorCode | str", message: str):
        from .models import ErrorCode as EC

        self.code = code if isinstance(code, EC) else EC(str(code))
        self.message = message
        super().__init__(message)


def detect_nvidia_gpu() -> str | None:
    """Return GPU name if nvidia-smi works; else None."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    try:
        out = subprocess.check_output(
            [smi, "--query-gpu=name", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        ).strip()
        if out:
            return out.splitlines()[0].strip()
    except Exception:
        return None
    return None


def resolve_device(*, prefer_gpu: bool) -> DeviceInfo:
    """
    v0.1: default CPU. If prefer_gpu and CUDA works, use it;
    otherwise fall back to CPU with a clear reason.
    """
    if not prefer_gpu:
        return DeviceInfo(device="cpu", compute_type="int8", fallback_reason=None)

    gpu = detect_nvidia_gpu()
    if not gpu:
        return DeviceInfo(
            device="cpu",
            compute_type="int8",
            fallback_reason="Không phát hiện NVIDIA GPU — dùng CPU",
        )

    # Actual CUDA usability is verified when loading WhisperModel
    return DeviceInfo(
        device="cuda",
        compute_type="float16",
        gpu_name=gpu,
        fallback_reason=None,
    )


def add_nvidia_dll_dirs() -> None:
    """Make pip-installed CUDA wheels discoverable on Windows (dev only)."""
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


def collect_system_info() -> dict:
    from . import __version__
    from .ffmpeg import ffmpeg_path, ffprobe_path, which_or_bundled

    info = {
        "engine_version": __version__,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "appdata": str(appdata_root()),
        "ffmpeg": which_or_bundled("ffmpeg", ffmpeg_path()),
        "ffprobe": which_or_bundled("ffprobe", ffprobe_path()),
        "gpu": detect_nvidia_gpu(),
        "device_default": resolve_device(prefer_gpu=False).device,
    }
    return info
