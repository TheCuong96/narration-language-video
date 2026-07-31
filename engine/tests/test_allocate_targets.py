"""Gap-borrow allocation prefers longer slots over aggressive tempo."""

from __future__ import annotations

from dubvi.audio import allocate_speech_targets
from dubvi.models import Segment


def test_borrows_following_silence_before_speeding():
    # EN slots: 0-2 and 4-6  → 2s silence between them
    segments = [
        Segment(id=0, start=0.0, end=2.0, text_en="a", text_vi="aa"),
        Segment(id=1, start=4.0, end=6.0, text_en="b", text_vi="bb"),
    ]
    # First VI line needs 3s; second fits
    natural = {0: 3.0, 1: 1.5}
    targets = allocate_speech_targets(segments, natural, video_duration=8.0)

    # Should expand seg0 toward ~3s by borrowing the 2s gap (keep min_gap)
    assert targets[0] >= 2.9
    assert targets[0] <= 3.05
    # Second keeps at least its slot (or natural if we only expand deficits)
    assert targets[1] >= 1.5


def test_dense_speech_does_not_exceed_max_tempo_hint():
    # Back-to-back slots, almost no silence — cannot borrow much
    segments = [
        Segment(id=0, start=0.0, end=1.0, text_en="a", text_vi="aaaa"),
        Segment(id=1, start=1.05, end=2.05, text_en="b", text_vi="bbbb"),
    ]
    natural = {0: 1.8, 1: 1.8}
    targets = allocate_speech_targets(
        segments, natural, video_duration=2.1, max_tempo=1.20, min_gap=0.05
    )
    # Without silence, targets stay near original slots
    assert targets[0] < 1.3
    # Implied tempo natural/target should be allowed to exceed max_tempo
    # (spill handles the rest) — allocation must not invent time
    assert targets[0] + targets[1] <= 2.2


def test_short_tts_keeps_original_slot():
    segments = [Segment(id=0, start=1.0, end=4.0, text_en="hi", text_vi="xin chào")]
    natural = {0: 1.2}
    targets = allocate_speech_targets(segments, natural, video_duration=10.0)
    assert abs(targets[0] - 3.0) < 0.01
