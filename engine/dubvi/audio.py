"""Audio extract + narration timeline (strict slot fit to original timestamps)."""

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

# Never slow speech down. Default is 1×; speed up only when the next line (or
# the end of the video) would be overlapped.
MIN_TEMPO = 1.0
# Practical ceiling for stacked atempo (≈ 8×); enough for long VI lines in short slots.
MAX_TEMPO = 8.0


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
    """Return (id, start, end) with sane minimum lengths, in time order."""
    out: list[tuple[int, float, float]] = []
    for s in segments:
        start = float(s.start)
        end = float(s.end)
        if end <= start:
            end = start + 0.3
        out.append((s.id, start, end))
    out.sort(key=lambda w: (w[1], w[2], w[0]))
    return out


def _play_deadlines(segments: list[Segment], video_duration: float) -> dict[int, float]:
    """Latest time each line may occupy at 1×: next line's start, or video end."""
    wins = _segment_windows(segments)
    out: dict[int, float] = {}
    for i, (sid, start, end) in enumerate(wins):
        if i + 1 < len(wins):
            deadline = wins[i + 1][1]
        elif video_duration > start + 0.05:
            deadline = video_duration
        else:
            deadline = end
        out[sid] = max(deadline, start + 0.2)
    return out


def allocate_speech_targets(
    segments: list[Segment],
    natural_durs: dict[int, float] | None = None,
    video_duration: float = 0.0,
    *,
    max_tempo: float = MAX_TEMPO,
    min_gap: float = 0.0,
) -> dict[int, float]:
    """
    Max play duration per segment at 1× before the next line (or video end).

    Lines still start at the original timestamp. Speech may run past the
    subtitle/Whisper ``end`` into the following gap; it is only sped up when
    it would overlap the next line. natural_durs / max_tempo / min_gap are
    accepted for call-site compatibility.
    """
    del natural_durs, max_tempo, min_gap
    deadlines = _play_deadlines(segments, video_duration)
    wins = _segment_windows(segments)
    return {sid: max(deadlines[sid] - start, 0.2) for sid, start, _end in wins}


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
    Build full narration WAV. Each line starts at the original timestamp.

    - Default tempo is 1× (never slowed to fill a long cue).
    - TTS may occupy the gap until the next line.
    - Speed up only when TTS would overlap the next line (or the video end).
    """
    narration = work / cache.NARRATION
    if narration.exists() and narration.stat().st_size > 0:
        if tracker:
            tracker.begin_stage(Stage.ALIGNING, "Kiểm tra narration đã căn giờ trong cache")
        events.log("Dùng cache narration")
        narr_dur = probe_duration(narration)
        if narr_dur > video_duration + 0.05 and video_duration > 0.05:
            tempo = narr_dur / video_duration
            events.log(
                f"Cache narration dài hơn video ({narr_dur:.1f}s > {video_duration:.1f}s) — "
                f"tăng tốc {tempo:.2f}× để giữ đủ nội dung"
            )
            fit_audio_to_duration(narration, narration, video_duration)
        elif (
            video_duration > 0.05
            and narr_dur > 0
            and narr_dur < video_duration - 0.05
        ):
            pad = work / "sil_cache_pad.wav"
            make_silence(pad, video_duration - narr_dur)
            tmp = work / "narration.__pad__.wav"
            concat_wavs([narration, pad], work / "concat_cache_pad.txt", tmp)
            tmp.replace(narration)
        if tracker:
            tracker.emit(1, 1, "Đã kiểm tra căn giờ từ cache")
        return narration

    fitted_dir = work / cache.FITTED_DIR
    fitted_dir.mkdir(parents=True, exist_ok=True)
    if tracker:
        tracker.begin_stage(Stage.ALIGNING, "Đang căn thời gian giọng đọc")
    else:
        events.stage(Stage.ALIGNING, "Đang căn thời gian giọng đọc")

    natural_durs: dict[int, float] = {}
    for s in segments:
        mp3 = mp3_paths.get(s.id)
        if mp3 and mp3.exists():
            d = probe_duration(mp3)
            if d > 0:
                natural_durs[s.id] = d

    targets = allocate_speech_targets(segments, natural_durs, video_duration)
    sped = 0
    kept = 0
    for s in segments:
        nat = natural_durs.get(s.id)
        tgt = targets.get(s.id)
        if nat and tgt:
            if nat > tgt * 1.02:
                sped += 1
            else:
                kept += 1
    events.log(
        f"Căn giờ 1×: {len(natural_durs)} đoạn TTS, "
        f"{kept} đoạn giữ tốc độ bình thường, "
        f"{sped} đoạn tăng tốc vì không đủ thời gian đến câu sau"
    )

    pieces: list[Path] = []
    cursor = 0.0
    ordered = sorted(segments, key=lambda s: (float(s.start), float(s.end), s.id))
    total = len(ordered)
    deadlines = _play_deadlines(ordered, video_duration)

    for idx, s in enumerate(ordered):
        if cancel:
            cancel.check()

        start = float(s.start)
        play_start = max(start, cursor)
        play_end = max(deadlines.get(s.id, start + 0.3), play_start + 0.2)
        slot = play_end - play_start

        gap = play_start - cursor
        if gap > 0.02:
            sil = fitted_dir / f"sil_{idx:04d}.wav"
            if not sil.exists():
                make_silence(sil, gap)
            pieces.append(sil)
            cursor = play_start

        fitted = fitted_dir / f"{s.id:04d}.wav"
        mp3 = mp3_paths.get(s.id)

        if mp3 and mp3.exists():
            if not fitted.exists():
                stretch_to_duration(
                    mp3,
                    fitted,
                    slot,
                    allow_spill=False,
                    max_tempo=MAX_TEMPO,
                    min_tempo=MIN_TEMPO,
                    fit_slack=0.0,
                )
            pieces.append(fitted)
        else:
            if not fitted.exists():
                make_silence(fitted, slot)
            pieces.append(fitted)

        cursor = play_end

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
            cursor = video_duration

    list_file = work / "concat.txt"
    concat_wavs(pieces, list_file, narration)

    # Safety: narration must match video length for mux (-shortest).
    narr_dur = probe_duration(narration)
    if video_duration > 0.05 and narr_dur > 0:
        if narr_dur > video_duration + 0.05:
            tempo = narr_dur / video_duration
            events.log(
                f"Giọng đọc dài hơn video ({narr_dur:.1f}s > {video_duration:.1f}s) — "
                f"tăng tốc toàn bộ {tempo:.2f}× để khớp"
            )
            if tracker:
                tracker.emit(
                    max(total, 1),
                    max(total, 1),
                    f"Tăng tốc giọng đọc {tempo:.2f}× để khớp video",
                )
            fit_audio_to_duration(narration, narration, video_duration)
        elif narr_dur < video_duration - 0.05:
            pad = fitted_dir / "sil_tail_fix.wav"
            make_silence(pad, video_duration - narr_dur)
            tmp = work / "narration.__pad__.wav"
            concat_wavs([narration, pad], work / "concat_pad.txt", tmp)
            tmp.replace(narration)

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
    duration = probe_duration(video)

    def _on_mux_progress(frac: float) -> None:
        pct = max(0, min(100, int(round(frac * 100))))
        msg = f"FFmpeg đang ghép… {pct}%"
        if tracker:
            tracker.emit(pct, 100, msg, force_frac=frac)
        else:
            events.progress(Stage.MUXING, pct, 100, msg)

    if tracker:
        tracker.begin_stage(Stage.MUXING, f"Đang ghép video ({mode}) → {output.name}")
        tracker.emit(0, 100, "Bắt đầu ghép video…")
    else:
        events.stage(Stage.MUXING, f"Đang ghép video ({mode}) → {output.name}")

    plan = mux_video(
        video,
        narration,
        output,
        audio_mode=audio_mode,
        mix_original_db=mix_original_db,
        allow_reencode=allow_reencode,
        duration_sec=duration,
        on_progress=_on_mux_progress,
    )

    if plan.reencode_video and duration >= 300 and tracker:
        events.log("Đã re-encode video — lần sau dùng nguồn H.264/AV1 remux sẽ nhanh hơn")

    if tracker:
        tracker.emit(100, 100, "Ghép xong")
    else:
        events.progress(Stage.MUXING, 100, 100, "Ghép xong")
