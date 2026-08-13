"""Long-video chunk planning and parallel early-stage processing."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from . import cache, events, translation, transcription
from .ffmpeg import detect_silence_midpoints, extract_audio_segment, probe_duration
from .jobs import CancellationToken
from .models import ErrorCode, JobConfig, Segment, Stage, StartFrom
from .system_info import EngineError, get_logger

log = get_logger("dubvi.chunks")

DEFAULT_CHUNK_SECONDS = 300.0
DEFAULT_MIN_VIDEO_SECONDS = 600.0
DEFAULT_CHUNK_WORKERS = 4
SILENCE_SNAP_WINDOW = 45.0


@dataclass(frozen=True)
class ChunkPlan:
    index: int
    start_sec: float
    end_sec: float

    @property
    def duration_sec(self) -> float:
        return max(self.end_sec - self.start_sec, 0.0)


def default_chunk_workers() -> int:
    cpu = os.cpu_count() or 4
    return max(2, min(DEFAULT_CHUNK_WORKERS, cpu))


def should_use_chunks(duration_sec: float, cfg: JobConfig) -> bool:
    if not cfg.enable_chunking:
        return False
    if duration_sec < cfg.chunk_min_duration_sec:
        return False
    if cfg.start_from not in (
        StartFrom.AUTO,
        StartFrom.EXTRACT,
        StartFrom.TRANSCRIBE,
        StartFrom.TRANSLATE,
    ):
        return False
    return duration_sec > cfg.chunk_duration_sec * 1.2


def _nearest_silence(target: float, silence_points: list[float], window: float) -> float | None:
    best: float | None = None
    best_dist = window + 1.0
    for point in silence_points:
        dist = abs(point - target)
        if dist <= window and dist < best_dist:
            best = point
            best_dist = dist
    return best


def plan_chunks(
    total_duration: float,
    *,
    target_chunk_sec: float = DEFAULT_CHUNK_SECONDS,
    silence_points: list[float] | None = None,
) -> list[ChunkPlan]:
    """Split timeline into ~target_chunk_sec windows, snapping boundaries to silence."""
    if total_duration <= target_chunk_sec * 1.05:
        return [ChunkPlan(index=0, start_sec=0.0, end_sec=total_duration)]

    silence = silence_points or []
    plans: list[ChunkPlan] = []
    start = 0.0
    index = 0

    while start < total_duration - 0.5:
        nominal_end = min(start + target_chunk_sec, total_duration)
        if nominal_end >= total_duration - 0.05:
            end = total_duration
        else:
            snap = _nearest_silence(nominal_end, silence, SILENCE_SNAP_WINDOW)
            end = snap if snap is not None and snap > start + 30.0 else nominal_end
            end = min(end, total_duration)

        if end <= start + 0.5:
            end = min(start + target_chunk_sec, total_duration)
        if end <= start + 0.05:
            break

        plans.append(ChunkPlan(index=index, start_sec=start, end_sec=end))
        start = end
        index += 1

    if not plans:
        plans.append(ChunkPlan(index=0, start_sec=0.0, end_sec=total_duration))
    return plans


def merge_segments(segment_groups: list[list[Segment]]) -> list[Segment]:
    """Merge chunk segment lists into one timeline with contiguous ids."""
    merged: list[Segment] = []
    next_id = 0
    for group in segment_groups:
        for s in sorted(group, key=lambda x: (x.start, x.end, x.id)):
            merged.append(
                Segment(
                    id=next_id,
                    start=s.start,
                    end=s.end,
                    text_en=s.text_en,
                    text_vi=s.text_vi,
                )
            )
            next_id += 1
    return merged


def _chunk_work_dir(work: Path, plan: ChunkPlan) -> Path:
    return work / cache.CHUNKS_DIR / f"{plan.index:03d}"


def _ensure_chunk_audio(
    full_flac: Path,
    plan: ChunkPlan,
    chunk_work: Path,
) -> Path:
    chunk_flac = chunk_work / cache.AUDIO_FLAC
    if chunk_flac.exists() and chunk_flac.stat().st_size > 0:
        return chunk_flac
    extract_audio_segment(full_flac, chunk_flac, plan.start_sec, plan.end_sec)
    return chunk_flac


def _process_chunk_early(
    plan: ChunkPlan,
    *,
    full_flac: Path,
    work: Path,
    model,
    cfg: JobConfig,
    cancel: CancellationToken | None,
) -> tuple[ChunkPlan, list[Segment], list[Segment]]:
    chunk_work = _chunk_work_dir(work, plan)
    chunk_work.mkdir(parents=True, exist_ok=True)
    chunk_flac = _ensure_chunk_audio(full_flac, plan, chunk_work)

    chunk_dur = probe_duration(chunk_flac)
    if chunk_dur <= 0:
        chunk_dur = plan.duration_sec

    en_path = chunk_work / cache.TRANSCRIPT_EN
    vi_path = chunk_work / cache.TRANSCRIPT_VI

    segments_en = transcription.transcribe(
        chunk_flac,
        en_path,
        model,
        source_lang=cfg.source_lang,
        cancel=cancel,
        tracker=None,
        duration_sec=chunk_dur,
        time_offset=plan.start_sec,
        use_whisper_lock=True,
    )

    segments_vi = translation.translate_segments(
        segments_en,
        vi_path,
        source_lang=cfg.source_lang,
        target_lang=cfg.target_lang,
        terms=cfg.terms,
        cancel=cancel,
        tracker=None,
        provider_name=cfg.translate_provider,
        prefer_gpu=cfg.prefer_gpu,
        concurrency=cfg.translate_concurrency,
    )
    return plan, segments_en, segments_vi


def process_early_stages_chunked(
    *,
    full_flac: Path,
    work: Path,
    duration: float,
    model,
    cfg: JobConfig,
    cancel: CancellationToken | None,
    tracker=None,
) -> tuple[list[Segment], list[Segment]]:
    """
    Extract+transcribe+translate each chunk in parallel workers.

    Whisper calls are serialized via whisper_lock inside transcribe().
    """
    silence = detect_silence_midpoints(full_flac)
    plans = plan_chunks(
        duration,
        target_chunk_sec=cfg.chunk_duration_sec,
        silence_points=silence,
    )
    workers = cfg.chunk_workers if cfg.chunk_workers > 0 else default_chunk_workers()
    workers = max(1, min(workers, len(plans)))

    label = (
        f"Video dài — xử lý {len(plans)} phần (~{cfg.chunk_duration_sec / 60:.0f} phút/phần, "
        f"{workers} luồng)"
    )
    events.log(label)
    if tracker:
        tracker.begin_stage(Stage.TRANSCRIBING, label)
        tracker.emit(0, len(plans), "Đang phân tích theo phần…")

    groups_en: list[list[Segment]] = [[] for _ in plans]
    groups_vi: list[list[Segment]] = [[] for _ in plans]
    done = 0

    def _on_chunk_done(plan: ChunkPlan, segs_en: list[Segment], segs_vi: list[Segment]) -> None:
        nonlocal done
        groups_en[plan.index] = segs_en
        groups_vi[plan.index] = segs_vi
        done += 1
        msg = f"Xong phần {done}/{len(plans)} ({plan.start_sec / 60:.0f}–{plan.end_sec / 60:.0f} phút)"
        events.log(msg)
        if tracker:
            tracker.emit(done, len(plans), msg)

    if len(plans) == 1 or workers == 1:
        for plan in plans:
            if cancel:
                cancel.check()
            _, segs_en, segs_vi = _process_chunk_early(
                plan,
                full_flac=full_flac,
                work=work,
                model=model,
                cfg=cfg,
                cancel=cancel,
            )
            _on_chunk_done(plan, segs_en, segs_vi)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _process_chunk_early,
                    plan,
                    full_flac=full_flac,
                    work=work,
                    model=model,
                    cfg=cfg,
                    cancel=cancel,
                ): plan
                for plan in plans
            }
            for fut in as_completed(futures):
                if cancel:
                    cancel.check()
                plan, segs_en, segs_vi = fut.result()
                _on_chunk_done(plan, segs_en, segs_vi)

    segments_en = merge_segments(groups_en)
    segments_vi = merge_segments(groups_vi)

    if not segments_en:
        raise EngineError(ErrorCode.TRANSCRIBE_FAILED, "Không nhận được đoạn lời nói nào")

    cache.save_segments(work / cache.TRANSCRIPT_EN, segments_en)
    cache.save_segments(work / cache.TRANSCRIPT_VI, segments_vi)

    if tracker:
        tracker.emit(len(plans), len(plans), f"Đã ghép {len(segments_en)} đoạn từ {len(plans)} phần")
    return segments_en, segments_vi
