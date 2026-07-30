"""Probe media files for UI (duration, size) without loading Whisper."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .ffmpeg import probe_duration, probe_streams
from .queue import is_video_file


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
