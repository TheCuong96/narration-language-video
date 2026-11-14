"""Community providers: deep-translator + edge-tts (no API keys)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import threading
import time

from .base import TtsProvider, TranslateProvider


class GoogleRateLimiter:
    def __init__(self, rate=4, *, clock=time.monotonic, sleep=time.sleep):
        self.interval = 1.0 / rate
        self.clock = clock
        self.sleep = sleep
        self.lock = threading.Lock()
        self.next_request = 0.0

    def acquire(self):
        with self.lock:
            delay = self.next_request - self.clock()
            if delay > 0:
                self.sleep(delay)
            self.next_request = self.clock() + self.interval

    def cooldown(self, seconds):
        with self.lock:
            self.next_request = max(self.next_request, self.clock() + seconds)


def is_rate_limit(error):
    return any(term in str(error).lower() for term in
               ("too many requests", "429", "rate limit", "wait and try again later"))


GOOGLE_LIMITER = GoogleRateLimiter()


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

    supports_batch = True
    handles_batch_errors = True

    def translate(self, text: str, *, source: str, target: str) -> str:
        from deep_translator import GoogleTranslator
        from ..models import ErrorCode
        from ..system_info import EngineError

        if not text.strip():
            return text
        src = "auto" if source in ("", "auto") else source
        # All Google requests, including retries, share one process-wide gate.
        for attempt in range(5):
            GOOGLE_LIMITER.acquire()
            try:
                result = GoogleTranslator(source=src, target=target).translate(text)
                if self._usable(result):
                    return str(result)
                raise RuntimeError("unusable translation")
            except Exception as exc:
                if is_rate_limit(exc) and attempt < 4:
                    GOOGLE_LIMITER.cooldown(2 ** (attempt + 1))
                    continue
                raise EngineError(ErrorCode.TRANSLATE_FAILED,
                                  "Google giới hạn request; hãy thử lại sau hoặc chọn dịch local."
                                  if is_rate_limit(exc) else "Google không trả được bản dịch hợp lệ.") from exc
        raise EngineError(ErrorCode.TRANSLATE_FAILED, "Google dịch thất bại.")

    def translate_batch(self, texts: list[str], *, source: str, target: str) -> list[str]:
        # deep-translator.translate_batch itself loops translate(); using that
        # implementation would bypass our limiter and replay successful items.
        # Commit each success exactly once through the guarded translate method.
        from .. import events
        from ..system_info import EngineError
        out = []
        for index, text in enumerate(texts):
            try:
                out.append(self.translate(text, source=source, target=target))
            except EngineError:
                events.warning("GOOGLE_SEGMENT_FAILED", f"Google không dịch được đoạn trong batch {index + 1}; giữ văn bản gốc.")
                out.append(text)
        return out


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
