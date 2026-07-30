"""Disk cache for resume-after-stop (transcripts, TTS segments, narration)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .models import Segment
from .system_info import get_logger

log = get_logger("dubvi.cache")

TRANSCRIPT_EN = "transcript_en.json"
TRANSCRIPT_VI = "transcript_vi.json"
SCRIPT_VI = "script_vi.txt"
AUDIO_FLAC = "audio.flac"
NARRATION = "narration.wav"
SEGMENTS_DIR = "segments"
FITTED_DIR = "fitted"


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_segments(path: Path, segments: list[Segment]) -> None:
    save_json(path, [s.to_dict() for s in segments])


def load_segments(path: Path) -> list[Segment] | None:
    raw = load_json(path)
    if raw is None:
        return None
    return [Segment.from_dict(x) for x in raw]


def clear_downstream(work: Path, *, keep_en: bool = True) -> None:
    """Clear caches that depend on later stages (for --force)."""
    for name in (TRANSCRIPT_VI, SCRIPT_VI, NARRATION, "concat.txt"):
        p = work / name
        if p.exists():
            p.unlink()
    if not keep_en:
        p = work / TRANSCRIPT_EN
        if p.exists():
            p.unlink()
        audio = work / AUDIO_FLAC
        if audio.exists():
            audio.unlink()
    for dname in (FITTED_DIR, SEGMENTS_DIR):
        d = work / dname
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


def cleanup_temps_after_success(work: Path, *, keep_transcripts: bool = True) -> None:
    """
    After successful mux: remove bulky temps, keep transcripts for re-run insight.
    On failure the caller must NOT call this.
    """
    for name in (AUDIO_FLAC, NARRATION, "concat.txt"):
        p = work / name
        if p.exists():
            try:
                p.unlink()
            except OSError as e:
                log.warning("cleanup %s: %s", p, e)
    for dname in (FITTED_DIR, SEGMENTS_DIR):
        d = work / dname
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    if not keep_transcripts:
        for name in (TRANSCRIPT_EN, TRANSCRIPT_VI, SCRIPT_VI):
            p = work / name
            if p.exists():
                p.unlink()
