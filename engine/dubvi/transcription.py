"""Speech recognition via faster-whisper."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from . import cache, events
from .jobs import CancellationToken
from .models import DeviceInfo, ErrorCode, Segment, Stage
from .system_info import EngineError, add_nvidia_dll_dirs, get_logger, resolve_device

if TYPE_CHECKING:
    from .progress import ProgressTracker

log = get_logger("dubvi.transcription")

_model = None
_model_key: tuple | None = None


def load_whisper_model(
    model_name: str,
    *,
    prefer_gpu: bool = False,
) -> tuple[object, DeviceInfo]:
    """Load Whisper with CPU default; GPU opt-in + automatic CPU fallback."""
    global _model, _model_key

    device_info = resolve_device(prefer_gpu=prefer_gpu)
    key = (model_name, device_info.device, device_info.compute_type)
    if _model is not None and _model_key == key:
        return _model, device_info

    add_nvidia_dll_dirs()
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise EngineError(
            ErrorCode.WHISPER_LOAD_FAILED,
            "Thiếu faster-whisper. Cài: pip install -r engine/requirements-base.txt",
        ) from e

    from .models_manager import is_model_downloaded, whisper_download_root

    download_root = whisper_download_root()
    events.stage(
        Stage.INIT,
        f"Đang tải Whisper model={model_name} device={device_info.device}",
    )
    if not is_model_downloaded(model_name):
        events.warning(
            "MODEL_NOT_DOWNLOADED",
            f"Model '{model_name}' chưa có trên máy. Hãy tải trong Settings "
            f"(~dung lượng xem danh sách model). Thư mục: {download_root}",
            model=model_name,
        )

    def _load(device: str, compute: str):
        return WhisperModel(
            model_name,
            device=device,
            compute_type=compute,
            download_root=download_root,
        )

    try:
        model = _load(device_info.device, device_info.compute_type)
    except Exception as e:
        if device_info.device != "cpu":
            reason = f"GPU không dùng được ({e}); chuyển sang CPU"
            log.warning(reason)
            events.log(reason, level="warn")
            device_info = DeviceInfo(
                device="cpu",
                compute_type="int8",
                gpu_name=device_info.gpu_name,
                fallback_reason=reason,
            )
            try:
                model = _load("cpu", "int8")
            except Exception as e2:
                raise EngineError(
                    ErrorCode.WHISPER_LOAD_FAILED,
                    f"Không tải được Whisper: {e2}",
                ) from e2
        else:
            raise EngineError(
                ErrorCode.WHISPER_LOAD_FAILED,
                f"Không tải được Whisper: {e}",
            ) from e

    if device_info.fallback_reason:
        events.log(device_info.fallback_reason, level="warn")

    _model = model
    _model_key = (model_name, device_info.device, device_info.compute_type)
    events.system(
        {
            "whisper_device": device_info.device,
            "whisper_compute": device_info.compute_type,
            "gpu_name": device_info.gpu_name,
            "fallback_reason": device_info.fallback_reason,
        }
    )
    return model, device_info


def transcribe(
    audio_path: Path,
    transcript_path: Path,
    model,
    *,
    source_lang: str = "en",
    cancel: CancellationToken | None = None,
    tracker: ProgressTracker | None = None,
    duration_sec: float = 0.0,
) -> list[Segment]:
    cached = cache.load_segments(transcript_path)
    if cached is not None:
        events.log(f"Dùng cache transcript: {transcript_path.name}")
        if tracker:
            tracker.begin_stage(Stage.TRANSCRIBING, "Dùng cache nhận dạng")
            tracker.emit(1, 1, "Đã có transcript trong cache")
        return cached

    if cancel:
        cancel.check()

    if tracker:
        tracker.begin_stage(Stage.TRANSCRIBING, "Đang nhận dạng lời nói (Whisper)…")
        tracker.emit(0, 100, "Whisper đang khởi động / phân tích audio…")
    else:
        events.stage(Stage.TRANSCRIBING, "Đang nhận dạng lời nói")

    kwargs: dict = {
        "vad_filter": True,
        "vad_parameters": dict(min_silence_duration_ms=400),
        "word_timestamps": False,
    }
    if source_lang and source_lang != "auto":
        kwargs["language"] = source_lang

    try:
        segments_iter, info = model.transcribe(str(audio_path), **kwargs)
    except Exception as e:
        raise EngineError(ErrorCode.TRANSCRIBE_FAILED, f"Nhận dạng thất bại: {e}") from e

    events.log(
        f"Ngôn ngữ phát hiện: {info.language} (prob={info.language_probability:.2f})"
    )
    if tracker:
        tracker.emit(5, 100, f"Đã phát hiện ngôn ngữ: {info.language}")

    segments: list[Segment] = []
    last_pct = -1
    duration = max(float(duration_sec or 0), 0.0)

    for seg in segments_iter:
        if cancel:
            cancel.check()
        text = (seg.text or "").strip()
        if not text:
            continue
        segments.append(
            Segment(
                id=len(segments),
                start=round(seg.start, 3),
                end=round(seg.end, 3),
                text_en=text,
            )
        )
        # Prefer timeline progress over segment-count (count grows unbounded)
        if duration > 0:
            pct = int(max(5, min(99, (float(seg.end) / duration) * 100)))
        else:
            pct = min(99, 5 + len(segments))  # coarse fallback

        if tracker:
            if pct != last_pct and (pct % 2 == 0 or len(segments) % 5 == 0):
                last_pct = pct
                tracker.emit(
                    pct,
                    100,
                    f"Nhận dạng ~{pct}% · {len(segments)} đoạn · {seg.end:.0f}s",
                )
        elif len(segments) % 10 == 0:
            events.progress(
                Stage.TRANSCRIBING,
                pct if duration > 0 else len(segments),
                100 if duration > 0 else max(len(segments), 1),
                f"Đã nhận {len(segments)} đoạn",
            )

    if not segments:
        raise EngineError(ErrorCode.TRANSCRIBE_FAILED, "Không nhận được đoạn lời nói nào")

    cache.save_segments(transcript_path, segments)
    if tracker:
        tracker.emit(100, 100, f"Xong nhận dạng · {len(segments)} đoạn")
    else:
        events.progress(Stage.TRANSCRIBING, len(segments), len(segments), "Xong nhận dạng")
    return segments
