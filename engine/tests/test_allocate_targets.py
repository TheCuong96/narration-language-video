"""Strict slot targets: original EN window only (no gap-borrow)."""

from __future__ import annotations

from dubvi.audio import allocate_speech_targets
from dubvi.models import Segment


def test_targets_match_original_slots_even_if_tts_longer():
    # EN slots: 0-2 and 4-6  → 2s silence between them must NOT be borrowed
    segments = [
        Segment(id=0, start=0.0, end=2.0, text_en="a", text_vi="aa"),
        Segment(id=1, start=4.0, end=6.0, text_en="b", text_vi="bb"),
    ]
    natural = {0: 3.0, 1: 1.5}
    targets = allocate_speech_targets(segments, natural, video_duration=8.0)

    assert abs(targets[0] - 2.0) < 0.01
    assert abs(targets[1] - 2.0) < 0.01


def test_dense_speech_targets_stay_on_slots():
    segments = [
        Segment(id=0, start=0.0, end=1.0, text_en="a", text_vi="aaaa"),
        Segment(id=1, start=1.05, end=2.05, text_en="b", text_vi="bbbb"),
    ]
    natural = {0: 1.8, 1: 1.8}
    targets = allocate_speech_targets(
        segments, natural, video_duration=2.1, max_tempo=1.20, min_gap=0.05
    )
    assert abs(targets[0] - 1.0) < 0.01
    assert abs(targets[1] - 1.0) < 0.01


def test_short_tts_keeps_original_slot():
    segments = [Segment(id=0, start=1.0, end=4.0, text_en="hi", text_vi="xin chào")]
    natural = {0: 1.2}
    targets = allocate_speech_targets(segments, natural, video_duration=10.0)
    assert abs(targets[0] - 3.0) < 0.01
