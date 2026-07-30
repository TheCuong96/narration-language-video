from __future__ import annotations

from pathlib import Path

from dubvi.jobs import video_work_dir


def test_unicode_and_spaces_in_stem(tmp_path):
    work = video_work_dir(tmp_path, "Bài học 01 - Intro")
    assert work.exists()
    assert "Bài học 01 - Intro" in str(work)
