"""TTS Vietnamese voice with exponential backoff (edge-tts or local XTTS)."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path

from . import events
from .jobs import CancellationToken
from .models import ErrorCode, Segment, Stage
from .system_info import EngineError, get_logger

log = get_logger("dubvi.tts")

MIN_MP3_BYTES = 500
# edge-tts: one HTTP/WebSocket request per segment — parallelism = main speed lever.
MIN_ADAPTIVE_CONCURRENCY = 4
DEFAULT_ADAPTIVE_INITIAL = 16
MAX_ADAPTIVE_CONCURRENCY = 96
# Seconds of in-flight TTS work we aim to keep on the wire (AIMD scales toward this).
ADAPTIVE_PIPELINE_TARGET_SEC = 45.0
PROBE_PARALLEL = 6


def default_tts_concurrency(
    provider_name: str,
    *,
    prefer_gpu: bool = False,
) -> int:
    """Fixed fallback when adaptive mode is disabled."""
    name = (provider_name or "edge-tts").lower()
    if name.startswith("xtts"):
        return 1 if prefer_gpu else 2
    return DEFAULT_ADAPTIVE_INITIAL


def resolve_adaptive_max(
    provider_name: str,
    *,
    max_concurrency: int = 0,
    segment_count: int = 0,
) -> int:
    """Upper bound for adaptive edge-tts parallelism."""
    if (provider_name or "edge-tts").lower().startswith("xtts"):
        return 2
    cap = max_concurrency if max_concurrency > 0 else MAX_ADAPTIVE_CONCURRENCY
    cap = min(cap, MAX_ADAPTIVE_CONCURRENCY)
    if segment_count > 0:
        cap = min(cap, segment_count)
    return max(MIN_ADAPTIVE_CONCURRENCY, cap)


class AdaptiveTtsPool:
    """
    Dynamic in-flight limit (AIMD): ramp up on fast success, halve on errors.

    Unlike a fixed Semaphore(N), the limit grows until the network/provider
    pushes back, then backs off.
    """

    def __init__(self, *, initial: int, minimum: int, maximum: int):
        self._limit = max(minimum, min(initial, maximum))
        self._min = minimum
        self._max = maximum
        self._in_flight = 0
        self._success_streak = 0
        self._lock = asyncio.Lock()
        self._cond = asyncio.Condition(self._lock)
        self._last_logged = self._limit

    @property
    def limit(self) -> int:
        return self._limit

    async def acquire(self) -> None:
        async with self._cond:
            while self._in_flight >= self._limit:
                await self._cond.wait()
            self._in_flight += 1

    async def release(self, *, ok: bool, latency_sec: float) -> None:
        async with self._cond:
            self._in_flight = max(0, self._in_flight - 1)
            old = self._limit
            if ok:
                self._success_streak += 1
                fast = latency_sec < 2.0
                if fast and self._success_streak >= 3 and self._limit < self._max:
                    bump = max(2, self._limit // 3)
                    self._limit = min(self._max, self._limit + bump)
                    self._success_streak = 0
            else:
                self._success_streak = 0
                self._limit = max(self._min, self._limit // 2)

            if self._limit != self._last_logged and (
                self._limit != old or abs(self._limit - self._last_logged) >= 4
            ):
                self._last_logged = self._limit
                events.log(f"TTS tự điều chỉnh: {self._limit} request song song (max {self._max})")
            self._cond.notify_all()


async def _tts_once(
    text: str,
    out_mp3: Path,
    voice: str,
    rate: str,
    *,
    provider,
) -> None:
    await provider.synthesize(text, out_mp3, voice=voice, rate=rate)


async def probe_edge_tts_throughput(
    voice: str,
    provider,
    *,
    max_cap: int,
) -> tuple[int, float]:
    """
    Fire several tiny TTS requests in parallel and infer a starting concurrency
    from measured latency (faster network → higher initial limit).
    """
    latencies: list[float] = []

    async def _one_probe(idx: int) -> None:
        tmp = Path(tempfile.gettempdir()) / f"dubvi_tts_probe_{os.getpid()}_{idx}.mp3"
        t0 = time.perf_counter()
        try:
            await _tts_once("Kiểm tra tốc độ.", tmp, voice, "+0%", provider=provider)
            if tmp.exists() and tmp.stat().st_size >= MIN_MP3_BYTES:
                latencies.append(time.perf_counter() - t0)
        except Exception as e:
            log.debug("TTS probe %s failed: %s", idx, e)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    await asyncio.gather(*[_one_probe(i) for i in range(PROBE_PARALLEL)], return_exceptions=True)

    if not latencies:
        return MIN_ADAPTIVE_CONCURRENCY, 3.0

    avg = sum(latencies) / len(latencies)
    # Keep ~ADAPTIVE_PIPELINE_TARGET_SEC of work in flight at steady state.
    suggested = int(ADAPTIVE_PIPELINE_TARGET_SEC / max(avg, 0.2))
    suggested = max(MIN_ADAPTIVE_CONCURRENCY, min(max_cap, suggested))
    return suggested, avg


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
    rates = ["+0%", "+5%", "+10%", "+0%", "+15%"]
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
    max_concurrency: int = 0,
) -> dict[int, Path]:
    """Generate MP3 per segment in parallel; skip existing valid files (resume)."""
    if tracker:
        tracker.begin_stage(Stage.TTS, "Đang chuẩn bị bộ tạo giọng đọc…")

    from .providers import get_tts_provider

    provider = get_tts_provider(
        provider_name,
        prefer_gpu=prefer_gpu,
        speaker_wav=speaker_wav or None,
        language=language,
    )
    is_online = getattr(provider, "requires_internet", True)
    is_edge = not (provider_name or "edge-tts").lower().startswith("xtts")
    seg_total = max(len(segments), 1)
    max_cap = resolve_adaptive_max(
        provider_name,
        max_concurrency=max_concurrency,
        segment_count=seg_total,
    )

    adaptive = concurrency <= 0 and is_edge and is_online
    pool: AdaptiveTtsPool | None = None
    sem: asyncio.Semaphore | None = None

    if adaptive:
        initial, avg_lat = await probe_edge_tts_throughput(voice, provider, max_cap=max_cap)
        pool = AdaptiveTtsPool(
            initial=initial,
            minimum=MIN_ADAPTIVE_CONCURRENCY,
            maximum=max_cap,
        )
        workers_label = f"tự điều chỉnh {initial}→{max_cap} (mạng ~{avg_lat:.1f}s/request)"
    else:
        workers = concurrency if concurrency > 0 else default_tts_concurrency(
            provider_name, prefer_gpu=prefer_gpu
        )
        workers = max(1, min(workers, seg_total, max_cap if is_edge else workers))
        sem = asyncio.Semaphore(workers)
        workers_label = str(workers)

    seg_dir.mkdir(parents=True, exist_ok=True)
    label = f"Đang tạo giọng đọc ({len(segments)} đoạn, {workers_label}) [{provider.name}]"
    if tracker:
        tracker.begin_stage(Stage.TTS, label)
    else:
        events.stage(Stage.TTS, label)
    events.log(provider.privacy_note())
    if adaptive:
        events.log(
            f"TTS thích ứng mạng: bắt đầu {pool.limit} request song song, "
            f"tối đa {max_cap} — tự tăng/giảm theo tốc độ Internet"
        )
    elif int(workers_label) > 1:
        events.log(f"TTS song song cố định: {workers_label} request cùng lúc")

    paths: dict[int, Path] = {}
    total = seg_total
    failures = 0
    done = 0
    progress_lock = asyncio.Lock()

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

        ok = False
        latency = 0.0
        if pool is not None:
            await pool.acquire()
        else:
            assert sem is not None
            await sem.acquire()
        try:
            if cancel:
                cancel.check()
            t0 = time.perf_counter()
            try:
                await tts_segment_with_backoff(
                    text, mp3, voice=voice, provider=provider
                )
                latency = time.perf_counter() - t0
                ok = True
                async with progress_lock:
                    paths[s.id] = mp3
            except EngineError as e:
                latency = time.perf_counter() - t0
                async with progress_lock:
                    failures += 1
                events.error(e.code, f"Đoạn {s.id}: {e.message}", fatal=False)
                log.error("TTS give up seg %s: %s", s.id, e)
        finally:
            if pool is not None:
                await pool.release(ok=ok, latency_sec=latency)
            else:
                sem.release()

        async with progress_lock:
            done += 1
            cur = pool.limit if pool else int(workers_label)
            await _emit_progress(f"Tạo giọng {done}/{total} · {cur} song song")

    await asyncio.gather(*[_process_segment(i, s) for i, s in enumerate(segments)])

    if failures and failures == total:
        raise EngineError(ErrorCode.TTS_FAILED, "Tất cả đoạn TTS đều thất bại")
    if pool is not None:
        events.log(f"TTS xong · mức song song cuối: {pool.limit}/{max_cap}")
    return paths


async def list_vi_voices() -> list[dict]:
    import edge_tts

    voices = await edge_tts.list_voices()
    return [v for v in voices if str(v.get("Locale", "")).startswith("vi-")]
