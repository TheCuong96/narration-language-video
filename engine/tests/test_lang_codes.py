from dubvi.lang_codes import to_nllb_lang, to_xtts_lang


def test_nllb_codes():
    assert to_nllb_lang("en") == "eng_Latn"
    assert to_nllb_lang("vi") == "vie_Latn"
    assert to_nllb_lang("auto") == "eng_Latn"
    assert to_nllb_lang("eng_Latn") == "eng_Latn"


def test_xtts_codes():
    assert to_xtts_lang("vi") == "vi"
    assert to_xtts_lang("vie_Latn") == "vi"
    assert to_xtts_lang("en") == "en"
