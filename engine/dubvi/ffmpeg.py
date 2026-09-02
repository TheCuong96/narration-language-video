"""FFmpeg / ffprobe helpers — no shell=True, array argv only."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from .models import ErrorCode
from .system_info import EngineError, get_logger

log = get_logger("dubvi.ffmpeg")


def _bundled_bin_dir() -> Path | None:
    """
    Look for bundled ffmpeg next to the frozen exe or via DUBVI_FFMPEG_DIR.
    Layout (future Tauri): resources/bin/ffmpeg.exe
    """
    env = os.environ.get("DUBVI_FFMPEG_DIR")
    if env:
        p = Path(env)
        if p.is_dir():
            return p

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "bin")
            candidates.append(Path(meipass))
        candidates.append(Path(sys.executable).resolve().parent / "bin")
        candidates.append(Path(sys.executable).resolve().parent)
    # Dev: engine/../resources/bin or repo resources/bin
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / "bin")
    candidates.append(here.parent.parent / "resources" / "bin")

    for c in candidates:
        exe = c / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        if exe.is_file():
            return c
    return None


def ffmpeg_path() -> str:
    bundled = _bundled_bin_dir()
    if bundled:
        name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        return str(bundled / name)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise EngineError(ErrorCode.FFMPEG_MISSING, "Không tìm thấy ffmpeg (bundle hoặc PATH)")


def ffprobe_path() -> str:
    bundled = _bundled_bin_dir()
    if bundled:
        name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
        p = bundled / name
        if p.is_file():
            return str(p)
    found = shutil.which("ffprobe")
    if found:
        return found
    raise EngineError(ErrorCode.FFPROBE_MISSING, "Không tìm thấy ffprobe (bundle hoặc PATH)")


def which_or_bundled(name: str, resolved: str | None = None) -> str | None:
    try:
        if name == "ffmpeg":
            return resolved or ffmpeg_path()
        if name == "ffprobe":
            return resolved or ffprobe_path()
    except EngineError:
        return shutil.which(name)
    return shutil.which(name)


def run_ffmpeg(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    """Run ffmpeg/ffprobe with list argv. Never uses shell=True."""
    cmd = list(args)
    log.debug("run: %s", " ".join(cmd))
    kwargs: dict = {
        "check": check,
        "shell": False,
        # Always capture stderr so failures include FFmpeg's real message.
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
    else:
        kwargs["stdout"] = subprocess.DEVNULL
    try:
        return subprocess.run(cmd, **kwargs)
    except FileNotFoundError as e:
        raise EngineError(ErrorCode.FFMPEG_MISSING, f"Không chạy được: {cmd[0]}") from e
    except subprocess.CalledProcessError as e:
        err = ""
        if e.stderr:
            err = e.stderr.strip()
            # Keep the most useful tail (format guess / encoder errors live at end).
            if len(err) > 800:
                err = err[-800:]
        raise EngineError(
            ErrorCode.INTERNAL,
            f"FFmpeg thất bại (exit {e.returncode}): {err or cmd[0]}",
        ) from e


def run_ffmpeg_with_progress(
    args: list[str],
    *,
    duration_sec: float = 0.0,
    on_progress: Callable[[float], None] | None = None,
) -> None:
    """
    Run FFmpeg and report 0..1 progress via -progress pipe:1 (and stderr time= fallback).

    Used for long mux/re-encode steps so the UI does not sit at 0%.
    """
    cmd = list(args)
    if len(cmd) >= 2:
        out_idx = len(cmd) - 1
        cmd = cmd[:out_idx] + ["-progress", "pipe:1", "-nostats"] + cmd[out_idx:]

    log.debug("run (progress): %s", " ".join(cmd))
    stderr_lines: list[str] = []
    last_frac = -1.0
    duration = max(float(duration_sec or 0), 0.0)
    time_re = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")

    def _emit(frac: float) -> None:
        nonlocal last_frac
        f = max(0.0, min(1.0, frac))
        if on_progress and (f >= last_frac + 0.02 or f >= 0.99):
            last_frac = f
            on_progress(f)

    def _emit_from_seconds(sec: float) -> None:
        if duration > 0:
            _emit(sec / duration)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except FileNotFoundError as e:
        raise EngineError(ErrorCode.FFMPEG_MISSING, f"Không chạy được: {cmd[0]}") from e

    def _read_stdout() -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_ms="):
                try:
                    ms = int(line.split("=", 1)[1])
                    _emit_from_seconds(ms / 1_000_000.0)
                except ValueError:
                    pass

    def _read_stderr() -> None:
        if proc.stderr is None:
            return
        for line in proc.stderr:
            stderr_lines.append(line)
            m = time_re.search(line)
            if m:
                h, mnt, sec = int(m.group(1)), int(m.group(2)), float(m.group(3))
                _emit_from_seconds(h * 3600 + mnt * 60 + sec)

    t_out = threading.Thread(target=_read_stdout, daemon=True)
    t_err = threading.Thread(target=_read_stderr, daemon=True)
    t_out.start()
    t_err.start()
    code = proc.wait()
    t_out.join(timeout=2)
    t_err.join(timeout=2)

    if code != 0:
        err = "".join(stderr_lines).strip()
        if len(err) > 800:
            err = err[-800:]
        raise EngineError(
            ErrorCode.INTERNAL,
            f"FFmpeg thất bại (exit {code}): {err or cmd[0]}",
        )
    if on_progress:
        on_progress(1.0)


def _video_codec_name(video: Path) -> str:
    info = probe_streams(video)
    for s in info.get("streams") or []:
        if s.get("codec_type") == "video":
            return str(s.get("codec_name") or "")
    return ""


def _video_stream_args(vcodec: str, *, reencode: bool) -> list[str]:
    if reencode:
        return [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
        ]
    args = ["-c:v", "copy"]
    if vcodec == "av1":
        args += ["-tag:v", "av01"]
    elif vcodec in ("hevc", "h265"):
        args += ["-tag:v", "hvc1"]
    return args


def probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            ffprobe_path(),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    ).strip()
    if not out:
        return 0.0
    return float(out)


def extract_video_segment(
    src: Path,
    dst: Path,
    start_sec: float,
    end_sec: float,
    *,
    copy: bool = True,
) -> dict:
    """
    Clone [start_sec, end_sec) from src into a new video file at dst.

    Tries stream copy first (fast). Falls back to H.264/AAC re-encode if copy fails
    (e.g. keyframe / container mismatch). Source file is never modified.
    """
    if start_sec < 0:
        raise EngineError(ErrorCode.INVALID_ARGS, "Thời điểm bắt đầu phải ≥ 0")
    if end_sec <= start_sec:
        raise EngineError(
            ErrorCode.INVALID_ARGS,
            "Thời điểm kết thúc phải lớn hơn thời điểm bắt đầu",
        )

    src = src.expanduser().resolve()
    if not src.is_file():
        raise EngineError(ErrorCode.INPUT_NOT_FOUND, f"Không tìm thấy video: {src}")

    total = probe_duration(src)
    if total > 0 and start_sec >= total:
        raise EngineError(
            ErrorCode.INVALID_ARGS,
            f"Bắt đầu ({start_sec:.2f}s) vượt quá độ dài video ({total:.2f}s)",
        )
    if total > 0 and end_sec > total + 0.05:
        end_sec = total

    duration = end_sec - start_sec
    if duration < 0.05:
        raise EngineError(ErrorCode.INVALID_ARGS, "Đoạn cắt quá ngắn (< 0.05s)")

    dst = dst.expanduser().resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f"{dst.stem}.partial{dst.suffix}")

    used_copy = False
    if copy:
        try:
            run_ffmpeg(
                [
                    ffmpeg_path(),
                    "-y",
                    "-ss",
                    f"{start_sec:.3f}",
                    "-i",
                    str(src),
                    "-t",
                    f"{duration:.3f}",
                    "-map",
                    "0",
                    "-c",
                    "copy",
                    "-avoid_negative_ts",
                    "make_zero",
                    str(tmp),
                ]
            )
            used_copy = True
        except EngineError:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            used_copy = False

    if not used_copy:
        run_ffmpeg(
            [
                ffmpeg_path(),
                "-y",
                "-ss",
                f"{start_sec:.3f}",
                "-i",
                str(src),
                "-t",
                f"{duration:.3f}",
                "-map",
                "0:v:0?",
                "-map",
                "0:a:0?",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(tmp),
            ]
        )

    if dst.exists():
        dst.unlink()
    tmp.replace(dst)

    out_dur = probe_duration(dst)
    return {
        "path": str(dst),
        "source": str(src),
        "start_sec": start_sec,
        "end_sec": end_sec,
        "duration_sec": out_dur if out_dur > 0 else duration,
        "copied": used_copy,
    }


def extract_audio_segment(
    src: Path,
    dst: Path,
    start_sec: float,
    end_sec: float,
    *,
    sample_rate: int = 16000,
) -> None:
    """Extract [start_sec, end_sec) from an audio file (FLAC/WAV) for chunk processing."""
    if start_sec < 0:
        raise EngineError(ErrorCode.INVALID_ARGS, "Thời điểm bắt đầu phải ≥ 0")
    if end_sec <= start_sec:
        raise EngineError(
            ErrorCode.INVALID_ARGS,
            "Thời điểm kết thúc phải lớn hơn thời điểm bắt đầu",
        )
    duration = end_sec - start_sec
    if duration < 0.05:
        raise EngineError(ErrorCode.INVALID_ARGS, "Đoạn audio quá ngắn (< 0.05s)")

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size > 0:
        return
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-i",
            str(src),
            "-t",
            f"{duration:.3f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "flac",
            str(dst),
        ]
    )


def detect_silence_midpoints(
    audio: Path,
    *,
    noise_db: float = -35.0,
    min_silence_sec: float = 0.35,
    min_silence_gap: float = 0.5,
) -> list[float]:
    """
    Return approximate midpoints of silent regions (seconds).

    Used to snap chunk boundaries away from speech. Returns [] on failure.
    """
    import re

    af = f"silencedetect=noise={noise_db}dB:d={min_silence_sec}"
    try:
        proc = subprocess.run(
            [
                ffmpeg_path(),
                "-hide_banner",
                "-i",
                str(audio),
                "-af",
                af,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
    except Exception as e:
        log.warning("silencedetect failed: %s", e)
        return []

    stderr = proc.stderr or ""
    starts: list[float] = []
    ends: list[float] = []
    for line in stderr.splitlines():
        m_start = re.search(r"silence_start:\s*([0-9.]+)", line)
        if m_start:
            starts.append(float(m_start.group(1)))
        m_end = re.search(r"silence_end:\s*([0-9.]+)", line)
        if m_end:
            ends.append(float(m_end.group(1)))

    midpoints: list[float] = []
    for i, start in enumerate(starts):
        end = ends[i] if i < len(ends) else start + min_silence_gap
        if end - start >= min_silence_gap * 0.5:
            midpoints.append((start + end) / 2.0)
    return midpoints


def extract_audio_flac(video: Path, flac_out: Path) -> None:
    """
    Extract mono 16 kHz FLAC for Whisper — smaller than PCM WAV,
    Unicode / spaces in paths supported via Path str args.
    """
    flac_out.parent.mkdir(parents=True, exist_ok=True)
    if flac_out.exists() and flac_out.stat().st_size > 0:
        return
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "flac",
            str(flac_out),
        ]
    )


def make_silence(dst: Path, duration_sec: float, *, sample_rate: int = 24000) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dur = max(duration_sec, 0.05)
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=mono",
            "-t",
            f"{dur:.3f}",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ]
    )


def atempo_filter_chain(tempo: float) -> list[str]:
    """Build stacked atempo filters (each filter only accepts 0.5–2.0)."""
    filters: list[str] = []
    t = max(tempo, 1e-6)
    while t < 0.5:
        filters.append("atempo=0.5")
        t /= 0.5
    while t > 2.0:
        filters.append("atempo=2.0")
        t /= 2.0
    filters.append(f"atempo={t:.4f}")
    return filters


def _pad_trim_wav(
    src: Path,
    dst: Path,
    target_sec: float,
    *,
    sample_rate: int = 24000,
) -> float:
    """Copy speech at 1× and pad/trim to target_sec. Never changes tempo."""
    target = max(float(target_sec), 0.05)
    out = dst
    tmp: Path | None = None
    if src.resolve() == dst.resolve():
        tmp = dst.with_name(dst.stem + ".__pad__.wav")
        out = tmp
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-i",
            str(src),
            "-af",
            f"apad=whole_dur={target:.3f},atrim=0:{target:.3f}",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(out),
        ]
    )
    if tmp is not None:
        tmp.replace(dst)
    actual = probe_duration(dst)
    return actual if actual > 0 else target


def stretch_to_duration(
    src: Path,
    dst: Path,
    target_sec: float,
    *,
    allow_spill: bool = False,
    max_tempo: float = 8.0,
    min_tempo: float = 1.0,
    fit_slack: float = 0.0,
) -> float:
    """
    Fit audio into target_sec using atempo + pad.

    - Longer than target → speed up (up to max_tempo).
    - Shorter than target → keep 1× (never below min_tempo) and pad silence.
    - allow_spill=True keeps leftover length after max speedup (legacy); strict
      align uses allow_spill=False so output duration == target_sec.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    target = max(float(target_sec), 0.05)
    floor = max(float(min_tempo), 1.0)
    dur = probe_duration(src)
    if dur <= 0:
        make_silence(dst, target)
        return target

    # Never slow speech to fill time: 1× + silence when it already fits.
    if dur <= target + 0.05:
        return _pad_trim_wav(src, dst, target)

    slack = max(0.0, min(fit_slack, 0.5))
    usable = max(target * (1.0 - slack), 0.05)
    tempo = dur / usable if usable > 0 else 1.0
    tempo = max(floor, min(tempo, max_tempo))
    if tempo <= 1.01:
        return _pad_trim_wav(src, dst, target)

    filters = atempo_filter_chain(tempo)
    sped_dur = dur / tempo

    if sped_dur <= target + 0.02 or not allow_spill:
        # Strict fit (default): nail exact slot length.
        af = ",".join(filters) + f",apad=whole_dur={target:.3f},atrim=0:{target:.3f}"
        out_dur = target
    else:
        # Legacy spill: keep full speech after capped speedup.
        af = ",".join(filters)
        out_dur = sped_dur

    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-i",
            str(src),
            "-af",
            af,
            "-ar",
            "24000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ]
    )
    actual = probe_duration(dst)
    return actual if actual > 0 else out_dur


def fit_audio_to_duration(
    src: Path,
    dst: Path,
    target_sec: float,
    *,
    sample_rate: int = 24000,
) -> float:
    """
    Match duration to target_sec without ever slowing speech.

    Longer than target → speed up (stacked atempo) so full content still fits.
    Shorter than target → keep 1× and pad silence.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    target = max(float(target_sec), 0.05)
    dur = probe_duration(src)
    if dur <= 0:
        make_silence(dst, target, sample_rate=sample_rate)
        return target

    if dur <= target + 0.05:
        if dur >= target - 0.01 and src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
            return dur
        return _pad_trim_wav(src, dst, target, sample_rate=sample_rate)

    tempo = max(1.0, dur / target)
    filters = atempo_filter_chain(tempo)
    af = ",".join(filters) + f",apad=whole_dur={target:.3f},atrim=0:{target:.3f}"

    out = dst
    tmp: Path | None = None
    if src.resolve() == dst.resolve():
        tmp = dst.with_name(dst.stem + ".__fit__.wav")
        out = tmp

    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-i",
            str(src),
            "-af",
            af,
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(out),
        ]
    )
    if tmp is not None:
        tmp.replace(dst)

    actual = probe_duration(dst)
    return actual if actual > 0 else target


def concat_wavs(pieces: list[Path], list_file: Path, narration: Path) -> None:
    list_file.parent.mkdir(parents=True, exist_ok=True)
    with list_file.open("w", encoding="utf-8") as f:
        for p in pieces:
            # FFmpeg concat demuxer: escape single quotes in path
            escaped = str(p.resolve()).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    run_ffmpeg(
        [
            ffmpeg_path(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:a",
            "pcm_s16le",
            str(narration),
        ]
    )


def probe_streams(path: Path) -> dict:
    """Return ffprobe JSON for format + streams."""
    out = subprocess.check_output(
        [
            ffprobe_path(),
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration:stream=index,codec_type,codec_name,codec_tag_string",
            "-of",
            "json",
            str(path),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    import json

    return json.loads(out or "{}")


def plan_mux(
    video: Path,
    output: Path,
    audio_mode: "AudioMode",
    *,
    allow_reencode: bool = True,
) -> "MuxPlan":
    """Decide whether video stream can be copied into the output container."""
    from .models import COPY_FRIENDLY_CONTAINERS, AudioMode, MuxPlan

    info = probe_streams(video)
    streams = info.get("streams") or []
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    astreams = [s for s in streams if s.get("codec_type") == "audio"]
    vcodec = (vstreams[0].get("codec_name") if vstreams else "") or ""
    out_suffix = output.suffix.lower() or ".mp4"

    # Dual-track is more reliable in MKV; if user asked dual on .mp4 we still try.
    copy_ok = True
    reason = "Sao chép video stream (không re-encode)"

    if out_suffix not in COPY_FRIENDLY_CONTAINERS and out_suffix != ".webm":
        # avi etc. as output — prefer remux to mp4
        copy_ok = False
        reason = f"Container đầu ra {out_suffix} kém tương thích — cần xử lý lại video"

    # VP8/VP9/Theora → MP4 usually needs re-encode. AV1/HEVC can remux with tags.
    if out_suffix == ".mp4" and vcodec in {"vp8", "vp9", "theora"}:
        copy_ok = False
        reason = (
            f"Codec video '{vcodec}' không copy được sang {out_suffix} — "
            "bắt buộc re-encode video"
        )
    elif out_suffix == ".mp4" and vcodec in {"av1", "hevc", "h265"}:
        copy_ok = True
        reason = (
            f"Sao chép {vcodec} sang MP4 (remux, tag container — không re-encode)"
        )
    elif out_suffix == ".mp4" and vcodec == "mpeg4":
        copy_ok = False
        reason = f"Codec video '{vcodec}' — re-encode sang H.264 cho tương thích MP4"

    if audio_mode == AudioMode.DUAL_TRACK and not astreams:
        # Still fine — only VI track
        pass

    if not copy_ok and not allow_reencode:
        raise EngineError(
            ErrorCode.MUX_FAILED,
            f"Cần re-encode video nhưng bị tắt: {reason}",
        )

    return MuxPlan(
        video_codec_copy=copy_ok,
        reencode_video=not copy_ok,
        reason=reason,
        output_suffix=out_suffix,
        audio_mode=audio_mode,
    )


def mux_video(
    video: Path,
    narration: Path,
    output: Path,
    *,
    audio_mode: "AudioMode | str" = "vi_only",
    mix_original_db: float = -18.0,
    allow_reencode: bool = True,
    duration_sec: float = 0.0,
    on_progress: Callable[[float], None] | None = None,
) -> "MuxPlan":
    """
    Mux narration onto video without modifying the source file.

    Modes:
      vi_only     — map VI audio only, copy video when possible
      dual_track  — original audio + VI (titles/language metadata)
      mix         — amix VI with ducked original
    """
    from . import events
    from .models import AudioMode, MuxPlan

    if isinstance(audio_mode, str):
        audio_mode = AudioMode(audio_mode)

    output.parent.mkdir(parents=True, exist_ok=True)
    plan = plan_mux(video, output, audio_mode, allow_reencode=allow_reencode)
    vcodec = _video_codec_name(video)
    duration = duration_sec if duration_sec > 0 else probe_duration(video)

    if plan.reencode_video:
        mins = duration / 60.0 if duration > 0 else 0
        events.warning(
            "REENCODE_REQUIRED",
            plan.reason,
            input=str(video),
            output=str(output),
            audio_mode=audio_mode.value,
        )
        if mins >= 5:
            events.log(
                f"Re-encode video ~{mins:.0f} phút — có thể mất vài chục phút trên CPU; "
                "thanh tiến độ sẽ cập nhật dần",
                level="warn",
            )
    else:
        events.log(plan.reason)

    tmp = output.with_name(f"{output.stem}.partial{output.suffix}")

    def _build_cmd(*, reencode: bool) -> list[str]:
        cmd: list[str] = [ffmpeg_path(), "-y", "-i", str(video), "-i", str(narration)]
        vcodec_args = _video_stream_args(vcodec, reencode=reencode)
        movflags = ["-movflags", "+faststart"] if output.suffix.lower() == ".mp4" else []

        if audio_mode == AudioMode.VI_ONLY:
            cmd += [
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                *vcodec_args,
                *movflags,
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(tmp),
            ]
        elif audio_mode == AudioMode.DUAL_TRACK:
            cmd += [
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-map",
                "1:a:0",
                *vcodec_args,
                *movflags,
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-metadata:s:a:0",
                "language=eng",
                "-metadata:s:a:0",
                "title=Original",
                "-metadata:s:a:1",
                "language=vie",
                "-metadata:s:a:1",
                "title=Vietnamese",
                "-shortest",
                str(tmp),
            ]
        elif audio_mode == AudioMode.MIX:
            info = probe_streams(video)
            has_audio = any(s.get("codec_type") == "audio" for s in (info.get("streams") or []))
            if not has_audio:
                events.warning(
                    "MIX_NO_ORIGINAL_AUDIO",
                    "Video không có audio gốc — xuất chỉ giọng Việt",
                    input=str(video),
                )
                cmd += [
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    *vcodec_args,
                    *movflags,
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    str(tmp),
                ]
            else:
                duck = 10 ** (mix_original_db / 20.0)
                filter_complex = (
                    f"[0:a]volume={duck:.6f},aformat=sample_rates=48000:channel_layouts=stereo[orig];"
                    f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo[vi];"
                    f"[orig][vi]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                )
                cmd += [
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "0:v:0",
                    "-map",
                    "[aout]",
                    *vcodec_args,
                    *movflags,
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    str(tmp),
                ]
        else:
            raise EngineError(ErrorCode.INVALID_ARGS, f"Audio mode không hỗ trợ: {audio_mode}")
        return cmd

    try:
        reencode = plan.reencode_video
        try:
            run_ffmpeg_with_progress(
                _build_cmd(reencode=reencode),
                duration_sec=duration,
                on_progress=on_progress,
            )
        except EngineError:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            if not reencode and allow_reencode:
                events.log(
                    "Remux (copy) thất bại — thử re-encode H.264…",
                    level="warn",
                )
                reencode = True
                run_ffmpeg_with_progress(
                    _build_cmd(reencode=True),
                    duration_sec=duration,
                    on_progress=on_progress,
                )
                plan = MuxPlan(
                    video_codec_copy=False,
                    reencode_video=True,
                    reason="Remux thất bại — đã re-encode H.264",
                    output_suffix=plan.output_suffix,
                    audio_mode=plan.audio_mode,
                )
            else:
                raise

        if output.exists():
            output.unlink()
        tmp.replace(output)
        return plan
    except EngineError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise
    except Exception as e:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise EngineError(ErrorCode.MUX_FAILED, f"Không ghép được video: {output.name}") from e
