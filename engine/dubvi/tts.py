"""TTS Vietnamese voice with exponential backoff (edge-tts or local XTTS)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from . import events
from .jobs import CancellationToken
from .models import ErrorCode, Segment, Stage
from .system_info import EngineError, get_logger

log = get_logger("dubvi.tts")

MIN_MP3_BYTES = 500
# edge-tts has no batch API — each segment is one HTTP/WebSocket request.
# Parallel requests are the main speed lever (not separate API keys).
DEFAULT_EDGE_TTS_CONCURRENCY = 10
MAX_EDGE_TTS_CONCURRENCY = 20


def default_tts_concurrency(
    provider_name: str,
    *,
    prefer_gpu: bool = False,
) -> int:
    """Pick safe default parallelism for the active TTS backend."""
    name = (provider_name or "edge-tts").lower()
    if name.startswith("xtts"):
        return 1 if prefer_gpu else 2
    return DEFAULT_EDGE_TTS_CONCURRENCY


async def _tts_once(
    text: str,
    out_mp3: Path,
    voice: str,
    rate: str,
    *,
    provider,
) -> None:
    await provider.synthesize(text, out_mp3, voice=voice, rate=rate)


async def tts_segment_with_backoff(
    text: str,
    out_mp3: Path,
    *,
    voice: str,
    provider,
    max_attempts: int = 5,
    base_delay: float = 1.5,
) -> None:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    rates = ["+0%", "-5%", "+5%", "+0%", "-10%"]
    last_err: Exception | None = None
    attempts = max_attempts if getattr(provider, "requires_internet", True) else min(2, max_attempts)

    for attempt in range(attempts):
        rate = rates[attempt % len(rates)]
        try:
            if out_mp3.exists():
                out_mp3.unlink()
            await _tts_once(text, out_mp3, voice, rate, provider=provider)
            if out_mp3.exists() and out_mp3.stat().st_size >= MIN_MP3_BYTES:
                return
            if out_mp3.exists():
                out_mp3.unlink()
            last_err = RuntimeError("TTS file too small")
        except EngineError:
            raise
        except Exception as e:
            last_err = e
            log.warning("TTS attempt %s: %s", attempt + 1, e)
            if out_mp3.exists():
                try:
                    out_mp3.unlink()
                except OSError:
                    pass
        delay = base_delay * (2**attempt) if getattr(provider, "requires_internet", True) else 0.5
        await asyncio.sleep(delay)

    raise EngineError(
        ErrorCode.TTS_FAILED,
        f"Không thể tạo giọng đọc sau {attempts} lần: {last_err}",
    )


async def synthesize_all(
    segments: list[Segment],
    seg_dir: Path,
    *,
    voice: str,
    cancel: CancellationToken | None = None,
    tracker=None,
    provider_name: str = "edge-tts",
    prefer_gpu: bool = False,
    speaker_wav: str = "",
    language: str = "vi",
    concurrency: int = 0,
) -> dict[int, Path]:
    """Generate MP3 per segment in parallel; skip existing valid files (resume)."""
    from .providers import get_tts_provider

    provider = get_tts_provider(
        provider_name,
        prefer_gpu=prefer_gpu,
        speaker_wav=speaker_wav or None,
        language=language,
    )
    workers = concurrency if concurrency > 0 else default_tts_concurrency(
        provider_name, prefer_gpu=prefer_gpu
    )
    if not (provider_name or "edge-tts").lower().startswith("xtts"):
        workers = min(workers, MAX_EDGE_TTS_CONCURRENCY)
    workers = max(1, min(workers, max(len(segments), 1)))

    seg_dir.mkdir(parents=True, exist_ok=True)
    label = (
        f"Đang tạo giọng đọc ({len(segments)} đoạn, {workers} luồng) "
        f"[{provider.name}]"
    )
    if tracker:
        tracker.begin_stage(Stage.TTS, label)
    else:
        events.stage(Stage.TTS, label)
    events.log(provider.privacy_note())
    if workers > 1:
        events.log(
            f"TTS song song: {workers} request cùng lúc "
            f"(edge-tts không có batch — mỗi đoạn = 1 request)"
        )

    paths: dict[int, Path] = {}
    total = max(len(segments), 1)
    failures = 0
    done = 0
    progress_lock = asyncio.Lock()
    sem = asyncio.Semaphore(workers)

    async def _emit_progress(msg: str) -> None:
        if tracker:
            tracker.emit(done, total, msg)
        elif done % 5 == 0 or done == total:
            events.progress(Stage.TTS, done, total, msg)

    async def _process_segment(i: int, s: Segment) -> None:
        nonlocal done, failures
        if cancel:
            cancel.check()
        text = (s.text_vi or s.text_en or "").strip()
        mp3 = seg_dir / f"{s.id:04d}.mp3"
        if not text:
            async with progress_lock:
                done += 1
                await _emit_progress(f"Bỏ qua đoạn trống {done}/{total}")
            return

        if mp3.exists() and mp3.stat().st_size >= MIN_MP3_BYTES:
            async with progress_lock:
                paths[s.id] = mp3
                done += 1
                await _emit_progress(f"Tạo giọng {done}/{total} đoạn (cache)")
            return

        async with sem:
            if cancel:
                cancel.check()
            try:
                await tts_segment_with_backoff(
                    text, mp3, voice=voice, provider=provider
                )
                async with progress_lock:
                    paths[s.id] = mp3
            except EngineError as e:
                async with progress_lock:
                    failures += 1
                events.error(e.code, f"Đoạn {s.id}: {e.message}", fatal=False)
                log.error("TTS give up seg %s: %s", s.id, e)

        async with progress_lock:
            done += 1
            await _emit_progress(f"Tạo giọng {done}/{total} đoạn")

    await asyncio.gather(*[_process_segment(i, s) for i, s in enumerate(segments)])

    if failures and failures == total:
        raise EngineError(ErrorCode.TTS_FAILED, "Tất cả đoạn TTS đều thất bại")
    return paths


async def list_vi_voices() -> list[dict]:
    import edge_tts

    voices = await edge_tts.list_voices()
    return [v for v in voices if str(v.get("Locale", "")).startswith("vi-")]
