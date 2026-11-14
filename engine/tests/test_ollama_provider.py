from unittest.mock import Mock

import pytest
import requests

from dubvi import ollama_manager as manager
from dubvi.providers import get_translate_provider
from dubvi.providers.ollama import TranslateGemmaProvider, build_prompt
from dubvi.system_info import EngineError


@pytest.fixture
def http(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"message": {"content": "Xin chào"}}
    call = Mock(return_value=response)
    monkeypatch.setattr(requests.Session, "request", call)
    monkeypatch.setattr(manager, "is_model_installed", lambda *a: True)
    return call, response


@pytest.mark.parametrize("name", ["translategemma", *manager.ALLOWED_MODELS])
def test_registry(name):
    provider = get_translate_provider(name)
    assert isinstance(provider, TranslateGemmaProvider)
    assert provider.name == ("translategemma:4b" if name == "translategemma" else name)
    assert not provider.requires_internet


def test_allowlist():
    with pytest.raises(EngineError):
        get_translate_provider("translategemma:evil")


def test_chat(http):
    call, _ = http
    assert TranslateGemmaProvider().translate(" Hello ", source="en", target="vi-VN") == "Xin chào"
    payload = call.call_args.kwargs["json"]
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0
    assert payload["keep_alive"] == "30m"
    assert payload["options"]["num_ctx"] == 16384
    assert 0 < payload["options"]["num_predict"] < 16384
    prompt = payload["messages"][0]["content"]
    assert "English (en) to Vietnamese (vi)" in prompt
    assert prompt.endswith(":\n\n\nHello")


def test_unknown_language():
    assert "xyz (xyz)" in build_prompt("Hi", "xyz", "vi")


def test_empty_no_http(http):
    assert TranslateGemmaProvider().translate("  ", source="en", target="vi") == "  "
    http[0].assert_not_called()


def test_not_installed(http, monkeypatch):
    monkeypatch.setattr(manager, "is_model_installed", lambda *a: False)
    with pytest.raises(EngineError, match="chưa tải"):
        TranslateGemmaProvider().translate("Hello", source="en", target="vi")


@pytest.mark.parametrize("error, message", [(requests.Timeout(), "thời gian"),
    (requests.ConnectionError(), "Ollama chưa chạy")])
def test_transport_errors(http, error, message):
    http[0].side_effect = error
    with pytest.raises(EngineError, match=message):
        TranslateGemmaProvider().translate("PRIVATE", source="en", target="vi")


def test_http_500(http):
    response = http[1]
    response.status_code = 500
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    with pytest.raises(EngineError, match="HTTP 500"):
        TranslateGemmaProvider().translate("PRIVATE", source="en", target="vi")


def test_invalid_json(http):
    http[1].json.side_effect = ValueError("PRIVATE")
    with pytest.raises(EngineError, match="JSON") as error:
        TranslateGemmaProvider().translate("PRIVATE", source="en", target="vi")
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("data", [{}, {"message": {}}, {"message": {"content": " "}},
                                  {"message": {"content": 3}}])
def test_empty_content(http, data):
    http[1].json.return_value = data
    with pytest.raises(EngineError, match="rỗng"):
        TranslateGemmaProvider().translate("Hello", source="en", target="vi")


def test_runaway_output_rejected(http):
    http[1].json.return_value = {"done_reason": "length", "message": {"content": "lặp lặp lặp"}}
    with pytest.raises(EngineError, match="quá dài"):
        TranslateGemmaProvider().translate("Hello", source="en", target="vi")


def test_clean_fence(http):
    http[1].json.return_value = {"message": {"content": "```text\nTranslation: Xin chào\n```"}}
    assert TranslateGemmaProvider().translate("Hello", source="en", target="vi") == "Xin chào"


def test_markers(http):
    http[1].json.return_value = {"message": {"content": "[[DUBVI_SEG_000001]]\nMột\n[[DUBVI_SEG_000002]]\nHai"}}
    assert TranslateGemmaProvider().translate_batch(["One", "Two"], source="en", target="vi") == ["Một", "Hai"]


@pytest.mark.parametrize("output", ["missing markers", "[[DUBVI_SEG_000001]]\nMột",
    "[[DUBVI_SEG_000002]]\nHai\n[[DUBVI_SEG_000001]]\nMột",
    "[[DUBVI_SEG_000001]]\nMột\n[[DUBVI_SEG_000001]]\nHai",
    "[[DUBVI_SEG_000001]]\n\n[[DUBVI_SEG_000002]]\nHai"])
def test_marker_failure_splits(monkeypatch, output):
    provider = TranslateGemmaProvider()
    chat = Mock(side_effect=[output, "invalid singleton", "Một", "invalid singleton", "Hai"])
    monkeypatch.setattr(provider, "_chat", chat)
    assert provider.translate_batch(["One", "Two"], source="en", target="vi") == ["Một", "Hai"]
    assert chat.call_count == 5


def test_bounded_batch(monkeypatch):
    provider = TranslateGemmaProvider()
    calls = []
    def chat(prompt):
        import re
        text = prompt.split("\n\n\n", 1)[1]
        calls.append(len(re.findall(r"\[\[DUBVI_SEG_\d+\]\]", text)))
        return text
    monkeypatch.setattr(provider, "_chat", chat)
    assert len(provider.translate_batch(["x"] * 65, source="en", target="vi")) == 65
    assert max(calls) <= 32
