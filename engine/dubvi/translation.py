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
    """Pick safe default parallelism (threads) or batch size (local models)."""
    name = (provider_name or "deep-translator").lower()
    if name.startswith("nllb") or "offline" in name:
        # Batched model.generate() call, not threads — GPU handles bigger batches.
        return 16 if prefer_gpu else 8
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


def _translate_batch_with_backoff(
    provider,
    texts: list[str],
    *,
    source: str,
    target: str,
    max_attempts: int = 2,
    base_delay: float = 0.5,
) -> list[str]:
    """Batch-translate with retry; halves the batch and retries on failure

    (e.g. transient CUDA OOM on a long segment) instead of failing every
    segment in the batch.
    """
    if not texts:
        return []
    last_err: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return provider.translate_batch(texts, source=source, target=target)
        except EngineError:
            raise
        except Exception as e:
            last_err = e
            delay = base_delay * (2**attempt)
            log.warning(
                "batch translate (%d đoạn) lần %s lỗi: %s; sleep %.1fs",
                len(texts),
                attempt + 1,
                e,
                delay,
            )
            time.sleep(delay)
    if len(texts) == 1:
        raise EngineError(
            ErrorCode.TRANSLATE_FAILED,
            f"Dịch thất bại sau {max_attempts} lần: {last_err}",
        )
    mid = len(texts) // 2
    log.warning(
        "Chia nhỏ batch dịch (%d → %d + %d) sau lỗi: %s",
        len(texts),
        mid,
        len(texts) - mid,
        last_err,
    )
    left = _translate_batch_with_backoff(provider, texts[:mid], source=source, target=target)
    right = _translate_batch_with_backoff(provider, texts[mid:], source=source, target=target)
    return left + right


def _translate_batch_segments(
    batch: list[Segment],
    *,
    translator,
    src: str,
    target_lang: str,
    terms: list[str],
) -> list[Segment]:
    """Translate several segments in one model call; falls back per-segment on failure."""
    protected_texts: list[str] = []
    mappings: list[dict[str, str]] = []
    for s in batch:
        protected, mapping = protect_terms(s.text_en, terms)
        protected_texts.append(protected)
        mappings.append(mapping)

    try:
        outputs = _translate_batch_with_backoff(
            translator, protected_texts, source=src, target=target_lang
        )
    except Exception as e:
        log.warning("batch translate thất bại (%d đoạn), dịch từng đoạn: %s", len(batch), e)
        return [
            _translate_one_segment(
                s, translator=translator, src=src, target_lang=target_lang, terms=terms
            )
            for s in batch
        ]

    result: list[Segment] = []
    for s, mapping, out in zip(batch, mappings, outputs):
        vi = restore_terms(out or s.text_en, mapping)
        result.append(
            Segment(
                id=s.id,
                start=s.start,
                end=s.end,
                text_en=s.text_en,
                text_vi=clean_vi(vi),
            )
        )
    return result


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

    if tracker:
        tracker.begin_stage(Stage.TRANSLATING, "Đang chuẩn bị bộ dịch…")

    from .providers import get_translate_provider

    src = "auto" if source_lang in ("", "auto") else source_lang
    translator = get_translate_provider(provider_name, prefer_gpu=prefer_gpu)
    workers = concurrency if concurrency > 0 else default_translate_concurrency(
        provider_name, prefer_gpu=prefer_gpu
    )
    workers = max(1, min(workers, max(len(segments), 1)))
    # Local models (NLLB) translate a whole batch in one model call instead of
    # one thread per segment — much faster than either serial or thread-pool.
    use_batch = getattr(translator, "supports_batch", False) and not translator.requires_internet
    mode_label = f"lô {workers} đoạn" if use_batch else f"{workers} luồng"

    if tracker:
        tracker.begin_stage(
            Stage.TRANSLATING,
            f"Đang dịch {len(segments)} đoạn ({src} → {target_lang}, {mode_label}) "
            f"[{translator.name}]",
        )
    else:
        events.stage(
            Stage.TRANSLATING,
            f"Đang dịch {len(segments)} đoạn ({src} → {target_lang}, {mode_label}) "
            f"[{translator.name}]",
        )
    events.log(translator.privacy_note())
    if use_batch:
        events.log(f"Dịch theo lô: {workers} đoạn/lượt (model chạy trên máy)")
    elif workers > 1:
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

    if pending and use_batch:
        for start in range(0, len(pending), workers):
            chunk = pending[start : start + workers]
            if cancel:
                cancel.check()
            batch_segments = [s for _, s in chunk]
            for seg in _translate_batch_segments(
                batch_segments,
                translator=translator,
                src=src,
                target_lang=target_lang,
                terms=terms,
            ):
                translated[seg.id] = seg
                done += 1
            _emit_progress()
            _maybe_save_partial()
    elif pending and workers > 1:
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
