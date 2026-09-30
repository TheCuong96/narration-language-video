import os

import pytest

from dubvi.providers.ollama import TranslateGemmaProvider


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("DUBVI_TEST_OLLAMA") != "1", reason="Set DUBVI_TEST_OLLAMA=1; requires running Ollama and preinstalled 4B")
def test_real_local_translation():
    provider = TranslateGemmaProvider(model=os.environ.get("DUBVI_TEST_OLLAMA_MODEL", "translategemma:4b"))
    assert provider.translate("Hello, how are you?", source="en", target="vi").strip()
    assert len(provider.translate_batch(["Hello", "Thank you"], source="en", target="vi")) == 2
