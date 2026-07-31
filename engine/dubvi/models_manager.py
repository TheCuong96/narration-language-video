"""Model download / list / delete under %LOCALAPPDATA%/DubVI/models."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Callable

from . import events
from .models import ErrorCode
from .system_info import EngineError, appdata_root, get_logger

log = get_logger("dubvi.models")

# Approximate download sizes (CTranslate2 faster-whisper conversions + offline NLLB/XTTS)
MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "tiny",
        "kind": "whisper",
        "label": "Tiny",
        "size_mb": 75,
        "speed": "Rất nhanh",
        "quality": "Thấp — thử nghiệm",
        "recommended_for": "Máy yếu / kiểm tra nhanh",
    },
    {
        "id": "base",
        "kind": "whisper",
        "label": "Base",
        "size_mb": 145,
        "speed": "Nhanh",
        "quality": "Khá",
        "recommended_for": "Video ngắn, máy trung bình",
    },
    {
        "id": "small",
        "kind": "whisper",
        "label": "Small (đề xuất CPU)",
        "size_mb": 485,
        "speed": "Trung bình",
        "quality": "Tốt",
        "recommended_for": "Máy CPU phổ thông — đề xuất v0.1",
        "recommended": True,
    },
    {
        "id": "medium",
        "kind": "whisper",
        "label": "Medium",
        "size_mb": 1500,
        "speed": "Chậm trên CPU",
        "quality": "Rất tốt",
        "recommended_for": "Máy mạnh hoặc GPU",
    },
    {
        "id": "large-v3",
        "kind": "whisper",
        "label": "Large v3",
        "size_mb": 3000,
        "speed": "Rất chậm trên CPU",
        "quality": "Cao nhất",
        "recommended_for": "Chỉ khi cần chất lượng tối đa + GPU",
    },
    {
        "id": "nllb-200-distilled-600M",
        "kind": "translate",
        "label": "NLLB-200 distilled 600M",
        "size_mb": 2400,
        "speed": "Trung bình (GPU nhanh hơn)",
        "quality": "Tốt — dịch offline",
        "recommended_for": "Dịch local không cần Google",
        "hf_repo": "facebook/nllb-200-distilled-600M",
        "provider": "nllb",
    },
    {
        "id": "xtts-v2",
        "kind": "tts",
        "label": "XTTS-v2 (viXTTS)",
        "size_mb": 1900,
        "speed": "Chậm trên CPU — nên dùng GPU",
        "quality": "Cao — giọng local / clone",
        "recommended_for": "TTS offline chất lượng cao (GPU khuyến nghị)",
        # Vietnamese fine-tune of Coqui XTTS-v2
        "hf_repo": "capleaf/viXTTS",
        "provider": "xtts-v2",
        "license_note": "Coqui CPML — không dùng thương mại",
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


def catalog_entry(model_id: str) -> dict[str, Any] | None:
    return next((m for m in MODEL_CATALOG if m["id"] == model_id), None)


def list_models(*, kind: str | None = None) -> list[dict[str, Any]]:
    out = []
    for m in MODEL_CATALOG:
        if kind and m.get("kind", "whisper") != kind:
            continue
        used = model_disk_usage_bytes(m["id"]) if is_model_downloaded(m["id"]) else 0
        out.append(
            {
                **m,
                "kind": m.get("kind", "whisper"),
                "downloaded": is_model_downloaded(m["id"]),
                "local_bytes": used,
                "local_mb": round(used / (1024 * 1024), 1) if used else 0,
                "download_root": str(models_dir()),
            }
        )
    return out


ProgressCb = Callable[[int, int, str], None]


def _disk_guard(model_id: str, size_mb: int) -> None:
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


def _write_marker(dest: Path, model_id: str, size_mb: int, extra: dict[str, Any] | None = None) -> None:
    payload = {
        "model_id": model_id,
        "path": str(dest),
        "size_mb_estimate": size_mb,
        "downloaded_at": time.time(),
    }
    if extra:
        payload.update(extra)
    (dest / "downloaded.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def _download_hf_snapshot(
    model_id: str,
    *,
    hf_repo: str,
    dest: Path,
    progress_cb: ProgressCb | None = None,
) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as e:
        raise EngineError(
            ErrorCode.WHISPER_LOAD_FAILED,
            "Thiếu huggingface_hub. Cài: pip install -r engine/requirements-offline.txt",
        ) from e

    events.progress("downloading_model", 5, 100, f"Đang tải HF {hf_repo}")
    if progress_cb:
        progress_cb(5, 100, model_id)

    try:
        path = snapshot_download(
            repo_id=hf_repo,
            local_dir=str(dest),
            local_dir_use_symlinks=False,
        )
    except TypeError:
        # Newer huggingface_hub removed local_dir_use_symlinks
        path = snapshot_download(repo_id=hf_repo, local_dir=str(dest))
    events.progress("downloading_model", 90, 100, f"Đã tải xong snapshot {model_id}")
    if progress_cb:
        progress_cb(90, 100, model_id)
    return Path(path)


def _ensure_xtts_speaker(dest: Path) -> None:
    """Pick a short reference wav used when user has not set xtts_speaker_wav."""
    speaker = dest / "speaker_default.wav"
    if speaker.is_file() and speaker.stat().st_size > 1000:
        return

    # Prefer Vietnamese samples shipped with viXTTS
    local_candidates = [
        dest / "vi_sample.wav",
        dest / "samples" / "nu-nhe-nhang.wav",
        dest / "samples" / "nu-calm.wav",
        dest / "samples" / "nam-calm.wav",
    ]
    for src in local_candidates:
        if src.is_file() and src.stat().st_size > 1000:
            shutil.copy2(src, speaker)
            events.log(f"Đã chọn speaker mặc định: {src.name}")
            return

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return

    remote_candidates = [
        ("capleaf/viXTTS", "vi_sample.wav"),
        ("capleaf/viXTTS", "samples/nu-nhe-nhang.wav"),
        ("coqui/XTTS-v2", "samples/en_sample.wav"),
    ]
    for repo, file_name in remote_candidates:
        try:
            downloaded = hf_hub_download(repo_id=repo, filename=file_name)
            shutil.copy2(downloaded, speaker)
            events.log(f"Đã lấy speaker mặc định: {file_name}")
            return
        except Exception as e:
            log.debug("speaker download miss %s/%s: %s", repo, file_name, e)

    events.warning(
        "XTTS_SPEAKER_MISSING",
        "Không tìm thấy sample speaker. Đặt đường dẫn WAV trong Settings (xtts_speaker_wav).",
    )


def download_model(
    model_id: str,
    *,
    progress_cb: ProgressCb | None = None,
) -> Path:
    """
    Download model into LOCALAPPDATA/DubVI/models/<id>.
    Never silent: emits size estimate and progress events.
    """
    meta = catalog_entry(model_id)
    if meta is None:
        raise EngineError(ErrorCode.INVALID_ARGS, f"Model không hợp lệ: {model_id}")

    size_mb = int(meta["size_mb"])
    kind = meta.get("kind", "whisper")
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
    if meta.get("license_note"):
        events.warning("MODEL_LICENSE", str(meta["license_note"]), model=model_id)

    _disk_guard(model_id, size_mb)

    dest = model_path(model_id)
    dest.mkdir(parents=True, exist_ok=True)
    events.progress("downloading_model", 0, 100, f"Bắt đầu tải {model_id}")
    t0 = time.time()

    def _hook(progress: float) -> None:
        pct = int(max(0, min(100, progress * 100)))
        events.progress("downloading_model", pct, 100, f"Đang tải {model_id}: {pct}%")
        if progress_cb:
            progress_cb(pct, 100, model_id)

    try:
        if kind == "whisper":
            try:
                from faster_whisper.utils import download_model as fw_download
            except Exception as e:
                raise EngineError(
                    ErrorCode.WHISPER_LOAD_FAILED,
                    f"Không import được faster-whisper để tải model: {e}",
                ) from e
            try:
                path = fw_download(
                    model_id,
                    output_dir=str(dest),
                    local_files_only=False,
                )
                _write_marker(dest, model_id, size_mb, {"path": str(path), "kind": kind})
            except TypeError:
                import os

                os.environ["HF_HOME"] = str(models_dir() / "hf")
                path = fw_download(model_id)
                _write_marker(dest, model_id, size_mb, {"path": str(path), "kind": kind})
        else:
            hf_repo = meta.get("hf_repo")
            if not hf_repo:
                raise EngineError(
                    ErrorCode.INVALID_ARGS,
                    f"Model {model_id} thiếu hf_repo trong catalog",
                )
            _download_hf_snapshot(
                model_id, hf_repo=hf_repo, dest=dest, progress_cb=progress_cb
            )
            if kind == "tts" and model_id == "xtts-v2":
                _ensure_xtts_speaker(dest)
            _write_marker(
                dest,
                model_id,
                size_mb,
                {"kind": kind, "hf_repo": hf_repo},
            )
    except EngineError:
        raise
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
