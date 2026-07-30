from dubvi.providers import get_translate_provider, get_tts_provider


def test_community_providers():
    t = get_translate_provider("deep-translator")
    assert t.requires_internet
    assert not t.requires_api_key
    assert "upload" in t.privacy_note().lower() or "Upload" in t.privacy_note() or "không" in t.privacy_note().lower()

    tts = get_tts_provider("edge-tts")
    assert tts.requires_internet
