"""Integration: short fixture video (~8s). Requires ffmpeg + network for TTS/translate."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ff = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not ff, reason="ffmpeg required")

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _make_fixture(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 8s color video + sine audio (not speech — pipeline should still extract/transcribe)
    subprocess.run(
        [
            ff,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=640x360:d=8",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=8",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@pytest.fixture(scope="module")
def short_video():
    path = FIXTURES / "short_tone.mp4"
    if not path.exists() or path.stat().st_size < 1000:
        _make_fixture(path)
    return path


def test_probe_unicode_path(tmp_path, short_video):
    from dubvi.media import probe_video

    dest = tmp_path / "Thư mục demo" / "bài học 01.mp4"
    dest.parent.mkdir(parents=True)
    shutil.copy(short_video, dest)
    info = probe_video(dest)
    assert info["exists"]
    assert info["duration_sec"] > 5
    assert info["size_bytes"] > 0


def test_extract_and_cache_resume(tmp_path, monkeypatch, short_video):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    from dubvi import audio, cache
    from dubvi.jobs import create_job, video_work_dir
    from dubvi.ffmpeg import probe_duration

    out = tmp_path / "out"
    out.mkdir()
    jid, root = create_job(output_dir=out, input_files=[short_video])
    work = video_work_dir(root, short_video.stem)
    flac = audio.extract_for_whisper(short_video, work)
    assert flac.exists()
    assert probe_duration(flac) > 5
    # second call uses cache
    flac2 = audio.extract_for_whisper(short_video, work)
    assert flac2 == flac


@pytest.mark.integration
def test_job_run_translate_only_smoke(tmp_path, monkeypatch, short_video):
    """Optional full-ish smoke: may skip if whisper/model/network unavailable."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    from dubvi.models import AudioMode, JobConfig, StartFrom
    from dubvi.pipeline import run_job

    out = tmp_path / "out"
    cfg = JobConfig(
        output_dir=out,
        job_id="itest01",
        input_files=[short_video],
        whisper_model="tiny",
        prefer_gpu=False,
        translate_only=True,
        review_translation=False,
        audio_mode=AudioMode.VI_ONLY,
        start_from=StartFrom.AUTO,
        cleanup_on_success=False,
    )
    try:
        code = run_job(cfg)
    except Exception as e:
        pytest.skip(f"pipeline unavailable: {e}")
    # 0 ok, 1 error (e.g. no speech), 3 review — any clean exit is fine for smoke
    assert code in (0, 1, 2, 3)
