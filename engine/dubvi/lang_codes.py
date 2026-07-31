"""Map ISO language codes ↔ NLLB / XTTS language tags."""

from __future__ import annotations

# Common ISO-639-1 → NLLB Flores codes
NLLB_LANG: dict[str, str] = {
    "en": "eng_Latn",
    "vi": "vie_Latn",
    "zh": "zho_Hans",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
    "fr": "fra_Latn",
    "de": "deu_Latn",
    "es": "spa_Latn",
    "pt": "por_Latn",
    "ru": "rus_Cyrl",
    "th": "tha_Thai",
    "id": "ind_Latn",
    "hi": "hin_Deva",
    "ar": "arb_Arab",
}

# Already-NLLB tags pass through
_NLLB_SET = set(NLLB_LANG.values())


def to_nllb_lang(code: str, *, default: str = "eng_Latn") -> str:
    raw = (code or "").strip()
    if not raw or raw.lower() == "auto":
        return default
    if raw in _NLLB_SET:
        return raw
    low = raw.lower().replace("-", "_")
    if low in NLLB_LANG:
        return NLLB_LANG[low]
    # eng_Latn style already
    if "_" in raw and len(raw) >= 6:
        return raw
    return NLLB_LANG.get(low[:2], default)


def to_xtts_lang(code: str, *, default: str = "vi") -> str:
    raw = (code or "").strip().lower()
    if not raw or raw == "auto":
        return default
    if "_" in raw:
        # vie_Latn → try iso
        prefix = raw.split("_", 1)[0]
        for iso, nllb in NLLB_LANG.items():
            if nllb.startswith(prefix):
                return iso
    return raw[:2] if len(raw) >= 2 else default
