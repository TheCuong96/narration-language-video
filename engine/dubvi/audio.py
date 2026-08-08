"""Audio extract + narration timeline (gap-borrow + mild tempo)."""

from __future__ import annotations

from pathlib import Path

from . import cache, events
from .ffmpeg import (
    concat_wavs,
    extract_audio_flac,
    fit_audio_to_duration,
    make_silence,
    mux_video,
    probe_duration,
    stretch_to_duration,
)
from .jobs import CancellationToken
from .models import AudioMode, Segment, Stage
from .system_info import get_logger

log = get_logger("dubvi.audio")

# Mild speed-up only after silence has been borrowed. 1.20 ≈ +20% (was 1.55).
MAX_TEMPO = 1.20
MIN_TEMPO = 0.90
# Keep a little pause between phrases when reclaiming silence.
MIN_GAP = 0.05


def extract_for_whisper(video: Path, work: Path, tracker=None) -> Path:
    flac = work / cache.AUDIO_FLAC
    if tracker:
        tracker.begin_stage(Stage.EXTRACTING, "Đang tách âm thanh (FLAC)")
        tracker.emit(0, 1, "FFmpeg đang tách audio…")
    else:
        events.stage(Stage.EXTRACTING, "Đang tách âm thanh (FLAC)")
    extract_audio_flac(video, flac)
    if tracker:
        tracker.emit(1, 1, "Đã tách âm thanh")
    else:
        events.progress(Stage.EXTRACTING, 1, 1, "Đã tách âm thanh")
    return flac


def _segment_windows(segments: list[Segment]) -> list[tuple[int, float, float]]:
    """Return (id, start, end) with sane minimum lengths."""
    out: list[tuple[int, float, float]] = []
    for s in segments:
        start = float(s.start)
        end = float(s.end)
        if end <= start:
            end = start + 0.3
        out.append((s.id, start, end))
    return out


def allocate_speech_targets(
    segments: list[Segment],
    natural_durs: dict[int, float],
    video_duration: float,
    *,
    max_tempo: float = MAX_TEMPO,
    min_gap: float = MIN_GAP,
) -> dict[int, float]:
    """
    Assign each segment a target play duration.

    Strategy:
    1. Start from the original EN time slot.
    2. If TTS is longer, borrow from following silence gaps (keep min_gap).
    3. Only residual mismatch is left for mild atempo (≤ max_tempo) + spill.
    """
    wins = _segment_windows(segments)
    if not wins:
        return {}

    n = len(wins)
    slots = [max(end - start, 0.2) for _, start, end in wins]
    natural = [
        max(float(natural_durs.get(sid, slots[i])), 0.05) for i, (sid, _, _) in enumerate(wins)
    ]

    # Silence after each segment (before next speech / end of video)
    gaps_after = [0.0] * n
    for i in range(n - 1):
        gaps_after[i] = max(0.0, wins[i + 1][1] - wins[i][2])
    gaps_after[n - 1] = max(0.0, float(video_duration) - wins[n - 1][2])

    # Borrowable silence (preserve a small pause between phrases)
    borrowable = [max(0.0, g - min_gap) for g in gaps_after]
    # Trailing silence can be fully used
    if n:
        borrowable[n - 1] = gaps_after[n - 1]

    targets = list(slots)

    for i in range(n):
        need = natural[i] - targets[i]
        if need <= 0.02:
            continue
        # Prefer immediate following gap, then later gaps
        for j in range(i, n):
            if need <= 0.001:
                break
            take = min(need, borrowable[j])
            if take <= 0:
                continue
            borrowable[j] -= take
            targets[i] += take
            need -= take

    # Anything still longer than target will be handled by mild tempo + spill.
    # Cap implied tempo hint: expand target to natural/max_tempo when possible
    # by using leftover borrowable (second pass, proportional leftovers).
    leftover = sum(borrowable)
    if leftover > 0.01:
        soft_deficits = []
        for i in range(n):
            min_fit = natural[i] / max(max_tempo, 1.01)
            soft_deficits.append(max(0.0, min_fit - targets[i]))
        total_soft = sum(soft_deficits)
        if total_soft > 0:
            give = min(leftover, total_soft)
            for i in range(n):
                if soft_deficits[i] <= 0:
                    continue
                extra = soft_deficits[i] / total_soft * give
                targets[i] += extra

    return {wins[i][0]: targets[i] for i in range(n)}


def build_narration(
    segments: list[Segment],
    work: Path,
    video_duration: float,
    mp3_paths: dict[int, Path],
    *,
    cancel: CancellationToken | None = None,
    tracker=None,
) -> Path:
    """
    Build full narration WAV aligned to original timestamps.

    Prefer natural speaking rate: borrow silence gaps to give long Vietnamese
    lines more room, then apply only mild atempo (≤ ~1.20×). Remaining overflow
    still spills into following gaps (no hard trim). If the finished timeline is
    still longer than the video, speed up the whole narration so nothing is cut
    off at mux time.
    """
    narration = work / cache.NARRATION
    if narration.exists() and narration.stat().st_size > 0:
        events.log("Dùng cache narration.wav")
        return narration

    fitted_dir = work / cache.FITTED_DIR
    fitted_dir.mkdir(parents=True, exist_ok=True)
    if tracker:
        tracker.begin_stage(Stage.ALIGNING, "Đang căn thời gian giọng đọc")
    else:
        events.stage(Stage.ALIGNING, "Đang căn thời gian giọng đọc")

    # Measure natural TTS lengths, then allocate expanded targets from silence
    natural_durs: dict[int, float] = {}
    for s in segments:
        mp3 = mp3_paths.get(s.id)
        if mp3 and mp3.exists():
            d = probe_duration(mp3)
            if d > 0:
                natural_durs[s.id] = d

    targets = allocate_speech_targets(segments, natural_durs, video_duration)
    if natural_durs:
        sped = 0
        for s in segments:
            nat = natural_durs.get(s.id)
            tgt = targets.get(s.id)
            if nat and tgt and nat > tgt * 1.02:
                sped += 1
        events.log(
            f"Căn giờ mềm: {len(natural_durs)} đoạn TTS, "
            f"{sped} đoạn cần tăng tốc nhẹ (≤{MAX_TEMPO:.2f}×), còn lại giữ nhịp tự nhiên"
        )

    pieces: list[Path] = []
    cursor = 0.0
    spill = 0.0
    total = len(segments)

    for idx, s in enumerate(segments):
        if cancel:
            cancel.check()

        start = float(s.start)
        end = float(s.end)
        if end <= start:
            end = start + 0.3
        slot = max(end - start, 0.2)
        target = max(targets.get(s.id, slot), 0.2)

        gap = start - cursor
        if spill > 0 and gap > 0:
            used = min(spill, gap)
            spill -= used
            cursor += used
            gap = start - cursor

        if gap > 0.02:
            sil = fitted_dir / f"sil_{idx:04d}.wav"
            if not sil.exists():
                make_silence(sil, gap)
            pieces.append(sil)
            cursor = start

        fitted = fitted_dir / f"{s.id:04d}.wav"
        mp3 = mp3_paths.get(s.id)

        if mp3 and mp3.exists():
            if not fitted.exists():
                actual = stretch_to_duration(
                    mp3,
                    fitted,
                    target,
                    allow_spill=True,
                    max_tempo=MAX_TEMPO,
                    min_tempo=MIN_TEMPO,
                    fit_slack=0.0,
                )
            else:
                actual = probe_duration(fitted) or target
            pieces.append(fitted)
            # Advance by played speech; spill eats the next silence
            if actual > target + 0.05:
                spill += actual - target
                cursor += actual
            else:
                # Prefer original end when we fit; if target grew into gap, use played length
                cursor = max(end, cursor + actual)
        else:
            if not fitted.exists():
                make_silence(fitted, target)
            pieces.append(fitted)
            cursor = max(end, cursor + target)

        if tracker:
            tracker.emit(idx + 1, max(total, 1), f"Căn thời gian {idx + 1}/{total}")
        elif (idx + 1) % 10 == 0 or idx + 1 == total:
            events.progress(Stage.ALIGNING, idx + 1, total)

    if cursor < video_duration - 0.05:
        sil = fitted_dir / "sil_end.wav"
        rest = video_duration - cursor
        if rest > 0.02:
            if not sil.exists():
                make_silence(sil, rest)
            pieces.append(sil)

    list_file = work / "concat.txt"
    concat_wavs(pieces, list_file, narration)

    # Final safety net: mux uses -shortest, so a longer narration would lose its
    # tail. Speed up the full track (never hard-trim speech) to match the video.
    narr_dur = probe_duration(narration)
    if narr_dur > video_duration + 0.05 and video_duration > 0.05:
        tempo = narr_dur / video_duration
        events.log(
            f"Giọng đọc dài hơn video ({narr_dur:.1f}s > {video_duration:.1f}s) — "
            f"tăng tốc toàn bộ {tempo:.2f}× để giữ đủ nội dung"
        )
        if tracker:
            tracker.emit(
                max(total, 1),
                max(total, 1),
                f"Tăng tốc giọng đọc {tempo:.2f}× để khớp video",
            )
        fit_audio_to_duration(narration, narration, video_duration)

    if tracker:
        tracker.emit(max(total, 1), max(total, 1), "Đã căn thời gian")
    else:
        events.progress(Stage.ALIGNING, total, total, "Đã căn thời gian")
    return narration


def mux(
    video: Path,
    narration: Path,
    output: Path,
    *,
    audio_mode: AudioMode | str = AudioMode.VI_ONLY,
    mix_original_db: float = -18.0,
    allow_reencode: bool = True,
    tracker=None,
) -> None:
    mode = audio_mode.value if isinstance(audio_mode, AudioMode) else audio_mode
    if tracker:
        tracker.begin_stage(Stage.MUXING, f"Đang ghép video ({mode}) → {output.name}")
        tracker.emit(0, 1, "FFmpeg đang ghép…")
    else:
        events.stage(Stage.MUXING, f"Đang ghép video ({mode}) → {output.name}")
    mux_video(
        video,
        narration,
        output,
        audio_mode=audio_mode,
        mix_original_db=mix_original_db,
        allow_reencode=allow_reencode,
    )
    if tracker:
        tracker.emit(1, 1, "Ghép xong")
    else:
        events.progress(Stage.MUXING, 1, 1, "Ghép xong")
