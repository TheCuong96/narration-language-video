"""Batched local-model translation (NLLB) — the main local-speed lever."""

from __future__ import annotations

import dubvi.providers as providers_module
from dubvi.models import Segment
from dubvi.providers.base import TranslateProvider
from dubvi.translation import (
    _translate_batch_with_backoff,
    default_translate_concurrency,
    translate_segments,
)


class FakeBatchProvider(TranslateProvider):
    """Stands in for NllbTranslateProvider without loading torch/transformers."""

    name = "nllb"
    requires_internet = False
    requires_api_key = False
    supports_batch = True

    def __init__(self, *, fail_min_size: int | None = None):
        self.batch_calls: list[list[str]] = []
        self._fail_min_size = fail_min_size

    def translate(self, text: str, *, source: str, target: str) -> str:
        return self.translate_batch([text], source=source, target=target)[0]

    def translate_batch(self, texts: list[str], *, source: str, target: str) -> list[str]:
        self.batch_calls.append(list(texts))
        if self._fail_min_size is not None and len(texts) >= self._fail_min_size:
            raise RuntimeError("simulated OOM")
        return [f"vi:{t}" for t in texts]

    def privacy_note(self) -> str:
        return "chạy trên máy"


def _make_segments(n: int) -> list[Segment]:
    return [
        Segment(id=i, start=float(i), end=float(i + 1), text_en=f"hello {i}")
        for i in range(n)
    ]


def test_default_translate_concurrency_batches_nllb():
    assert default_translate_concurrency("nllb") == 8
    assert default_translate_concurrency("nllb", prefer_gpu=True) == 16
    assert default_translate_concurrency("deep-translator") >= 2


def test_translate_segments_batches_local_provider(tmp_path, monkeypatch):
    fake = FakeBatchProvider()
    monkeypatch.setattr(
        providers_module, "get_translate_provider", lambda name, prefer_gpu=False: fake
    )

    segments = _make_segments(5)
    out = translate_segments(
        segments,
        tmp_path / "vi.json",
        source_lang="en",
        target_lang="vi",
        terms=[],
        provider_name="nllb",
        concurrency=2,
    )

    assert [s.id for s in out] == list(range(5))
    assert all(s.text_vi == f"vi:hello {s.id}" for s in out)
    # Grouped into batches of at most 2 (concurrency=2), covering all 5 segments.
    assert all(len(c) <= 2 for c in fake.batch_calls)
    assert sum(len(c) for c in fake.batch_calls) == 5


def test_translate_batch_with_backoff_halves_on_repeated_failure():
    fake = FakeBatchProvider(fail_min_size=3)
    texts = ["a", "b", "c", "d"]

    out = _translate_batch_with_backoff(
        fake, texts, source="en", target="vi", max_attempts=1, base_delay=0.01
    )

    assert out == ["vi:a", "vi:b", "vi:c", "vi:d"]
    # Size-4 batch always fails at fail_min_size=3 → halves into 2+2, which succeed.
    assert [len(c) for c in fake.batch_calls] == [4, 2, 2]
