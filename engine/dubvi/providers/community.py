"""Community providers: deep-translator + edge-tts (no API keys)."""

from __future__ import annotations

from pathlib import Path

from .base import TtsProvider, TranslateProvider


class GoogleDeepTranslator(TranslateProvider):
    name = "deep-translator"
    requires_internet = True
    requires_api_key = False

    def translate(self, text: str, *, source: str, target: str) -> str:
        from deep_translator import GoogleTranslator

        src = "auto" if source in ("", "auto") else source
        return GoogleTranslator(source=src, target=target).translate(text) or text


class EdgeTtsProvider(TtsProvider):
    name = "edge-tts"
    requires_internet = True
    requires_api_key = False

    async def synthesize(
        self,
        text: str,
        out_path: Path,
        *,
        voice: str,
        rate: str = "+0%",
    ) -> None:
        import edge_tts

        out_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(str(out_path))
