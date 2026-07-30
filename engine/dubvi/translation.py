"""Segment translation EN → VI with term protection and exponential backoff."""

from __future__ import annotations

import re
import time
from pathlib import Path

from . import cache, events
from .jobs import CancellationToken
from .models import ErrorCode, Segment, Stage
from .system_info import EngineError, get_logger

log = get_logger("dubvi.translation")


def protect_terms(text: str, terms: list[str]) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}
    out = text
    for i, term in enumerate(terms):
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        if pattern.search(out):
            token = f"XTERM{i}X"
            mapping[token] = term
            out = pattern.sub(token, out)
    return out, mapping


def restore_terms(text: str, mapping: dict[str, str]) -> str:
    out = text
    for token, term in mapping.items():
        out = re.sub(re.escape(token), term, out, flags=re.IGNORECASE)
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
    max_attempts: int = 5,
    base_delay: float = 1.0,
) -> str:
    last_err: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return provider.translate(text, source=source, target=target)
        except Exception as e:
            last_err = e
            delay = base_delay * (2**attempt)
            log.warning("translate attempt %s failed: %s; sleep %.1fs", attempt + 1, e, delay)
            time.sleep(delay)
    raise EngineError(
        ErrorCode.TRANSLATE_FAILED,
        f"Dịch thất bại sau {max_attempts} lần: {last_err}",
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
    translator = get_translate_provider("deep-translator")
    if tracker:
        tracker.begin_stage(
            Stage.TRANSLATING,
            f"Đang dịch {len(segments)} đoạn ({src} → {target_lang})",
        )
    else:
        events.stage(Stage.TRANSLATING, f"Đang dịch {len(segments)} đoạn ({src} → {target_lang})")
    events.log(translator.privacy_note())

    # Resume: reuse already-translated segments
    by_id: dict[int, Segment] = {}
    if cached:
        for s in cached:
            if s.text_vi:
                by_id[s.id] = s

    result: list[Segment] = []
    total = len(segments)

    for i, s in enumerate(segments):
        if cancel:
            cancel.check()
        if s.id in by_id:
            result.append(by_id[s.id])
        else:
            protected, mapping = protect_terms(s.text_en, terms)
            try:
                vi = translate_with_backoff(
                    translator, protected, source=src, target=target_lang
                )
            except EngineError:
                raise
            except Exception as e:
                raise EngineError(ErrorCode.TRANSLATE_FAILED, str(e)) from e
            vi = restore_terms(vi or s.text_en, mapping)
            result.append(
                Segment(
                    id=s.id,
                    start=s.start,
                    end=s.end,
                    text_en=s.text_en,
                    text_vi=clean_vi(vi),
                )
            )
            time.sleep(0.25)

        if (i + 1) % 1 == 0 or i + 1 == total:
            msg = f"Đã dịch {i + 1}/{total} đoạn"
            if tracker:
                tracker.emit(i + 1, total, msg)
            else:
                events.progress(Stage.TRANSLATING, i + 1, total, msg)
            if (i + 1) % 5 == 0 or i + 1 == total:
                cache.save_segments(out_path, result)

    cache.save_segments(out_path, result)
    return result
