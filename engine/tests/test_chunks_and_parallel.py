from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from dubvi.chunks import (
    merge_segments,
    plan_chunks,
    should_use_chunks,
)
from dubvi.models import JobConfig, Segment, StartFrom
from dubvi.tts import (
    AdaptiveTtsPool,
    default_tts_concurrency,
    resolve_adaptive_max,
)


def test_plan_chunks_short_video():
    plans = plan_chunks(240.0, target_chunk_sec=300.0)
    assert len(plans) == 1
    assert plans[0].start_sec == 0.0
    assert plans[0].end_sec == 240.0


def test_plan_chunks_with_silence_snap():
    silence = [295.0, 598.0, 902.0]
    plans = plan_chunks(1200.0, target_chunk_sec=300.0, silence_points=silence)
    assert len(plans) >= 3
    assert plans[0].start_sec == 0.0
    assert abs(plans[0].end_sec - 295.0) < 0.01
    assert plans[-1].end_sec == 1200.0


def test_merge_segments_reindexes():
    a = [Segment(id=0, start=0.0, end=1.0, text_en="a", text_vi="a")]
    b = [Segment(id=5, start=300.0, end=301.0, text_en="b", text_vi="b")]
    merged = merge_segments([a, b])
    assert [s.id for s in merged] == [0, 1]
    assert merged[1].start == 300.0


def test_should_use_chunks_threshold():
    cfg = JobConfig(output_dir=Path("."), job_id="x")
    assert should_use_chunks(500.0, cfg) is False
    assert should_use_chunks(700.0, cfg) is True
    cfg.enable_chunking = False
    assert should_use_chunks(3600.0, cfg) is False


def test_should_use_chunks_respects_start_from():
    cfg = JobConfig(output_dir=Path("."), job_id="x", start_from=StartFrom.TTS)
    assert should_use_chunks(3600.0, cfg) is False


def test_default_tts_concurrency():
    assert default_tts_concurrency("edge-tts") == 16
    assert default_tts_concurrency("xtts-v2", prefer_gpu=True) == 1


def test_resolve_adaptive_max():
    assert resolve_adaptive_max("edge-tts", segment_count=200) == 96
    assert resolve_adaptive_max("edge-tts", max_concurrency=40, segment_count=200) == 40
    assert resolve_adaptive_max("edge-tts", segment_count=10) == 10


def test_adaptive_pool_ramps_and_backs_off():
    async def _run():
        pool = AdaptiveTtsPool(initial=8, minimum=4, maximum=32)
        await pool.acquire()
        await pool.release(ok=True, latency_sec=0.5)
        await pool.acquire()
        await pool.acquire()
        await pool.acquire()
        await pool.release(ok=True, latency_sec=0.4)
        await pool.release(ok=True, latency_sec=0.3)
        await pool.release(ok=True, latency_sec=0.2)
        assert pool.limit >= 8
        old = pool.limit
        await pool.acquire()
        await pool.release(ok=False, latency_sec=2.0)
        assert pool.limit <= old

    asyncio.run(_run())


def test_synthesize_all_runs_concurrently(tmp_path):
    from dubvi.tts import synthesize_all

    segments = [
        Segment(id=i, start=float(i), end=float(i + 1), text_en=f"line {i}", text_vi=f"dòng {i}")
        for i in range(6)
    ]
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def fake_backoff(text, out_mp3, *, voice, provider):
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.05)
        out_mp3.parent.mkdir(parents=True, exist_ok=True)
        out_mp3.write_bytes(b"x" * 600)
        async with lock:
            active -= 1

    provider = MagicMock()
    provider.name = "mock"
    provider.requires_internet = True
    provider.privacy_note = lambda: "mock"

    async def _run():
        with patch("dubvi.tts.tts_segment_with_backoff", new=AsyncMock(side_effect=fake_backoff)):
            with patch("dubvi.providers.get_tts_provider", return_value=provider):
                return await synthesize_all(
                    segments,
                    tmp_path / "segments",
                    voice="vi-VN-HoaiMyNeural",
                    provider_name="edge-tts",
                    concurrency=3,
                )

    paths = asyncio.run(_run())

    assert len(paths) == 6
    assert peak >= 2
