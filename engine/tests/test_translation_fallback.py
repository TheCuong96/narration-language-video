from unittest.mock import Mock

import pytest

from dubvi import models_manager, providers
from dubvi.providers.fallback import LocalFallbackProvider
from dubvi.system_info import EngineError


@pytest.mark.parametrize("online", [False, True])
def test_online_requires_opt_in(monkeypatch, online):
    primary = Mock(requires_internet=False, name="primary")
    primary.name = "translategemma:4b"
    primary.translate.side_effect = RuntimeError("private text")
    monkeypatch.setattr(models_manager, "is_model_downloaded", lambda *a: False)
    google = Mock()
    google.name = "deep-translator"
    google.translate.return_value = "Xin chào"
    registry = Mock(return_value=google)
    monkeypatch.setattr(providers, "get_translate_provider", registry)
    provider = LocalFallbackProvider(primary, online=online)
    if online:
        assert provider.translate("Hello", source="en", target="vi") == "Xin chào"
        registry.assert_called_once()
    else:
        with pytest.raises(EngineError):
            provider.translate("Hello", source="en", target="vi")
        registry.assert_not_called()


def test_local_alternative(monkeypatch):
    primary = Mock()
    primary.name = "nllb"
    primary.translate.side_effect = RuntimeError()
    monkeypatch.setattr(models_manager, "is_model_downloaded", lambda model: model == "translategemma:4b")
    alternate = Mock()
    alternate.name = "translategemma:4b"
    alternate.translate.return_value = "Xin chào"
    monkeypatch.setattr(providers, "get_translate_provider", lambda *a, **kw: alternate)
    assert LocalFallbackProvider(primary).translate("Hello", source="en", target="vi") == "Xin chào"
