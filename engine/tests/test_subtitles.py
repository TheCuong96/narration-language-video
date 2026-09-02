from __future__ import annotations

from pathlib import Path

import pytest

from dubvi.chunks import should_use_chunks
from dubvi.errors_ui import friendly_error
from dubvi.models import ErrorCode, JobConfig, StartFrom
from dubvi.progress import ProgressTracker
from dubvi.pipeline import _needs_whisper, _try_load_existing_subtitles
from dubvi.subtitles import (
    find_subtitle_for_video,
    parse_subtitle_file,
    parse_timestamp,
    resolve_subtitle_path,
)
from dubvi.system_info import EngineError

UDEMY_SRT = (
    Path(__file__).resolve().parents[2]
    / "test-udemy"
    / "001 Day 1 - Running Your First LLM Locally with Ollama and Open Source Models_vi.srt"
)

SAMPLE_SRT = """1
00:00:00,120 --> 00:00:02,200
Đây là thời điểm quan trọng.

2
00:00:02,240 --> 00:00:06,800
Đây là khởi đầu của một cuộc phiêu lưu.

3
00:00:07,120 --> 00:00:11,680
<i>Cho dù bạn là người mới</i>
"""

SAMPLE_VTT = """WEBVTT

NOTE ignore this

00:00:00.120 --> 00:00:02.200
Đây là thời điểm quan trọng.

2
00:00:02.240 --> 00:00:06.800 align:start
Đây là khởi đầu của một cuộc phiêu lưu.
"""


def test_parse_timestamp_srt_and_vtt():
    assert abs(parse_timestamp("00:00:02,200") - 2.2) < 1e-6
    assert abs(parse_timestamp("00:01:01,810") - 61.81) < 1e-6
    assert abs(parse_timestamp("01:02:03.500") - 3723.5) < 1e-6
    assert abs(parse_timestamp("01:05.890") - 65.89) < 1e-6


def test_parse_srt_strips_tags_and_ids(tmp_path: Path):
    path = tmp_path / "lesson_vi.srt"
    path.write_text(SAMPLE_SRT, encoding="utf-8")
    segs = parse_subtitle_file(path)
    assert len(segs) == 3
    assert segs[0].id == 0
    assert segs[0].text_vi == "Đây là thời điểm quan trọng."
    assert abs(segs[0].start - 0.12) < 1e-6
    assert abs(segs[0].end - 2.2) < 1e-6
    assert segs[2].text_vi == "Cho dù bạn là người mới"
    assert all(s.text_vi for s in segs)


def test_parse_vtt(tmp_path: Path):
    path = tmp_path / "lesson.vi.vtt"
    path.write_text(SAMPLE_VTT, encoding="utf-8")
    segs = parse_subtitle_file(path)
    assert len(segs) == 2
    assert segs[1].text_vi == "Đây là khởi đầu của một cuộc phiêu lưu."
    assert abs(segs[1].start - 2.24) < 1e-6


def test_empty_subtitle_raises(tmp_path: Path):
    path = tmp_path / "empty.srt"
    path.write_text("1\n00:00:00,000 --> 00:00:01,000\n\n", encoding="utf-8")
    with pytest.raises(EngineError) as ei:
        parse_subtitle_file(path)
    assert ei.value.code == ErrorCode.SUBTITLE_INVALID


def test_finds_udemy_style_sidecar(tmp_path: Path):
    video = tmp_path / "001 Day 1 - Running Your First LLM Locally.mp4"
    video.write_bytes(b"x")
    srt = tmp_path / "001 Day 1 - Running Your First LLM Locally_vi.srt"
    srt.write_text(SAMPLE_SRT, encoding="utf-8")
    (tmp_path / "001 Day 1 - Running Your First LLM Locally.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nEnglish leftover\n",
        encoding="utf-8",
    )
    found = find_subtitle_for_video(video)
    assert found == srt


def test_prefers_explicit_extra_file(tmp_path: Path):
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"x")
    sidecar = tmp_path / "lesson_vi.srt"
    sidecar.write_text(SAMPLE_SRT, encoding="utf-8")
    other_dir = tmp_path / "subs"
    other_dir.mkdir()
    extra = other_dir / "lesson.vi.srt"
    extra.write_text(SAMPLE_SRT, encoding="utf-8")
    found = find_subtitle_for_video(video, extra_files=[extra])
    assert found == extra.resolve()


def test_yt_dlp_dot_lang_pattern(tmp_path: Path):
    video = tmp_path / "talk.mkv"
    video.write_bytes(b"x")
    srt = tmp_path / "talk.vi.srt"
    srt.write_text(SAMPLE_SRT, encoding="utf-8")
    assert find_subtitle_for_video(video) == srt


def test_matches_vi_srt_in_mixed_folder(tmp_path: Path):
    """Videos and SRTs can be interleaved; pair by `{stem}_vi.srt`, not by sort order."""
    (tmp_path / "zzz intro.mp4").write_bytes(b"x")
    (tmp_path / "aaa notes_vi.srt").write_text(SAMPLE_SRT, encoding="utf-8")
    (tmp_path / "readme.txt").write_text("x", encoding="utf-8")
    video = tmp_path / "001 Day 1 - Running Your First LLM.mp4"
    video.write_bytes(b"x")
    srt = tmp_path / "001 Day 1 - Running Your First LLM_vi.srt"
    srt.write_text(SAMPLE_SRT, encoding="utf-8")
    (tmp_path / "unrelated_vi.srt").write_text(SAMPLE_SRT, encoding="utf-8")
    assert find_subtitle_for_video(video) == srt


def test_pairs_each_video_with_its_own_vi_srt(tmp_path: Path):
    a = tmp_path / "lecture a.mp4"
    b = tmp_path / "lecture b.mp4"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    sa = tmp_path / "lecture a_vi.srt"
    sb = tmp_path / "lecture b_vi.srt"
    sa.write_text(SAMPLE_SRT, encoding="utf-8")
    sb.write_text(SAMPLE_SRT, encoding="utf-8")
    assert find_subtitle_for_video(a) == sa
    assert find_subtitle_for_video(b) == sb


def test_finds_vi_srt_in_subs_subfolder(tmp_path: Path):
    video = tmp_path / "talk.mp4"
    video.write_bytes(b"x")
    subs = tmp_path / "Subs"
    subs.mkdir()
    srt = subs / "talk_vi.srt"
    srt.write_text(SAMPLE_SRT, encoding="utf-8")
    assert find_subtitle_for_video(video) == srt
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"x")
    with pytest.raises(EngineError) as ei:
        resolve_subtitle_path(video)
    assert ei.value.code == ErrorCode.SUBTITLE_NOT_FOUND
    assert "lesson_vi.srt" in ei.value.message


def test_chunks_still_used_when_srt_mode_falls_back_to_translate():
    cfg = JobConfig(output_dir=Path("."), job_id="x", use_existing_subtitles=True)
    assert should_use_chunks(3600.0, cfg) is True
    cfg2 = JobConfig(output_dir=Path("."), job_id="x")
    assert should_use_chunks(3600.0, cfg2) is True
    cfg3 = JobConfig(output_dir=Path("."), job_id="x", start_from=StartFrom.TTS)
    assert should_use_chunks(3600.0, cfg3) is False


def test_skip_asr_progress_marks_three_stages_done():
    t = ProgressTracker(file_index=0, file_total=1, file_name="a.mp4")
    t.begin_stage("init")
    t.skip_asr_pipeline("Dùng phụ đề")
    assert t._stage_fracs["extracting"] == 1.0
    assert t._stage_fracs["transcribing"] == 1.0
    assert t._stage_fracs["translating"] == 1.0
    assert t.overall_percent() > 30


def test_subtitle_friendly_errors():
    missing = friendly_error(ErrorCode.SUBTITLE_NOT_FOUND, "lesson.mp4")
    assert "phụ đề" in missing.title.lower() or "phụ đề" in missing.message.lower()
    invalid = friendly_error(ErrorCode.SUBTITLE_INVALID)
    assert invalid.title


def test_needs_whisper_even_when_srt_mode_is_on():
    auto = JobConfig(output_dir=Path("."), job_id="x")
    srt = JobConfig(output_dir=Path("."), job_id="x", use_existing_subtitles=True)
    tts = JobConfig(output_dir=Path("."), job_id="x", start_from=StartFrom.TTS)
    assert _needs_whisper(auto) is True
    assert _needs_whisper(srt) is True
    assert _needs_whisper(tts) is False


def test_try_load_subtitles_returns_none_without_sidecar(tmp_path: Path):
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"x")
    work = tmp_path / "work"
    work.mkdir()
    cfg = JobConfig(output_dir=tmp_path, job_id="x", use_existing_subtitles=True)
    tracker = ProgressTracker(file_index=0, file_total=1, file_name=video.name)
    assert _try_load_existing_subtitles(video, work, cfg, tracker) is None


def test_try_load_subtitles_reads_sidecar(tmp_path: Path):
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"x")
    srt = tmp_path / "lesson_vi.srt"
    srt.write_text(SAMPLE_SRT, encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    cfg = JobConfig(output_dir=tmp_path, job_id="x", use_existing_subtitles=True)
    tracker = ProgressTracker(file_index=0, file_total=1, file_name=video.name)
    segs = _try_load_existing_subtitles(video, work, cfg, tracker)
    assert segs is not None
    assert len(segs) == 3
    assert segs[0].text_vi == "Đây là thời điểm quan trọng."


@pytest.mark.skipif(not UDEMY_SRT.is_file(), reason="test-udemy SRT not present")
def test_parse_real_udemy_srt():
    segs = parse_subtitle_file(UDEMY_SRT)
    assert len(segs) > 50
    assert segs[0].text_vi.startswith("Đây là thời điểm")
    assert segs[0].end > segs[0].start
    assert all(s.text_vi.strip() for s in segs)
    assert segs[-1].start > 60
