"""Input discovery and persistent queue state for sequential jobs."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .models import VIDEO_EXTENSIONS, ErrorCode, QueueItemStatus
from .system_info import EngineError, get_logger, job_dir

log = get_logger("dubvi.queue")

QUEUE_FILE = "queue.json"


def is_video_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def resolve_inputs(
    *,
    input_dir: Path | None = None,
    input_files: list[Path] | None = None,
    only: list[str] | None = None,
) -> list[Path]:
    """
    Resolve one video, many videos, or a folder of supported formats.
    Dedupes while preserving order.
    """
    found: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        try:
            rp = p.expanduser().resolve()
        except OSError as e:
            raise EngineError(ErrorCode.INPUT_NOT_FOUND, f"Đường dẫn không hợp lệ: {p}") from e
        key = str(rp).lower()
        if key in seen:
            return
        if not is_video_file(rp):
            raise EngineError(
                ErrorCode.UNSUPPORTED_FORMAT,
                f"Định dạng không hỗ trợ hoặc không phải video: {rp.name}",
            )
        seen.add(key)
        found.append(rp)

    for f in input_files or []:
        p = Path(f)
        if p.is_dir():
            # Allow dropping a folder among files
            for child in sorted(p.iterdir()):
                if is_video_file(child):
                    add(child)
        else:
            add(p)

    if input_dir is not None:
        d = input_dir.expanduser().resolve()
        if not d.is_dir():
            raise EngineError(ErrorCode.INPUT_NOT_FOUND, f"Không tìm thấy thư mục: {d}")
        for ext in VIDEO_EXTENSIONS:
            for child in sorted(d.glob(f"*{ext}")):
                add(child)
            for child in sorted(d.glob(f"*{ext.upper()}")):
                add(child)

    if only:
        keys = {k.lower() for k in only}
        found = [
            v
            for v in found
            if v.stem.lower() in keys or any(k in v.stem.lower() for k in keys)
        ]

    if not found:
        raise EngineError(
            ErrorCode.NO_VIDEOS,
            "Không có video phù hợp (MP4, MKV, MOV, AVI, WebM)",
        )
    return found


def output_path_for(video: Path, output_dir: Path) -> Path:
    """Prefer .mp4 output; keep mkv if source is mkv for dual-track friendliness."""
    suffix = ".mp4"
    if video.suffix.lower() == ".mkv":
        suffix = ".mkv"
    return output_dir / f"{video.stem}{suffix}"


def load_queue(job_id: str) -> dict[str, Any] | None:
    path = job_dir(job_id) / QUEUE_FILE
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_queue(job_id: str, data: dict[str, Any]) -> Path:
    root = job_dir(job_id)
    path = root / QUEUE_FILE
    data["updated_at"] = time.time()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def init_queue(job_id: str, videos: list[Path], output_dir: Path) -> dict[str, Any]:
    items = []
    for i, v in enumerate(videos):
        out = output_path_for(v, output_dir)
        items.append(
            {
                "index": i,
                "input": str(v),
                "output": str(out),
                "stem": v.stem,
                "status": QueueItemStatus.PENDING.value,
                "error": None,
                "code": None,
            }
        )
    data = {"job_id": job_id, "items": items, "created_at": time.time()}
    save_queue(job_id, data)
    return data


def update_item(
    job_id: str,
    stem: str,
    *,
    status: QueueItemStatus | str,
    error: str | None = None,
    code: str | None = None,
    output: str | None = None,
) -> dict[str, Any]:
    data = load_queue(job_id) or {"job_id": job_id, "items": []}
    st = status.value if isinstance(status, QueueItemStatus) else status
    for item in data["items"]:
        if item["stem"] == stem:
            item["status"] = st
            if error is not None:
                item["error"] = error
            if code is not None:
                item["code"] = code
            if output is not None:
                item["output"] = output
            break
    save_queue(job_id, data)
    return data


def failed_stems(job_id: str) -> list[str]:
    data = load_queue(job_id)
    if not data:
        return []
    return [i["stem"] for i in data["items"] if i.get("status") == QueueItemStatus.FAILED.value]


def pending_or_failed(job_id: str) -> list[str]:
    data = load_queue(job_id)
    if not data:
        return []
    want = {
        QueueItemStatus.PENDING.value,
        QueueItemStatus.FAILED.value,
        QueueItemStatus.REVIEW.value,
        QueueItemStatus.CANCELLED.value,
    }
    return [i["stem"] for i in data["items"] if i.get("status") in want]


def resumable_stems(job_id: str) -> list[str]:
    """Stems that can continue after stop/cancel (same job, StartFrom.AUTO).

    Includes cancelled, stuck running (hard-kill), pending, and failed.
    Review items keep the dedicated continue-after-review path.
    """
    data = load_queue(job_id)
    if not data:
        return []
    want = {
        QueueItemStatus.PENDING.value,
        QueueItemStatus.FAILED.value,
        QueueItemStatus.CANCELLED.value,
        QueueItemStatus.RUNNING.value,
    }
    return [i["stem"] for i in data["items"] if i.get("status") in want]


def mark_active_cancelled(job_id: str) -> dict[str, Any] | None:
    """Mark running items as cancelled so UI/resume can continue them."""
    data = load_queue(job_id)
    if not data:
        return None
    changed = False
    for item in data["items"]:
        if item.get("status") == QueueItemStatus.RUNNING.value:
            item["status"] = QueueItemStatus.CANCELLED.value
            changed = True
    if changed:
        save_queue(job_id, data)
    return data


def append_videos(
    job_id: str,
    videos: list[Path],
    output_dir: Path,
) -> tuple[dict[str, Any], list[Path]]:
    """
    Append new videos as pending items to a live job queue.
    Skips paths already in the queue. Rejects duplicate stems (work-dir clash).
    Returns (queue_data, newly_added_paths).
    """
    data = load_queue(job_id) or {
        "job_id": job_id,
        "items": [],
        "created_at": time.time(),
    }
    items: list[dict[str, Any]] = list(data.get("items") or [])
    existing_paths = set()
    existing_stems = set()
    for it in items:
        raw = it.get("input") or ""
        try:
            existing_paths.add(str(Path(raw).expanduser().resolve()).lower())
        except OSError:
            existing_paths.add(str(raw).lower())
        existing_stems.add(str(it.get("stem") or "").lower())

    added: list[Path] = []
    for v in videos:
        try:
            rp = v.expanduser().resolve()
        except OSError as e:
            raise EngineError(ErrorCode.INPUT_NOT_FOUND, f"Đường dẫn không hợp lệ: {v}") from e
        if not is_video_file(rp):
            raise EngineError(
                ErrorCode.UNSUPPORTED_FORMAT,
                f"Định dạng không hỗ trợ hoặc không phải video: {rp.name}",
            )
        key = str(rp).lower()
        if key in existing_paths:
            continue
        stem = rp.stem
        if stem.lower() in existing_stems:
            raise EngineError(
                ErrorCode.UNSUPPORTED_FORMAT,
                f"Đã có video cùng tên «{stem}» trong hàng đợi — đổi tên file rồi thêm lại.",
            )
        out = output_path_for(rp, output_dir)
        items.append(
            {
                "index": len(items),
                "input": str(rp),
                "output": str(out),
                "stem": stem,
                "status": QueueItemStatus.PENDING.value,
                "error": None,
                "code": None,
            }
        )
        existing_paths.add(key)
        existing_stems.add(stem.lower())
        added.append(rp)

    # Re-index for stable UI ordering
    for i, it in enumerate(items):
        it["index"] = i
    data["items"] = items
    data["job_id"] = job_id
    save_queue(job_id, data)
    return data, added


def next_work_item(
    job_id: str,
    *,
    also_stems: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Next queue item to process for a live/resume job.

    Always picks pending items (including videos appended mid-run).
    Also picks cancelled/failed/running stems listed in also_stems (resume/retry).
    """
    data = load_queue(job_id)
    if not data:
        return None
    also = {s.lower() for s in (also_stems or [])}
    resume_statuses = {
        QueueItemStatus.CANCELLED.value,
        QueueItemStatus.FAILED.value,
        QueueItemStatus.RUNNING.value,
    }
    for item in data.get("items") or []:
        st = item.get("status")
        stem = str(item.get("stem") or "")
        if st == QueueItemStatus.PENDING.value:
            return item
        if stem.lower() in also and st in resume_statuses:
            return item
    return None
