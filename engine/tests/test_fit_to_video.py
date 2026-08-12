from __future__ import annotations

"""When narration is longer than the video, fit_audio_to_duration must keep
full content by speeding up — never hard-trim the tail.

Requires ffmpeg on PATH — skipped otherwise.
"""

import shutil
from pathlib import Path

import pytest

ff = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not ff, reason="ffmpeg not on PATH")


def _make_tone(path: Path, duration: float, freq: int = 440) -> None:
    from dubvi.ffmpeg import run_ffmpeg, ffmpeg_path

    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:duration={duration}",
            "-ar",
            "24000",
            "-ac",
            "1",
            str(path),
        ]
    )


def test_fit_audio_speeds_up_without_losing_length_budget(tmp_path: Path):
    from dubvi.ffmpeg import fit_audio_to_duration, probe_duration

    src = tmp_path / "long.wav"
    dst = tmp_path / "fit.wav"
    _make_tone(src, 3.0)

    actual = fit_audio_to_duration(src, dst, target_sec=2.0)
    dur = probe_duration(dst)

    assert 1.95 <= dur <= 2.05
    assert 1.95 <= actual <= 2.05
    # Source was longer; output must match target (content kept via tempo, not trim)
    assert probe_duration(src) > 2.5


def test_fit_audio_handles_inplace(tmp_path: Path):
    from dubvi.ffmpeg import fit_audio_to_duration, probe_duration

    wav = tmp_path / "narration.wav"
    _make_tone(wav, 2.5)
    actual = fit_audio_to_duration(wav, wav, target_sec=1.5)
    dur = probe_duration(wav)
    assert 1.45 <= dur <= 1.55
    assert 1.45 <= actual <= 1.55


def test_build_narration_fits_each_slot_to_original_times(tmp_path: Path):
    """Long VI TTS must speed into EN slots — narration stays ≤ video, no spill drift."""
    from dubvi.audio import build_narration
    from dubvi.ffmpeg import probe_duration
    from dubvi.models import Segment

    work = tmp_path / "work"
    work.mkdir()
    segs_dir = work / "segments"
    segs_dir.mkdir()

    # Two slots with a gap; each TTS is longer than its slot
    segments = [
        Segment(id=0, start=0.0, end=1.0, text_en="a", text_vi="aaaa"),
        Segment(id=1, start=1.5, end=2.5, text_en="b", text_vi="bbbb"),
    ]
    mp3s: dict[int, Path] = {}
    for sid, dur in ((0, 1.8), (1, 1.8)):
        p = segs_dir / f"{sid:04d}.mp3"
        _make_tone(p, dur, freq=330 + sid * 40)
        mp3s[sid] = p

    video_duration = 3.0
    narration = build_narration(segments, work, video_duration, mp3s)
    narr_dur = probe_duration(narration)

    assert narr_dur <= video_duration + 0.08
    assert narr_dur > video_duration * 0.85

    # Fitted pieces must match slot lengths (1.0s each), not natural 1.8s
    from dubvi import cache

    fitted0 = work / cache.FITTED_DIR / "0000.wav"
    fitted1 = work / cache.FITTED_DIR / "0001.wav"
    assert 0.95 <= probe_duration(fitted0) <= 1.05
    assert 0.95 <= probe_duration(fitted1) <= 1.05
