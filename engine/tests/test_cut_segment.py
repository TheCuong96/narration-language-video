from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dubvi.media import (
    clone_video_segment,
    default_clip_path,
    named_clip_path,
    parse_timestamp,
)
from dubvi.system_info import EngineError

ff = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not ff, reason="ffmpeg not on PATH")


def _make_sample(tmp_path: Path, seconds: float = 2.0) -> Path:
    from dubvi.ffmpeg import ffmpeg_path, run_ffmpeg

    src = tmp_path / "sample.mp4"
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=blue:s=320x240:d={seconds}",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            str(seconds),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(src),
        ]
    )
    return src


def test_parse_timestamp_formats():
    assert parse_timestamp(90) == 90.0
    assert parse_timestamp("90") == 90.0
    assert parse_timestamp("1:30") == 90.0
    assert parse_timestamp("1:02:03") == 3723.0
    assert parse_timestamp("0:05.5") == 5.5
    with pytest.raises(EngineError):
        parse_timestamp("abc")


def test_default_clip_path():
    src = Path(r"C:\vids\demo.mp4")
    out = default_clip_path(src, 0, 90)
    assert out.name == "demo_clip_0-90.mp4"
    assert out.parent == src.parent


def test_clone_video_segment(tmp_path: Path):
    from dubvi.ffmpeg import probe_duration

    src = _make_sample(tmp_path, 2.0)
    result = clone_video_segment(src, "0.2", "1.2")
    assert result["ok"] is True
    out = Path(result["path"])
    assert out.is_file()
    assert out.name == "sample_clip_0.2-1.2.mp4"
    dur = probe_duration(out)
    # Stream-copy cuts land on keyframes — allow a bit of slack.
    assert 0.6 <= dur <= 1.5


def test_clone_rejects_bad_range(tmp_path: Path):
    src = _make_sample(tmp_path, 1.0)
    with pytest.raises(EngineError):
        clone_video_segment(src, "1.5", "0.5")


def test_named_clip_path_and_clone(tmp_path: Path):
    src = _make_sample(tmp_path, 1.5)
    out = named_clip_path(src, "doan gioi thieu")
    assert out.name == "doan gioi thieu.mp4"
    assert out.parent == src.parent

    result = clone_video_segment(src, 0, 1, name="phan_1")
    assert Path(result["path"]).name == "phan_1.mp4"

    # Collision → _2
    again = clone_video_segment(src, 0, 0.5, name="phan_1")
    assert Path(again["path"]).name == "phan_1_2.mp4"

    with pytest.raises(EngineError):
        named_clip_path(src, "   ")
