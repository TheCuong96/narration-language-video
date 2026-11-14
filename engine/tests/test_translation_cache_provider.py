from unittest.mock import Mock

import pytest

from dubvi import cache, translation
from dubvi.models import Segment


@pytest.fixture
def provider(monkeypatch):
    from dubvi import providers
    fake = Mock(name="translator", requires_internet=False, supports_batch=True)
    fake.name = "nllb"
    fake.privacy_note.return_value = "Local"
    fake.translate_batch.side_effect = lambda texts, **kw: ["vi:" + t for t in texts]
    monkeypatch.setattr(providers, "get_translate_provider", lambda *a, **kw: fake)
    return fake


def run(path, name="nllb", texts=None, terms=None):
    segments = [Segment(id=i, start=i, end=i+1, text_en=t) for i, t in enumerate(texts or ["Hello Plaid", "World"])]
    return translation.translate_segments(segments, path, source_lang="en", target_lang="vi",
                                          terms=terms or [], provider_name=name, concurrency=2)


def test_same_provider_reuse(tmp_path, provider):
    path = tmp_path / "transcript_vi.json"
    run(path)
    provider.translate_batch.reset_mock()
    run(path)
    provider.translate_batch.assert_not_called()


def test_provider_switch_invalidates(tmp_path, provider):
    path = tmp_path / "transcript_vi.json"
    for name in ["deep-translator", "nllb", "translategemma:4b", "translategemma:12b"]:
        provider.translate_batch.reset_mock()
        run(path, name)
        provider.translate_batch.assert_called_once()


def test_text_and_terms_invalidates(tmp_path, provider):
    path = tmp_path / "transcript_vi.json"
    run(path)
    provider.translate_batch.reset_mock()
    run(path, terms=["Plaid"])
    provider.translate_batch.assert_called_once()
    provider.translate_batch.reset_mock()
    run(path, texts=["Changed", "World"], terms=["Plaid"])
    provider.translate_batch.assert_called_once()


def test_protected_terms_and_identity(tmp_path, provider):
    out = run(tmp_path / "vi.json", terms=["Plaid"])
    assert out[0].text_vi == "vi:Hello Plaid"
    assert [(s.id, s.start, s.end) for s in out] == [(0, 0, 1), (1, 1, 2)]


def test_legacy_cache_not_reused(tmp_path, provider):
    path = tmp_path / "transcript_vi.json"
    en = tmp_path / cache.TRANSCRIPT_EN
    cache.save_json(en, [])
    cache.save_segments(path, [Segment(id=0, start=0, end=1, text_en="Hello", text_vi="old")])
    run(path)
    provider.translate_batch.assert_called()
    assert en.exists()


def test_partial_cache_reuses_only_successes(tmp_path, provider):
    path = tmp_path / "transcript_vi.json"
    run(path)
    segments = cache.load_segments(path)
    segments[1].text_vi = ""
    cache.save_segments(path, segments)
    provider.translate_batch.reset_mock()
    run(path)
    assert provider.translate_batch.call_args.args[0] == ["World"]


def test_interrupted_write_does_not_reuse_previous_stamp(tmp_path, monkeypatch):
    path = tmp_path / "vi.json"
    cache.save_json(cache.translation_metadata_path(path), {"translation_fingerprint": "old"})
    def crash(*args):
        raise OSError("interrupted")
    monkeypatch.setattr(cache, "save_segments", crash)
    with pytest.raises(OSError):
        cache.save_translation_segments(path, [], "new")
    assert cache.load_json(cache.translation_metadata_path(path)) == {}


def test_pipeline_shortcut_checks_provider(tmp_path, provider):
    from dubvi.pipeline import _vi_cache_matches
    from dubvi.models import JobConfig
    segments = [Segment(id=0, start=0, end=1, text_en="Hello")]
    cache.save_segments(tmp_path / cache.TRANSCRIPT_EN, segments)
    translation.translate_segments(segments, tmp_path / cache.TRANSCRIPT_VI,
        source_lang="en", target_lang="vi", terms=[], provider_name="nllb")
    cfg = JobConfig(output_dir=tmp_path, job_id="cache-test", translate_provider="nllb")
    # JobConfig includes default protected terms; use the same fingerprint inputs.
    fingerprint = translation.translation_fingerprint(segments, source_lang="en", target_lang="vi",
                                                     terms=cfg.terms, provider_name="nllb")
    cache.save_translation_segments(tmp_path / cache.TRANSCRIPT_VI,
                                    cache.load_segments(tmp_path / cache.TRANSCRIPT_VI), fingerprint)
    assert _vi_cache_matches(tmp_path, cfg)
    cfg.translate_provider = "translategemma:4b"
    assert not _vi_cache_matches(tmp_path, cfg)


def test_review_keeps_provider_stamp(tmp_path, provider, monkeypatch):
    from dubvi import review
    segments = [Segment(id=0, start=0, end=1, text_en="Hello", text_vi="Xin chào")]
    cache.save_segments(tmp_path / cache.TRANSCRIPT_EN, segments)
    fingerprint = translation.translation_fingerprint(segments, source_lang="en", target_lang="vi",
                                                     terms=[], provider_name="translategemma:4b")
    cache.save_translation_segments(tmp_path / cache.TRANSCRIPT_VI, segments, fingerprint)
    monkeypatch.setattr(review, "work_for_stem", lambda *a: tmp_path)
    review.save_translation("job", "video", [{**segments[0].to_dict(), "text_vi": "Chào bạn"}])
    assert translation.cache_matches(tmp_path / cache.TRANSCRIPT_VI, segments,
        source_lang="en", target_lang="vi", terms=[], provider_name="translategemma:4b")
    assert cache.load_segments(tmp_path / cache.TRANSCRIPT_VI)[0].text_vi == "Chào bạn"
