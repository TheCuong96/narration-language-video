from __future__ import annotations

import struct
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _wav_active_duration(path: Path, rel_thresh: float = 0.08) -> float:
    """Duration of samples above a fraction of peak amplitude (speech, not pad)."""
    with wave.open(str(path), "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        rate = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw != 2 or nch != 1 or n <= 0:
        return 0.0
    samples = struct.unpack("<" + "h" * n, raw)
    peak = max(abs(x) for x in samples) or 1
    thresh = peak * rel_thresh
    start = next((i for i, x in enumerate(samples) if abs(x) > thresh), 0)
    end = n - next((i for i, x in enumerate(reversed(samples)) if abs(x) > thresh), 0)
    return max(end - start, 0) / float(rate)


@pytest.fixture
def wav_active_duration():
    return _wav_active_duration
