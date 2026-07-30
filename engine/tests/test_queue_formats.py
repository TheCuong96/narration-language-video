from __future__ import annotations

from pathlib import Path

import pytest

from dubvi.models import ErrorCode
from dubvi.queue import is_video_file, output_path_for, resolve_inputs
from dubvi.system_info import EngineError


def test_is_video_file_extensions(tmp_path: Path):
    for ext in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
        p = tmp_path / f"a{ext}"
        p.write_bytes(b"x")
        assert is_video_file(p)
    other = tmp_path / "a.txt"
    other.write_text("x")
    assert not is_video_file(other)


def test_resolve_folder_and_files(tmp_path: Path):
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "one.mp4").write_bytes(b"1")
    (folder / "two.mkv").write_bytes(b"2")
    extra = tmp_path / "drop.mov"
    extra.write_bytes(b"3")

    videos = resolve_inputs(input_dir=folder, input_files=[extra])
    names = sorted(v.name for v in videos)
    assert names == ["drop.mov", "one.mp4", "two.mkv"]


def test_unsupported_raises(tmp_path: Path):
    bad = tmp_path / "x.txt"
    bad.write_text("no")
    with pytest.raises(EngineError) as ei:
        resolve_inputs(input_files=[bad])
    assert ei.value.code == ErrorCode.UNSUPPORTED_FORMAT


def test_output_path_mkv():
    out = output_path_for(Path("lesson.mkv"), Path("D:/out"))
    assert out.name == "lesson.mkv"
    out2 = output_path_for(Path("lesson.mp4"), Path("D:/out"))
    assert out2.name == "lesson.mp4"
