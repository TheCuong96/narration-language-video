"""Small explicit local-first fallback; online requires user opt-in."""
from .base import TranslateProvider
from .. import events, models_manager
from ..system_info import EngineError
from ..models import ErrorCode


class LocalFallbackProvider(TranslateProvider):
    supports_batch = True
    handles_batch_errors = True
    requires_internet = False

    def __init__(self, primary, *, prefer_gpu=False, online=False):
        self.primary = primary
        self.name = primary.name
        self.prefer_gpu = prefer_gpu
        self.online = online

    def privacy_note(self):
        return self.primary.privacy_note() + (" Fallback Google được bật khi dịch local lỗi." if self.online else "")

    @staticmethod
    def _reason(exc):
        return exc.message if isinstance(exc, EngineError) else type(exc).__name__

    def _alternatives(self):
        from . import get_translate_provider
        model, name = (("nllb-200-distilled-600M", "nllb")
                       if self.name.startswith("translategemma") else ("translategemma:4b", "translategemma:4b"))
        if models_manager.is_model_downloaded(model):
            yield get_translate_provider(name, prefer_gpu=self.prefer_gpu)
        if self.online:
            yield get_translate_provider("deep-translator")

    def translate(self, text, *, source, target):
        try:
            return self.primary.translate(text, source=source, target=target)
        except Exception as exc:
            for provider in self._alternatives():
                events.log(f"Fallback {self.name} → {provider.name}; đoạn đơn; lý do: {self._reason(exc)}", level="warn")
                try:
                    return provider.translate(text, source=source, target=target)
                except Exception:
                    continue
            raise EngineError(ErrorCode.TRANSLATE_FAILED, f"Dịch {self.name} thất bại: {self._reason(exc)}; không có provider fallback khả dụng.") from exc

    def translate_batch(self, texts, *, source, target):
        try:
            if getattr(self.primary, "supports_batch", False):
                out = self.primary.translate_batch(texts, source=source, target=target)
                if len(out) != len(texts) or any(not str(item).strip() for item in out):
                    raise ValueError("invalid batch")
                return out
        except Exception as exc:
            # Split failed local batches before using alternate providers.
            events.log(f"Batch {len(texts)} đoạn của {self.name} lỗi: {self._reason(exc)}; chia nhỏ", level="warn")
            if len(texts) > 1:
                mid = len(texts) // 2
                return (self.translate_batch(texts[:mid], source=source, target=target)
                        + self.translate_batch(texts[mid:], source=source, target=target))
        out = []
        for index, text in enumerate(texts):
            try:
                out.append(self.translate(text, source=source, target=target))
            except EngineError:
                events.warning("LOCAL_SEGMENT_FAILED", f"Đoạn {index + 1} trong batch dịch lỗi; giữ văn bản gốc.")
                out.append(text)
        return out
