from pathlib import Path

import pytest

from dubvi.jobs import CancellationToken, create_job
from dubvi.models import ErrorCode
from dubvi.system_info import EngineError, ensure_disk_space, estimate_work_bytes


def test_create_job(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    jid, root = create_job(output_dir=tmp_path / "out", input_files=[tmp_path / "a.mp4"])
    assert jid
    assert (root / "job.json").exists()


def test_estimate_and_disk_low(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    video = tmp_path / "big.mp4"
    video.write_bytes(b"0" * 1024)
    needed = estimate_work_bytes(video)
    assert needed > 0

    def tiny_free(_path):
        return 1024  # 1 KB

    monkeypatch.setattr("dubvi.system_info.free_disk_bytes", tiny_free)
    with pytest.raises(EngineError) as ei:
        ensure_disk_space(video, tmp_path / "work", tmp_path / "out")
    assert ei.value.code == ErrorCode.DISK_SPACE_LOW
    assert "Cần ít nhất" in ei.value.message
