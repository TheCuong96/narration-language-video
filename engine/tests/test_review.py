from __future__ import annotations

import json

from dubvi import cache, review
from dubvi.jobs import create_job, video_work_dir
from dubvi.models import Segment
from dubvi.system_info import job_dir


def test_save_translation_invalidates_tts(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    jid, root = create_job(output_dir=tmp_path / "out", input_files=[])
    work = video_work_dir(root, "lesson")
    cache.save_segments(
        work / cache.TRANSCRIPT_EN,
        [Segment(0, 0, 1, "Hello", ""), Segment(1, 1, 2, "World", "")],
    )
    cache.save_segments(
        work / cache.TRANSCRIPT_VI,
        [Segment(0, 0, 1, "Hello", "Xin chào"), Segment(1, 1, 2, "World", "Thế giới")],
    )
    seg_dir = work / cache.SEGMENTS_DIR
    seg_dir.mkdir()
    (seg_dir / "0000.mp3").write_bytes(b"x" * 600)
    (work / cache.NARRATION).write_bytes(b"narr")

    review.save_translation(
        jid,
        "lesson",
        [
            {"id": 0, "text_vi": "Chào bạn", "text_en": "Hello", "start": 0, "end": 1},
            {"id": 1, "text_vi": "Địa cầu", "text_en": "World", "start": 1, "end": 2},
        ],
    )
    assert not (work / cache.NARRATION).exists()
    assert not seg_dir.exists()
    loaded = cache.load_segments(work / cache.TRANSCRIPT_VI)
    assert loaded is not None
    assert loaded[0].text_vi == "Chào bạn"
