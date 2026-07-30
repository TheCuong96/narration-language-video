"""Translation review: read/edit Vietnamese segments before TTS."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import cache, events
from .jobs import video_work_dir
from .models import ErrorCode, Segment
from .system_info import EngineError, job_dir


def work_for_stem(job_id: str, stem: str) -> Path:
    return video_work_dir(job_dir(job_id), stem)


def get_review_payload(job_id: str, stem: str) -> dict[str, Any]:
    work = work_for_stem(job_id, stem)
    en_path = work / cache.TRANSCRIPT_EN
    vi_path = work / cache.TRANSCRIPT_VI
    en = cache.load_segments(en_path) or []
    vi = cache.load_segments(vi_path) or []
    by_id = {s.id: s for s in vi}
    merged: list[dict[str, Any]] = []
    source = vi if vi else en
    for s in source:
        en_seg = next((x for x in en if x.id == s.id), None)
        vi_seg = by_id.get(s.id, s)
        merged.append(
            {
                "id": s.id,
                "start": s.start,
                "end": s.end,
                "text_en": (en_seg.text_en if en_seg else s.text_en),
                "text_vi": vi_seg.text_vi,
            }
        )
    return {
        "job_id": job_id,
        "stem": stem,
        "work_dir": str(work),
        "transcript_en": str(en_path) if en_path.exists() else None,
        "transcript_vi": str(vi_path) if vi_path.exists() else None,
        "segments": merged,
    }


def save_translation(
    job_id: str,
    stem: str,
    segments_data: list[dict[str, Any]],
) -> Path:
    """
    Persist edited Vietnamese text. Invalidates TTS/narration cache so
    continue will regenerate voice from the new text.
    """
    if not segments_data:
        raise EngineError(ErrorCode.TRANSLATION_INVALID, "Danh sách đoạn dịch trống")

    work = work_for_stem(job_id, stem)
    en = cache.load_segments(work / cache.TRANSCRIPT_EN) or []
    en_by_id = {s.id: s for s in en}

    segments: list[Segment] = []
    for raw in segments_data:
        try:
            sid = int(raw["id"])
        except (KeyError, TypeError, ValueError) as e:
            raise EngineError(ErrorCode.TRANSLATION_INVALID, "Mỗi đoạn cần id hợp lệ") from e
        text_vi = str(raw.get("text_vi") or "").strip()
        if not text_vi:
            raise EngineError(
                ErrorCode.TRANSLATION_INVALID,
                f"Đoạn {sid} thiếu bản dịch tiếng Việt",
            )
        base = en_by_id.get(sid)
        segments.append(
            Segment(
                id=sid,
                start=float(raw.get("start", base.start if base else 0)),
                end=float(raw.get("end", base.end if base else 0)),
                text_en=str(raw.get("text_en") or (base.text_en if base else "")),
                text_vi=text_vi,
            )
        )

    out = work / cache.TRANSCRIPT_VI
    cache.save_segments(out, segments)

    # Invalidate downstream voice caches
    narr = work / cache.NARRATION
    if narr.exists():
        narr.unlink()
    for dname in (cache.SEGMENTS_DIR, cache.FITTED_DIR):
        d = work / dname
        if d.exists():
            import shutil

            shutil.rmtree(d, ignore_errors=True)

    script_path = work / cache.SCRIPT_VI
    lines = [f"[{s.start:.1f}-{s.end:.1f}] {s.text_vi}" for s in segments]
    script_path.write_text("\n".join(lines), encoding="utf-8")

    events.log(f"Đã lưu bản dịch đã sửa: {stem} ({len(segments)} đoạn)")
    return out


def load_translation_file(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise EngineError(ErrorCode.TRANSLATION_INVALID, "File dịch phải là JSON array")
    return data
