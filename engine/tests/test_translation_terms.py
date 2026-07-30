from __future__ import annotations

from dubvi.translation import clean_vi, protect_terms, restore_terms


def test_protect_and_restore_tech_terms():
    text = "We use Next.js with MongoDB and Zod"
    protected, mapping = protect_terms(text, ["Next.js", "MongoDB", "Zod"])
    assert "Next.js" not in protected
    assert "XTERM" in protected
    # Simulate translator leaving tokens
    restored = restore_terms(protected, mapping)
    assert "Next.js" in restored
    assert "MongoDB" in restored


def test_clean_vi():
    assert clean_vi("  Xin chào  &  thế giới  ") == "Xin chào và thế giới"
