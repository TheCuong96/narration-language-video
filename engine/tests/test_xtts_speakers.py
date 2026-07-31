from pathlib import Path

from dubvi import models_manager


def test_list_xtts_speakers_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert models_manager.list_xtts_speakers() == []


def test_list_xtts_speakers_finds_samples(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root = models_manager.model_path("xtts-v2")
    samples = root / "samples"
    samples.mkdir(parents=True)
    for name in ("nu-nhe-nhang.wav", "nam-calm.wav"):
        p = samples / name
        p.write_bytes(b"0" * 2000)
    default = root / "speaker_default.wav"
    default.write_bytes(b"0" * 2000)

    speakers = models_manager.list_xtts_speakers()
    names = {s["name"] for s in speakers}
    assert "speaker_default.wav" in names
    assert "nu-nhe-nhang.wav" in names
    assert "nam-calm.wav" in names
    assert speakers[0]["default"] is True
    assert any("Nữ" in s["label"] for s in speakers)
