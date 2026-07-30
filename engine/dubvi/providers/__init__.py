"""Translation / TTS provider registry (Community defaults; paid stubs later)."""

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


def get_translate_provider(name: str = "deep-translator") -> TranslateProvider:
    if name in ("deep-translator", "community", "google-free"):
        return GoogleDeepTranslator()
    # Future: google-cloud, azure — require API keys; not in v0.1
    raise ValueError(f"Translate provider chưa hỗ trợ trong Community: {name}")


def get_tts_provider(name: str = "edge-tts") -> TtsProvider:
    if name in ("edge-tts", "community"):
        return EdgeTtsProvider()
    raise ValueError(f"TTS provider chưa hỗ trợ trong Community: {name}")
