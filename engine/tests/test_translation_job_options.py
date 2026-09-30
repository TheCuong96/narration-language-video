from pathlib import Path

import pytest

from dubvi import cli
from dubvi.models import JobConfig
from dubvi.settings_store import AppSettings


def test_run_batch_options(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_settings", lambda: AppSettings())
    args = cli._build_parser().parse_args([
        "run", "--files", str(tmp_path / "video.mp4"), "-o", str(tmp_path),
        "--translate-provider", "translategemma:12b", "--translate-concurrency", "9",
        "--translate-fallback-online",
    ])
    cfg = cli._cfg_from_run(args)
    assert cfg.translate_provider == "translategemma:12b"
    assert cfg.translate_concurrency == 9
    assert cfg.translate_fallback_online


@pytest.mark.parametrize("command", ["resume", "retry", "continue"])
def test_restore_translation_options(monkeypatch, tmp_path, command):
    from dubvi import queue
    state = {"output_dir": str(tmp_path), "options": {
        "translate_provider": "translategemma:12b", "translate_concurrency": 9,
        "translate_fallback_online": True, "source_lang": "ja", "target_lang": "vi",
        "extra_terms": ["Dub VI"],
    }}
    monkeypatch.setattr(cli, "load_job_state", lambda *a: state)
    monkeypatch.setattr(queue, "load_queue", lambda *a: {"items": [{"stem": "video", "input": str(tmp_path / "video.mp4")}]})
    monkeypatch.setattr(queue, "resumable_stems", lambda *a: ["video"])
    monkeypatch.setattr(queue, "failed_stems", lambda *a: ["video"])
    monkeypatch.setattr(queue, "mark_active_cancelled", lambda *a: None)
    captured = []
    monkeypatch.setattr(cli, "run_job", lambda cfg: captured.append(cfg) or 0)
    monkeypatch.setattr(cli, "continue_stem", lambda cfg, *a: captured.append(cfg) or 0)
    args = [command, "--job-id", "testjob"]
    if command == "continue":
        args += ["--stem", "video"]
    assert cli.main(args) == 0
    cfg = captured[0]
    assert cfg.translate_provider == "translategemma:12b"
    assert cfg.translate_concurrency == 9
    assert cfg.translate_fallback_online
    assert cfg.source_lang == "ja"
    assert cfg.extra_terms == ["Dub VI"]
