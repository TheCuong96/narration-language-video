from __future__ import annotations

from pathlib import Path

from dubvi import queue
from dubvi.models import QueueItemStatus
from dubvi.system_info import job_dir


def test_mark_active_cancelled_and_resumable(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    job_id = "resume123abc"
    root = job_dir(job_id)
    assert root.exists()

    videos = [
        tmp_path / "a.mp4",
        tmp_path / "b.mp4",
        tmp_path / "c.mp4",
    ]
    for v in videos:
        v.write_bytes(b"x")

    out = tmp_path / "out"
    out.mkdir()
    q = queue.init_queue(job_id, videos, out)
    assert [i["status"] for i in q["items"]] == ["pending", "pending", "pending"]

    queue.update_item(job_id, "a", status=QueueItemStatus.RUNNING)
    queue.update_item(job_id, "b", status=QueueItemStatus.COMPLETED)
    queue.update_item(job_id, "c", status=QueueItemStatus.PENDING)

    marked = queue.mark_active_cancelled(job_id)
    assert marked is not None
    by_stem = {i["stem"]: i["status"] for i in marked["items"]}
    assert by_stem["a"] == QueueItemStatus.CANCELLED.value
    assert by_stem["b"] == QueueItemStatus.COMPLETED.value
    assert by_stem["c"] == QueueItemStatus.PENDING.value

    stems = queue.resumable_stems(job_id)
    assert stems == ["a", "c"]


def test_resumable_includes_failed_excludes_review(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    job_id = "resume456def"
    videos = [tmp_path / "x.mp4", tmp_path / "y.mp4"]
    for v in videos:
        v.write_bytes(b"x")
    out = tmp_path / "out"
    out.mkdir()
    queue.init_queue(job_id, videos, out)
    queue.update_item(job_id, "x", status=QueueItemStatus.FAILED)
    queue.update_item(job_id, "y", status=QueueItemStatus.REVIEW)

    assert queue.resumable_stems(job_id) == ["x"]
    assert "y" in queue.pending_or_failed(job_id)
