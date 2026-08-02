"""Probe media files for UI (duration, size) without loading Whisper."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .ffmpeg import extract_video_segment, probe_duration, probe_streams
from .models import VIDEO_EXTENSIONS, ErrorCode
from .queue import is_video_file
from .system_info import EngineError


def parse_timestamp(value: str | float | int) -> float:
    """Parse seconds as float, or HH:MM:SS / MM:SS / SS strings."""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", ".")
    if not s:
        raise EngineError(ErrorCode.INVALID_ARGS, "Thời gian trống")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    parts = s.split(":")
    if not all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        raise EngineError(
            ErrorCode.INVALID_ARGS,
            f"Định dạng thời gian không hợp lệ: {value!r} (dùng giây hoặc MM:SS / HH:MM:SS)",
        )
    if len(parts) == 2:
        m, sec = parts
        return int(m) * 60 + float(sec)
    if len(parts) == 3:
        h, m, sec = parts
        return int(h) * 3600 + int(m) * 60 + float(sec)
    raise EngineError(
        ErrorCode.INVALID_ARGS,
        f"Định dạng thời gian không hợp lệ: {value!r}",
    )


def _sanitize_filename(name: str) -> str:
    """Strip path separators and Windows-reserved characters from a file name."""
    s = name.strip().replace("\\", "/").split("/")[-1].strip()
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s)
    s = s.rstrip(". ")
    return s


def default_clip_stem(src: Path, start_sec: float, end_sec: float) -> str:
    """Suggested stem: `{source_stem}_clip_{start}-{end}`."""

    def _tag(t: float) -> str:
        if abs(t - round(t)) < 1e-6:
            return str(int(round(t)))
        return f"{t:.1f}".rstrip("0").rstrip(".")

    return f"{src.stem}_clip_{_tag(start_sec)}-{_tag(end_sec)}"


def default_clip_path(src: Path, start_sec: float, end_sec: float) -> Path:
    """Build `{stem}_clip_{start}-{end}{suffix}` next to the source video."""
    name = f"{default_clip_stem(src, start_sec, end_sec)}{src.suffix}"
    return src.parent / name


def named_clip_path(src: Path, name: str) -> Path:
    """
    Build an output path next to src using a user-provided name (stem or full file name).
    Keeps the source extension when the name has no/unsupported extension.
    """
    cleaned = _sanitize_filename(name)
    if not cleaned:
        raise EngineError(ErrorCode.INVALID_ARGS, "Tên video không được để trống")

    src_suffix = src.suffix.lower() or ".mp4"
    # If user typed an extension matching a known video type, keep it; else treat as stem.
    stem_part = Path(cleaned).stem
    typed_suffix = Path(cleaned).suffix.lower()

    if typed_suffix in VIDEO_EXTENSIONS:
        filename = f"{stem_part}{typed_suffix}"
    else:
        # "my clip" or "my.clip.extra" without real video ext → append source suffix
        filename = f"{cleaned}{src_suffix}" if not typed_suffix else f"{stem_part}{src_suffix}"

    filename = _sanitize_filename(filename)
    if not Path(filename).stem:
        raise EngineError(ErrorCode.INVALID_ARGS, "Tên video không hợp lệ")

    return unique_path(src.parent / filename)


def unique_path(path: Path) -> Path:
    """If path exists, append _2, _3, … before the suffix."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    n = 2
    while True:
        candidate = path.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def clone_video_segment(
    src: Path,
    start: str | float,
    end: str | float,
    *,
    output: Path | None = None,
    name: str | None = None,
    copy: bool = True,
) -> dict[str, Any]:
    """
    Cut [start, end) from an existing video into a new file and return probe info.

    Prefer ``output`` (full path). Else ``name`` (stem/filename next to source).
    Else default `{stem}_clip_{start}-{end}`.
    """
    src = Path(src).expanduser().resolve()
    if not src.is_file():
        raise EngineError(ErrorCode.INPUT_NOT_FOUND, f"Không tìm thấy video: {src}")
    if not is_video_file(src):
        raise EngineError(
            ErrorCode.UNSUPPORTED_FORMAT,
            f"Định dạng không hỗ trợ: {src.suffix}",
        )

    start_sec = parse_timestamp(start)
    end_sec = parse_timestamp(end)
    if output is not None:
        dst = unique_path(Path(output).expanduser().resolve())
    elif name and str(name).strip():
        dst = named_clip_path(src, str(name))
    else:
        dst = unique_path(default_clip_path(src, start_sec, end_sec))

    cut = extract_video_segment(src, dst, start_sec, end_sec, copy=copy)
    info = probe_video(dst)
    return {
        "ok": True,
        "path": cut["path"],
        "source": cut["source"],
        "start_sec": cut["start_sec"],
        "end_sec": cut["end_sec"],
        "duration_sec": info.get("duration_sec") or cut["duration_sec"],
        "duration_label": info.get("duration_label") or _fmt_duration(cut["duration_sec"]),
        "size_bytes": info.get("size_bytes") or 0,
        "size_label": info.get("size_label") or "—",
        "stem": info.get("stem") or Path(cut["path"]).stem,
        "name": info.get("name") or Path(cut["path"]).name,
        "copied": cut["copied"],
    }


def probe_video(path: Path) -> dict[str, Any]:
    p = path.expanduser().resolve()
    info: dict[str, Any] = {
        "path": str(p),
        "name": p.name,
        "stem": p.stem,
        "suffix": p.suffix.lower(),
        "exists": p.is_file(),
        "supported": is_video_file(p) if p.is_file() else False,
        "size_bytes": p.stat().st_size if p.is_file() else 0,
        "duration_sec": 0.0,
        "duration_label": "—",
        "size_label": "—",
        "video_codec": None,
        "audio_codec": None,
        "error": None,
    }
    if not p.is_file():
        info["error"] = "NOT_FOUND"
        return info
    info["size_label"] = _fmt_bytes(info["size_bytes"])
    try:
        dur = probe_duration(p)
        info["duration_sec"] = dur
        info["duration_label"] = _fmt_duration(dur)
        streams = probe_streams(p)
        for s in streams.get("streams") or []:
            if s.get("codec_type") == "video" and not info["video_codec"]:
                info["video_codec"] = s.get("codec_name")
            if s.get("codec_type") == "audio" and not info["audio_codec"]:
                info["audio_codec"] = s.get("codec_name")
    except Exception as e:
        info["error"] = str(e)
    return info


def probe_many(paths: list[Path]) -> list[dict[str, Any]]:
    return [probe_video(p) for p in paths]


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    if n < 1024**3:
        return f"{n / (1024**2):.1f} MB"
    return f"{n / (1024**3):.2f} GB"


def _fmt_duration(sec: float) -> str:
    if sec <= 0:
        return "—"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
