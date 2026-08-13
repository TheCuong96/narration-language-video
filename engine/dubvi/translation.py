"""Segment translation EN → VI with term protection and exponential backoff."""

from __future__ import annotations

import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import cache, events
from .jobs import CancellationToken
from .models import ErrorCode, Segment, Stage
from .system_info import EngineError, get_logger

log = get_logger("dubvi.translation")


def default_translate_concurrency(provider_name: str, *, prefer_gpu: bool = False) -> int:
    """Pick safe default parallelism for the active translation backend."""
    name = (provider_name or "deep-translator").lower()
    if name.startswith("nllb") or "offline" in name:
        return 1
    return min(4, max(2, (os.cpu_count() or 4) // 2))


def protect_terms(text: str, terms: list[str]) -> tuple[str, dict[str, str]]:
    """Replace protected terms with placeholders Google Translate won't reject.

    Avoid tokens like ``XTERM13X`` — Google with ``source=en`` often returns
    \"No translation was found\" for those. ``{{T0}}`` style is stable.
    """
    mapping: dict[str, str] = {}
    out = text
    for i, term in enumerate(terms):
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        if pattern.search(out):
            token = f"{{{{T{i}}}}}"
            mapping[token] = term
            out = pattern.sub(token, out)
    return out, mapping


def restore_terms(text: str, mapping: dict[str, str]) -> str:
    out = text
    for token, term in mapping.items():
        out = re.sub(re.escape(token), term, out, flags=re.IGNORECASE)
        # Google sometimes strips one layer of braces: {T0} instead of {{T0}}
        loose = token.replace("{{", "{").replace("}}", "}")
        if loose != token:
            out = re.sub(re.escape(loose), term, out, flags=re.IGNORECASE)
    # Legacy placeholders from older builds / cached protected text
    for token, term in list(mapping.items()):
        m = re.fullmatch(r"\{\{T(\d+)\}\}", token)
        if m:
            legacy = f"XTERM{m.group(1)}X"
            out = re.sub(re.escape(legacy), term, out, flags=re.IGNORECASE)
    replacements = {
        r"\bPlayed\b": "Plaid",
        r"\bAppRide\b": "Appwrite",
        r"\bApp Ride\b": "Appwrite",
        r"\bZot\b": "Zod",
        r"\bShadZien\b": "shadcn",
    }
    for pat, rep in replacements.items():
        out = re.sub(pat, rep, out)
    return out


def clean_vi(text: str) -> str:
    text = text.strip().replace("&", " và ")
    return re.sub(r"\s+", " ", text)


def translate_with_backoff(
    provider,
    text: str,
    *,
    source: str,
    target: str,
    max_attempts: int = 3,
    base_delay: float = 0.8,
) -> str:
    last_err: Exception | None = None
    # Provider already tries multiple backends; keep outer retries short.
    attempts = max_attempts if getattr(provider, "requires_internet", True) else min(2, max_attempts)
    for attempt in range(attempts):
        try:
            return provider.translate(text, source=source, target=target)
        except EngineError:
            raise
        except Exception as e:
            last_err = e
            delay = base_delay * (2**attempt)
            log.warning("translate attempt %s failed: %s; sleep %.1fs", attempt + 1, e, delay)
            time.sleep(delay)
    raise EngineError(
        ErrorCode.TRANSLATE_FAILED,
        f"Dịch thất bại sau {attempts} lần: {last_err}",
    )


def _translate_one_segment(
    s: Segment,
    *,
    translator,
    src: str,
    target_lang: str,
    terms: list[str],
) -> Segment:
    protected, mapping = protect_terms(s.text_en, terms)
    try:
        vi = translate_with_backoff(translator, protected, source=src, target=target_lang)
        vi = restore_terms(vi or s.text_en, mapping)
    except Exception as e:
        log.warning("segment %s translate failed, keep EN: %s", s.id, e)
        events.log(
            f"Cảnh báo: không dịch được đoạn {s.id}, giữ tiếng Anh — {e}",
            level="warn",
        )
        vi = s.text_en
    return Segment(
        id=s.id,
        start=s.start,
        end=s.end,
        text_en=s.text_en,
        text_vi=clean_vi(vi),
    )


def translate_segments(
    segments: list[Segment],
    out_path: Path,
    *,
    source_lang: str,
    target_lang: str,
    terms: list[str],
    cancel: CancellationToken | None = None,
    tracker=None,
    provider_name: str = "deep-translator",
    prefer_gpu: bool = False,
    concurrency: int = 0,
) -> list[Segment]:
    cached = cache.load_segments(out_path)
    if cached is not None and len(cached) == len(segments) and all(s.text_vi for s in cached):
        events.log(f"Dùng cache bản dịch: {out_path.name}")
        if tracker:
            tracker.begin_stage(Stage.TRANSLATING, "Dùng cache bản dịch")
            tracker.emit(1, 1, "Đã có bản dịch trong cache")
        return cached

    from .providers import get_translate_provider

    src = "auto" if source_lang in ("", "auto") else source_lang
    translator = get_translate_provider(provider_name, prefer_gpu=prefer_gpu)
    workers = concurrency if concurrency > 0 else default_translate_concurrency(
        provider_name, prefer_gpu=prefer_gpu
    )
    workers = max(1, min(workers, max(len(segments), 1)))

    if tracker:
        tracker.begin_stage(
            Stage.TRANSLATING,
            f"Đang dịch {len(segments)} đoạn ({src} → {target_lang}, {workers} luồng) "
            f"[{translator.name}]",
        )
    else:
        events.stage(
            Stage.TRANSLATING,
            f"Đang dịch {len(segments)} đoạn ({src} → {target_lang}, {workers} luồng) "
            f"[{translator.name}]",
        )
    events.log(translator.privacy_note())
    if workers > 1:
        events.log(f"Dịch song song: {workers} đoạn cùng lúc")

    # Resume: reuse already-translated segments
    by_id: dict[int, Segment] = {}
    if cached:
        for s in cached:
            if s.text_vi:
                by_id[s.id] = s

    total = len(segments)
    pending: list[tuple[int, Segment]] = [
        (i, s) for i, s in enumerate(segments) if s.id not in by_id
    ]
    translated: dict[int, Segment] = dict(by_id)
    done = len(by_id)
    progress_lock = threading.Lock()

    def _emit_progress() -> None:
        msg = f"Đã dịch {done}/{total} đoạn"
        if tracker:
            tracker.emit(done, total, msg)
        else:
            events.progress(Stage.TRANSLATING, done, total, msg)

    def _maybe_save_partial() -> None:
        if done % 5 != 0 and done != total:
            return
        filled: list[Segment] = []
        for s in segments:
            if s.id in translated:
                filled.append(translated[s.id])
            elif s.id in by_id:
                filled.append(by_id[s.id])
            else:
                filled.append(s)
        cache.save_segments(out_path, filled)

    if pending and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _translate_one_segment,
                    s,
                    translator=translator,
                    src=src,
                    target_lang=target_lang,
                    terms=terms,
                ): (i, s)
                for i, s in pending
            }
            for fut in as_completed(futures):
                if cancel:
                    cancel.check()
                seg = fut.result()
                with progress_lock:
                    translated[seg.id] = seg
                    done += 1
                    _emit_progress()
                    _maybe_save_partial()
    else:
        throttle = 0.0
        if workers == 1 and translator.requires_internet:
            # Single-thread online path keeps a light throttle for stability.
            throttle = 0.05
        for i, s in enumerate(segments):
            if cancel:
                cancel.check()
            if s.id in by_id:
                continue
            seg = _translate_one_segment(
                s,
                translator=translator,
                src=src,
                target_lang=target_lang,
                terms=terms,
            )
            translated[seg.id] = seg
            done += 1
            _emit_progress()
            if throttle:
                time.sleep(throttle)
            _maybe_save_partial()

    result = [translated[s.id] for s in segments]
    cache.save_segments(out_path, result)
    return result
