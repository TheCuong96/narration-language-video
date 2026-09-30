"""TranslateGemma's documented single-user prompt over local Ollama HTTP."""
from __future__ import annotations

import re
import threading
_CHAT_LOCK = threading.RLock()
import unicodedata

from .. import ollama_manager as manager
from ..models import ErrorCode
from ..system_info import EngineError
from .base import TranslateProvider

LANGUAGES = {"en": "English", "vi": "Vietnamese", "zh": "Chinese", "ja": "Japanese",
             "ko": "Korean", "fr": "French", "de": "German", "es": "Spanish",
             "th": "Thai", "id": "Indonesian"}
PROMPT_VERSION = "translategemma-markers-v1"


def language(code: str) -> tuple[str, str]:
    code = (code or "auto").strip()
    if code.lower() == "vi-vn":
        code = "vi"
    return LANGUAGES.get(code.lower(), code), code


def build_prompt(text: str, source: str, target: str, *, batch: bool = False) -> str:
    src, sc = language(source)
    tgt, tc = language(target)
    instructions = (" Preserve every [[DUBVI_SEG_000001]] marker exactly; return one translation "
                    "per marker in the same order. Do not remove, duplicate or reorder markers, "
                    "and do not add explanations. Preserve {{T0}} protected-term tokens." if batch
                    else "")
    return (f"You are a professional {src} ({sc}) to {tgt} ({tc}) translator. Your goal is to "
            f"accurately convey the meaning and nuances of the original {src} text while adhering "
            f"to {tgt} grammar, vocabulary, and cultural sensitivities.{instructions}\n"
            f"Produce only the {tgt} translation, without any additional explanations or commentary. "
            f"Please translate the following {src} text into {tgt}:\n\n\n{text}")


def clean_output(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[^\n]*\n", "", text)
    text = re.sub(r"\n?```$", "", text).strip()
    return re.sub(r"^(?:Translation|Vietnamese translation|Bản dịch)\s*:\s*", "", text,
                  flags=re.IGNORECASE).strip()


class TranslateGemmaProvider(TranslateProvider):
    requires_internet = False
    requires_api_key = False
    supports_batch = True
    prompt_version = PROMPT_VERSION
    handles_batch_errors = True

    def __init__(self, model="translategemma:4b", base_url=manager.BASE_URL,
                 connect_timeout=4, read_timeout=300, keep_alive="30m"):
        self.model = self.name = manager.normalize_model(model)
        self.base_url = manager.normalize_base_url(base_url)
        self.timeout = (connect_timeout, read_timeout)
        self.keep_alive = keep_alive

    def privacy_note(self) -> str:
        return "TranslateGemma dịch qua localhost; transcript không rời máy. Chỉ lần tải model cần Internet."

    def _chat(self, prompt: str) -> str:
        with _CHAT_LOCK:
            return self._chat_locked(prompt)

    def _chat_locked(self, prompt: str) -> str:
        if not manager.is_model_installed(self.model, self.base_url):
            raise EngineError(ErrorCode.TRANSLATE_FAILED,
                              f"Model {self.model} chưa tải. Vào Settings → Tải model Ollama.")
        data = manager.json_response(manager.request("POST", "/api/chat", base_url=self.base_url,
            timeout=self.timeout, json={"model": self.model, "messages": [{"role": "user", "content": prompt}],
                "stream": False, "keep_alive": self.keep_alive, "options": {"temperature": 0}}))
        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not clean_output(content):
            raise EngineError(ErrorCode.TRANSLATE_FAILED, "Ollama trả bản dịch rỗng hoặc thiếu message.content.")
        return clean_output(content)

    def translate(self, text: str, *, source: str, target: str) -> str:
        normalized = unicodedata.normalize("NFC", text).strip()
        if not normalized:
            return text
        return self._chat(build_prompt(normalized, source, target))

    def translate_batch(self, texts: list[str], *, source: str, target: str) -> list[str]:
        if not texts:
            return []
        if len(texts) > 32 or sum(len(t) for t in texts) > 16000:
            if len(texts) == 1:
                return [self.translate(texts[0], source=source, target=target)]
            mid = len(texts) // 2
            return (self.translate_batch(texts[:mid], source=source, target=target)
                    + self.translate_batch(texts[mid:], source=source, target=target))
        markers = [f"[[DUBVI_SEG_{i + 1:06d}]]" for i in range(len(texts))]
        text = "\n".join(f"{m}\n{t.strip()}" for m, t in zip(markers, texts))
        output = self._chat(build_prompt(text, source, target, batch=True))
        matches = list(re.finditer(r"\[\[DUBVI_SEG_\d+\]\]", output))
        parsed = [output[m.end():matches[i + 1].start() if i + 1 < len(matches)
                         else len(output)].strip() for i, m in enumerate(matches)]
        if ([m.group() for m in matches] == markers and all(parsed)
                and not output[:matches[0].start()].strip()):
            return parsed
        if len(texts) == 1:
            return [self.translate(texts[0], source=source, target=target)]
        mid = len(texts) // 2
        return (self.translate_batch(texts[:mid], source=source, target=target)
                + self.translate_batch(texts[mid:], source=source, target=target))
