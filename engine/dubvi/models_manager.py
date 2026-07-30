"""Whisper model download / list / delete under %LOCALAPPDATA%/DubVI/models."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from . import events
from .models import ErrorCode
from .system_info import EngineError, appdata_root, get_logger

log = get_logger("dubvi.models")

# Approximate download sizes (CTranslate2 faster-whisper conversions)
MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "tiny",
        "label": "Tiny",
        "size_mb": 75,
        "speed": "Rất nhanh",
        "quality": "Thấp — thử nghiệm",
        "recommended_for": "Máy yếu / kiểm tra nhanh",
    },
    {
        "id": "base",
        "label": "Base",
        "size_mb": 145,
        "speed": "Nhanh",
        "quality": "Khá",
        "recommended_for": "Video ngắn, máy trung bình",
    },
    {
        "id": "small",
        "label": "Small (đề xuất CPU)",
        "size_mb": 485,
        "speed": "Trung bình",
        "quality": "Tốt",
        "recommended_for": "Máy CPU phổ thông — đề xuất v0.1",
        "recommended": True,
    },
    {
        "id": "medium",
        "label": "Medium",
        "size_mb": 1500,
        "speed": "Chậm trên CPU",
        "quality": "Rất tốt",
        "recommended_for": "Máy mạnh hoặc GPU",
    },
    {
        "id": "large-v3",
        "label": "Large v3",
        "size_mb": 3000,
        "speed": "Rất chậm trên CPU",
        "quality": "Cao nhất",
        "recommended_for": "Chỉ khi cần chất lượng tối đa + GPU",
    },
]


def models_dir() -> Path:
    d = appdata_root() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def model_path(model_id: str) -> Path:
    return models_dir() / model_id


def is_model_downloaded(model_id: str) -> bool:
    p = model_path(model_id)
    if not p.exists():
        return False
    # faster-whisper stores a folder with model.bin / config
    return any(p.iterdir()) if p.is_dir() else p.is_file()


def model_disk_usage_bytes(model_id: str | None = None) -> int:
    root = models_dir() if model_id is None else model_path(model_id)
    if not root.exists():
        return 0
    total = 0
    if root.is_file():
        return root.stat().st_size
    for f in root.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def list_models() -> list[dict[str, Any]]:
    out = []
    for m in MODEL_CATALOG:
        used = model_disk_usage_bytes(m["id"]) if is_model_downloaded(m["id"]) else 0
        out.append(
            {
                **m,
                "downloaded": is_model_downloaded(m["id"]),
                "local_bytes": used,
                "local_mb": round(used / (1024 * 1024), 1) if used else 0,
                "download_root": str(models_dir()),
            }
        )
    return out


ProgressCb = Callable[[int, int, str], None]


def download_model(
    model_id: str,
    *,
    progress_cb: ProgressCb | None = None,
) -> Path:
    """
    Download faster-whisper model into LOCALAPPDATA/DubVI/models/<id>.
    Never silent: emits size estimate and progress events.
    """
    meta = next((m for m in MODEL_CATALOG if m["id"] == model_id), None)
    if meta is None:
        raise EngineError(ErrorCode.INVALID_ARGS, f"Model không hợp lệ: {model_id}")

    size_mb = int(meta["size_mb"])
    events.stage(
        "downloading_model",
        f"Sẽ tải model '{model_id}' (~{size_mb} MB) vào {models_dir()}",
    )
    events.warning(
        "MODEL_DOWNLOAD_SIZE",
        f"Model {model_id} khoảng {size_mb} MB. Cần Internet và đủ dung lượng ổ cứng.",
        model=model_id,
        size_mb=size_mb,
    )

    # Disk check
    from .system_info import free_disk_bytes

    free = free_disk_bytes(models_dir())
    need = size_mb * 1024 * 1024 + 200 * 1024 * 1024
    if free < need:
        raise EngineError(
            ErrorCode.DISK_SPACE_LOW,
            f"Cần ít nhất {need // (1024**3) or need // (1024**2)} "
            f"{'GB' if need >= 1024**3 else 'MB'} trống để tải model {model_id}, "
            f"nhưng ổ đĩa chỉ còn {free // (1024**2)} MB.",
        )

    dest = model_path(model_id)
    dest.mkdir(parents=True, exist_ok=True)

    try:
        from faster_whisper.utils import download_model as fw_download
    except Exception as e:
        raise EngineError(
            ErrorCode.WHISPER_LOAD_FAILED,
            f"Không import được faster-whisper để tải model: {e}",
        ) from e

    events.progress("downloading_model", 0, 100, f"Bắt đầu tải {model_id}")
    t0 = time.time()

    def _hook(progress: float) -> None:
        # progress 0..1 if provided by library; otherwise synthetic
        pct = int(max(0, min(100, progress * 100)))
        events.progress("downloading_model", pct, 100, f"Đang tải {model_id}: {pct}%")
        if progress_cb:
            progress_cb(pct, 100, model_id)

    try:
        # faster-whisper download_model(size_or_id, output_dir=..., local_files_only=False)
        path = fw_download(
            model_id,
            output_dir=str(dest),
            local_files_only=False,
        )
        # Some versions return cache path under huggingface hub; ensure copy/marker
        marker = dest / "downloaded.json"
        marker.write_text(
            json.dumps(
                {
                    "model_id": model_id,
                    "path": str(path),
                    "size_mb_estimate": size_mb,
                    "downloaded_at": time.time(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except TypeError:
        # Older signature without output_dir — use download_root via env HF hub
        import os

        os.environ["HF_HOME"] = str(models_dir() / "hf")
        path = fw_download(model_id)
        (dest / "downloaded.json").write_text(
            json.dumps({"model_id": model_id, "path": str(path)}, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        raise EngineError(
            ErrorCode.WHISPER_LOAD_FAILED,
            f"Tải model thất bại (có thể thử lại): {e}",
        ) from e

    events.progress("downloading_model", 100, 100, f"Xong {model_id}")
    events.log(f"Đã tải model {model_id} trong {time.time() - t0:.0f}s → {dest}")
    _hook(1.0)
    return dest


def delete_model(model_id: str, *, confirm: bool = False) -> None:
    if not confirm:
        raise EngineError(
            ErrorCode.INVALID_ARGS,
            "Cần xác nhận mới xóa model (confirm=true)",
        )
    p = model_path(model_id)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    # Also clear HF hub cache slice if present
    hf = models_dir() / "hf"
    events.log(f"Đã xóa model cache: {model_id}")
    events.system({"models": list_models(), "hf_cache": str(hf)})


def whisper_download_root() -> str:
    return str(models_dir())
