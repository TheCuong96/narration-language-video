"""Audio extract + narration timeline (spillover for long Vietnamese lines)."""

from __future__ import annotations

from pathlib import Path

from . import cache, events
from .ffmpeg import (
    concat_wavs,
    extract_audio_flac,
    make_silence,
    mux_video,
    probe_duration,
    stretch_to_duration,
)
from .jobs import CancellationToken
from .models import AudioMode, Segment, Stage
from .system_info import get_logger

log = get_logger("dubvi.audio")


def extract_for_whisper(video: Path, work: Path) -> Path:
    flac = work / cache.AUDIO_FLAC
    events.stage(Stage.EXTRACTING, "Đang tách âm thanh (FLAC)")
    extract_audio_flac(video, flac)
    events.progress(Stage.EXTRACTING, 1, 1, "Đã tách âm thanh")
    return flac


def build_narration(
    segments: list[Segment],
    work: Path,
    video_duration: float,
    mp3_paths: dict[int, Path],
    *,
    cancel: CancellationToken | None = None,
) -> Path:
    """
    Build full narration WAV aligned to original timestamps.

    If Vietnamese TTS is still longer after max atempo, keep the full sentence
    (no hard trim) and spill overflow into the following silence gap.
    """
    narration = work / cache.NARRATION
    if narration.exists() and narration.stat().st_size > 0:
        events.log("Dùng cache narration.wav")
        return narration

    fitted_dir = work / cache.FITTED_DIR
    fitted_dir.mkdir(parents=True, exist_ok=True)
    events.stage(Stage.ALIGNING, "Đang căn thời gian giọng đọc")

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
        target = max(end - start, 0.2)

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
                actual = stretch_to_duration(mp3, fitted, target, allow_spill=True)
            else:
                actual = probe_duration(fitted) or target
            pieces.append(fitted)
            if actual > target + 0.05:
                spill += actual - target
                cursor += actual
            else:
                cursor = end
        else:
            if not fitted.exists():
                make_silence(fitted, target)
            pieces.append(fitted)
            cursor = end

        if (idx + 1) % 10 == 0 or idx + 1 == total:
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
) -> None:
    mode = audio_mode.value if isinstance(audio_mode, AudioMode) else audio_mode
    events.stage(Stage.MUXING, f"Đang ghép video ({mode}) → {output.name}")
    mux_video(
        video,
        narration,
        output,
        audio_mode=audio_mode,
        mix_original_db=mix_original_db,
        allow_reencode=allow_reencode,
    )
    events.progress(Stage.MUXING, 1, 1, "Ghép xong")
