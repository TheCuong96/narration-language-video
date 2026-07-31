"""Translation / TTS provider registry (Community + offline local)."""

from __future__ import annotations

from pathlib import Path

from .base import TtsProvider, TranslateProvider
from .community import EdgeTtsProvider, GoogleDeepTranslator

__all__ = [
    "TranslateProvider",
    "TtsProvider",
    "GoogleDeepTranslator",
    "EdgeTtsProvider",
    "get_translate_provider",
    "get_tts_provider",
]


def get_translate_provider(
    name: str = "deep-translator",
    *,
    prefer_gpu: bool = False,
) -> TranslateProvider:
    key = (name or "deep-translator").strip().lower()
    if key in ("deep-translator", "community", "google-free"):
        return GoogleDeepTranslator()
    if key in ("nllb", "nllb-offline", "offline-translate"):
        from .offline import NllbTranslateProvider

        return NllbTranslateProvider(prefer_gpu=prefer_gpu)
    raise ValueError(f"Translate provider chưa hỗ trợ: {name}")


def get_tts_provider(
    name: str = "edge-tts",
    *,
    prefer_gpu: bool = False,
    speaker_wav: str | Path | None = None,
    language: str = "vi",
) -> TtsProvider:
    key = (name or "edge-tts").strip().lower()
    if key in ("edge-tts", "community"):
        return EdgeTtsProvider()
    if key in ("xtts-v2", "xtts", "vixtts", "offline-tts"):
        from .offline import XttsTtsProvider

        return XttsTtsProvider(
            prefer_gpu=prefer_gpu,
            speaker_wav=speaker_wav,
            language=language,
        )
    raise ValueError(f"TTS provider chưa hỗ trợ: {name}")
