import json
from unittest.mock import Mock

import pytest
import requests

from dubvi import ollama_manager as manager, models_manager
from dubvi.system_info import EngineError


@pytest.fixture
def http(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"models": [{"name": "translategemma:4b", "size": 12345}]}
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    call = Mock(return_value=response)
    monkeypatch.setattr(requests.Session, "request", call)
    return call, response


@pytest.mark.parametrize("url", ["https://127.0.0.1:11434", "http://example.com:11434",
    "http://127.0.0.1:11434/path", "http://localhost:11434?evil=1", "http://user@localhost:11434"])
def test_remote_url_denied(url):
    with pytest.raises(EngineError):
        manager.normalize_base_url(url)


def test_tags(http):
    assert manager.is_model_installed("translategemma:4b")
    assert not manager.is_model_installed("translategemma:12b")
    assert http[0].call_args.args == ("GET", manager.BASE_URL + "/api/tags")
    assert http[0].call_args.kwargs["allow_redirects"] is False


def test_runtime_unavailable(http):
    http[0].side_effect = requests.ConnectionError()
    health = manager.check_health()
    assert not health["available"]
    assert "NLLB" in health["error"]
    entries = models_manager.list_models(kind="translate")
    assert len([m for m in entries if m.get("runtime") == "ollama"]) == 3
    assert all(not m["downloaded"] and not m["runtime_available"] and not m["download_root"]
               for m in entries if m.get("runtime") == "ollama")


def test_model_dispatch_without_paths(http, monkeypatch):
    monkeypatch.setattr(models_manager, "model_path", Mock(side_effect=AssertionError("Ollama must not use local paths")))
    assert models_manager.is_model_downloaded("translategemma:4b")
    assert models_manager.model_disk_usage_bytes("translategemma:4b") == 12345
    monkeypatch.setattr(models_manager, "list_models", lambda: [])
    models_manager.delete_model("translategemma:4b", confirm=True)
    assert any(c.args[0] == "DELETE" for c in http[0].call_args_list)


def test_pull_progress(http):
    http[1].iter_lines.return_value = [b'', json.dumps({"status": "pulling", "completed": 25, "total": 100}).encode(),
                                      b'{"status":"verifying"}', b'{"status":"success"}']
    callback = Mock()
    assert models_manager.download_model("translategemma:4b", progress_cb=callback) is None
    callback.assert_any_call(25, 100, "pulling")
    assert http[0].call_args.kwargs["json"] == {"model": "translategemma:4b", "stream": True}


@pytest.mark.parametrize("lines", [[b'{"status":"pulling"}'], [b'broken'], [b'{"error":"bad"}']])
def test_pull_failure(http, lines):
    http[1].iter_lines.return_value = lines
    with pytest.raises(EngineError):
        manager.pull_model("translategemma:4b")


def test_delete(http):
    manager.delete_model("translategemma:12b")
    assert http[0].call_args.args == ("DELETE", manager.BASE_URL + "/api/delete")
    assert http[0].call_args.kwargs["json"] == {"model": "translategemma:12b"}


def test_doctor_offline(http, monkeypatch, capsys, tmp_path):
    from dubvi import cli
    from dubvi.settings_store import AppSettings
    from dubvi import system_info
    http[0].side_effect = requests.ConnectionError()
    monkeypatch.setattr(cli, "load_settings", lambda: AppSettings(translate_provider="translategemma:4b"))
    monkeypatch.setattr(system_info, "appdata_root", lambda: tmp_path)
    monkeypatch.setattr(models_manager, "models_dir", lambda: tmp_path / "models")
    code = cli.main(["doctor"])
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    checks = {c["name"]: c for c in report["checks"]}
    assert not checks["ollama_runtime"]["ok"]
    assert checks["model_translategemma_4b"]["required"]
    assert not checks["model_translategemma_12b"]["required"]
    assert not report["privacy"]["translate_needs_internet"]
