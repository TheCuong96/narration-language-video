from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dubvi.models import AudioMode

ff = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not ff, reason="ffmpeg not on PATH")


def test_plan_mux_copy_for_h264_mp4(tmp_path: Path):
    from dubvi.ffmpeg import ffmpeg_path, plan_mux, run_ffmpeg

    src = tmp_path / "v.mp4"
    # Tiny black h264 + silent aac
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:d=0.5",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "0.5",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(src),
        ]
    )
    plan = plan_mux(src, tmp_path / "out.mp4", AudioMode.VI_ONLY)
    assert plan.video_codec_copy is True
    assert plan.reencode_video is False
