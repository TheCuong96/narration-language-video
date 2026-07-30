from __future__ import annotations

from dubvi.cache import load_segments, save_segments
from dubvi.models import ErrorCode, Segment


def test_segment_roundtrip(tmp_path):
    path = tmp_path / "t.json"
    segs = [
        Segment(id=0, start=0.0, end=1.5, text_en="Hello", text_vi="Xin chào"),
        Segment(id=1, start=1.5, end=3.0, text_en="World", text_vi="Thế giới"),
    ]
    save_segments(path, segs)
    loaded = load_segments(path)
    assert loaded is not None
    assert loaded[0].text_vi == "Xin chào"
    assert loaded[1].end == 3.0


def test_error_codes_are_strings():
    assert ErrorCode.DISK_SPACE_LOW.value == "DISK_SPACE_LOW"
    assert ErrorCode.FFMPEG_MISSING.value == "FFMPEG_MISSING"
