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
    actual = stretch_to_duration(src, dst, target_sec=0.5, allow_spill=True, max_tempo=1.55)
    dur = probe_duration(dst)
    assert dur > 0.8  # not hard-trimmed to 0.5s
    assert actual > 0.8
