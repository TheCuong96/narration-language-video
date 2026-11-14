from __future__ import annotations

"""Strict slot fit: stretch_to_duration must match target (speed up or 1×+pad).

Requires ffmpeg on PATH — skipped otherwise.
"""

import shutil
from pathlib import Path

import pytest

ff = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not ff, reason="ffmpeg not on PATH")


def test_strict_fit_speeds_up_long_audio(tmp_path: Path):
    from dubvi.ffmpeg import probe_duration, stretch_to_duration, run_ffmpeg, ffmpeg_path

    src = tmp_path / "src.wav"
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-ar",
            "24000",
            "-ac",
            "1",
            str(src),
        ]
    )
    dst = tmp_path / "fitted.wav"
    actual = stretch_to_duration(
        src, dst, target_sec=0.5, allow_spill=False, max_tempo=8.0, min_tempo=1.0
    )
    dur = probe_duration(dst)
    assert 0.45 <= dur <= 0.55
    assert 0.45 <= actual <= 0.55


def test_short_audio_stays_1x_and_pads(tmp_path: Path, wav_active_duration):
    from dubvi.ffmpeg import probe_duration, stretch_to_duration, run_ffmpeg, ffmpeg_path

    src = tmp_path / "src.wav"
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.4",
            "-ar",
            "24000",
            "-ac",
            "1",
            str(src),
        ]
    )
    dst = tmp_path / "fitted.wav"
    actual = stretch_to_duration(
        src, dst, target_sec=1.0, allow_spill=False, max_tempo=8.0, min_tempo=1.0
    )
    dur = probe_duration(dst)
    assert 0.95 <= dur <= 1.05
    assert 0.95 <= actual <= 1.05
    # Must pad, not time-stretch: tone stays ~0.4s at the start.
    active = wav_active_duration(dst)
    assert 0.32 <= active <= 0.52


def test_legacy_spill_still_available(tmp_path: Path):
    from dubvi.ffmpeg import probe_duration, stretch_to_duration, run_ffmpeg, ffmpeg_path

    src = tmp_path / "src.wav"
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-ar",
            "24000",
            "-ac",
            "1",
            str(src),
        ]
    )
    dst = tmp_path / "fitted.wav"
    actual = stretch_to_duration(
        src, dst, target_sec=0.5, allow_spill=True, max_tempo=1.20
    )
    dur = probe_duration(dst)
    # 2s / 1.20 ≈ 1.67s — spill keeps length, does not nail 0.5s
    assert dur > 1.4
    assert actual > 1.4
