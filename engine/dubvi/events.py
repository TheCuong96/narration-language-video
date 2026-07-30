"""Structured JSON Lines events for UI / Tauri sidecar IPC."""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from typing import Any

from .models import ErrorCode, Stage

_lock = threading.Lock()
_json_mode = True


def set_json_mode(enabled: bool) -> None:
    global _json_mode
    _json_mode = enabled


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict[str, Any]) -> None:
    """Write one JSON object per line to stdout (never mixed with free text)."""
    data = {"ts": _now(), **payload}
    line = json.dumps(data, ensure_ascii=False)
    with _lock:
        if _json_mode:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        else:
            # Human-readable fallback for legacy CLI
            t = data.get("type", "")
            msg = data.get("message") or data.get("stage") or ""
            sys.stderr.write(f"[{t}] {msg}\n")
            sys.stderr.flush()


def stage(stage_name: Stage | str, message: str = "", **extra: Any) -> None:
    name = stage_name.value if isinstance(stage_name, Stage) else stage_name
    emit({"type": "stage", "stage": name, "message": message, **extra})


def progress(
    stage_name: Stage | str,
    current: int,
    total: int,
    message: str = "",
    **extra: Any,
) -> None:
    name = stage_name.value if isinstance(stage_name, Stage) else stage_name
    emit(
        {
            "type": "progress",
            "stage": name,
            "current": current,
            "total": total,
            "message": message,
            **extra,
        }
    )


def log(message: str, level: str = "info", **extra: Any) -> None:
    emit({"type": "log", "level": level, "message": message, **extra})


def file_completed(input_path: str, output_path: str, **extra: Any) -> None:
    emit(
        {
            "type": "file_completed",
            "input": input_path,
            "output": output_path,
            **extra,
        }
    )


def error(
    code: ErrorCode | str,
    message: str,
    *,
    fatal: bool = False,
    **extra: Any,
) -> None:
    c = code.value if isinstance(code, ErrorCode) else code
    try:
        from .errors_ui import friendly_error

        fe = friendly_error(c, message)
        friendly = {"title": fe.title, "body": fe.message, "hint": fe.hint}
    except Exception:
        friendly = None
    payload: dict[str, Any] = {
        "type": "error",
        "code": c,
        "message": message,
        "fatal": fatal,
        **extra,
    }
    if friendly:
        payload["friendly"] = friendly
    emit(payload)


def completed(output: str | None = None, **extra: Any) -> None:
    emit({"type": "completed", "output": output, **extra})


def cancelled(message: str = "Job cancelled") -> None:
    emit({"type": "cancelled", "code": ErrorCode.CANCELLED.value, "message": message})


def system(info: dict[str, Any]) -> None:
    emit({"type": "system", **info})


def warning(code: str, message: str, **extra: Any) -> None:
    emit({"type": "warning", "code": code, "message": message, **extra})


def review_ready(
    *,
    job_id: str,
    stem: str,
    transcript_path: str,
    segments: list[dict[str, Any]],
    message: str = "Xem và sửa bản dịch trước khi tạo giọng",
) -> None:
    emit(
        {
            "type": "review_ready",
            "job_id": job_id,
            "stem": stem,
            "transcript_path": transcript_path,
            "segments": segments,
            "message": message,
            "code": ErrorCode.REVIEW_PENDING.value,
        }
    )


def queue_updated(queue: dict[str, Any]) -> None:
    emit({"type": "queue_updated", "queue": queue})
