from pathlib import Path

from dubvi import cache
from dubvi.models import Segment


def test_resume_keeps_transcript(tmp_path):
    work = tmp_path / "v"
    work.mkdir()
    segs = [Segment(0, 0.0, 1.0, "Hello", "Xin chào")]
    cache.save_segments(work / cache.TRANSCRIPT_EN, segs)
    cache.save_segments(work / cache.TRANSCRIPT_VI, segs)
    loaded = cache.load_segments(work / cache.TRANSCRIPT_VI)
    assert loaded and loaded[0].text_vi == "Xin chào"
    cache.clear_downstream(work, keep_en=True)
    assert (work / cache.TRANSCRIPT_EN).exists()
    assert not (work / cache.TRANSCRIPT_VI).exists()
