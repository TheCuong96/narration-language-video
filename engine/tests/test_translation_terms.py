from __future__ import annotations

from dubvi.providers.community import GoogleDeepTranslator
from dubvi.translation import clean_vi, protect_terms, restore_terms


def test_protect_and_restore_tech_terms():
    text = "We use Next.js with MongoDB and Zod"
    protected, mapping = protect_terms(text, ["Next.js", "MongoDB", "Zod"])
    assert "Next.js" not in protected
    assert "{{T" in protected
    # Simulate translator leaving tokens
    restored = restore_terms(protected, mapping)
    assert "Next.js" in restored
    assert "MongoDB" in restored


def test_protect_tokens_avoid_xterm_style():
    """Legacy XTERM#X placeholders break GoogleTranslate(source=en)."""
    text = "Talking about SSG, ISR, and SSR plenty of times."
    protected, mapping = protect_terms(text, ["SSR"])
    assert "XTERM" not in protected
    assert "{{T0}}" in protected
    assert restore_terms(protected, mapping) == text


def test_google_deep_translator_handles_protected_ssr():
    text = "You might have heard me talking about SSG, ISR, and SSR plenty of times in my courses."
    protected, mapping = protect_terms(text, ["SSR"])
    vi = GoogleDeepTranslator().translate(protected, source="en", target="vi")
    restored = restore_terms(vi, mapping)
    assert "SSR" in restored
    assert "XTERM" not in restored


def test_clean_vi():
    assert clean_vi("  Xin chào  &  thế giới  ") == "Xin chào và thế giới"
