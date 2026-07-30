"""edge-tts Vietnamese voice with exponential backoff."""

from __future__ import annotations

import asyncio
from pathlib import Path

from . import events
from .jobs import CancellationToken
from .models import ErrorCode, Segment, Stage
from .system_info import EngineError, get_logger

log = get_logger("dubvi.tts")

MIN_MP3_BYTES = 500


async def _tts_once(text: str, out_mp3: Path, voice: str, rate: str) -> None:
    from .providers import get_tts_provider

    provider = get_tts_provider("edge-tts")
    await provider.synthesize(text, out_mp3, voice=voice, rate=rate)


async def tts_segment_with_backoff(
    text: str,
    out_mp3: Path,
    *,
    voice: str,
    max_attempts: int = 5,
    base_delay: float = 1.5,
) -> None:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    rates = ["+0%", "-5%", "+5%", "+0%", "-10%"]
    last_err: Exception | None = None

    for attempt in range(max_attempts):
        rate = rates[attempt % len(rates)]
        try:
            if out_mp3.exists():
                out_mp3.unlink()
            await _tts_once(text, out_mp3, voice, rate)
            if out_mp3.exists() and out_mp3.stat().st_size >= MIN_MP3_BYTES:
                return
            if out_mp3.exists():
                out_mp3.unlink()
            last_err = RuntimeError("TTS file too small")
        except Exception as e:
            last_err = e
            log.warning("TTS attempt %s: %s", attempt + 1, e)
            if out_mp3.exists():
                try:
                    out_mp3.unlink()
                except OSError:
                    pass
        delay = base_delay * (2**attempt)
        await asyncio.sleep(delay)

    raise EngineError(
        ErrorCode.TTS_FAILED,
        f"Không thể tạo giọng đọc sau {max_attempts} lần: {last_err}",
    )


async def synthesize_all(
    segments: list[Segment],
    seg_dir: Path,
    *,
    voice: str,
    cancel: CancellationToken | None = None,
    tracker=None,
) -> dict[int, Path]:
    """Generate MP3 per segment; skip existing valid files (resume)."""
    seg_dir.mkdir(parents=True, exist_ok=True)
    if tracker:
        tracker.begin_stage(Stage.TTS, f"Đang tạo giọng đọc ({len(segments)} đoạn)")
    else:
        events.stage(Stage.TTS, f"Đang tạo giọng đọc ({len(segments)} đoạn)")
    paths: dict[int, Path] = {}
    total = max(len(segments), 1)
    failures = 0

    for i, s in enumerate(segments):
        if cancel:
            cancel.check()
        text = (s.text_vi or s.text_en or "").strip()
        mp3 = seg_dir / f"{s.id:04d}.mp3"
        if not text:
            if tracker:
                tracker.emit(i + 1, total, f"Bỏ qua đoạn trống {i + 1}/{total}")
            continue
        if mp3.exists() and mp3.stat().st_size >= MIN_MP3_BYTES:
            paths[s.id] = mp3
        else:
            try:
                await tts_segment_with_backoff(text, mp3, voice=voice)
                paths[s.id] = mp3
            except EngineError as e:
                failures += 1
                events.error(e.code, f"Đoạn {s.id}: {e.message}", fatal=False)
                log.error("TTS give up seg %s: %s", s.id, e)

        msg = f"Tạo giọng {i + 1}/{total} đoạn"
        if tracker:
            tracker.emit(i + 1, total, msg)
        elif (i + 1) % 5 == 0 or i + 1 == total:
            events.progress(Stage.TTS, i + 1, total, msg)

    if failures and failures == total:
        raise EngineError(ErrorCode.TTS_FAILED, "Tất cả đoạn TTS đều thất bại")
    return paths


async def list_vi_voices() -> list[dict]:
    import edge_tts

    voices = await edge_tts.list_voices()
    return [v for v in voices if str(v.get("Locale", "")).startswith("vi-")]
