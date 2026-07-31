from dubvi.providers import get_translate_provider, get_tts_provider


def test_community_providers():
    t = get_translate_provider("deep-translator")
    assert t.requires_internet
    assert not t.requires_api_key
    assert (
        "upload" in t.privacy_note().lower()
        or "Upload" in t.privacy_note()
        or "không" in t.privacy_note().lower()
    )

    tts = get_tts_provider("edge-tts")
    assert tts.requires_internet


def test_offline_provider_registry():
    t = get_translate_provider("nllb")
    assert t.name == "nllb"
    assert not t.requires_internet
    assert "máy" in t.privacy_note().lower() or "local" in t.privacy_note().lower()

    tts = get_tts_provider("xtts-v2")
    assert tts.name == "xtts-v2"
    assert not tts.requires_internet
    assert not tts.requires_api_key


def test_unknown_provider_raises():
    try:
        get_translate_provider("nope")
        assert False, "expected ValueError"
    except ValueError:
        pass
    try:
        get_tts_provider("nope")
        assert False, "expected ValueError"
    except ValueError:
        pass
