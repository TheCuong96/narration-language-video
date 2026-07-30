"""Job workspace under %LOCALAPPDATA%/DubVI/jobs/<job-id>."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .system_info import job_dir, new_job_id


CANCEL_FLAG = "cancel.flag"
STATE_FILE = "job.json"


class CancellationToken:
    """Poll a flag file between long-running steps."""

    def __init__(self, root: Path):
        self.root = root
        self._flag = root / CANCEL_FLAG

    @property
    def path(self) -> Path:
        return self._flag

    def request_cancel(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._flag.write_text("1", encoding="utf-8")

    def clear(self) -> None:
        if self._flag.exists():
            self._flag.unlink()

    def is_cancelled(self) -> bool:
        return self._flag.exists()

    def check(self) -> None:
        if self.is_cancelled():
            from .models import ErrorCode
            from .system_info import EngineError

            raise EngineError(ErrorCode.CANCELLED, "Người dùng đã hủy tác vụ")


def request_cancel(job_id: str) -> Path:
    token = CancellationToken(job_dir(job_id))
    token.request_cancel()
    return token.path


def create_job(
    *,
    output_dir: Path,
    input_dir: Path | None = None,
    input_files: list[Path] | None = None,
    options: dict[str, Any] | None = None,
    job_id: str | None = None,
    clear_cancel: bool = True,
) -> tuple[str, Path]:
    jid = job_id or new_job_id()
    root = job_dir(jid)
    token = CancellationToken(root)
    if clear_cancel:
        token.clear()
    state = {
        "job_id": jid,
        "created_at": time.time(),
        "input_dir": str(input_dir.resolve()) if input_dir else None,
        "input_files": [str(p) for p in (input_files or [])],
        "output_dir": str(output_dir.resolve()),
        "status": "created",
        "options": options or {},
    }
    # Merge with existing state if resuming
    existing = load_job_state(jid)
    if existing:
        state = {**existing, **state, "created_at": existing.get("created_at", state["created_at"])}
    (root / STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return jid, root


def update_job_state(job_id: str, **fields: Any) -> None:
    root = job_dir(job_id)
    path = root / STATE_FILE
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data.update(fields)
    data["updated_at"] = time.time()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def video_work_dir(job_root: Path, video_stem: str) -> Path:
    """Per-video cache inside the job folder."""
    # Sanitize stem for filesystem while preserving Unicode
    safe = "".join(c if c not in '<>:"/\\|?*' else "_" for c in video_stem)
    d = job_root / "videos" / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_job_state(job_id: str) -> dict[str, Any] | None:
    path = job_dir(job_id) / STATE_FILE
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
