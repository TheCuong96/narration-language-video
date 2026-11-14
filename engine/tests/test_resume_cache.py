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


def test_speed_policy_change_clears_legacy_voice_caches(tmp_path):
    work = tmp_path / "v"
    work.mkdir()
    old_files = [
        work / "narration_1x.wav",
        work / "narration_slot.wav",
        work / "narration.wav",
    ]
    old_dirs = [
        work / "segments",
        work / "fitted_1x",
        work / "fitted_slot",
        work / "fitted_soft",
        work / "fitted",
    ]
    for path in old_files:
        path.write_bytes(b"old")
    for path in old_dirs:
        path.mkdir()
        (path / "cached.wav").write_bytes(b"old")

    cache.clear_downstream(work, keep_en=True)

    assert not any(path.exists() for path in old_files)
    assert not any(path.exists() for path in old_dirs)
