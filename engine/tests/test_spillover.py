from __future__ import annotations

"""Unit-level check: stretch_to_duration with allow_spill must not trim when too long.

Requires ffmpeg on PATH — skipped otherwise.
"""

import shutil
from pathlib import Path

import pytest

ff = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not ff, reason="ffmpeg not on PATH")


def test_allow_spill_keeps_full_audio(tmp_path: Path):
    from dubvi.ffmpeg import probe_duration, stretch_to_duration, run_ffmpeg, ffmpeg_path

    # Build a ~2s tone as "speech"
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
    # Target much shorter than source — with allow_spill should keep ~sped audio, not 0.5s trim
    actual = stretch_to_duration(src, dst, target_sec=0.5, allow_spill=True, max_tempo=1.20)
    dur = probe_duration(dst)
    # 2s / 1.20 ≈ 1.67s — must not hard-trim to 0.5s
    assert dur > 1.4
    assert actual > 1.4


def test_mild_tempo_default_does_not_race_to_1_55(tmp_path: Path):
    from dubvi.ffmpeg import probe_duration, stretch_to_duration, run_ffmpeg, ffmpeg_path

    src = tmp_path / "src.wav"
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1.2",
            "-ar",
            "24000",
            "-ac",
            "1",
            str(src),
        ]
    )
    dst = tmp_path / "fitted.wav"
    # Slot 1.0s, natural 1.2s → default max_tempo 1.20 fits almost naturally
    actual = stretch_to_duration(src, dst, target_sec=1.0, allow_spill=True)
    dur = probe_duration(dst)
    assert 0.95 <= dur <= 1.05
    assert 0.95 <= actual <= 1.05
