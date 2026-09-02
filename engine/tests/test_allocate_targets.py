"""Speech targets: 1× until the next line; speed up only if that window is too short."""

from __future__ import annotations

from dubvi.audio import allocate_speech_targets
from dubvi.models import Segment


def test_targets_use_gap_until_next_line():
    # 2s of silence between lines is available at 1× (not a reason to speed up)
    segments = [
        Segment(id=0, start=0.0, end=2.0, text_en="a", text_vi="aa"),
        Segment(id=1, start=4.0, end=6.0, text_en="b", text_vi="bb"),
    ]
    natural = {0: 3.0, 1: 1.5}
    targets = allocate_speech_targets(segments, natural, video_duration=8.0)

    assert abs(targets[0] - 4.0) < 0.01
    assert abs(targets[1] - 4.0) < 0.01


def test_dense_speech_deadline_is_next_start():
    segments = [
        Segment(id=0, start=0.0, end=1.0, text_en="a", text_vi="aaaa"),
        Segment(id=1, start=1.05, end=2.05, text_en="b", text_vi="bbbb"),
    ]
    natural = {0: 1.8, 1: 1.8}
    targets = allocate_speech_targets(
        segments, natural, video_duration=2.1, max_tempo=1.20, min_gap=0.05
    )
    assert abs(targets[0] - 1.05) < 0.01
    assert abs(targets[1] - 1.05) < 0.01


def test_last_line_may_use_rest_of_video():
    segments = [Segment(id=0, start=1.0, end=4.0, text_en="hi", text_vi="xin chào")]
    natural = {0: 1.2}
    targets = allocate_speech_targets(segments, natural, video_duration=10.0)
    assert abs(targets[0] - 9.0) < 0.01
