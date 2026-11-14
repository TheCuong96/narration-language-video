from __future__ import annotations

"""Sources whose video timestamps are stretched relative to the audio (broken
downloads: frames / nominal fps == audio length, but PTS run ~1.5x longer)
must be retimed so the dub does not go silent for the last third.
"""

import shutil
from pathlib import Path

import pytest

from dubvi.ffmpeg import AvTiming, stretched_video_fps

ff = shutil.which("ffmpeg")


def test_detects_stretched_video_from_real_course_file():
    # "Welcome to the course.mp4": 1929 frames @30 = 64.3s of picture, PTS end 95.87s.
    t = AvTiming(video_sec=95.866667, audio_sec=64.319252, frames=1929, fps=30.0)
    assert stretched_video_fps(t) == pytest.approx(30.0)


def test_normal_file_is_left_alone():
    t = AvTiming(video_sec=11.4, audio_sec=11.377007, frames=342, fps=30.0)
    assert stretched_video_fps(t) is None


def test_audio_genuinely_shorter_is_left_alone():
    # Silent outro: frame count matches the video length, not the audio.
    t = AvTiming(video_sec=95.866667, audio_sec=64.3, frames=2876, fps=30.0)
    assert stretched_video_fps(t) is None


def test_missing_frame_count_is_left_alone():
    t = AvTiming(video_sec=95.866667, audio_sec=64.3, frames=0, fps=30.0)
    assert stretched_video_fps(t) is None


@pytest.mark.skipif(not ff, reason="ffmpeg not on PATH")
def test_normalize_source_retimes_stretched_video(tmp_path: Path):
    from dubvi import audio
    from dubvi.ffmpeg import ffmpeg_path, probe_av_timing, probe_duration, run_ffmpeg

    src = tmp_path / "stretched.mp4"
    # 60 frames @30fps (2s of picture) with PTS stretched 1.5x, plus 2s of audio.
    run_ffmpeg(
        [
            ffmpeg_path(), "-y",
            "-f", "lavfi", "-i", "testsrc=size=64x64:rate=30:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-vf", "setpts=1.5*PTS", "-fps_mode", "passthrough",
            "-c:v", "libx264", "-c:a", "aac", "-video_track_timescale", "90000",
            str(src),
        ]
    )
    before = probe_av_timing(src)
    assert before is not None and before.video_sec > before.audio_sec * 1.3

    work = tmp_path / "work"
    work.mkdir()
    fixed = audio.normalize_source(src, work)
    assert fixed != src
    assert probe_duration(fixed) == pytest.approx(2.0, abs=0.15)
    assert audio.media_source(src, work) == fixed

    plain = tmp_path / "plain.mp4"
    shutil.copy(fixed, plain)
    other_work = tmp_path / "work2"
    other_work.mkdir()
    assert audio.normalize_source(plain, other_work) == plain
