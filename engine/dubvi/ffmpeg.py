"""FFmpeg / ffprobe helpers — no shell=True, array argv only."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
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


def stretch_to_duration(
    src: Path,
    dst: Path,
    target_sec: float,
    *,
    allow_spill: bool = True,
    max_tempo: float = 1.20,
    min_tempo: float = 0.90,
    fit_slack: float = 0.0,
) -> float:
    """
    Fit audio into target_sec using atempo + pad.

    Prefer near-natural speed: caller should expand target_sec by borrowing
    silence gaps before relying on tempo. Default max_tempo is mild (~20%).

    If allow_spill and audio is still longer after max speedup, do NOT trim speech —
    return the actual duration (caller may spill into following gaps).
    Returns the duration written to dst.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    dur = probe_duration(src)
    if dur <= 0:
        make_silence(dst, target_sec)
        return target_sec

    # fit_slack=0 → aim for full target; >0 (e.g. 0.05) leaves a tiny pad margin
    slack = max(0.0, min(fit_slack, 0.5))
    usable = max(target_sec * (1.0 - slack), 0.05)
    tempo = dur / usable if usable > 0 else 1.0
    tempo = max(min_tempo, min(tempo, max_tempo))

    filters: list[str] = []
    t = tempo
    while t < 0.5:
        filters.append("atempo=0.5")
        t /= 0.5
    while t > 2.0:
        filters.append("atempo=2.0")
        t /= 2.0
    filters.append(f"atempo={t:.4f}")

    sped_dur = dur / tempo
    if sped_dur <= target_sec + 0.02:
        # Pad to exact slot
        af = ",".join(filters) + f",apad=whole_dur={target_sec:.3f},atrim=0:{target_sec:.3f}"
        out_dur = target_sec
    elif allow_spill:
        # Keep full speech — no atrrim on the end
        af = ",".join(filters)
        out_dur = sped_dur
    else:
        # Legacy hard trim (not preferred)
        af = ",".join(filters) + f",atrim=0:{target_sec:.3f},apad=whole_dur={target_sec:.3f}"
        out_dur = target_sec

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
    # Verify
    actual = probe_duration(dst)
    return actual if actual > 0 else out_dur


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

    # WebM/VP9/AV1 in MP4 often cannot copy
    if out_suffix == ".mp4" and vcodec in {"vp8", "vp9", "av1", "theora", "mpeg4"}:
        # mpeg4 (ASP) sometimes copies; vp*/av1 into mp4 usually no
        if vcodec in {"vp8", "vp9", "av1", "theora"}:
            copy_ok = False
            reason = (
                f"Codec video '{vcodec}' không copy được sang {out_suffix} — "
                "bắt buộc re-encode video"
            )

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

    if plan.reencode_video:
        events.warning(
            "REENCODE_REQUIRED",
            plan.reason,
            input=str(video),
            output=str(output),
            audio_mode=audio_mode.value,
        )
    else:
        events.log(plan.reason)

    tmp = output.with_name(f"{output.stem}.partial{output.suffix}")
    cmd: list[str] = [ffmpeg_path(), "-y", "-i", str(video), "-i", str(narration)]

    vcodec_args = (
        ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
        if plan.reencode_video
        else ["-c:v", "copy"]
    )

    try:
        if audio_mode == AudioMode.VI_ONLY:
            cmd += [
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                *vcodec_args,
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(tmp),
            ]
        elif audio_mode == AudioMode.DUAL_TRACK:
            # Keep original audio (if any) + Vietnamese
            cmd += [
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-map",
                "1:a:0",
                *vcodec_args,
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
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    str(tmp),
                ]
        else:
            raise EngineError(ErrorCode.INVALID_ARGS, f"Audio mode không hỗ trợ: {audio_mode}")

        run_ffmpeg(cmd)
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
