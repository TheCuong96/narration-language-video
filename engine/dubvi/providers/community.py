"""Community providers: deep-translator + edge-tts (no API keys)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .base import TtsProvider, TranslateProvider


class GoogleDeepTranslator(TranslateProvider):
    name = "deep-translator"
    requires_internet = True
    requires_api_key = False

    @staticmethod
    def _usable(result: str | None) -> bool:
        if not result or not str(result).strip():
            return False
        low = str(result).lower()
        # Google free endpoint sometimes returns an HTML/error body as "translation".
        poison = (
            "no translation was found",
            "error 500",
            "server error",
            "that’s an error",
            "that's an error",
            "<html",
            "try again later",
        )
        return not any(p in low for p in poison)

    def translate(self, text: str, *, source: str, target: str) -> str:
        from deep_translator import GoogleTranslator, MyMemoryTranslator

        src = "auto" if source in ("", "auto") else source
        errors: list[Exception] = []

        candidates: list[tuple[str, Callable[[], str | None]]] = [
            (f"google:{src}", lambda: GoogleTranslator(source=src, target=target).translate(text)),
        ]
        if src != "auto":
            candidates.append(
                (
                    "google:auto",
                    lambda: GoogleTranslator(source="auto", target=target).translate(text),
                )
            )

        # MyMemory uses locale-style codes; keep as last resort (length limits).
        if len(text) <= 450:
            mm_src = "en-GB" if src in ("en", "auto", "") else src
            mm_tgt = "vi-VN" if target.lower() in ("vi", "vi-vn") else target
            candidates.append(
                (
                    "mymemory",
                    lambda: MyMemoryTranslator(source=mm_src, target=mm_tgt).translate(text),
                )
            )

        for _label, fn in candidates:
            try:
                result = fn()
                if self._usable(result):
                    return str(result)
                errors.append(RuntimeError(f"unusable translation: {result!r}"[:200]))
            except Exception as e:  # noqa: BLE001 — try next backend
                errors.append(e)
                continue

        if errors:
            raise errors[0]
        return text


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
